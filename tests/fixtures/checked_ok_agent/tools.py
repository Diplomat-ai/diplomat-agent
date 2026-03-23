"""Fixture for testing # checked:ok and # canary:ok recognition."""

from __future__ import annotations

import stripe


class FakeSession:
    def add(self, obj): ...
    def commit(self): ...
    def delete(self, obj): ...


session = FakeSession()


def confirmed_with_checked_ok(amount: float) -> dict:
    """This tool has been reviewed and acknowledged."""
    result = stripe.Refund.create(amount=int(amount * 100))  # checked:ok — validated at API layer
    return {"refund_id": result["id"]}


def confirmed_with_canary_ok(customer_id: str) -> dict:
    """This tool has been reviewed using the legacy marker."""
    session.delete({"id": customer_id})  # canary:ok — reviewed by team lead
    session.commit()
    return {"deleted": customer_id}


def still_unguarded(data: dict) -> dict:
    """This tool has no marker — should remain unguarded."""
    session.add(data)
    session.commit()
    return {"saved": True}
