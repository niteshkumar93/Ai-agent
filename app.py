import streamlit as st
import pandas as pd
from baseline_manager import save_baseline, load_baseline
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import io
import os
from datetime import datetime
from baseline_tracker_dashboard import render_baseline_tracker_dashboard
# -----------------------------------------------------------
# HELPER FUNCTIONS
# -----------------------------------------------------------
def format_execution_time(raw_time: str):
    """Format timestamp from XML to readable format"""
    if raw_time in (None, "", "Unknown"):
        return "Unknown"

    # Try different datetime formats
    formats_to_try = [
        "%Y-%m-%dT%H:%M:%S",           # ISO format: 2025-01-15T14:30:00
        "%Y-%m-%d %H:%M:%S",           # Common format: 2025-01-15 14:30:00
        "%a %b %d %H:%M:%S %Z %Y",     # Full format: Wed Jan 15 14:30:00 UTC 2025
        "%Y-%m-%dT%H:%M:%S.%f",        # With milliseconds
        "%Y-%m-%dT%H:%M:%SZ",          # With Z suffix
        "%d/%m/%Y %H:%M:%S",           # DD/MM/YYYY format
        "%m/%d/%Y %H:%M:%S",           # MM/DD/YYYY format
    ]
    
    for fmt in formats_to_try:
        try:
            dt = datetime.strptime(raw_time, fmt)
            return dt.strftime("%d %b %Y, %H:%M UTC")
        except ValueError:
            continue
    
    # If no format matches, return as-is
    return raw_time

# -----------------------------------------------------------
# IMPORT PROVAR MODULES (EXISTING)
# -----------------------------------------------------------
from xml_extractor import extract_failed_tests
from ai_reasoner import (
    generate_ai_summary, 
    generate_batch_analysis,
    generate_jira_ticket,
    suggest_test_improvements
)
from baseline_manager import (
    save_baseline as save_provar_baseline,
    compare_with_baseline as compare_provar_baseline,
    load_baseline as load_provar_baseline
)

# -----------------------------------------------------------
# IMPORT AUTOMATIONAPI MODULES
# -----------------------------------------------------------
from automation_api_extractor import (
    extract_automation_api_failures,
    group_failures_by_spec,
    get_failure_statistics
)
from automation_api_baseline_manager import (
    save_baseline as save_api_baseline,
    compare_with_baseline as compare_api_baseline,
    load_baseline as load_api_baseline,
    baseline_exists as api_baseline_exists
)

# -----------------------------------------------------------
# CONSTANTS
# -----------------------------------------------------------
KNOWN_PROJECTS = [
    "VF_Lightning_Windows", "Regmain-Flexi", "DateTime",
    "CPQ_Classic", "CPQ_Lightning", "QAM_Lightning", "QAM_Classic",
    "Internationalization_pipeline", "Lightning_Console_LogonAs",
    "DynamicForm", "Classic_Console_LogonAS", "LWC_Pipeline",
    "Regmain_LS_Windows", "Regmain_LC_Windows", "Prerelease-Lightning",
    "Regmain-VF", "FSL", "HYBRID_AUTOMATION_Pipeline", "Smoke_LC_Windows",
    "Smoke_CC_Windows", "Smoke_LS_Windows", "Smoke_CS_Windows",
]

APP_VERSION = "3.0.0"  # New version with AutomationAPI support

# -----------------------------------------------------------
# PROVAR HELPER FUNCTIONS (EXISTING)
# -----------------------------------------------------------
def safe_extract_failures(uploaded_file):
    try:
        uploaded_file.seek(0)
        return extract_failed_tests(uploaded_file)
    except Exception as e:
        st.error(f"Error parsing {uploaded_file.name}: {str(e)}")
        return []

def detect_project(path: str, filename: str):
    for p in KNOWN_PROJECTS:
        if path and (f"/{p}" in path or f"\\{p}" in path):
            return p
        if p.lower() in filename.lower():
            return p
    if "datetime" in filename.lower():
        return "Date_Time"
    return "UNKNOWN_PROJECT"

def shorten_project_cache_path(path):
    if not path:
        return ""
    marker = "Jenkins\\"
    if marker in path:
        return path.split(marker, 1)[1]
    return path.replace("/", "\\").split("\\")[-1]

def render_summary_card(xml_name, new_count, existing_count, total_count):
    """Render a summary card for each XML file"""
    status_color = "🟢" if new_count == 0 else "🔴"
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Status", status_color)
    with col2:
        st.metric("New Failures", new_count, delta=None if new_count == 0 else f"+{new_count}", delta_color="inverse")
    with col3:
        st.metric("Existing Failures", existing_count)
    with col4:
        st.metric("Total Failures", total_count)

