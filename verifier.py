"""Safe, honest verification: compile submitted text; never execute it."""

from __future__ import annotations

import ast
import math
from typing import Any


def _trusted_actual(operation: str, test_input: Any) -> tuple[Any, str | None]:
    """Run a bounded built-in reference operation on fixture data, never candidate code."""
    if operation == "divide":
        if (
            type(test_input) is list
            and len(test_input) == 2
            and all(type(value) in (int, float) and math.isfinite(value) for value in test_input)
            and test_input[1] != 0
        ):
            return test_input[0] / test_input[1], None
    elif operation == "list_item":
        if (
            type(test_input) is dict
            and type(test_input.get("items")) is list
            and type(test_input.get("index")) is int
            and len(test_input["items"]) <= 100
            and -len(test_input["items"]) <= test_input["index"] < len(test_input["items"])
        ):
            return test_input["items"][test_input["index"]], None
    elif operation == "dict_default":
        if type(test_input) is dict and len(test_input) <= 100:
            return test_input.get("age", "unknown"), None
    elif operation == "format_age":
        if type(test_input) in (int, str):
            return f"Age: {test_input}", None
    elif operation == "parse_integer":
        if type(test_input) is str and len(test_input) <= 100:
            try:
                return int(test_input), None
            except ValueError:
                return None, "Trusted fixture input is not a valid integer string."
    elif operation == "sum_numbers":
        if (
            type(test_input) is list
            and len(test_input) <= 100
            and all(type(value) in (int, float) and math.isfinite(value) for value in test_input)
        ):
            return sum(test_input), None
    elif operation == "rectangle_area":
        if (
            type(test_input) is list
            and len(test_input) == 2
            and all(type(value) in (int, float) and math.isfinite(value) for value in test_input)
        ):
            return test_input[0] * test_input[1], None
    return None, f"Unsupported operation or invalid trusted input for {operation!r}."


def _compile_check(code: str | None) -> dict[str, Any]:
    if code is None:
        return {"ran": False, "passed": False, "detail": "No suggested code is available."}
    try:
        compile(code, "<suggested code>", "exec")
        ast.parse(code, filename="<suggested code>", mode="exec")
    except (SyntaxError, ValueError, TypeError) as error:
        return {"ran": True, "passed": False, "detail": f"{type(error).__name__}: {error}"}
    return {"ran": True, "passed": True, "detail": "Python compilation and AST parsing passed."}


def verify_fix(
    suggested_code: str | None,
    trusted_tests: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Compile candidate code and run allowlisted reference tests, never the candidate."""
    compilation = _compile_check(suggested_code)
    test_results: list[dict[str, Any]] = []
    for test in trusted_tests or []:
        expected = test.get("expected")
        actual, error = _trusted_actual(
            str(test.get("operation", "")),
            test.get("input"),
        )
        passed = error is None and actual == expected
        test_results.append(
            {
                "name": str(test.get("name", "Trusted sample test")),
                "input": test.get("input"),
                "expected": expected,
                "actual": actual,
                "passed": passed,
                "detail": error or "Allowlisted trusted reference operation completed.",
                "basis": "Computed by an allowlisted trusted reference operation; submitted code was not run.",
            }
        )

    tests_passed = bool(test_results) and all(item["passed"] for item in test_results)
    complete = compilation["passed"] and bool(test_results) and tests_passed
    if suggested_code is None:
        status = "not_available"
    elif not compilation["passed"]:
        status = "failed"
    elif not test_results:
        status = "incomplete"
    elif not tests_passed:
        status = "failed"
    else:
        status = "sample_checks_passed"

    return {
        "status": status,
        "compilation": compilation,
        "trusted_tests": test_results,
        "complete_for_fixture": complete,
        "candidate_executed": False,
        "warning": (
            "Submitted code was never executed. Compilation proves syntax only; trusted reference "
            "operations ran on fixture inputs, not on the candidate. Logical correctness for "
            "arbitrary code remains unverified."
        ),
    }
