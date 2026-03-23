"""Fake CrewAI support agent tools for testing agent-canary.

Tools use CrewAI-style patterns but the scanner must detect them
purely via side-effect patterns, not framework decorators.
"""

from __future__ import annotations

import requests
import httpx


# -----------------------------------------------------------------------
# UNGUARDED — HTTP write (external API POST), no rate limit
# -----------------------------------------------------------------------
def escalate_ticket(ticket_id: str, reason: str) -> dict:
    """Escalate a support ticket via external API. No rate limit."""
    response = requests.post(
        "https://api.helpdesk.example.com/tickets/escalate",
        json={"ticket_id": ticket_id, "reason": reason},
    )
    response.raise_for_status()
    return response.json()


# -----------------------------------------------------------------------
# UNGUARDED — publish content without approval
# -----------------------------------------------------------------------
def publish_knowledge_article(title: str, content: str) -> dict:
    """Publish a knowledge base article. No approval step."""
    response = httpx.post(
        "https://kb.example.com/api/articles",
        json={"title": title, "content": content, "status": "published"},
    )
    return response.json()


# -----------------------------------------------------------------------
# LOW_RISK — GET request only
# -----------------------------------------------------------------------
def get_ticket_details(ticket_id: str) -> dict:
    """Fetch ticket details. Read-only."""
    response = requests.get(
        f"https://api.helpdesk.example.com/tickets/{ticket_id}"
    )
    return response.json()


# -----------------------------------------------------------------------
# PARTIALLY_GUARDED — email with partial guard (if check)
# -----------------------------------------------------------------------
def send_customer_reply(customer_email: str, reply_text: str) -> bool:
    """Send a reply to the customer. Partial guard on reply length."""
    import smtplib

    # Partial guard: length check but no rate limit
    if len(reply_text) > 10000:
        raise ValueError("Reply too long")

    smtp = smtplib.SMTP("mail.example.com")
    smtp.sendmail("support@example.com", customer_email, reply_text)
    return True
