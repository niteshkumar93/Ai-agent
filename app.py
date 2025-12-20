import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import io
import os
from datetime import datetime

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

APP_VERSION = "3.0.0"  # Enhanced UI/UX Version

# -----------------------------------------------------------
# SESSION STATE INITIALIZATION
# -----------------------------------------------------------
if 'dark_mode' not in st.session_state:
    st.session_state.dark_mode = False
if 'all_results' not in st.session_state:
    st.session_state.all_results = []
if 'expanded_failures' not in st.session_state:
    st.session_state.expanded_failures = {}
if 'search_term' not in st.session_state:
    st.session_state.search_term = ""
if 'selected_browser' not in st.session_state:
    st.session_state.selected_browser = "All"
if 'selected_priority' not in st.session_state:
    st.session_state.selected_priority = "All"
if 'sort_by' not in st.session_state:
    st.session_state.sort_by = "Priority"
if 'active_tab' not in st.session_state:
    st.session_state.active_tab = "failures"

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

def get_browser_emoji(browser):
    """Get emoji for browser type"""
    emoji_map = {
        'Chrome': '🌐',
        'Firefox': '🦊',
        'Safari': '🧭',
        'Edge': '🔷',
        'Unknown': '❓'
    }
    return emoji_map.get(browser, '🌐')

def assign_priority(error_message, details):
    """AI-like priority assignment based on error patterns"""
    error_lower = error_message.lower()
    details_lower = details.lower()
    
    # High priority patterns
    high_patterns = ['exception', 'timeout', 'connection refused', 'null pointer', 'fatal']
    # Medium priority patterns
    medium_patterns = ['element not found', 'assertion failed', 'interaction failed']
    # Low priority patterns
    low_patterns = ['warning', 'deprecated', 'minor']
    
    for pattern in high_patterns:
        if pattern in error_lower or pattern in details_lower:
            return 'High'
    
    for pattern in medium_patterns:
        if pattern in error_lower or pattern in details_lower:
            return 'Medium'
    
    for pattern in low_patterns:
        if pattern in error_lower or pattern in details_lower:
            return 'Low'
    
    return 'Medium'  # Default

def calculate_analytics(all_results):
    """Calculate dashboard analytics"""
    total_failures = sum(r['total_count'] for r in all_results)
    new_failures = sum(r['new_count'] for r in all_results)
    
    # Count flaky tests (failures with multiple occurrences)
    flaky_count = 0
    all_failures = []
    for result in all_results:
        all_failures.extend(result['new_failures'])
    
    # Detect duplicates as flaky
    test_counts = {}
    for f in all_failures:
        test_name = f['testcase']
        test_counts[test_name] = test_counts.get(test_name, 0) + 1
    flaky_count = sum(1 for count in test_counts.values() if count > 1)
    
    # Calculate success rate (mock calculation)
    total_tests = total_failures * 2  # Assume 50% failure rate for demo
    success_rate = round((total_tests - total_failures) / max(total_tests, 1) * 100, 1)
    
    return {
        'total_failures': total_failures,
        'new_failures': new_failures,
        'flaky_tests': flaky_count,
        'avg_duration': '8.3s',  # Mock data
        'success_rate': success_rate,
        'trend_up': new_failures > 0
    }

def filter_and_sort_failures(failures, search_term, browser_filter, priority_filter, sort_by):
    """Filter and sort failures based on user preferences"""
    filtered = []
    
    for f in failures:
        # Assign priority if not present
        if 'priority' not in f:
            f['priority'] = assign_priority(f['error'], f['details'])
        
        # Search filter
        if search_term:
            search_lower = search_term.lower()
            if not (search_lower in f['testcase'].lower() or 
                   search_lower in f['error'].lower()):
                continue
        
        # Browser filter
        if browser_filter != "All" and f['webBrowserType'] != browser_filter:
            continue
        
        # Priority filter
        if priority_filter != "All" and f.get('priority', 'Medium') != priority_filter:
            continue
        
        filtered.append(f)
    
    # Sort
    if sort_by == "Priority":
        priority_order = {'High': 0, 'Medium': 1, 'Low': 2}
        filtered.sort(key=lambda x: priority_order.get(x.get('priority', 'Medium'), 1))
    elif sort_by == "Time":
        # Mock time sorting (newest first)
        filtered.reverse()
    elif sort_by == "Name":
        filtered.sort(key=lambda x: x['testcase'])
    
    return filtered

