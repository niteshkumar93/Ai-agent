# pdf_extractor.py

try:
    import PyPDF2
except ImportError:
    try:
        import pypdf as PyPDF2
    except ImportError:
        raise ImportError("Please install: pip install PyPDF2")

import re
from typing import List, Dict, Tuple, Optional

def extract_pdf_failures(pdf_file) -> List[Dict]:
    """
    Extract failures from Provar PDF reports.
    
    Process:
    1. First page: Get summary (Passed, Failed, Skipped counts)
    2. First page: Find test cases marked with ⊗ failed icon
    3. Later pages: Extract detailed error info for failed test cases
    """
    
    pdf_file.seek(0)
    
    try:
        reader = PyPDF2.PdfReader(pdf_file)
    except Exception as e:
        return create_no_failure_record(f"PDF read error: {e}")
    
    if len(reader.pages) == 0:
        return create_no_failure_record("PDF has no pages")
    
    # Extract all pages text
    all_pages_text = []
    for page_num, page in enumerate(reader.pages):
        try:
            page_text = page.extract_text()
            all_pages_text.append({
                'page_num': page_num + 1,
                'text': page_text
            })
        except Exception as e:
            print(f"Error extracting page {page_num + 1}: {e}")
            continue
    
    if not all_pages_text:
        return create_no_failure_record("Could not extract text from PDF")
    
    # Get first page (summary page)
    first_page_text = all_pages_text[0]['text']
    
    # Extract metadata from first page
    metadata = extract_metadata_from_summary(first_page_text)
    
    # Get failure count from summary
    failed_count = extract_failure_count(first_page_text)
    
    if failed_count == 0:
        return create_no_failure_record(
            message="",
            metadata=metadata,
            is_clean_run=True
        )
    
    # Find failed test case names from first page summary
    failed_testcase_names = extract_failed_testcase_names(first_page_text)
    
    if not failed_testcase_names:
        return create_no_failure_record(
            message="Failed count > 0 but no failed test cases found in summary",
            metadata=metadata
        )
    
    # For each failed test case, find its detailed section
    failures = []
    full_text = "\n\n".join([p['text'] for p in all_pages_text])
    
    for tc_name in failed_testcase_names:
        failure_details = extract_testcase_details(tc_name, full_text, metadata)
        if failure_details:
            failures.append(failure_details)
    
    return failures if failures else create_no_failure_record(
        message="Could not extract details for failed test cases",
        metadata=metadata
    )


def create_no_failure_record(message: str = "", metadata: Dict = None, is_clean_run: bool = False) -> List[Dict]:
    """Create a record indicating no failures"""
    if metadata is None:
        metadata = {"browser": "Unknown", "project": "", "time": "Unknown"}
    
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


def extract_metadata_from_summary(first_page: str) -> Dict:
    """Extract execution time, browser, project from summary page"""
    metadata = {}
    
    # Extract Started time (e.g., "Started 03 Dec 2025, 15:09:08")
    time_match = re.search(r'Started\s+(\d{2}\s+\w{3}\s+\d{4},\s+\d{2}:\d{2}:\d{2})', first_page)
    if time_match:
        metadata['time'] = time_match.group(1)
    else:
        # Alternative pattern
        time_match = re.search(r'(\d{2}\s+\w{3}\s+\d{4},\s+\d{2}:\d{2}:\d{2})', first_page)
        if time_match:
            metadata['time'] = time_match.group(1)
    
    # Extract project (e.g., "HYBRID_AUTOMATION_Pipeline")
    project_patterns = [
        r'Project[:\s]*(HYBRID_AUTOMATION_Pipeline|VF_Lightning_Windows|CPQ_\w+|QAM_\w+|Regmain[\w_-]+)',
        r'(HYBRID_AUTOMATION_Pipeline|VF_Lightning_Windows|CPQ_Classic|CPQ_Lightning|QAM_Lightning)',
    ]
    for pattern in project_patterns:
        match = re.search(pattern, first_page)
        if match:
            metadata['project'] = match.group(1)
            break
    
    # Browser - might be in details section or system info
    browser_match = re.search(r'(Chrome|Firefox|Safari|Edge)[\s\d]*', first_page)
    if browser_match:
        metadata['browser'] = browser_match.group(1)
    else:
        metadata['browser'] = "Unknown"
    
    return metadata


