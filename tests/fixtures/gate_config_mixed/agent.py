"""Fixture for --emit-gate-config: one implemented family (payment), one
implemented family (email), and one unimplemented family (file_delete)."""

import os

import stripe


def charge_customer(customer_id: str, amount: int):
    """Real payment call — payment category, implemented gate family."""
    return stripe.PaymentIntent.create(amount=amount, currency="usd", customer=customer_id)


def send_email(to: str, subject: str, body: str):
    """Real email send — email category, implemented gate family."""
    return send_mail(to=to, subject=subject, body=body)


def cleanup_temp_file(path: str):
    """Real file delete — file_delete category, no gate family yet."""
    os.remove(path)
