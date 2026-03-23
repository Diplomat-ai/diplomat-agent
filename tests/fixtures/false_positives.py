"""False positive fixture — these functions must NOT be detected as side effects."""


def clean_data(data: str) -> str:
    """remove_null_bytes - utilitaire, pas un delete."""
    return remove_null_bytes(data)


def check_health(session):
    """SELECT 1 healthcheck - read only."""
    result = session.execute(text("SELECT 1"))
    return result.scalar()


def get_publication_date(publication):
    """Lecture d'attribut - pas un publish."""
    return publication.published_at.isoformat()


def list_items(db):
    """SQLAlchemy select - read only."""
    result = db.execute(select(Item).limit(50))
    return result.scalars().all()


def format_name(name: str) -> str:
    """str.removeprefix - pas un delete."""
    return name.removeprefix("Dr. ")
