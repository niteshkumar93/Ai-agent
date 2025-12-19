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
    get_baseline_history,
    rollback_baseline,
    load_baseline
)

# -----------------------------------------------------------
# CONSTANTS
# -----------------------------------------------------------
KNOWN_PROJECTS = [
    "VF_Lightning_Windows",
    "Regmain-Flexi",
    "Date_Time",
    "CPQ_Classic",
    "CPQ_Lightning",
    "QAM_Lightning",
    "QAM_Classic",
    "Internationalization_pipeline",
    "Lightning_Console_LogonAs",
    "DynamicForm",
    "Classic_Console_LogonAS",
    "LWC_Pipeline",
    "Regmain_LS_Windows",
    "Regmain_LC_Windows",
    "Regmain-VF",
    "FSL",
    "HYBRID_AUTOMATION_Pipeline",
]

# -----------------------------------------------------------
# SESSION STATE
# -----------------------------------------------------------
if "df" not in st.session_state:
    st.session_state.df = None
if "show_dashboard" not in st.session_state:
    st.session_state.show_dashboard = False
if "baseline_saved" not in st.session_state:
    st.session_state.baseline_saved = False

# -----------------------------------------------------------
# HELPERS
# -----------------------------------------------------------
def safe_extract_failures(uploaded_file):
    try:
        uploaded_file.seek(0)
        return extract_failed_tests(uploaded_file)
    except Exception:
        return []
    
def detect_project_from_path(path: str):
    if not path:
        return None
    for p in KNOWN_PROJECTS:
        if f"\\{p}" in path or f"/{p}" in path:
            return p
    return None
def detect_project_from_filename(filename: str):
    if not filename:
        return None
    name = os.path.splitext(filename)[0]
    for p in KNOWN_PROJECTS:
        if p.lower() in name.lower():
            return p
    return None

def shorten_project_cache_path(path: str) -> str:
    if not path:
        return ""
    marker = "Jenkins\\"
    if marker in path:
        return path.split(marker, 1)[1]
    return path.replace("/", "\\").split("\\")[-1]

# -----------------------------------------------------------
# PAGE CONFIG
# -----------------------------------------------------------
st.set_page_config(
    page_title="Provar AI - XML Analyzer",
    layout="wide",
)

# -----------------------------------------------------------
# SIDEBAR
# -----------------------------------------------------------
with st.sidebar:
    st.header("⚙ Settings")
    use_ai = st.checkbox("🤖 Use AI Analysis", value=False)
    admin_key = st.text_input("🔐 Admin Key", type="password")

# -----------------------------------------------------------
# TITLE
# -----------------------------------------------------------
st.markdown("## 🚀 Provar AI XML Analyzer")
st.write("Upload one or more **JUnit XML Reports** below:")

# -----------------------------------------------------------
# FILE UPLOAD
# -----------------------------------------------------------
uploaded_files = st.file_uploader(
    "📄 Upload XML Reports",
    type=["xml"],
    accept_multiple_files=True,
)

# -----------------------------------------------------------
# BASELINE SELECTION (SAFE + ZERO FAILURE SAFE)
# -----------------------------------------------------------
sample_failures = []          # ✅ ALWAYS defined
detected_project = None

if uploaded_files:
    sample_failures = safe_extract_failures(uploaded_files[0])

    # 🔹 Detect project EVEN IF ZERO FAILURES
    if sample_failures:
        detected_project = detect_project_from_path(
            sample_failures[0].get("projectCachePath", "")
        )
    else:
        # 👇 fallback: try reading project from filename
        for p in KNOWN_PROJECTS:
            if p.lower() in uploaded_files[0].name.lower():
                detected_project = p
                break

    st.subheader("📦 Baseline Selection")

    selected_project = st.selectbox(
        "Select project baseline",
        KNOWN_PROJECTS,
        index=KNOWN_PROJECTS.index(detected_project)
        if detected_project in KNOWN_PROJECTS else 0
    )

    baseline_exists = bool(load_baseline(selected_project))

    if baseline_exists:
        st.success("✅ Baseline available")
        analysis_mode = st.radio(
            "Analysis mode",
            ["Compare with baseline", "New analysis (ignore baseline)"]
        )
    else:
        st.warning("⚠️ No baseline found for this project")
        analysis_mode = "New analysis (ignore baseline)"
        st.info("You can create a baseline after analysis")

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
                "testcase_path": f.get("testcase_path", f["name"].replace(".", "/")),
                "error": f["error"],
                "details": f["details"],
                "source": file.name,
                "webBrowserType": f.get("webBrowserType", "Unknown"),
                "projectCachePath": shorten_project_cache_path(
                    f.get("projectCachePath", "")
                ),
            })

    if analysis_mode == "Compare with baseline" and baseline_exists:
        new_failures, existing_failures = compare_with_baseline(
            selected_project,
            all_failures
        )
    else:
        new_failures = all_failures
        existing_failures = []

    st.subheader("📊 Baseline Comparison")
    st.success(f"🆕 New Failures: {len(new_failures)}")
    st.info(f"♻️ Existing Failures: {len(existing_failures)}")

    results = []
    progress = st.progress(0)

    for i, f in enumerate(new_failures):
        progress.progress(int((i + 1) / max(len(new_failures), 1) * 100))
        f["analysis"] = (
            generate_ai_summary(f["testcase"], f["error"], f["details"])
            if use_ai else "⏭ AI Skipped"
        )
        results.append(f)
        time.sleep(0.03)

    if results:
     st.session_state.df = pd.DataFrame(results)
else:
    # Zero-failure baseline support
    st.session_state.df = pd.DataFrame([{
        "testcase": "✅ No Failures",
        "testcase_path": "",
        "error": "",
        "details": "",
       "source": file.name,
        "webBrowserType": "N/A",
        "projectCachePath": selected_project,
        "analysis": "All tests passed successfully"
    }])

    st.success("🎉 Analysis Completed!")

# -----------------------------------------------------------
# REPORT
# -----------------------------------------------------------
if st.session_state.df is not None:

    df = st.session_state.df

    st.subheader("🧾 Report Environment")
    st.markdown(f"""
- **Browser:** `{df.loc[0, 'webBrowserType']}`
- **Project Cache Path:** `{df.loc[0, 'projectCachePath']}`
""")

    st.subheader("📌 New Failure Analysis")
    for _, row in df.iterrows():
        with st.expander(f"🔹 {row['testcase']}"):
            st.write("❗ Error:", row["error"])
            st.write("📄 Details:", row["details"])
            st.write("🤖 AI:", row["analysis"])

    # -------------------------------------------------------
    # SAVE BASELINE
    # -------------------------------------------------------
    if st.button("🧱 Save as Baseline"):
     try:
        save_baseline(
            selected_project,
            df.to_dict(orient="records") if not df.empty else [],
            admin_key
        )
        st.success(f"✅ Baseline saved for {selected_project}")
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
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    # -------------------------------------------------------
    # DASHBOARD
    # -------------------------------------------------------
    if st.button("📊 Show Dashboard"):
        render_dashboard(df)
