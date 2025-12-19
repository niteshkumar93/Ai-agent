import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import io
import os

from xml_extractor import extract_failed_tests
from ai_reasoner import generate_ai_summary
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
        st.metric("Known Failures", existing_count)
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
st.set_page_config("Provar AI - Multi-XML Analyzer", layout="wide", page_icon="🚀")

# Custom CSS for better UI
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
    </style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-header">🚀 Provar AI - Multi-XML Analyzer</div>', unsafe_allow_html=True)

# -----------------------------------------------------------
# SIDEBAR CONFIGURATION
# -----------------------------------------------------------
with st.sidebar:
    st.header("⚙️ Configuration")
    use_ai = st.checkbox("🤖 Use AI Analysis", value=False, help="Enable AI-powered failure analysis")
    admin_key = st.text_input("🔐 Admin Key", type="password", help="Required for saving baselines")
    
    st.markdown("---")
    st.markdown("### 📊 Upload Statistics")
    if 'upload_stats' in st.session_state:
        st.info(f"**Files Uploaded:** {st.session_state.upload_stats.get('count', 0)}")
        st.info(f"**Total Failures:** {st.session_state.upload_stats.get('total_failures', 0)}")
        st.info(f"**New Failures:** {st.session_state.upload_stats.get('new_failures', 0)}")

# -----------------------------------------------------------
# FILE UPLOAD SECTION
# -----------------------------------------------------------
st.markdown("## 📁 Upload XML Reports")
st.markdown("Upload multiple JUnit XML reports for simultaneous analysis")

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
        analyze_all = st.button("🔍 Analyze All Reports", type="primary", use_container_width=True)
    
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
    
    # -----------------------------------------------------------
    # DISPLAY RESULTS
    # -----------------------------------------------------------
    if st.session_state.all_results:
        
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
                                
                                if use_ai:
                                    with st.expander("🤖 AI Analysis"):
                                        ai_analysis = generate_ai_summary(f['testcase'], f['error'], f['details'])
                                        st.info(ai_analysis)
                                
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
    st.info("👆 Upload one or more XML files to begin analysis")
    
    st.markdown("### 🎯 Features")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("**📊 Multi-File Analysis**")
        st.write("Upload and analyze multiple XML reports simultaneously")
    with col2:
        st.markdown("**🤖 AI-Powered Insights**")
        st.write("Get intelligent failure analysis and suggestions")
    with col3:
        st.markdown("**📈 Baseline Tracking**")
        st.write("Compare results against historical baselines")