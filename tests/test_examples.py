from analyzer import analyze_code
from examples import EXAMPLES, get_detection_basis


def test_requested_example_cases_have_expected_static_outcomes():
    cases = {
        "Missing colon": "SyntaxError",
        "Undefined variable": "NameError",
        "Invalid list index": "IndexError",
        "Division by zero": "ZeroDivisionError",
        "Incorrect data type": "TypeError",
    }
    for title, expected_type in cases.items():
        sample = EXAMPLES[title]
        result = analyze_code(sample["original_code"])
        assert expected_type in {finding["error_type"] for finding in result["findings"]}
        assert sample["detection_basis"]

    clean = EXAMPLES["Clean Python code"]
    assert analyze_code(clean["original_code"])["status"] == "clean"
    assert clean["detection_basis"]


def test_every_example_explains_detection_limits():
    assert all(sample.get("detection_basis") for sample in EXAMPLES.values())


def test_detection_basis_is_available_for_samples_with_or_without_metadata():
    assert get_detection_basis({"detection_basis": "Static AST analysis."}) == (
        "Static AST analysis."
    )
    assert get_detection_basis({}) == "Detection details unavailable."
