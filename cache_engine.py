import os
import hashlib
import json

CACHE_DIR = "data/cache"
os.makedirs(CACHE_DIR, exist_ok=True)

def get_pdf_hash(pdf_path):
    with open(pdf_path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()

def load_cache(pdf_hash):
    path = f"{CACHE_DIR}/{pdf_hash}.json"
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    return None

def save_cache(pdf_hash, data):
    path = f"{CACHE_DIR}/{pdf_hash}.json"
    with open(path, "w") as f:
        json.dump(data, f, indent=4)
