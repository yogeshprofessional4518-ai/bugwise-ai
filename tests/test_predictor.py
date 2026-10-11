from predictor import predict_output


def test_predicts_arithmetic_print():
    assert predict_output("print(10 + 20)") == {
        "status": "predicted",
        "output": "30\n",
        "message": "",
    }


def test_predicts_sequential_assignments():
    result = predict_output("a = 10; b = 20; print(a + b)")
    assert result["status"] == "predicted"
    assert result["output"] == "30\n"


def test_predicts_string_print():
    assert predict_output('print("Hello BugWise AI")')["output"] == "Hello BugWise AI\n"


def test_predicts_division():
    assert predict_output("print(10 / 2)")["output"] == "5.0\n"


def test_predicts_boolean_and_string_assignments():
    result = predict_output(
        'greeting = "Hello"\nenabled = True\nif enabled:\n    print(greeting, enabled)'
    )
    assert result["status"] == "predicted"
    assert result["output"] == "Hello True\n"


def test_predicts_remaining_arithmetic_operators():
    result = predict_output("print(8 - 3, 3 * 4, 7 // 2, 7 % 2, 2 ** 3)")
    assert result["status"] == "predicted"
    assert result["output"] == "5 12 3 1 8\n"


def test_reports_division_by_zero_without_output():
    result = predict_output("print(10 / 0)")
    assert result["status"] == "error"
    assert result["message"] == "ZeroDivisionError: division by zero"
    assert result["output"] == ""


def test_reports_undefined_variable():
    result = predict_output("print(unknown_variable)")
    assert result["status"] == "error"
    assert result["message"] == "NameError: name 'unknown_variable' is not defined"


def test_reports_syntax_error():
    result = predict_output("if True\n    print('bad')")
    assert result["status"] == "error"
    assert result["message"].startswith("SyntaxError on line 1:")


def test_rejects_loops_and_non_print_calls():
    loop = predict_output("for item in [1, 2]:\n    print(item)")
    malicious = predict_output("print(__import__('os').system('echo unsafe'))")
    assert loop["status"] == "unavailable"
    assert malicious["status"] == "unavailable"
    unavailable = "Prediction unavailable for this code. The program was not executed."
    assert loop["message"] == unavailable
    assert malicious["message"] == unavailable


def test_rejects_shadowing_the_print_builtin():
    result = predict_output("print = 3\nprint(1)")
    assert result["status"] == "unavailable"


def test_preserves_print_order():
    result = predict_output('print("first")\nprint("second")')
    assert result["output"] == "first\nsecond\n"


def test_predicts_only_the_determinable_conditional_branch():
    result = predict_output('value = 3\nif value > 2:\n    print("yes")\nelse:\n    print("no")')
    assert result["status"] == "predicted"
    assert result["output"] == "yes\n"


def test_rejects_extremely_large_expressions():
    result = predict_output("print(2 ** 100000000)")
    assert result["status"] == "unavailable"
    assert result["output"] == ""


def test_rejects_excessively_nested_expressions():
    result = predict_output("print(" + "-" * 40 + "1)")
    assert result["status"] == "unavailable"