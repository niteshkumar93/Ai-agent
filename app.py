import streamlit as st
import pandas as pd
import time
import io

from xml_extractor import extract_failed_tests
from ai_reasoner import generate_ai_summary
from dashboard import render_dashboard


# -----------------------------------------------------------
# 🟦 SESSION STATE (Fix 3 – Dashboard Memory)
# -----------------------------------------------------------
if "show_dashboard" not in st.session_state:
    st.session_state.show_dashboard = False


# -----------------------------------------------------------
# 🎨 THEME HANDLER — LIGHT / DARK MODE
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
# ⚙ SIDEBAR SETTINGS
# -----------------------------------------------------------
with st.sidebar.expander("⚙ Settings", expanded=True):
    theme_choice = st.radio("Theme Mode:", ["Dark", "Light"], index=0)
    use_ai = st.checkbox("🤖 Use AI Analysis (Local Ollama Model)", value=False)

apply_theme(theme_choice)


# -----------------------------------------------------------
# 🏁 MAIN TITLE
# -----------------------------------------------------------
st.markdown("<h1 class='title-text'>🚀 Provar AI XML Analyzer</h1>", unsafe_allow_html=True)
st.write("Upload one or more **JUnit XML Reports** below:")


# -----------------------------------------------------------
# 📄 MULTIPLE XML UPLOAD
# -----------------------------------------------------------
uploaded_files = st.file_uploader(
    "📄 Upload XML Reports",
    type=["xml"],
    accept_multiple_files=True
)


# -----------------------------------------------------------
# 🧠 MAIN ANALYSIS LOGIC
# -----------------------------------------------------------
if uploaded_files:

    st.success(f"{len(uploaded_files)} file(s) uploaded.")

    if st.button("🔍 Analyze XML Reports", use_container_width=True):
        st.session_state.show_dashboard = False  # Reset dashboard display

        all_failures = []

        # STEP 1 — Extract failures
        for file in uploaded_files:
            st.info(f"Extracting failures from **{file.name}** ...")

            failures = extract_failed_tests(file)

            for f in failures:
                all_failures.append({
                    "testcase": f["name"],
                    "error": f["error"],
                    "details": f["details"],
                    "source": file.name
                })

        total = len(all_failures)
        st.write(f"### Found **{total} failed testcases** across {len(uploaded_files)} file(s).")

        progress = st.progress(0)
        step = 100 / total if total > 0 else 1

        results = []


        # STEP 2 — AI Analysis (Optional)
        for i, failure in enumerate(all_failures):

            progress.progress(int((i + 1) * step))

            if use_ai:
                ai_summary = generate_ai_summary(
                    testcase=failure["testcase"],
                    error_message=failure["error"],
                    details=failure["details"]
                )
            else:
                ai_summary = "⏭ AI Skipped (AI is turned OFF in Settings)"

            failure["analysis"] = ai_summary
            results.append(failure)

            time.sleep(0.05)

        st.success("🎉 Analysis Completed!")
        df = pd.DataFrame(results)


        # -----------------------------------------------------------
        # 📌 Accordion UI — Clean Failure View
        # -----------------------------------------------------------
        st.subheader("📌 Failure Analysis")

        for idx, row in df.iterrows():
            with st.expander(f"🔹 {row['testcase']} — 📄 {row['source']}"):
                st.markdown(f"**❗ Error:** {row['error']}")
                st.markdown(f"**📄 Details:** {row['details']}")
                st.markdown("### 🤖 AI Summary")
                st.write(row["analysis"])


        # -----------------------------------------------------------
        # 📊 DASHBOARD BUTTON (Fix 3 – session_state)
        # -----------------------------------------------------------
        if st.button("📊 Show Dashboard"):
            st.session_state.show_dashboard = True

        if st.session_state.show_dashboard:
            render_dashboard(df)


        # -----------------------------------------------------------
        # ⬇ EXPORT TO EXCEL (.xlsx)
        # -----------------------------------------------------------
        if st.button("⬇ Export to Excel (.xlsx)"):

            excel_buffer = io.BytesIO()
            df.to_excel(excel_buffer, index=False, sheet_name="AI_Analysis")

            st.download_button(
                label="📥 Download XLSX File",
                data=excel_buffer.getvalue(),
                file_name="Provar_AI_Analysis.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
