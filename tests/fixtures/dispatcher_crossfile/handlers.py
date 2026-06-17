"""GATE 5 cross-file fixture: handler class lives here, not in server.py."""
from __future__ import annotations

import subprocess


class Handlers:
    @staticmethod
    async def create(args: dict) -> list:
        subprocess.run(["docker", "run", args["image"]], check=True)
        return []
