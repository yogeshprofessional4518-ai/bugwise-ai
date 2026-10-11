from pathlib import Path

import streamlit as st
from streamlit.testing.v1 import AppTest


APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


def _run_app():
    st.cache_data.clear()
    return AppTest.from_file(str(APP_PATH)).run(timeout=20)


def _select_java(app):
    app.selectbox(key="language_choice").set_value("Java").run(timeout=20)
    return app


def test_language_selector_defaults_to_python_and_offers_java_samples():
    app = _run_app()
    assert app.selectbox(key="language_choice").value == "Python"

    _select_java(app)
    assert not app.exception
    assert app.selectbox(key="language_choice").value == "Java"
    assert "Hello Java" in app.selectbox(key="example_choice").options


def test_java_sample_integrates_analysis_fix_evidence_and_verification():
    app = _select_java(_run_app())
    app.selectbox(key="example_choice").set_value("Missing semicolon")
    next(button for button in app.button if button.label == "Load Example").click().run(
        timeout=20
    )
    next(button for button in app.button if button.label == "Analyze Code").click().run(
        timeout=20
    )

    assert not app.exception
    result = app.session_state["latest_result"]
    assert result["language"] == "Java"
    assert result["fix"]["has_suggestion"]
    assert ");" in result["fix"]["suggested_code"]
    assert result["fix"]["diff"]
    assert result["verification"]["status"] == "unsupported"
    assert [tab.label for tab in app.tabs] == [
        "Overview",
        "Diagnosis",
        "Suggested Fix",
        "Fix Evidence",
        "Verification",
    ]
    assert any("Verification is unsupported for Java" in item.value for item in app.info)


def test_java_literal_output_is_predicted_and_learning_mode_remains_available():
    app = _select_java(_run_app())
    app.toggle[0].set_value(True).run(timeout=20)
    app.selectbox(key="example_choice").set_value("Hello Java")
    next(button for button in app.button if button.label == "Load Example").click().run(
        timeout=20
    )
    next(button for button in app.button if button.label == "Analyze Code").click().run(
        timeout=20
    )

    assert not app.exception
    assert app.session_state["latest_result"]["prediction"]["status"] == "predicted"
    assert any(item.value == "Hello Java" for item in app.code)
    assert any("Predicted Output — Not Executed" in item.value for item in app.markdown)
    assert any("Learn from this result" in item.value for item in app.markdown)


def test_requested_java_sum_is_rendered_in_predicted_output_panel():
    app = _select_java(_run_app())
    app.text_area(key="code_editor").set_value(
        'int a = 10; int b = 20; int sum = a + b; System.out.println("Sum: " + sum);'
    )
    next(button for button in app.button if button.label == "Analyze Code").click().run(
        timeout=20
    )

    assert not app.exception
    assert app.session_state["latest_result"]["prediction"]["output"] == "Sum: 30\n"
    assert any("Predicted Output — Not Executed" in item.value for item in app.markdown)
    assert any(item.value == "Sum: 30" for item in app.code)