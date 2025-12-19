import os
import requests
import json
from typing import List, Dict

# -------------------------------------------------------
# GROQ CONFIGURATION (FREE & FAST)
# -------------------------------------------------------
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.3-70b-versatile"  # Fast & accurate
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# -------------------------------------------------------
# FALLBACK: OpenAI (if Groq not available)
# -------------------------------------------------------
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = "gpt-4o-mini"


def generate_ai_summary(testcase, error_message, details):
    """
    Generate AI analysis for individual test failure.
    Uses Groq (free) as primary, OpenAI as fallback.
    """

    prompt = f"""Analyze this Provar/Salesforce test failure and provide a clear, actionable summary.

**Testcase:** {testcase}
**Error:** {error_message}
**Details:** {details}

Provide a structured analysis with:

1. **Root Cause** (2-3 sentences explaining why this failed)
2. **Suggested Fix** (specific actionable steps)
3. **Priority** (High/Medium/Low with reasoning)
4. **Potential Impact** (what this failure affects)

Keep it concise and actionable for QA engineers."""

    # Try Groq first (FREE!)
    if GROQ_API_KEY:
        try:
            return _call_groq(prompt)
        except Exception as e:
            # Fallback to OpenAI if Groq fails
            if OPENAI_API_KEY:
                try:
                    return _call_openai(prompt)
                except:
                    return f"❌ AI Error: {str(e)}"
            return f"⚠️ Groq Error: {str(e)}\n\nPlease check your GROQ_API_KEY in Streamlit secrets."
    
    # Try OpenAI if Groq not configured
    elif OPENAI_API_KEY:
        try:
            return _call_openai(prompt)
        except Exception as e:
            return f"❌ OpenAI Error: {str(e)}"
    
    return "⚠️ No AI service configured. Add GROQ_API_KEY or OPENAI_API_KEY to your Streamlit secrets."


def generate_batch_analysis(failures: List[Dict]) -> str:
    """
    🆕 NEW FEATURE: Analyze multiple failures together to find patterns.
    This helps identify common root causes across test failures.
    """
    
    if not failures or len(failures) == 0:
        return "No failures to analyze."
    
    # Prepare batch data
    failure_summary = "\n".join([
        f"- {f['testcase']}: {f['error'][:100]}" 
        for f in failures[:10]  # Limit to first 10 for token efficiency
    ])
    
    prompt = f"""Analyze these {len(failures)} test failures and identify patterns:

{failure_summary}

Provide:
1. **Common Patterns** - What failures are related?
2. **Root Causes** - Top 3 likely root causes
3. **Priority Actions** - What should be fixed first?
4. **Risk Assessment** - Overall impact on the test suite

Be concise and actionable."""

    if GROQ_API_KEY:
        try:
            return _call_groq(prompt)
        except Exception as e:
            return f"❌ Batch Analysis Error: {str(e)}"
    
    return "⚠️ Batch analysis requires GROQ_API_KEY configuration."


def generate_trend_analysis(historical_data: List[Dict]) -> str:
    """
    🆕 NEW FEATURE: Analyze trends over time.
    Identifies recurring issues and degradation patterns.
    """
    
    if not historical_data or len(historical_data) < 2:
        return "Need at least 2 data points for trend analysis."
    
    prompt = f"""Analyze these test execution trends:

{json.dumps(historical_data, indent=2)}

Provide insights on:
1. **Trend Direction** - Improving or degrading?
2. **Recurring Issues** - Tests that fail repeatedly
3. **Stability Score** - Rate overall test suite health (1-10)
4. **Recommendations** - Top 3 actions to improve stability

Be data-driven and specific."""

    if GROQ_API_KEY:
        try:
            return _call_groq(prompt)
        except Exception as e:
            return f"❌ Trend Analysis Error: {str(e)}"
    
    return "⚠️ Trend analysis requires GROQ_API_KEY configuration."


def generate_jira_ticket(testcase, error_message, details, ai_analysis=""):
    """
    🆕 NEW FEATURE: Generate ready-to-use Jira ticket content.
    """
    
    prompt = f"""Create a complete Jira ticket for this test failure:

**Testcase:** {testcase}
**Error:** {error_message}
**Details:** {details}
{f"**AI Analysis:** {ai_analysis}" if ai_analysis else ""}

Generate a Jira ticket with:
- **Title** (concise, searchable)
- **Description** (clear problem statement)
- **Steps to Reproduce**
- **Expected vs Actual Result**
- **Priority & Labels**
- **Assignee Suggestion** (role, e.g., "QA Lead" or "Dev Team")

Format it as ready-to-paste Jira content."""

    if GROQ_API_KEY:
        try:
            return _call_groq(prompt)
        except Exception as e:
            return f"❌ Jira Generation Error: {str(e)}"
    
    return "⚠️ Jira generation requires GROQ_API_KEY configuration."


def suggest_test_improvements(testcase, error_message, details):
    """
    🆕 NEW FEATURE: Get suggestions to make tests more robust.
    """
    
    prompt = f"""Analyze this test and suggest improvements to prevent future failures:

**Testcase:** {testcase}
**Error:** {error_message}
**Details:** {details}

Provide:
1. **Test Design Issues** - Flaws in the test approach
2. **Stability Improvements** - How to make it more reliable
3. **Best Practices** - What's missing?
4. **Code Suggestions** - Specific improvements (if applicable)

Focus on prevention and robustness."""

    if GROQ_API_KEY:
        try:
            return _call_groq(prompt)
        except Exception as e:
            return f"❌ Improvement Suggestions Error: {str(e)}"
    
    return "⚠️ Test improvement suggestions require GROQ_API_KEY configuration."


# -------------------------------------------------------
# INTERNAL API CALLS
# -------------------------------------------------------

def _call_groq(prompt: str) -> str:
    """Call Groq API (FREE & FAST)"""
    
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {
                "role": "system",
                "content": "You are a QA automation expert specializing in Salesforce Provar test analysis. Provide clear, actionable insights."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.3,
        "max_tokens": 1000
    }
    
    response = requests.post(GROQ_API_URL, headers=headers, json=payload, timeout=30)
    
    if response.status_code == 200:
        return response.json()["choices"][0]["message"]["content"].strip()
    else:
        raise Exception(f"Groq API error: {response.status_code} - {response.text}")


def _call_openai(prompt: str) -> str:
    """Call OpenAI API (FALLBACK)"""
    
    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)
        
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "You are a QA automation expert specializing in Salesforce Provar test analysis."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            max_tokens=1000,
            temperature=0.3
        )
        
        return response.choices[0].message.content.strip()
    
    except ImportError:
        raise Exception("OpenAI library not installed. Run: pip install openai")