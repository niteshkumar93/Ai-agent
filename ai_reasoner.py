import os
import requests

# -------------------------------------------------------
# ENV DETECTION
# -------------------------------------------------------
IS_CLOUD = os.getenv("STREAMLIT_CLOUD") == "true"

# -------------------------------------------------------
# LOCAL OLLAMA CONFIG
# -------------------------------------------------------
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3"

# -------------------------------------------------------
# CLOUD CONFIG (OpenAI)
# -------------------------------------------------------
if IS_CLOUD:
    import openai
    openai.api_key = os.getenv("OPENAI_API_KEY")
    OPENAI_MODEL = "gpt-4o-mini"


def generate_ai_summary(testcase, error_message, details):

    prompt = f"""
Analyze this test failure and generate a Jira-style summary.

Testcase: {testcase}
Error: {error_message}
Details: {details}

Return format:
Summary:
Root Cause:
Suggested Fix:
"""

    # ---------------------------------------------------
    # ☁️ CLOUD MODE — OpenAI
    # ---------------------------------------------------
    if IS_CLOUD:
        try:
            response = openai.ChatCompletion.create(
                model=OPENAI_MODEL,
                messages=[{"role": "user", "content": prompt}],
                timeout=30
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            return f"❌ Cloud AI Error: {str(e)}"

    # ---------------------------------------------------
    # 🖥️ LOCAL MODE — OLLAMA
    # ---------------------------------------------------
    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False
            },
            timeout=120
        )
        return response.json().get("response", "").strip()

    except requests.exceptions.Timeout:
        return "❌ Ollama Timeout"
    except Exception as e:
        return f"❌ Ollama Error: {str(e)}"
