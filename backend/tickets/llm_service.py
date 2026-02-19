"""
LLM classification for support tickets.
Uses Google Gemini API. Prompt is included for review as per assignment.
"""
import json
import logging
import re
from typing import Optional
from django.conf import settings

logger = logging.getLogger(__name__)

# Prompt used for classification — included in codebase for review
CLASSIFY_PROMPT = """You are a support ticket classifier. Given a ticket description, respond with exactly two values:

1. category: one of billing, technical, account, general
   - billing: payments, refunds, invoices, subscription issues
   - technical: bugs, errors, integration, API, performance
   - account: login, password, profile, access, permissions
   - general: anything that doesn't fit the above

2. priority: one of low, medium, high, critical
   - low: minor questions, feature requests, cosmetic issues
   - medium: non-urgent problems, workarounds exist
   - high: significant impact, no workaround, blocking work
   - critical: outage, security, data loss, system down

Respond with ONLY a JSON object, no other text. Format:
{"category": "<one of billing|technical|account|general>", "priority": "<one of low|medium|high|critical>"}

Ticket description:
"""
# End of prompt


def classify_ticket(description: str) -> Optional[dict]:
    """
    Call Google Gemini to suggest category and priority. Returns None on any failure.
    """
    api_key = getattr(settings, 'GOOGLE_API_KEY', None) or ''
    if not api_key or not description or not description.strip():
        return None

    try:
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=CLASSIFY_PROMPT + description.strip(),
            config=types.GenerateContentConfig(
                temperature=0,
                max_output_tokens=100,
            ),
        )
        text = (response.text or '').strip()
        if not text:
            return None
        # Extract JSON from markdown code block if present
        if '```' in text:
            match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
            if match:
                text = match.group(1)
        data = json.loads(text)
        category = (data.get('category') or '').lower()
        priority = (data.get('priority') or '').lower()
        valid_categories = {'billing', 'technical', 'account', 'general'}
        valid_priorities = {'low', 'medium', 'high', 'critical'}
        if category not in valid_categories or priority not in valid_priorities:
            return None
        return {'suggested_category': category, 'suggested_priority': priority}
    except Exception as e:
        logger.exception("LLM classify failed: %s", e)
        return None
