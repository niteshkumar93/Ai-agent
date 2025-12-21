# api_xml_extractor.py
"""
Parser for Automation API XML reports.
Extracts failures from testsuite with spec file information.
"""

import xml.etree.ElementTree as ET
from typing import List, Dict, Optional
import re


def extract_api_failures(xml_file) -> List[Dict]:
    """
    Extract failures from Automation API XML reports.
    
    Structure:
    - <testsuites> root
    - <testsuite> with name="SpecFileName" (e.g., "FS_MAP_SF_RL_LX_Text_Ads_Opp_OBJ_Console")
    - <testcase> with failures
    - <failure> containing error messages
    
    Returns list of failure dictionaries.
    """
    
    xml_file.seek(0)
    
    try:
        tree = ET.parse(xml_file)
        root = tree.getroot()
    except ET.ParseError as e:
        return create_no_failure_record(f"XML parse error: {e}")
    except Exception as e:
        return create_no_failure_record(f"Error reading XML: {e}")
    
    # Extract metadata from root
    metadata = extract_metadata_from_root(root)
    
    # Find all testsuites
    testsuites = root.findall('.//testsuite')
    
    if not testsuites:
        return create_no_failure_record("No testsuites found in XML")
    
    failures = []
    
    for testsuite in testsuites:
        spec_name = testsuite.get('name', 'Unknown')
        failures_count = int(testsuite.get('failures', '0'))
        
        # Skip testsuites with no failures
        if failures_count == 0:
            continue
        
        # Extract spec file path from failure messages (it contains full path)
        spec_file_path = extract_spec_file_path(testsuite)
        
        # Process each testcase in this testsuite
        testcases = testsuite.findall('.//testcase')
        
        for testcase in testcases:
            failure_elements = testcase.findall('.//failure')
            
            if failure_elements:
                # This testcase has failures
                testcase_name = testcase.get('name', 'Unknown')
                testcase_time = testcase.get('time', '0')
                
                failure_info = extract_failure_info(
                    spec_name=spec_name,
                    spec_file_path=spec_file_path,
                    testcase_name=testcase_name,
                    testcase_time=testcase_time,
                    failure_elements=failure_elements,
                    metadata=metadata
                )
                
                if failure_info:
                    failures.append(failure_info)
    
    if not failures:
        return create_no_failure_record(
            metadata=metadata,
            is_clean_run=True
        )
    
    return failures


def create_no_failure_record(
    message: str = "",
    metadata: Dict = None,
    is_clean_run: bool = False
) -> List[Dict]:
    """Create a record indicating no failures"""
    
    if metadata is None:
        metadata = {
            "report_name": "Unknown",
            "total_tests": 0,
            "total_failures": 0,
            "timestamp": "Unknown"
        }
    
    return [{
        "name": "__NO_FAILURES__",
        "spec_name": "",
        "spec_file_path": "",
        "testcase_name": "",
        "error": "" if is_clean_run else message,
        "error_type": "",
        "error_details": "",
        "is_skipped": False,
        "skip_reason": "",
        "execution_time": 0,
        "report_name": metadata.get("report_name", "Unknown"),
        "total_tests": metadata.get("total_tests", 0),
        "total_failures": metadata.get("total_failures", 0),
        "timestamp": metadata.get("timestamp", "Unknown"),
        "_no_failures": True,
    }]


def extract_metadata_from_root(root) -> Dict:
    """Extract metadata from root testsuites element"""
    
    metadata = {}
    
    # Extract from root attributes
    metadata["total_tests"] = int(root.get('tests', '0'))
    metadata["total_failures"] = int(root.get('failures', '0'))
    metadata["total_time"] = float(root.get('time', '0'))
    metadata["total_errors"] = int(root.get('errors', '0'))
    metadata["disabled"] = int(root.get('disabled', '0'))
    
    # Try to find timestamp from first testsuite
    first_suite = root.find('.//testsuite')
    if first_suite is not None:
        metadata["timestamp"] = first_suite.get('timestamp', 'Unknown')
    else:
        metadata["timestamp"] = "Unknown"
    
    # Extract report name from file path in failures
    # Will be updated when we find it in failure messages
    metadata["report_name"] = "AutomationAPI"
    
    return metadata


