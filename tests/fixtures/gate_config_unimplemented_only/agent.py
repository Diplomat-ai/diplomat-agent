"""Fixture for --emit-gate-config: only categories without a gate family."""

import os


def cleanup_temp_file(path: str):
    """file_delete — no gate family yet."""
    os.remove(path)
