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

if uploaded_files and st.button("🔍 Analyze XML Reports", use_container_width=True):

    st.session_state.df = None
    per_file_results = {}

    for file in uploaded_files:
        failures = safe_extract_failures(file)

        # Detect project
        detected_project = None
        if failures:
            detected_project = detect_project_from_path(
                failures[0].get("projectCachePath", "")
            )
        if not detected_project:
            detected_project = detect_project_from_filename(file.name)

        detected_project = detected_project or KNOWN_PROJECTS[0]

        # Normalize failures
        normalized = []
        for f in failures:
            normalized.append({
                "testcase": f["name"],
                "testcase_path": f.get("testcase_path", ""),
                "error": f["error"],
                "details": f["details"],
                "source": file.name,
                "webBrowserType": f.get("webBrowserType", "Unknown"),
                "projectCachePath": shorten_project_cache_path(
                    f.get("projectCachePath", "")
                ),
            })

        # Compare baseline (per file!)
        if load_baseline(detected_project):
            new_f, existing_f = compare_with_baseline(
                detected_project, normalized
            )
        else:
            new_f, existing_f = normalized, []

        per_file_results[file.name] = {
            "project": detected_project,
            "new": new_f,
            "existing": existing_f,
            "all": normalized,
        }

    st.session_state.file_results = per_file_results
    st.success("🎉 Analysis Completed!")

# -----------------------------------------------------------
# ANALYZE (PER XML FILE — SINGLE SOURCE OF TRUTH)
# -----------------------------------------------------------
if uploaded_files and st.button("🔍 Analyze XML Reports", use_container_width=True):

    st.session_state.file_results = {}

    for file in uploaded_files:
        failures = safe_extract_failures(file)

        # Detect project
        project = None
        if failures:
            project = detect_project(
                failures[0].get("projectCachePath", ""),
                file.name
            )
        else:
            project = detect_project("", file.name)

        normalized = []
        for f in failures:
            normalized.append({
                "testcase": f["name"],
                "testcase_path": f.get("testcase_path", ""),
                "error": f["error"],
                "details": f["details"],
                "source": file.name,
                "webBrowserType": f.get("webBrowserType", "Unknown"),
                "projectCachePath": shorten_project_cache_path(
                    f.get("projectCachePath", "")
                ),
            })

        # Compare with baseline PER FILE
        if load_baseline(project):
            new_f, existing_f = compare_with_baseline(project, normalized)
        else:
            new_f, existing_f = normalized, []

        st.session_state.file_results[file.name] = {
            "project": project,
            "new": new_f,
            "existing": existing_f,
            "all": normalized,
        }

    st.success("🎉 Analysis Completed!")

# -----------------------------------------------------------
# RESULTS (PER FILE VIEW)
# -----------------------------------------------------------
if "file_results" in st.session_state:

    total_new = 0
    total_existing = 0

    for file_name, data in st.session_state.file_results.items():

        total_new += len(data["new"])
        total_existing += len(data["existing"])

        with st.expander(f"📄 {file_name} — {data['project']}"):

            st.markdown(
                f"""
                **Project:** `{data['project']}`  
                🆕 **New Failures:** {len(data['new'])}  
                ♻️ **Existing Failures:** {len(data['existing'])}
                """
            )

            if not data["new"]:
                st.success("✅ No failures in this XML report")

            for f in data["new"]:
                st.markdown(f"### ❌ {f['testcase']}")
                st.write("Path:", f["testcase_path"])
                st.write("Error:", f["error"])
                st.write("Details:", f["details"])

            # 🔐 BASELINE PER XML FILE
            if st.button(
                f"🧱 Save Baseline ({file_name})",
                key=f"baseline_{file_name}"
            ):
                try:
                    save_baseline(
                        data["project"],
                        data["all"],
                        admin_key
                    )
                    st.success("✅ Baseline saved")
                except Exception as e:
                    st.error(str(e))

    # ✅ GLOBAL SUMMARY (DERIVED, NOT AGGREGATED)
    st.success(f"🆕 Total New Failures: {total_new}")
    st.info(f"♻️ Total Existing Failures: {total_existing}")

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
