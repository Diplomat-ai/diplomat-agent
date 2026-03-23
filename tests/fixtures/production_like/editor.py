async def save_version(workflow_id: str, content: dict, db=None):
    """Direct ORM mutation + commit — no session.add visible."""
    entity = await get_entity(workflow_id)
    entity.content_data = content
    entity.version += 1
    await db.commit()

async def update_field(workflow_id: str, field: str, value: str, db=None):
    """Field update + commit — no validation."""
    entity = await get_entity(workflow_id)
    setattr(entity, field, value)
    await db.commit()
