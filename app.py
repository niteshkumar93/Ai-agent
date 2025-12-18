import streamlit as st
import pandas as pd
import time
import io
import os
def safe_extract_failures(uploaded_file):
    try:
        uploaded_file.seek(0)  # 🔑 reset pointer
        return extract_failed_tests(uploaded_file)
    except Exception:
        return []

from xml_extractor import extract_failed_tests
from ai_reasoner import generate_ai_summary
from dashboard import render_dashboard
from baseline_manager import(
    save_baseline,
    compare_with_baseline,
    get_baseline_history,
    rollback_baseline,
)
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
# 🟦 SESSION STATE (TOP LEVEL)
# -----------------------------------------------------------
if "df" not in st.session_state:
    st.session_state.df = None
if "show_dashboard" not in st.session_state:
    st.session_state.show_dashboard = False
if "baseline_saved" not in st.session_state:
    st.session_state.baseline_saved = False
if "rollback_done" not in st.session_state:
    st.session_state.rollback_done = False

# -----------------------------------------------------------
# 🌍 ENV
# -----------------------------------------------------------
IS_CLOUD = os.getenv("STREAMLIT_CLOUD") == "true"

# -----------------------------------------------------------
# 🎨 THEME
# -----------------------------------------------------------
def apply_theme(mode):
    if mode == "Dark":
        st.markdown("""
            <style>
                body { background-color: #0e0e0e; }
                .title-text { color: #ffffff !important; }
            </style>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
            <style>
                body { background-color: #ffffff; }
                .title-text { color: #111111 !important; }
            </style>
        """, unsafe_allow_html=True)

# -----------------------------------------------------------
# 🌐 PAGE CONFIG
# -----------------------------------------------------------
st.set_page_config(
    page_title="Provar AI - XML Analyzer",
    layout="wide",
    initial_sidebar_state="expanded",
)

# -----------------------------------------------------------
# ⚙ SIDEBAR
# -----------------------------------------------------------
with st.sidebar.expander("⚙ Settings", expanded=True):
    theme_choice = st.radio("Theme Mode", ["Dark", "Light"], index=0)
    use_ai = st.checkbox("🤖 Use AI Analysis", value=False)

    project_name = st.text_input(
        "📦 Project Name (Baseline Key)",
        value="QAM_Lightning",
    )

    admin_key = st.text_input(
        "🔐 Admin Key (Required for Baseline / Rollback)",
        type="password",
    )

    if IS_CLOUD:
        st.caption("☁️ AI Engine: OpenAI (Cloud)")
    else:
        st.caption("🖥️ AI Engine: Ollama (Local)")

apply_theme(theme_choice)

# -----------------------------------------------------------
# 🏁 TITLE
# -----------------------------------------------------------
st.markdown("<h1 class='title-text'>🚀 Provar AI XML Analyzer</h1>", unsafe_allow_html=True)
st.write("Upload one or more **JUnit XML Reports** below:")
def detect_project_from_path(path: str):
    if not path:
        return None
    for p in KNOWN_PROJECTS:
        if f"\\{p}" in path or f"/{p}" in path:
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
# 📄 UPLOAD
# -----------------------------------------------------------
uploaded_files = st.file_uploader(
    "📄 Upload XML Reports",
    type=["xml"],
    accept_multiple_files=True,
)
selected_project = None
baseline_exists = False

if uploaded_files:
    # Try auto-detect from first XML
    sample_failures = safe_extract_failures(uploaded_files[0])

    detected_project = None

    if sample_failures:
        detected_project = detect_project_from_path(
            sample_failures[0].get("projectCachePath", "")
        )

    st.subheader("📦 Baseline Selection")

    selected_project = None
analysis_mode = "New analysis (ignore baseline)"
baseline_exists = False

