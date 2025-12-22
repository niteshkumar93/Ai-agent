import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
from baseline_history_manager import (
    get_all_baselines_summary,
    get_baseline_history,
    get_baseline_comparison,
    export_baseline_report,
    delete_baseline_version
)


def render_baseline_tracker_dashboard():
    """
    Main dashboard for tracking all baselines across both report types.
    Shows: All baselines, their stats, history, and comparison.
    """
    
    st.markdown("## 📊 Baseline Tracker Dashboard")
    st.markdown("Track all your baselines, view history, and monitor changes over time.")
    
    st.markdown("---")
    
    # Tab selection for report type
    tab1, tab2, tab3 = st.tabs(["🔵 Provar Baselines", "🟢 AutomationAPI Baselines", "📈 Combined Overview"])
    
    with tab1:
        _render_report_type_section("provar")
    
    with tab2:
        _render_report_type_section("automation_api")
    
    with tab3:
        _render_combined_overview()


def _render_report_type_section(report_type: str):
    """Render baseline tracker for a specific report type"""
    
    display_name = "Provar Regression" if report_type == "provar" else "AutomationAPI"
    
    st.markdown(f"### {display_name} Baselines Overview")
    
    # Get all baselines summary
    summaries = get_all_baselines_summary(report_type)
    
    if not summaries:
        st.info(f"ℹ️ No baselines found for {display_name} reports yet.")
        return
    
    # Display summary metrics
    col1, col2, col3, col4 = st.columns(4)
    
    total_baselines = len(summaries)
    total_failures = sum(s["failure_count"] for s in summaries)
    avg_failures = total_failures // total_baselines if total_baselines > 0 else 0
    
    with col1:
        st.metric("📁 Total Baselines", total_baselines)
    with col2:
        st.metric("🔴 Total Failures Tracked", total_failures)
    with col3:
        st.metric("📊 Avg Failures/Baseline", avg_failures)
    with col4:
        # Count baselines updated in last 24 hours
        recent_count = sum(1 for s in summaries if _is_recent(s["last_updated"]))
        st.metric("🕐 Updated Recently", recent_count)
    
    st.markdown("---")
    
    # Create DataFrame for display
    df = pd.DataFrame(summaries)
    df = df[["project", "failure_count", "last_updated", "total_versions"]]
    df.columns = ["Project", "Failures", "Last Updated", "Total Versions"]
    
    st.markdown("### 📋 All Baselines")
    st.dataframe(df, use_container_width=True, height=300)
    
    st.markdown("---")
    
    # Project selector for detailed view
    st.markdown("### 🔍 Detailed View")
    
    project_names = [s["project"] for s in summaries]
    selected_project = st.selectbox(
        f"Select {display_name} Project",
        options=project_names,
        key=f"project_select_{report_type}"
    )
    
    if selected_project:
        _render_project_details(selected_project, report_type)