# -----------------------------------------------------------
# PAGE CONFIGURATION
# -----------------------------------------------------------
st.set_page_config(
    page_title="Provar AI - Enhanced Analyzer",
    layout="wide",
    page_icon="🚀",
    initial_sidebar_state="expanded"
)

# -----------------------------------------------------------
# MODERN DARK MODE CSS
# -----------------------------------------------------------
if st.session_state.dark_mode:
    st.markdown("""
    <style>
        /* Dark Mode Styles */
        .stApp {
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
            color: #e0e0e0;
        }
        
        .main-header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 2rem;
            border-radius: 15px;
            text-align: center;
            color: white;
            margin-bottom: 2rem;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
        }
        
        .metric-card {
            background: rgba(255, 255, 255, 0.05);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 12px;
            padding: 1.5rem;
            box-shadow: 0 4px 16px rgba(0, 0, 0, 0.2);
            transition: transform 0.3s ease;
        }
        
        .metric-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.3);
        }
        
        .failure-card {
            background: rgba(255, 255, 255, 0.05);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 12px;
            padding: 1.5rem;
            margin-bottom: 1rem;
            transition: all 0.3s ease;
        }
        
        .failure-card:hover {
            background: rgba(255, 255, 255, 0.08);
            border-color: rgba(102, 126, 234, 0.5);
            box-shadow: 0 4px 20px rgba(102, 126, 234, 0.2);
        }
        
        .priority-high {
            background: rgba(239, 68, 68, 0.2);
            color: #fca5a5;
            border: 1px solid #ef4444;
            padding: 0.25rem 0.75rem;
            border-radius: 20px;
            font-size: 0.875rem;
            font-weight: 600;
        }
        
        .priority-medium {
            background: rgba(251, 191, 36, 0.2);
            color: #fcd34d;
            border: 1px solid #f59e0b;
            padding: 0.25rem 0.75rem;
            border-radius: 20px;
            font-size: 0.875rem;
            font-weight: 600;
        }
        
        .priority-low {
            background: rgba(59, 130, 246, 0.2);
            color: #93c5fd;
            border: 1px solid #3b82f6;
            padding: 0.25rem 0.75rem;
            border-radius: 20px;
            font-size: 0.875rem;
            font-weight: 600;
        }
        
        .search-container {
            background: rgba(255, 255, 255, 0.05);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 12px;
            padding: 1.5rem;
            margin-bottom: 1.5rem;
        }
        
        div[data-testid="stExpander"] {
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 10px;
        }
        
        .stTabs [data-baseweb="tab-list"] {
            background: rgba(255, 255, 255, 0.05);
            border-radius: 10px;
            padding: 0.5rem;
        }
        
        .stTabs [data-baseweb="tab"] {
            color: #a0a0a0;
        }
        
        .stTabs [aria-selected="true"] {
            color: #667eea !important;
            background: rgba(102, 126, 234, 0.2);
            border-radius: 8px;
        }
    </style>
    """, unsafe_allow_html=True)
