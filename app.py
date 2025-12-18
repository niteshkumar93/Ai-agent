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
# 🟦 SESSION STATE
# -----------------------------------------------------------
if "show_dashboard" not in st.session_state:
    st.session_state.show_dashboard = False

# -----------------------------------------------------------
# 🌍 ENV DETECTION
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
    initial_sidebar_state="expanded"
)

# -----------------------------------------------------------
# ⚙ SIDEBAR
# -----------------------------------------------------------
with st.sidebar.expander("⚙ Settings", expanded=True):
    theme_choice = st.radio("Theme Mode:", ["Dark", "Light"], index=0)
    use_ai = st.checkbox("🤖 Use AI Analysis", value=False)

    project_name = st.text_input(
        "📦 Project Name (Baseline Key)",
        value="QAM_Lightning"
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

# -----------------------------------------------------------
# 📄 UPLOAD
# -----------------------------------------------------------
uploaded_files = st.file_uploader(
    "📄 Upload XML Reports",
    type=["xml"],
    accept_multiple_files=True
)

# -----------------------------------------------------------
# 🔧 Helper
# -----------------------------------------------------------
def shorten_project_cache_path(full_path: str) -> str:
    if not full_path:
        return ""
    marker = "Jenkins\\"
    if marker in full_path:
        return full_path.split(marker, 1)[1]
    parts = full_path.replace("/", "\\").split("\\")
    return "\\".join(parts[-2:])

# -----------------------------------------------------------
# 🧠 MAIN LOGIC
# -----------------------------------------------------------
if uploaded_files:

    st.success(f"{len(uploaded_files)} file(s) uploaded.")

    if st.button("🔍 Analyze XML Reports", use_container_width=True):

        st.session_state.show_dashboard = False
        all_failures = []

        # -------------------------------
        # Extract Failures
        # -------------------------------
        for file in uploaded_files:
            st.info(f"Extracting failures from **{file.name}** ...")
            failures = extract_failed_tests(file)

            for f in failures:
                all_failures.append({
                    "testcase": f["name"],
                    "testcase_path": f.get(
                    "testcase_path",
                   f["name"].replace(".", "/")
),
                    "error": f["error"],
                    "details": f["details"],
                    "source": file.name,
                    "webBrowserType": f["webBrowserType"],
                    "projectCachePath": shorten_project_cache_path(
                        f["projectCachePath"]
                    )
                })

        # -------------------------------
        # BASELINE COMPARISON
        # -------------------------------
        new_failures, existing_failures = compare_with_baseline(
            project_name,
            all_failures
        )

        st.subheader("📊 Baseline Comparison")
        st.success(f"🆕 New Failures: {len(new_failures)}")
        st.info(f"♻️ Existing Failures: {len(existing_failures)}")

        # -------------------------------
        # AI Analysis (ONLY NEW FAILURES)
        # -------------------------------
        progress = st.progress(0)
        step = 100 / len(new_failures) if new_failures else 100

        results = []

        for i, failure in enumerate(new_failures):
            progress.progress(int((i + 1) * step))

            if use_ai:
                failure["analysis"] = generate_ai_summary(
                    testcase=failure["testcase"],
                    error_message=failure["error"],
                    details=failure["details"]
                )
            else:
                failure["analysis"] = "⏭ AI Skipped (AI is turned OFF)"

            results.append(failure)
            time.sleep(0.05)

        st.success("🎉 Analysis Completed!")

        df = pd.DataFrame(results)

        # -------------------------------
        # REPORT ENV
        # -------------------------------
        if not df.empty:
            st.subheader("🧾 Report Environment")
            st.markdown(f"""
- **Browser:** `{df.loc[0, 'webBrowserType']}`
- **Project Cache Path:** `{df.loc[0, 'projectCachePath']}`
""")

        # -------------------------------
        # FAILURE VIEW
        # -------------------------------
        st.subheader("📌 New Failure Analysis")

        for _, row in df.iterrows():
            with st.expander(f"🔹 {row['testcase']} — 📄 {row['source']}"):
                st.markdown(f"**📁 Testcase Path:** `{row['testcase_path']}`")
                st.markdown(f"**❗ Error:** {row['error']}")
                st.markdown(f"**📄 Details:** {row['details']}")
                st.markdown("### 🤖 AI Summary")
                st.write(row["analysis"])

        # -------------------------------
        # BASELINE SAVE
        # -------------------------------
        if st.button("⭐ Mark This Report as Baseline"):
            save_baseline(project_name, all_failures)
            st.success("Baseline saved successfully ✅")

        # -------------------------------
        # DASHBOARD
        # -------------------------------
        if st.button("📊 Show Dashboard"):
            st.session_state.show_dashboard = True

        if st.session_state.show_dashboard:
            render_dashboard(pd.DataFrame(all_failures))

        # -------------------------------
        # EXPORT
        # -------------------------------
        if st.button("⬇ Export to Excel (.xlsx)"):
            buffer = io.BytesIO()
            df.to_excel(buffer, index=False, sheet_name="New_Failures")
            st.download_button(
                label="📥 Download XLSX File",
                data=buffer.getvalue(),
                file_name="Provar_AI_New_Failures.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
