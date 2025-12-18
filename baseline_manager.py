import json
import os
from datetime import datetime

BASELINE_DIR = "baselines"
os.makedirs(BASELINE_DIR, exist_ok=True)

def failure_id(f):
    return f"{f['testcase_path']}::{f['testcase']}"

def save_baseline(project_name, failures):
    path = os.path.join(BASELINE_DIR, f"{project_name}.json")
    data = {
        "project": project_name,
        "created_at": datetime.now().strftime("%Y-%m-%d"),
        "failures": [failure_id(f) for f in failures]
    }
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

def load_baseline(project_name):
    path = os.path.join(BASELINE_DIR, f"{project_name}.json")
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)

def compare_with_baseline(project_name, failures):
    baseline = load_baseline(project_name)
    if not baseline:
        return failures, []   # no baseline yet

    baseline_set = set(baseline["failures"])
    current_set = {failure_id(f) for f in failures}

    new_failures = [
        f for f in failures if failure_id(f) not in baseline_set
    ]

    existing_failures = [
        f for f in failures if failure_id(f) in baseline_set
    ]

    return new_failures, existing_failures
