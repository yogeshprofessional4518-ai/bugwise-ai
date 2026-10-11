"""Heuristic Java checks and narrow prediction without compiling or running source."""

from __future__ import annotations

import difflib
import re
from typing import Any

from java_predictor import predict_java_output as _predict_java_output

_TYPES = r"byte|short|int|long|float|double|boolean|char|String"
_DECLARATION_RE = re.compile(
    rf"\b(?:final\s+)?(?P<type>{_TYPES})\s+(?P<name>[A-Za-z_$][\w$]*)"
    r"\s*(?:=\s*(?P<value>[^;]+))?\s*;?"
)
_MISSING_SEMICOLON_PATTERNS = (
    re.compile(rf"^\s*(?:final\s+)?(?:{_TYPES})\s+[A-Za-z_$][\w$]*\s*=.+$"),
    re.compile(r"^\s*System\s*\.\s*out\s*\.\s*println\s*\(.*\)\s*$"),
)
_PRINT_WITHOUT_PARENS_RE = re.compile(
    r'''System\s*\.\s*out\s*\.\s*println\s+(?P<literal>"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*')\s*(?P<semicolon>;?)'''
)
_MAIN_CAPITALIZATION_RE = re.compile(r"\b(void\s+)Main(\s*\()")
_ASSIGNMENT_RE = re.compile(r"^\s*([A-Za-z_$][\w$]*)\s*=(?!=).+;\s*$")


def _finding(
    error_type: str,
    message: str,
    line_number: int,
    next_action: str,
    confidence: str,
    source_line: str,
    category: str = "static",
    **extra: Any,
) -> dict[str, Any]:
    return {
        "category": category,
        "error_type": error_type,
        "message": message,
        "line_number": line_number,
        "next_action": next_action,
        "confidence": confidence,
        "source_line": source_line,
        **extra,
    }


def _strip_comments(source: str) -> str:
    """Replace comments with spaces while preserving strings and source positions."""
    result = list(source)
    index = 0
    state = "code"
    quote = ""
    while index < len(source):
        char = source[index]
        following = source[index + 1] if index + 1 < len(source) else ""
        if state == "code":
            if char in {'"', "'"}:
                state = "string"
                quote = char
            elif char == "/" and following == "/":
                state = "line_comment"
                result[index] = result[index + 1] = " "
                index += 1
            elif char == "/" and following == "*":
                state = "block_comment"
                result[index] = result[index + 1] = " "
                index += 1
        elif state == "string":
            if char == "\\":
                index += 1
            elif char == quote:
                state = "code"
        elif state == "line_comment":
            if char == "\n":
                state = "code"
            else:
                result[index] = " "
        elif state == "block_comment":
            if char == "*" and following == "/":
                result[index] = result[index + 1] = " "
                index += 1
                state = "code"
            elif char != "\n":
                result[index] = " "
        index += 1
    return "".join(result)


def _mask_literals_and_comments(source: str) -> str:
    """Mask strings and comments so delimiters inside them do not affect balance checks."""
    masked = list(source)
    index = 0
    state = "code"
    quote = ""
    while index < len(source):
        char = source[index]
        following = source[index + 1] if index + 1 < len(source) else ""
        if state == "code":
            if char in {'"', "'"}:
                state = "string"
                quote = char
                masked[index] = " "
            elif char == "/" and following == "/":
                state = "line_comment"
                masked[index] = masked[index + 1] = " "
                index += 1
            elif char == "/" and following == "*":
                state = "block_comment"
                masked[index] = masked[index + 1] = " "
                index += 1
        elif state == "string":
            if char != "\n":
                masked[index] = " "
            if char == "\\":
                index += 1
                if index < len(source) and source[index] != "\n":
                    masked[index] = " "
            elif char == quote:
                state = "code"
        elif state == "line_comment":
            if char == "\n":
                state = "code"
            else:
                masked[index] = " "
        elif state == "block_comment":
            if char == "*" and following == "/":
                masked[index] = masked[index + 1] = " "
                index += 1
                state = "code"
            elif char != "\n":
                masked[index] = " "
        index += 1
    return "".join(masked)


def _delimiter_findings(source: str) -> list[dict[str, Any]]:
    masked = _mask_literals_and_comments(source)
    pairs = {")": "(", "]": "[", "}": "{"}
    openings = set(pairs.values())
    stack: list[tuple[str, int]] = []
    findings: list[dict[str, Any]] = []
    for position, char in enumerate(masked):
        if char in openings:
            stack.append((char, position))
        elif char in pairs:
            line_number = source.count("\n", 0, position) + 1
            if not stack or stack[-1][0] != pairs[char]:
                line = source.splitlines()[line_number - 1]
                findings.append(
                    _finding(
                        "JavaUnmatchedDelimiter",
                        f"Closing delimiter {char!r} has no matching opener in the inspected source.",
                        line_number,
                        "Check the nearby parentheses, brackets, and braces.",
                        "High confidence for this unmatched closing delimiter.",
                        line,
                    )
                )
            else:
                stack.pop()
    for opening, position in stack:
        line_number = source.count("\n", 0, position) + 1
        line = source.splitlines()[line_number - 1]
        expected = {"(": ")", "[": "]", "{": "}"}[opening]
        findings.append(
            _finding(
                "JavaUnmatchedDelimiter",
                f"Opening delimiter {opening!r} is not closed; expected {expected!r}.",
                line_number,
                "Add the matching closing delimiter after the complete expression or block.",
                "High confidence for this unmatched opening delimiter.",
                line,
            )
        )
    return findings


