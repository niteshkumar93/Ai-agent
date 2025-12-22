import json
import os
from typing import List, Dict

# Separate baseline directory for AutomationAPI
BASELINE_DIR = "baselines/automation_api"
os.makedirs(BASELINE_DIR, exist_ok=True)

def _get_baseline_path(project_name: str) -> str:
    """Get baseline file path for AutomationAPI project"""
    return os.path.join(BASELINE_DIR, f"{project_name}.json")


def baseline_exists(project_name: str) -> bool:
    """Check if baseline exists for this AutomationAPI project"""
    return os.path.exists(_get_baseline_path(project_name))


def load_baseline(project_name: str) -> List[Dict]:
    """Load baseline for AutomationAPI project"""
    path = _get_baseline_path(project_name)
    
    if not os.path.exists(path):
        return []
    
    if os.path.getsize(path) == 0:
        return []
    
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        return []


def save_baseline(project_name: str, failures: List[Dict], admin_key: str):
    """Save baseline for AutomationAPI project (admin only)"""
    expected = os.getenv("BASELINE_ADMIN_KEY")
    if not expected:
        raise RuntimeError("❌ BASELINE_ADMIN_KEY not configured")
    
    if admin_key != expected:
        raise PermissionError("❌ Admin key invalid")
    
    # Clean up failures before saving (remove internal flags)
    clean_failures = []
    for f in failures:
        if not f.get("_no_failures"):
            clean_failure = {
                "project": f.get("project"),
                "spec_file": f.get("spec_file"),
                "test_name": f.get("test_name"),
                "error_summary": f.get("error_summary"),
                "is_skipped": f.get("is_skipped", False)
            }
            clean_failures.append(clean_failure)
    
    path = _get_baseline_path(project_name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(clean_failures, f, indent=2)


def compare_with_baseline(project_name: str, current_failures: List[Dict]):
    """
    Compare current failures with baseline.
    Returns: (new_failures, existing_failures)
    """
    baseline = load_baseline(project_name)
    
    # Create signature for baseline failures (spec + test_name + error)
    baseline_sigs = {
        f"{b.get('spec_file')}|{b.get('test_name')}|{b.get('error_summary', '')}"
        for b in baseline
    }
    
    new_failures = []
    existing_failures = []
    
    for failure in current_failures:
        # Skip metadata-only records
        if failure.get("_no_failures"):
            continue
        
        sig = f"{failure.get('spec_file')}|{failure.get('test_name')}|{failure.get('error_summary', '')}"
        
        if sig in baseline_sigs:
            existing_failures.append(failure)
        else:
            new_failures.append(failure)
    
    return new_failures, existing_failures


def list_available_baselines() -> List[str]:
    """List all available AutomationAPI baselines"""
    if not os.path.exists(BASELINE_DIR):
        return []
    
    return [
        f.replace(".json", "")
        for f in os.listdir(BASELINE_DIR)
        if f.endswith(".json")
    ]