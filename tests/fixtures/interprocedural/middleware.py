"""Middleware decorators whose names have no guard keywords."""
from __future__ import annotations
class AuthError(Exception): pass
class PermissionDenied(Exception): pass

def require_policy(func):
    def wrapper(*args, **kwargs):
        if not current_user: raise AuthError("Unauthenticated")
        return func(*args, **kwargs)
    return wrapper

def enforce_access(func):
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated: abort(403)
        return func(*args, **kwargs)
    return wrapper

def protected(func):
    def wrapper(*args, **kwargs):
        if not is_authorized(current_user): raise PermissionDenied("denied")
        return func(*args, **kwargs)
    return wrapper

def require_role(role: str):
    def decorator(func):
        def wrapper(*args, **kwargs):
            if not current_user.has_role(role): raise AuthError(f"Role {role!r} required")
            return func(*args, **kwargs)
        return wrapper
    return decorator

def throttle_writes(func):
    def wrapper(*args, **kwargs):
        check_rate_limit(current_user)
        return func(*args, **kwargs)
    return wrapper

def log_calls(func):
    def wrapper(*args, **kwargs):
        print(f"Calling {func.__name__}")
        return func(*args, **kwargs)
    return wrapper