def extract_spec_file_path(testsuite) -> str:
    """
    Extract the spec file path from failure messages.
    
    Format: D:\Jenkins\workspace\AutomationAPI_Flexi5\...\BaseSpec.js
    We want: AutomationAPI_Flexi5
    """
    
    # Look for path in any failure message
    testcases = testsuite.findall('.//testcase')
    
    for testcase in testcases:
        failures = testcase.findall('.//failure')
        for failure in failures:
            message = failure.get('message', '')
            cdata = failure.text or ''
            full_text = message + ' ' + cdata
            
            # Look for Jenkins workspace path
            match = re.search(r'D:\\Jenkins\\workspace\\([^\\]+)', full_text)
            if match:
                return match.group(1)
            
            # Alternative: Look for file:/// path
            match = re.search(r'file:///D:/Jenkins/workspace/([^/]+)', full_text)
            if match:
                return match.group(1)
    
    return "Unknown"


def extract_failure_info(
    spec_name: str,
    spec_file_path: str,
    testcase_name: str,
    testcase_time: str,
    failure_elements: List,
    metadata: Dict
) -> Optional[Dict]:
    """
    Extract detailed failure information from testcase.
    
    A testcase can have multiple <failure> elements.
    """
    
    # Determine if this is a skipped failure
    is_skipped = False
    skip_reason = ""
    error_message = ""
    error_type = ""
    error_details = ""
    
    # Process all failure elements
    for failure in failure_elements:
        failure_type = failure.get('type', 'unknown')
        failure_message = failure.get('message', '')
        failure_cdata = failure.text or ''
        
        # Check if this is a skipped test (due to previous failure)
        if 'Skipping the test case because the previous step has failed' in failure_message or \
           'Skipping the test case because the previous step has failed' in failure_cdata:
            is_skipped = True
            skip_reason = extract_skip_reason(failure_message, failure_cdata)
        
        # Extract error information
        if not is_skipped:
            error_type = failure_type
            error_message = extract_clean_error_message(failure_message)
            error_details = extract_error_details(failure_cdata)
        else:
            # For skipped tests, still capture the original error
            if not error_message:
                error_message = "Skipped due to previous failure"
                error_details = skip_reason
    
    # Get clean spec name (the actual spec file like "Opp_Text_Ads_RL_ConsoleSpec")
    clean_spec_name = extract_spec_name_from_path(failure_elements)
    if not clean_spec_name:
        clean_spec_name = spec_name
    
    return {
        "name": testcase_name,
        "spec_name": clean_spec_name,
        "spec_file_path": spec_file_path,
        "testcase_name": testcase_name,
        "error": error_message,
        "error_type": error_type,
        "error_details": error_details,
        "is_skipped": is_skipped,
        "skip_reason": skip_reason,
        "execution_time": float(testcase_time),
        "report_name": metadata.get("report_name", "AutomationAPI"),
        "total_tests": metadata.get("total_tests", 0),
        "total_failures": metadata.get("total_failures", 0),
        "timestamp": metadata.get("timestamp", "Unknown"),
    }


def extract_spec_name_from_path(failure_elements: List) -> str:
    """
    Extract the spec file name from error stack trace.
    
    Example: Opp_Text_Ads_RL_ConsoleSpec from:
    "at Opp_Text_Ads_RL_ConsoleSpec.<anonymous> (D:\Jenkins\...)"
    """
    
    for failure in failure_elements:
        failure_cdata = failure.text or ''
        
        # Pattern: "at SpecName.<anonymous>"
        match = re.search(r'at\s+([A-Za-z0-9_]+Spec)\.<anonymous>', failure_cdata)
        if match:
            return match.group(1)
        
        # Alternative: Look for .spec file reference
        match = re.search(r'([A-Za-z0-9_]+Spec)\.js', failure_cdata)
        if match:
            return match.group(1)
    
    return ""


