"""BugWise AI — Explain. Fix. Verify."""

from __future__ import annotations

import streamlit as st

from analyzer import analyze_code
from examples import EXAMPLES, find_example_for_source
from explainer import explain_findings
from fixer import get_fix_options, suggest_fix
from verifier import verify_fix

st.set_page_config(page_title="BugWise AI", page_icon="🐞", layout="wide")

st.markdown(
    """
    <style>
    .stApp { background: #0b1020; color: #e6edf7; }
    [data-testid="stSidebar"] { background: #10182a; }
    .hero { padding: 1.1rem 1.4rem; border: 1px solid #25324a; border-radius: 16px;
            background: linear-gradient(115deg, #121d33, #111827); margin-bottom: 1rem; }
    .hero h1 { margin: 0; color: #f4f7ff; }
    .hero p { color: #aab8ce; margin: .35rem 0 0; }
    .panel { padding: 1rem; border: 1px solid #25324a; border-radius: 12px;
             background: #111827; margin: .55rem 0; }
    .muted { color: #aab8ce; }
    </style>
    """,
    unsafe_allow_html=True,
)


def _load_example() -> None:
    sample = EXAMPLES[st.session_state.example_choice]
    st.session_state.code_editor = sample["original_code"]
    st.session_state.selected_example = sample["id"]
    st.session_state.latest_result = None
    st.session_state.reveal_correction = False


def _clear_editor() -> None:
    st.session_state.code_editor = ""
    st.session_state.latest_result = None
    st.session_state.reveal_correction = False


if "code_editor" not in st.session_state:
    st.session_state.code_editor = ""
if "history" not in st.session_state:
    st.session_state.history = []
if "latest_result" not in st.session_state:
    st.session_state.latest_result = None
if "selected_example" not in st.session_state:
    st.session_state.selected_example = None
if "reveal_correction" not in st.session_state:
    st.session_state.reveal_correction = False
if "example_choice" not in st.session_state:
    st.session_state.example_choice = next(iter(EXAMPLES))

st.markdown(
    '<div class="hero"><h1>🐞 BugWise AI</h1><p>Understand the bug. Fix the code. Verify the solution.</p></div>',
    unsafe_allow_html=True,
)

with st.sidebar:
    st.subheader("Learning tools")
    learning_mode = st.toggle("Learning Mode", value=False)
    selected = st.selectbox(
        "Educational sample cases",
        list(EXAMPLES),
        key="example_choice",
        on_change=_load_example,
    )
    sample = EXAMPLES[selected]
    st.caption(f"Expected diagnosis: {sample['expected_diagnosis']}")
    st.divider()
    st.subheader("Session history")
    if st.button("Clear history", use_container_width=True):
        st.session_state.history = []
    if not st.session_state.history:
        st.caption("No analyses in this session yet.")
    else:
        for item in st.session_state.history[-6:][::-1]:
            st.caption(f"{item['status']} · {item['preview']}")

left, right = st.columns([1.2, 1])
with left:
    st.subheader("Your Python code")
    source = st.text_area(
        "Code editor",
        key="code_editor",
        height=330,
        label_visibility="collapsed",
        placeholder="Paste Python code here…",
    )
    analyze_col, clear_col = st.columns(2)
    with analyze_col:
        analyze_clicked = st.button("Analyze Code", type="primary", use_container_width=True)
    with clear_col:
        st.button("Clear", use_container_width=True, on_click=_clear_editor)

    if learning_mode and source.strip():
        st.info("Hint: Start with the exact line reported by Python. Check names, punctuation, and block indentation.")
        if st.button("Reveal suggested correction"):
            st.session_state.reveal_correction = True

    if analyze_clicked:
        if not source.strip():
            st.warning("Enter or select some Python code before analyzing.")
        else:
            with st.spinner("Parsing and checking the code…"):
                analysis = analyze_code(source)
                matching_example = find_example_for_source(source)
                fix = suggest_fix(
                    source,
                    analysis["findings"],
                    educational_example=matching_example,
                )
                fix_options = get_fix_options(analysis["findings"])
                trusted_tests = (
                    matching_example["trusted_tests"]
                    if matching_example
                    and fix["suggested_code"] == matching_example["corrected_code"]
                    else []
                )
                code_to_validate = (
                    fix["suggested_code"]
                    or fix["attempted_code"]
                    or source
                )
                verification = verify_fix(
                    code_to_validate,
                    trusted_tests if fix["suggested_code"] else [],
                )
                explanations = explain_findings(
                    analysis["findings"],
                    corrected_example=fix["suggested_code"],
                )
                result = {
                    "source": source,
                    "analysis": analysis,
                    "fix": fix,
                    "fix_options": fix_options,
                    "verification": verification,
                    "explanations": explanations,
                    "matching_example": matching_example,
                }
                st.session_state.latest_result = result
                st.session_state.reveal_correction = not learning_mode
                st.session_state.history.append(
                    {
                        "status": analysis["status"],
                        "preview": source.splitlines()[0][:55],
                        "finding_count": len(analysis["findings"]),
                    }
                )

