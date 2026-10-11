"""Limited SELECT evaluator over fixed built-in tables; never opens a database."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from sql_sample_data import SAMPLE_TABLES

MAX_QUERY_LENGTH = 20_000
MAX_TOKEN_COUNT = 2_000
MAX_RESULT_ROWS = 1_000
RESULT_LABEL = "Predicted Result — Computed from Built-in Sample Data (Not Executed Against a Database)"
RESULT_NOTE = (
    "Illustrative results use only BugWise AI's built-in sample data. They may differ from "
    "your actual database's schema, data, SQL dialect, or query behavior."
)
UNAVAILABLE_MESSAGE = (
    "SQL result prediction is unavailable for this query. Only the documented built-in "
    "sample-query subset is supported; the query was not executed."
)


class _Unsupported(Exception):
    pass


@dataclass(frozen=True)
class _Token:
    kind: str
    value: str


@dataclass(frozen=True)
class _Ref:
    qualifier: str | None
    column: str


def _unavailable() -> dict[str, Any]:
    return {
        "status": "unavailable",
        "output": "",
        "columns": [],
        "rows": [],
        "label": RESULT_LABEL,
        "message": UNAVAILABLE_MESSAGE,
    }


def _tokenize(source: str) -> list[_Token]:
    tokens: list[_Token] = []
    index = 0
    while index < len(source):
        char = source[index]
        following = source[index + 1] if index + 1 < len(source) else ""
        if char.isspace():
            index += 1
            continue
        if char == "-" and following == "-":
            while index < len(source) and source[index] != "\n":
                index += 1
            continue
        if char == "/" and following == "*":
            end = source.find("*/", index + 2)
            if end < 0:
                raise _Unsupported()
            index = end + 2
            continue
        if char == "'":
            index += 1
            value: list[str] = []
            while index < len(source):
                if source[index] == "'":
                    if index + 1 < len(source) and source[index + 1] == "'":
                        value.append("'")
                        index += 2
                        continue
                    index += 1
                    break
                if source[index] in "\r\n":
                    raise _Unsupported()
                value.append(source[index])
                index += 1
            else:
                raise _Unsupported()
            tokens.append(_Token("string", "".join(value)))
            continue
        if char.isalpha() or char == "_":
            end = index + 1
            while end < len(source) and (source[end].isalnum() or source[end] in "_$"):
                end += 1
            tokens.append(_Token("word", source[index:end]))
            index = end
            continue
        if char.isdigit() or (char in "+-" and following.isdigit()):
            end = index + (1 if char in "+-" else 0)
            while end < len(source) and source[end].isdigit():
                end += 1
            digits = source[index:end]
            if len(digits.lstrip("+-")) > 10:
                raise _Unsupported()
            tokens.append(_Token("integer", digits))
            index = end
            continue
        pair = source[index:index + 2]
        if pair in {"<=", ">=", "!=", "<>"}:
            tokens.append(_Token("operator", pair))
            index += 2
            continue
        if char in "=<>":
            tokens.append(_Token("operator", char))
            index += 1
            continue
        if char in "*(),.;":
            tokens.append(_Token(char, char))
            index += 1
            continue
        raise _Unsupported()
    if not tokens or len(tokens) > MAX_TOKEN_COUNT:
        raise _Unsupported()
    return tokens


@dataclass(frozen=True)
class _Item:
    kind: str
    reference: _Ref | None
    alias: str | None = None


@dataclass(frozen=True)
class _Join:
    table: str
    alias: str
    left: _Ref
    right: _Ref


class _Parser:
    _CLAUSE_WORDS = {"FROM", "WHERE", "INNER", "JOIN", "GROUP", "ORDER", "LIMIT", "ASC", "DESC"}
    _AGGREGATES = {"COUNT", "SUM", "AVG", "MIN", "MAX"}

    def __init__(self, tokens: list[_Token]):
        self.tokens = tokens
        self.position = 0

    def current(self) -> _Token | None:
        return self.tokens[self.position] if self.position < len(self.tokens) else None

    def take(self, kind: str, value: str | None = None) -> _Token:
        token = self.current()
        if token is None or token.kind != kind or (value is not None and token.value.upper() != value):
            raise _Unsupported()
        self.position += 1
        return token

    def accept(self, kind: str, value: str | None = None) -> bool:
        token = self.current()
        if token is None or token.kind != kind or (value is not None and token.value.upper() != value):
            return False
        self.position += 1
        return True

    def ref(self) -> _Ref:
        first = self.take("word").value.lower()
        if self.accept("."):
            return _Ref(first, self.take("word").value.lower())
        return _Ref(None, first)

    def item(self) -> _Item:
        if self.accept("*"):
            item = _Item("star", None)
        elif self.current() and self.current().kind == "word" and self.current().value.upper() in self._AGGREGATES:
            aggregate = self.take("word").value.lower()
            self.take("(")
            reference = None if aggregate == "count" and self.accept("*") else self.ref()
            self.take(")")
            item = _Item(aggregate, reference)
        else:
            item = _Item("column", self.ref())
        alias = None
        if self.accept("word", "AS"):
            alias = self.take("word").value
        elif self.current() and self.current().kind == "word" and self.current().value.upper() not in self._CLAUSE_WORDS | {"AND", "OR", "ON", "USING"}:
            alias = self.take("word").value
        return _Item(item.kind, item.reference, alias)

    def value(self) -> Any:
        token = self.current()
        if token is None:
            raise _Unsupported()
        if token.kind == "string":
            self.position += 1
            return token.value
        if token.kind == "integer":
            self.position += 1
            return int(token.value)
        if token.kind == "word" and token.value.upper() in {"TRUE", "FALSE"}:
            self.position += 1
            return token.value.upper() == "TRUE"
        return self.ref()

    def predicate_atom(self):
        if self.accept("("):
            predicate = self.predicate_or()
            self.take(")")
            return predicate
        left = self.ref()
        operator = self.take("operator").value
        right = self.value()
        return ("compare", left, operator, right)

    def predicate_and(self):
        result = self.predicate_atom()
        while self.accept("word", "AND"):
            result = ("and", result, self.predicate_atom())
        return result

    def predicate_or(self):
        result = self.predicate_and()
        while self.accept("word", "OR"):
            result = ("or", result, self.predicate_and())
        return result

    def parse(self) -> dict[str, Any]:
        self.take("word", "SELECT")
        distinct = self.accept("word", "DISTINCT")
        items = [self.item()]
        while self.accept(","):
            items.append(self.item())
        if any(item.kind == "star" for item in items) and len(items) != 1:
            raise _Unsupported()

        self.take("word", "FROM")
        table = self.take("word").value.lower()
        alias = table
        if self.accept("word", "AS"):
            alias = self.take("word").value.lower()
        elif self.current() and self.current().kind == "word" and self.current().value.upper() not in self._CLAUSE_WORDS | {"ON", "USING"}:
            alias = self.take("word").value.lower()

        join = None
        if self.accept("word", "INNER"):
            self.take("word", "JOIN")
            join_table = self.take("word").value.lower()
            join_alias = join_table
            if self.accept("word", "AS"):
                join_alias = self.take("word").value.lower()
            elif self.current() and self.current().kind == "word" and self.current().value.upper() != "ON":
                join_alias = self.take("word").value.lower()
            self.take("word", "ON")
            left = self.ref()
            self.take("operator", "=")
            right = self.ref()
            join = _Join(join_table, join_alias, left, right)
        elif self.accept("word", "JOIN"):
            raise _Unsupported()

        where = self.predicate_or() if self.accept("word", "WHERE") else None
        group_by = []
        if self.accept("word", "GROUP"):
            self.take("word", "BY")
            group_by.append(self.ref())
            while self.accept(","):
                group_by.append(self.ref())

        order_by = []
        if self.accept("word", "ORDER"):
            self.take("word", "BY")
            while True:
                ref = self.ref()
                descending = self.accept("word", "DESC")
                if not descending:
                    self.accept("word", "ASC")
                order_by.append((ref, descending))
                if not self.accept(","):
                    break

        limit = None
        if self.accept("word", "LIMIT"):
            limit = int(self.take("integer").value)
            if limit < 0:
                raise _Unsupported()
        self.accept(";")
        if self.current() is not None:
            raise _Unsupported()
        return {
            "distinct": distinct,
            "items": items,
            "table": table,
            "alias": alias,
            "join": join,
            "where": where,
            "group_by": group_by,
            "order_by": order_by,
            "limit": limit,
        }


def _rows(table: str, alias: str) -> list[dict[str, Any]]:
    if table not in SAMPLE_TABLES:
        raise _Unsupported()
    data = SAMPLE_TABLES[table]
    result = []
    for values in data["rows"]:
        row = {}
        for column, value in zip(data["columns"], values):
            row[f"{alias}.{column}"] = value
            row[f"{table}.{column}"] = value
            row[column] = value if column not in row else None
        result.append(row)
    return result


def _resolve(ref: _Ref, row: dict[str, Any]) -> Any:
    key = f"{ref.qualifier}.{ref.column}" if ref.qualifier else ref.column
    if key not in row or row[key] is None:
        raise _Unsupported()
    return row[key]


def _merge(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    result = {key: value for key, value in left.items() if "." in key}
    result.update({key: value for key, value in right.items() if "." in key})
    columns = {key for key in left.keys() | right.keys() if "." not in key}
    for column in columns:
        lv, rv = left.get(column), right.get(column)
        if column in left and column in right:
            result[column] = None
        elif column in left:
            result[column] = lv
        else:
            result[column] = rv
    return result


def _compare(left: Any, operator: str, right: Any) -> bool:
    if type(left) is not type(right):
        raise _Unsupported()
    operations = {
        "=": lambda: left == right,
        "==": lambda: left == right,
        "!=": lambda: left != right,
        "<>": lambda: left != right,
        "<": lambda: left < right,
        ">": lambda: left > right,
        "<=": lambda: left <= right,
        ">=": lambda: left >= right,
    }
    if operator not in operations:
        raise _Unsupported()
    return operations[operator]()


def _matches(node: Any, row: dict[str, Any]) -> bool:
    if node[0] == "and":
        return _matches(node[1], row) and _matches(node[2], row)
    if node[0] == "or":
        return _matches(node[1], row) or _matches(node[2], row)
    left = _resolve(node[1], row)
    right = _resolve(node[3], row) if isinstance(node[3], _Ref) else node[3]
    return _compare(left, node[2], right)


def _label(item: _Item) -> str:
    if item.alias:
        return item.alias
    if item.kind == "star":
        return "*"
    if item.kind == "column":
        return item.reference.column
    arg = "*" if item.reference is None else item.reference.column
    return f"{item.kind.upper()}({arg})"


def _aggregate(kind: str, values: list[Any]) -> Any:
    if kind == "count":
        return sum(value is not None for value in values)
    if not values:
        return None
    if kind in {"sum", "avg"} and any(type(value) is not int for value in values):
        raise _Unsupported()
    if kind == "sum":
        return sum(values)
    if kind == "avg":
        return sum(values) / len(values)
    if kind == "min":
        return min(values)
    if kind == "max":
        return max(values)
    raise _Unsupported()


def _evaluate(query: dict[str, Any]) -> tuple[list[str], list[list[Any]]]:
    table, alias = query["table"], query["alias"]
    rows = _rows(table, alias)
    join = query["join"]
    if join:
        if {table, join.table} != {"students", "departments"} or table == join.table:
            raise _Unsupported()
        joined = []
        for left in rows:
            for right in _rows(join.table, join.alias):
                row = _merge(left, right)
                if _compare(_resolve(join.left, row), "=", _resolve(join.right, row)):
                    joined.append(row)
        rows = joined

    if query["where"] is not None:
        rows = [row for row in rows if _matches(query["where"], row)]

    items: list[_Item] = query["items"]
    if items[0].kind == "star":
        if join:
            raise _Unsupported()
        columns = list(SAMPLE_TABLES[table]["columns"])
        records = [{"values": [_resolve(_Ref(None, col), row) for col in columns], "source": row} for row in rows]
    else:
        columns = [_label(item) for item in items]
        if len(set(columns)) != len(columns):
            raise _Unsupported()
        aggregates = [item for item in items if item.kind in {"count", "sum", "avg", "min", "max"}]
        group_by: list[_Ref] = query["group_by"]
        if aggregates or group_by:
            ordinary = [item for item in items if item.kind == "column"]
            if ordinary and not group_by:
                raise _Unsupported()
            if group_by and any(item.reference not in group_by for item in ordinary):
                raise _Unsupported()
            groups: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
            for row in rows:
                group_key = tuple(_resolve(ref, row) for ref in group_by)
                groups.setdefault(group_key, []).append(row)
            if aggregates and not group_by:
                group_rows = [rows]
            else:
                group_rows = list(groups.values())
            records = []
            for group in group_rows:
                representative = group[0] if group else {}
                values = []
                for item in items:
                    if item.kind == "column":
                        values.append(_resolve(item.reference, representative))
                    else:
                        inputs = [1 for _ in group] if item.reference is None else [
                            _resolve(item.reference, row) for row in group
                        ]
                        values.append(_aggregate(item.kind, inputs))
                records.append({"values": values, "source": representative})
        else:
            records = [
                {"values": [_resolve(item.reference, row) for item in items], "source": row}
                for row in rows
            ]

    order_by = query["order_by"]
    for ref, descending in reversed(order_by):
        if ref.qualifier is None and ref.column in columns:
            index = columns.index(ref.column)
            records.sort(key=lambda record: (record["values"][index] is None, record["values"][index]), reverse=descending)
        else:
            records.sort(key=lambda record: _resolve(ref, record["source"]), reverse=descending)
    if query["distinct"]:
        unique = []
        seen = set()
        for record in records:
            key = tuple(record["values"])
            if key not in seen:
                seen.add(key)
                unique.append(record)
        records = unique
    if query["limit"] is not None:
        records = records[:query["limit"]]
    if len(records) > MAX_RESULT_ROWS:
        raise _Unsupported()
    return columns, [record["values"] for record in records]


def predict_sql_query(query: str) -> dict[str, Any]:
    if not isinstance(query, str) or not query.strip() or len(query) > MAX_QUERY_LENGTH:
        return _unavailable()
    try:
        parsed = _Parser(_tokenize(query)).parse()
        columns, rows = _evaluate(parsed)
    except (_Unsupported, ArithmeticError, TypeError, ValueError, RecursionError):
        return _unavailable()
    return {
        "status": "predicted",
        "output": "",
        "columns": columns,
        "rows": rows,
        "label": RESULT_LABEL,
        "message": RESULT_NOTE,
    }
