"""
LLM classification for support tickets.
Uses Google Gemini API.
"""
import json
import logging
import re
from typing import Optional
from django.conf import settings

logger = logging.getLogger(__name__)

# Prompt used for classification — included in codebase for review
CLASSIFY_PROMPT = """You are a support ticket classifier. Output ONLY valid JSON.

Rules (apply in order):
- If the ticket is about LOGIN, PASSWORD, RESET PASSWORD, UNLOCK ACCOUNT, or account access → category MUST be "account".
- If the ticket is about PAYMENT, REFUND, INVOICE, CHARGE, SUBSCRIPTION, or billing → category MUST be "billing".
- If the ticket is about API, webhook, endpoint, 500 error, server error, integration, or logs → category MUST be "technical".
- Otherwise use "general".

Priority rules:
- critical: outage, system down, data loss, breach, security incident, "urgent" or "restore"
- high: "no workaround", "blocking", "deadline", "can't access", "as soon as possible"
- low: "minor", "cosmetic", "not urgent", "feature request", "would be nice"
- medium: everything else

1. category: one of billing, technical, account, general
2. priority: one of low, medium, high, critical

Output format (no other text):
{"category": "billing|technical|account|general", "priority": "low|medium|high|critical"}

Ticket description:
"""
# End of prompt

# Keyword checks so we can correct LLM when it suggests wrong category
TECHNICAL_KEYWORDS = re.compile(
    r'\b(api|webhook|endpoint|500|502|503|server\s*error|integration|bug|crash|timeout|logs)\b',
    re.IGNORECASE
)
ACCOUNT_KEYWORDS = re.compile(
    r'\b(login|log\s*in|password|reset\s*password|unlock|account|permission|profile|access|locked\s*out)\b',
    re.IGNORECASE
)
BILLING_KEYWORDS = re.compile(
    r'\b(charge|charged|refund|invoice|payment|subscription|billed|billing|duplicate\s*charge)\b',
    re.IGNORECASE
)
# Outage/system-down: prefer technical over account when these appear
OUTAGE_OR_DOWN_KEYWORDS = re.compile(
    r'\b(outage|system\s*down|platform\s*down|been\s+down|is\s+down|full\s+outage|data\s*loss|breach)\b',
    re.IGNORECASE
)
# Priority: check critical first, then high, then low; default medium
CRITICAL_PRIORITY_KEYWORDS = re.compile(
    r'\b(outage|down\s*for|system\s*down|platform\s*down|been\s+down|full\s+outage|data\s*loss|breach|security\s*incident|urgent|restore|backup)\b',
    re.IGNORECASE
)
HIGH_PRIORITY_KEYWORDS = re.compile(
    r'\b(no\s*workaround|blocking|deadline|can\'t\s*access|cannot\s*access|as\s*soon\s*as\s*possible|critical\s*deadline)\b',
    re.IGNORECASE
)
LOW_PRIORITY_KEYWORDS = re.compile(
    r'\b(minor|cosmetic|not\s*urgent|feature\s*request|would\s*be\s*nice|small\s*issue)\b',
    re.IGNORECASE
)


def _suggested_priority_from_keywords(description: str) -> str:
    """Suggest priority from description when LLM fails or says medium."""
    if not description:
        return 'medium'
    if CRITICAL_PRIORITY_KEYWORDS.search(description):
        return 'critical'
    if HIGH_PRIORITY_KEYWORDS.search(description):
        return 'high'
    if LOW_PRIORITY_KEYWORDS.search(description):
        return 'low'
    return 'medium'


def _description_looks_technical(description: str) -> bool:
    return bool(description and TECHNICAL_KEYWORDS.search(description))


def _description_looks_account(description: str) -> bool:
    return bool(description and ACCOUNT_KEYWORDS.search(description))


def _description_looks_billing(description: str) -> bool:
    return bool(description and BILLING_KEYWORDS.search(description))


def _description_looks_outage_or_system_down(description: str) -> bool:
    """Outage/down takes precedence over account (e.g. 'can't log in because platform is down')."""
    return bool(description and OUTAGE_OR_DOWN_KEYWORDS.search(description))


def classify_ticket(description: str) -> Optional[dict]:
    """
    Call Google Gemini to suggest category and priority. Returns None on any failure.
    """
    if not description or not description.strip():
        return None
    # Outage/down → always technical + critical, before any LLM call (so it always works)
    if _description_looks_outage_or_system_down(description):
        return {'suggested_category': 'technical', 'suggested_priority': 'critical'}
    api_key = getattr(settings, 'GOOGLE_API_KEY', None) or ''
    if not api_key:
        # No key: use keyword fallbacks only (outage/down wins over account)
        pri = _suggested_priority_from_keywords(description)
        if _description_looks_outage_or_system_down(description):
            return {'suggested_category': 'technical', 'suggested_priority': 'critical'}
        if _description_looks_account(description):
            return {'suggested_category': 'account', 'suggested_priority': pri}
        if _description_looks_billing(description):
            return {'suggested_category': 'billing', 'suggested_priority': pri}
        if _description_looks_technical(description):
            return {'suggested_category': 'technical', 'suggested_priority': pri}
        return {'suggested_category': 'general', 'suggested_priority': pri}

    try:
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model='gemini-1.5-flash',
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
        # Override when LLM is wrong: prefer account/billing over technical when description clearly matches
        if category == 'technical':
            if _description_looks_account(description) and not _description_looks_technical(description):
                category = 'account'
            elif _description_looks_billing(description) and not _description_looks_technical(description):
                category = 'billing'
        elif category == 'general' and _description_looks_technical(description):
            category = 'technical'
        # Outage/system down → always technical (overrides account from "log in" in outage message)
        if _description_looks_outage_or_system_down(description):
            category = 'technical'
        # If LLM said medium but description suggests higher/lower priority, override
        if priority == 'medium':
            keyword_priority = _suggested_priority_from_keywords(description)
            if keyword_priority != 'medium':
                priority = keyword_priority
        # Outage/down → always critical priority
        if _description_looks_outage_or_system_down(description):
            priority = 'critical'
        return {'suggested_category': category, 'suggested_priority': priority}
    except Exception as e:
        logger.exception("LLM classify failed: %s", e)
        pri = _suggested_priority_from_keywords(description)
        if _description_looks_outage_or_system_down(description):
            return {'suggested_category': 'technical', 'suggested_priority': 'critical'}
        if _description_looks_account(description):
            return {'suggested_category': 'account', 'suggested_priority': pri}
        if _description_looks_billing(description):
            return {'suggested_category': 'billing', 'suggested_priority': pri}
        if _description_looks_technical(description):
            return {'suggested_category': 'technical', 'suggested_priority': pri}
        return {'suggested_category': 'general', 'suggested_priority': pri}
