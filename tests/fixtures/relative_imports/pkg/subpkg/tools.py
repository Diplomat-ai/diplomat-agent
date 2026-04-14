from ..middleware import require_auth

@require_auth
def delete_item(item_id):
    db.delete(item_id)
    db.commit()
