"""Conservative SQL linting and text-only suggestions; submitted SQL is never executed."""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass
from typing import Any

from sql_predictor import UNAVAILABLE_MESSAGE, predict_sql_query

_MAX_SOURCE_LENGTH = 50_000
_MAX_TOKENS = 5_000
_KEYWORD_TYPOS = {
    "SELEC": "SELECT",
    "SELCT": "SELECT",
    "SELET": "SELECT",
    "FORM": "FROM",
    "FRM": "FROM",
    "WHRE": "WHERE",
    "WHER": "WHERE",
    "GRUP": "GROUP",
    "ORDR": "ORDER",
    "JON": "JOIN",
    "JION": "JOIN",
}
_CLAUSES = {"AS", "WHERE", "GROUP", "HAVING", "ORDER", "LIMIT", "OFFSET", "UNION", "JOIN", "ON"}
_AGGREGATES = {"COUNT", "SUM", "AVG", "MIN", "MAX"}


@dataclass(frozen=True)
class _Token:
    kind: str
    value: str
    start: int
    end: int


def _finding(
    error_type: str,
    message: str,
    source: str,
    offset: int,
    next_action: str,
    confidence: str,
    category: str = "static",
    replacement: tuple[int, int, str] | None = None,
) -> dict[str, Any]:
    line_number = source.count("\n", 0, offset) + 1
    line_start = source.rfind("\n", 0, offset) + 1
    line_end = source.find("\n", offset)
    if line_end < 0:
        line_end = len(source)
    result = {
        "category": category,
        "error_type": error_type,
        "message": message,
        "line_number": line_number,
        "next_action": next_action,
        "confidence": confidence,
        "source_line": source[line_start:line_end],
    }
    if replacement is not None:
        result["replacement"] = replacement
    return result


def _scan(source: str) -> tuple[list[_Token], str, list[dict[str, Any]]]:
    tokens: list[_Token] = []
    masked = list(source)
    findings: list[dict[str, Any]] = []
    index = 0
    length = len(source)
    while index < length:
        char = source[index]
        following = source[index + 1] if index + 1 < length else ""
        if char.isspace():
            index += 1
            continue
        if char == "-" and following == "-":
            start = index
            while index < length and source[index] != "\n":
                masked[index] = " "
                index += 1
            continue
        if char == "/" and following == "*":
            start = index
            end = source.find("*/", index + 2)
            if end < 0:
                findings.append(
                    _finding(
                        "SQLUnclosedComment",
                        "A block comment is not closed.",
                        source,
                        start,
                        "Close the comment with */ before the following query text.",
                        "High confidence for an unterminated block comment.",
                        replacement=(length, length, "*/"),
                    )
                )
                for position in range(start, length):
                    if source[position] != "\n":
                        masked[position] = " "
                break
            for position in range(start, end + 2):
                if source[position] != "\n":
                    masked[position] = " "
            index = end + 2
            continue
        if char in "'\"`[":
            start = index
            closing = "]" if char == "[" else char
            index += 1
            content_start = index
            closed = False
            while index < length:
                if source[index] == closing:
                    if closing in "'\"`" and index + 1 < length and source[index + 1] == closing:
                        index += 2
                        continue
                    closed = True
                    break
                index += 1
            if not closed:
                findings.append(
                    _finding(
                        "SQLUnclosedQuote",
                        "A quoted SQL string or identifier is not closed.",
                        source,
                        start,
                        f"Add the matching {closing!r} delimiter.",
                        "High confidence for this unterminated quoted value.",
                        replacement=(length, length, closing),
                    )
                )
                for position in range(start, length):
                    if source[position] != "\n":
                        masked[position] = " "
                break
            value = source[content_start:index]
            index += 1
            kind = "quoted_identifier" if char in '`[' or char == '"' else "string"
            tokens.append(_Token(kind, value, start, index))
            for position in range(start, index):
                if source[position] != "\n":
                    masked[position] = " "
            continue
        if char.isalpha() or char == "_":
            start = index
            index += 1
            while index < length and (source[index].isalnum() or source[index] in "_$"):
                index += 1
            tokens.append(_Token("word", source[start:index], start, index))
            continue
        if char.isdigit():
            start = index
            index += 1
            while index < length and (source[index].isdigit() or source[index] == "."):
                index += 1
            tokens.append(_Token("number", source[start:index], start, index))
            continue
        if char in ",().;*+-/%=<>!":
            start = index
            index += 1
            if index < length and source[start:index + 1] in {"<=", ">=", "!=", "<>"}:
                index += 1
            tokens.append(_Token("symbol", source[start:index], start, index))
            continue
        tokens.append(_Token("other", char, index, index + 1))
        index += 1
        if len(tokens) > _MAX_TOKENS:
            break
    if len(tokens) > _MAX_TOKENS:
        findings.append(
            _finding(
                "SQLInputLimit",
                "The query exceeds the SQL analysis token limit.",
                source,
                0,
                "Reduce the query size before requesting static analysis.",
                "Certain: analysis stopped at the configured token limit.",
                category="unsupported",
            )
        )
    return tokens[:_MAX_TOKENS], "".join(masked), findings


