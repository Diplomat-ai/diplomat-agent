"""Plain Python agent tools (no framework) for testing diplomat-agent.

Uses requests, SQLAlchemy-style patterns, and stripe directly.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import requests
import stripe


# Simulated SQLAlchemy-style objects
class FakeDB:
    def commit(self): ...
    def add(self, obj): ...
    def delete(self, obj): ...
    def flush(self): ...

db = FakeDB()


# -----------------------------------------------------------------------
# UNGUARDED — stripe payment
# -----------------------------------------------------------------------
def charge_customer(customer_id: str, amount: float, description: str) -> dict:
    """Charge a customer via Stripe. No validation on amount, no rate limit."""
    charge = stripe.Charge.create(
        amount=int(amount * 100),
        currency="usd",
        customer=customer_id,
        description=description,
    )
    return {"charge_id": charge["id"], "amount": amount}


# -----------------------------------------------------------------------
# UNGUARDED — file deletion
# -----------------------------------------------------------------------
def cleanup_user_data(user_id: str, data_dir: str) -> bool:
    """Delete all files for a user. No confirmation, no auth check."""
    user_path = Path(data_dir) / user_id
    shutil.rmtree(str(user_path))
    return True


# -----------------------------------------------------------------------
# UNGUARDED — database delete
# -----------------------------------------------------------------------
def purge_old_records(table_name: str, days_old: int) -> int:
    """Delete records older than N days. No bounds on days_old."""
    import sqlite3
    conn = sqlite3.connect("app.db")
    cursor = conn.cursor()
    cursor.execute(
        f"DELETE FROM {table_name} WHERE created_at < datetime('now', '-{days_old} days')"
    )
    conn.commit()
    deleted = cursor.rowcount
    conn.close()
    return deleted


# -----------------------------------------------------------------------
# PARTIALLY_GUARDED — database write with partial validation
# -----------------------------------------------------------------------
def create_user(username: str, email: str, role: str = "user") -> dict:
    """Create a new user. Has partial validation (username length)."""
    if len(username) < 3:
        raise ValueError("Username too short")

    user = {"username": username, "email": email, "role": role}
    db.add(user)
    db.commit()
    return user


# -----------------------------------------------------------------------
# LOW_RISK — read only
# -----------------------------------------------------------------------
def fetch_exchange_rates(base_currency: str = "USD") -> dict:
    """Fetch current exchange rates. Read-only GET request."""
    response = requests.get(
        f"https://api.exchangerate.example.com/latest?base={base_currency}"
    )
    return response.json()


# -----------------------------------------------------------------------
# GUARDED — full Pydantic validation + auth
# -----------------------------------------------------------------------
def transfer_funds(
    from_account: str,
    to_account: str,
    amount: float,
    idempotency_key: str,
    current_user=None,
) -> dict:
    """Transfer funds between accounts. Has idempotency key and auth check."""
    from pydantic import BaseModel, Field

    class TransferRequest(BaseModel):
        amount: float = Field(gt=0, le=10000)

    # Auth check
    if current_user is None:
        raise PermissionError("Authentication required")

    # Validate with Pydantic
    validated = TransferRequest(amount=amount)

    result = stripe.Transfer.create(
        amount=int(validated.amount * 100),
        currency="usd",
        destination=to_account,
        idempotency_key=idempotency_key,
    )
    return {"transfer_id": result["id"]}
