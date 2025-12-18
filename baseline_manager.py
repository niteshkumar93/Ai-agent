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
GITHUB_REPO = "niteshkumar93/Ai-agent"  # 🔁 change if repo name differs

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

    # File not present
    if not os.path.exists(path):
        return []

    # Empty file
    if os.path.getsize(path) == 0:
        return []

    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        # Corrupted JSON → ignore safely
        return []

# -----------------------------------------------------------
# SAVE + AUTO‑COMMIT BASELINE
# -----------------------------------------------------------
def save_baseline(project_name: str, failures: List[Dict]):
    path = _get_baseline_path(project_name)

    # Save locally
    with open(path, "w", encoding="utf-8") as f:
        json.dump(failures, f, indent=2)

    # Auto‑commit to GitHub
    _commit_to_github(project_name, failures)

# -----------------------------------------------------------
# GITHUB COMMIT LOGIC
# -----------------------------------------------------------
def _commit_to_github(project_name: str, failures: List[Dict]):
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        raise RuntimeError("❌ GITHUB_TOKEN not found")

    file_path = f"{BASELINE_DIR}/{project_name}.json"
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{file_path}"

    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json"
    }

    # Check if file already exists (for SHA)
    r = requests.get(url, headers=headers)
    sha = r.json().get("sha") if r.status_code == 200 else None

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
# BASELINE COMPARISON
# -----------------------------------------------------------
def compare_with_baseline(
    project_name: str,
    current_failures: List[Dict]
):
    """
    Returns:
      new_failures: failures NOT present in baseline
      existing_failures: failures already known
    """
    baseline = load_baseline(project_name)

    # testcase + error = unique signature
    baseline_keys = {
        f"{b['testcase']}|{b['error']}"
        for b in baseline
    }

    new_failures = []
    existing_failures = []

    for f in current_failures:
        key = f"{f['testcase']}|{f['error']}"
        if key in baseline_keys:
            existing_failures.append(f)
        else:
            new_failures.append(f)

    return new_failures, existing_failures

# -----------------------------------------------------------
# BASELINE HISTORY (GITHUB COMMITS)
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
    if r.status_code != 200:
        return []

    return r.json()
