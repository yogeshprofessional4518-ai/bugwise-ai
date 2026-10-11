from pathlib import Path

import streamlit as st
from streamlit.testing.v1 import AppTest


APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


def _run_app():
    st.cache_data.clear()
    return AppTest.from_file(str(APP_PATH)).run(timeout=20)


def _select_sql(app):
    app.selectbox(key="language_choice").set_value("SQL").run(timeout=20)
    return app


def test_language_selector_keeps_python_default_and_offers_sql():
    app = _run_app()
    assert app.selectbox(key="language_choice").value == "Python"
    _select_sql(app)
    assert not app.exception
    assert app.selectbox(key="language_choice").value == "SQL"
    assert "Basic SELECT" in app.selectbox(key="example_choice").options


def test_sql_example_loads_and_static_analysis_runs_without_execution():
    app = _select_sql(_run_app())
    app.selectbox(key="example_choice").set_value("Misspelled keyword")
    next(button for button in app.button if button.label == "Load Example").click().run(
        timeout=20
    )
    next(button for button in app.button if button.label == "Analyze Code").click().run(
        timeout=20
    )

    assert not app.exception
    result = app.session_state["latest_result"]
    assert result["language"] == "SQL"
    assert result["analysis"]["findings"][0]["error_type"] == "SQLKeywordSpelling"
    assert result["fix"]["suggested_code"] == "SELECT name FROM users;"
    assert result["fix"]["diff"]
    assert result["verification"]["status"] == "unsupported"
    assert result["prediction"]["status"] == "unavailable"
    assert any("SQL result prediction is unavailable" in item.value for item in app.info)
    assert any("Verification is unsupported for SQL" in item.value for item in app.info)
    assert [tab.label for tab in app.tabs] == [
        "Overview",
        "Diagnosis",
        "Suggested Fix",
        "Fix Evidence",
        "Verification",
    ]


def test_sql_learning_mode_keeps_sample_lesson_and_hint_flow():
    app = _select_sql(_run_app())
    app.toggle[0].set_value(True).run(timeout=20)
    app.selectbox(key="example_choice").set_value("Incomplete WHERE")
    next(button for button in app.button if button.label == "Load Example").click().run(
        timeout=20
    )
    next(button for button in app.button if button.label == "Analyze Code").click().run(
        timeout=20
    )

    assert not app.exception
    assert any("Learn from this result" in item.value for item in app.markdown)
    assert any("SQL query structure" in item.label for item in app.expander)
    assert any(button.label == "Show Hint" for button in app.button)


def test_sql_ui_does_not_expose_execution_controls():
    app = _select_sql(_run_app())
    labels = [button.label for button in app.button]
    assert "Analyze Code" in labels
    assert "Run Code" not in labels
    assert all("execute" not in item.value.lower() for item in app.warning)
    assert any("Built-in sample data" in item.value for item in app.markdown)
    assert any(item.label == "students" for item in app.expander)
    assert any(item.label == "departments" for item in app.expander)
    assert len(app.dataframe) == 2
    assert app.dataframe[0].value["name"].tolist() == ["Arun", "Priya", "Kumar", "Divya", "Ravi"]
    assert app.dataframe[1].value["department_name"].tolist() == [
        "AI & DS",
        "Computer Science",
        "Information Technology",
    ]


def test_sql_query_computes_and_renders_only_builtin_sample_results():
    app = _select_sql(_run_app())
    app.text_area(key="code_editor").set_value(
        "SELECT name, age FROM students WHERE age >= 20 ORDER BY age DESC LIMIT 2;"
    )
    next(button for button in app.button if button.label == "Analyze Code").click().run(
        timeout=20
    )

    result = app.session_state["latest_result"]["prediction"]
    assert not app.exception
    assert result["rows"] == [["Divya", 22], ["Priya", 21]]
    assert any(
        "Predicted Result — Computed from Built-in Sample Data (Not Executed Against a Database)"
        in item.value
        for item in app.markdown
    )
    assert any("may differ from your actual database" in item.value for item in app.caption)
    assert len(app.dataframe) == 4
    assert app.dataframe[2].value.to_dict("records") == [
        {"name": "Divya", "age": 22},
        {"name": "Priya", "age": 21},
    ]


def test_unsupported_statement_is_not_shown_as_clean_sql():
    app = _select_sql(_run_app())
    app.text_area(key="code_editor").set_value("DELETE FROM users;")
    next(button for button in app.button if button.label == "Analyze Code").click().run(
        timeout=20
    )

    assert not app.exception
    assert app.session_state["latest_result"]["analysis"]["status"] == "unsupported"
    assert any("Only SELECT queries receive SQL analysis" in item.value for item in app.info)
    assert not any("No issue was identified" in item.value for item in app.success)
