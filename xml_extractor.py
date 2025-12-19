import xml.etree.ElementTree as ET
from typing import List, Dict


def extract_failed_tests(xml_file) -> List[Dict]:
    """
    Always returns a list.
    - If failures exist → list of failed testcases
    - If NO failures → list with ONE metadata-only record
    """

    xml_file.seek(0)  # 🔑 IMPORTANT for Streamlit re-runs
    tree = ET.parse(xml_file)
    root = tree.getroot()

    # --------------------------------------------------
    # GLOBAL PROPERTIES (report-level)
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
    for testcase in root.findall(".//testcase"):

        failure = testcase.find("failure")
        if failure is not None:
            failures.append({
                "name": testcase.attrib.get("name"),
                "testcase_path": testcase.attrib.get("classname"),
                "error": failure.attrib.get("message", "Execution failed"),
                "details": (failure.text or "").strip(),
                "webBrowserType": web_browser,
                "projectCachePath": project_cache_path,
            })

    # --------------------------------------------------
    # ZERO FAILURE HANDLING (VERY IMPORTANT)
    # --------------------------------------------------
    if not failures:
        # Return ONE metadata-only row
        return [{
            "name": "__NO_FAILURES__",
            "testcase_path": "",
            "error": "",
            "details": "",
            "webBrowserType": web_browser,
            "projectCachePath": project_cache_path,
            "_no_failures": True,  # 🔑 flag for app.py
        }]

    return failures
import xml.etree.ElementTree as ET

def extract_failed_tests(xml_file):
    tree = ET.parse(xml_file)
    root = tree.getroot()

    # -------------------------------
    # GLOBAL PROPERTIES
    # -------------------------------
    properties = {}
    props_node = root.find("properties")

    if props_node is not None:
        for prop in props_node.findall("property"):
            properties[prop.attrib.get("name")] = prop.attrib.get("value")

    web_browser = properties.get("webBrowserType", "Unknown")
    project_cache_path = properties.get("projectCachePath", "")

    failures = []

    # -------------------------------
    # FAILED TESTCASES
    # -------------------------------
    for testcase in root.findall("testcase"):
        failure = testcase.find("failure")
        if failure is not None:
            failures.append({
                "name": testcase.attrib.get("name"),
                "testcase_path": testcase.attrib.get("classname"),
                "error": failure.attrib.get("message", "Execution failed"),
                "details": (failure.text or "").strip(),
                "webBrowserType": web_browser,
                "projectCachePath": project_cache_path,
            })

    # 🔑 IMPORTANT: return metadata even if no failures
    if not failures:
        return [{
            "name": "__NO_FAILURES__",
            "testcase_path": "",
            "error": "",
            "details": "",
            "webBrowserType": web_browser,
            "projectCachePath": project_cache_path,
        }]

    return failures
