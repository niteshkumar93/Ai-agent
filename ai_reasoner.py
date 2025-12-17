import requests

MODEL_NAME = "llama3"   # Local fast 3B model
OLLAMA_URL = "http://localhost:11434/api/generate"


def generate_ai_summary(testcase, error_message, details):
    prompt = f"""
Analyze the following test failure and generate a Jira-style summary.

Testcase: {testcase}
Error: {error_message}
Details: {details}

Respond using this structure:

Summary:
Root Cause:
Suggested Fix:
"""

    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL_NAME,
                "prompt": prompt,
                "stream": False
            },
            timeout=120      # Increased timeout for first model load
        )

        data = response.json()
        return data.get("response", "").strip()

    except requests.exceptions.Timeout:
        return "❌ AI Timeout: Ollama took too long to respond. Try again or switch off AI."

    except Exception as e:
        return f"❌ Ollama Error: {str(e)}"
