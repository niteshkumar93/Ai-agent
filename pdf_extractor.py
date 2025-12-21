# pdf_extractor.py

try:
    import PyPDF2
except ImportError:
    try:
        import pypdf as PyPDF2
    except ImportError:
        raise ImportError("Please install PyPDF2 or pypdf: pip install PyPDF2")

import re
from typing import List, Dict, Optional, Tuple

def extract_pdf_failures(pdf_file) -> List[Dict]:
    """
    Extract failed test cases from Provar PDF reports.
    Handles multiple PDF report formats.
    """
    
    pdf_file.seek(0)
    
    try:
        reader = PyPDF2.PdfReader(pdf_file)
    except Exception as e:
        print(f"Error reading PDF: {e}")
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
            "webBrowserType": "Unknown",
            "projectCachePath": "",
            "timestamp": "Unknown",
            "_no_failures": True,
        }]
    
    # Extract text from all pages
    full_text = ""
    for page_num, page in enumerate(reader.pages):
        try:
            page_text = page.extract_text()
            full_text += page_text + f"\n--- PAGE {page_num + 1} ---\n"
        except Exception as e:
            print(f"Error extracting text from page {page_num}: {e}")
            continue
    
    if not full_text.strip():
        return [{
            "name": "__NO_FAILURES__",
            "testcase_path": "",
            "error": "PDF text extraction failed",
            "details": "Could not extract text from PDF",
            "failed_step": "",
            "previous_passed_step": "",
            "next_step": "",
            "all_steps": [],
            "screenshot_available": False,
            "screenshot_info": "",
            "webBrowserType": "Unknown",
            "projectCachePath": "",
            "timestamp": "Unknown",
            "_no_failures": True,
        }]
    
    # Debug: Save extracted text (optional)
    # with open("debug_pdf_text.txt", "w", encoding="utf-8") as f:
    #     f.write(full_text)
    
    # Extract metadata
    execution_time = extract_execution_time(full_text)
    browser_type = extract_browser_type(full_text)
    project_path = extract_project_path(full_text)
    
    # Extract failures
    failures = []
    
    # Method 1: Look for "Failed" or "Error" test cases
    failed_testcases = find_failed_testcases_method1(full_text)
    
    # Method 2: Look for error messages and stack traces
    if not failed_testcases:
        failed_testcases = find_failed_testcases_method2(full_text)
    
    # Method 3: Look for red X markers or failure indicators
    if not failed_testcases:
        failed_testcases = find_failed_testcases_method3(full_text)
    
    for tc_info in failed_testcases:
        failure_data = {
            "name": tc_info.get("name", "Unknown Test"),
            "testcase_path": tc_info.get("path", ""),
            "error": tc_info.get("error", "Test execution failed"),
            "details": tc_info.get("details", ""),
            "failed_step": tc_info.get("failed_step", ""),
            "previous_passed_step": tc_info.get("previous_step", ""),
            "next_step": tc_info.get("next_step", ""),
            "all_steps": tc_info.get("all_steps", []),
            "screenshot_available": tc_info.get("screenshot_available", False),
            "screenshot_info": tc_info.get("screenshot_info", ""),
            "webBrowserType": browser_type,
            "projectCachePath": project_path,
            "timestamp": execution_time,
        }
        failures.append(failure_data)
    
    # If no failures found, return metadata indicating no failures
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
            "webBrowserType": browser_type,
            "projectCachePath": project_path,
            "timestamp": execution_time,
            "_no_failures": True,
        }]
    
    return failures