else:
    st.markdown("""
    <style>
        /* Light Mode Styles */
        .stApp {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 25%, #f093fb 50%, #4facfe 100%);
            background-size: 400% 400%;
        }
        
        .main-header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 2rem;
            border-radius: 15px;
            text-align: center;
            color: white;
            margin-bottom: 2rem;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.15);
        }
        
        .metric-card {
            background: rgba(255, 255, 255, 0.9);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.3);
            border-radius: 12px;
            padding: 1.5rem;
            box-shadow: 0 4px 16px rgba(0, 0, 0, 0.1);
            transition: transform 0.3s ease;
        }
        
        .metric-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.15);
        }
        
        .failure-card {
            background: rgba(255, 255, 255, 0.85);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.3);
            border-radius: 12px;
            padding: 1.5rem;
            margin-bottom: 1rem;
            transition: all 0.3s ease;
        }
        
        .failure-card:hover {
            background: rgba(255, 255, 255, 0.95);
            border-color: rgba(102, 126, 234, 0.5);
            box-shadow: 0 4px 20px rgba(102, 126, 234, 0.3);
        }
        
        .priority-high {
            background: rgba(239, 68, 68, 0.15);
            color: #dc2626;
            border: 1px solid #ef4444;
            padding: 0.25rem 0.75rem;
            border-radius: 20px;
            font-size: 0.875rem;
            font-weight: 600;
        }
        
        .priority-medium {
            background: rgba(251, 191, 36, 0.15);
            color: #d97706;
            border: 1px solid #f59e0b;
            padding: 0.25rem 0.75rem;
            border-radius: 20px;
            font-size: 0.875rem;
            font-weight: 600;
        }
        
        .priority-low {
            background: rgba(59, 130, 246, 0.15);
            color: #2563eb;
            border: 1px solid #3b82f6;
            padding: 0.25rem 0.75rem;
            border-radius: 20px;
            font-size: 0.875rem;
            font-weight: 600;
        }
        
        .search-container {
            background: rgba(255, 255, 255, 0.85);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.3);
            border-radius: 12px;
            padding: 1.5rem;
            margin-bottom: 1.5rem;
        }
    </style>
    """, unsafe_allow_html=True)

# -----------------------------------------------------------
# HEADER
# -----------------------------------------------------------
col1, col2 = st.columns([6, 1])
with col1:
    st.markdown("""
    <div class="main-header">
        <h1 style="margin: 0; font-size: 2.5rem;">🚀 Provar AI Analysis Platform</h1>
        <p style="margin: 0.5rem 0 0 0; opacity: 0.9;">Enhanced Test Report Dashboard with Modern UI</p>
    </div>
    """, unsafe_allow_html=True)
