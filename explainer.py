"""Beginner-friendly, rule-based explanations for analyzer findings."""

from __future__ import annotations

from typing import Any

_LESSONS = {
    "SyntaxError": (
        "Python could not understand the code's grammar.",
        "A required symbol or a valid statement structure may be missing.",
        "Use the indicated line and Python's syntax message to repair the structure.",
        "Python syntax and block structure",
        "Compile small changes often so syntax problems are caught near their source.",
    ),
    "IndentationError": (
        "Python uses indentation to mark which statements belong to a block.",
        "A statement under a function, loop, or condition may not be indented consistently.",
        "Indent the statement to match the block it belongs to.",
        "Indentation and code blocks",
        "Use consistent four-space indentation and avoid mixing tabs and spaces.",
    ),
    "NameError": (
        "Python encountered a name that has not been defined in the analyzed source.",
        "This is often a spelling mismatch, a missing assignment, or a missing import.",
        "Compare the spelling with nearby definitions, or define/import the name.",
        "Names and variable scope",
        "Choose descriptive names and reuse the exact spelling at every reference.",
    ),
    "ZeroDivisionError": (
        "Python cannot divide a number by zero.",
        "The divisor is explicitly zero in this expression.",
        "Check the divisor before dividing, or choose the correct non-zero value.",
        "Arithmetic operators and edge cases",
        "Test boundary values such as zero before performing division.",
    ),
    "IndexError": (
        "A sequence index points outside the available positions.",
        "The literal index is outside the range of the list or tuple shown.",
        "Use a valid index, iterate over the sequence, or check its length.",
        "Sequence indexing",
        "Remember that indexing starts at zero and ends at length minus one.",
    ),
    "KeyError": (
        "A dictionary lookup requested a key that is not present.",
        "The key is absent from the dictionary literal shown.",
        "Check membership first or use dict.get() with a suitable default.",
        "Dictionary lookup",
        "Validate external keys before assuming they exist.",
    ),
    "TypeError": (
        "An operation received values of incompatible types.",
        "This expression adds a string and a number without converting either.",
        "Convert the number to text or format the result with an f-string.",
        "Python types and explicit conversion",
        "Inspect the types on both sides of an operation when it fails.",
    ),
    "ValueError": (
        "A function received a value of the right general type but an invalid format.",
        "The literal text cannot be interpreted as an integer.",
        "Validate the input and handle invalid text before converting it.",
        "Parsing and input validation",
        "Treat user input as untrusted and handle conversion errors deliberately.",
    ),
    "AttributeError": (
        "An object does not provide the requested attribute or method.",
        "The literal receiver is a string, which does not have this list method.",
        "Use an operation supported by the object's type, or use a list.",
        "Objects, types, and methods",
        "Check the object's type and available methods before calling an attribute.",
    ),
    "ModuleNotFoundError": (
        "Python could not locate a module requested by an import.",
        "The package may be missing from the active environment or misspelled.",
        "Check the import spelling and install the package in the selected environment.",
        "Imports and Python environments",
        "Install dependencies in the same environment used to launch the app.",
    ),
}


def explain_findings(
    findings: list[dict[str, Any]],
    corrected_example: str | None = None,
) -> list[dict[str, Any]]:
    """Build transparent rule-based lessons from actual findings."""
    explanations: list[dict[str, Any]] = []
    for finding in findings:
        lesson = _LESSONS.get(finding["error_type"])
        if lesson is None:
            what = f"This may be a {finding['error_type']} problem."
            why = finding["message"]
            how = finding["next_action"]
            concept = "Debugging and error messages"
            tip = "Read the traceback from the bottom up and check the reported line."
        else:
            what, why, how, concept, tip = lesson
        explanations.append(
            {
                "error_type": finding["error_type"],
                "what_it_means": what,
                "why_it_likely_happened": why,
                "how_to_fix": how,
                "corrected_example": corrected_example,
                "concept": concept,
                "prevention_tip": tip,
                "basis": "Rule-based explanation from static analysis; not generated by an LLM.",
            }
        )
    return explanations
