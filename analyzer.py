"""Static Python diagnostics. Submitted source is parsed and compiled, never run."""

from __future__ import annotations

import ast
import builtins
import importlib.machinery
import symtable
import sys
from typing import Any


def _finding(
    category: str,
    error_type: str,
    message: str,
    line_number: int | None,
    confidence: str,
    next_action: str,
    **extra: Any,
) -> dict[str, Any]:
    return {
        "category": category,
        "error_type": error_type,
        "message": message,
        "line_number": line_number,
        "confidence": confidence,
        "next_action": next_action,
        **extra,
    }


def _top_level_name_errors(source: str, tree: ast.Module) -> list[dict[str, Any]]:
    """Find unresolved global names without guessing about local/dynamic scope."""
    try:
        table = symtable.symtable(source, "<submitted code>", "exec")
    except SyntaxError:
        return []

    known_builtins = set(dir(builtins))
    result: list[dict[str, Any]] = []
    seen: set[str] = set()

    def inspect_scope(scope: symtable.SymbolTable) -> None:
        for symbol in scope.get_symbols():
            if (
                symbol.is_referenced()
                and symbol.is_global()
                and not symbol.is_assigned()
                and not symbol.is_imported()
                and symbol.get_name() not in known_builtins
                and symbol.get_name() not in seen
            ):
                name = symbol.get_name()
                seen.add(name)
                line = next(
                    (
                        node.lineno
                        for node in ast.walk(tree)
                        if isinstance(node, ast.Name)
                        and node.id == name
                        and isinstance(node.ctx, ast.Load)
                    ),
                    None,
                )
                result.append(
                    _finding(
                        "static",
                        "NameError",
                        f"'{name}' is referenced but is not defined in this source.",
                        line,
                        "Likely: unresolved global name in static scope analysis.",
                        "Define the name, import it, or check for a spelling mistake.",
                        symbol=name,
                    )
                )
        for child in scope.get_children():
            inspect_scope(child)

    inspect_scope(table)
    return result


def _literal_runtime_risks(tree: ast.Module) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    literal_history: dict[str, list[tuple[int, int, ast.expr | None]]] = {}
    for statement in tree.body:
        if isinstance(statement, ast.Assign):
            targets = [target.id for target in statement.targets if isinstance(target, ast.Name)]
            value = statement.value
        elif isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name):
            targets = [statement.target.id]
            value = statement.value
        else:
            continue
        if not targets:
            continue
        literal_value = (
            value
            if isinstance(value, (ast.Constant, ast.List, ast.Tuple, ast.Dict))
            else None
        )
        for name in targets:
            literal_history.setdefault(name, []).append(
                (statement.lineno, statement.col_offset, literal_value)
            )

    def literal_binding(node: ast.expr, line_number: int, column_offset: int) -> ast.expr | None:
        if isinstance(node, (ast.Constant, ast.List, ast.Tuple, ast.Dict)):
            return node
        if isinstance(node, ast.Name):
            preceding = [
                value
                for line, column, value in literal_history.get(node.id, [])
                if (line, column) < (line_number, column_offset)
            ]
            return preceding[-1] if preceding else None
        return None

    def numeric_literal(node: ast.expr) -> int | float | None:
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            return node.value
        if (
            isinstance(node, ast.UnaryOp)
            and isinstance(node.op, ast.USub)
            and isinstance(node.operand, ast.Constant)
            and type(node.operand.value) in (int, float)
        ):
            return -node.operand.value
        return None

    def resolved_numeric_literal(node: ast.expr) -> int | float | None:
        resolved = literal_binding(node, node.lineno, node.col_offset)
        return numeric_literal(resolved) if resolved is not None else None

    def integer_literal(node: ast.expr) -> int | None:
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, int)
            and not isinstance(node.value, bool)
        ):
            return node.value
        if (
            isinstance(node, ast.UnaryOp)
            and isinstance(node.op, ast.USub)
            and isinstance(node.operand, ast.Constant)
            and isinstance(node.operand.value, int)
            and not isinstance(node.operand.value, bool)
        ):
            return -node.operand.value
        return None

    for node in ast.walk(tree):
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Div, ast.FloorDiv, ast.Mod)):
            divisor = resolved_numeric_literal(node.right)
            if divisor == 0:
                findings.append(
                    _finding(
                        "potential_runtime",
                        "ZeroDivisionError",
                        "This expression divides by a statically known zero value.",
                        node.lineno,
                        "High for this expression; runtime control flow was not executed.",
                        "Use a non-zero divisor or handle the zero case before dividing.",
                    )
                )
        elif isinstance(node, ast.Subscript):
            container = literal_binding(node.value, node.lineno, node.col_offset)
            key = node.slice
            index_value = integer_literal(key)
            if (
                isinstance(container, (ast.List, ast.Tuple))
                and index_value is not None
                and (index_value >= len(container.elts) or index_value < -len(container.elts))
            ):
                extra = {}
                if isinstance(container, ast.List) and isinstance(node.value, ast.Name):
                    extra = {
                        "container_name": node.value.id,
                        "index_value": index_value,
                    }
                findings.append(
                    _finding(
                        "potential_runtime",
                        "IndexError",
                        f"Index {index_value} is outside this literal's valid index range.",
                        node.lineno,
                        "High for this literal access; runtime control flow was not executed.",
                        "Check the collection length and use a valid index or guard the access.",
                        **extra,
                    )
                )
            elif isinstance(container, ast.Dict) and isinstance(key, ast.Constant):
                literal_keys = {
                    item.value
                    for item in container.keys
                    if isinstance(item, ast.Constant)
                }
                if key.value not in literal_keys:
                    findings.append(
                        _finding(
                            "potential_runtime",
                            "KeyError",
                            f"Key {key.value!r} is not present in this dictionary literal.",
                            node.lineno,
                            "High for this literal access; runtime control flow was not executed.",
                            "Check key membership or use dict.get() with an appropriate default.",
                        )
                    )
        elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            left = literal_binding(node.left, node.lineno, node.col_offset)
            right = literal_binding(node.right, node.lineno, node.col_offset)
            if isinstance(left, ast.Constant) and isinstance(right, ast.Constant):
                incompatible = (
                    isinstance(left.value, str)
                    and isinstance(right.value, (int, float))
                    or isinstance(right.value, str)
                    and isinstance(left.value, (int, float))
                )
                if incompatible:
                    findings.append(
                        _finding(
                            "potential_runtime",
                            "TypeError",
                            "This expression adds a string and a number, which Python does not allow.",
                            node.lineno,
                            "High for these literal operand types.",
                            "Convert the number to text, or use an f-string.",
                        )
                    )
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "int"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            try:
                int(node.args[0].value)
            except ValueError:
                findings.append(
                    _finding(
                        "potential_runtime",
                        "ValueError",
                        f"int() cannot convert {node.args[0].value!r} to an integer.",
                        node.lineno,
                        "High for this literal argument.",
                        "Validate the input or provide a string containing an integer.",
                    )
                )
        elif isinstance(node, ast.Attribute):
            receiver = literal_binding(node.value, node.lineno, node.col_offset)
            value = receiver.value if isinstance(receiver, ast.Constant) else None
            if isinstance(value, str) and node.attr in {"append", "extend", "sort", "reverse"}:
                findings.append(
                    _finding(
                        "potential_runtime",
                        "AttributeError",
                        f"A string has no {node.attr}() method.",
                        node.lineno,
                        "High for this literal receiver.",
                        "Use a list if you need to mutate a sequence, or choose a string method.",
                    )
                )

    return findings


