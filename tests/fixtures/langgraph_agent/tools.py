"""Fake LangGraph e-commerce agent tools for testing diplomat-agent.

This file intentionally contains tools with various governance postures:
- process_refund: payment, UNGUARDED
- update_order: database_write, PARTIALLY_GUARDED
- get_order: read-only, LOW_RISK
- delete_customer: database_delete, UNGUARDED
- send_notification: email, GUARDED
"""

from __future__ import annotations

import stripe

# Fake ORM session
class FakeSession:
    def add(self, obj): ...
    def commit(self): ...
    def delete(self, obj): ...

session = FakeSession()


# -----------------------------------------------------------------------
# UNGUARDED — payment side effect, zero guards
# -----------------------------------------------------------------------
def process_refund(amount: float, customer_id: str) -> dict:
    """Process a refund for a customer. No guards whatsoever."""
    result = stripe.Refund.create(
        amount=int(amount * 100),
        customer=customer_id,
    )
    return {"refund_id": result["id"], "status": "processed"}


# -----------------------------------------------------------------------
# PARTIALLY_GUARDED — database write with partial validation only
# -----------------------------------------------------------------------
def update_order(order_id: str, status: str, discount: float = 0.0) -> dict:
    """Update an order status. Has partial input validation."""
    # Partial guard: validates discount is non-negative, but no upper bound
    if discount < 0:
        raise ValueError("Discount cannot be negative")

    order = {"id": order_id, "status": status, "discount": discount}
    session.add(order)
    session.commit()
    return {"order_id": order_id, "new_status": status}


# -----------------------------------------------------------------------
# LOW_RISK — read-only, no guards needed
# -----------------------------------------------------------------------
def get_order(order_id: str) -> dict:
    """Fetch an order by ID. Read-only."""
    import requests
    response = requests.get(f"https://api.example.com/orders/{order_id}")
    return response.json()


# -----------------------------------------------------------------------
# UNGUARDED — database delete, zero guards
# -----------------------------------------------------------------------
def delete_customer(customer_id: str) -> dict:
    """Delete a customer record. No confirmation, no auth check."""
    customer = {"id": customer_id}
    session.delete(customer)
    session.commit()
    return {"deleted": customer_id}


# -----------------------------------------------------------------------
# GUARDED — email with rate limit + auth check
# -----------------------------------------------------------------------
def send_notification(email: str, message: str, current_user=None) -> dict:
    """Send a notification email. Has rate limiting and auth check."""
    import smtplib

    # Auth guard
    if current_user is None or not current_user.is_authenticated:
        raise PermissionError("Authentication required")

    # Assume rate_limit decorator is applied elsewhere (import present)
    smtp = smtplib.SMTP("localhost")
    smtp.sendmail("noreply@example.com", email, message)
    return {"sent": True, "recipient": email}
