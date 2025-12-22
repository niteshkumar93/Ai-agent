import json
import os
from datetime import datetime
from typing import List, Dict, Optional
import requests
import base64

# History directories
PROVAR_HISTORY_DIR = "baselines/provar_history"
API_HISTORY_DIR = "baselines/api_history"
GITHUB_REPO = "niteshkumar93/Ai-agent"

os.makedirs(PROVAR_HISTORY_DIR, exist_ok=True)
os.makedirs(API_HISTORY_DIR, exist_ok=True)


def _get_history_path(project_name: str, report_type: str = "provar") -> str:
    """Get history file path for a project"""
    base_dir = PROVAR_HISTORY_DIR if report_type == "provar" else API_HISTORY_DIR
    return os.path.join(base_dir, f"{project_name}_history.json")


def save_baseline_history(project_name: str, failures: List[Dict], report_type: str = "provar"):
    """
    Save baseline history entry whenever a baseline is updated.
    Tracks: timestamp, failure count, failures list
    """
    history_path = _get_history_path(project_name, report_type)
    
    # Load existing history
    history = []
    if os.path.exists(history_path):
        try:
            with open(history_path, "r", encoding="utf-8") as f:
                history = json.load(f)
        except:
            history = []
    
    # Create new history entry
    new_entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "failure_count": len(failures),
        "failures": failures,
        "report_type": report_type
    }
    
    # Append to history (keep last 50 entries)
    history.append(new_entry)
    history = history[-50:]  # Keep only last 50 entries
    
    # Save updated history
    with open(history_path, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2)
    
    # Commit to GitHub if token available
    _commit_history_to_github(project_name, history, report_type)


def get_baseline_history(project_name: str, report_type: str = "provar", limit: int = 10) -> List[Dict]:
    """
    Get baseline history for a project.
    Returns list of history entries (most recent first)
    """
    history_path = _get_history_path(project_name, report_type)
    
    if not os.path.exists(history_path):
        return []
    
    try:
        with open(history_path, "r", encoding="utf-8") as f:
            history = json.load(f)
            # Return most recent entries first
            return list(reversed(history))[:limit]
    except:
        return []


def get_all_baselines_summary(report_type: str = "provar") -> List[Dict]:
    """
    Get summary of all baselines for a report type.
    Returns: [{"project": name, "failure_count": X, "last_updated": datetime, "total_versions": Y}]
    """
    base_dir = PROVAR_HISTORY_DIR if report_type == "provar" else API_HISTORY_DIR
    
    if not os.path.exists(base_dir):
        return []
    
    summaries = []
    
    for filename in os.listdir(base_dir):
        if filename.endswith("_history.json"):
            project_name = filename.replace("_history.json", "")
            history = get_baseline_history(project_name, report_type, limit=1)
            
            if history:
                latest = history[0]
                
                # Count total versions
                all_history = get_baseline_history(project_name, report_type, limit=1000)
                
                summaries.append({
                    "project": project_name,
                    "failure_count": latest.get("failure_count", 0),
                    "last_updated": latest.get("timestamp", "Unknown"),
                    "total_versions": len(all_history),
                    "report_type": report_type
                })
    
    # Sort by last updated (most recent first)
    summaries.sort(key=lambda x: x["last_updated"], reverse=True)
    
    return summaries


def get_baseline_comparison(project_name: str, report_type: str = "provar") -> Optional[Dict]:
    """
    Compare current baseline with previous version.
    Returns: {"current": {...}, "previous": {...}, "diff": {...}}
    """
    history = get_baseline_history(project_name, report_type, limit=2)
    
    if len(history) < 2:
        return None
    
    current = history[0]
    previous = history[1]
    
    # Calculate differences
    current_count = current.get("failure_count", 0)
    previous_count = previous.get("failure_count", 0)
    
    diff = {
        "failure_count_change": current_count - previous_count,
        "percentage_change": round(((current_count - previous_count) / previous_count * 100), 2) if previous_count > 0 else 0,
        "time_between": _calculate_time_diff(previous.get("timestamp"), current.get("timestamp"))
    }
    
    return {
        "current": current,
        "previous": previous,
        "diff": diff
    }


def delete_baseline_version(project_name: str, version_index: int, report_type: str = "provar", admin_key: str = None):
    """
    Delete a specific version from baseline history.
    Version 0 is the most recent.
    """
    # Verify admin key
    expected = os.getenv("BASELINE_ADMIN_KEY")
    if not expected or admin_key != expected:
        raise PermissionError("❌ Admin key invalid")
    
    history_path = _get_history_path(project_name, report_type)
    
    if not os.path.exists(history_path):
        raise FileNotFoundError(f"No history found for {project_name}")
    
    with open(history_path, "r", encoding="utf-8") as f:
        history = json.load(f)
    
    # Convert to most recent first for user-friendly indexing
    history = list(reversed(history))
    
    if version_index >= len(history):
        raise IndexError(f"Version {version_index} does not exist")
    
    # Remove the version
    del history[version_index]
    
    # Save updated history (convert back to oldest first)
    with open(history_path, "w", encoding="utf-8") as f:
        json.dump(list(reversed(history)), f, indent=2)


def _calculate_time_diff(time1: str, time2: str) -> str:
    """Calculate human-readable time difference"""
    try:
        dt1 = datetime.strptime(time1, "%Y-%m-%d %H:%M:%S")
        dt2 = datetime.strptime(time2, "%Y-%m-%d %H:%M:%S")
        diff = dt2 - dt1
        
        days = diff.days
        hours = diff.seconds // 3600
        minutes = (diff.seconds % 3600) // 60
        
        if days > 0:
            return f"{days} day(s)"
        elif hours > 0:
            return f"{hours} hour(s)"
        else:
            return f"{minutes} minute(s)"
    except:
        return "Unknown"


def _commit_history_to_github(project_name: str, history: List[Dict], report_type: str):
    """Commit history to GitHub (optional)"""
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        return
    
    try:
        base_dir = "provar_history" if report_type == "provar" else "api_history"
        file_path = f"baselines/{base_dir}/{project_name}_history.json"
        url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{file_path}"
        
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json",
        }
        
        # Get current SHA if file exists
        sha = None
        r = requests.get(url, headers=headers)
        if r.status_code == 200:
            sha = r.json().get("sha")
        
        # Prepare content
        content = base64.b64encode(
            json.dumps(history, indent=2).encode("utf-8")
        ).decode("utf-8")
        
        payload = {
            "message": f"Update history for {project_name} ({report_type})",
            "content": content,
        }
        if sha:
            payload["sha"] = sha
        
        requests.put(url, headers=headers, json=payload)
    except:
        pass  # Silent fail for GitHub commits


def export_baseline_report(project_name: str, report_type: str = "provar") -> str:
    """
    Export baseline history as formatted text report.
    Returns formatted string.
    """
    history = get_baseline_history(project_name, report_type, limit=1000)
    
    if not history:
        return f"No history found for {project_name}"
    
    report = f"""
====================================================
BASELINE HISTORY REPORT
====================================================
Project: {project_name}
Report Type: {report_type.upper()}
Total Versions: {len(history)}
Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
====================================================

"""
    
    for i, entry in enumerate(history):
        report += f"""
Version #{i + 1}
-----------------------
Timestamp: {entry.get('timestamp', 'Unknown')}
Failure Count: {entry.get('failure_count', 0)}
"""
        
        if i > 0:
            prev = history[i - 1]
            change = entry.get('failure_count', 0) - prev.get('failure_count', 0)
            report += f"Change from Previous: {change:+d}\n"
        
        report += "\n"
    
    return report