def _missing_imports(tree: ast.Module) -> list[dict[str, Any]]:
    """Check top-level imports on sys.path without importing user/package code."""
    findings: list[dict[str, Any]] = []
    seen: set[str] = set()
    available = set(sys.builtin_module_names) | set(sys.stdlib_module_names)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [alias.name.split(".", 1)[0] for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names = [node.module.split(".", 1)[0]]
        else:
            continue
        for name in names:
            if name in available or name in seen:
                continue
            seen.add(name)
            if importlib.machinery.PathFinder.find_spec(name, sys.path) is None:
                findings.append(
                    _finding(
                        "environment_dependent",
                        "ModuleNotFoundError",
                        f"Top-level module {name!r} was not found on this process's sys.path.",
                        node.lineno,
                        "Likely unavailable in this environment; custom import hooks are not checked.",
                        "Check the module spelling and install it in the environment running BugWise AI.",
                        module=name,
                    )
                )
    return findings


def analyze_code(source: str) -> dict[str, Any]:
    """Return a stable analysis result without executing submitted Python."""
    if not isinstance(source, str) or not source.strip():
        return {
            "status": "empty",
            "source_valid": False,
            "summary": "Enter Python code to begin an analysis.",
            "findings": [],
        }

    try:
        compile(source, "<submitted code>", "exec")
        tree = ast.parse(source, filename="<submitted code>", mode="exec")
    except (SyntaxError, IndentationError) as error:
        error_name = "IndentationError" if isinstance(error, IndentationError) else "SyntaxError"
        message = error.msg or str(error)
        return {
            "status": "invalid",
            "source_valid": False,
            "summary": f"{error_name}: {message}",
            "findings": [
                _finding(
                    "static",
                    error_name,
                    message,
                    error.lineno,
                    "Certain: Python's compiler rejected the source.",
                    "Correct the reported syntax or indentation, then analyze again.",
                    offset=error.offset,
                    source_line=error.text.rstrip() if error.text else None,
                )
            ],
        }
    except (ValueError, TypeError) as error:
        return {
            "status": "invalid",
            "source_valid": False,
            "summary": f"Python could not parse this source: {error}",
            "findings": [
                _finding(
                    "static",
                    type(error).__name__,
                    str(error),
                    None,
                    "Certain: Python's parser rejected the source.",
                    "Check that the input is valid Python source text.",
                )
            ],
        }

    findings = _top_level_name_errors(source, tree)
    findings.extend(_literal_runtime_risks(tree))
    findings.extend(_missing_imports(tree))
    if findings:
        status = "findings"
        summary = f"Found {len(findings)} static or literal-based risk(s)."
    else:
        status = "clean"
        summary = "No issues were identified by the available static checks."

    return {
        "status": status,
        "source_valid": True,
        "summary": summary,
        "findings": findings,
    }