def extract_failure_count(first_page: str) -> int:
    """
    Extract the number of failed test cases from summary.
    Look for patterns like:
    - "Failed 2"
    - "2 Failed"
    """
    patterns = [
        r'Failed\s+(\d+)',
        r'(\d+)\s+Failed',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, first_page, re.IGNORECASE)
        if match:
            return int(match.group(1))
    
    return 0


def extract_failed_testcase_names(first_page: str) -> List[str]:
    """
    Extract names of failed test cases from summary page.
    Look for test case names followed by "failed" or ⊗ symbol.
    
    Pattern: "Lightning_Formatted_Datetime_App_Page.testcase ⊗ failed"
    """
    failed_testcases = []
    
    # Method 1: Find lines with .testcase and failed/⊗ marker
    # Pattern: testcase_name.testcase followed by failed indicator
    pattern1 = r'([A-Za-z0-9_]+\.testcase)\s*(?:⊗|×|❌)?\s*failed'
    matches1 = re.findall(pattern1, first_page, re.IGNORECASE)
    failed_testcases.extend(matches1)
    
    # Method 2: Find .testcase followed by ⊗ symbol on next line
    pattern2 = r'([A-Za-z0-9_]+\.testcase)\s*\n?\s*(?:⊗|×|❌)'
    matches2 = re.findall(pattern2, first_page)
    failed_testcases.extend(matches2)
    
    # Method 3: Lines containing both .testcase and the failed symbol
    lines = first_page.split('\n')
    for i, line in enumerate(lines):
        if '.testcase' in line:
            # Check this line and next few lines for failure indicator
            context = '\n'.join(lines[i:i+3])
            if re.search(r'⊗|×|❌|failed', context, re.IGNORECASE):
                tc_match = re.search(r'([A-Za-z0-9_]+\.testcase)', line)
                if tc_match:
                    tc_name = tc_match.group(1)
                    if tc_name not in failed_testcases:
                        failed_testcases.append(tc_name)
    
    # Remove duplicates while preserving order
    seen = set()
    unique_failures = []
    for tc in failed_testcases:
        if tc not in seen:
            seen.add(tc)
            unique_failures.append(tc)
    
    return unique_failures


def extract_testcase_details(testcase_name: str, full_text: str, metadata: Dict) -> Optional[Dict]:
    """
    Extract detailed information for a specific failed test case.
    
    The PDF structure has:
    1. Summary section with test case name
    2. Detailed section with same test case name (highlighted in yellow)
    3. Error details and stack trace
    4. Step execution details
    """
    
    # Find the detailed section for this test case
    # Look for the test case name in a header/section
    tc_pattern = re.escape(testcase_name)
    
    # Find where this testcase's detailed section starts
    tc_match = None
    for match in re.finditer(tc_pattern, full_text):
        # Check if this is a section header (not just a reference)
        start_pos = match.start()
        context_before = full_text[max(0, start_pos - 50):start_pos]
        context_after = full_text[start_pos:start_pos + 500]
        
        # This is likely the detailed section if followed by Summary/Output
        if re.search(r'Summary|Output|Outcome', context_after, re.IGNORECASE):
            tc_match = match
            break
    
    if not tc_match:
        return {
            "name": testcase_name,
            "testcase_path": testcase_name,
            "error": "Test execution failed",
            "details": "Detailed error information not found in report",
            "failed_step": "",
            "previous_passed_step": "",
            "next_step": "",
            "all_steps": [],
            "screenshot_available": False,
            "screenshot_info": "",
            "webBrowserType": metadata.get("browser", "Unknown"),
            "projectCachePath": metadata.get("project", ""),
            "timestamp": metadata.get("time", "Unknown"),
        }
    
    # Extract section from this test case to next test case or end
    section_start = tc_match.start()
    
    # Find the end of this section (start of next .testcase or end of document)
    next_tc_pattern = r'\n[A-Za-z0-9_]+\.testcase\n'
    next_match = re.search(next_tc_pattern, full_text[section_start + 100:])
    
    if next_match:
        section_end = section_start + 100 + next_match.start()
    else:
        section_end = len(full_text)
    
    testcase_section = full_text[section_start:section_end]
    
    # Extract error message
    error_msg = extract_error_from_section(testcase_section)
    
    # Extract error details (stack trace)
    error_details = extract_error_details_from_section(testcase_section)
    
    # Extract steps
    steps = extract_steps_from_testcase_section(testcase_section)
    
    # Find failed step and context
    failed_step = ""
    previous_step = ""
    next_step = ""
    
    for i, step in enumerate(steps):
        if step['status'] == 'failed':
            failed_step = step['text']
            previous_step = steps[i - 1]['text'] if i > 0 else ""
            next_step = steps[i + 1]['text'] if i < len(steps) - 1 else ""
            break
    
    # Screenshot detection
    screenshot_available = bool(re.search(r'screenshot|capture|image', testcase_section, re.IGNORECASE))
    
    return {
        "name": testcase_name,
        "testcase_path": testcase_name,
        "error": error_msg,
        "details": error_details,
        "failed_step": failed_step,
        "previous_passed_step": previous_step,
        "next_step": next_step,
        "all_steps": steps,
        "screenshot_available": screenshot_available,
        "screenshot_info": "Screenshot available in report" if screenshot_available else "",
        "webBrowserType": metadata.get("browser", "Unknown"),
        "projectCachePath": metadata.get("project", ""),
        "timestamp": metadata.get("time", "Unknown"),
    }


