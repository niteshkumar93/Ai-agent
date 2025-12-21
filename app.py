import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import io
import os
import streamlit as st
from datetime import datetime

# Import existing modules
from xml_extractor import extract_failed_tests
from pdf_extractor import extract_pdf_failures  # NEW
from ai_reasoner import (
    generate_ai_summary, 
    generate_batch_analysis,
    generate_jira_ticket,
    suggest_test_improvements
)
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

APP_VERSION = "3.0.0"  # Added PDF support

# -----------------------------------------------------------
# HELPERS
# -----------------------------------------------------------
def format_execution_time(raw_time: str):
    """Format timestamp from XML to readable format"""
    if raw_time in (None, "", "Unknown"):
        return "Unknown"

    formats_to_try = [
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%a %b %d %H:%M:%S %Z %Y",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%SZ",
        "%d/%m/%Y %H:%M:%S",
        "%m/%d/%Y %H:%M:%S",
    ]
    
    for fmt in formats_to_try:
        try:
            dt = datetime.strptime(raw_time, fmt)
            return dt.strftime("%d %b %Y, %H:%M UTC")
        except ValueError:
            continue
    
    return raw_time

def safe_extract_failures(uploaded_file, file_type='xml'):
    """Extract failures from XML or PDF"""
    try:
        uploaded_file.seek(0)
        if file_type == 'pdf':
            return extract_pdf_failures(uploaded_file)
        else:
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
    return KNOWN_PROJECTS[0]

def shorten_project_cache_path(path):
    if not path:
        return ""
    marker = "Jenkins\\"
    if marker in path:
        return path.split(marker, 1)[1]
    return path.replace("/", "\\").split("\\")[-1]

def render_summary_card(xml_name, new_count, existing_count, total_count):
    """Render a summary card for each file"""
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

def render_pdf_step_visualization(steps_data):
    """Visualize test steps with pass/fail status"""
    if not steps_data:
        return
    
    # Create a visual step flow
    for idx, step in enumerate(steps_data):
        status_icon = "✅" if step['status'] == 'passed' else "❌" if step['status'] == 'failed' else "⚪"
        status_color = "green" if step['status'] == 'passed' else "red" if step['status'] == 'failed' else "gray"
        
        col1, col2 = st.columns([1, 10])
        with col1:
            st.markdown(f"**{idx+1}**")
        with col2:
            if step['status'] == 'failed':
                st.error(f"{status_icon} **{step['text']}**")
            elif step['status'] == 'passed':
                st.success(f"{status_icon} {step['text']}")
            else:
                st.info(f"{status_icon} {step['text']}")

# -----------------------------------------------------------
# PAGE CONFIGURATION
# -----------------------------------------------------------
st.set_page_config("Provar AI - Enhanced Analyzer", layout="wide", page_icon="🚀")

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
    .pdf-step-passed {
        background-color: #d4edda;
        padding: 0.5rem;
        border-radius: 5px;
        margin: 0.2rem 0;
    }
    .pdf-step-failed {
        background-color: #f8d7da;
        padding: 0.5rem;
        border-radius: 5px;
        margin: 0.2rem 0;
        font-weight: bold;
    }
    .screenshot-box {
        border: 2px solid #007bff;
        padding: 1rem;
        border-radius: 10px;
        background-color: #f0f8ff;
    }
    </style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------
# SIDEBAR - MODE SELECTION
# -----------------------------------------------------------
with st.sidebar:
    st.markdown('<div class="main-header">🤖 Provar AI</div>', unsafe_allow_html=True)
    
    st.markdown("---")
    
    # MODE SELECTOR
    analysis_mode = st.radio(
        "📊 Analysis Mode",
        options=["XML Reports", "PDF Reports"],
        help="Choose between XML or PDF report analysis"
    )
    
    st.markdown("---")
    
    # AI Settings (common for both modes)
    st.header("⚙️ Configuration")
    st.subheader("🤖 AI Features")
    use_ai = st.checkbox("Enable AI Analysis", value=False, help="Use Groq AI for intelligent failure analysis")
    
    with st.expander("🎯 Advanced AI Features"):
        enable_batch_analysis = st.checkbox("Batch Pattern Analysis", value=True)
        enable_jira_generation = st.checkbox("Jira Ticket Generation", value=True)
        enable_test_improvements = st.checkbox("Test Improvement Suggestions", value=False)
    
    admin_key = st.text_input("🔐 Admin Key", type="password", help="Required for saving baselines")
    
    st.markdown("---")
    st.caption(f"Version: {APP_VERSION}")
    
    # Reset Button
    if st.button("🔄 Reset All", type="secondary", use_container_width=True):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.success("✅ UI Reset!")
        st.rerun()
    
    # Statistics
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

