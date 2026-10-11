"""Restricted Java output prediction using tokenization and explicit expression rules."""

from __future__ import annotations

import re
from dataclasses import dataclass

_MAX_SOURCE_LENGTH = 20_000
_MAX_TOKENS = 2_000
_MAX_EXPRESSION_DEPTH = 40
_MAX_STRING_LENGTH = 10_000
_MAX_OUTPUT_LENGTH = 50_000
_INT_MIN = -(2**31)
_INT_MAX = 2**31 - 1
UNAVAILABLE_MESSAGE = "Prediction unavailable for Java code. The program was not executed."

_CLASS_WRAPPER = re.compile(
    r"\A\s*(?:public\s+)?class\s+[A-Za-z_$][\w$]*\s*\{\s*"
    r"public\s+static\s+void\s+main\s*\(\s*String\s*\[\s*\]\s*"
    r"[A-Za-z_$][\w$]*\s*\)\s*\{(?P<body>.*?)\}\s*\}\s*\Z",
    re.DOTALL,
)
_IDENTIFIER = re.compile(r"[A-Za-z_$][A-Za-z0-9_$]*")


class _Unsupported(Exception):
    pass


class _DivisionByZero(Exception):
    pass


@dataclass(frozen=True)
class _Token:
    kind: str
    value: str


def _unavailable() -> dict[str, str]:
    return {"status": "unavailable", "output": "", "message": UNAVAILABLE_MESSAGE}


def _tokenize(source: str) -> list[_Token]:
    tokens: list[_Token] = []
    index = 0
    while index < len(source):
        char = source[index]
        if char.isspace():
            index += 1
            continue
        if char == '"':
            index += 1
            value: list[str] = []
            while index < len(source) and source[index] != '"':
                char = source[index]
                if char == "\\":
                    index += 1
                    if index >= len(source):
                        raise _Unsupported()
                    escape = source[index]
                    decoded = {'"': '"', "\\": "\\", "n": "\n", "r": "\r", "t": "\t"}.get(escape)
                    if decoded is None:
                        raise _Unsupported()
                    value.append(decoded)
                else:
                    if char in "\r\n":
                        raise _Unsupported()
                    value.append(char)
                index += 1
                if len(value) > _MAX_STRING_LENGTH:
                    raise _Unsupported()
            if index >= len(source):
                raise _Unsupported()
            index += 1
            tokens.append(_Token("string", "".join(value)))
            continue
        if char.isdigit():
            end = index + 1
            while end < len(source) and source[end].isdigit():
                end += 1
            digits = source[index:end]
            if len(digits) > 10 or (len(digits) > 1 and digits.startswith("0")):
                raise _Unsupported()
            tokens.append(_Token("integer", digits))
            index = end
            continue
        identifier = _IDENTIFIER.match(source, index)
        if identifier:
            tokens.append(_Token("identifier", identifier.group()))
            index = identifier.end()
            continue
        if char in "+-*/()=;.":
            tokens.append(_Token(char, char))
            index += 1
            continue
        raise _Unsupported()
    if len(tokens) > _MAX_TOKENS:
        raise _Unsupported()
    return tokens


