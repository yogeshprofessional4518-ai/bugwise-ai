"""SQL examples for static query-structure analysis; no database fixtures are run."""

SQL_EXAMPLES = {
    "Basic SELECT": {
        "id": "sql-basic-select",
        "original_code": "SELECT name, age FROM users WHERE active = 1;",
        "expected_diagnosis": "No supported SQL structure issue was identified.",
        "detection_basis": "Static checks found no supported issue; schema and dialect were not validated.",
        "corrected_code": None,
        "trusted_tests": [],
        "concept": "SELECT, FROM, and WHERE clauses",
        "prevention_tip": "Check query structure against the target database's schema and dialect.",
    },
    "Misspelled keyword": {
        "id": "sql-keyword-typo",
        "original_code": "SELEC name FROM users;",
        "expected_diagnosis": "SELEC appears to be a misspelling of SELECT.",
        "detection_basis": "A close, known keyword spelling appears in the statement-start position.",
        "corrected_code": "SELECT name FROM users;",
        "trusted_tests": [],
        "concept": "SQL keywords",
        "prevention_tip": "Review clause keywords for spelling and order.",
    },
    "Incomplete WHERE": {
        "id": "sql-incomplete-where",
        "original_code": "SELECT name FROM users WHERE = 1;",
        "expected_diagnosis": "WHERE has no recognizable left-hand expression.",
        "detection_basis": "The WHERE clause begins with a comparison operator.",
        "corrected_code": None,
        "trusted_tests": [],
        "concept": "SQL filtering conditions",
        "prevention_tip": "Write the condition's column or expression before its operator.",
    },
    "JOIN without condition": {
        "id": "sql-join-condition",
        "original_code": "SELECT users.name FROM users JOIN roles;",
        "expected_diagnosis": "This JOIN may need an ON or USING condition.",
        "detection_basis": "A common JOIN form is not followed by ON or USING; this is a dialect-aware review note.",
        "corrected_code": None,
        "trusted_tests": [],
        "concept": "SQL join conditions",
        "prevention_tip": "State how rows from each joined table are related unless using an intentional cross or natural join.",
    },
    "Aggregate grouping review": {
        "id": "sql-grouping-review",
        "original_code": "SELECT COUNT(*), category FROM items;",
        "expected_diagnosis": "category may need to appear in a GROUP BY clause.",
        "detection_basis": "Standard SQL groups non-aggregate selected columns; database dialect behavior can vary.",
        "corrected_code": "SELECT COUNT(*), category FROM items GROUP BY category;",
        "trusted_tests": [],
        "concept": "SQL aggregation and grouping",
        "prevention_tip": "Group non-aggregate selected columns when combining them with aggregate expressions.",
    },
}


def find_sql_example_for_source(source: str) -> dict | None:
    """Return an exact SQL fixture match, if one exists."""
    return next(
        (example for example in SQL_EXAMPLES.values() if source == example["original_code"]),
        None,
    )
