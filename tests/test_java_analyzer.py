from java_analyzer import (
    analyze_java,
    predict_java_output,
    suggest_java_fix,
    verify_java_fix,
)
from java_examples import JAVA_EXAMPLES, find_java_example_for_source


def _finding_types(source):
    return {finding["error_type"] for finding in analyze_java(source)["findings"]}


def test_reports_missing_semicolon_and_suggests_safe_correction():
    source = (
        "class Main {\n"
        "  public static void main(String[] args) {\n"
        "    System.out.println(\"Hi\")\n"
        "  }\n"
        "}\n"
    )
    analysis = analyze_java(source)
    assert "JavaMissingSemicolon" in _finding_types(source)
    fix = suggest_java_fix(source, analysis["findings"])
    assert fix["suggested_code"].count('println("Hi");') == 1
    assert fix["diff"]


def test_detects_unmatched_delimiters_but_ignores_delimiters_in_comments_and_strings():
    malformed = "class Main {\n  String text = \"(\";\n"
    clean = "class Main { // }\n  String text = \"(\";\n}\n"
    assert "JavaUnmatchedDelimiter" in _finding_types(malformed)
    assert "JavaUnmatchedDelimiter" not in _finding_types(clean)


def test_detects_capitalized_main_and_suggests_lowercase_fix():
    source = "class Main {\n  public static void Main(String[] args) {\n  }\n}\n"
    analysis = analyze_java(source)
    assert "JavaMainCapitalization" in _finding_types(source)
    assert "void main(String[] args)" in suggest_java_fix(source, analysis["findings"])["suggested_code"]


def test_detects_println_missing_parentheses_and_suggests_correction():
    source = "class Main {\n  public static void main(String[] args) {\n    System.out.println \"ready\";\n  }\n}\n"
    analysis = analyze_java(source)
    assert "JavaPrintlnSyntax" in _finding_types(source)
    fix = suggest_java_fix(source, analysis["findings"])
    assert 'System.out.println("ready");' in fix["suggested_code"]


def test_reports_direct_literal_type_mismatch():
    source = 'class Main {\n  int age = "old";\n}\n'
    findings = analyze_java(source)["findings"]
    assert any(item["error_type"] == "JavaTypeMismatch" for item in findings)
    assert any("declared type 'int'" in item["message"] for item in findings)


def test_does_not_guess_type_mismatch_for_unknown_initializer_expression():
    source = "class Main {\n  int age = existingValue;\n}\n"
    assert "JavaTypeMismatch" not in _finding_types(source)


def test_reports_possible_undeclared_local_assignment_cautiously():
    source = "class Main {\n  public static void main(String[] args) {\n    count = 1;\n  }\n}\n"
    finding = next(
        item for item in analyze_java(source)["findings"]
        if item["error_type"] == "JavaUndeclaredVariable"
    )
    assert finding["confidence"].startswith("Possible:")
    assert "complex Java scopes" in finding["confidence"]


def test_predicts_only_literal_println_calls_in_supported_main_wrapper():
    source = (
        "public class Main {\n"
        "  public static void main(String[] args) {\n"
        "    System.out.println(\"first\");\n"
        "    System.out.println(\"second\");\n"
        "  }\n"
        "}\n"
    )
    assert predict_java_output(source) == {
        "status": "predicted",
        "output": "first\nsecond\n",
        "message": "",
    }
    assert predict_java_output(source.replace('"first"', "value"))["status"] == "unavailable"


def test_java_verification_is_explicitly_unsupported_and_never_executes():
    result = verify_java_fix()
    assert result["status"] == "unsupported"
    assert result["compilation"]["passed"] is None
    assert result["candidate_executed"] is False


def test_java_examples_use_shared_sample_shape():
    assert JAVA_EXAMPLES
    for example in JAVA_EXAMPLES.values():
        assert example["id"]
        assert example["original_code"]
        assert example["expected_diagnosis"]
        assert example["detection_basis"]
        assert "trusted_tests" in example
    sample = next(iter(JAVA_EXAMPLES.values()))
    assert find_java_example_for_source(sample["original_code"]) is sample