def _depths_and_delimiters(
    source: str,
    tokens: list[_Token],
) -> tuple[dict[int, int], list[dict[str, Any]]]:
    depth_at: dict[int, int] = {}
    stack: list[_Token] = []
    findings: list[dict[str, Any]] = []
    for index, token in enumerate(tokens):
        if token.value == "(":
            stack.append(token)
            depth_at[index] = len(stack)
        elif token.value == ")":
            if stack:
                depth_at[index] = len(stack) - 1
                stack.pop()
            else:
                findings.append(
                    _finding(
                        "SQLUnmatchedParenthesis",
                        "A closing parenthesis has no matching opening parenthesis.",
                        source,
                        token.start,
                        "Remove the extra ) or add its intended opening parenthesis.",
                        "High confidence for an unmatched closing parenthesis.",
                    )
                )
        else:
            depth_at[index] = len(stack)
    for token in stack:
        findings.append(
            _finding(
                "SQLUnmatchedParenthesis",
                "An opening parenthesis is not closed.",
                source,
                token.start,
                "Add the matching ) after the complete expression.",
                "High confidence for an unmatched opening parenthesis.",
                replacement=(len(source), len(source), ")"),
            )
        )
    return depth_at, findings


def _keyword_typo_findings(
    source: str,
    tokens: list[_Token],
) -> tuple[list[dict[str, Any]], list[_Token]]:
    findings: list[dict[str, Any]] = []
    normalized = list(tokens)
    for index, token in enumerate(tokens):
        if token.kind != "word":
            continue
        upper = token.value.upper()
        expected = _KEYWORD_TYPOS.get(upper)
        if expected is None:
            continue
        next_token = tokens[index + 1] if index + 1 < len(tokens) else None
        previous_words = [
            _KEYWORD_TYPOS.get(item.value.upper(), item.value.upper())
            for item in tokens[max(0, index - 3):index]
            if item.kind == "word"
        ]
        valid_context = (
            expected == "SELECT" and index == 0
            or expected == "FROM" and any(word == "SELECT" for word in previous_words) and next_token is not None and next_token.kind in {"word", "quoted_identifier"}
            or expected == "WHERE" and any(word == "FROM" for word in previous_words) and next_token is not None
            or expected in {"GROUP", "ORDER"} and next_token is not None and next_token.value.upper() == "BY"
            or expected == "JOIN" and next_token is not None and next_token.kind in {"word", "quoted_identifier"}
        )
        if not valid_context:
            continue
        corrected = expected if token.value.isupper() else expected.title() if token.value.istitle() else expected.lower()
        findings.append(
            _finding(
                "SQLKeywordSpelling",
                f"{token.value!r} appears to be a misspelling of SQL keyword {expected}.",
                source,
                token.start,
                f"Replace {token.value!r} with {expected}.",
                "High confidence for this recognized keyword position.",
                replacement=(token.start, token.end, corrected),
            )
        )
        normalized[index] = _Token("word", expected, token.start, token.end)
    return findings, normalized


def _find_top_level(tokens: list[_Token], depths: dict[int, int], word: str, start: int = 0) -> int | None:
    return next(
        (
            index
            for index in range(start, len(tokens))
            if depths.get(index, 0) == 0
            and tokens[index].kind == "word"
            and tokens[index].value.upper() == word
        ),
        None,
    )


