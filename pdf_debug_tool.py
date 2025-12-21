# pdf_debug_tool.py
"""
Standalone PDF debugging tool to understand PDF structure
Run this separately to see what's extracted from your PDF
"""

try:
    import PyPDF2
except ImportError:
    try:
        import pypdf as PyPDF2
    except ImportError:
        print("Please install: pip install PyPDF2")
        exit(1)

import re
import sys

def debug_pdf(pdf_path: str):
    """Debug PDF extraction to see what content is available"""
    
    print("=" * 80)
    print(f"DEBUGGING PDF: {pdf_path}")
    print("=" * 80)
    
    with open(pdf_path, 'rb') as file:
        reader = PyPDF2.PdfReader(file)
        
        print(f"\n✓ PDF has {len(reader.pages)} pages")
        
        # Extract text from all pages
        full_text = ""
        for page_num, page in enumerate(reader.pages):
            print(f"\n--- Extracting Page {page_num + 1} ---")
            try:
                page_text = page.extract_text()
                print(f"✓ Extracted {len(page_text)} characters")
                full_text += page_text + f"\n\n--- END PAGE {page_num + 1} ---\n\n"
            except Exception as e:
                print(f"✗ Error: {e}")
        
        # Save full text
        output_file = "pdf_extracted_text.txt"
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(full_text)
        print(f"\n✓ Full text saved to: {output_file}")
        
        # Analysis
        print("\n" + "=" * 80)
        print("TEXT ANALYSIS")
        print("=" * 80)
        
        # Look for test cases
        testcases = re.findall(r'([A-Za-z0-9_.\-/]+\.testcase)', full_text, re.IGNORECASE)
        print(f"\n✓ Found {len(testcases)} test case references:")
        for tc in set(testcases[:10]):  # Show first 10 unique
            print(f"  - {tc}")
        
        # Look for failure keywords
        failure_keywords = ['failed', 'error', 'exception', '✗', '×', '❌', 'FAIL']
        print(f"\n✓ Checking for failure indicators:")
        for keyword in failure_keywords:
            count = len(re.findall(keyword, full_text, re.IGNORECASE))
            if count > 0:
                print(f"  - '{keyword}': {count} occurrences")
        
        # Look for step markers
        step_patterns = [
            (r'\d+\.\d+\s+', 'Numbered steps (e.g., 2.11)'),
            (r'Step\s+\d+', 'Step N format'),
            (r'(?:On|Click|Set|Verify|Wait|Enter)', 'Action keywords'),
            (r'[✓✗×❌]', 'Status symbols'),
        ]
        
        print(f"\n✓ Checking for step patterns:")
        for pattern, description in step_patterns:
            matches = re.findall(pattern, full_text, re.IGNORECASE)
            if matches:
                print(f"  - {description}: {len(matches)} found")
                print(f"    Example: {matches[0] if matches else 'N/A'}")
        
        # Look for error messages
        print(f"\n✓ Looking for error messages:")
        error_patterns = [
            r'Error[:\s]*([^\n]{20,100})',
            r'Exception[:\s]*([^\n]{20,100})',
            r'Failed[:\s]*([^\n]{20,100})',
        ]
        
        for pattern in error_patterns:
            matches = re.findall(pattern, full_text, re.IGNORECASE)
            if matches:
                print(f"  Found {len(matches)} error messages")
                print(f"  Example: {matches[0][:80]}...")
                break
        
        # Look for screenshots
        screenshot_mentions = len(re.findall(r'screenshot|image|capture', full_text, re.IGNORECASE))
        print(f"\n✓ Screenshot mentions: {screenshot_mentions}")
        
        # Sample text
        print("\n" + "=" * 80)
        print("SAMPLE TEXT (First 1000 characters)")
        print("=" * 80)
        print(full_text[:1000])
        print("\n... (see full text in pdf_extracted_text.txt)")
        
        # Look for specific patterns in your PDF
        print("\n" + "=" * 80)
        print("PROVAR-SPECIFIC PATTERNS")
        print("=" * 80)
        
        # Browser type
        browser_match = re.search(r'(?:Browser|webBrowserType)[:\s]*([^\n]+)', full_text, re.IGNORECASE)
        if browser_match:
            print(f"✓ Browser: {browser_match.group(1).strip()}")
        else:
            print("✗ Browser type not found")
        
        # Project path
        project_match = re.search(r'(?:Project|Path)[:\s]*([^\n]*(?:Jenkins|workspace|VF_Lightning)[^\n]*)', full_text, re.IGNORECASE)
        if project_match:
            print(f"✓ Project: {project_match.group(1).strip()[:80]}...")
        else:
            print("✗ Project path not found")
        
        # Execution time
        time_match = re.search(r'(?:Time|Date)[:\s]*([^\n]{10,50})', full_text, re.IGNORECASE)
        if time_match:
            print(f"✓ Time: {time_match.group(1).strip()}")
        else:
            print("✗ Execution time not found")
        
        print("\n" + "=" * 80)
        print("DEBUG COMPLETE")
        print("=" * 80)
        print(f"\nReview '{output_file}' to see the full extracted text")
        print("This will help identify the correct patterns for your PDF format")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python pdf_debug_tool.py <path_to_pdf>")
        print("\nExample:")
        print("  python pdf_debug_tool.py Test_Run_Report.pdf")
    else:
        debug_pdf(sys.argv[1])