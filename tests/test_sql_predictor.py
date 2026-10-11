from sql_predictor import RESULT_LABEL, UNAVAILABLE_MESSAGE, predict_sql_query
from sql_sample_data import DEPARTMENTS_ROWS, STUDENTS_ROWS, sample_rows_as_dicts


def test_built_in_sample_rows_match_the_requested_dataset():
    assert STUDENTS_ROWS == (
        (1, "Arun", 20, 101),
        (2, "Priya", 21, 102),
        (3, "Kumar", 19, 101),
        (4, "Divya", 22, 103),
        (5, "Ravi", 17, 102),
    )
    assert DEPARTMENTS_ROWS == (
        (101, "AI & DS"),
        (102, "Computer Science"),
        (103, "Information Technology"),
    )
    assert sample_rows_as_dicts("students")[0]["name"] == "Arun"


def test_selects_students_columns_filters_orders_and_limits_sample_rows():
    result = predict_sql_query(
        "SELECT name, age FROM students WHERE age >= 19 ORDER BY age DESC LIMIT 2;"
    )
    assert result["status"] == "predicted"
    assert result["label"] == RESULT_LABEL
    assert result["columns"] == ["name", "age"]
    assert result["rows"] == [["Divya", 22], ["Priya", 21]]
    assert "Illustrative" in result["message"]


def test_select_star_uses_only_builtin_table_columns():
    result = predict_sql_query("SELECT * FROM departments ORDER BY department_id;")
    assert result["columns"] == ["department_id", "department_name"]
    assert result["rows"] == [
        [101, "AI & DS"],
        [102, "Computer Science"],
        [103, "Information Technology"],
    ]


def test_where_supports_comparisons_and_and_or_precedence():
    result = predict_sql_query(
        "SELECT name FROM students WHERE age >= 20 AND department_id = 101 OR name = 'Ravi' ORDER BY student_id;"
    )
    assert result["rows"] == [["Arun"], ["Ravi"]]


def test_where_supports_each_requested_comparison_operator():
    cases = {
        ("department_id", "= 101"): [["Arun"], ["Kumar"]],
        ("department_id", "!= 101"): [["Priya"], ["Divya"], ["Ravi"]],
        ("age", "< 20"): [["Kumar"], ["Ravi"]],
        ("age", "> 20"): [["Priya"], ["Divya"]],
        ("age", "<= 19"): [["Kumar"], ["Ravi"]],
        ("age", ">= 21"): [["Priya"], ["Divya"]],
    }
    for (column, condition), expected in cases.items():
        query = f"SELECT name FROM students WHERE {column} {condition} ORDER BY student_id;"
        assert predict_sql_query(query)["rows"] == expected


def test_inner_join_works_between_the_two_builtin_tables():
    result = predict_sql_query(
        "SELECT students.name, departments.department_name "
        "FROM students INNER JOIN departments "
        "ON students.department_id = departments.department_id "
        "ORDER BY students.student_id;"
    )
    assert result["status"] == "predicted"
    assert result["columns"] == ["name", "department_name"]
    assert result["rows"] == [
        ["Arun", "AI & DS"],
        ["Priya", "Computer Science"],
        ["Kumar", "AI & DS"],
        ["Divya", "Information Technology"],
        ["Ravi", "Computer Science"],
    ]


def test_aggregates_and_group_by_use_sample_rows():
    result = predict_sql_query(
        "SELECT COUNT(*), SUM(age), AVG(age), MIN(age), MAX(age) FROM students;"
    )
    assert result["rows"] == [[5, 99, 19.8, 17, 22]]

    grouped = predict_sql_query(
        "SELECT department_id, COUNT(*) FROM students GROUP BY department_id ORDER BY department_id;"
    )
    assert grouped["rows"] == [[101, 2], [102, 2], [103, 1]]


def test_distinct_and_string_filter_are_supported():
    result = predict_sql_query(
        "SELECT DISTINCT department_id FROM students WHERE name != 'Ravi' ORDER BY department_id;"
    )
    assert result["rows"] == [[101], [102], [103]]


def test_unsupported_tables_syntax_and_extra_statements_fail_closed():
    for query in (
        "SELECT * FROM payroll;",
        "SELECT age + 1 FROM students;",
        "SELECT * FROM students LEFT JOIN departments ON students.department_id = departments.department_id;",
        "SELECT * FROM students; DELETE FROM students;",
        "SELECT name FROM students WHERE age BETWEEN 18 AND 22;",
        "SELECT name FROM students ORDER BY unknown_column;",
        "SELECT name FROM students LIMIT -1;",
        "SELECT name FROM students WHERE name = 'Arun' OR 1 = 1;",
    ):
        result = predict_sql_query(query)
        assert result["status"] == "unavailable", query
        assert result["rows"] == []
        assert result["message"] == UNAVAILABLE_MESSAGE


def test_ambiguous_unqualified_join_columns_are_not_guessed():
    result = predict_sql_query(
        "SELECT department_id FROM students INNER JOIN departments "
        "ON students.department_id = departments.department_id;"
    )
    assert result["status"] == "unavailable"


def test_query_size_and_empty_queries_are_unavailable():
    assert predict_sql_query("")["status"] == "unavailable"
    assert predict_sql_query(" " * 20_001)["status"] == "unavailable"
