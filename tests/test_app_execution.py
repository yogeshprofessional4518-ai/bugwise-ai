from pathlib import Path

import streamlit as st
from streamlit.testing.v1 import AppTest


APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


def _run_app():
    st.cache_data.clear()
    return AppTest.from_file(str(APP_PATH)).run(timeout=20)


def test_analyze_displays_separate_predicted_output_without_running_code():
    app = _run_app()
    app.text_area(key="code_editor").set_value("print(10 + 20)")
    next(button for button in app.button if button.label == "Analyze Code").click().run(
        timeout=20
    )

    assert not app.exception
    assert any("Predicted Output — Not Executed" in item.value for item in app.markdown)
    assert any(item.value == "30" for item in app.code)
    assert app.session_state["latest_result"]["prediction"]["status"] == "predicted"


def test_unsupported_source_shows_non_execution_message():
    app = _run_app()
    app.text_area(key="code_editor").set_value("for value in [1, 2]:\n    print(value)")
    next(button for button in app.button if button.label == "Analyze Code").click().run(
        timeout=20
    )

    assert not app.exception
    assert any(
        item.value == "Prediction unavailable for this code. The program was not executed."
        for item in app.info
    )


def test_detected_error_is_labeled_as_predicted_not_observed():
    app = _run_app()
    app.text_area(key="code_editor").set_value("print(10 / 0)")
    next(button for button in app.button if button.label == "Analyze Code").click().run(
        timeout=20
    )

    assert not app.exception
    assert any(
        "Predicted error (not observed during execution): ZeroDivisionError: division by zero"
        in item.value
        for item in app.error
    )
    assert not any(item.value == "10" for item in app.code)


def test_execution_controls_and_docker_ui_are_absent():
    app = _run_app()
    labels = [button.label for button in app.button]
    visible_text = "\n".join(
        item.value for item in [*app.markdown, *app.code, *app.warning, *app.info]
    )

    assert "Analyze Code" in labels
    assert "Run Code" not in labels
    assert "Docker" not in visible_text
    assert "Program Output" not in visible_text
    assert "Recheck Docker" not in labels


def test_fix_evidence_and_verification_workflows_remain_available():
    app = _run_app()
    app.text_area(key="code_editor").set_value("total = 7\nprint(totla)")
    next(button for button in app.button if button.label == "Analyze Code").click().run(
        timeout=20
    )

    result = app.session_state["latest_result"]
    assert not app.exception
    assert [tab.label for tab in app.tabs] == [
        "Overview",
        "Diagnosis",
        "Suggested Fix",
        "Fix Evidence",
        "Verification",
    ]
    assert result["fix"]["has_suggestion"]
    assert result["fix"]["diff"]
    assert result["verification"]["compilation"]["passed"]
