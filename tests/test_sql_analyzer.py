from sql_analyzer import (
    analyze_sql,
    explain_sql_findings,
    predict_sql_output,
    suggest_sql_fix,
    verify_sql_fix,
)


def _findings(source):
    return analyze_sql(source)["findings"]


def _types(source):
    return {finding["error_type"] for finding in _findings(source)}


def test_accepts_basic_select_without_claiming_schema_validation():
    result = analyze_sql("SELECT name, age FROM users WHERE active = 1;")
    assert result["status"] == "clean"
    assert result["source_valid"] is None


def test_valid_explicit_column_aliases_are_not_reported_as_missing_commas():
    result = analyze_sql("SELECT name AS student_name, age FROM students;")
    assert not any(
        finding["error_type"] == "SQLPossibleMissingComma"
        for finding in result["findings"]
    )


def test_detects_incomplete_select_projection():
    assert "SQLIncompleteSelect" in _types("SELECT FROM users;")
    assert "SQLIncompleteSelect" in _types("SELECT ;")


def test_select_without_from_is_reported_as_dialect_dependent_review_note():
    finding = next(
        finding for finding in _findings("SELECT user_name;")
        if finding["error_type"] == "SQLPossibleMissingFrom"
    )
    assert finding["category"] == "dialect_dependent"
    assert "some SQL dialects allow SELECT expressions without FROM" in finding["next_action"]


def test_missing_comma_suggestion_is_explicitly_uncertain():
    findings = _findings("SELECT first_name last_name, email FROM users;")
    finding = next(item for item in findings if item["error_type"] == "SQLPossibleMissingComma")
    assert finding["category"] == "possible"
    assert "Possible:" in finding["confidence"]
    fix = suggest_sql_fix("SELECT first_name last_name, email FROM users;", findings)
    assert fix["has_suggestion"]
    assert fix["suggested_code"] == "SELECT first_name, last_name, email FROM users;"
    assert fix["original_code"] == "SELECT first_name last_name, email FROM users;"


def test_requested_two_column_missing_comma_case_is_detected_as_possible():
    source = "SELECT name age FROM students;"
    finding = next(
        item for item in _findings(source)
        if item["error_type"] == "SQLPossibleMissingComma"
    )
    assert finding["category"] == "possible"
    assert "implicit alias" in finding["next_action"]
    fix = suggest_sql_fix(source, _findings(source))
    assert fix["suggested_code"] == "SELECT name, age FROM students;"
    assert fix["original_code"] == source


def test_detects_incomplete_where_forms():
    assert "SQLIncompleteWhere" in _types("SELECT name FROM users WHERE;")
    assert "SQLIncompleteWhere" in _types("SELECT name FROM users WHERE = 1;")
    assert "SQLIncompleteWhere" in _types("SELECT name FROM users WHERE age >;")


def test_detects_join_without_condition_but_not_cross_or_natural_join():
    assert "SQLPossibleMissingJoinCondition" in _types("SELECT * FROM users u JOIN roles r;")
    assert "SQLPossibleMissingJoinCondition" not in _types("SELECT * FROM users CROSS JOIN roles;")
    assert "SQLPossibleMissingJoinCondition" not in _types("SELECT * FROM users NATURAL JOIN roles;")
    assert "SQLPossibleMissingJoinCondition" not in _types(
        "SELECT * FROM users u JOIN roles r ON u.role_id = r.id;"
    )
    assert "SQLIncompleteJoinCondition" in _types("SELECT * FROM users u JOIN roles r ON;")


def test_detects_group_by_spelling_and_possible_aggregate_grouping():
    findings = _findings("SELECT COUNT(*), category FROM items;")
    group_finding = next(item for item in findings if item["error_type"] == "SQLPossibleMissingGroupBy")
    assert group_finding["category"] == "dialect_dependent"
    fix = suggest_sql_fix("SELECT COUNT(*), category FROM items;", findings)
    assert "GROUP BY category" in fix["suggested_code"]
    typo = analyze_sql("SELECT category FROM items GRUP BY category;")
    assert any(item["error_type"] == "SQLKeywordSpelling" for item in typo["findings"])


def test_recognizes_safe_keyword_correction_with_a_diff():
    source = "SELEC name FORM users;"
    findings = _findings(source)
    fix = suggest_sql_fix(source, findings)
    assert fix["suggested_code"] == "SELECT name FROM users;"
    assert fix["diff"]
    assert fix["reason"]


def test_reports_unclosed_quotes_parentheses_and_block_comments():
    assert "SQLUnclosedQuote" in _types("SELECT 'open FROM users;")
    assert "SQLUnmatchedParenthesis" in _types("SELECT (name FROM users;")
    assert "SQLUnclosedComment" in _types("SELECT name FROM users /* comment")


def test_ignores_delimiters_and_keywords_inside_strings_and_comments():
    result = analyze_sql("SELECT 'FROM ) WHERE', name FROM users -- JOIN x\n;")
    assert result["findings"] == []


def test_non_select_and_multi_statement_input_are_not_parsed_as_select():
    result = analyze_sql("DELETE FROM users;")
    assert result["status"] == "unsupported"
    assert "SQLUnsupportedStatement" in _types("DELETE FROM users;")
    assert "SQLUnsupportedStatement" in _types("SELECT a FROM t; SELECT b FROM u;")


def test_arbitrary_input_is_bounded_and_never_executed():
    injection = "SELECT name FROM users; DROP TABLE users;"
    assert analyze_sql(injection)["status"] == "unsupported"
    assert predict_sql_output()["status"] == "unavailable"
    assert verify_sql_fix()["candidate_executed"] is False
    assert explain_sql_findings(_findings("SELECT FROM users;"))
    oversized = analyze_sql("SELECT " + "x " * 30_000)
    assert oversized["status"] == "unsupported"


def test_fixes_never_overwrite_source_and_known_good_query_gets_no_fix():
    source = "SELECT name FROM users WHERE age = 2;"
    result = suggest_sql_fix(source, _findings(source))
    assert result["original_code"] == source
    assert result["suggested_code"] is None
    assert result["has_suggestion"] is False
