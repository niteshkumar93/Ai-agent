import streamlit as st
import pandas as pd
import time
import io
import os

from xml_extractor import extract_failed_tests
from ai_reasoner import generate_ai_summary
from dashboard import render_dashboard
from baseline_manager import (
    save_baseline,
    compare_with_baseline,
    load_baseline
)

# -----------------------------------------------------------
# CONSTANTS
# -----------------------------------------------------------
KNOWN_PROJECTS = [
    "VF_Lightning_Windows", "Regmain-Flexi", "Date_Time",
    "CPQ_Classic", "CPQ_Lightning", "QAM_Lightning", "QAM_Classic",
    "Internationalization_pipeline", "Lightning_Console_LogonAs",
    "DynamicForm", "Classic_Console_LogonAS", "LWC_Pipeline",
    "Regmain_LS_Windows", "Regmain_LC_Windows",
    "Regmain-VF", "FSL", "HYBRID_AUTOMATION_Pipeline",
]

# -----------------------------------------------------------
# SESSION STATE
# -----------------------------------------------------------
if "df" not in st.session_state:
    st.session_state.df = None

# -----------------------------------------------------------
# HELPERS
# -----------------------------------------------------------
def safe_extract_failures(uploaded_file):
    try:
        uploaded_file.seek(0)
        return extract_failed_tests(uploaded_file)
    except Exception:
        return []

def detect_project(path, filename):
    for p in KNOWN_PROJECTS:
        if path and (f"/{p}" in path or f"\\{p}" in path):
            return p
        if p.lower() in filename.lower():
            return p
    return KNOWN_PROJECTS[0]

def shorten_project_cache_path(path):
    if not path:
        return ""
    marker = "Jenkins\\"
    if marker in path:
        return path.split(marker, 1)[1]
    return path.replace("/", "\\").split("\\")[-1]

# -----------------------------------------------------------
# PAGE
# -----------------------------------------------------------
st.set_page_config("Provar AI - XML Analyzer", layout="wide")
st.title("🚀 Provar AI XML Analyzer")

with st.sidebar:
    use_ai = st.checkbox("🤖 Use AI Analysis", value=False)
    admin_key = st.text_input("🔐 Admin Key", type="password")

uploaded_files = st.file_uploader(
    "📄 Upload JUnit XML Reports",
    type=["xml"],
    accept_multiple_files=True
)

# -----------------------------------------------------------
# BASELINE SELECTION
# -----------------------------------------------------------
selected_project = None
analysis_mode = "New analysis"
baseline_exists = False

if uploaded_files:
    sample_failures = safe_extract_failures(uploaded_files[0])
    sample_path = sample_failures[0]["projectCachePath"] if sample_failures else ""
    selected_project = detect_project(sample_path, uploaded_files[0].name)

    st.subheader("📦 Baseline Selection")

    selected_project = st.selectbox(
        "Select project baseline",
        KNOWN_PROJECTS,
        index=KNOWN_PROJECTS.index(selected_project)
    )

    baseline_exists = bool(load_baseline(selected_project))

    if baseline_exists:
        analysis_mode = st.radio(
            "Analysis mode",
            ["Compare with baseline", "New analysis (ignore baseline)"]
        )
    else:
        st.warning("⚠️ No baseline found for this project")

# -----------------------------------------------------------
# ANALYZE
# -----------------------------------------------------------
if uploaded_files and st.button("🔍 Analyze XML Reports", use_container_width=True):

    all_failures = []

    for file in uploaded_files:
        failures = safe_extract_failures(file)
        for f in failures:
            all_failures.append({
                "testcase": f["name"],
                "testcase_path": f.get("testcase_path", ""),
                "error": f["error"],
                "details": f["details"],
                "source": file.name,
                "webBrowserType": f.get("webBrowserType", "Unknown"),
                "projectCachePath": shorten_project_cache_path(
                    f.get("projectCachePath", "")
                )
            })

    if analysis_mode == "Compare with baseline" and baseline_exists:
        new_failures, existing_failures = compare_with_baseline(
            selected_project, all_failures
        )
    else:
        new_failures = all_failures
        existing_failures = []

    st.success(f"🆕 New Failures: {len(new_failures)}")
    st.info(f"♻️ Existing Failures: {len(existing_failures)}")

    results = []

    if new_failures:
        for f in new_failures:
            f["analysis"] = (
                generate_ai_summary(f["testcase"], f["error"], f["details"])
                if use_ai else "⏭ AI Skipped"
            )
            results.append(f)
    else:
        # ✅ ZERO FAILURE REPORT
        results.append({
            "testcase": "✅ All Tests Passed",
            "testcase_path": "",
            "error": "",
            "details": "",
            "source": uploaded_files[0].name,
            "webBrowserType": "N/A",
            "projectCachePath": selected_project,
            "analysis": "No failures detected"
        })

    st.session_state.df = pd.DataFrame(results)
    st.success("🎉 Analysis Completed!")

# -----------------------------------------------------------
# REPORT
# -----------------------------------------------------------
if st.session_state.df is not None:
    df = st.session_state.df

    st.subheader("🧾 Report Environment")
    st.write(f"**Project:** `{selected_project}`")

    st.subheader("📌 Analysis Results")
    for _, row in df.iterrows():
        with st.expander(row["testcase"]):
            st.write("❗ Error:", row["error"])
            st.write("📄 Details:", row["details"])
            st.write("🤖 AI:", row["analysis"])

    # -------------------------------------------------------
    # SAVE BASELINE (ZERO FAILURE SAFE)
    # -------------------------------------------------------
    if st.button("🧱 Save as Baseline"):
        try:
            save_baseline(
                selected_project,
                df.to_dict(orient="records"),
                admin_key
            )
            st.success("✅ Baseline saved successfully")
        except Exception as e:
            st.error(str(e))

    # -------------------------------------------------------
    # EXPORT
    # -------------------------------------------------------
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)

    st.download_button(
        "⬇ Download Excel",
        buffer.getvalue(),
        "Provar_AI_Analysis.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    if st.button("📊 Show Dashboard"):
        render_dashboard(df)
