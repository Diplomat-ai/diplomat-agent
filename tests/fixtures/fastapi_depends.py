"""FastAPI routes with Depends() auth — should be detected as having auth checks."""


# Simulated DB session
class FakeDB:
    def add(self, obj): ...
    def delete(self, obj): ...
    async def commit(self): ...

db = FakeDB()


class Task:
    def __init__(self, **kw): ...


async def get_current_org():
    """Auth dependency."""
    pass


async def delete_workflow(
    workflow_id: str,
    org=Depends(get_current_org),
):
    """Delete with auth — should be PARTIALLY_GUARDED, not UNGUARDED."""
    await db.delete(workflow_id)
    await db.commit()


async def create_task(
    data: dict,
    org=Depends(get_current_org),
):
    """Create with auth — should be PARTIALLY_GUARDED."""
    db.add(Task(**data))
    await db.commit()


async def create_without_auth(data: dict):
    """Create without auth — should stay UNGUARDED."""
    db.add(Task(**data))
    await db.commit()


from fastapi.security import HTTPBearer

security_scheme = HTTPBearer()


async def protected_route(
    credentials=Security(security_scheme),
):
    """Security() guard — should be detected as auth_check."""
    data = await db.execute(select(Item))
    await db.commit()
