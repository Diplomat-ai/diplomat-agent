"""Tools decorated by middleware — guards detected inter-procedurally."""
from __future__ import annotations
from middleware import require_policy, enforce_access, protected, require_role, throttle_writes, log_calls

class FakeSession:
    def delete(self, obj): ...
    def commit(self): ...
    def add(self, obj): ...

session = FakeSession()

@require_policy
def delete_record(record_id: str) -> dict:
    session.delete({"id": record_id}); session.commit(); return {"deleted": record_id}

@enforce_access
def update_record(record_id: str, data: dict) -> dict:
    session.add({"id": record_id, **data}); session.commit(); return {"updated": record_id}

@protected
def purge_user(user_id: str) -> dict:
    session.delete({"user_id": user_id}); session.commit(); return {"purged": user_id}

@require_role("admin")
def send_admin_email(recipient: str, body: str) -> dict:
    import smtplib; smtp = smtplib.SMTP("localhost")
    smtp.sendmail("admin@example.com", recipient, body); return {"sent": True}

@throttle_writes
def bulk_write(records: list) -> dict:
    [session.add(r) for r in records]; session.commit(); return {"count": len(records)}

@log_calls
def unguarded_write(data: dict) -> dict:
    session.add(data); session.commit(); return {"ok": True}
