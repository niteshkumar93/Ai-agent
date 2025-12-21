# custom_pdf_parser.py
"""
Custom parser specifically for Provar PDF reports
Handles Lightning_Formatted_Datetime style reports
"""

try:
    import PyPDF2
except ImportError:
    import pypdf as PyPDF2

import re
from typing import List, Dict, Tuple

def parse_provar_pdf(pdf_file) -> List[Dict]:
    """
    Parse Provar PDF reports - handles multiple formats
    """
    pdf_file.seek(0)
    reader = PyPDF2.PdfReader(pdf_file)
    
    full_text = ""
    for page in reader.pages:
        full_text += page.extract_text() + "\n"
    
    # Extract metadata
    metadata = extract_metadata(full_text)
    
    # Find all test cases
    testcases = find_all_testcases(full_text)
    
    failures = []
    for tc_name, tc_text in testcases:
        if is_failed_testcase(tc_text):
            failure_info = parse_failed_testcase(tc_name, tc_text, metadata)
            failures.append(failure_info)
    
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
            "screenshot_info": "",
            "webBrowserType": metadata.get("browser", "Unknown"),
            "projectCachePath": metadata.get("project", ""),
            "timestamp": metadata.get("time", "Unknown"),
            "_no_failures": True,
        }]
    
    return failures


def extract_metadata(text: str) -> Dict:
    """Extract report metadata"""
    metadata = {}
    
    # Browser
    browser_patterns = [
        r'(?:Browser|webBrowserType)[:\s]*(Chrome|Firefox|Safari|Edge)',
        r'(Chrome|Firefox|Safari|Edge)\s*\d+',
    ]
    for pattern in browser_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            metadata['browser'] = match.group(1)
            break
    
    # Project - look for VF_Lightning_Windows style
    project_patterns = [
        r'(VF_Lightning_Windows|CPQ_Classic|QAM_Lightning|Regmain[_-]\w+)',
        r'Project[:\s]*([^\n]{10,})',
    ]
    for pattern in project_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            metadata['project'] = match.group(1).strip()
            break
    
    # Time
    time_match = re.search(r'(\d{1,2}/\d{1,2}/\d{4}\s+\d{1,2}:\d{2})', text)
    if time_match:
        metadata['time'] = time_match.group(1)
    
    return metadata


def find_all_testcases(text: str) -> List[Tuple[str, str]]:
    """
    Find all test cases and their content sections
    Returns: [(testcase_name, testcase_content), ...]
    """
    testcases = []
    
    # Pattern for Lightning_Formatted_Datetime_App_Page.testcase style
    pattern = r'([A-Za-z0-9_]+\.testcase)'
    matches = list(re.finditer(pattern, text))
    
    for i, match in enumerate(matches):
        tc_name = match.group(1)
        start = match.start()
        
        # Get content until next testcase or end
        if i + 1 < len(matches):
            end = matches[i + 1].start()
        else:
            end = len(text)
        
        tc_content = text[start:end]
        testcases.append((tc_name, tc_content))
    
    return testcases


def is_failed_testcase(text: str) -> bool:
    """Check if testcase section indicates failure"""
    failure_indicators = [
        r'\bfailed\b',
        r'\berror\b',
        r'\bexception\b',
        r'✗', r'×', r'❌',
        r'\bFAIL\b',
        r'could not',
        r'unable to',
        r'timeout',
        r'not found',
    ]
    
    for indicator in failure_indicators:
        if re.search(indicator, text, re.IGNORECASE):
            return True
    
    return False