def extract_clean_error_message(message: str) -> str:
    """
    Extract a clean, readable error message.
    
    Examples:
    - "Expected Object(...) to be null, 'Invalid Test Case XML'."
    - "Failed: Skipping the test case..."
    """
    
    if not message:
        return "Test execution failed"
    
    # For "Expected ... to be null, 'message'" pattern
    match = re.search(r"to be null,\s*['\"]([^'\"]+)['\"]", message)
    if match:
        return match.group(1)
    
    # For TimeoutError
    if 'TimeoutError' in message:
        match = re.search(r'TimeoutError:\s*([^\n]+)', message)
        if match:
            return match.group(1)
    
    # For generic errors - take first 200 chars
    clean = message.strip()
    if len(clean) > 200:
        return clean[:200] + "..."
    
    return clean


def extract_error_details(cdata: str) -> str:
    """
    Extract detailed error information from CDATA section.
    
    Includes:
    - Error type
    - Stack trace (first 10 lines)
    - Relevant context
    """
    
    if not cdata:
        return ""
    
    lines = cdata.split('\n')
    
    # Take first 15 lines of error (usually contains the important info)
    error_lines = []
    for line in lines[:15]:
        line = line.strip()
        if line and not line.startswith('---'):
            error_lines.append(line)
    
    return '\n'.join(error_lines)


def extract_skip_reason(message: str, cdata: str) -> str:
    """
    Extract the reason why a test was skipped.
    
    Pattern: "Skipping the test case because the previous step has failed with error: [ERROR]"
    """
    
    full_text = message + ' ' + cdata
    
    # Pattern 1: After "previous step has failed with error:"
    match = re.search(r'previous step has failed with error:\s*(.+?)(?:\n|$)', full_text)
    if match:
        reason = match.group(1).strip()
        # Limit to 300 chars
        if len(reason) > 300:
            return reason[:300] + "..."
        return reason
    
    # Pattern 2: Look for the actual error message
    match = re.search(r'TimeoutError:\s*(.+?)(?:\n|$)', full_text)
    if match:
        return match.group(1).strip()
    
    return "Previous step failed"


def compare_api_reports(current_failures: List[Dict], baseline_failures: List[Dict]) -> Dict:
    """
    Compare current API report with baseline.
    
    Returns:
    - new_failures: Failures not in baseline
    - fixed_failures: Failures in baseline but not in current
    - common_failures: Failures in both
    """
    
    # Handle no failures case
    if current_failures and current_failures[0].get('_no_failures'):
        current_failures = []
    
    if baseline_failures and baseline_failures[0].get('_no_failures'):
        baseline_failures = []
    
    # Create lookup keys: spec_name + testcase_name
    def make_key(failure):
        return f"{failure.get('spec_name', '')}::{failure.get('testcase_name', '')}"
    
    current_map = {make_key(f): f for f in current_failures}
    baseline_map = {make_key(f): f for f in baseline_failures}
    
    current_keys = set(current_map.keys())
    baseline_keys = set(baseline_map.keys())
    
    # Calculate differences
    new_keys = current_keys - baseline_keys
    fixed_keys = baseline_keys - current_keys
    common_keys = current_keys & baseline_keys
    
    return {
        "new_failures": [current_map[k] for k in new_keys],
        "fixed_failures": [baseline_map[k] for k in fixed_keys],
        "common_failures": [current_map[k] for k in common_keys],
        "current_total": len(current_failures),
        "baseline_total": len(baseline_failures),
        "new_count": len(new_keys),
        "fixed_count": len(fixed_keys),
        "common_count": len(common_keys),
    }