"""Small, fixed SQL sample dataset used only by the restricted predictor and UI."""

STUDENTS_COLUMNS = ("student_id", "name", "age", "department_id")
STUDENTS_ROWS = (
    (1, "Arun", 20, 101),
    (2, "Priya", 21, 102),
    (3, "Kumar", 19, 101),
    (4, "Divya", 22, 103),
    (5, "Ravi", 17, 102),
)

DEPARTMENTS_COLUMNS = ("department_id", "department_name")
DEPARTMENTS_ROWS = (
    (101, "AI & DS"),
    (102, "Computer Science"),
    (103, "Information Technology"),
)

SAMPLE_TABLES = {
    "students": {"columns": STUDENTS_COLUMNS, "rows": STUDENTS_ROWS},
    "departments": {"columns": DEPARTMENTS_COLUMNS, "rows": DEPARTMENTS_ROWS},
}


def sample_rows_as_dicts(table_name: str) -> list[dict[str, object]]:
    """Return display-friendly copies of a built-in sample table."""
    table = SAMPLE_TABLES[table_name]
    return [dict(zip(table["columns"], row)) for row in table["rows"]]