from analyzer import analyze_code
from examples import EXAMPLES, find_example_for_source
from explainer import explain_findings
from fixer import get_fix_options, suggest_fix


def test_unique_typo_gets_suggested_without_mutating_input():
    source = "count = 3\nprint(coutn)\n"
    result = suggest_fix(source, analyze_code(source)["findings"])
    assert source == "count = 3\nprint(coutn)\n"
    assert result["suggested_code"] == "count = 3\nprint(count)\n"
    assert result["verified"] is False
    assert result["compilation_passed"] is True
    assert "coutn" in result["diff"]


def test_ambiguous_or_unrelated_name_is_not_changed():
    source = "print(unknown_value)\n"
    result = suggest_fix(source, analyze_code(source)["findings"])
    assert result["has_suggestion"] is False
    assert result["suggested_code"] is None


def test_missing_colon_is_fixed_only_for_recognized_block_header():
    source = "if True\n    print('ok')\n"
    result = suggest_fix(source, analyze_code(source)["findings"])
    assert result["suggested_code"] == "if True:\n    print('ok')\n"
    assert result["compiles"] is True
    assert result["compilation_passed"] is True
    assert "awaiting syntax validation" not in result["confidence"]
    assert result["diff"].splitlines()[-3:] == [
        "-if True",
        "+if True:",
        "     print('ok')",
    ]
    assert result["attempted_code"] == result["suggested_code"]
    assert result["reason"] != result["confidence"]


def test_unsafe_or_unrecognized_syntax_is_not_guessed():
    source = "value = (1 + )\n"
    result = suggest_fix(source, analyze_code(source)["findings"])
    assert result["suggested_code"] is None


def test_non_compiling_educational_correction_is_not_returned():
    source = "print(value)\n"
    malformed_example = {
        "original_code": source,
        "corrected_code": "if True\n    print(value)\n",
    }
    result = suggest_fix(source, [], educational_example=malformed_example)
    assert result["suggested_code"] is None
    assert result["has_suggestion"] is False
    assert result["compiles"] is False
    assert result["compilation_passed"] is False
    assert result["attempted_code"] == malformed_example["corrected_code"]
    assert result["diff"]
    assert "SyntaxError" in result["compilation_error"]


def test_logical_sample_correction_requires_exact_educational_input():
    sample = EXAMPLES["Incorrect loop logic"]
    assert find_example_for_source(sample["original_code"]) is sample
    assert find_example_for_source(sample["original_code"] + "# edited\n") is None
    result = suggest_fix(
        sample["original_code"],
        analyze_code(sample["original_code"])["findings"],
        educational_example=sample,
    )
    assert result["suggested_code"] == sample["corrected_code"]
    assert result["verified"] is False
    assert result["compiles"] is True
    assert (
        explain_findings(
            [{"error_type": "NameError", "message": "name issue", "next_action": "define it"}],
            result["suggested_code"],
        )[0]["corrected_example"]
        == sample["corrected_code"]
    )


def test_list_index_fix_options_are_labeled_and_compile():
    source = "items = ['a', 'b']\nprint(items[3])\n"
    findings = analyze_code(source)["findings"]
    options = get_fix_options(findings)

    assert [option["label"] for option in options] == [
        "Guard the access",
        "Iterate over the list",
    ]
    assert "skipping the access is acceptable" in options[0]["when_to_use"]
    assert "process every item" in options[1]["when_to_use"]
    assert "items[3]" in options[0]["code"]
    assert all("items = [...]" in option["code"] for option in options)
    for option in options:
        compiled = compile(option["code"], "<test>", "exec")
        assert compiled is not None


def test_list_index_options_do_not_guess_a_replacement_index():
    findings = analyze_code("items = ['a', 'b']\nprint(items[3])\n")["findings"]
    options = get_fix_options(findings)

    assert all("items[1]" not in option["code"] for option in options)
    assert all("not automatic edits" not in option["when_to_use"] for option in options)


def test_unsupported_index_error_has_no_fix_options():
    findings = [{"error_type": "IndexError", "line_number": 3}]
    assert get_fix_options(findings) == []
