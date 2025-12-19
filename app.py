import streamlit as st
import pandas as pd
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
if "file_results" not in st.session_state:
    st.session_state.file_results = {}

# -----------------------------------------------------------
# HELPERS
# -----------------------------------------------------------
def safe_extract_failures(uploaded_file):
    try:
        uploaded_file.seek(0)
        return extract_failed_tests(uploaded_file)
    except Exception:
        return []

def detect_project(project_path: str, filename: str):
    for p in KNOWN_PROJECTS:
        if project_path and (f"/{p}" in project_path or f"\\{p}" in project_path):
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
# ANALYZE (SINGLE BUTTON – PER FILE LOGIC)
# -----------------------------------------------------------
if uploaded_files and st.button("🔍 Analyze XML Reports", use_container_width=True):

    st.session_state.file_results = {}

    for file in uploaded_files:
        failures = safe_extract_failures(file)

        # Detect project (safe even for zero failures)
        project_path = failures[0].get("projectCachePath", "") if failures else ""
        project = detect_project(project_path, file.name)

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

        # Baseline comparison PER FILE
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
# RESULTS — ONE ACCORDION PER XML FILE
# -----------------------------------------------------------
if st.session_state.file_results:

    total_new = 0
    total_existing = 0

    st.subheader("📊 Analysis Results (Per XML File)")

    for file_name, data in st.session_state.file_results.items():

        total_new += len(data["new"])
        total_existing += len(data["existing"])

        with st.expander(f"📄 {file_name} — {data['project']}", expanded=False):

            st.markdown(
                f"""
                **Project:** `{data['project']}`  
                🆕 **New Failures:** {len(data['new'])}  
                ♻️ **Existing Failures:** {len(data['existing'])}
                """
            )

            # ZERO FAILURE CASE
            if not data["new"]:
                st.success("✅ No failures in this XML report")

            # SHOW FAILURES
            for f in data["new"]:
                st.markdown(f"### ❌ {f['testcase']}")
                st.write("**Path:**", f["testcase_path"])
                st.write("**Error:**", f["error"])
                st.write("**Details:**", f["details"])

                if use_ai:
                    f["analysis"] = generate_ai_summary(
                        f["testcase"], f["error"], f["details"]
                    )
                    st.write("🤖 **AI:**", f["analysis"])

            # BASELINE PER XML FILE
            if st.button(
                f"🧱 Save Baseline ({file_name})",
                key=f"baseline_{file_name}"
            ):
                try:
                    save_baseline(
                        data["project"],
                        data["all"],  # baseline saved per XML
                        admin_key
                    )
                    st.success("✅ Baseline saved successfully")
                except Exception as e:
                    st.error(str(e))

    # -------------------------------------------------------
    # GLOBAL SUMMARY (CORRECT, NON‑DUPLICATED)
    # -------------------------------------------------------
    st.divider()
    st.success(f"🆕 Total New Failures: {total_new}")
    st.info(f"♻️ Total Existing Failures: {total_existing}")

    # -------------------------------------------------------
    # EXPORT (ALL FILES COMBINED)
    # -------------------------------------------------------
    export_rows = []
    for data in st.session_state.file_results.values():
        export_rows.extend(data["all"])

    if export_rows:
        df = pd.DataFrame(export_rows)
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            df.to_excel(writer, index=False)

        st.download_button(
            "⬇ Download Excel (All XMLs)",
            buffer.getvalue(),
            "Provar_AI_Analysis.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    if st.button("📊 Show Dashboard"):
        render_dashboard(pd.DataFrame(export_rows))
