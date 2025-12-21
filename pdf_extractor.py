# pdf_extractor.py
from typing import List, Dict, Optional
import re

# --------------------------------------------------
# MAIN ENTRY POINT
# --------------------------------------------------
def extract_pdf_failures(pdf_file) -> List[Dict]:
    """
    Extract failures from Provar PDF reports.
    Uses icon + text parsing (✓ ⊛ ⊗ ✗ ⊙)
    """

    # Lazy import (CRITICAL for Streamlit safety)
    try:
        import pdfplumber
    except ImportError:
        return create_no_failure_record(
            message="pdfplumber not installed. PDF analysis unavailable."
        )

    pdf_file.seek(0)

    try:
        with pdfplumber.open(pdf_file) as pdf:
            if not pdf.pages:
                return create_no_failure_record("PDF has no pages")

            full_text = ""
            for page in pdf.pages:
                page_text = page.extract_text() or ""
                full_text += page_text + "\n"

    except Exception as e:
        return create_no_failure_record(f"PDF read error: {str(e)}")

    if not full_text.strip():
        return create_no_failure_record("Could not extract text from PDF")

    metadata = extract_metadata(full_text)
    testcase_sections = find_testcase_sections_with_outcomes(full_text)

    failed_sections = [
        (tc_name, section)
        for tc_name, section, outcome in testcase_sections
        if outcome == "failed"
    ]

    if not failed_sections:
        return create_no_failure_record(
            metadata=metadata,
            is_clean_run=True
        )

    failures = []
    for tc_name, section in failed_sections:
        details = extract_failure_details(tc_name, section, metadata)
        if details:
            failures.append(details)

    return failures if failures else create_no_failure_record(
        metadata=metadata,
        is_clean_run=True
    )


# --------------------------------------------------
# NO FAILURE RECORD
# --------------------------------------------------
def create_no_failure_record(
    message: str = "",
    metadata: Dict = None,
    is_clean_run: bool = False
) -> List[Dict]:

    metadata = metadata or {}

    return [{
        "name": "__NO_FAILURES__",
        "testcase_path": "",
        "error": "" if is_clean_run else message,
        "details": "",
        "failed_step": "",
        "previous_passed_step": "",
        "next_step": "",
        "all_steps": [],
        "screenshot_available": False,
        "screenshot_info": "",
        "webBrowserType": metadata.get("browser", "Unknown"),
        "projectCachePath": metadata.get("project", ""),
        "timestamp": metadata.get("time", "Unknown"),
        "_no_failures": True,
    }]


# --------------------------------------------------
# METADATA EXTRACTION
# --------------------------------------------------
def extract_metadata(text: str) -> Dict:
    metadata = {}

    time_match = re.search(
        r'Started\s+(\d{2}\s+\w{3}\s+\d{4},\s+\d{2}:\d{2}:\d{2})',
        text
    )
    metadata["time"] = time_match.group(1) if time_match else "Unknown"

    project_match = re.search(
        r'(VF_Lightning_Windows|HYBRID_AUTOMATION_Pipeline|AutomationAPI_Flexi5|CPQ_\w+|QAM_\w+|Regmain[\w_-]+)',
        text
    )
    metadata["project"] = project_match.group(1) if project_match else ""

    browser_match = re.search(r'(Chrome|Firefox|Safari|Edge)', text)
    metadata["browser"] = browser_match.group(1) if browser_match else "Unknown"

    return metadata


# --------------------------------------------------
# TESTCASE SECTION DETECTION
# --------------------------------------------------
def find_testcase_sections_with_outcomes(text: str) -> List[tuple]:
    testcases = []
    pattern = r'([A-Za-z0-9_]+\.testcase)'
    matches = list(re.finditer(pattern, text))

    for i, match in enumerate(matches):
        name = match.group(1)
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        section = text[start:end]

        outcome = extract_outcome_status(section)
        testcases.append((name, section, outcome))

    return testcases


def extract_outcome_status(section: str) -> str:
    if re.search(r'(⊗|✗|failed)', section, re.IGNORECASE):
        return "failed"
    if re.search(r'(⊛|✓|passed|successful)', section, re.IGNORECASE):
        return "successful"
    if re.search(r'(⊘|skipped)', section, re.IGNORECASE):
        return "skipped"
    return "unknown"


# --------------------------------------------------
# FAILURE DETAILS
# --------------------------------------------------
def extract_failure_details(tc_name: str, section: str, metadata: Dict) -> Optional[Dict]:
    steps = extract_steps_from_output(section)

    failed_step = ""
    previous_step = ""
    next_step = ""

    for i, step in enumerate(steps):
        if step["status"] == "failed":
            failed_step = step["text"]
            previous_step = steps[i - 1]["text"] if i > 0 else ""
            next_step = steps[i + 1]["text"] if i + 1 < len(steps) else ""
            break

    return {
        "name": tc_name,
        "testcase_path": tc_name,
        "error": extract_error_message(section),
        "details": extract_error_details(section),
        "failed_step": failed_step,
        "previous_passed_step": previous_step,
        "next_step": next_step,
        "all_steps": steps,
        "screenshot_available": bool(re.search(r'screenshot|image', section, re.I)),
        "screenshot_info": "Screenshot available in report",
        "webBrowserType": metadata.get("browser", "Unknown"),
        "projectCachePath": metadata.get("project", ""),
        "timestamp": metadata.get("time", "Unknown"),
    }


# --------------------------------------------------
# ERROR EXTRACTION
# --------------------------------------------------
def extract_error_message(section: str) -> str:
    match = re.search(r'Error:\s*(.+)', section)
    return match.group(1).strip() if match else "Execution failed"


def extract_error_details(section: str) -> str:
    lines = section.splitlines()
    error_lines = [l for l in lines if "Exception" in l or "Error" in l]
    return "\n".join(error_lines[:10]) if error_lines else ""


# --------------------------------------------------
# STEP EXTRACTION
# --------------------------------------------------
def extract_steps_from_output(section: str) -> List[Dict]:
    steps = []

    pattern = r'([⊛⊗⊙✓✗])\s*(.+)'
    for idx, match in enumerate(re.finditer(pattern, section)):
        symbol, text = match.groups()

        if symbol in ("⊗", "✗"):
            status = "failed"
        elif symbol in ("⊛", "✓"):
            status = "passed"
        elif symbol == "⊙":
            status = "info"
        else:
            status = "unknown"

        steps.append({
            "index": idx,
            "text": text.strip(),
            "status": status
        })

    return steps
