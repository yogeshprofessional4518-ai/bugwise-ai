"""BugWise AI — Explain. Fix. Verify."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import streamlit as st

from analyzer import analyze_code
from examples import EXAMPLES, find_example_for_source
from explainer import explain_findings
from fixer import get_fix_options, suggest_fix
from predictor import predict_output
from verifier import verify_fix

LOGGER = logging.getLogger(__name__)
_EXAMPLE_LABELS = {
    "Undefined variable": "NameError · undefined variable",
    "Missing colon": "SyntaxError · missing colon",
    "Division by zero": "ZeroDivisionError · division by zero",
    "Invalid list index": "IndexError · out-of-range list index",
    "Incorrect data type": "TypeError · incompatible operand types",
    "Clean Python code": "Clean Python code",
}

st.set_page_config(
    page_title="BugWise AI — Explain. Fix. Verify.",
    page_icon="🐞",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    :root {
        color-scheme: dark;
        --bw-bg: #0b1220;
        --bw-surface: #111b2d;
        --bw-surface-raised: #152238;
        --bw-border: #26364e;
        --bw-text: #e8eef8;
        --bw-muted: #9aabc2;
        --bw-accent: #67d4c0;
    }
    .stApp { background: var(--bw-bg); color: var(--bw-text); }
    [data-testid="stHeader"] { background: rgba(11, 18, 32, .94); }
    [data-testid="stSidebar"] { background: #0e1727; border-right: 1px solid var(--bw-border); }
    [data-testid="stSidebar"] > div { padding-top: 1.2rem; }
    .block-container { max-width: 1440px; padding-top: 1.35rem; padding-bottom: 2rem; }
    .hero {
        display: flex; align-items: center; gap: 1rem; padding: 1rem 1.3rem;
        margin-bottom: 1.1rem; border: 1px solid var(--bw-border); border-radius: 16px;
        background: linear-gradient(110deg, #14233a 0%, #101a2b 68%, #132432 100%);
    }
    .hero-icon {
        display: grid; place-items: center; width: 3.1rem; height: 3.1rem; flex: 0 0 auto;
        border: 1px solid #35546a; border-radius: 14px; background: #172d3b; font-size: 1.55rem;
    }
    .hero h1 { margin: 0; color: #f5f8ff; font-size: clamp(1.55rem, 3vw, 2.1rem); letter-spacing: -.035em; }
    .hero p { margin: .2rem 0 0; color: #b1c1d6; font-size: .96rem; }
    .eyebrow { margin: 0 0 .15rem; color: var(--bw-accent); font-size: .72rem; font-weight: 700; letter-spacing: .13em; text-transform: uppercase; }
    .section-title { margin: .25rem 0 .15rem; color: #f1f5fc; font-size: 1.06rem; font-weight: 650; }
    .section-hint { margin: 0 0 .8rem; color: var(--bw-muted); font-size: .84rem; }
    .surface {
        padding: 1rem 1.05rem; border: 1px solid var(--bw-border); border-radius: 12px;
        background: var(--bw-surface); margin: .45rem 0 .7rem;
    }
    .muted { color: var(--bw-muted); }
    div[data-testid="stMetric"] {
        background: var(--bw-surface); border: 1px solid var(--bw-border);
        border-radius: 11px; padding: .8rem .95rem;
    }
    div[data-testid="stMetricLabel"] { color: #aebed2; }
    div[data-testid="stMetricValue"] { color: #f1f6ff; }
    div[data-testid="stTabs"] button { font-weight: 600; }
    div[data-testid="stCodeBlock"] { border: 1px solid var(--bw-border); border-radius: 10px; }
    div[data-testid="stTextArea"] textarea {
        background: #0d1727; border: 1px solid #30415b; border-radius: 10px;
        color: #e4edf9; font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
        font-size: .9rem; line-height: 1.55;
    }
    .stButton > button, .stDownloadButton > button {
        min-height: 2.55rem; border-radius: 9px; font-weight: 600;
    }
    [data-testid="stAlert"] { border-radius: 10px; }
    @media (max-width: 700px) {
        .block-container { padding: 1rem .8rem 1.5rem; }
        .hero { padding: .85rem; gap: .7rem; }
        .hero-icon { width: 2.7rem; height: 2.7rem; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def _initialize_state() -> None:
    defaults: dict[str, Any] = {
        "code_editor": "",
        "history": [],
        "session_analyses": 0,
        "session_findings": 0,
        "session_issue_counts": {},
        "latest_result": None,
        "selected_example": None,
        "reveal_correction": False,
        "example_choice": next(iter(EXAMPLES)),
        "practice_hint_shown": False,
        "practice_answer_shown": False,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _load_example() -> None:
    sample = EXAMPLES[st.session_state.example_choice]
    st.session_state.code_editor = sample["original_code"]
    st.session_state.selected_example = sample["id"]
    st.session_state.latest_result = None
    st.session_state.reveal_correction = False
    st.session_state.practice_hint_shown = False
    st.session_state.practice_answer_shown = False


def _clear_editor() -> None:
    st.session_state.code_editor = ""
    st.session_state.latest_result = None
    st.session_state.selected_example = None
    st.session_state.reveal_correction = False
    st.session_state.practice_hint_shown = False
    st.session_state.practice_answer_shown = False


def _analyze(source: str) -> dict[str, Any]:
    analysis = analyze_code(source)
    prediction = predict_output(source)
    matching_example = find_example_for_source(source)
    fix = suggest_fix(
        source,
        analysis["findings"],
        educational_example=matching_example,
    )
    fix_options = get_fix_options(analysis["findings"])
    trusted_tests = (
        matching_example["trusted_tests"]
        if matching_example and fix["suggested_code"] == matching_example["corrected_code"]
        else []
    )
    code_to_validate = fix["suggested_code"] or fix["attempted_code"] or source
    verification = verify_fix(
        code_to_validate,
        trusted_tests if fix["suggested_code"] else [],
    )
    explanations = explain_findings(
        analysis["findings"],
        corrected_example=fix["suggested_code"],
    )
    return {
        "source": source,
        "analysis": analysis,
        "prediction": prediction,
        "fix": fix,
        "fix_options": fix_options,
        "verification": verification,
        "explanations": explanations,
        "matching_example": matching_example,
        "created_at": datetime.now().strftime("%H:%M:%S"),
    }


def _record_analysis(source: str, result: dict[str, Any], learning_mode: bool) -> None:
    st.session_state.latest_result = result
    st.session_state.reveal_correction = not learning_mode
    st.session_state.practice_hint_shown = False
    st.session_state.practice_answer_shown = False
    analysis = result["analysis"]
    st.session_state.history.append(
        {
            "created_at": result["created_at"],
            "status": analysis["status"],
            "preview": source.splitlines()[0][:48],
            "finding_count": len(analysis["findings"]),
            "finding_types": [finding["error_type"] for finding in analysis["findings"]],
        }
    )
    st.session_state.session_analyses += 1
    st.session_state.session_findings += len(analysis["findings"])
    for finding in analysis["findings"]:
        error_type = finding["error_type"]
        counts = st.session_state.session_issue_counts
        st.session_state.session_issue_counts = {
            **counts,
            error_type: counts.get(error_type, 0) + 1,
        }


def _finding_label(finding: dict[str, Any]) -> str:
    line = f" · line {finding['line_number']}" if finding.get("line_number") else ""
    return f"{finding['error_type']}{line}"


def _finding_kind(finding: dict[str, Any]) -> str:
    if finding["error_type"] in {"SyntaxError", "IndentationError"}:
        return "Confirmed syntax error"
    if finding["category"] == "potential_runtime":
        return "Potential runtime risk"
    if finding["category"] == "environment_dependent":
        return "Environment-dependent warning"
    return "Static-analysis warning"


def _practice_for(result: dict[str, Any]) -> tuple[str, str, str]:
    findings = result["analysis"]["findings"]
    kind = findings[0]["error_type"] if findings else "clean"
    prompts = {
        "SyntaxError": (
            "What punctuation does a Python `if` block header require?",
            "Look at the end of the line that introduces the block.",
            "A colon (`:`) ends an `if` block header.",
        ),
        "IndentationError": (
            "How does Python know which statements belong to a function body?",
            "Compare the leading whitespace on the function line and its body.",
            "The body is indented beneath the function definition, consistently (commonly four spaces).",
        ),
        "NameError": (
            "What should you check first when Python reports an unknown name?",
            "Compare the spelling at the use site with its assignment or import.",
            "Check that the name is defined or imported in the relevant scope and spelled consistently.",
        ),
        "IndexError": (
            "If a list has three items, what is its last positive index?",
            "Remember that the first item uses index zero.",
            "The last positive index is 2: indexes start at 0 and end at length minus 1.",
        ),
        "ZeroDivisionError": (
            "What should a program check before using a value as a divisor?",
            "Consider the boundary value zero.",
            "Check whether the divisor is zero and handle that case before dividing.",
        ),
        "TypeError": (
            "How can you combine a number and text for display?",
            "Consider converting the number or using formatted-string syntax.",
            "Convert the number to text or use an f-string such as `f'Age: {age}'`.",
        ),
        "clean": (
            "Does a clean static analysis prove code is free of runtime errors?",
            "Static analysis does not execute the program.",
            "No. It only means these static checks found no issue; behavior still needs appropriate testing.",
        ),
    }
    return prompts.get(
        kind,
        (
            "What is one way to check the assumption behind this finding?",
            "Use the reported line and the next action as a starting point.",
            "Check the relevant inputs and boundary cases with a test suited to the intended behavior.",
        ),
    )


def _show_diagnosis(result: dict[str, Any], learning_mode: bool) -> None:
    analysis = result["analysis"]
    if not analysis["findings"]:
        st.success("No issue was identified by the available static checks.")
    for finding in analysis["findings"]:
        with st.container():
            st.markdown(f"**{_finding_label(finding)}** · `{_finding_kind(finding)}`")
            st.write(finding["message"])
            st.caption(f"{finding['category']} · {finding['confidence']}")
            st.markdown(f"**Next action:** {finding['next_action']}")
            if finding.get("source_line"):
                st.code(finding["source_line"], language="python")
            st.divider()

    matching_example = result["matching_example"]
    if not analysis["findings"] and matching_example:
        st.info(
            "Sample note: "
            + matching_example["expected_diagnosis"]
            + " This expected diagnosis is fixture metadata, not a general static-analysis result."
        )

    if learning_mode and (result["explanations"] or matching_example):
        st.markdown("#### Learn from this result")
        if result["explanations"]:
            seen_concepts: set[str] = set()
            for lesson in result["explanations"]:
                concept = lesson["concept"]
                if concept in seen_concepts:
                    continue
                seen_concepts.add(concept)
                with st.expander(concept, expanded=True):
                    st.write(f"**In simple terms:** {lesson['what_it_means']}")
                    st.write(f"**Why it may happen:** {lesson['why_it_likely_happened']}")
                    st.write(f"**How to approach it:** {lesson['how_to_fix']}")
                    st.write(f"**Prevention tip:** {lesson['prevention_tip']}")
                    st.caption(lesson["basis"])
        elif matching_example:
            st.write(matching_example.get("python_concept", "Review the Python concept in this sample."))
            if matching_example.get("prevention_tip"):
                st.caption(f"Prevention tip: {matching_example['prevention_tip']}")

        question, hint, answer = _practice_for(result)
        st.markdown("#### Quick practice")
        st.write(question)
        if st.button("Show Hint", key="show_practice_hint"):
            st.session_state.practice_hint_shown = True
            st.session_state.practice_answer_shown = False
        if st.session_state.practice_hint_shown:
            st.info(hint)
            if st.button("Reveal answer", key="reveal_practice_answer"):
                st.session_state.practice_answer_shown = True
        if st.session_state.practice_answer_shown:
            st.success(answer)


def _show_fix(result: dict[str, Any], learning_mode: bool) -> None:
    fix = result["fix"]
    available = fix["has_suggestion"]
    revealed = not learning_mode or st.session_state.reveal_correction
    if not available:
        st.info("No defensible automatic correction is available for this input.")
        if fix["compilation_passed"] is False:
            st.warning("A proposed edit was rejected because it did not pass syntax validation.")
    elif learning_mode and not revealed:
        st.info("The suggested code is hidden while Learning Mode is on.")
        if st.button("Reveal suggested correction", key="reveal_suggested_correction"):
            st.session_state.reveal_correction = True
    else:
        st.caption(f"{fix['reason']} {fix['confidence']}")
        original, corrected = st.columns(2)
        with original:
            st.markdown("**Original code**")
            st.code(fix["original_code"], language="python")
        with corrected:
            st.markdown("**Suggested code**")
            st.code(fix["suggested_code"], language="python")
            st.download_button(
                "Download Fixed Code",
                data=fix["suggested_code"],
                file_name="bugwise_fixed.py",
                mime="text/x-python",
                key="download_fixed_code",
            )
        st.caption("Use the code block's built-in copy control to copy the suggested code.")

    if result["fix_options"]:
        st.markdown("#### Alternative fix options")
        st.caption(
            "These are syntax-checked alternatives, not automatic edits. Choose based on the "
            "behavior you intend."
        )
        for option in result["fix_options"]:
            with st.expander(option["label"]):
                st.write(option["when_to_use"])
                st.code(option["code"], language="python")


def _show_evidence(result: dict[str, Any], learning_mode: bool) -> None:
    analysis = result["analysis"]
    fix = result["fix"]
    matching_example = result["matching_example"]
    if analysis["findings"]:
        st.markdown("**Finding evidence**")
        for finding in analysis["findings"]:
            st.write(
                f"- **{_finding_label(finding)}:** {finding['message']} "
                f"({_finding_kind(finding)})"
            )
    elif matching_example:
        st.write(f"**Sample expectation:** {matching_example['expected_diagnosis']}")
    else:
        st.write("No static finding was produced for the original source.")

    correction_hidden = learning_mode and fix["has_suggestion"] and not st.session_state.reveal_correction
    if correction_hidden:
        st.info("The line-level correction is hidden while Learning Mode is on.")
        if st.button("Reveal correction to view diff", key="reveal_correction_for_diff"):
            st.session_state.reveal_correction = True
    elif fix["diff"]:
        st.markdown("**Changed lines**")
        st.code(fix["diff"], language="diff")
    elif fix["has_suggestion"]:
        st.info("The suggested correction is available; no line-level diff was produced.")
    else:
        st.caption("No source changes were suggested.")
    if fix["attempted_code"] and not fix["has_suggestion"] and fix["compilation_passed"] is False:
        st.warning("The attempted change failed compilation and is not offered as a correction.")


def _show_verification(result: dict[str, Any]) -> None:
    verification = result["verification"]
    compilation = verification["compilation"]
    if compilation["passed"]:
        st.success("Syntax validation passed.")
        st.caption("The candidate was compiled and parsed; this does not establish correct behavior.")
    else:
        st.error("Syntax validation failed or no valid candidate was available.")
        st.caption(compilation["detail"])

    if verification["trusted_tests"]:
        st.markdown("**Trusted reference checks**")
        st.caption(
            "These allowlisted operations ran on educational fixture inputs, not on submitted "
            "or suggested code. They are not behavioral verification of the candidate."
        )
        for test in verification["trusted_tests"]:
            status = "Success" if test["passed"] else "Warning"
            st.write(
                f"- **{status}: {test['name']}** — expected `{test['expected']}`, "
                f"reference result `{test['actual']}`."
            )
    else:
        st.info("No relevant trusted fixture check was run.")
    st.caption(verification["warning"])


def _show_overview(result: dict[str, Any]) -> None:
    analysis = result["analysis"]
    findings = analysis["findings"]
    confirmed = sum(
        finding["error_type"] in {"SyntaxError", "IndentationError"}
        for finding in findings
    )
    potential = sum(finding["category"] == "potential_runtime" for finding in findings)
    static_warnings = len(findings) - confirmed - potential
    first_issue = findings[0]["error_type"] if findings else "None"
    metrics = st.columns(4)
    metrics[0].metric("Findings", len(findings))
    metrics[1].metric("Confirmed syntax errors", confirmed)
    metrics[2].metric("Potential runtime risks", potential)
    metrics[3].metric("First category", first_issue)

    st.markdown("**Analysis summary**")
    if analysis["status"] == "invalid":
        st.error(analysis["summary"])
    elif findings:
        st.warning(analysis["summary"])
    else:
        st.success(analysis["summary"])
    st.caption(
        f"Source parse: {'valid' if analysis['source_valid'] else 'not valid / not provided'} · "
        f"Other static or environment warnings: {static_warnings}"
    )
    if findings:
        st.caption(
            "A potential runtime risk is inferred from static evidence; it is not a claim that "
            "the submitted program was run or that the failure definitely occurs."
        )


def _show_prediction(prediction: dict[str, str]) -> None:
    st.markdown("#### Predicted Output — Not Executed")
    st.caption("Rule-based prediction for supported Python syntax; submitted code was not run.")
    if prediction["status"] == "predicted":
        st.code(prediction["output"] or "(no printed output)", language="text")
    elif prediction["status"] == "error":
        st.error(f"Predicted error (not observed during execution): {prediction['message']}")
    else:
        st.info(prediction["message"])


_initialize_state()

st.markdown(
    """
    <div class="hero">
      <div class="hero-icon">🐞</div>
      <div>
        <p class="eyebrow">Python debugging workspace</p>
        <h1>BugWise AI</h1>
        <p>Understand the Bug. Fix the Code. Verify the Solution.</p>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.markdown('<p class="eyebrow">Workspace</p>', unsafe_allow_html=True)
    learning_mode = st.toggle("Learning Mode", value=False, help="Show beginner explanations and a guided practice question.")
    st.markdown("#### Sample cases")
    st.selectbox(
        "Choose a Python example",
        list(EXAMPLES),
        key="example_choice",
        format_func=lambda name: _EXAMPLE_LABELS.get(name, name),
    )
    selected_sample = EXAMPLES[st.session_state.example_choice]
    st.caption(f"Expected diagnosis: {selected_sample['expected_diagnosis']}")
    st.caption(f"Detection: {selected_sample['detection_basis']}")
    st.button("Load Example", use_container_width=True, on_click=_load_example)
    st.divider()
    st.markdown("#### Session activity")
    if st.button("Clear history", use_container_width=True):
        st.session_state.history = []
    if not st.session_state.history:
        if st.session_state.session_analyses:
            st.caption("Recent history was cleared; current-session metrics are retained.")
        else:
            st.caption("No analyses recorded in this session yet.")
    else:
        for item in reversed(st.session_state.history[-5:]):
            st.caption(
                f"{item['created_at']} · {item['status']} · "
                f"{item['finding_count']} finding(s) · {item['preview']}"
            )

