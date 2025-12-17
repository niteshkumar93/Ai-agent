import xml.etree.ElementTree as ET

def extract_failed_tests(xml_file):
    tree = ET.parse(xml_file)
    root = tree.getroot()

    failed_tests = []

    for tc in root.findall("testcase"):
        name = tc.get("name")
        classname = tc.get("classname")
        time = tc.get("time")

        failure = tc.find("failure")

        if failure is not None:
            error_message = failure.get("message") or "Execution failed"
            details = failure.text.strip() if failure.text else ""

            failed_tests.append({
                "name": name,               # <-- required by AI engine
                "classname": classname,
                "time": time,
                "error": error_message,     # <-- required by AI engine
                "details": details,         # <-- used in Jira text
            })

    return failed_tests
