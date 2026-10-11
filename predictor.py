"""Bounded AST-only prediction for a small, explicitly supported Python subset."""

from __future__ import annotations

import ast
import builtins
import math
import operator
from typing import Any

_MAX_SOURCE_LENGTH = 50_000
_MAX_AST_NODES = 300
_MAX_AST_DEPTH = 32
_MAX_INTEGER_BITS = 4096
_MAX_EXPONENT = 1000
_MAX_STRING_LENGTH = 10_000
_MAX_OUTPUT_LENGTH = 50_000
_UNAVAILABLE_MESSAGE = "Prediction unavailable for this code. The program was not executed."

_BINARY_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_COMPARISON_OPERATORS = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
}


class _UnsupportedCode(Exception):
    pass


class _PredictionError(Exception):
    pass


def _unsupported() -> _UnsupportedCode:
    return _UnsupportedCode(_UNAVAILABLE_MESSAGE)


def _check_limits(tree: ast.AST) -> None:
    pending = [(tree, 1)]
    count = 0
    while pending:
        node, depth = pending.pop()
        count += 1
        if count > _MAX_AST_NODES or depth > _MAX_AST_DEPTH:
            raise _unsupported()
        pending.extend((child, depth + 1) for child in ast.iter_child_nodes(node))


def _check_value(value: Any) -> Any:
    if type(value) not in (bool, int, float, str, type(None)):
        raise _unsupported()
    if type(value) is int and value.bit_length() > _MAX_INTEGER_BITS:
        raise _unsupported()
    if type(value) is float and not math.isfinite(value):
        raise _unsupported()
    if type(value) is str and len(value) > _MAX_STRING_LENGTH:
        raise _unsupported()
    return value


def _validate_expression(node: ast.expr) -> None:
    if isinstance(node, ast.Constant):
        _check_value(node.value)
    elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
        return
    elif isinstance(node, ast.BinOp) and type(node.op) in _BINARY_OPERATORS:
        _validate_expression(node.left)
        _validate_expression(node.right)
    elif isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub, ast.Not)):
        _validate_expression(node.operand)
    elif isinstance(node, ast.BoolOp) and isinstance(node.op, (ast.And, ast.Or)):
        for value in node.values:
            _validate_expression(value)
    elif isinstance(node, ast.Compare) and all(
        type(operation) in _COMPARISON_OPERATORS for operation in node.ops
    ):
        _validate_expression(node.left)
        for comparator in node.comparators:
            _validate_expression(comparator)
    else:
        raise _unsupported()


def _validate_statements(statements: list[ast.stmt]) -> None:
    for statement in statements:
        if isinstance(statement, ast.Assign):
            if not statement.targets or any(
                not isinstance(target, ast.Name)
                or not isinstance(target.ctx, ast.Store)
                or target.id == "print"
                for target in statement.targets
            ):
                raise _unsupported()
            _validate_expression(statement.value)
        elif isinstance(statement, ast.Expr):
            call = statement.value
            if (
                not isinstance(call, ast.Call)
                or not isinstance(call.func, ast.Name)
                or call.func.id != "print"
                or call.keywords
                or any(isinstance(argument, ast.Starred) for argument in call.args)
            ):
                raise _unsupported()
            for argument in call.args:
                _validate_expression(argument)
        elif isinstance(statement, ast.If):
            _validate_expression(statement.test)
            _validate_statements(statement.body)
            _validate_statements(statement.orelse)
        else:
            raise _unsupported()


