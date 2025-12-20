import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import io
import os
APP_VERSION = "2.0.2"  # Increment this with each deployment
st.sidebar.caption(f"Version: {APP_VERSION}")
from xml_extractor import extract_failed_tests
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

APP_VERSION = "2.1.0"  # Enhanced with AI features

# -----------------------------------------------------------
# HELPERS
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
    return KNOWN_PROJECTS[0]

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
            'File': result['filename'][:30] + '...' if len(result['filename']) > 30 else result['filename'],
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
st.set_page_config("Provar AI - Enhanced XML Analyzer", layout="wide", page_icon="🚀")


# iOS Glassmorphism Design
st.markdown("""
    <style>
    /* Animated gradient background */
    .stApp {
        background: linear-gradient(135deg, 
            #667eea 0%, 
            #764ba2 25%, 
            #f093fb 50%, 
            #4facfe 75%, 
            #00f2fe 100%
        );
        background-size: 400% 400%;
        animation: gradientShift 15s ease infinite;
    }
    
    @keyframes gradientShift {
        0% { background-position: 0% 50%; }
        50% { background-position: 100% 50%; }
        100% { background-position: 0% 50%; }
    }
    
    /* Glass effect for all cards */
    .element-container, .stMarkdown, .stExpander, div[data-testid="stMetric"] {
        background: rgba(255, 255, 255, 0.15) !important;
        backdrop-filter: blur(20px) saturate(180%) !important;
        -webkit-backdrop-filter: blur(20px) saturate(180%) !important;
        border: 1px solid rgba(255, 255, 255, 0.3) !important;
        border-radius: 20px !important;
        box-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.15) !important;
        padding: 15px !important;
        margin: 10px 0 !important;
    }
    
    /* Sidebar glass effect */
    section[data-testid="stSidebar"] {
        background: rgba(255, 255, 255, 0.1) !important;
        backdrop-filter: blur(40px) saturate(180%) !important;
        -webkit-backdrop-filter: blur(40px) saturate(180%) !important;
        border-right: 1px solid rgba(255, 255, 255, 0.2) !important;
    }
    
    section[data-testid="stSidebar"] > div {
        background: transparent !important;
    }
    
    /* iOS-style buttons */
    .stButton > button {
        background: rgba(255, 255, 255, 0.2) !important;
        backdrop-filter: blur(20px) !important;
        border: 1px solid rgba(255, 255, 255, 0.3) !important;
        border-radius: 15px !important;
        color: white !important;
        font-weight: 600 !important;
        padding: 12px 24px !important;
        transition: all 0.3s ease !important;
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.1) !important;
    }
    
    .stButton > button:hover {
        background: rgba(255, 255, 255, 0.3) !important;
        transform: translateY(-2px) !important;
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.15) !important;
    }
    
    .stButton > button[kind="primary"] {
        background: rgba(0, 122, 255, 0.7) !important;
        border: 1px solid rgba(255, 255, 255, 0.4) !important;
    }
    
    .stButton > button[kind="primary"]:hover {
        background: rgba(0, 122, 255, 0.85) !important;
    }
    
    /* Header styling */
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: white !important;
        text-align: center;
        padding: 1rem 0;
        text-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
    }
    
    /* Section divider */
    .section-divider {
        border-top: 2px solid rgba(255, 255, 255, 0.3);
        margin: 2rem 0;
    }
    
    /* AI feature box with glass */
    .ai-feature-box {
        background: rgba(102, 126, 234, 0.3) !important;
        backdrop-filter: blur(20px) !important;
        border: 1px solid rgba(255, 255, 255, 0.3) !important;
        padding: 1rem;
        border-radius: 15px;
        color: white;
        margin: 1rem 0;
        box-shadow: 0 8px 32px rgba(102, 126, 234, 0.2);
    }
    
    /* Text styling */
    h1, h2, h3, h4, h5, h6 {
        color: white !important;
        text-shadow: 0 2px 8px rgba(0, 0, 0, 0.1) !important;
    }
    
    p, span, label, div {
        color: rgba(255, 255, 255, 0.95) !important;
    }
    
    /* File uploader */
    section[data-testid="stFileUploader"] {
        background: rgba(255, 255, 255, 0.1) !important;
        backdrop-filter: blur(20px) !important;
        border: 2px dashed rgba(255, 255, 255, 0.4) !important;
        border-radius: 20px !important;
        padding: 30px !important;
    }
    
    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        background: rgba(255, 255, 255, 0.1) !important;
        backdrop-filter: blur(20px) !important;
        border-radius: 15px !important;
        padding: 5px !important;
    }
    
    .stTabs [data-baseweb="tab"] {
        color: rgba(255, 255, 255, 0.8) !important;
        border-radius: 10px !important;
    }
    
    .stTabs [aria-selected="true"] {
        background: rgba(255, 255, 255, 0.25) !important;
        backdrop-filter: blur(10px) !important;
        color: white !important;
        font-weight: 600 !important;
    }
    
    /* Alerts with glass */
    .stSuccess {
        background: rgba(52, 199, 89, 0.2) !important;
        backdrop-filter: blur(20px) !important;
        border: 1px solid rgba(52, 199, 89, 0.4) !important;
        border-radius: 15px !important;
        color: white !important;
    }
    
    .stError {
        background: rgba(255, 59, 48, 0.2) !important;
        backdrop-filter: blur(20px) !important;
        border: 1px solid rgba(255, 59, 48, 0.4) !important;
        border-radius: 15px !important;
        color: white !important;
    }
    
    .stWarning {
        background: rgba(255, 204, 0, 0.2) !important;
        backdrop-filter: blur(20px) !important;
        border: 1px solid rgba(255, 204, 0, 0.4) !important;
        border-radius: 15px !important;
        color: white !important;
    }
    
    .stInfo {
        background: rgba(0, 122, 255, 0.2) !important;
        backdrop-filter: blur(20px) !important;
        border: 1px solid rgba(0, 122, 255, 0.4) !important;
        border-radius: 15px !important;
        color: white !important;
    }
    
    /* Smooth scrollbar */
    ::-webkit-scrollbar {
        width: 8px;
        height: 8px;
    }
    
    ::-webkit-scrollbar-track {
        background: rgba(255, 255, 255, 0.05);
        border-radius: 10px;
    }
    
    ::-webkit-scrollbar-thumb {
        background: rgba(255, 255, 255, 0.3);
        border-radius: 10px;
    }
    
    ::-webkit-scrollbar-thumb:hover {
        background: rgba(255, 255, 255, 0.4);
    }
    
    /* Input fields */
    .stTextInput > div > div > input {
        background: rgba(255, 255, 255, 0.15) !important;
        backdrop-filter: blur(20px) !important;
        border: 1px solid rgba(255, 255, 255, 0.3) !important;
        border-radius: 12px !important;
        color: white !important;
    }
    
    /* Checkbox */
    .stCheckbox {
        background: rgba(255, 255, 255, 0.1) !important;
        backdrop-filter: blur(10px) !important;
        border-radius: 10px !important;
        padding: 8px 12px !important;
    }
    </style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-header">🚀 Provar AI - Enhanced XML Analyzer</div>', unsafe_allow_html=True)

# -----------------------------------------------------------
# SIDEBAR CONFIGURATION
# -----------------------------------------------------------
with st.sidebar:
    st.header("⚙️ Configuration")
    
    # AI Settings
    st.subheader("🤖 AI Features")
    use_ai = st.checkbox("Enable AI Analysis", value=True, help="Use Groq AI for intelligent failure analysis")
    
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
        for key in ['all_results', 'upload_stats', 'batch_analysis']:
            if key in st.session_state:
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
# FILE UPLOAD SECTION
# -----------------------------------------------------------
st.markdown("## 📁 Upload XML Reports")
st.markdown("Upload multiple JUnit XML reports for simultaneous AI-powered analysis")

uploaded_files = st.file_uploader(
    "Choose XML files",
    type=["xml"],
    accept_multiple_files=True,
    help="Select one or more XML files to analyze"
)

if uploaded_files:
    st.success(f"✅ {len(uploaded_files)} file(s) uploaded successfully!")
    
    # Initialize session state for results
    if 'all_results' not in st.session_state:
        st.session_state.all_results = []
    
    # -----------------------------------------------------------
    # GLOBAL ANALYSIS BUTTON
    # -----------------------------------------------------------
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        analyze_all = st.button("🔍 Analyze All Reports with AI", type="primary", use_container_width=True)
    
    if analyze_all:
        st.session_state.all_results = []
        
        # Progress tracking
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for idx, xml_file in enumerate(uploaded_files):
            status_text.text(f"Processing {xml_file.name}... ({idx + 1}/{len(uploaded_files)})")
            
            failures = safe_extract_failures(xml_file)
            
            if failures:
                project_path = failures[0].get("projectCachePath", "")
                detected_project = detect_project(project_path, xml_file.name)
                
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
                
                # Compare with baseline
                baseline_exists = bool(load_baseline(detected_project))
                if baseline_exists:
                    new_f, existing_f = compare_with_baseline(detected_project, normalized)
                else:
                    new_f, existing_f = normalized, []
                
                # Store results
                st.session_state.all_results.append({
                    'filename': xml_file.name,
                    'project': detected_project,
                    'new_failures': new_f,
                    'existing_failures': existing_f,
                    'new_count': len(new_f),
                    'existing_count': len(existing_f),
                    'total_count': len(normalized),
                    'baseline_exists': baseline_exists
                })
            
            progress_bar.progress((idx + 1) / len(uploaded_files))
        
        status_text.text("✅ Analysis complete!")
        progress_bar.empty()
        
        # Update upload statistics
        total_failures = sum(r['total_count'] for r in st.session_state.all_results)
        new_failures = sum(r['new_count'] for r in st.session_state.all_results)
        
        st.session_state.upload_stats = {
            'count': len(uploaded_files),
            'total_failures': total_failures,
            'new_failures': new_failures
        }
        
        # Generate batch analysis if enabled
        if use_ai and enable_batch_analysis:
            with st.spinner("🧠 Running batch pattern analysis..."):
                all_failures = []
                for result in st.session_state.all_results:
                    all_failures.extend(result['new_failures'])
                
                if all_failures:
                    st.session_state.batch_analysis = generate_batch_analysis(all_failures)
    
    # -----------------------------------------------------------
    # DISPLAY RESULTS
    # -----------------------------------------------------------
    if st.session_state.all_results:
        
        st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
        
        # -----------------------------------------------------------
        # 🆕 BATCH PATTERN ANALYSIS
        # -----------------------------------------------------------
        if 'batch_analysis' in st.session_state and st.session_state.batch_analysis:
            st.markdown('<div class="ai-feature-box">', unsafe_allow_html=True)
            st.markdown("## 🧠 AI Batch Pattern Analysis")
            st.markdown("AI has analyzed all failures together to identify patterns and priorities.")
            st.markdown('</div>', unsafe_allow_html=True)
            
            st.markdown(st.session_state.batch_analysis)
            st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
        
        st.markdown("## 📊 Overall Summary")
        
        # Overall statistics
        total_new = sum(r['new_count'] for r in st.session_state.all_results)
        total_existing = sum(r['existing_count'] for r in st.session_state.all_results)
        total_all = sum(r['total_count'] for r in st.session_state.all_results)
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("📄 Total Files", len(st.session_state.all_results))
        with col2:
            st.metric("🆕 Total New Failures", total_new, delta=f"+{total_new}" if total_new > 0 else "0", delta_color="inverse")
        with col3:
            st.metric("♻️ Total Existing Failures", total_existing)
        with col4:
            st.metric("📈 Total All Failures", total_all)
        
        # Comparison chart
        render_comparison_chart(st.session_state.all_results)
        
        st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
        st.markdown("## 📋 Detailed Results by File")
        
        # Individual file results
        for idx, result in enumerate(st.session_state.all_results):
            with st.expander(f"📄 {result['filename']} - Project: {result['project']}", expanded=False):
                
                # Summary card for this file
                render_summary_card(
                    result['filename'],
                    result['new_count'],
                    result['existing_count'],
                    result['total_count']
                )
                
                st.markdown("---")
                
                # Tabs for different failure types
                tab1, tab2, tab3 = st.tabs(["🆕 New Failures", "♻️ Existing Failures", "⚙️ Actions"])
                
                with tab1:
                    if result['new_count'] == 0:
                        st.success("✅ No new failures detected!")
                    else:
                        for i, f in enumerate(result['new_failures']):
                            with st.container():
                                st.markdown(f"**{i+1}. {f['testcase']}**")
                                col1, col2 = st.columns([1, 3])
                                with col1:
                                    st.write("**Browser:**", f['webBrowserType'])
                                    st.write("**Path:**", f['testcase_path'][:50] + "..." if len(f['testcase_path']) > 50 else f['testcase_path'])
                                with col2:
                                    st.error(f"**Error:** {f['error']}")
                                    with st.expander("View Details"):
                                        st.code(f['details'], language="text")
                                
                                # AI Features
                                if use_ai:
                                    ai_tabs = []
                                    if True:  # Basic analysis always available
                                        ai_tabs.append("🤖 AI Analysis")
                                    if enable_jira_generation:
                                        ai_tabs.append("📝 Jira Ticket")
                                    if enable_test_improvements:
                                        ai_tabs.append("💡 Improvements")
                                    
                                    if len(ai_tabs) > 0:
                                        ai_tab_objects = st.tabs(ai_tabs)
                                        
                                        # Basic AI Analysis
                                        with ai_tab_objects[0]:
                                            with st.spinner("Analyzing..."):
                                                ai_analysis = generate_ai_summary(f['testcase'], f['error'], f['details'])
                                                st.info(ai_analysis)
                                        
                                        # Jira Ticket Generation
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
                                                        key=f"jira_{idx}_{i}"
                                                    )
                                        
                                        # Test Improvements
                                        if enable_test_improvements and len(ai_tab_objects) > 2:
                                            with ai_tab_objects[-1]:
                                                with st.spinner("Generating improvement suggestions..."):
                                                    improvements = suggest_test_improvements(
                                                        f['testcase'],
                                                        f['error'],
                                                        f['details']
                                                    )
                                                    st.success(improvements)
                                
                                st.markdown("---")
                
                with tab2:
                    if result['existing_count'] == 0:
                        st.info("ℹ️ No existing failures found in baseline")
                    else:
                        st.warning(f"Found {result['existing_count']} known failures")
                        for i, f in enumerate(result['existing_failures']):
                            with st.expander(f"{i+1}. {f['testcase']}"):
                                st.write("**Error:**", f['error'])
                                st.write("**Browser:**", f['webBrowserType'])
                
                with tab3:
                    st.markdown("### 🛠️ Baseline Management")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button(f"💾 Save as Baseline", key=f"save_{idx}"):
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
                            st.success("✅ Baseline exists for this project")
                        else:
                            st.warning("⚠️ No baseline found")
                    
                    # Export options
                    st.markdown("### 📤 Export Options")
                    export_data = pd.DataFrame(result['new_failures'] + result['existing_failures'])
                    
                    if not export_data.empty:
                        csv = export_data.to_csv(index=False)
                        st.download_button(
                            label="📥 Download as CSV",
                            data=csv,
                            file_name=f"{result['filename']}_failures.csv",
                            mime="text/csv",
                            key=f"export_{idx}"
                        )

else:
    # Welcome message when no files uploaded
    st.info("👆 Upload one or more XML files to begin AI-powered analysis")
    
    st.markdown("### 🎯 Features")
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
    
    st.markdown("---")
    
    st.markdown("### 🆕 New AI Features")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("**🧠 Batch Pattern Analysis**")
        st.write("AI identifies common patterns across all failures")
    with col2:
        st.markdown("**📝 Jira Auto-Generation**")
        st.write("Create ready-to-use Jira tickets instantly")
    with col3:
        st.markdown("**💡 Test Improvements**")
        st.write("Get suggestions to make tests more stable")