editor_col, result_col = st.columns([1.05, 1])
with editor_col:
    st.markdown('<p class="eyebrow">01 / Source</p>', unsafe_allow_html=True)
    st.markdown('<p class="section-title">Python editor</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="section-hint">Paste or write Python. Analysis and prediction use static, restricted checks; submitted code is never executed.</p>',
        unsafe_allow_html=True,
    )
    source = st.text_area(
        "Python code",
        key="code_editor",
        height=410,
        label_visibility="collapsed",
        placeholder="def calculate_total(items):\n    return sum(items)\n",
    )
    analyze_col, reset_col = st.columns([1.2, 0.9])
    with analyze_col:
        analyze_clicked = st.button(
            "Analyze Code",
            type="primary",
            use_container_width=True,
            help="Parse and statically inspect the code without running it.",
        )
    with reset_col:
        st.button("Clear Code", use_container_width=True, on_click=_clear_editor)
    if st.session_state.selected_example:
        example = next(
            item for item in EXAMPLES.values()
            if item["id"] == st.session_state.selected_example
        )
        st.caption(f"Loaded sample · expected: {example['expected_diagnosis']}")

    if analyze_clicked:
        if not source.strip():
            st.warning("Enter or load Python code before analyzing.")
        else:
            st.session_state.latest_result = None
            try:
                with st.spinner("Parsing and checking the code…"):
                    result = _analyze(source)
            except Exception as error:
                LOGGER.exception("BugWise analysis failed")
                st.error(f"Analysis failed ({type(error).__name__}); the submitted code was not executed.")
                with st.expander("Technical details"):
                    st.code(str(error))
            else:
                _record_analysis(source, result, learning_mode)

