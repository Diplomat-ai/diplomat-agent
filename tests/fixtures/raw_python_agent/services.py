"""Plain Python agent services for testing diplomat-agent.

These tools match the Phase 6 spec:
- make_payment: stripe.Charge.create with Pydantic Field(le=10000) → GUARDED or PARTIALLY_GUARDED
- bulk_delete: cursor.execute DELETE, no guards → UNGUARDED
- send_email: smtplib, no guards → UNGUARDED
"""

from __future__ import annotations

import smtplib
import sqlite3

import stripe


# -----------------------------------------------------------------------
# PARTIALLY_GUARDED — payment with Pydantic validation
# -----------------------------------------------------------------------
def make_payment(amount: float, recipient: str) -> dict:
    """Make a payment via Stripe. Has Pydantic Field validation."""
    from pydantic import BaseModel, Field

    class PaymentRequest(BaseModel):
        amount: float = Field(gt=0, le=10000)

    validated = PaymentRequest(amount=amount)
    charge = stripe.Charge.create(
        amount=int(validated.amount * 100),
        currency="usd",
        description=f"Payment to {recipient}",
    )
    return {"charge_id": charge["id"], "amount": validated.amount}


# -----------------------------------------------------------------------
# UNGUARDED — bulk DELETE, no guards
# -----------------------------------------------------------------------
def bulk_delete(ids: list) -> int:
    """Delete records by IDs. No guard, no confirmation."""
    conn = sqlite3.connect("app.db")
    cursor = conn.cursor()
    placeholders = ",".join("?" for _ in ids)
    cursor.execute(f"DELETE FROM records WHERE id IN ({placeholders})", ids)
    conn.commit()
    deleted = cursor.rowcount
    conn.close()
    return deleted


# -----------------------------------------------------------------------
# UNGUARDED — send email via SMTP, no guards
# -----------------------------------------------------------------------
def send_email(to: str, subject: str, body: str) -> bool:
    """Send an email. No rate limit, no auth check."""
    smtp = smtplib.SMTP("mail.example.com")
    message = f"Subject: {subject}\n\n{body}"
    smtp.sendmail("noreply@example.com", to, message)
    smtp.quit()
    return True