def extract_error_from_section(section: str) -> str:
    """Extract main error message"""
    
    # Look for specific error patterns
    patterns = [
        r'Error doing interaction[^\n]*\.\s*Connection Name[^\n]*cause[:\s]*([^\n]+)',
        r'NoSuchElementException[:\s]*([^\n]+)',
        r'org\.openqa\.selenium[^\n]*Exception[:\s]*([^\n]+)',
        r'Error[:\s]*([^\n]{20,200})',
        r'Exception[:\s]*([^\n]{20,200})',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, section, re.IGNORECASE)
        if match:
            error = match.group(1).strip()
            # Clean up and truncate
            error = error[:200] if len(error) > 200 else error
            return error
    
    # Default
    return "Test execution failed"


def extract_error_details_from_section(section: str) -> str:
    """Extract detailed error information including stack trace"""
    
    # Find the error block (usually starts with "Error doing" or exception name)
    error_start_patterns = [
        r'(Error doing interaction[^\n]*(?:\n[^\n]+){0,20})',
        r'(org\.openqa\.selenium[^\n]*(?:\n[^\n]+){0,20})',
        r'(NoSuchElementException[^\n]*(?:\n[^\n]+){0,15})',
    ]
    
    for pattern in error_start_patterns:
        match = re.search(pattern, section, re.IGNORECASE)
        if match:
            error_block = match.group(1)
            
            # Clean up the error block
            lines = error_block.split('\n')
            cleaned_lines = []
            
            for line in lines[:25]:  # Limit to 25 lines
                line = line.strip()
                if line and not line.startswith('---'):
                    cleaned_lines.append(line)
            
            return '\n'.join(cleaned_lines)
    
    # Fallback: return first 500 chars of section
    return section[:500].strip()


def extract_steps_from_testcase_section(section: str) -> List[Dict]:
    """
    Extract execution steps from test case section.
    
    Steps are marked with:
    - ⊙ for info/action
    - ⊗ for failure (red X)
    - ⊛ for success
    
    Format: "⊗ On SF accountPanel2 component in LWC"
    """
    steps = []
    
    # Pattern for steps with symbols
    step_pattern = r'([⊙⊗⊛])\s*([^\n]+?)(?=\n[⊙⊗⊛]|\n\n|\Z)'
    matches = re.finditer(step_pattern, section, re.DOTALL)
    
    for idx, match in enumerate(matches):
        symbol, step_text = match.groups()
        
        # Determine status based on symbol
        if symbol == '⊗':
            status = 'failed'
        elif symbol == '⊛':
            status = 'passed'
        else:  # ⊙
            status = 'info'
        
        # Clean step text
        step_text = step_text.strip()
        
        # Remove timestamp if present (e.g., "15:18:22(10:13.826)")
        step_text = re.sub(r'\d{2}:\d{2}:\d{2}\([^\)]+\)', '', step_text).strip()
        
        if step_text and len(step_text) > 5:
            steps.append({
                'text': step_text,
                'status': status,
                'index': idx
            })
    
    # If no steps found with symbols, try numbered format (2.11, 2.12, etc.)
    if not steps:
        numbered_pattern = r'(\d+\.\d+)\s+([^\n]+)'
        matches = re.finditer(numbered_pattern, section)
        
        for idx, match in enumerate(matches):
            step_num, step_text = match.groups()
            
            # Check context for failure indicators
            if re.search(r'error|failed|exception', step_text, re.IGNORECASE):
                status = 'failed'
            else:
                status = 'passed'
            
            steps.append({
                'text': f"{step_num} {step_text.strip()}",
                'status': status,
                'index': idx
            })
    
    return steps