def _literal_type_mismatch(declared_type: str, literal: str) -> bool | None:
    literal = literal.strip()
    if literal == "null":
        return declared_type not in {"String"}
    if declared_type == "String":
        if literal.startswith('"') and literal.endswith('"'):
            return False
        if re.fullmatch(r"[+-]?\d+(?:\.\d+)?[fFdDlL]?", literal) or literal in {"true", "false"}:
            return True
        return None
    if declared_type == "char":
        if literal.startswith("'") and literal.endswith("'"):
            return len(literal) < 3
        if literal.startswith('"') or literal in {"true", "false"}:
            return True
        return None
    if declared_type == "boolean":
        if literal in {"true", "false"}:
            return False
        if re.fullmatch(r"[+-]?\d+(?:\.\d+)?[fFdDlL]?", literal) or literal.startswith(('"', "'")):
            return True
        return None
    integer_literal = re.fullmatch(r"[+-]?\d+[lL]?", literal)
    numeric_literal = re.fullmatch(
        r"[+-]?(?:\d+\.\d*|\.\d+|\d+)(?:[eE][+-]?\d+)?[fFdDlL]?", literal
    )
    if not numeric_literal:
        if literal.startswith(('"', "'")) or literal in {"true", "false"}:
            return True
        return None
    if declared_type in {"byte", "short", "int", "long"}:
        if not integer_literal:
            return True
        suffix = literal[-1:].lower() if literal[-1:].isalpha() else ""
        if suffix == "l" and declared_type != "long":
            return True
        try:
            value = int(literal.rstrip("lL"))
        except ValueError:
            return True
        bounds = {
            "byte": (-128, 127),
            "short": (-32768, 32767),
            "int": (-(2**31), 2**31 - 1),
            "long": (-(2**63), 2**63 - 1),
        }
        lower, upper = bounds[declared_type]
        if not lower <= value <= upper:
            return True
        return declared_type == "long" and not suffix and not -(2**31) <= value <= 2**31 - 1
    if declared_type == "float":
        suffix = literal[-1:].lower() if literal[-1:].isalpha() else ""
        return suffix == "d"
    if declared_type == "double":
        return False
    return False


def analyze_java(source: str) -> dict[str, Any]:
    """Report only beginner Java issues identified by narrow textual rules."""
    if not isinstance(source, str) or not source.strip():
        return {
            "status": "empty",
            "source_valid": False,
            "summary": "Enter Java code to begin an analysis.",
            "findings": [],
        }

    findings = _delimiter_findings(source)
    commentless = _strip_comments(source)
    lines = source.splitlines()
    commentless_lines = commentless.splitlines()
    declared_names = {match.group("name") for match in _DECLARATION_RE.finditer(commentless)}
    main_match = re.search(r"main\s*\(\s*String\s*\[\s*\]\s*([A-Za-z_$][\w$]*)", commentless)
    if main_match:
        declared_names.add(main_match.group(1))

    for line_number, (line, code_line) in enumerate(zip(lines, commentless_lines), start=1):
        stripped = code_line.strip()
        if not stripped:
            continue

        print_without_parens = _PRINT_WITHOUT_PARENS_RE.search(code_line)
        if print_without_parens:
            start = code_line.index("println", print_without_parens.start()) + len("println")
            end = print_without_parens.end("literal")
            literal = print_without_parens.group("literal")
            findings.append(
                _finding(
                    "JavaPrintlnSyntax",
                    "System.out.println needs parentheses around its argument.",
                    line_number,
                    "Write the value inside parentheses, for example System.out.println(\"text\");",
                    "High confidence for this simple literal-print form.",
                    line,
                    replacement=(start, end, f"({literal})"),
                )
            )
            if not print_without_parens.group("semicolon"):
                findings.append(
                    _finding(
                        "JavaMissingSemicolon",
                        "This println statement is missing a semicolon.",
                        line_number,
                        "End the statement with a semicolon.",
                        "High confidence for this recognized println statement.",
                        line,
                        replacement=(len(code_line.rstrip()), len(code_line.rstrip()), ";"),
                    )
                )
            continue

        main_case = _MAIN_CAPITALIZATION_RE.search(code_line)
        if main_case:
            start = main_case.start() + len(main_case.group(1))
            end = start + len("Main")
            findings.append(
                _finding(
                    "JavaMainCapitalization",
                    "Java's conventional entry-point method is lowercase main, not Main.",
                    line_number,
                    "Change Main to main in the method declaration.",
                    "High confidence for this entry-point spelling.",
                    line,
                    replacement=(start, end, "main"),
                )
            )

        if not stripped.endswith(";") and any(
            pattern.match(code_line) for pattern in _MISSING_SEMICOLON_PATTERNS
        ):
            insertion = len(code_line.rstrip())
            findings.append(
                _finding(
                    "JavaMissingSemicolon",
                    "This recognized Java statement appears to be missing a semicolon.",
                    line_number,
                    "End the declaration or println statement with a semicolon.",
                    "High confidence for this simple statement form.",
                    line,
                    replacement=(insertion, insertion, ";"),
                )
            )

        assignment = _ASSIGNMENT_RE.match(code_line)
        if assignment and assignment.group(1) not in declared_names and main_match:
            name = assignment.group(1)
            findings.append(
                _finding(
                    "JavaUndeclaredVariable",
                    f"No declaration for {name!r} was found in this source before its assignment.",
                    line_number,
                    f"Declare {name} with its intended type before assigning to it.",
                    "Possible: external fields and complex Java scopes are not resolved.",
                    line,
                )
            )

    for match in _DECLARATION_RE.finditer(commentless):
        initializer = match.group("value")
        if initializer is None or _literal_type_mismatch(match.group("type"), initializer) is not True:
            continue
        line_number = source.count("\n", 0, match.start()) + 1
        line = lines[line_number - 1]
        findings.append(
            _finding(
                "JavaTypeMismatch",
                f"The literal initializer does not match the declared type {match.group('type')!r}.",
                line_number,
                "Make the initializer and declared type agree; the intended value cannot be inferred safely.",
                "High confidence for this direct literal assignment.",
                line,
            )
        )

    if findings:
        summary = f"Found {len(findings)} possible Java issue(s) using limited static rules."
        status = "findings"
    else:
        summary = "No issues were identified by the available Java checks."
        status = "clean"
    return {
        "status": status,
        "source_valid": None,
        "summary": summary,
        "findings": findings,
    }


