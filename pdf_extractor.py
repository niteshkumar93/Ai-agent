# pdf_extractor.py

try:
    import PyPDF2
except ImportError:
    try:
        import pypdf as PyPDF2
    except ImportError:
        raise ImportError("Please install: pip install PyPDF2")

import re
from typing import List, Dict, Optional

def extract_pdf_failures(pdf_file) -> List[Dict]:
    """
    Extract failures from Provar PDF reports.
    
    NEW LOGIC:
    1. Find all .testcase sections in PDF
    2. For each testcase, check if "Outcome" shows "⊗ failed"
    3. Only process testcases with failed outcome
    4. Extract steps - ⊛ or ✓ = passed, ⊗ or ✗ = failed
    """
    
    pdf_file.seek(0)
    
    try:
        reader = PyPDF2.PdfReader(pdf_file)
    except Exception as e:
        return create_no_failure_record(f"PDF read error: {e}")
    
    if len(reader.pages) == 0:
        return create_no_failure_record("PDF has no pages")
    
    # Extract all pages text
    full_text = ""
    for page_num, page in enumerate(reader.pages):
        try:
            page_text = page.extract_text()
            full_text += page_text + f"\n--- PAGE {page_num + 1} ---\n"
        except Exception as e:
            print(f"Error extracting page {page_num + 1}: {e}")
            continue
    
    if not full_text:
        return create_no_failure_record("Could not extract text from PDF")
    
    # Extract metadata
    metadata = extract_metadata(full_text)
    
    # Find all test case sections with their outcomes
    testcase_sections = find_testcase_sections_with_outcomes(full_text)
    
    # Filter only FAILED test cases (Outcome: ⊗ failed)
    failed_testcases = []
    for tc_name, tc_section, outcome in testcase_sections:
        if outcome == 'failed':
            failed_testcases.append((tc_name, tc_section))
    
    if not failed_testcases:
        return create_no_failure_record(
            message="",
            metadata=metadata,
            is_clean_run=True
        )
    
    # Process each failed test case
    failures = []
    for tc_name, tc_section in failed_testcases:
        failure_details = extract_failure_details(tc_name, tc_section, metadata)
        if failure_details:
            failures.append(failure_details)
    
    return failures if failures else create_no_failure_record(
        message="",
        metadata=metadata,
        is_clean_run=True
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


def extract_metadata(text: str) -> Dict:
    """Extract execution time, browser, project from PDF"""
    metadata = {}
    
    # Extract Started time
    time_match = re.search(r'Started\s+(\d{2}\s+\w{3}\s+\d{4},\s+\d{2}:\d{2}:\d{2})', text)
    if time_match:
        metadata['time'] = time_match.group(1)
    else:
        metadata['time'] = "Unknown"
    
    # Extract project
    project_patterns = [
        r'Project[:\s]*(VF_Lightning_Windows|HYBRID_AUTOMATION_Pipeline|CPQ_\w+|QAM_\w+|Regmain[\w_-]+)',
        r'(VF_Lightning_Windows|HYBRID_AUTOMATION_Pipeline|CPQ_Classic|CPQ_Lightning)',
    ]
    for pattern in project_patterns:
        match = re.search(pattern, text)
        if match:
            metadata['project'] = match.group(1)
            break
    
    if 'project' not in metadata:
        metadata['project'] = ""
    
    # Extract browser
    browser_match = re.search(r'(Chrome|Firefox|Safari|Edge)[\s\d]*', text)
    metadata['browser'] = browser_match.group(1) if browser_match else "Unknown"
    
    return metadata


def find_testcase_sections_with_outcomes(text: str) -> List[tuple]:
    """
    Find all test case sections and their outcomes.
    
    Returns: [(testcase_name, section_text, outcome), ...]
    where outcome is 'failed', 'successful', or 'skipped'
    """
    testcases = []
    
    # Find all .testcase occurrences
    testcase_pattern = r'([A-Za-z0-9_]+\.testcase)'
    matches = list(re.finditer(testcase_pattern, text))
    
    for i, match in enumerate(matches):
        tc_name = match.group(1)
        section_start = match.start()
        
        # Get section until next testcase or end
        if i + 1 < len(matches):
            section_end = matches[i + 1].start()
        else:
            section_end = len(text)
        
        section = text[section_start:section_end]
        
        # Check if this section has "Summary" and "Outcome" - this is the main test case section
        if 'Summary' in section and 'Outcome' in section:
            outcome = extract_outcome_status(section)
            testcases.append((tc_name, section, outcome))
    
    return testcases


def extract_outcome_status(section: str) -> str:
    """
    Extract the outcome status from test case section.
    
    Looks for patterns:
    - "Outcome ⊗ failed" → failed
    - "Outcome ⊛ successful" or "✓ successful" → successful  
    - "Outcome ⊘ skipped" → skipped
    """
    
    # Pattern: Outcome followed by symbol and status word
    outcome_pattern = r'Outcome\s*(?:⊗|×|✗)?\s*(failed|failure)'
    if re.search(outcome_pattern, section, re.IGNORECASE):
        return 'failed'
    
    outcome_pattern = r'Outcome\s*(?:⊛|✓|✔)?\s*(successful|success|passed)'
    if re.search(outcome_pattern, section, re.IGNORECASE):
        return 'successful'
    
    outcome_pattern = r'Outcome\s*(?:⊘|○)?\s*(skipped|skip)'
    if re.search(outcome_pattern, section, re.IGNORECASE):
        return 'skipped'
    
    # Check for just the symbols near "Outcome"
    if re.search(r'Outcome\s*(?:\n|\s)*[⊗×✗]', section):
        return 'failed'
    
    if re.search(r'Outcome\s*(?:\n|\s)*[⊛✓✔]', section):
        return 'successful'
    
    return 'unknown'


def extract_failure_details(tc_name: str, section: str, metadata: Dict) -> Optional[Dict]:
    """Extract detailed failure information from a test case section"""
    
    # Extract error message
    error_msg = extract_error_message(section)
    
    # Extract full error details
    error_details = extract_error_details(section)
    
    # Extract steps from Output section
    steps = extract_steps_from_output(section)
    
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
    screenshot_available = bool(re.search(r'screenshot|capture|image', section, re.IGNORECASE))
    
    return {
        "name": tc_name,
        "testcase_path": tc_name,
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


def extract_error_message(section: str) -> str:
    """Extract main error message"""
    
    patterns = [
        r'\[NoSuchElementException:\s*([^\]]+)\]',
        r'NoSuchElementException:\s*([^\n]+)',
        r'Error doing interaction[^\n]*\.\s*[^\n]*cause[:\s]*[{\[]?([^}\]]+)[}\]]?',
        r'Exception:\s*([^\n]+)',
        r'Error:\s*([^\n]+)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, section, re.IGNORECASE)
        if match:
            error = match.group(1).strip()
            return error[:200] if len(error) > 200 else error
    
    return "Test execution failed"


def extract_error_details(section: str) -> str:
    """Extract detailed error information"""
    
    # Find error block starting with common error patterns
    error_start = -1
    error_patterns = [
        r'Error doing interaction',
        r'NoSuchElementException',
        r'org\.openqa\.selenium',
        r'Exception:',
    ]
    
    for pattern in error_patterns:
        match = re.search(pattern, section, re.IGNORECASE)
        if match:
            error_start = match.start()
            break
    
    if error_start == -1:
        return "Error details not found"
    
    # Extract from error start to next major section or reasonable limit
    error_end = error_start + 1000  # Limit to 1000 chars
    section_end = re.search(r'\n\n[A-Z]', section[error_start:])
    if section_end:
        error_end = min(error_end, error_start + section_end.start())
    
    error_block = section[error_start:error_end]
    
    # Clean up
    lines = error_block.split('\n')
    cleaned = []
    for line in lines[:20]:  # Max 20 lines
        line = line.strip()
        if line and not line.startswith('---'):
            cleaned.append(line)
    
    return '\n'.join(cleaned)


def extract_steps_from_output(section: str) -> List[Dict]:
    """
    Extract steps from Output section.
    
    CRITICAL LOGIC:
    - ⊛ or ✓ = PASSED step (green)
    - ⊗ or ✗ = FAILED step (red)
    - ⊙ = INFO step (blue - neither pass nor fail)
    
    Format in PDF:
    Output
    ⊛ Salesforce Connect: LWCTesting (Test)
      ⊙ Connecting to Salesforce as LWCTesting
    ⊗ On SF accountPanel2 component in LWC
      ⊙ Start of With Screen
    """
    
    steps = []
    
    # Find Output section
    output_match = re.search(r'Output\s*\n', section, re.IGNORECASE)
    if not output_match:
        return steps
    
    output_start = output_match.end()
    
    # Find end of Output section (next major section or end)
    output_end = len(section)
    next_section = re.search(r'\n\n[A-Z][a-z]+\s*\n', section[output_start:])
    if next_section:
        output_end = output_start + next_section.start()
    
    output_section = section[output_start:output_end]
    
    # Extract steps with symbols
    # Pattern: Symbol followed by text (may span multiple lines)
    step_pattern = r'([⊛⊗⊙✓✗○])\s*([^\n]+(?:\n(?![⊛⊗⊙✓✗○])[^\n]+)*)'
    
    matches = re.finditer(step_pattern, output_section)
    
    for idx, match in enumerate(matches):
        symbol, step_text = match.groups()
        
        # Determine status based on symbol
        if symbol in ['⊗', '✗']:
            status = 'failed'
        elif symbol in ['⊛', '✓']:
            status = 'passed'
        elif symbol == '⊙':
            status = 'info'
        elif symbol == '○':
            status = 'skipped'
        else:
            status = 'unknown'
        
        # Clean step text
        step_text = step_text.strip()
        
        # Remove sub-bullets (indented ⊙ lines are part of main step)
        lines = step_text.split('\n')
        main_line = lines[0].strip()
        
        # Remove timestamps like "15:18:41(09:32.420)"
        main_line = re.sub(r'\d{2}:\d{2}:\d{2}\([^\)]+\)', '', main_line).strip()
        
        if main_line and len(main_line) > 3:
            steps.append({
                'text': main_line,
                'status': status,
                'index': idx
            })
    
    return steps


def extract_failed_testcase_names(first_page: str) -> List[str]:
    """
    DEPRECATED - keeping for compatibility but not used in new logic.
    New logic checks Outcome status instead of summary.
    """
    return []