"""Test helper — should NOT appear in any report."""


async def create_test_task(db):
    """Test setup — creates a task for testing."""
    db.add(Task(name="test"))
    await db.commit()