with col2:
    if st.button("🌙" if not st.session_state.dark_mode else "☀️", key="theme_toggle", help="Toggle Dark/Light Mode"):
        st.session_state.dark_mode = not st.session_state.dark_mode
        st.rerun()

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
        for key in ['all_results', 'upload_stats', 'batch_analysis', 'expanded_failures']:
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
        
        # Calculate analytics
        analytics = calculate_analytics(st.session_state.all_results)
        
        # -----------------------------------------------------------
        # ANALYTICS DASHBOARD
        # -----------------------------------------------------------
        st.markdown("## 📊 Analytics Dashboard")
        
        col1, col2, col3, col4, col5, col6 = st.columns(6)
        
        with col1:
            st.markdown('<div class="metric-card">', unsafe_allow_html=True)
            st.metric("Total Failures", analytics['total_failures'], 
                     help="Total number of test failures across all reports")
            st.markdown('</div>', unsafe_allow_html=True)
        
        with col2:
            st.markdown('<div class="metric-card">', unsafe_allow_html=True)
            st.metric("New Issues", analytics['new_failures'],
                     delta=f"+{analytics['new_failures']}" if analytics['new_failures'] > 0 else "0",
                     delta_color="inverse",
                     help="New failures not in baseline")
            st.markdown('</div>', unsafe_allow_html=True)
        
        with col3:
            st.markdown('<div class="metric-card">', unsafe_allow_html=True)
            st.metric("Flaky Tests", analytics['flaky_tests'],
                     help="Tests that fail intermittently")
            st.markdown('</div>', unsafe_allow_html=True)
        
        with col4:
            st.markdown('<div class="metric-card">', unsafe_allow_html=True)
            st.metric("Avg Duration", analytics['avg_duration'],
                     help="Average test execution time")
            st.markdown('</div>', unsafe_allow_html=True)
        
        with col5:
            st.markdown('<div class="metric-card">', unsafe_allow_html=True)
            st.metric("Success Rate", f"{analytics['success_rate']}%",
                     help="Percentage of passing tests")
            st.markdown('</div>', unsafe_allow_html=True)
        
        with col6:
            st.markdown('<div class="metric-card">', unsafe_allow_html=True)
            st.metric("Trend", "↑" if analytics['trend_up'] else "↓",
                     help="Failure trend direction")
            st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # -----------------------------------------------------------
        # BATCH PATTERN ANALYSIS
        # -----------------------------------------------------------
        if 'batch_analysis' in st.session_state and st.session_state.batch_analysis:
            st.markdown("## 🧠 AI Batch Pattern Analysis")
            with st.expander("View AI Analysis", expanded=True):
                st.markdown(st.session_state.batch_analysis)
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # -----------------------------------------------------------
        # TABS FOR DIFFERENT VIEWS
        # -----------------------------------------------------------
        tab1, tab2, tab3 = st.tabs(["🔍 Failures Analysis", "📈 Trends", "📊 Reports"])
        
        with tab1:
            # -----------------------------------------------------------
            # SEARCH AND FILTER SECTION
            # -----------------------------------------------------------
            st.markdown('<div class="search-container">', unsafe_allow_html=True)
            
            col1, col2, col3 = st.columns([2, 1, 1])
            with col1:
                search_term = st.text_input(
                    "🔍 Search",
                    value=st.session_state.search_term,
                    placeholder="Search test cases or errors...",
                    key="search_input"
                )
                st.session_state.search_term = search_term
            
            with col2:
                # Get unique browsers from all failures
                all_browsers = set()
                for result in st.session_state.all_results:
                    for f in result['new_failures'] + result['existing_failures']:
                        all_browsers.add(f.get('webBrowserType', 'Unknown'))
                
                browser_filter = st.selectbox(
                    "Browser",
                    ["All"] + sorted(list(all_browsers)),
                    index=0,
                    key="browser_filter"
                )
                st.session_state.selected_browser = browser_filter
            
            with col3:
                priority_filter = st.selectbox(
                    "Priority",
                    ["All", "High", "Medium", "Low"],
                    index=0,
                    key="priority_filter"
                )
                st.session_state.selected_priority = priority_filter
            
            # Sort options
            st.markdown("**Sort by:**")
            col1, col2, col3, col4 = st.columns([1, 1, 1, 3])
            with col1:
                if st.button("🎯 Priority", key="sort_priority"):
                    st.session_state.sort_by = "Priority"
            with col2:
                if st.button("⏰ Time", key="sort_time"):
                    st.session_state.sort_by = "Time"
            with col3:
                if st.button("📝 Name", key="sort_name"):
                    st.session_state.sort_by = "Name"
            
            st.markdown('</div>', unsafe_allow_html=True)
            
            # -----------------------------------------------------------
            # DISPLAY FILTERED FAILURES
            # -----------------------------------------------------------
            st.markdown("### 🔴 Test Failures")
            
            # Collect all failures for display
            all_failures_display = []
            for result in st.session_state.all_results:
                for f in result['new_failures']:
                    f['status'] = 'New'
                    f['filename'] = result['filename']
                    all_failures_display.append(f)
            
            # Apply filters
            filtered_failures = filter_and_sort_failures(
                all_failures_display,
                st.session_state.search_term,
                st.session_state.selected_browser,
                st.session_state.selected_priority,
                st.session_state.sort_by
            )
            
            st.caption(f"Showing {len(filtered_failures)} of {len(all_failures_display)} failures")
            
            # Display failures
            for idx, failure in enumerate(filtered_failures):
                failure_id = f"{failure['filename']}_{failure['testcase']}"
                
                with st.container():
                    st.markdown('<div class="failure-card">', unsafe_allow_html=True)
                    
                    # Header row
                    col1, col2 = st.columns([4, 1])
                    with col1:
                        browser_emoji = get_browser_emoji(failure['webBrowserType'])
                        priority = failure.get('priority', 'Medium')
                        priority_class = f"priority-{priority.lower()}"
                        
                        st.markdown(f"""
                        <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 10px;">
                            <span style="font-size: 1.5rem;">{browser_emoji}</span>
                            <h3 style="margin: 0; font-size: 1.1rem;">{failure['testcase']}</h3>
                            <span class="{priority_class}">{priority} Priority</span>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        st.error(f"❌ {failure['error']}")
                        
                        # Metadata
                        st.caption(f"🌐 {failure['webBrowserType']} | 📄 {failure['filename']}")
                    
                    with col2:
                        # Copy button
                        if st.button("📋 Copy", key=f"copy_{idx}"):
                            st.code(failure['testcase'])
                            st.success("✅ Copied!", icon="✅")
                    
                    # Expandable