class _Parser:
    def __init__(self, tokens: list[_Token]):
        self.tokens = tokens
        self.position = 0
        self.variables: dict[str, int | str] = {}
        self.output: list[str] = []

    def _current(self) -> _Token | None:
        return self.tokens[self.position] if self.position < len(self.tokens) else None

    def _take(self, kind: str, value: str | None = None) -> _Token:
        token = self._current()
        if token is None or token.kind != kind or (value is not None and token.value != value):
            raise _Unsupported()
        self.position += 1
        return token

    def _check_int(self, value: int) -> int:
        if not _INT_MIN <= value <= _INT_MAX:
            raise _Unsupported()
        return value

    def _primary(self, depth: int) -> int | str:
        if depth > _MAX_EXPRESSION_DEPTH:
            raise _Unsupported()
        token = self._current()
        if token is None:
            raise _Unsupported()
        if token.kind == "integer":
            self.position += 1
            return self._check_int(int(token.value))
        if token.kind == "string":
            self.position += 1
            return token.value
        if token.kind == "identifier":
            self.position += 1
            if token.value not in self.variables:
                raise _Unsupported()
            return self.variables[token.value]
        if token.kind == "(":
            self.position += 1
            value = self._expression(depth + 1)
            self._take(")")
            return value
        raise _Unsupported()

    def _unary(self, depth: int) -> int | str:
        if depth > _MAX_EXPRESSION_DEPTH:
            raise _Unsupported()
        token = self._current()
        if token is not None and token.kind in {"+", "-"}:
            self.position += 1
            value = self._unary(depth + 1)
            if type(value) is not int:
                raise _Unsupported()
            return self._check_int(value if token.kind == "+" else -value)
        return self._primary(depth)

    def _term(self, depth: int) -> int | str:
        value = self._unary(depth)
        while (token := self._current()) is not None and token.kind in {"*", "/"}:
            self.position += 1
            right = self._unary(depth)
            if type(value) is not int or type(right) is not int:
                raise _Unsupported()
            if token.kind == "/":
                if right == 0:
                    raise _DivisionByZero()
                quotient = abs(value) // abs(right)
                value = self._check_int(-quotient if (value < 0) != (right < 0) else quotient)
            else:
                value = self._check_int(value * right)
        return value

    def _expression(self, depth: int = 0) -> int | str:
        value = self._term(depth)
        while (token := self._current()) is not None and token.kind in {"+", "-"}:
            self.position += 1
            right = self._term(depth)
            if token.kind == "+" and (type(value) is str or type(right) is str):
                value = f"{value}{right}"
                if len(value) > _MAX_STRING_LENGTH:
                    raise _Unsupported()
            elif type(value) is int and type(right) is int:
                value = self._check_int(value + right if token.kind == "+" else value - right)
            else:
                raise _Unsupported()
        return value

    def _statement(self) -> None:
        token = self._current()
        if token is None:
            return
        if token.kind == "identifier" and token.value == "System":
            self._take("identifier", "System")
            self._take(".")
            self._take("identifier", "out")
            self._take(".")
            self._take("identifier", "println")
            self._take("(")
            value = "" if self._current() is not None and self._current().kind == ")" else self._expression()
            self._take(")")
            self._take(";")
            self.output.append(f"{value}\n")
            if sum(map(len, self.output)) > _MAX_OUTPUT_LENGTH:
                raise _Unsupported()
            return

        if token.kind == "identifier" and token.value in {"int", "String"}:
            declared_type = self._take("identifier").value
            name = self._take("identifier").value
            if name in self.variables:
                raise _Unsupported()
            self._take("=")
            value = self._expression()
            if (declared_type == "int" and type(value) is not int) or (
                declared_type == "String" and type(value) is not str
            ):
                raise _Unsupported()
            self.variables[name] = value
            self._take(";")
            return

        if token.kind == "identifier":
            name = self._take("identifier").value
            if name not in self.variables:
                raise _Unsupported()
            self._take("=")
            value = self._expression()
            if type(value) is not type(self.variables[name]):
                raise _Unsupported()
            self.variables[name] = value
            self._take(";")
            return

        raise _Unsupported()

    def parse(self) -> str:
        while self._current() is not None:
            self._statement()
        if not self.output:
            raise _Unsupported()
        return "".join(self.output)


def predict_java_output(source: str) -> dict[str, str]:
    """Predict output for bounded integer/string statements in a tiny Java subset."""
    if not isinstance(source, str) or not source.strip() or len(source) > _MAX_SOURCE_LENGTH:
        return _unavailable()
    wrapper = _CLASS_WRAPPER.fullmatch(source)
    body = wrapper.group("body") if wrapper else source
    try:
        output = _Parser(_tokenize(body)).parse()
    except _DivisionByZero:
        return {
            "status": "error",
            "output": "",
            "message": "ArithmeticException: / by zero",
        }
    except (_Unsupported, ValueError, RecursionError):
        return _unavailable()
    return {"status": "predicted", "output": output, "message": ""}