def _evaluate(node: ast.expr, variables: dict[str, Any]) -> Any:
    if isinstance(node, ast.Constant):
        return _check_value(node.value)
    if isinstance(node, ast.Name):
        if node.id not in variables:
            if node.id in dir(builtins):
                raise _unsupported()
            raise _PredictionError(f"NameError: name '{node.id}' is not defined")
        return variables[node.id]
    if isinstance(node, ast.BinOp):
        left = _evaluate(node.left, variables)
        right = _evaluate(node.right, variables)
        if type(node.op) is ast.Add and type(left) is type(right) is str:
            if len(left) + len(right) > _MAX_STRING_LENGTH:
                raise _unsupported()
        elif (
            type(node.op) not in _BINARY_OPERATORS
            or type(left) not in (int, float)
            or type(right) not in (int, float)
        ):
            raise _unsupported()
        if type(node.op) is ast.Pow:
            if abs(right) > _MAX_EXPONENT:
                raise _unsupported()
            if type(left) is int and type(right) is int and right > 0 and abs(left) > 1:
                estimated_bits = int(right * math.log2(abs(left))) + 1
                if estimated_bits > _MAX_INTEGER_BITS:
                    raise _unsupported()
        try:
            return _check_value(_BINARY_OPERATORS[type(node.op)](left, right))
        except ZeroDivisionError as error:
            raise _PredictionError("ZeroDivisionError: division by zero") from error
        except (ArithmeticError, TypeError, ValueError):
            raise _unsupported()
    if isinstance(node, ast.UnaryOp):
        value = _evaluate(node.operand, variables)
        if isinstance(node.op, ast.Not):
            return not value
        if type(value) not in (int, float):
            raise _unsupported()
        operation = operator.pos if isinstance(node.op, ast.UAdd) else operator.neg
        try:
            return _check_value(operation(value))
        except (ArithmeticError, TypeError, ValueError):
            raise _unsupported()
    if isinstance(node, ast.BoolOp):
        value = _evaluate(node.values[0], variables)
        for child in node.values[1:]:
            if isinstance(node.op, ast.And) and not value:
                break
            if isinstance(node.op, ast.Or) and value:
                break
            value = _evaluate(child, variables)
        return value
    if isinstance(node, ast.Compare):
        left = _evaluate(node.left, variables)
        for operation, comparator in zip(node.ops, node.comparators):
            right = _evaluate(comparator, variables)
            try:
                matched = _COMPARISON_OPERATORS[type(operation)](left, right)
            except (TypeError, ValueError):
                raise _unsupported()
            if not matched:
                return False
            left = right
        return True
    raise _unsupported()


def _run_statements(
    statements: list[ast.stmt],
    variables: dict[str, Any],
    output: list[str],
) -> None:
    for statement in statements:
        if isinstance(statement, ast.Assign):
            value = _evaluate(statement.value, variables)
            for target in statement.targets:
                variables[target.id] = value
        elif isinstance(statement, ast.Expr):
            values = [_evaluate(argument, variables) for argument in statement.value.args]
            rendered = " ".join(str(value) for value in values)
            output.append(rendered + "\n")
            if sum(map(len, output)) > _MAX_OUTPUT_LENGTH:
                raise _unsupported()
        elif isinstance(statement, ast.If):
            branch = statement.body if _evaluate(statement.test, variables) else statement.orelse
            _run_statements(branch, variables, output)


def predict_output(source: str) -> dict[str, str]:
    """Predict output only for bounded, deterministic constructs in the allowlist."""
    if not isinstance(source, str) or not source.strip():
        return {"status": "unavailable", "output": "", "message": _UNAVAILABLE_MESSAGE}
    if len(source) > _MAX_SOURCE_LENGTH:
        return {"status": "unavailable", "output": "", "message": _UNAVAILABLE_MESSAGE}

    try:
        tree = ast.parse(source, filename="<submitted code>", mode="exec")
    except (SyntaxError, ValueError, TypeError) as error:
        if isinstance(error, SyntaxError):
            line = f" on line {error.lineno}" if error.lineno else ""
            detail = f"SyntaxError{line}: {error.msg}"
        else:
            detail = f"{type(error).__name__}: {error}"
        return {"status": "error", "output": "", "message": detail}
    except RecursionError:
        return {"status": "unavailable", "output": "", "message": _UNAVAILABLE_MESSAGE}

    try:
        _check_limits(tree)
        _validate_statements(tree.body)
        output: list[str] = []
        _run_statements(tree.body, {}, output)
    except _PredictionError as error:
        return {"status": "error", "output": "", "message": str(error)}
    except _UnsupportedCode as error:
        return {"status": "unavailable", "output": "", "message": str(error)}
    except (ArithmeticError, TypeError, ValueError):
        return {"status": "unavailable", "output": "", "message": _UNAVAILABLE_MESSAGE}

    predicted = "".join(output)
    return {"status": "predicted", "output": predicted, "message": ""}