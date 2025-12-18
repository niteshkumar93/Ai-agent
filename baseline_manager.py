# baseline_manager.py

import json
import os
import base64
import requests
from typing import List, Dict

# -----------------------------------------------------------
# CONFIG
# -----------------------------------------------------------
BASELINE_DIR = "baselines"
GITHUB_REPO = "niteshkumar93/Ai-agent"

# -----------------------------------------------------------
# BASELINE LIST (KNOWN PROJECTS)
# -----------------------------------------------------------
KNOWN_PROJECTS = [
    "VF_Lightning_Windows",
    "Regmain-Flexi",
    "Date_Time",
    "CPQ_Classic",
    "CPQ_Lightning",
    "QAM_Lightning",
    "QAM_Classic",
    "Internationalization_pipeline",
    "Lightning_Console_LogonAs",
    "DynamicForm",
    "Classic_Console_LogonAS",
    "LWC_Pipeline",
    "Regmain_LS_Windows",
    "Regmain_LC_Windows",
    "Regmain-VF",
    "FSL",
    "HYBRID_AUTOMATION_Pipeline",
]

# -----------------------------------------------------------
# HELPERS
# -----------------------------------------------------------
def _get_baseline_path(project_name: str) -> str:
    os.makedirs(BASELINE_DIR, exist_ok=True)
    return os.path.join(BASELINE_DIR, f"{project_name}.json")

def list_available_baselines() -> List[str]:
    if not os.path.exists(BASELINE_DIR):
        return []
    return [
        f.replace(".json", "")
        for f in os.listdir(BASELINE_DIR)
        if f.endswith(".json")
    ]

def baseline_exists(project_name: str) -> bool:
    return os.path.exists(_get_baseline_path(project_name))

# -----------------------------------------------------------
# LOAD BASELINE (SAFE)
# -----------------------------------------------------------
def load_baseline(project_name: str) -> List[Dict]:
    path = _get_baseline_path(project_name)
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return []

# -----------------------------------------------------------
# SAVE BASELINE (ADMIN ONLY)
# -----------------------------------------------------------
def save_baseline(project_name: str, failures: List[Dict], admin_key: str):
    expected = os.getenv("BASELINE_ADMIN_KEY")
    if admin_key != expected:
        raise PermissionError("❌ Admin key invalid")

    path = _get_baseline_path(project_name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(failures, f, indent=2)

    _commit_to_github(project_name, failures)

# -----------------------------------------------------------
# GITHUB COMMIT (SAFE)
# -----------------------------------------------------------
def _commit_to_github(project_name: str, failures: List[Dict]):
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        return

    file_path = f"{BASELINE_DIR}/{project_name}.json"
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{file_path}"

    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
    }

    sha = None
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        sha = r.json().get("sha")

    content = base64.b64encode(
        json.dumps(failures, indent=2).encode("utf-8")
    ).decode("utf-8")

    payload = {
        "message": f"Update baseline for {project_name}",
        "content": content,
    }
    if sha:
        payload["sha"] = sha

    requests.put(url, headers=headers, json=payload)

# -----------------------------------------------------------
# COMPARE
# -----------------------------------------------------------
def compare_with_baseline(project_name: str, current_failures: List[Dict]):
    baseline = load_baseline(project_name)
    baseline_keys = {f"{b['testcase']}|{b['error']}" for b in baseline}

    new_failures, existing_failures = [], []
    for f in current_failures:
        key = f"{f['testcase']}|{f['error']}"
        (existing_failures if key in baseline_keys else new_failures).append(f)

    return new_failures, existing_failures

# -----------------------------------------------------------
# HISTORY
# -----------------------------------------------------------
def get_baseline_history(project_name: str):
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        return []

    url = f"https://api.github.com/repos/{GITHUB_REPO}/commits"
    params = {"path": f"{BASELINE_DIR}/{project_name}.json"}
    headers = {"Authorization": f"token {token}"}

    r = requests.get(url, headers=headers, params=params)
    return r.json() if r.status_code == 200 else []