with right:
    st.subheader("Analysis")
    result = st.session_state.latest_result
    if result is None:
        st.markdown(
            '<div class="panel muted">Your diagnosis, explanation, correction, diff, and verification results will appear here.</div>',
            unsafe_allow_html=True,
        )
    else:
        analysis = result["analysis"]
        if analysis["status"] == "invalid":
            st.error(analysis["summary"])
        elif analysis["findings"]:
            st.warning(analysis["summary"])
        else:
            st.success(analysis["summary"])

        st.markdown("#### Diagnosis")
        if not analysis["findings"]:
            st.write("No issue was identified by the available static checks.")
        for finding in analysis["findings"]:
            line = f" · line {finding['line_number']}" if finding["line_number"] else ""
            st.markdown(
                f"**{finding['error_type']}**{line} — {finding['message']}  \n"
                f"_{finding['category']} · {finding['confidence']}_  \n"
                f"Next: {finding['next_action']}"
            )
        matching_example = result["matching_example"]
        if not analysis["findings"] and matching_example:
            st.info(
                "Educational sample diagnosis (exact sample match): "
                + matching_example["expected_diagnosis"]
                + " This logical issue is not inferred for arbitrary code."
            )
            if matching_example.get("python_concept"):
                with st.expander("Learning concept", expanded=True):
                    st.write(f"**Concept:** {matching_example['python_concept']}")
                    st.write(f"**Tip:** {matching_example['prevention_tip']}")

        fix_data = result["fix"]
        st.markdown("#### Fix Evidence")
        if analysis["findings"]:
            st.write(
                "**Original issue:** "
                + "; ".join(
                    f"{finding['error_type']}"
                    + (
                        f" at line {finding['line_number']}"
                        if finding["line_number"]
                        else ""
                    )
                    + f" — {finding['message']}"
                    for finding in analysis["findings"]
                )
            )
        elif matching_example:
            st.write(f"**Original issue:** {matching_example['expected_diagnosis']}")
        else:
            st.write("**Original issue:** No static issue was identified.")

        if fix_data["has_suggestion"] and (
            not learning_mode or st.session_state.reveal_correction
        ):
            st.write("**Exact change:**")
            if fix_data["diff"]:
                st.code(fix_data["diff"], language="diff")
        elif fix_data["compilation_passed"] is False and fix_data["diff"]:
            st.write("**Exact change:** Rejected suggestion (not offered as a correction).")
            st.code(fix_data["diff"], language="diff")
        elif learning_mode and fix_data["has_suggestion"]:
            st.write("**Exact change:** Hidden until you reveal the suggested correction.")
        else:
            st.write("**Exact change:** No correction was suggested.")
        st.write(
            "**Validation result:** "
            + (
                "Syntax validation passed"
                if verification["compilation"]["passed"]
                else "Syntax validation failed"
            )
        )

        if fix_data["has_suggestion"] and (
            not learning_mode or st.session_state.reveal_correction
        ):
            st.markdown("#### Suggested corrected code")
            st.code(fix_data["suggested_code"], language="python")
            st.caption(f"{fix_data['reason']} {fix_data['confidence']}")
        elif learning_mode and fix_data["has_suggestion"]:
            st.caption("Correction hidden in Learning Mode. Use “Reveal suggested correction” when ready.")
        elif analysis["findings"]:
            st.caption("No unambiguous code edit is available; use the diagnosis and next action above.")

        if result["explanations"]:
            st.markdown("#### Explanation & Learning")
            explained_concepts: set[str] = set()
            for lesson in result["explanations"]:
                concept = lesson["concept"]
                if concept in explained_concepts:
                    continue
                explained_concepts.add(concept)
                with st.expander(f"{concept}", expanded=True):
                    st.write(f"**What it means:** {lesson['what_it_means']}")
                    st.write(f"**Why it likely occurred:** {lesson['why_it_likely_happened']}")
                    st.write(f"**How to fix it:** {lesson['how_to_fix']}")
                    st.write(f"**Python concept:** {concept}")
                    st.write(f"**Prevention tip:** {lesson['prevention_tip']}")
                    st.caption(lesson["basis"])

        if result["fix_options"]:
            st.markdown("#### Fix Options")
            st.caption(
                "These are alternatives, not automatic edits. Choose based on the behavior you intend."
            )
            for option in result["fix_options"]:
                with st.expander(option["label"]):
                    st.write(option["when_to_use"])
                    st.code(option["code"], language="python")

        st.markdown("#### Verification")
        verification = result["verification"]
        syntax_status = (
            "Syntax validation passed"
            if verification["compilation"]["passed"]
            else "Syntax validation failed"
        )
        if verification["compilation"]["passed"]:
            st.success(syntax_status)
        else:
            st.error(syntax_status)
        if not verification["compilation"]["passed"]:
            st.caption(f"Compiler detail: {verification['compilation']['detail']}")
        else:
            st.caption("compile() and AST parsing completed.")
        st.markdown("**Behavioral testing**")
        if verification["trusted_tests"]:
            st.caption(
                "Trusted reference checks run on educational fixture inputs; the suggested "
                "code itself was not executed, so this is not behavioral verification of the fix."
            )
        else:
            st.caption(
                "No relevant behavioral test was run. Syntax validation does not establish "
                "that the code behaves correctly."
            )
        for test in verification["trusted_tests"]:
            icon = "✅" if test["passed"] else "❌"
            st.write(
                f"{icon} **Reference check: {test['name']}** — expected "
                f"`{test['expected']}`, trusted reference actual `{test['actual']}`"
            )
        st.caption(verification["warning"])

st.divider()
st.caption(
    "Static analysis only: BugWise AI never executes submitted code. A clean parse is not proof "
    "of correct behavior, and runtime errors cannot all be predicted without execution."
)
