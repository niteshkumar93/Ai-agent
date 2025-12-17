import os
import json

BASELINE_DIR = "data/baseline"
os.makedirs(BASELINE_DIR, exist_ok=True)

BASELINE_FILE = f"{BASELINE_DIR}/baseline.json"

def load_baseline():
    if os.path.exists(BASELINE_FILE):
        with open(BASELINE_FILE, "r") as f:
            return json.load(f)
    return {}

def save_baseline(data):
    with open(BASELINE_FILE, "w") as f:
        json.dump(data, f, indent=4)
