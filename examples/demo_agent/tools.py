"""Demo agent with tool calls for testing agent-canary.

Run: agent-canary examples/demo_agent/
"""

from __future__ import annotations

import stripe
import requests
from functools import wraps


def rate_limit(max_calls: int = 10, period: int = 60):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*a, **kw):
            return fn(*a, **kw)
        return wrapper
    return decorator


def login_required(fn):
    @wraps(fn)
    def wrapper(*a, **kw):
        return fn(*a, **kw)
    return wrapper


# --- NO CHECKS: payment with no guard at all ---

def process_refund(customer_id: str, amount: float):
    """Refund a customer. No validation on amount, no rate limit, no idempotency."""
    refund = stripe.Refund.create(amount=int(amount * 100), payment_intent=customer_id)
    return refund


# --- PARTIAL: database write with auth but no rate limit ---

@login_required
def save_order(session, order_data: dict):
    """Save an order to the database. Has auth, but no rate limit or input validation."""
    order = session.add(order_data)
    session.commit()
    return order


# --- PARTIAL: HTTP write with rate limit but no auth ---

@rate_limit(max_calls=5, period=60)
def notify_webhook(url: str, payload: dict):
    """Send a webhook notification. Rate limited, but no auth or input validation on url."""
    response = requests.post(url, json=payload)
    return response.json()