def _render_project_details(project_name: str, report_type: str):
    """Render detailed view for a specific project baseline"""
    
    st.markdown(f"#### 📂 Project: {project_name}")
    
    # Get history
    history = get_baseline_history(project_name, report_type, limit=20)
    
    if not history:
        st.warning(f"No history found for {project_name}")
        return
    
    # Show comparison with previous version
    comparison = get_baseline_comparison(project_name, report_type)
    
    if comparison:
        st.markdown("##### 📊 Change from Previous Version")
        
        col1, col2, col3 = st.columns(3)
        
        diff = comparison["diff"]
        
        with col1:
            change = diff["failure_count_change"]
            st.metric(
                "Failure Count Change",
                f"{change:+d}",
                delta=f"{change:+d}",
                delta_color="inverse"
            )
        
        with col2:
            pct = diff["percentage_change"]
            st.metric(
                "Percentage Change",
                f"{pct:+.1f}%",
                delta=f"{pct:+.1f}%",
                delta_color="inverse"
            )
        
        with col3:
            st.metric(
                "Time Since Last Update",
                diff["time_between"]
            )
    
    st.markdown("---")
    
    # History Timeline Chart
    st.markdown("##### 📈 History Timeline")
    
    # Prepare data for chart
    timestamps = [h["timestamp"] for h in reversed(history)]
    failure_counts = [h["failure_count"] for h in reversed(history)]
    
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=timestamps,
        y=failure_counts,
        mode='lines+markers',
        name='Failure Count',
        line=dict(color='#FF4B4B', width=3),
        marker=dict(size=10)
    ))
    
    fig.update_layout(
        title=f"Baseline History for {project_name}",
        xaxis_title="Update Time",
        yaxis_title="Failure Count",
        height=400,
        hovermode='x unified'
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    st.markdown("---")
    
    # History Table
    st.markdown("##### 📜 Version History")
    
    # Create expandable sections for each version
    for i, entry in enumerate(history):
        timestamp = entry.get("timestamp", "Unknown")
        count = entry.get("failure_count", 0)
        
        # Determine change indicator
        if i < len(history) - 1:
            prev_count = history[i + 1]["failure_count"]
            change = count - prev_count
            change_text = f" ({change:+d})" if change != 0 else " (no change)"
        else:
            change_text = " (initial)"
        
        with st.expander(
            f"Version #{i + 1} • {timestamp} • {count} failures{change_text}",
            expanded=(i == 0)  # Expand only the latest version
        ):
            st.markdown(f"**Timestamp:** {timestamp}")
            st.markdown(f"**Failure Count:** {count}")
            
            # Show failures if expanded
            failures = entry.get("failures", [])
            
            if failures:
                st.markdown("**Failures in this version:**")
                
                # Create a simple table
                failure_data = []
                for f in failures[:10]:  # Show first 10
                    if report_type == "provar":
                        failure_data.append({
                            "Test Case": f.get("testcase", "Unknown"),
                            "Error": f.get("error", "")[:50] + "..."
                        })
                    else:
                        failure_data.append({
                            "Test Case": f.get("test_name", "Unknown"),
                            "Spec": f.get("spec_file", "Unknown"),
                            "Error": f.get("error_summary", "")[:50] + "..."
                        })
                
                st.dataframe(pd.DataFrame(failure_data), use_container_width=True)
                
                if len(failures) > 10:
                    st.caption(f"... and {len(failures) - 10} more failures")
            else:
                st.info("No failures in this version (clean baseline)")
    
    st.markdown("---")
    
    # Export options
    st.markdown("##### 📤 Export Options")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button(f"📥 Export History Report", key=f"export_{project_name}_{report_type}"):
            report = export_baseline_report(project_name, report_type)
            st.download_button(
                label="💾 Download Report",
                data=report,
                file_name=f"{project_name}_baseline_history.txt",
                mime="text/plain",
                key=f"download_{project_name}_{report_type}"
            )
            st.success("✅ Report generated!")
    
    with col2:
        # Delete version option (admin only)
        with st.expander("🗑️ Delete Version (Admin)"):
            version_to_delete = st.number_input(
                "Version number to delete (1 = latest)",
                min_value=1,
                max_value=len(history),
                value=1,
                key=f"delete_version_{project_name}_{report_type}"
            )
            
            admin_key = st.text_input(
                "Admin Key",
                type="password",
                key=f"delete_admin_{project_name}_{report_type}"
            )
            
            if st.button("Delete Version", key=f"delete_btn_{project_name}_{report_type}"):
                if admin_key:
                    try:
                        delete_baseline_version(
                            project_name,
                            version_to_delete - 1,  # Convert to 0-indexed
                            report_type,
                            admin_key
                        )
                        st.success(f"✅ Version #{version_to_delete} deleted!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error: {str(e)}")
                else:
                    st.error("❌ Admin key required")


def _render_combined_overview():
    """Render combined overview of both report types"""
    
    st.markdown("### 🌐 Combined Overview")
    
    provar_summaries = get_all_baselines_summary("provar")
    api_summaries = get_all_baselines_summary("automation_api")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 🔵 Provar Statistics")
        if provar_summaries:
            total_provar = len(provar_summaries)
            total_provar_failures = sum(s["failure_count"] for s in provar_summaries)
            
            st.metric("Total Projects", total_provar)
            st.metric("Total Failures", total_provar_failures)
            
            # Recent updates
            recent_provar = [s for s in provar_summaries if _is_recent(s["last_updated"])]
            st.metric("Recent Updates (24h)", len(recent_provar))
        else:
            st.info("No Provar baselines yet")
    
    with col2:
        st.markdown("#### 🟢 AutomationAPI Statistics")
        if api_summaries:
            total_api = len(api_summaries)
            total_api_failures = sum(s["failure_count"] for s in api_summaries)
            
            st.metric("Total Projects", total_api)
            st.metric("Total Failures", total_api_failures)
            
            # Recent updates
            recent_api = [s for s in api_summaries if _is_recent(s["last_updated"])]
            st.metric("Recent Updates (24h)", len(recent_api))
        else:
            st.info("No AutomationAPI baselines yet")
    
    st.markdown("---")
    
    # Combined chart
    if provar_summaries or api_summaries:
        st.markdown("#### 📊 Baseline Distribution")
        
        fig = go.Figure()
        
        if provar_summaries:
            provar_projects = [s["project"] for s in provar_summaries[:10]]
            provar_counts = [s["failure_count"] for s in provar_summaries[:10]]
            
            fig.add_trace(go.Bar(
                name='Provar',
                x=provar_projects,
                y=provar_counts,
                marker_color='#1f77b4'
            ))
        
        if api_summaries:
            api_projects = [s["project"] for s in api_summaries[:10]]
            api_counts = [s["failure_count"] for s in api_summaries[:10]]
            
            fig.add_trace(go.Bar(
                name='AutomationAPI',
                x=api_projects,
                y=api_counts,
                marker_color='#2ca02c'
            ))
        
        fig.update_layout(
            title="Failure Count by Project (Top 10 per type)",
            xaxis_title="Project",
            yaxis_title="Failure Count",
            barmode='group',
            height=500
        )
        
        st.plotly_chart(fig, use_container_width=True)


def _is_recent(timestamp_str: str, hours: int = 24) -> bool:
    """Check if timestamp is within last N hours"""
    try:
        ts = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
        diff = datetime.now() - ts
        return diff.total_seconds() < (hours * 3600)
    except:
        return False