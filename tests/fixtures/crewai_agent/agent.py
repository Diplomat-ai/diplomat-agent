"""Fake CrewAI support agent tools for testing diplomat-canary.

These tools match the Phase 6 spec:
- search_knowledge: read-only → LOW_RISK
- create_ticket: HTTP POST, no guards → UNGUARDED
- escalate_to_human: HTTP POST with auth check → PARTIALLY_GUARDED
"""

from __future__ import annotations

import requests


# -----------------------------------------------------------------------
# LOW_RISK — read-only search
# -----------------------------------------------------------------------
def search_knowledge(query: str) -> dict:
    """Search the knowledge base. Read-only."""
    response = requests.get(
        "https://kb.example.com/api/search",
        params={"q": query},
    )
    return response.json()


# -----------------------------------------------------------------------
# UNGUARDED — HTTP POST, no guards at all
# -----------------------------------------------------------------------
def create_ticket(title: str, priority: str, customer_id: str) -> dict:
    """Create a support ticket via external API. No guards."""
    response = requests.post(
        "https://api.helpdesk.example.com/tickets",
        json={"title": title, "priority": priority, "customer_id": customer_id},
    )
    response.raise_for_status()
    return response.json()


# -----------------------------------------------------------------------
# PARTIALLY_GUARDED — HTTP POST with auth check
# -----------------------------------------------------------------------
def escalate_to_human(ticket_id: str, reason: str, current_user=None) -> dict:
    """Escalate a ticket to a human agent. Has auth check but no rate limit."""
    if current_user is None or not current_user.is_authenticated:
        raise PermissionError("Authentication required")

    response = requests.post(
        "https://api.helpdesk.example.com/tickets/escalate",
        json={"ticket_id": ticket_id, "reason": reason},
    )
    return response.json()
