from java_predictor import UNAVAILABLE_MESSAGE, predict_java_output


def test_predicts_requested_integer_sum_and_string_concatenation():
    source = 'int a = 10; int b = 20; int sum = a + b; System.out.println("Sum: " + sum);'
    result = predict_java_output(source)

    assert result == {"status": "predicted", "output": "Sum: 30\n", "message": ""}


def test_predicts_literal_println_and_integer_arithmetic():
    result = predict_java_output(
        'int total = (8 + 4) * 2 - 6 / 3; System.out.println(total);'
    )
    assert result["status"] == "predicted"
    assert result["output"] == "22\n"


def test_predicts_string_variable_concatenation_with_integer_variable():
    source = 'String label = "Sum: "; int sum = 10 + 20; System.out.println(label + sum);'
    result = predict_java_output(source)
    assert result["status"] == "predicted"
    assert result["output"] == "Sum: 30\n"


def test_accepts_supported_statements_inside_conventional_main_wrapper():
    source = (
        "public class Main {\n"
        "  public static void main(String[] args) {\n"
        '    int a = 10; System.out.println("value=" + a);\n'
        "  }\n"
        "}\n"
    )
    result = predict_java_output(source)
    assert result["status"] == "predicted"
    assert result["output"] == "value=10\n"


def test_java_integer_division_truncates_toward_zero():
    result = predict_java_output("int quotient = -7 / 2; System.out.println(quotient);")
    assert result["status"] == "predicted"
    assert result["output"] == "-3\n"


def test_division_by_zero_is_a_predicted_error_without_partial_output():
    result = predict_java_output(
        'System.out.println("before"); int value = 1 / 0; System.out.println(value);'
    )
    assert result["status"] == "error"
    assert result["message"] == "ArithmeticException: / by zero"
    assert result["output"] == ""


def test_rejects_unsupported_statements_and_unknown_calls():
    for source in (
        "for (int i = 0; i < 2; i++) { System.out.println(i); }",
        "System.out.print(1);",
        "int value = Integer.parseInt(input); System.out.println(value);",
        "int value = 1; value += 2; System.out.println(value);",
    ):
        assert predict_java_output(source) == {
            "status": "unavailable",
            "output": "",
            "message": UNAVAILABLE_MESSAGE,
        }


def test_rejects_unsupported_types_and_division_overflow():
    assert predict_java_output("double value = 1.5; System.out.println(value);")["status"] == "unavailable"
    result = predict_java_output("int value = -2147483648 / -1; System.out.println(value);")
    assert result["status"] == "unavailable"


def test_rejects_missing_semicolons_and_unbounded_source():
    assert predict_java_output('System.out.println("hello")')["status"] == "unavailable"
    assert predict_java_output(" " * 20_001)["status"] == "unavailable"


def test_rejects_octal_looking_leading_zero_integer_literal():
    result = predict_java_output("int value = 010; System.out.println(value);")
    assert result["status"] == "unavailable"
    assert result["message"] == UNAVAILABLE_MESSAGE