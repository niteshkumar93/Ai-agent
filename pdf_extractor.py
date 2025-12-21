import PyPDF2
import re
from typing import List, Dict, Optional
import base64

def extract_pdf_failures(pdf_file) -> List[Dict]:
    """
    Extract failed test cases from Provar PDF reports with step details and screenshots.
    Returns list of failures with:
    - Test case name
    - Failed step
    - Previous passed step
    - Error message
    - Screenshot (if available)
    """
    
    pdf_file.seek(0)
    reader = PyPDF2.PdfReader(pdf_file)
    
    failures = []
    current_testcase = None
    current_steps = []
    execution_time = "Unknown"
    browser_type = "Unknown"
    project_path = ""
    
    # Extract text from all pages
    full_text = ""
    for page in reader.pages:
        full_text += page.extract_text() + "\n"
    
    # Extract global metadata
    execution_time = extract_execution_time(full_text)
    browser_type = extract_browser_type(full_text)
    project_path = extract_project_path(full_text)
    
    # Split into sections by test case
    testcase_sections = split_by_testcases(full_text)
    
    for section in testcase_sections:
        failure_info = parse_testcase_section(section, browser_type, project_path, execution_time)
        if failure_info:
            failures.append(failure_info)
    
    # Handle no failures case
    if not failures:
        return [{
            "name": "__NO_FAILURES__",
            "testcase_path": "",
            "error": "",
            "details": "",
            "failed_step": "",
            "previous_passed_step": "",
            "next_step": "",
            "all_steps": [],
            "screenshot_available": False,
            "screenshot_data": None,
            "webBrowserType": browser_type,
            "projectCachePath": project_path,
            "timestamp": execution_time,
            "_no_failures": True,
        }]
    
    return failures


def extract_execution_time(text: str) -> str:
    """Extract execution timestamp from PDF text"""
    patterns = [
        r"Execution Time[:\s]+([^\n]+)",
        r"Started[:\s]+([^\n]+)",
        r"Timestamp[:\s]+([^\n]+)",
        r"(\d{1,2}/\d{1,2}/\d{4}\s+\d{1,2}:\d{2}:\d{2})",
        r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})",
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    
    return "Unknown"


