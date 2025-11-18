"""
Dual Chat System
1. ICP Builder Chat - Help users define their ICP
2. Research Assistant - Deep dive on companies
"""

import os
import httpx
import json
from typing import List, Dict

# Grok API
GROK_API_KEY = os.getenv("GROK_API_KEY")
GROK_API_URL = "https://api.x.ai/v1/chat/completions"

# ============================================================================
# ICP BUILDER CHAT
# ============================================================================

async def handle_icp_chat(message: str, user: dict, history: List[Dict] = None) -> dict:
    """
    ICP Builder Chat - Help users define their ideal customer profile
    """
    if history is None:
        history = []

    # System prompt for ICP builder
    system_prompt = """You are an expert ICP (Ideal Customer Profile) consultant.
Your goal is to help users define their perfect target customer through conversation.

Ask strategic questions about:
1. Industry/vertical
2. Company size (employees)
3. Location/geography
4. Pain points they solve
5. Decision-maker role
6. Budget/revenue indicators

Extract structured ICP criteria from the conversation. When you have enough information,
output JSON in this format:
{
  "ready": true,
  "icp": {
    "industry": "SaaS",
    "min_size": 50,
    "max_size": 200,
    "location": "United States",
    "pain_points": "Manual data entry, inefficient workflows",
    "decision_maker": "VP of Operations"
  }
}

If you need more information, keep asking questions naturally."""

    # Build messages
    messages = [
        {"role": "system", "content": system_prompt}
    ]

    # Add history
    for msg in history:
        messages.append(msg)

    # Add current message
    messages.append({"role": "user", "content": message})

    # Call Grok
    async with httpx.AsyncClient() as client:
        response = await client.post(
            GROK_API_URL,
            headers={
                "Authorization": f"Bearer {GROK_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "grok-2-latest",
                "messages": messages,
                "temperature": 0.7
            }
        )
        data = response.json()

    assistant_message = data["choices"][0]["message"]["content"]

    # Try to parse JSON (if ICP is ready)
    try:
        # Look for JSON in response
        if "{" in assistant_message and "}" in assistant_message:
            json_start = assistant_message.find("{")
            json_end = assistant_message.rfind("}") + 1
            json_str = assistant_message[json_start:json_end]
            parsed = json.loads(json_str)

            if parsed.get("ready"):
                return {
                    "message": assistant_message,
                    "icp_ready": True,
                    "icp": parsed["icp"]
                }
    except:
        pass  # Not JSON, keep chatting

    return {
        "message": assistant_message,
        "icp_ready": False
    }

# ============================================================================
# RESEARCH ASSISTANT CHAT
# ============================================================================

async def handle_research_chat(company: str, user: dict) -> dict:
    """
    Research Assistant - Deep dive on a specific company
    Uses web search + Grok to gather intel
    """
    # Build research prompt
    prompt = f"""Research the company: {company}

Provide a comprehensive analysis including:
1. What they do (products/services)
2. Target market & customers
3. Company size (estimated employees)
4. Recent news/funding
5. Key decision makers (if known)
6. Pain points they likely have
7. Why they might be a good prospect

Be concise but thorough. Format as markdown."""

    # Call Grok with web search enabled
    async with httpx.AsyncClient() as client:
        response = await client.post(
            GROK_API_URL,
            headers={
                "Authorization": f"Bearer {GROK_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "grok-2-latest",
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.3
            }
        )
        data = response.json()

    insights = data["choices"][0]["message"]["content"]

    return {
        "company": company,
        "insights": insights
    }

# ============================================================================
# CHAT HISTORY MANAGEMENT
# ============================================================================

# In-memory history (for demo)
# TODO: Move to Redis or database for production
chat_histories = {}

def save_chat_history(user_id: str, session_id: str, messages: List[Dict]):
    """Save chat history"""
    key = f"{user_id}:{session_id}"
    chat_histories[key] = messages

def get_chat_history(user_id: str, session_id: str) -> List[Dict]:
    """Get chat history"""
    key = f"{user_id}:{session_id}"
    return chat_histories.get(key, [])

def clear_chat_history(user_id: str, session_id: str):
    """Clear chat history"""
    key = f"{user_id}:{session_id}"
    if key in chat_histories:
        del chat_histories[key]
