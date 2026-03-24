"""Fake LangGraph agent workflows for testing diplomat-agent.

This file contains workflow orchestration code. The scanner should
detect side effects here too.
"""

from __future__ import annotations

import requests


def run_customer_onboarding(name: str, email: str, plan: str) -> dict:
    """Onboard a new customer. Makes external API calls, no guards."""
    response = requests.post(
        "https://api.example.com/customers",
        json={"name": name, "email": email, "plan": plan},
    )
    return response.json()


def check_workflow_status(workflow_id: str) -> dict:
    """Check workflow status. Read-only."""
    response = requests.get(
        f"https://api.example.com/workflows/{workflow_id}",
    )
    return response.json()
