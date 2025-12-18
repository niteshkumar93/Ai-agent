import xml.etree.ElementTree as ET

def extract_failed_tests(xml_file):
    tree = ET.parse(xml_file)
    root = tree.getroot()

    # --------------------------------------------------
    # GLOBAL PROPERTIES (common for full report)
    # --------------------------------------------------
    properties = {}
    props_node = root.find("properties")

    if props_node is not None:
        for prop in props_node.findall("property"):
            properties[prop.attrib.get("name")] = prop.attrib.get("value")

    web_browser = properties.get("webBrowserType", "Unknown")
    project_cache_path = properties.get("projectCachePath", "")

    failures = []

    # --------------------------------------------------
    # FAILED TESTCASES
    # --------------------------------------------------
    for testcase in root.findall("testcase"):
        failure = testcase.find("failure")
        if failure is not None:
            failures.append({
                "name": testcase.attrib.get("name"),
                "testcase_path": testcase.attrib.get("classname"),
                "error": failure.attrib.get("message", "Execution failed"),
                "details": (failure.text or "").strip(),
                "webBrowserType": web_browser,
                "projectCachePath": project_cache_path
            })

    return failures