def suggest_java_fix(source: str, findings: list[dict[str, Any]]) -> dict[str, Any]:
    suggested = source
    for line_number, start, end, text in sorted(
        (
            (finding["line_number"], *finding["replacement"])
            for finding in findings
            if "replacement" in finding
        ),
        reverse=True,
    ):
        lines = suggested.splitlines(keepends=True)
        line = lines[line_number - 1]
        lines[line_number - 1] = line[:start] + text + line[end:]
        suggested = "".join(lines)
    has_suggestion = suggested != source
    diff = "".join(
        difflib.unified_diff(
            source.splitlines(keepends=True),
            suggested.splitlines(keepends=True),
            fromfile="original.java",
            tofile="suggested.java",
        )
    )
    return {
        "original_code": source,
        "suggested_code": suggested if has_suggestion else None,
        "attempted_code": suggested if has_suggestion else None,
        "has_suggestion": has_suggestion,
        "reason": (
            "Applied only high-confidence Java text corrections."
            if has_suggestion
            else "No unambiguous automatic Java correction was identified."
        ),
        "confidence": "Review the suggested Java changes before use.",
        "verified": False,
        "compiles": None,
        "compilation_passed": None,
        "compilation_error": None,
        "diff": diff,
    }


def explain_java_findings(findings: list[dict[str, Any]], corrected_example: str | None = None) -> list[dict[str, Any]]:
    lessons = {
        "JavaMissingSemicolon": ("Java statements usually end with a semicolon.", "A recognized declaration or println statement ends without one."),
        "JavaUnmatchedDelimiter": ("Parentheses and braces must be paired.", "A delimiter in this source has no matching partner."),
        "JavaUndeclaredVariable": ("Java variables need declarations before use.", "No matching declaration was found in the inspected source."),
        "JavaTypeMismatch": ("Java declarations have explicit types.", "A direct literal initializer is incompatible with the declared type."),
        "JavaMainCapitalization": ("Java method names are case-sensitive.", "The conventional program entry point is spelled main."),
        "JavaPrintlnSyntax": ("println arguments belong inside parentheses.", "The recognized call places a literal after println without parentheses."),
    }
    result = []
    for finding in findings:
        what, why = lessons.get(
            finding["error_type"],
            ("This may be a Java syntax issue.", finding["message"]),
        )
        result.append(
            {
                "error_type": finding["error_type"],
                "what_it_means": what,
                "why_it_likely_happened": why,
                "how_to_fix": finding["next_action"],
                "corrected_example": corrected_example,
                "concept": "Java syntax and declarations",
                "prevention_tip": "Check exact spelling, delimiter pairs, statement endings, and declared types.",
                "basis": "Limited rule-based Java source inspection; no compiler was invoked.",
            }
        )
    return result


def verify_java_fix() -> dict[str, Any]:
    return {
        "status": "unsupported",
        "compilation": {
            "ran": False,
            "passed": None,
            "detail": "Java compilation is unsupported; source was not compiled or executed.",
        },
        "trusted_tests": [],
        "complete_for_fixture": False,
        "candidate_executed": False,
        "warning": "Java compile and behavioral verification are unsupported. No Java compiler, shell command, or submitted-code execution was used.",
    }


def predict_java_output(source: str) -> dict[str, str]:
    """Backward-compatible entry point for Java output prediction."""
    return _predict_java_output(source)