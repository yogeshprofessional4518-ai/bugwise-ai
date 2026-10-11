from analyzer import analyze_code


def test_valid_code_is_clean():
    result = analyze_code("value = 2 + 3\n")
    assert result["status"] == "clean"
    assert result["source_valid"] is True
    assert result["findings"] == []


def test_syntax_error_has_location_and_consistent_shape():
    result = analyze_code("if True\n    pass\n")
    finding = result["findings"][0]
    assert finding["error_type"] == "SyntaxError"
    assert finding["line_number"] == 1
    assert {"category", "message", "confidence", "next_action"} <= finding.keys()


def test_leading_blank_line_preserves_original_syntax_error_line_number():
    result = analyze_code("\nif True\n    pass\n")
    finding = result["findings"][0]
    assert finding["error_type"] == "SyntaxError"
    assert finding["line_number"] == 2
    assert finding["source_line"].strip() == "if True"


def test_missing_colon_syntax_error_precedes_static_name_checks():
    result = analyze_code("if True\n    print(undefined_name)\n")
    assert result["findings"][0]["error_type"] == "SyntaxError"
    assert len(result["findings"]) == 1


def test_undefined_name_is_reported_with_line_number():
    result = analyze_code("value = 1\nprint(missing_name)\n")
    finding = next(item for item in result["findings"] if item["error_type"] == "NameError")
    assert finding["line_number"] == 2
    assert finding["symbol"] == "missing_name"


def test_invalid_literal_list_index_is_reported():
    result = analyze_code("items = ['a', 'b']\nprint(items[2])\n")
    finding = next(item for item in result["findings"] if item["error_type"] == "IndexError")
    assert finding["line_number"] == 2


def test_valid_python_has_no_findings():
    result = analyze_code("items = ['a', 'b']\nprint(items[1])\n")
    assert result["source_valid"] is True
    assert result["findings"] == []


def test_indentation_error_is_distinguished():
    result = analyze_code("def greet():\nprint('hi')\n")
    assert result["findings"][0]["error_type"] == "IndentationError"


def test_empty_input_is_handled():
    assert analyze_code("  ")["status"] == "empty"


def test_common_static_and_literal_findings():
    cases = {
        "print(missing_name)": "NameError",
        "value = 8 / 0": "ZeroDivisionError",
        "items = [1]\nprint(items[3])": "IndexError",
        "data = {'x': 1}\nprint(data['y'])": "KeyError",
        "label = 'x' + 4": "TypeError",
        "age = 20\nlabel = 'Age: ' + age": "TypeError",
        "number = int('nope')": "ValueError",
        "text = 'hi'\ntext.append('!')": "AttributeError",
    }
    for source, error_type in cases.items():
        findings = analyze_code(source)["findings"]
        assert error_type in {item["error_type"] for item in findings}


def test_missing_import_is_reported_without_importing_it():
    findings = analyze_code("import bugwise_module_that_does_not_exist\n")["findings"]
    assert any(item["error_type"] == "ModuleNotFoundError" for item in findings)