if analysis_mode == "XML Reports":
    # ========== EXISTING XML ANALYZER ==========
    st.markdown('<div class="main-header">📄 XML Report Analysis and Baseline Tool</div>', unsafe_allow_html=True)
    
    st.markdown("## 📁 Upload XML Reports")
    uploaded_files = st.file_uploader(
        "Choose XML files",
        type=["xml"],
        accept_multiple_files=True,
        key="xml_uploader"
    )
    
    if uploaded_files:
        st.success(f"✅ {len(uploaded_files)} XML file(s) uploaded!")
        
        if 'all_results' not in st.session_state:
            st.session_state.all_results = []
        
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            analyze_all = st.button("🔍 Analyze All XML Reports", type="primary", use_container_width=True)
        
        if analyze_all:
            st.session_state.all_results = []
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for idx, xml_file in enumerate(uploaded_files):
                status_text.text(f"Processing {xml_file.name}... ({idx + 1}/{len(uploaded_files)})")
                
                failures = safe_extract_failures(xml_file, 'xml')
                
                if failures:
                    project_path = failures[0].get("projectCachePath", "")
                    detected_project = detect_project(project_path, xml_file.name)
                    execution_time = failures[0].get("timestamp", "Unknown")
                    
                    normalized = []
                    for f in failures:
                        if f.get("name") != "__NO_FAILURES__":
                            normalized.append({
                                "testcase": f["name"],
                                "testcase_path": f.get("testcase_path", ""),
                                "error": f["error"],
                                "details": f["details"],
                                "source": xml_file.name,
                                "webBrowserType": f.get("webBrowserType", "Unknown"),
                                "projectCachePath": shorten_project_cache_path(f.get("projectCachePath", "")),
                            })
                    
                    baseline_exists = bool(load_baseline(detected_project))
                    if baseline_exists:
                        new_f, existing_f = compare_with_baseline(detected_project, normalized)
                    else:
                        new_f, existing_f = normalized, []
                    
                    st.session_state.all_results.append({
                        'filename': xml_file.name,
                        'project': detected_project,
                        'new_failures': new_f,
                        'existing_failures': existing_f,
                        'new_count': len(new_f),
                        'existing_count': len(existing_f),
                        'total_count': len(normalized),
                        'baseline_exists': baseline_exists,
                        'execution_time': execution_time,
                        'report_type': 'xml'
                    })
                
                progress_bar.progress((idx + 1) / len(uploaded_files))
            
            status_text.text("✅ Analysis complete!")
            progress_bar.empty()
            
            # Update stats
            total_failures = sum(r['total_count'] for r in st.session_state.all_results)
            new_failures = sum(r['new_count'] for r in st.session_state.all_results)
            
            st.session_state.upload_stats = {
                'count': len(uploaded_files),
                'total_failures': total_failures,
                'new_failures': new_failures
            }
        
        # Display XML results (existing code continues...)
        if st.session_state.all_results:
            st.markdown("## 📊 XML Analysis Results")
            
            for idx, result in enumerate(st.session_state.all_results):
                formatted_time = format_execution_time(result.get("execution_time", "Unknown"))
                
                with st.expander(
                    f"📄 {result['filename']} | ⏰ {formatted_time} – Project: {result['project']}",
                    expanded=False
                ):
                    render_summary_card(
                        result['filename'],
                        result['new_count'],
                        result['existing_count'],
                        result['total_count']
                    )
                    
                    st.markdown("---")
                    
                    tab1, tab2, tab3 = st.tabs(["🆕 New Failures", "♻️ Existing Failures", "⚙️ Actions"])
                    
                    with tab1:
                        if result['new_count'] == 0:
                            st.success("✅ No new failures detected!")
                        else:
                            for i, f in enumerate(result['new_failures']):
                                with st.expander(f"🆕 {i+1}. {f['testcase']}", expanded=False):
                                    st.write("**Browser:**", f['webBrowserType'])
                                    st.markdown("**Path:**")
                                    st.code(f['testcase_path'], language="text")
                                    st.error(f"Error: {f['error']}")
                                    st.markdown("**Error Details:**")
                                    st.code(f['details'], language="text")
                                    
                                    # AI Features (existing code)
                                    if use_ai:
                                        with st.spinner("Analyzing..."):
                                            ai_analysis = generate_ai_summary(f['testcase'], f['error'], f['details'])
                                            st.info(ai_analysis)
                    
                    with tab2:
                        if result['existing_count'] == 0:
                            st.info("ℹ️ No existing failures")
                        else:
                            for i, f in enumerate(result['existing_failures']):
                                with st.expander(f"♻️ {i+1}. {f['testcase']}", expanded=False):
                                    st.write("**Browser:**", f['webBrowserType'])
                                    st.markdown("**Path:**")
                                    st.code(f['testcase_path'], language="text")
                                    st.error(f"Error: {f['error']}")
                    
                    with tab3:
                        st.markdown("### 🛠️ Baseline Management")
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            if st.button(f"💾 Save as Baseline", key=f"save_xml_{idx}"):
                                if not admin_key:
                                    st.error("❌ Admin key required!")
                                else:
                                    try:
                                        all_failures = result['new_failures'] + result['existing_failures']
                                        save_baseline(result['project'], all_failures, admin_key)
                                        st.success("✅ Baseline saved!")
                                    except Exception as e:
                                        st.error(f"❌ Error: {str(e)}")
                        
                        with col2:
                            if result['baseline_exists']:
                                st.success("✅ Baseline exists")
                            else:
                                st.warning("⚠️ No baseline found")
    
    else:
        st.info("👆 Upload XML files to begin analysis")

