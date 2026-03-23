# Simule un décorateur orchestrateur
def activity_defn(func):
    """Mock Temporal activity decorator."""
    return func

@activity_defn
async def save_data(data: dict):
    """Save data — no idempotency key."""
    session.add(Record(**data))
    await session.commit()
    return str(data["id"])

@activity_defn
async def update_status(record_id: str, status: str, retry_count: int):
    """Update status — retry_count has no upper bound."""
    record = await session.get(Record, record_id)
    record.status = status
    record.retry_count = retry_count
    await session.commit()
