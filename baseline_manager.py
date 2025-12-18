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
# PATH HELPERS
# -----------------------------------------------------------
def _get_baseline_path(project_name: str) -> str:
    os.makedirs(BASELINE_DIR, exist_ok=True)
    return os.path.join(BASELINE_DIR, f"{project_name}.json")

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
    expected_key = os.getenv("BASELINE_ADMIN_KEY")

    if not expected_key or admin_key != expected_key:
        raise PermissionError("❌ Admin key invalid. Baseline write blocked.")

    path = _get_baseline_path(project_name)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(failures, f, indent=2)

    _commit_to_github(project_name, failures)

# -----------------------------------------------------------
# GITHUB COMMIT
# -----------------------------------------------------------
def _commit_to_github(project_name: str, failures: List[Dict]):
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        print("⚠️ GITHUB_TOKEN missing → skipping GitHub commit")
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
# COMPARE BASELINE
# -----------------------------------------------------------
def compare_with_baseline(project_name: str, current_failures: List[Dict]):
    baseline = load_baseline(project_name)

    baseline_keys = {
        f"{b['testcase']}|{b['error']}" for b in baseline
    }

    new_failures, existing_failures = [], []

    for f in current_failures:
        key = f"{f['testcase']}|{f['error']}"
        (existing_failures if key in baseline_keys else new_failures).append(f)

    return new_failures, existing_failures

# -----------------------------------------------------------
# BASELINE HISTORY (COMMITS)
# -----------------------------------------------------------
def get_baseline_history(project_name: str):
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        return []

    file_path = f"{BASELINE_DIR}/{project_name}.json"
    url = f"https://api.github.com/repos/{GITHUB_REPO}/commits"

    headers = {"Authorization": f"token {token}"}
    params = {"path": file_path}

    r = requests.get(url, headers=headers, params=params)
    return r.json() if r.status_code == 200 else []

# -----------------------------------------------------------
# ROLLBACK BASELINE
# -----------------------------------------------------------
def rollback_baseline(project_name: str, commit_sha: str, admin_key: str):
    expected_key = os.getenv("BASELINE_ADMIN_KEY")
    if admin_key != expected_key:
        raise PermissionError("❌ Admin key invalid")

    token = os.getenv("GITHUB_TOKEN")
    if not token:
        raise RuntimeError("GITHUB_TOKEN missing")

    file_path = f"{BASELINE_DIR}/{project_name}.json"
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{file_path}"

    headers = {"Authorization": f"token {token}"}
    params = {"ref": commit_sha}

    r = requests.get(url, headers=headers, params=params)
    content = base64.b64decode(r.json()["content"]).decode("utf-8")

    with open(_get_baseline_path(project_name), "w", encoding="utf-8") as f:
        f.write(content)
