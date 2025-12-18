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
# -----------------------------------------------------------
# 🔁 ROLLBACK BASELINE (ADMIN ONLY)
# -----------------------------------------------------------
def rollback_baseline(project_name: str, commit_sha: str, admin_key: str):
    ADMIN_KEY = os.getenv("BASELINE_ADMIN_KEY")

    if not ADMIN_KEY:
        raise RuntimeError("❌ BASELINE_ADMIN_KEY not configured")

    if admin_key != ADMIN_KEY:
        raise PermissionError("❌ Invalid admin key")

    token = os.getenv("GITHUB_TOKEN")
    if not token:
        raise RuntimeError("❌ GITHUB_TOKEN not found")

    file_path = f"{BASELINE_DIR}/{project_name}.json"
    repo_url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{file_path}"

    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json"
    }

    # 1️⃣ Get file content from selected commit
    commit_url = f"https://api.github.com/repos/{GITHUB_REPO}/git/commits/{commit_sha}"
    commit_resp = requests.get(commit_url, headers=headers)

    if commit_resp.status_code != 200:
        raise RuntimeError("❌ Unable to fetch commit data")

    tree_sha = commit_resp.json()["tree"]["sha"]

    tree_url = f"https://api.github.com/repos/{GITHUB_REPO}/git/trees/{tree_sha}?recursive=1"
    tree_resp = requests.get(tree_url, headers=headers)

    target_blob = None
    for item in tree_resp.json()["tree"]:
        if item["path"] == file_path:
            target_blob = item["sha"]
            break

    if not target_blob:
        raise RuntimeError("❌ Baseline file not found in selected commit")

    # 2️⃣ Fetch blob content
    blob_url = f"https://api.github.com/repos/{GITHUB_REPO}/git/blobs/{target_blob}"
    blob_resp = requests.get(blob_url, headers=headers)

    content = base64.b64decode(
        blob_resp.json()["content"]
    ).decode("utf-8")

    # 3️⃣ Save locally
    local_path = _get_baseline_path(project_name)
    with open(local_path, "w", encoding="utf-8") as f:
        f.write(content)

    # 4️⃣ Commit rollback version
    encoded = base64.b64encode(content.encode()).decode()

    current = requests.get(repo_url, headers=headers).json()
    sha = current.get("sha")

    payload = {
        "message": f"Rollback baseline for {project_name}",
        "content": encoded,
        "sha": sha
    }

    requests.put(repo_url, headers=headers, json=payload)