def render_comparison_chart(all_results):
    """Create a comparison chart across all uploaded XMLs"""
    if not all_results:
        return
    
    df_data = []
    for result in all_results:
        df_data.append({
            'File': result['project'],
            'New Failures': result['new_count'],
            'Existing Failures': result['existing_count'],
            'Total': result['total_count']
        })
    
    df = pd.DataFrame(df_data)
    
    fig = go.Figure()
    fig.add_trace(go.Bar(
        name='New Failures',
        x=df['File'],
        y=df['New Failures'],
        marker_color='#FF4B4B'
    ))
    fig.add_trace(go.Bar(
        name='Existing Failures',
        x=df['File'],
        y=df['Existing Failures'],
        marker_color='#FFA500'
    ))
    
    fig.update_layout(
        title='Failure Comparison Across All Reports',
        xaxis_title='XML Files',
        yaxis_title='Number of Failures',
        barmode='stack',
        height=400,
        hovermode='x unified'
    )
    
    st.plotly_chart(fig, use_container_width=True)

# -----------------------------------------------------------
# PAGE CONFIGURATION
# -----------------------------------------------------------
st.set_page_config("Provar AI - Multi-Platform XML Analyzer", layout="wide", page_icon="🚀")

# Custom CSS
st.markdown("""
    <style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        padding: 1rem 0;
    }
    .section-divider {
        border-top: 2px solid #e0e0e0;
        margin: 2rem 0;
    }
    .stExpander {
        border: 1px solid #e0e0e0;
        border-radius: 10px;
        margin-bottom: 1rem;
    }
    .ai-feature-box {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1rem;
        border-radius: 10px;
        color: white;
        margin: 1rem 0;
    }
    .spec-group {
        background: #f8f9fa;
        border-left: 4px solid #667eea;
        padding: 1rem;
        margin: 1rem 0;
        border-radius: 8px;
    }
    .real-failure {
        border-left: 4px solid #dc3545;
    }
    .skipped-failure {
        border-left: 4px solid #ffc107;
        background: #fff9e6;
    }
    </style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-header">🤖 Provar AI - Multi-Platform Report Analysis Tool</div>', unsafe_allow_html=True)

# -----------------------------------------------------------
# SIDEBAR CONFIGURATION
# -----------------------------------------------------------
with st.sidebar:
    st.subheader("🧭 Navigation")
    page = st.radio(
        "Go to:",
        options=[
            "📁 Provar Reports",
            "📊 Baseline Tracker"
            ],
            index=0
            )
    st.header("⚙️ Configuration")
    
    # NEW: Radio button for report type selection
    st.subheader("📊 Report Type")
    report_type = st.radio(
        "Select Report Type:",
        options=["Provar Regression Reports", "AutomationAPI Reports"],
        index=0,
        help="Choose the type of XML report you want to analyze"
    )
    
    st.markdown("---")
    
    # AI Settings
    st.subheader("🤖 AI Features")
    use_ai = st.checkbox("Enable AI Analysis", value=False, help="Use Groq AI for intelligent failure analysis")
    
    # Advanced AI Features
    with st.expander("🎯 Advanced AI Features"):
        enable_batch_analysis = st.checkbox("Batch Pattern Analysis", value=True, help="Find common patterns across failures")
        enable_jira_generation = st.checkbox("Jira Ticket Generation", value=True, help="Auto-generate Jira tickets")
        enable_test_improvements = st.checkbox("Test Improvement Suggestions", value=False, help="Get suggestions to improve test stability")
    
    admin_key = st.text_input("🔐 Admin Key", type="password", help="Required for saving baselines")
    
    st.markdown("---")
    
    # Version info
    st.caption(f"Version: {APP_VERSION}")
    
    # Reset Button
    if st.button("🔄 Reset All", type="secondary", use_container_width=True, help="Clear all data and start fresh"):
        # Clear session state
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.success("✅ UI Reset! Ready for new uploads.")
        st.rerun()
    
    st.markdown("---")
    st.markdown("### 📊 Upload Statistics")
    if 'upload_stats' in st.session_state:
        st.info(f"**Files Uploaded:** {st.session_state.upload_stats.get('count', 0)}")
        st.info(f"**Total Failures:** {st.session_state.upload_stats.get('total_failures', 0)}")
        st.info(f"**New Failures:** {st.session_state.upload_stats.get('new_failures', 0)}")
    
    # AI Status
    st.markdown("---")
    st.markdown("### 🤖 AI Status")
    groq_key = os.getenv("GROQ_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")
    
    if groq_key:
        st.success("✅ Groq AI (Free)")
    elif openai_key:
        st.info("ℹ️ OpenAI (Paid)")
    else:
        st.warning("⚠️ No AI configured")

# -----------------------------------------------------------
# MAIN CONTENT AREA
# -----------------------------------------------------------
# -----------------------------------------------------------
# MAIN CONTENT AREA
# -----------------------------------------------------------

if page == "📈 Baseline Tracker":
    render_baseline_tracker_dashboard()

else:
    # ============================================================
    # REPORT TYPE SWITCH
    # ============================================================

    if report_type == "Provar Regression Reports":
        # ============================================================
        # PROVAR XML REPORT ANALYSIS
        # ============================================================
        st.markdown("## 📁 Upload Provar XML Reports")
        st.markdown(
            "Upload multiple JUnit XML reports from Provar test executions "
            "for simultaneous AI-powered analysis"
        )

        uploaded_files = st.file_uploader(
            "Choose Provar XML files",
            type=["xml"],
            accept_multiple_files=True,
            key="provar_uploader",
            help="Select one or more XML files to analyze",
        )

        if uploaded_files:
            st.success(f"✅ {len(uploaded_files)} Provar file(s) uploaded successfully!")
            # 🔽 KEEP YOUR EXISTING PROVAR ANALYSIS LOGIC HERE (UNCHANGED)

        else:
            st.info("👆 Upload one or more Provar XML files to begin AI-powered analysis")

            st.markdown("### 🎯 Provar Features")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.markdown("**📊 Multi-File Analysis**")
                st.write("Upload and analyze multiple XML reports simultaneously")
            with col2:
                st.markdown("**🤖 AI-Powered Insights**")
                st.write("Get intelligent failure analysis with Groq (FREE)")
            with col3:
                st.markdown("**📈 Baseline Tracking**")
                st.write("Compare results against historical baselines")

    else:
        # ============================================================
        # AUTOMATION API REPORT ANALYSIS
        # ============================================================
        st.markdown("## 🔧 Upload AutomationAPI XML Reports")
        st.markdown(
            "Upload XML reports from AutomationAPI test executions "
            "(e.g., Jasmine / Selenium tests)"
        )

        uploaded_api_files = st.file_uploader(
            "Choose AutomationAPI XML files",
            type=["xml"],
            accept_multiple_files=True,
            key="api_uploader",
            help="Upload XML reports from AutomationAPI workspace",
        )

        if uploaded_api_files:
            st.success(f"✅ {len(uploaded_api_files)} AutomationAPI file(s) uploaded!")

            # -----------------------------------------------------------
            # ANALYSIS BUTTON
            # -----------------------------------------------------------
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                analyze_api = st.button(
                    "🔍 Analyze AutomationAPI Reports",
                    type="primary",
                    use_container_width=True,
                )

            if analyze_api:
                st.session_state.api_results = []

                progress_bar = st.progress(0)
                status_text = st.empty()

                for idx, xml_file in enumerate(uploaded_api_files):
                    status_text.text(
                        f"Processing {xml_file.name}... ({idx + 1}/{len(uploaded_api_files)})"
                    )

                    try:
                        failures = extract_automation_api_failures(xml_file)

                        if failures:
                            project = failures[0].get("project", "Unknown")
                            baseline_exists_flag = api_baseline_exists(project)

                            real_failures = [
                                f for f in failures if not f.get("_no_failures")
                            ]

                            if baseline_exists_flag and real_failures:
                                new_f, existing_f = compare_api_baseline(
                                    project, real_failures
                                )
                            else:
                                new_f, existing_f = real_failures, []

                            stats = get_failure_statistics(
                                real_failures if real_failures else failures
                            )

                            st.session_state.api_results.append(
                                {
                                    "filename": xml_file.name,
                                    "project": project,
                                    "all_failures": real_failures,
                                    "new_failures": new_f,
                                    "existing_failures": existing_f,
                                    "grouped_failures": group_failures_by_spec(
                                        real_failures
                                    ),
                                    "stats": stats,
                                    "baseline_exists": baseline_exists_flag,
                                    "timestamp": failures[0].get("timestamp", "Unknown"),
                                }
                            )

                    except Exception as e:
                        st.error(f"Error parsing {xml_file.name}: {str(e)}")

                    progress_bar.progress((idx + 1) / len(uploaded_api_files))

                status_text.text("✅ Analysis complete!")
                progress_bar.empty()

        else:
            st.info("👆 Upload AutomationAPI XML files to begin analysis")

            st.markdown("### 🎯 AutomationAPI Features")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.markdown("**📋 Spec-Based Grouping**")
                st.write("Failures grouped by spec file for clarity")
            with col2:
                st.markdown("**🎨 Smart Color Coding**")
                st.write("🔴 Real failures vs 🟡 Skipped failures")
            with col3:
                st.markdown("**📊 Detailed Statistics**")
                st.write("Per-spec analysis with execution times")


