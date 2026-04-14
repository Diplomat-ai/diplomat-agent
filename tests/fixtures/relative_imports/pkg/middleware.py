def require_auth(fn):
    def wrapper(*args, **kwargs):
        if not current_user:
            raise PermissionError("Unauthenticated")
        return fn(*args, **kwargs)
    return wrapper
