# baseline_manager.py
import json
import os
from typing import List, Dict

BASELINE_DIR = "baselines"


def _get_baseline_path(project_name: str) -> str:
    os.makedirs(BASELINE_DIR, exist_ok=True)
    return os.path.join(BASELINE_DIR, f"{project_name}.json")


def load_baseline(project_name: str) -> List[Dict]:
    path = _get_baseline_path(project_name)

    # ✅ If file does not exist → empty baseline
    if not os.path.exists(path):
        return []

    # ✅ If file exists but is empty → empty baseline
    if os.path.getsize(path) == 0:
        return []

    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        # ✅ If file is corrupted → ignore safely
        return []


def save_baseline(project_name: str, failures: List[Dict]):
    path = _get_baseline_path(project_name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(failures, f, indent=2)


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

    # Use testcase + error as unique signature
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