def _rule_findings(
    source: str,
    masked: str,
    tokens: list[_Token],
    depths: dict[int, int],
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    if not tokens:
        return findings
    select_index = _find_top_level(tokens, depths, "SELECT")
    if select_index != 0 or tokens[0].kind != "word":
        return [
            _finding(
                "SQLUnsupportedStatement",
                "Only SELECT queries receive SQL analysis; this statement was not interpreted.",
                source,
                tokens[0].start,
                "Choose a SELECT query for the currently supported static checks.",
                "Certain: this analyzer intentionally supports SELECT statements only.",
                category="unsupported",
            )
        ]
    top_level_semicolons = [
        index for index, token in enumerate(tokens)
        if token.value == ";" and depths.get(index, 0) == 0
    ]
    if len(top_level_semicolons) > 1 or (
        top_level_semicolons and top_level_semicolons[-1] != len(tokens) - 1
    ):
        return [
            _finding(
                "SQLUnsupportedStatement",
                "Multiple SQL statements are not analyzed together.",
                source,
                tokens[top_level_semicolons[0] + 1].start,
                "Analyze one SELECT statement at a time.",
                "Certain: multi-statement input is intentionally unsupported.",
                category="unsupported",
            )
        ]

    from_index = _find_top_level(tokens, depths, "FROM", select_index + 1)
    projection_start = select_index + 1
    while projection_start < len(tokens) and tokens[projection_start].value.upper() in {"ALL", "DISTINCT"}:
        projection_start += 1
    if (
        projection_start >= len(tokens)
        or tokens[projection_start].value == ";"
        or (from_index is not None and projection_start == from_index)
    ):
        findings.append(
            _finding(
                "SQLIncompleteSelect",
                "SELECT is missing its projection (the column or expression list).",
                source,
                tokens[select_index].start,
                "Add one or more columns or expressions after SELECT.",
                "High confidence for this incomplete SELECT form.",
            )
        )

    if from_index is None and projection_start < len(tokens):
        projection = tokens[projection_start:]
        if any(token.kind in {"word", "quoted_identifier"} for token in projection):
            findings.append(
                _finding(
                    "SQLPossibleMissingFrom",
                    "This SELECT may be missing a FROM clause if these names are table columns.",
                    source,
                    tokens[select_index].start,
                    "Add the intended table after FROM; some SQL dialects allow SELECT expressions without FROM.",
                    "Possible and dialect-dependent; no table name can be inferred safely.",
                    category="dialect_dependent",
                )
            )

    if from_index is not None:
        projection = tokens[projection_start:from_index]
        if (
            len(projection) == 2
            and all(token.kind == "word" and token.value.upper() not in _CLAUSES for token in projection)
        ):
            first, second = projection
            findings.append(
                _finding(
                    "SQLPossibleMissingComma",
                    f"Selected names {first.value!r} and {second.value!r} may need a comma between them.",
                    source,
                    second.start,
                    "If these are separate columns, add a comma before the second name; it may instead be an implicit alias.",
                    "Possible: SQL aliases can use this same two-name pattern.",
                    category="possible",
                    replacement=(first.end, second.start, ", "),
                )
            )
        for offset in range(max(0, len(projection) - 2)):
            first, second, comma = projection[offset:offset + 3]
            if (
                first.kind == "word"
                and second.kind == "word"
                and comma.value == ","
                and first.value.upper() not in _CLAUSES
                and second.value.upper() not in _CLAUSES
            ):
                findings.append(
                    _finding(
                        "SQLPossibleMissingComma",
                        f"Selected names {first.value!r} and {second.value!r} may need a comma between them.",
                        source,
                        second.start,
                        "If these are separate columns, add a comma before the second name; it may instead be an implicit alias.",
                        "Possible: SQL aliases can use this same token pattern.",
                        category="possible",
                        replacement=(first.end, second.start, ", "),
                    )
                )
                break
        for offset in range(max(0, len(projection) - 2)):
            first, second, third = projection[offset:offset + 3]
            if all(token.kind == "word" for token in (first, second, third)):
                if first.value.upper() in _CLAUSES or second.value.upper() in _CLAUSES:
                    continue
                findings.append(
                    _finding(
                        "SQLPossibleMissingComma",
                        f"Adjacent selected names near {third.value!r} may be missing a comma.",
                        source,
                        third.start,
                        "Review the selected columns and add a comma at the intended boundary; aliases can make this ambiguous.",
                        "Possible: the suggested comma creates a valid projection, but intended column boundaries are not inferred.",
                        category="possible",
                        replacement=(third.start, third.start, ", "),
                    )
                )
                break

    where_index = _find_top_level(tokens, depths, "WHERE", select_index + 1)
    if where_index is not None:
        next_index = where_index + 1
        invalid_starts = {"=", "<", ">", "!", ";", ")"}
        if next_index >= len(tokens) or tokens[next_index].value.upper() in _CLAUSES | {"AND", "OR"} or tokens[next_index].value in invalid_starts:
            findings.append(
                _finding(
                    "SQLIncompleteWhere",
                    "WHERE does not have a recognizable condition after it.",
                    source,
                    tokens[where_index].start,
                    "Add a condition such as column_name = value; the intended condition cannot be inferred.",
                    "High confidence for a missing condition; SQL expressions vary by dialect.",
                )
            )
        else:
            last = next(
                (index for index in range(where_index + 1, len(tokens)) if depths.get(index, 0) == 0 and tokens[index].value == ";"),
                len(tokens),
            )
            if last > where_index + 1 and tokens[last - 1].value in {"=", "<", ">", "!", "+", "-", "*", "/", "AND", "OR"}:
                findings.append(
                    _finding(
                        "SQLIncompleteWhere",
                        "The WHERE condition ends with an operator and is missing its right-hand expression.",
                        source,
                        tokens[last - 1].start,
                        "Add the intended value or expression after the operator.",
                        "High confidence for an incomplete condition.",
                    )
                )

    for index, token in enumerate(tokens):
        if token.kind != "word" or token.value.upper() != "JOIN":
            continue
        prior = tokens[index - 1].value.upper() if index else ""
        if prior in {"CROSS", "NATURAL"}:
            continue
        if index + 1 >= len(tokens):
            continue
        has_condition = False
        condition_token: int | None = None
        for following in range(index + 2, len(tokens)):
            candidate = tokens[following]
            if depths.get(following, 0) != 0:
                continue
            keyword = candidate.value.upper()
            if keyword in {"ON", "USING"}:
                has_condition = True
                condition_token = following
                break
            if candidate.value == ";" or keyword in {"WHERE", "GROUP", "HAVING", "ORDER", "LIMIT", "OFFSET", "JOIN", "LEFT", "RIGHT", "FULL", "INNER", "CROSS"}:
                break
        if not has_condition:
            findings.append(
                _finding(
                    "SQLPossibleMissingJoinCondition",
                    "This JOIN may be missing its ON or USING condition.",
                    source,
                    token.start,
                    "Add the intended join condition; CROSS JOIN and dialect-specific forms differ.",
                    "Possible and dialect-dependent; NATURAL and CROSS joins are treated separately.",
                    category="dialect_dependent",
                )
            )
        elif condition_token is not None:
            next_condition = condition_token + 1
            if (
                next_condition >= len(tokens)
                or tokens[next_condition].value == ";"
                or tokens[next_condition].value.upper() in _CLAUSES
            ):
                findings.append(
                    _finding(
                        "SQLIncompleteJoinCondition",
                        "ON or USING is present but has no recognizable condition.",
                        source,
                        tokens[condition_token].start,
                        "Add the intended join expression after ON or the column list after USING.",
                        "High confidence for an empty condition in this common JOIN form.",
                        category="dialect_dependent",
                    )
                )

    group_index = _find_top_level(tokens, depths, "GROUP", select_index + 1)
    if group_index is not None and (group_index + 1 >= len(tokens) or tokens[group_index + 1].value.upper() != "BY"):
        insertion = tokens[group_index].end
        findings.append(
            _finding(
                "SQLIncompleteGroupBy",
                "GROUP is not followed by BY.",
                source,
                tokens[group_index].start,
                "Write GROUP BY followed by the grouping expression.",
                "High confidence for this clause spelling.",
                replacement=(insertion, insertion, " BY"),
            )
        )

    if from_index is not None and group_index is None:
        aggregate_and_column = re.search(
            r"(?is)\bSELECT\s+(?:COUNT|SUM|AVG|MIN|MAX)\s*\(\s*(?:\*|[A-Za-z_][\w.]*)\s*\)\s*,\s*(?P<column>[A-Za-z_][\w.]*)(?:\s+AS\s+[A-Za-z_][\w.]*)?\s+FROM\b",
            masked,
        )
        if aggregate_and_column:
            column = aggregate_and_column.group("column")
            insertion = len(source.rstrip())
            for index in range(from_index + 1, len(tokens)):
                if depths.get(index, 0) == 0 and tokens[index].value.upper() in {"HAVING", "ORDER", "LIMIT", "OFFSET", ";"}:
                    insertion = tokens[index].start
                    break
            findings.append(
                _finding(
                    "SQLPossibleMissingGroupBy",
                    f"Selected column {column!r} appears alongside an aggregate without GROUP BY.",
                    source,
                    aggregate_and_column.start("column"),
                    f"In standard SQL, add GROUP BY {column}; grouping behavior differs by dialect and settings.",
                    "Dialect-dependent; some engines accept non-grouped columns under relaxed rules.",
                    category="dialect_dependent",
                    replacement=(insertion, insertion, f" GROUP BY {column}"),
                )
            )
    return findings


def analyze_sql(source: str) -> dict[str, Any]:
    """Inspect a bounded SELECT query with explicit, dialect-aware rules."""
    if not isinstance(source, str) or not source.strip():
        return {
            "status": "empty",
            "source_valid": False,
            "summary": "Enter SQL to begin an analysis.",
            "findings": [],
        }
    if len(source) > _MAX_SOURCE_LENGTH:
        return {
            "status": "unsupported",
            "source_valid": None,
            "summary": "SQL analysis is unavailable because the input exceeds the size limit.",
            "findings": [],
        }

    tokens, masked, findings = _scan(source)
    depths, delimiter_findings = _depths_and_delimiters(source, tokens)
    findings.extend(delimiter_findings)
    typo_findings, normalized_tokens = _keyword_typo_findings(source, tokens)
    findings.extend(typo_findings)
    if not any(item["error_type"] == "SQLInputLimit" for item in findings):
        findings.extend(_rule_findings(source, masked, normalized_tokens, depths))

    if findings:
        unsupported_finding = next(
            (item for item in findings if item["category"] == "unsupported"),
            None,
        )
        if unsupported_finding:
            status = "unsupported"
            summary = unsupported_finding["message"]
        else:
            status = "findings"
            summary = f"Found {len(findings)} SQL issue or review note(s) using limited static rules."
    else:
        status = "clean"
        summary = "No issues were identified by the available SQL checks."
    return {
        "status": status,
        "source_valid": None,
        "summary": summary,
        "findings": findings,
    }


def suggest_sql_fix(source: str, findings: list[dict[str, Any]]) -> dict[str, Any]:
    edits = [finding["replacement"] for finding in findings if finding.get("replacement")]
    suggested = source
    for start, end, replacement in sorted(edits, reverse=True):
        suggested = suggested[:start] + replacement + suggested[end:]
    has_suggestion = suggested != source
    diff = "".join(
        difflib.unified_diff(
            source.splitlines(keepends=True),
            suggested.splitlines(keepends=True),
            fromfile="original.sql",
            tofile="suggested.sql",
        )
    )
    return {
        "original_code": source,
        "suggested_code": suggested if has_suggestion else None,
        "attempted_code": suggested if has_suggestion else None,
        "has_suggestion": has_suggestion,
        "reason": (
            "Applied only explicit text corrections; review dialect-dependent edits before use."
            if has_suggestion
            else "No safe automatic SQL correction was identified."
        ),
        "confidence": "Suggestions are text-only and do not validate against a database.",
        "verified": False,
        "compiles": None,
        "compilation_passed": None,
        "compilation_error": None,
        "diff": diff,
    }


def explain_sql_findings(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    explanations = []
    for finding in findings:
        explanations.append(
            {
                "error_type": finding["error_type"],
                "what_it_means": finding["message"],
                "why_it_likely_happened": finding["confidence"],
                "how_to_fix": finding["next_action"],
                "corrected_example": None,
                "concept": "SQL query structure",
                "prevention_tip": "Review query clauses and delimiters; confirm dialect-dependent behavior with your database documentation.",
                "basis": "Rule-based SQL text inspection; no database connection or query execution was used.",
            }
        )
    return explanations


def verify_sql_fix() -> dict[str, Any]:
    return {
        "status": "unsupported",
        "compilation": {
            "ran": False,
            "passed": None,
            "detail": "SQL verification is unsupported; no SQL parser service, database, or query execution was used.",
        },
        "trusted_tests": [],
        "complete_for_fixture": False,
        "candidate_executed": False,
        "warning": "SQL query behavior depends on schema, data, and dialect. No query or fix was executed.",
    }


def predict_sql_output(source: str | None = None) -> dict[str, Any]:
    """Backward-compatible SQL prediction entry point backed by fixed sample data."""
    if source is None:
        return {
            "status": "unavailable",
            "output": "",
            "columns": [],
            "rows": [],
            "label": "Predicted Result — Computed from Built-in Sample Data (Not Executed Against a Database)",
            "message": UNAVAILABLE_MESSAGE,
        }
    return predict_sql_query(source)