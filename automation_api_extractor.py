import xml.etree.ElementTree as ET
from typing import List, Dict
import re
def extract_spec_from_testsuite(testsuite_node) -> str:
    """
    Resolve the real Provar Spec file by scanning ALL failures
    inside a testsuite. Handles cases where Spec appears only
    in later failures.
    """

    spec_pattern = re.compile(r'([A-Za-z0-9_]+Spec)')

    # 1️⃣ Scan all failure text + messages
    for testcase in testsuite_node.findall("testcase"):
        failure = testcase.find("failure")
        if failure is None:
            continue

        combined_text = (
            (failure.attrib.get("message", "") or "") + " " +
            (failure.text or "")
        )

        match = spec_pattern.search(combined_text)
        if match:
            return match.group(1)

    # 2️⃣ Fallback: classname ending with Spec
    for testcase in testsuite_node.findall("testcase"):
        classname = testcase.attrib.get("classname", "")
        if classname.endswith("Spec"):
            return classname

    # 3️⃣ Absolute fallback (flow name)
    return testsuite_node.attrib.get("name", "Unknown_Spec")

def extract_actual_spec_name(testcase_node) -> str:
    """
    Extract real Provar Spec file name PER TESTCASE.
    This fixes multi-spec collapsing.
    """

    # 1️⃣ classname itself is the spec (best & most reliable)
    classname = testcase_node.attrib.get("classname", "")
    if classname.endswith("Spec"):
        return classname

    # 2️⃣ Look inside failure text of THIS testcase only
    failure = testcase_node.find("failure")
    if failure is not None:
        failure_text = (failure.text or "") + " " + (failure.attrib.get("message", ""))
        match = re.search(r'([A-Za-z0-9_]+Spec)', failure_text)
        if match:
            return match.group(1)

    # 3️⃣ Look inside testcase name
    test_name = testcase_node.attrib.get("name", "")
    match = re.search(r'([A-Za-z0-9_]+Spec)', test_name)
    if match:
        return match.group(1)

    # 4️⃣ Fallback (flow name)
    return classname or "Unknown_Spec"


def extract_project_name(xml_file) -> str:
    """
    Extract project name from workspace path in XML.
    Example: D:\Jenkins\workspace\AutomationAPI_Flexi5 -> AutomationAPI_Flexi5
    """
    xml_file.seek(0)
    tree = ET.parse(xml_file)
    root = tree.getroot()
    # Try to find workspace path in failure messages
    for testcase in root.findall(".//testcase"):
        failure = testcase.find("failure")
        if failure is not None:
            failure_text = failure.text or ""
            # Look for Jenkins workspace path
            match = re.search(r'workspace[/\\]([^/\\]+)', failure_text)
            if match:
                return match.group(1)
    
    return "Unknown_Project"


def is_skipped_failure(error_message: str) -> bool:
    """
    Check if failure is due to previous step failure (should be marked as skipped/yellow)
    """
    skip_indicators = [
        "Skipping the test case because the previous step has failed",
        "previous step has failed with error"
    ]
    return any(indicator in error_message for indicator in skip_indicators)

def clean_error_message(raw_message: str) -> tuple:
    """
    Extract clean error summary and full details from failure message.
    Returns: (short_summary, full_details)
    """
    if not raw_message:
        return ("Unknown error", "")
    
    # Extract the main error message (first line usually)
    lines = raw_message.split('\n')
    summary = lines[0].strip() if lines else raw_message[:200]
    
    # Clean up common prefixes
    summary = summary.replace("Failed: ", "")
    summary = summary.replace("Error: ", "")
    
    # Truncate if too long
    if len(summary) > 150:
        summary = summary[:150] + "..."
    
    return (summary, raw_message)


