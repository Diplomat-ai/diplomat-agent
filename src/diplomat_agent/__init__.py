"""diplomat-agent: governance scanner for agentic codebases."""
from __future__ import annotations

try:
    from importlib.metadata import version as _v
    __version__ = _v("diplomat-agent")
except Exception:  # package not installed (e.g. editable dev without install)
    __version__ = "0.0.0+dev"