with result_col:
    st.markdown('<p class="eyebrow">02 / Results</p>', unsafe_allow_html=True)
    st.markdown('<p class="section-title">Analysis workspace</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="section-hint">Evidence-led diagnosis, optional fixes, and honest verification.</p>',
        unsafe_allow_html=True,
    )
    result = st.session_state.latest_result
    if result is None:
        st.markdown(
            '<div class="surface muted">Analyze code to see its overview, diagnosis, suggested fix, '
            'evidence, and verification details.</div>',
            unsafe_allow_html=True,
        )
    else:
        _show_prediction(result["prediction"])
        tabs = st.tabs(["Overview", "Diagnosis", "Suggested Fix", "Fix Evidence", "Verification"])
        with tabs[0]:
            _show_overview(result)
        with tabs[1]:
            _show_diagnosis(result, learning_mode)
        with tabs[2]:
            _show_fix(result, learning_mode)
        with tabs[3]:
            _show_evidence(result, learning_mode)
        with tabs[4]:
            _show_verification(result)

st.divider()
st.markdown('<p class="eyebrow">Session dashboard</p>', unsafe_allow_html=True)
st.markdown('<p class="section-title">Your debugging activity</p>', unsafe_allow_html=True)
history = st.session_state.history
issue_counts = st.session_state.session_issue_counts
dashboard = st.columns(3)
dashboard[0].metric("Analyses this session", st.session_state.session_analyses)
dashboard[1].metric("Findings this session", st.session_state.session_findings)
dashboard[2].metric("Issue types encountered", len(issue_counts))
if issue_counts:
    st.caption("Issue types: " + " · ".join(
        f"{name} ({count})" for name, count in sorted(issue_counts.items())
    ))
if history:
    st.dataframe(
        [
            {
                "Time": item["created_at"],
                "Result": item["status"],
                "Findings": item["finding_count"],
                "Code preview": item["preview"],
            }
            for item in reversed(history[-10:])
        ],
        hide_index=True,
    )
else:
    st.caption(
        "No recent history to display. Metrics reflect this browser session only; "
        "nothing is stored permanently."
    )

st.caption(
    "Submitted code is never executed. Predicted output is limited to supported AST patterns; "
    "verification checks syntax and trusted fixtures, not arbitrary program behavior."
)