def extract_automation_api_failures(xml_file) -> List[Dict]:
    """
    Extract failures from AutomationAPI XML report.
    Returns list of failures grouped by spec file.
    """
    xml_file.seek(0)
    tree = ET.parse(xml_file)
    root = tree.getroot()
    # Extract project name
    project_name = extract_project_name(xml_file)
    xml_file.seek(0)  # Reset for re-parsing
    
    # Get timestamp
    timestamp = root.attrib.get("timestamp", "Unknown")
    for suite in root.findall("testsuite"):
        if suite.attrib.get("timestamp"):
            timestamp = suite.attrib.get("timestamp")
            break
    
    # Get total stats
    total_tests = int(root.attrib.get("tests", 0))
    total_failures = int(root.attrib.get("failures", 0))
    
    failures = []
    
    # Parse all testsuites
    for testsuite in root.findall(".//testsuite"):
        suite_name = testsuite.attrib.get("name", "Unknown")
        # ✅ Resolve correct spec ONCE per testsuite
        resolved_spec_name = extract_spec_from_testsuite(testsuite)

        # Skip non-test suites (like "Launch Provar", "Screen Recording", etc.)
        if suite_name in ["Launch Provar", "Screen Recording", "Close Provar"]:
            continue
        
        # Parse testcases in this suite
        for testcase in testsuite.findall("testcase"):
            failure = testcase.find("failure")
            
            if failure is not None:
                spec_name = resolved_spec_name
                classname = testcase.attrib.get("classname", "Unknown")
                test_name = testcase.attrib.get("name", "Unknown Test")
                test_time = testcase.attrib.get("time", "0")
                
                # Get failure details
                failure_type = failure.attrib.get("type", "exception")
                raw_message = failure.attrib.get("message", "")
                full_details = failure.text or ""
                
                # Determine if this is a skipped failure
                is_skipped = is_skipped_failure(raw_message) or is_skipped_failure(full_details)
                
                # Clean error message
                error_summary, error_details = clean_error_message(raw_message)
                
                failures.append({
                    "project": project_name,
                    "spec_file": spec_name,
                    "test_name": test_name,
                    "classname": classname,
                    "error_summary": error_summary,
                    "error_details": error_details,
                    "full_stack_trace": full_details,
                    "failure_type": failure_type,
                    "execution_time": test_time,
                    "is_skipped": is_skipped,
                    "timestamp": timestamp,
                    "source": xml_file.name if hasattr(xml_file, 'name') else "uploaded_file.xml"
                })
    
    # If no failures found, return metadata-only record
    if not failures:
        return [{
            "project": project_name,
            "spec_file": "__NO_FAILURES__",
            "test_name": "All tests passed",
            "classname": "",
            "error_summary": "",
            "error_details": "",
            "full_stack_trace": "",
            "failure_type": "",
            "execution_time": "0",
            "is_skipped": False,
            "timestamp": timestamp,
            "source": xml_file.name if hasattr(xml_file, 'name') else "uploaded_file.xml",
            "_no_failures": True,
            "total_tests": total_tests,
            "total_failures": 0
        }]
    
    return failures


def group_failures_by_spec(failures: List[Dict]) -> Dict[str, List[Dict]]:
    """
    Group failures by spec file for better organization.
    Returns: {spec_name: [list of failures]}
    """
    grouped = {}
    
    for failure in failures:
        spec = failure["spec_file"]
        if spec not in grouped:
            grouped[spec] = []
        grouped[spec].append(failure)
    
    return grouped


def get_failure_statistics(failures: List[Dict]) -> Dict:
    """
    Calculate statistics about failures.
    """
    if not failures or (len(failures) == 1 and failures[0].get("_no_failures")):
        return {
            "total_failures": 0,
            "real_failures": 0,
            "skipped_failures": 0,
            "unique_specs": 0,
            "total_time": 0
        }
    
    real_failures = [f for f in failures if not f.get("is_skipped")]
    skipped_failures = [f for f in failures if f.get("is_skipped")]
    unique_specs = len(set(f["spec_file"] for f in failures))
    total_time = sum(float(f.get("execution_time", 0)) for f in failures)
    
    return {
        "total_failures": len(failures),
        "real_failures": len(real_failures),
        "skipped_failures": len(skipped_failures),
        "unique_specs": unique_specs,
        "total_time": round(total_time, 2)
    }