def parse_failed_testcase(tc_name: str, tc_text: str, metadata: Dict) -> Dict:
    """Parse details of a failed test case"""
    
    # Extract error message
    error_msg = extract_error_message(tc_text)
    
    # Extract steps
    steps = extract_steps_detailed(tc_text)
    
    # Find failed step
    failed_idx = -1
    for i, step in enumerate(steps):
        if step['status'] == 'failed':
            failed_idx = i
            break
    
    # Get context steps
    failed_step = steps[failed_idx]['text'] if failed_idx >= 0 else ""
    previous_step = steps[failed_idx - 1]['text'] if failed_idx > 0 else ""
    next_step = steps[failed_idx + 1]['text'] if failed_idx < len(steps) - 1 else ""
    
    # Screenshot detection
    screenshot = 'screenshot' in tc_text.lower()
    
    return {
        "name": tc_name,
        "testcase_path": tc_name,
        "error": error_msg,
        "details": tc_text[:1000],  # First 1000 chars
        "failed_step": failed_step,
        "previous_passed_step": previous_step,
        "next_step": next_step,
        "all_steps": steps,
        "screenshot_available": screenshot,
        "screenshot_info": "Screenshot captured" if screenshot else "",
        "webBrowserType": metadata.get("browser", "Unknown"),
        "projectCachePath": metadata.get("project", ""),
        "timestamp": metadata.get("time", "Unknown"),
    }


def extract_error_message(text: str) -> str:
    """Extract the main error message"""
    patterns = [
        r'Error[:\s]*([^\n]+)',
        r'Exception[:\s]*([^\n]+)',
        r'Failed[:\s]*([^\n]+)',
        r'(?:Timeout|Not found|Could not)[:\s]*([^\n]+)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()[:200]
    
    return "Test execution failed"


def extract_steps_detailed(text: str) -> List[Dict]:
    """
    Extract steps with status - handles multiple formats:
    - "2.11 Click the button" with status markers
    - "On SF <accountPanel2>" with ✓ or ✗
    - "Step N: Action" format
    """
    steps = []
    
    # Method 1: Numbered steps (2.11, 2.12, etc.)
    pattern1 = r'(\d+\.\d+)\s*([✓✗×❌]?)\s*([^\n]+?)(?=\d+\.\d+|\Z)'
    matches1 = list(re.finditer(pattern1, text, re.DOTALL))
    
    if matches1:
        for match in matches1:
            step_num, status_symbol, step_text = match.groups()
            
            # Determine status
            if status_symbol in ['✗', '×', '❌']:
                status = 'failed'
            elif status_symbol == '✓':
                status = 'passed'
            else:
                # Check if text contains failure keywords
                if re.search(r'error|failed|timeout|not found', step_text, re.IGNORECASE):
                    status = 'failed'
                else:
                    status = 'passed'  # Assume passed if no indicator
            
            steps.append({
                'text': f"{step_num} {step_text.strip()}",
                'status': status,
                'index': len(steps)
            })
    
    # Method 2: Action-based steps (On SF, Click, Set, etc.)
    if not steps:
        pattern2 = r'([✓✗×❌])?\s*((?:On|Click|Set|Verify|Wait|Enter|Select)\s+[^\n]+)'
        matches2 = list(re.finditer(pattern2, text, re.IGNORECASE))
        
        for match in matches2:
            status_symbol, step_text = match.groups()
            
            if status_symbol in ['✗', '×', '❌']:
                status = 'failed'
            elif status_symbol == '✓':
                status = 'passed'
            else:
                status = 'unknown'
            
            steps.append({
                'text': step_text.strip(),
                'status': status,
                'index': len(steps)
            })
    
    # Method 3: Step N format
    if not steps:
        pattern3 = r'Step\s+(\d+)[:\s]*([^\n]+)'
        matches3 = list(re.finditer(pattern3, text, re.IGNORECASE))
        
        for match in matches3:
            step_num, step_text = match.groups()
            
            # Check for failure in text
            if re.search(r'error|failed', step_text, re.IGNORECASE):
                status = 'failed'
            else:
                status = 'passed'
            
            steps.append({
                'text': f"Step {step_num}: {step_text.strip()}",
                'status': status,
                'index': len(steps)
            })
    
    return steps


# Make this compatible with your existing code
def extract_pdf_failures(pdf_file) -> List[Dict]:
    """Wrapper to maintain compatibility"""
    return parse_provar_pdf(pdf_file)