if uploaded_files:
    sample_failures = extract_failed_tests(uploaded_files[0])
    detected_project = None

    if sample_failures:
        detected_project = detect_project_from_path(
            sample_failures[0].get("projectCachePath", "")
        )

    st.subheader("📦 Baseline Selection")

    selected_project = st.selectbox(
        "Select baseline project",
        KNOWN_PROJECTS,
        index=KNOWN_PROJECTS.index(detected_project)
        if detected_project in KNOWN_PROJECTS else 0
    )

    from baseline_manager import load_baseline
    baseline_exists = bool(load_baseline(selected_project))

    if baseline_exists:
        st.success("✅ Baseline available for this project")
        analysis_mode = st.radio(
            "Choose analysis mode",
            ["Compare with baseline", "New analysis (ignore baseline)"]
        )
    else:
        st.warning("⚠️ Baseline not available for this project")
        st.info("You can save this report as a new baseline after analysis")

    from baseline_manager import load_baseline
    baseline_exists = bool(load_baseline(selected_project))

    if baseline_exists:
        st.success("✅ Baseline available for this project")
        analysis_mode = st.radio(
            "Choose analysis mode",
            ["Compare with baseline", "New analysis (ignore baseline)"]
        )
    else:
        st.warning("⚠️ Baseline not available for this project")
        analysis_mode = "New analysis (ignore baseline)"
        st.info("You can save this report as a new baseline after analysis")

# -----------------------------------------------------------
# 🔧 HELPERS
# -----------------------------------------------------------
def detect_project_from_path(path: str):
    if not path:
        return None
    for p in KNOWN_PROJECTS:
        if f"\\{p}" in path or f"/{p}" in path:
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
# 🧠 ANALYZE
# -----------------------------------------------------------
# -----------------------------------------------------------
# 🧠 ANALYZE
# -----------------------------------------------------------
if uploaded_files and st.button("🔍 Analyze XML Reports", use_container_width=True):

    st.session_state.df = None
    st.session_state.show_dashboard = False
    st.session_state.baseline_saved = False

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

    # ---- Decide comparison mode
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

    st.session_state.df = pd.DataFrame(results)
    st.success("🎉 Analysis Completed!")

    # ✅ SAFE BASELINE LOGIC
    if analysis_mode == "Compare with baseline":
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

    progress = st.progress(0)
    results = []

    for i, f in enumerate(new_failures):
        progress.progress(int((i + 1) / max(len(new_failures), 1) * 100))
        f["analysis"] = (
            generate_ai_summary(f["testcase"], f["error"], f["details"])
            if use_ai else "⏭ AI Skipped"
        )
        results.append(f)
        time.sleep(0.03)

    st.session_state.df = pd.DataFrame(results)
    st.success("🎉 Analysis Completed!")

# -----------------------------------------------------------
# 🧾 REPORT
# -----------------------------------------------------------
if st.session_state.df is not None and not st.session_state.df.empty:
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
    # 🧱 SAVE BASELINE
    # -------------------------------------------------------
    if st.button("🧱 Save as Baseline"):
     try:
        save_baseline(
            selected_project,
            df.to_dict(orient="records"),
            admin_key
        )
        st.success(f"✅ Baseline saved for {selected_project}")
     except Exception as e:
        st.error(str(e))


    if st.session_state.baseline_saved:
        st.success("✅ Baseline saved & committed to GitHub")

    # -------------------------------------------------------
    # 🕒 HISTORY + ROLLBACK
    # -------------------------------------------------------
    st.subheader("🕒 Baseline History")
    history = get_baseline_history(project_name)

    if history:
        commit_map = {
            f"{h['commit']['message']} | {h['commit']['author']['date']}": h["sha"]
            for h in history[:5]
        }

        selected = st.selectbox("Select baseline version", commit_map.keys())

        if st.button("⏪ Rollback to selected baseline"):
            if not admin_key:
                st.error("Admin key required")
            else:
                rollback_baseline(project_name, commit_map[selected], admin_key)
                st.session_state.rollback_done = True

    else:
        st.info("No baseline history found")

    if st.session_state.rollback_done:
        st.success("✅ Rollback successful")

    # -------------------------------------------------------
    # 📊 DASHBOARD
    # -------------------------------------------------------
    if st.button("📊 Show Dashboard"):
        st.session_state.show_dashboard = True

    if st.session_state.show_dashboard:
        render_dashboard(df)

    # -------------------------------------------------------
    # ⬇ EXPORT
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