def extract_browser_type(text: str) -> str:
    """Extract browser type from PDF"""
    patterns = [
        r"Browser[:\s]+(Chrome|Firefox|Safari|Edge|Internet Explorer)",
        r"webBrowserType[:\s]+([^\n]+)",
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    
    return "Unknown"


def extract_project_path(text: str) -> str:
    """Extract project cache path"""
    patterns = [
        r"Project Path[:\s]+([^\n]+)",
        r"projectCachePath[:\s]+([^\n]+)",
        r"Cache Path[:\s]+([^\n]+)",
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    
    return ""


def split_by_testcases(text: str) -> List[str]:
    """Split PDF text into individual test case sections"""
    # Look for test case headers (adjust pattern based on your PDF format)
    testcase_pattern = r"(?=(?:Test Case|TestCase|Testcase)[:\s]+[A-Za-z0-9_]+)"
    sections = re.split(testcase_pattern, text, flags=re.IGNORECASE)
    return [s.strip() for s in sections if s.strip()]


def parse_testcase_section(section: str, browser: str, project: str, timestamp: str) -> Optional[Dict]:
    """
    Parse a single test case section to extract failure information.
    Looks for:
    1. Test case name
    2. Step sequence with pass/fail markers
    3. Failed step details
    4. Error messages
    5. Screenshot references
    """
    
    # Extract test case name
    testcase_name = extract_testcase_name(section)
    if not testcase_name:
        return None
    
    # Extract all steps
    steps = extract_steps(section)
    if not steps:
        return None
    
    # Find failed step
    failed_step_info = find_failed_step(steps)
    if not failed_step_info:
        return None  # No failure in this test case
    
    failed_step = failed_step_info['step']
    failed_index = failed_step_info['index']
    
    # Get previous passed step
    previous_step = steps[failed_index - 1] if failed_index > 0 else None
    
    # Get next step (if exists)
    next_step = steps[failed_index + 1] if failed_index < len(steps) - 1 else None
    
    # Extract error message
    error_message = extract_error_message(section, failed_step)
    
    # Extract detailed error info
    error_details = extract_error_details(section)
    
    # Check for screenshot
    screenshot_available, screenshot_info = check_screenshot(section)
    
    # Build testcase path
    testcase_path = extract_testcase_path(section) or testcase_name
    
    return {
        "name": testcase_name,
        "testcase_path": testcase_path,
        "error": error_message,
        "details": error_details,
        "failed_step": failed_step,
        "previous_passed_step": previous_step['text'] if previous_step else "",
        "next_step": next_step['text'] if next_step else "",
        "all_steps": steps,
        "screenshot_available": screenshot_available,
        "screenshot_info": screenshot_info,
        "webBrowserType": browser,
        "projectCachePath": project,
        "timestamp": timestamp,
    }


def extract_testcase_name(section: str) -> Optional[str]:
    """Extract test case name from section"""
    patterns = [
        r"(?:Test Case|TestCase|Testcase)[:\s]+([A-Za-z0-9_.\-/]+)",
        r"^([A-Za-z0-9_]+\.testcase)",
    ]
    
    for pattern in patterns:
        match = re.search(pattern, section, re.IGNORECASE | re.MULTILINE)
        if match:
            return match.group(1).strip()
    
    return None


def extract_testcase_path(section: str) -> Optional[str]:
    """Extract full test case path"""
    patterns = [
        r"Path[:\s]+([^\n]+\.testcase)",
        r"Location[:\s]+([^\n]+)",
    ]
    
    for pattern in patterns:
        match = re.search(pattern, section, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    
    return None


def extract_steps(section: str) -> List[Dict]:
    """
    Extract all test steps with their pass/fail status.
    Returns list of dicts with: {text, status, index}
    """
    steps = []
    
    # Pattern to match steps with green tick (✓) or red cross (✗/×)
    # Also matches step numbers like "2.11"
    step_patterns = [
        r"([✓✗×❌])\s*(.+?)(?=\n[✓✗×❌]|\Z)",  # With symbols
        r"(\d+(?:\.\d+)?)\s+([✓✗×❌])?\s*(.+?)(?=\n\d+(?:\.\d+)?|\Z)",  # With numbers
        r"(?:On|Click|Set|Verify|Wait)\s+(.+?)(?=\n(?:On|Click|Set|Verify|Wait)|\Z)",  # Action keywords
    ]
    
    # Try each pattern
    for pattern in step_patterns:
        matches = re.finditer(pattern, section, re.IGNORECASE | re.DOTALL)
        temp_steps = []
        
        for idx, match in enumerate(matches):
            groups = match.groups()
            
            # Determine status and text based on pattern
            if len(groups) == 2:  # Symbol + text
                symbol, text = groups
                status = 'failed' if symbol in ['✗', '×', '❌'] else 'passed'
            elif len(groups) == 3:  # Number + symbol + text
                num, symbol, text = groups
                status = 'failed' if symbol and symbol in ['✗', '×', '❌'] else 'passed'
            else:
                text = groups[0]
                status = 'unknown'
            
            temp_steps.append({
                'text': text.strip(),
                'status': status,
                'index': idx
            })
        
        if temp_steps:
            steps = temp_steps
            break
    
    return steps


def find_failed_step(steps: List[Dict]) -> Optional[Dict]:
    """Find the first failed step in the list"""
    for step in steps:
        if step['status'] == 'failed':
            return step
    return None


def extract_error_message(section: str, failed_step: Dict) -> str:
    """Extract error message near the failed step"""
    patterns = [
        r"Error[:\s]+(.+?)(?=\n\n|\Z)",
        r"Exception[:\s]+(.+?)(?=\n\n|\Z)",
        r"Failed[:\s]+(.+?)(?=\n\n|\Z)",
        r"(?:Message|Details)[:\s]+(.+?)(?=\n\n|\Z)",
    ]
    
    for pattern in patterns:
        match = re.search(pattern, section, re.IGNORECASE | re.DOTALL)
        if match:
            return match.group(1).strip()[:200]  # Limit length
    
    return "Execution failed"


def extract_error_details(section: str) -> str:
    """Extract full error details"""
    patterns = [
        r"(?:Stack Trace|Error Details|Details)[:\s]+((?:.|\n)+?)(?=\n\n[A-Z]|\Z)",
        r"(?:Exception|Error)[:\s]+((?:.|\n)+?)(?=\n\nTest|\n\nStep|\Z)",
    ]
    
    for pattern in patterns:
        match = re.search(pattern, section, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    
    # Fallback: return section near error keywords
    error_section = re.search(r"(?:error|exception|failed).*?(?:\n.*?){0,10}", section, re.IGNORECASE | re.DOTALL)
    if error_section:
        return error_section.group(0).strip()
    
    return "No detailed error information available"


def check_screenshot(section: str) -> tuple:
    """
    Check if screenshot is available and extract reference.
    Returns (is_available: bool, info: str)
    """
    screenshot_patterns = [
        r"Screenshot[:\s]+([^\n]+)",
        r"Image[:\s]+([^\n]+)",
        r"Capture[:\s]+([^\n]+)",
        r"(?:screenshot|image).*?\.(?:png|jpg|jpeg)",
    ]
    
    for pattern in screenshot_patterns:
        match = re.search(pattern, section, re.IGNORECASE)
        if match:
            return True, match.group(0).strip()
    
    return False, "No screenshot available"