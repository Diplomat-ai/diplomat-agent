"""SARIF 2.1.0 reporter — produces SARIF JSON for GitHub Code Scanning.

Generates a SARIF v2.1.0 log consumable by ``github/codeql-action/upload-sarif``.
No external dependencies — uses only the stdlib ``json`` module.
"""

from __future__ import annotations

import json
from io import StringIO

from diplomat_agent import __version__
from diplomat_agent.models import ScanResult, Tool


_SARIF_VERSION = "2.1.0"
_SARIF_SCHEMA = "https://docs.oasis-open.org/sarif/sarif/v2.1.0/errata01/os/schemas/sarif-schema-2.1.0.json"

_LEVEL_MAP = {
    "UNGUARDED": "warning",
    "PARTIALLY_GUARDED": "note",
    "GUARDED": "none",
    "LOW_RISK": "none",
}


def _rule_id(tool: Tool) -> str:
    """Build a rule ID from the tool's primary effect category and verdict."""
    categories = sorted({se.category for se in tool.side_effects})
    primary = categories[0] if categories else "unknown"
    verdict = tool.verdict.lower().replace("_", "-")
    return f"diplomat-agent/{verdict}-{primary.replace('_', '-')}"


def _build_rules(tools: list[Tool]) -> list[dict]:
    """Deduplicate rules across all tools."""
    seen: dict[str, dict] = {}
    for tool in tools:
        if tool.verdict == "LOW_RISK":
            continue
        rid = _rule_id(tool)
        if rid in seen:
            continue
        tags = list(tool.owasp_agentic) if tool.owasp_agentic else []
        seen[rid] = {
            "id": rid,
            "shortDescription": {"text": rid.replace("diplomat-agent/", "").replace("-", " ").title()},
            "helpUri": "https://github.com/Diplomat-ai/diplomat-agent/blob/main/docs/owasp-agentic-mapping.md",
            "properties": {"tags": tags},
        }
    return list(seen.values())


def _build_result(tool: Tool) -> dict:
    """Convert a Tool into a SARIF result."""
    level = _LEVEL_MAP.get(tool.verdict, "warning")
    missing_text = ", ".join(tool.missing_hints) if tool.missing_hints else "none"
    msg = f"{tool.name}: {missing_text}"

    location = {
        "physicalLocation": {
            "artifactLocation": {"uri": tool.file},
            "region": {"startLine": tool.line},
        }
    }

    result: dict = {
        "ruleId": _rule_id(tool),
        "level": level,
        "message": {"text": msg},
        "locations": [location],
        "properties": {
            "owasp": tool.owasp_agentic,
            "checks": [{"type": g.type, "code": g.evidence} for g in tool.guards],
            "missing": tool.missing_hints,
        },
    }
    return result


def generate_sarif(result: ScanResult, scanned_path: str = ".") -> dict:
    """Build the complete SARIF 2.1.0 log object."""
    relevant = [t for t in result.tools if t.verdict != "LOW_RISK"]

    sarif: dict = {
        "$schema": _SARIF_SCHEMA,
        "version": _SARIF_VERSION,
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "diplomat-agent",
                        "version": __version__,
                        "informationUri": "https://github.com/Diplomat-ai/diplomat-agent",
                        "rules": _build_rules(relevant),
                    }
                },
                "results": [_build_result(t) for t in relevant],
            }
        ],
    }
    return sarif


def render_sarif(result: ScanResult, scanned_path: str = ".") -> str:
    """Return SARIF JSON string."""
    return json.dumps(generate_sarif(result, scanned_path), indent=2)
