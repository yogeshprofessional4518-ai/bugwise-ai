"""Educational sample cases. They are fixtures, not shortcuts for analyzing input."""

EXAMPLES = {
    "Undefined variable": {
        "id": "undefined-variable",
        "original_code": "total = 7\nprint(totla)\n",
        "expected_diagnosis": "Likely NameError: 'totla' resembles the defined name 'total'.",
        "detection_basis": "Statically detected as an unresolved name; runtime scope and dynamic definitions are not evaluated.",
        "corrected_code": "total = 7\nprint(total)\n",
        "trusted_tests": [],
    },
    "Missing colon": {
        "id": "missing-colon",
        "original_code": "if True\n    print('ready')\n",
        "expected_diagnosis": "SyntaxError at the if statement: the block header needs a colon.",
        "detection_basis": "Confirmed statically by Python's parser; the source is not executed.",
        "corrected_code": "if True:\n    print('ready')\n",
        "trusted_tests": [],
    },
    "Incorrect indentation": {
        "id": "incorrect-indentation",
        "original_code": "def greet():\nprint('hello')\n",
        "expected_diagnosis": "IndentationError: the function body is not indented.",
        "detection_basis": "Confirmed statically by Python's parser; the source is not executed.",
        "corrected_code": "def greet():\n    print('hello')\n",
        "trusted_tests": [],
    },
    "Division by zero": {
        "id": "division-by-zero",
        "original_code": "result = 10 / 0\n",
        "expected_diagnosis": "Potential ZeroDivisionError: the divisor is zero.",
        "detection_basis": "Statically detected from a literal divisor; whether execution reaches it is not tested.",
        "corrected_code": "result = 10 / 2\n",
        "trusted_tests": [
            {"name": "10 divided by 2", "operation": "divide", "input": [10, 2], "expected": 5}
        ],
    },
    "Invalid list index": {
        "id": "invalid-list-index",
        "original_code": "items = ['red', 'blue']\nprint(items[2])\n",
        "expected_diagnosis": "Potential IndexError: valid positions are 0 and 1.",
        "detection_basis": "Statically detected from a literal list and index; runtime control flow is not tested.",
        "corrected_code": "items = ['red', 'blue']\nprint(items[1])\n",
        "trusted_tests": [
            {"name": "Second item", "operation": "list_item", "input": {"items": ["red", "blue"], "index": 1}, "expected": "blue"}
        ],
    },
    "Missing dictionary key": {
        "id": "missing-dictionary-key",
        "original_code": "person = {'name': 'Ada'}\nprint(person['age'])\n",
        "expected_diagnosis": "Potential KeyError: the 'age' key is absent.",
        "detection_basis": "Statically detected from a literal dictionary and key; runtime control flow is not tested.",
        "corrected_code": "person = {'name': 'Ada'}\nprint(person.get('age', 'unknown'))\n",
        "trusted_tests": [
            {"name": "Missing age default", "operation": "dict_default", "input": {}, "expected": "unknown"}
        ],
    },
    "Incorrect data type": {
        "id": "incorrect-data-type",
        "original_code": "age = 20\nprint('Age: ' + age)\n",
        "expected_diagnosis": "Potential TypeError: a string and integer cannot be concatenated directly.",
        "detection_basis": "Statically detected from literal operand types; runtime control flow is not tested.",
        "corrected_code": "age = 20\nprint(f'Age: {age}')\n",
        "trusted_tests": [
            {"name": "Format age", "operation": "format_age", "input": 20, "expected": "Age: 20"}
        ],
    },
    "Invalid integer conversion": {
        "id": "invalid-integer-conversion",
        "original_code": "number = int('ten')\n",
        "expected_diagnosis": "Potential ValueError: 'ten' is not an integer representation.",
        "detection_basis": "Statically detected from a literal conversion argument; runtime control flow is not tested.",
        "corrected_code": "number = int('10')\n",
        "trusted_tests": [
            {"name": "Parse integer text", "operation": "parse_integer", "input": "10", "expected": 10}
        ],
    },
    "Incorrect loop logic": {
        "id": "incorrect-loop-logic",
        "original_code": "total = 0\nfor number in [1, 2, 3, 4]:\n    total = number\n",
        "expected_diagnosis": "Logical issue: assignment keeps only the last item instead of accumulating.",
        "detection_basis": "Sample teaching note only; arbitrary logical behavior requires tests and is not inferred statically.",
        "corrected_code": "total = 0\nfor number in [1, 2, 3, 4]:\n    total += number\n",
        "python_concept": "An accumulator combines each loop value; assignment replaces the previous value.",
        "prevention_tip": "Initialize an accumulator before the loop and check whether each iteration adds or replaces.",
        "trusted_tests": [
            {"name": "Sum four values", "operation": "sum_numbers", "input": [1, 2, 3, 4], "expected": 10}
        ],
    },
    "Incorrect calculation": {
        "id": "incorrect-calculation",
        "original_code": "length = 5\nwidth = 4\narea = length + width\n",
        "expected_diagnosis": "Logical issue: rectangle area is length multiplied by width, not added.",
        "detection_basis": "Sample teaching note only; arbitrary logical behavior requires tests and is not inferred statically.",
        "corrected_code": "length = 5\nwidth = 4\narea = length * width\n",
        "python_concept": "A rectangle's area is the product of its side lengths.",
        "prevention_tip": "Write down the intended formula and verify it with a small known example.",
        "trusted_tests": [
            {"name": "Rectangle area", "operation": "rectangle_area", "input": [5, 4], "expected": 20}
        ],
    },
    "Clean Python code": {
        "id": "clean-python-code",
        "original_code": "def add(left, right):\n    return left + right\n\nresult = add(2, 3)\n",
        "expected_diagnosis": "No issues found by the available static checks.",
        "detection_basis": "Static checks found no issue; this does not prove runtime behavior or correctness.",
        "corrected_code": None,
        "trusted_tests": [],
    },
}


def find_example_for_source(source: str) -> dict | None:
    """Return the fixture only when the editor contains that exact original sample."""
    return next(
        (
            example
            for example in EXAMPLES.values()
            if source == example["original_code"]
        ),
        None,
    )
