"""Conservative source suggestions; the submitted text is never overwritten."""

from __future__ import annotations

import ast
import builtins
import difflib
import re
import symtable
from typing import Any

from analyzer import analyze_code

_BLOCK_HEADER = re.compile(
    r"^\s*(?:async\s+)?(?:if|elif|else|for|while|def|class|try|except|finally|with)\b"
)


def _replace_name(source: str, name: str, replacement: str) -> str:
    tree = ast.parse(source)
    spans = [
        (node.lineno, node.col_offset, node.end_lineno, node.end_col_offset)
        for node in ast.walk(tree)
        if isinstance(node, ast.Name) and node.id == name and isinstance(node.ctx, ast.Load)
    ]
    lines = source.splitlines(keepends=True)
    for start_line, start_col, end_line, end_col in sorted(spans, reverse=True):
        line = lines[start_line - 1]
        start_char = len(line.encode("utf-8")[:start_col].decode("utf-8", errors="ignore"))
        end_char = len(line.encode("utf-8")[:end_col].decode("utf-8", errors="ignore"))
        lines[start_line - 1] = line[:start_char] + replacement + line[end_char:]
    return "".join(lines)


def _unique_name_suggestion(source: str, symbol: str) -> str | None:
    try:
        tree = ast.parse(source)
        table = symtable.symtable(source, "<submitted code>", "exec")
    except SyntaxError:
        return None

    candidates = set(dir(builtins))
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            candidates.add(node.name)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Param)):
            candidates.add(node.id)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                candidates.add(alias.asname or alias.name.split(".")[0])

    try:
        candidates.update(
            item.get_name()
            for item in table.get_symbols()
            if item.is_assigned() or item.is_imported()
        )
    except AttributeError:
        pass

    candidates.discard(symbol)
    matches = difflib.get_close_matches(symbol, sorted(candidates), n=2, cutoff=0.8)
    if len(matches) != 1:
        return None
    return matches[0]


def get_fix_options(findings: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Return syntax-checked alternatives for supported list-index diagnostics."""
    options: list[dict[str, str]] = []
    for finding in findings:
        if finding.get("error_type") != "IndexError":
            continue
        name = finding.get("container_name")
        index = finding.get("index_value")
        if not isinstance(name, str) or not name.isidentifier():
            continue
        if not isinstance(index, int) or isinstance(index, bool):
            continue

        candidates = [
            {
                "label": "Guard the access",
                "when_to_use": (
                    "Use this when skipping the access is acceptable if the index is outside "
                    "the list's valid range. Replace the placeholder list and decide what the "
                    "program should do when the index is invalid."
                ),
                "code": (
                    f"{name} = [...]  # Replace with your list values.\n"
                    f"if -len({name}) <= {index} < len({name}):\n"
                    f"    print({name}[{index}])  # Replace with the operation you intend.\n"
                ),
            },
            {
                "label": "Iterate over the list",
                "when_to_use": (
                    "Use this when the goal is to process every item in the list and the position itself "
                    "does not matter. Replace the placeholder list and example body with the "
                    "values and operation you intend."
                ),
                "code": (
                    f"{name} = [...]  # Replace with your list values.\n"
                    f"for item in {name}:\n"
                    "    print(item)  # Replace with the operation you intend.\n"
                ),
            },
        ]
        for option in candidates:
            try:
                compile(option["code"], "<BugWise fix option>", "exec")
            except (SyntaxError, ValueError, TypeError):
                continue
            options.append(option)
    return options


def suggest_fix(
    source: str,
    findings: list[dict[str, Any]] | None = None,
    educational_example: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return an optional suggestion with diff and explicit, initially-unverified state."""
    findings = findings if findings is not None else analyze_code(source)["findings"]
    suggested = source
    attempted_code: str | None = None
    reason = ""
    confidence = "No safe automatic correction was identified."

    name_error = next((item for item in findings if item["error_type"] == "NameError"), None)
    if name_error and name_error.get("symbol"):
        candidate = _unique_name_suggestion(source, name_error["symbol"])
        if candidate:
            suggested = _replace_name(source, name_error["symbol"], candidate)
            reason = f"Replaced the unresolved name with its unique close match, {candidate!r}."
            confidence = "Likely typo correction; review it before use."

    if suggested == source:
        syntax_finding = next(
            (item for item in findings if item["error_type"] == "SyntaxError"), None
        )
        if syntax_finding:
            lines = source.splitlines(keepends=True)
            line_number = syntax_finding.get("line_number")
            if line_number and 1 <= line_number <= len(lines):
                line = lines[line_number - 1]
                content = line.rstrip("\r\n")
                if _BLOCK_HEADER.match(content) and not content.rstrip().endswith(":"):
                    suffix = line[len(content):]
                    lines[line_number - 1] = content + ":" + suffix
                    suggested = "".join(lines)
                    attempted_code = suggested
                    reason = "Inserted the missing block delimiter."
                    confidence = "Conservative syntactic suggestion."

    if suggested == source:
        indent_finding = next(
            (item for item in findings if item["error_type"] == "IndentationError"), None
        )
        line_number = indent_finding.get("line_number") if indent_finding else None
        source_line = indent_finding.get("source_line") if indent_finding else None
        if (
            indent_finding
            and "expected an indented block" in indent_finding["message"].lower()
            and line_number
            and source_line is not None
            and line_number <= len(source.splitlines())
        ):
            lines = source.splitlines(keepends=True)
            target = lines[line_number - 1]
            leading = target[: len(target) - len(target.lstrip())]
            lines[line_number - 1] = leading + "    " + target[len(leading):]
            suggested = "".join(lines)
            attempted_code = suggested
            reason = "Indented the statement immediately following a block header."
            confidence = "Likely correction for a missing block indentation."

    if (
        suggested == source
        and educational_example
        and source == educational_example.get("original_code")
        and educational_example.get("corrected_code")
    ):
        suggested = educational_example["corrected_code"]
        attempted_code = suggested
        reason = "Known correction for this exact educational sample; review before use."
        confidence = "Known correction for this exact educational sample."

    compilation_error: str | None = None
    compilation_passed: bool | None = None
    if attempted_code is None and suggested != source:
        attempted_code = suggested
    if attempted_code is not None:
        try:
            compile(attempted_code, "<suggested code>", "exec")
            compilation_passed = True
        except (SyntaxError, ValueError, TypeError) as error:
            compilation_passed = False
            compilation_error = f"{type(error).__name__}: {error}"
            suggested = source
            reason = "The proposed correction did not pass Python compilation and is hidden."
            confidence = "This proposed correction is not offered because it failed compilation."
    diff_code = attempted_code if attempted_code is not None else suggested
    diff = "".join(
        difflib.unified_diff(
            source.splitlines(keepends=True),
            diff_code.splitlines(keepends=True),
            fromfile="original.py",
            tofile="suggested.py",
        )
    )
    has_suggestion = suggested != source
    return {
        "original_code": source,
        "suggested_code": suggested if has_suggestion else None,
        "attempted_code": attempted_code,
        "has_suggestion": has_suggestion,
        "reason": reason if has_suggestion else "No unambiguous correction was found.",
        "confidence": confidence,
        "verified": False,
        "compiles": compilation_passed is True,
        "compilation_passed": compilation_passed,
        "compilation_error": compilation_error,
        "diff": diff,
    }