else:
    # ========== NEW PDF ANALYZER ==========
    st.markdown('<div class="main-header">📑 PDF Report Analysis with Visual Steps</div>', unsafe_allow_html=True)
    
    st.markdown("## 📁 Upload PDF Reports")
    st.info("💡 PDF analysis extracts detailed step-by-step information including screenshots and error context")
    
    uploaded_pdf_files = st.file_uploader(
        "Choose PDF files",
        type=["pdf"],
        accept_multiple_files=True,
        key="pdf_uploader",
        help="Upload Provar PDF reports for detailed step analysis"
    )
    
    if uploaded_pdf_files:
        st.success(f"✅ {len(uploaded_pdf_files)} PDF file(s) uploaded!")
        
        if 'pdf_results' not in st.session_state:
            st.session_state.pdf_results = []
        
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            analyze_pdf = st.button("🔍 Analyze All PDF Reports", type="primary", use_container_width=True)
        
        if analyze_pdf:
            st.session_state.pdf_results = []
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for idx, pdf_file in enumerate(uploaded_pdf_files):
                status_text.text(f"Processing {pdf_file.name}... ({idx + 1}/{len(uploaded_pdf_files)})")
                
                failures = safe_extract_failures(pdf_file, 'pdf')
                
                if failures:
                    project_path = failures[0].get("projectCachePath", "")
                    detected_project = detect_project(project_path, pdf_file.name)
                    execution_time = failures[0].get("timestamp", "Unknown")
                    
                    normalized = []
                    for f in failures:
                        if f.get("name") != "__NO_FAILURES__":
                            normalized.append({
                                "testcase": f["name"],
                                "testcase_path": f.get("testcase_path", ""),
                                "error": f["error"],
                                "details": f["details"],
                                "failed_step": f.get("failed_step", ""),
                                "previous_passed_step": f.get("previous_passed_step", ""),
                                "next_step": f.get("next_step", ""),
                                "all_steps": f.get("all_steps", []),
                                "screenshot_available": f.get("screenshot_available", False),
                                "screenshot_info": f.get("screenshot_info", ""),
                                "source": pdf_file.name,
                                "webBrowserType": f.get("webBrowserType", "Unknown"),
                                "projectCachePath": shorten_project_cache_path(f.get("projectCachePath", "")),
                            })
                    
                    # Baseline comparison
                    baseline_exists = bool(load_baseline(detected_project))
                    if baseline_exists:
                        new_f, existing_f = compare_with_baseline(detected_project, normalized)
                    else:
                        new_f, existing_f = normalized, []
                    
                    st.session_state.pdf_results.append({
                        'filename': pdf_file.name,
                        'project': detected_project,
                        'new_failures': new_f,
                        'existing_failures': existing_f,
                        'new_count': len(new_f),
                        'existing_count': len(existing_f),
                        'total_count': len(normalized),
                        'baseline_exists': baseline_exists,
                        'execution_time': execution_time,
                        'report_type': 'pdf'
                    })
                
                progress_bar.progress((idx + 1) / len(uploaded_pdf_files))
            
            status_text.text("✅ PDF Analysis complete!")
            progress_bar.empty()
            
            # Update stats
            total_failures = sum(r['total_count'] for r in st.session_state.pdf_results)
            new_failures = sum(r['new_count'] for r in st.session_state.pdf_results)
            
            st.session_state.upload_stats = {
                'count': len(uploaded_pdf_files),
                'total_failures': total_failures,
                'new_failures': new_failures
            }
        
        # Display PDF results
        if st.session_state.pdf_results:
            st.markdown("## 📊 PDF Analysis Results")
            
            for idx, result in enumerate(st.session_state.pdf_results):
                formatted_time = format_execution_time(result.get("execution_time", "Unknown"))
                
                with st.expander(
                    f"📑 {result['filename']} | ⏰ {formatted_time} – Project: {result['project']}",
                    expanded=False
                ):
                    render_summary_card(
                        result['filename'],
                        result['new_count'],
                        result['existing_count'],
                        result['total_count']
                    )
                    
                    st.markdown("---")
                    
                    tab1, tab2, tab3 = st.tabs(["🆕 New Failures (Detailed)", "♻️ Existing Failures", "⚙️ Actions"])
                    
                    with tab1:
                        if result['new_count'] == 0:
                            st.success("✅ No new failures detected!")
                        else:
                            for i, f in enumerate(result['new_failures']):
                                with st.expander(f"🆕 {i+1}. {f['testcase']}", expanded=False):
                                    # Basic info
                                    col1, col2 = st.columns(2)
                                    with col1:
                                        st.write("**Browser:**", f['webBrowserType'])
                                    with col2:
                                        st.write("**Screenshot:**", "✅ Available" if f.get('screenshot_available') else "❌ Not Available")
                                    
                                    st.markdown("**Test Case Path:**")
                                    st.code(f['testcase_path'], language="text")
                                    
                                    # Error summary
                                    st.error(f"**Error:** {f['error']}")
                                    
                                    st.markdown("---")
                                    
                                    # Step-by-step visualization
                                    st.markdown("### 📋 Test Execution Steps")
                                    
                                    if f.get('all_steps'):
                                        render_pdf_step_visualization(f['all_steps'])
                                    else:
                                        # Fallback to showing available step info
                                        if f.get('previous_passed_step'):
                                            st.success(f"✅ Previous Passed Step: {f['previous_passed_step']}")
                                        
                                        if f.get('failed_step'):
                                            st.error(f"❌ **Failed Step:** {f['failed_step']}")
                                        
                                        if f.get('next_step'):
                                            st.info(f"⏭️ Next Step: {f['next_step']}")
                                    
                                    st.markdown("---")
                                    
                                    # Screenshot section
                                    if f.get('screenshot_available'):
                                        st.markdown('<div class="screenshot-box">', unsafe_allow_html=True)
                                        st.markdown("### 📸 Screenshot Information")
                                        st.info(f['screenshot_info'])
                                        st.markdown('</div>', unsafe_allow_html=True)
                                    
                                    st.markdown("---")
                                    
                                    # Detailed error
                                    with st.expander("🔍 Full Error Details", expanded=False):
                                        st.code(f['details'], language="text")
                                    
                                    # AI Features
                                    if use_ai:
                                        st.markdown("---")
                                        ai_tabs = ["🤖 AI Analysis"]
                                        if enable_jira_generation:
                                            ai_tabs.append("📝 Jira Ticket")
                                        if enable_test_improvements:
                                            ai_tabs.append("💡 Improvements")
                                        
                                        ai_tab_objects = st.tabs(ai_tabs)
                                        
                                        with ai_tab_objects[0]:
                                            with st.spinner("Analyzing with AI..."):
                                                # Include step context in AI analysis
                                                context = f"\nFailed Step: {f.get('failed_step', '')}\nPrevious Step: {f.get('previous_passed_step', '')}"
                                                ai_analysis = generate_ai_summary(f['testcase'], f['error'], f['details'] + context)
                                                st.info(ai_analysis)
                                        
                                        if enable_jira_generation and len(ai_tab_objects) > 1:
                                            with ai_tab_objects[1]:
                                                with st.spinner("Generating Jira ticket..."):
                                                    jira_content = generate_jira_ticket(
                                                        f['testcase'], 
                                                        f['error'], 
                                                        f['details'],
                                                        ai_analysis if 'ai_analysis' in locals() else ""
                                                    )
                                                    st.markdown(jira_content)
                                                    st.download_button(
                                                        "📥 Download Jira Content",
                                                        jira_content,
                                                        file_name=f"jira_{f['testcase'][:30]}.txt",
                                                        key=f"jira_pdf_{idx}_{i}"
                                                    )
                    
                    with tab2:
                        if result['existing_count'] == 0:
                            st.info("ℹ️ No existing failures in baseline")
                        else:
                            st.warning(f"Found {result['existing_count']} known failures")
                            for i, f in enumerate(result['existing_failures']):
                                with st.expander(f"♻️ {i+1}. {f['testcase']}", expanded=False):
                                    st.write("**Browser:**", f['webBrowserType'])
                                    st.markdown("**Path:**")
                                    st.code(f['testcase_path'], language="text")
                                    st.error(f"Error: {f['error']}")
                                    
                                    if f.get('failed_step'):
                                        st.markdown("**Failed Step:**")
                                        st.code(f['failed_step'], language="text")
                    
                    with tab3:
                        st.markdown("### 🛠️ Baseline Management")
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            if st.button(f"💾 Save as Baseline", key=f"save_pdf_{idx}"):
                                if not admin_key:
                                    st.error("❌ Admin key required!")
                                else:
                                    try:
                                        all_failures = result['new_failures'] + result['existing_failures']
                                        save_baseline(result['project'], all_failures, admin_key)
                                        st.success("✅ Baseline saved successfully!")
                                    except Exception as e:
                                        st.error(f"❌ Error: {str(e)}")
                        
                        with col2:
                            if result['baseline_exists']:
                                st.success("✅ Baseline exists")
                            else:
                                st.warning("⚠️ No baseline found")
                        
                        # Export
                        st.markdown("### 📤 Export Options")
                        export_data = pd.DataFrame(result['new_failures'] + result['existing_failures'])
                        
                        if not export_data.empty:
                            csv = export_data.to_csv(index=False)
                            st.download_button(
                                label="📥 Download as CSV",
                                data=csv,
                                file_name=f"{result['filename']}_failures.csv",
                                mime="text/csv",
                                key=f"export_pdf_{idx}"
                            )
    
    else:
        st.info("👆 Upload PDF files to begin detailed step-by-step analysis")
        
        st.markdown("### 🎯 PDF Analysis Features")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown("**📋 Step-by-Step Details**")
            st.write("See exactly which step failed with pass/fail markers")
        with col2:
            st.markdown("**📸 Screenshot Context**")
            st.write("View screenshot references at the point of failure")
        with col3:
            st.markdown("**🔍 Error Context**")
            st.write("Understand the flow with previous and next steps")