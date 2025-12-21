"""
Automation API XML Report Extractor
Extracts failures from Automation API Jenkins reports with spec file grouping
"""

import xml.etree.ElementTree as ET
import re
from typing import List, Dict, Optional


def extract_spec_name_from_path(file_path: str) -> str:
    """
    Extract spec file name from stack trace paths
    Example: D:\Jenkins\workspace\AutomationAPI_Flexi5\...\Opp_Text_Ads_RL_Console.spec.js
    Returns: Opp_Text_Ads_RL_Console
    """
    # Look for .spec.js pattern
    spec_match = re.search(r'([A-Za-z_]+)\.spec\.js', file_path)
    if spec_match:
        return spec_match.group(1)
    return "Unknown_Spec"


def extract_project_from_workspace(path: str) -> str:
    """
    Extract project name from Jenkins workspace path
    Example: D:\Jenkins\workspace\AutomationAPI_Flexi5\...
    Returns: AutomationAPI_Flexi5
    """
    workspace_match = re.search(r'workspace[/\\]([^/\\]+)', path)
    if workspace_match:
        return workspace_match.group(1)
    return "Unknown_Project"


def parse_error_summary(error_message: str) -> Dict[str, str]:
    """
    Parse the complex JavaScript error message to extract key information
    """
    summary = {
        "error_type": "Unknown",
        "short_description": "",
        "full_message": error_message
    }
    
    # Extract error type (toBe, exception, etc.)
    type_match = re.search(r'Error: Expected.*to be ([\w]+)', error_message)
    if type_match:
        summary["error_type"] = "Assertion Failure"
        summary["short_description"] = f"Assertion failed: Expected value to be {type_match.group(1)}"
    elif "TimeoutError" in error_message:
        summary["error_type"] = "Timeout"
        # Extract the element being searched for
        element_match = re.search(r"By\(xpath, (.*?)\)", error_message)
        if element_match:
            xpath = element_match.group(1).replace("&apos;", "'")
            summary["short_description"] = f"Element not found: {xpath[:100]}"
        else:
            summary["short_description"] = "Wait timed out while locating element"
    elif "Skipping the test case because the previous step has failed" in error_message:
        summary["error_type"] = "Skipped (Cascading Failure)"
        # Extract the original error
        original_match = re.search(r'failed with error: (.+?)(?:\n|$)', error_message)
        if original_match:
            summary["short_description"] = f"Dependent on previous failure"
        else:
            summary["short_description"] = "Skipped due to previous test failure"
    elif "Invalid Test Case XML" in error_message:
        summary["error_type"] = "Configuration Error"
        summary["short_description"] = "Test case XML validation failed"
    else:
        summary["error_type"] = "Error"
        # Take first line as summary
        first_line = error_message.split('\n')[0][:150]
        summary["short_description"] = first_line
    
    return summary


def is_cascading_failure(error_message: str) -> bool:
    """Check if this failure is caused by a previous failure"""
    return "Skipping the test case because the previous step has failed" in error_message


def extract_automation_api_failures(xml_file) -> List[Dict]:
    """
    Extract failures from Automation API XML reports
    Returns list of failures grouped by spec file
    """
    try:
        tree = ET.parse(xml_file)
        root = tree.getroot()
    except ET.ParseError as e:
        return [{
            "name": "__PARSE_ERROR__",
            "error": f"XML Parse Error: {str(e)}",
            "details": "Could not parse the XML file",
            "spec_file": "N/A",
            "projectCachePath": ""
        }]
    
    failures = []
    project_name = "Unknown"
    
    # Iterate through all testsuites
    for testsuite in root.findall('.//testsuite'):
        suite_name = testsuite.get('name', 'Unknown Suite')
        timestamp = testsuite.get('timestamp', 'Unknown')
        
        # Iterate through testcases
        for testcase in testsuite.findall('.//testcase'):
            testcase_name = testcase.get('name', 'Unknown Test')
            classname = testcase.get('classname', '')
            execution_time = testcase.get('time', '0')
            
            # Check if this testcase has failures
            failure_elements = testcase.findall('failure')
            
            if failure_elements:
                for failure_elem in failure_elements:
                    failure_type = failure_elem.get('type', 'unknown')
                    failure_message = failure_elem.get('message', 'No message')
                    failure_details = failure_elem.text or failure_message
                    
                    # Extract spec file name from stack trace
                    spec_file = extract_spec_name_from_path(failure_details)
                    
                    # Extract project from workspace path
                    if project_name == "Unknown":
                        project_name = extract_project_from_workspace(failure_details)
                    
                    # Parse error for summary
                    error_summary = parse_error_summary(failure_details)
                    
                    # Determine if this is a cascading failure
                    is_cascaded = is_cascading_failure(failure_details)
                    
                    failure_info = {
                        "name": testcase_name,
                        "classname": classname,
                        "spec_file": spec_file,
                        "suite_name": suite_name,
                        "error": error_summary["short_description"],
                        "error_type": error_summary["error_type"],
                        "details": failure_details,
                        "failure_type": failure_type,
                        "execution_time": execution_time,
                        "timestamp": timestamp,
                        "projectCachePath": failure_details.split('\n')[0] if '\n' in failure_details else "",
                        "is_cascading_failure": is_cascaded,
                        "testcase_path": f"{suite_name} > {testcase_name}"
                    }
                    
                    failures.append(failure_info)
    
    # If no failures found, return placeholder
    if not failures:
        return [{
            "name": "__NO_FAILURES__",
            "error": "No failures detected",
            "details": "All tests passed successfully",
            "spec_file": "N/A",
            "projectCachePath": ""
        }]
    
    # Group failures by spec file (sort by spec file name)
    failures.sort(key=lambda x: (x.get('spec_file', ''), x.get('name', '')))
    
    return failures


def group_failures_by_spec(failures: List[Dict]) -> Dict[str, List[Dict]]:
    """
    Group failures by their spec file name
    Returns: {spec_file_name: [list of failures]}
    """
    grouped = {}
    
    for failure in failures:
        spec_file = failure.get('spec_file', 'Unknown_Spec')
        
        if spec_file not in grouped:
            grouped[spec_file] = []
        
        grouped[spec_file].append(failure)
    
    return grouped


def get_spec_summary(spec_failures: List[Dict]) -> Dict:
    """
    Get summary statistics for a spec file
    """
    total = len(spec_failures)
    cascading = sum(1 for f in spec_failures if f.get('is_cascading_failure', False))
    root_failures = total - cascading
    
    # Get error types distribution
    error_types = {}
    for f in spec_failures:
        error_type = f.get('error_type', 'Unknown')
        error_types[error_type] = error_types.get(error_type, 0) + 1
    
    return {
        'total_failures': total,
        'root_failures': root_failures,
        'cascading_failures': cascading,
        'error_types': error_types,
        'first_failure': spec_failures[0] if spec_failures else None
    }


if __name__ == "__main__":
    # Test the extractor
    import sys
    
    if len(sys.argv) > 1:
        with open(sys.argv[1], 'r') as f:
            failures = extract_automation_api_failures(f)
            
            print(f"Found {len(failures)} failures")
            
            grouped = group_failures_by_spec(failures)
            print(f"\nGrouped into {len(grouped)} spec files:")
            
            for spec_file, spec_failures in grouped.items():
                summary = get_spec_summary(spec_failures)
                print(f"\n{spec_file}:")
                print(f"  Total: {summary['total_failures']}")
                print(f"  Root: {summary['root_failures']}")
                print(f"  Cascading: {summary['cascading_failures']}")
    else:
        print("Usage: python automation_api_extractor.py <xml_file>")