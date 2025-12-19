import streamlit as st
import pandas as pd
import io
import os

from xml_extractor import extract_failed_tests
from ai_reasoner import generate_ai_summary
from dashboard import render_dashboard
from baseline_manager import save_baseline, compare_with_baseline, load_baseline

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
# HELPERS
# -----------------------------------------------------------
def safe_extract_failures(uploaded_file):
    try:
        uploaded_file.seek(0)
        return extract_failed_tests(uploaded_file)
    except Exception:
        return []

def detect_project(path: str, filename: str):
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
# PER‑XML INDEPENDENT PROCESSING
# -----------------------------------------------------------
if uploaded_files:

    for xml_file in uploaded_files:

        with st.expander(f"📄 {xml_file.name}", expanded=False):

            failures = safe_extract_failures(xml_file)

            project_path = failures[0].get("projectCachePath", "") if failures else ""
            detected_project = detect_project(project_path, xml_file.name)

            # ---------------- Project (PER XML)
            project = st.selectbox(
                "Select project baseline",
                KNOWN_PROJECTS,
                index=KNOWN_PROJECTS.index(detected_project),
                key=f"project_{xml_file.name}"
            )

            baseline_exists = bool(load_baseline(project))

            # ---------------- Analysis mode (PER XML)
            if baseline_exists:
                mode = st.radio(
                    "Analysis mode",
                    ["Compare with baseline", "New analysis (ignore baseline)"],
                    key=f"mode_{xml_file.name}"
                )
            else:
                st.warning("⚠️ No baseline found for this project")
                mode = "New analysis (ignore baseline)"

            # ---------------- Analyze (PER XML)
            if st.button("🔍 Analyze XML", key=f"analyze_{xml_file.name}"):

                normalized = []
                for f in failures:
                    normalized.append({
                        "testcase": f["name"],
                        "testcase_path": f.get("testcase_path", ""),
                        "error": f["error"],
                        "details": f["details"],
                        "source": xml_file.name,
                        "webBrowserType": f.get("webBrowserType", "Unknown"),
                        "projectCachePath": shorten_project_cache_path(
                            f.get("projectCachePath", "")
                        ),
                    })

                # ---------- Baseline compare
                if mode == "Compare with baseline" and baseline_exists:
                    new_f, existing_f = compare_with_baseline(project, normalized)
                else:
                    new_f, existing_f = normalized, []

                # ---------- CORRECT COUNTS
                st.success(f"🆕 New Failures: {len(new_f)}")
                st.info(f"♻️ Existing Failures: {len(existing_f)}")

                # ---------- ZERO FAILURE (FIXED)
                if len(new_f) == 0:
                    st.success("✅ Zero failures detected in this XML report")

                # ---------- Show failures
                for f in new_f:
                    with st.expander(f"❌ {f['testcase']}"):
                        st.write("Path:", f["testcase_path"])
                        st.write("Error:", f["error"])
                        st.write("Details:", f["details"])

                        if use_ai:
                            st.write(
                                "🤖 AI:",
                                generate_ai_summary(
                                    f["testcase"],
                                    f["error"],
                                    f["details"]
                                )
                            )

                # ---------- Save baseline (PER XML)
                if st.button("🧱 Save Baseline", key=f"save_{xml_file.name}"):
                    try:
                        save_baseline(project, normalized, admin_key)
                        st.success("✅ Baseline saved successfully")
                    except Exception as e:
                        st.error(str(e))