def extract_execution_time(text: str) -> str:
    """Extract execution timestamp from PDF text"""
    patterns = [
        r"(?:Execution Time|Started|Start Time|Timestamp)[:\s]*([^\n]{10,50})",
        r"(?:Date|Time)[:\s]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}[^\n]{0,30})",
        r"(\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2})",
        r"(\d{1,2}/\d{1,2}/\d{4}\s+\d{1,2}:\d{2}:\d{2})",
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    
    return "Unknown"


def extract_browser_type(text: str) -> str:
    """Extract browser type from PDF"""
    patterns = [
        r"(?:Browser|webBrowserType)[:\s]*(Chrome|Firefox|Safari|Edge|Internet Explorer|IE)",
        r"(Chrome|Firefox|Safari|Edge)\s+\d+",
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    
    return "Unknown"


def extract_project_path(text: str) -> str:
    """Extract project cache path"""
    patterns = [
        r"(?:Project Path|projectCachePath|Cache Path)[:\s]*([^\n]+)",
        r"(?:Project|Path)[:\s]*([^\n]*(?:Jenkins|workspace)[^\n]*)",
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            path = match.group(1).strip()
            if len(path) > 10:  # Valid path
                return path
    
    return ""


def find_failed_testcases_method1(text: str) -> List[Dict]:
    """
    Method 1: Look for explicit failure markers like "Failed", "Error", "×"
    """
    failures = []
    
    # Split by test case sections
    testcase_pattern = r"(?:Test Case|TestCase|Test)[:\s]+([A-Za-z0-9_.\-/]+(?:\.testcase)?)"
    matches = list(re.finditer(testcase_pattern, text, re.IGNORECASE))
    
    for i, match in enumerate(matches):
        testcase_name = match.group(1).strip()
        start_pos = match.end()
        end_pos = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        section = text[start_pos:end_pos]
        
        # Check if this section contains failure indicators
        if has_failure_indicators(section):
            failure_info = extract_failure_details(testcase_name, section, text)
            if failure_info:
                failures.append(failure_info)
    
    return failures


def find_failed_testcases_method2(text: str) -> List[Dict]:
    """
    Method 2: Look for error messages and exceptions
    """
    failures = []
    
    # Find all error/exception blocks
    error_patterns = [
        r"(Error|Exception|Failed)[:\s]*([^\n]+(?:\n(?!\n)[^\n]+)*)",
        r"(?:✗|×|❌)\s*([^\n]+(?:\n(?!\n)[^\n]+)*)",
    ]
    
    for pattern in error_patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            error_text = match.group(0)
            
            # Try to find associated test case name
            before_text = text[max(0, match.start() - 500):match.start()]
            testcase_match = re.search(r"([A-Za-z0-9_.\-/]+\.testcase)", before_text)
            
            testcase_name = testcase_match.group(1) if testcase_match else "Unknown Test"
            
            failure_info = {
                "name": testcase_name,
                "path": "",
                "error": match.group(0)[:200],
                "details": error_text[:1000],
                "failed_step": extract_failed_step_nearby(text, match.start()),
                "previous_step": "",
                "next_step": "",
                "all_steps": [],
                "screenshot_available": "screenshot" in error_text.lower(),
                "screenshot_info": "Screenshot mentioned in error context"
            }
            
            failures.append(failure_info)
    
    return failures


def find_failed_testcases_method3(text: str) -> List[Dict]:
    """
    Method 3: Parse step-by-step execution looking for failures
    """
    failures = []
    
    # Look for step sequences with failure markers
    step_sections = re.split(r'\n(?=\d+\.|Step \d+)', text)
    
    current_testcase = "Unknown Test"
    steps = []
    
    for section in step_sections:
        # Try to identify test case
        tc_match = re.search(r"([A-Za-z0-9_.\-/]+\.testcase)", section)
        if tc_match:
            current_testcase = tc_match.group(1)
        
        # Check for failure in this section
        if re.search(r'(?:✗|×|❌|failed|error)', section, re.IGNORECASE):
            failure_info = {
                "name": current_testcase,
                "path": current_testcase,
                "error": "Step execution failed",
                "details": section[:500],
                "failed_step": section[:200],
                "previous_step": "",
                "next_step": "",
                "all_steps": [],
                "screenshot_available": "screenshot" in section.lower(),
                "screenshot_info": "Check failure details"
            }
            failures.append(failure_info)
    
    return failures


def has_failure_indicators(text: str) -> bool:
    """Check if text section contains failure indicators"""
    failure_keywords = [
        r'\bfailed\b',
        r'\berror\b',
        r'\bexception\b',
        r'✗', r'×', r'❌',
        r'\bFAIL\b',
        r'assertion.*failed',
        r'could not',
        r'unable to',
    ]
    
    for keyword in failure_keywords:
        if re.search(keyword, text, re.IGNORECASE):
            return True
    
    return False


def extract_failure_details(testcase_name: str, section: str, full_text: str) -> Optional[Dict]:
    """Extract detailed failure information from a test case section"""
    
    # Extract error message
    error_patterns = [
        r"(?:Error|Exception|Failed)[:\s]*([^\n]+)",
        r"(?:Message|Details)[:\s]*([^\n]+)",
    ]
    
    error_msg = "Execution failed"
    for pattern in error_patterns:
        match = re.search(pattern, section, re.IGNORECASE)
        if match:
            error_msg = match.group(1).strip()[:200]
            break
    
    # Extract steps
    steps = extract_steps_from_section(section)
    
    # Find failed step
    failed_step = ""
    previous_step = ""
    next_step = ""
    
    for i, step in enumerate(steps):
        if step.get('status') == 'failed':
            failed_step = step.get('text', '')
            previous_step = steps[i-1].get('text', '') if i > 0 else ""
            next_step = steps[i+1].get('text', '') if i < len(steps) - 1 else ""
            break
    
    # Check for screenshots
    screenshot_available = bool(re.search(r'screenshot|image|capture', section, re.IGNORECASE))
    
    return {
        "name": testcase_name,
        "path": testcase_name,
        "error": error_msg,
        "details": section[:1000],
        "failed_step": failed_step,
        "previous_step": previous_step,
        "next_step": next_step,
        "all_steps": steps,
        "screenshot_available": screenshot_available,
        "screenshot_info": "Screenshot available in report" if screenshot_available else ""
    }


def extract_steps_from_section(section: str) -> List[Dict]:
    """Extract test steps from a section"""
    steps = []
    
    # Multiple step patterns
    patterns = [
        r'(\d+(?:\.\d+)?)\s*([✓✗×❌]?)\s*([^\n]+)',  # Numbered steps
        r'([✓✗×❌])\s*([^\n]+)',  # Symbol-based steps
        r'(?:Step|Action)[:\s]*([^\n]+)',  # Step: format
    ]
    
    for pattern in patterns:
        matches = re.finditer(pattern, section)
        temp_steps = []
        
        for idx, match in enumerate(matches):
            groups = match.groups()
            
            if len(groups) == 3:  # Number + symbol + text
                num, symbol, text = groups
                status = 'failed' if symbol in ['✗', '×', '❌'] else 'passed' if symbol == '✓' else 'unknown'
            elif len(groups) == 2:  # Symbol + text
                symbol, text = groups
                status = 'failed' if symbol in ['✗', '×', '❌'] else 'passed' if symbol == '✓' else 'unknown'
            else:  # Just text
                text = groups[0]
                status = 'unknown'
            
            if text and len(text.strip()) > 3:
                temp_steps.append({
                    'text': text.strip(),
                    'status': status,
                    'index': idx
                })
        
        if temp_steps:
            steps = temp_steps
            break
    
    return steps


def extract_failed_step_nearby(text: str, position: int) -> str:
    """Extract failed step near an error position"""
    context = text[max(0, position - 200):position + 200]
    
    step_patterns = [
        r'(?:On|Click|Set|Verify|Wait|Enter|Select)\s+[^\n]{10,100}',
        r'Step[:\s]*([^\n]+)',
    ]
    
    for pattern in step_patterns:
        match = re.search(pattern, context, re.IGNORECASE)
        if match:
            return match.group(0)[:150]
    
    return "Step information not available"