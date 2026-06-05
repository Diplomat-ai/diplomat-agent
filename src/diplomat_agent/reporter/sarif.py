"""SARIF 2.1.0 reporter — produces SARIF JSON for GitHub Code Scanning.

Generates a SARIF v2.1.0 log consumable by ``github/codeql-action/upload-sarif``.
No external dependencies — uses only the stdlib ``json`` module.
"""

from __future__ import annotations

import json

from diplomat_agent import __version__
from diplomat_agent.models import ScanResult, Tool


_SARIF_VERSION = "2.1.0"
_SARIF_SCHEMA = "https://docs.oasis-open.org/sarif/sarif/v2.1.0/errata01/os/schemas/sarif-schema-2.1.0.json"

# Stable rule IDs by category + verdict
_CATEGORY_RULES: dict[str, dict] = {
    "database_write": {
        "id": "DA001",
        "name": "UnguardedDatabaseWrite",
        "shortDescription": {"text": "Database write with no protective guards"},
        "fullDescription": {"text": (
            "A function performs a database write operation (session.commit, .save, .create) "
            "with no input validation, rate limiting, auth check, or confirmation step. "
            "When called by an LLM, this function could be invoked with arbitrary arguments "
            "or in an infinite loop."
        )},
        "defaultConfiguration": {"level": "error"},
        "helpUri": "https://github.com/Diplomat-ai/diplomat-agent#what-counts-as-a-tool-call",
    },
    "database_delete": {
        "id": "DA002",
        "name": "UnguardedDatabaseDelete",
        "shortDescription": {"text": "Database delete with no protective guards"},
        "defaultConfiguration": {"level": "error"},
        "helpUri": "https://github.com/Diplomat-ai/diplomat-agent#what-counts-as-a-tool-call",
    },
    "http_write": {
        "id": "DA003",
        "name": "UnguardedHttpWrite",
        "shortDescription": {"text": "HTTP write request with no protective guards"},
        "defaultConfiguration": {"level": "error"},
        "helpUri": "https://github.com/Diplomat-ai/diplomat-agent#what-counts-as-a-tool-call",
    },
    "payment": {
        "id": "DA004",
        "name": "UnguardedPayment",
        "shortDescription": {"text": "Payment operation with no protective guards"},
        "defaultConfiguration": {"level": "error"},
        "helpUri": "https://github.com/Diplomat-ai/diplomat-agent#what-counts-as-a-tool-call",
    },
    "email": {
        "id": "DA005",
        "name": "UnguardedEmail",
        "shortDescription": {"text": "Email/messaging operation with no protective guards"},
        "defaultConfiguration": {"level": "warning"},
        "helpUri": "https://github.com/Diplomat-ai/diplomat-agent#what-counts-as-a-tool-call",
    },
    "agent_invocation": {
        "id": "DA006",
        "name": "UnguardedAgentInvocation",
        "shortDescription": {"text": "Agent invocation with no protective guards"},
        "defaultConfiguration": {"level": "warning"},
        "helpUri": "https://github.com/Diplomat-ai/diplomat-agent#what-counts-as-a-tool-call",
    },
    "destructive": {
        "id": "DA007",
        "name": "UnguardedDestructiveCommand",
        "shortDescription": {"text": "Subprocess/exec/eval with no protective guards"},
        "defaultConfiguration": {"level": "error"},
        "helpUri": "https://github.com/Diplomat-ai/diplomat-agent#what-counts-as-a-tool-call",
    },
    "publish": {
        "id": "DA008",
        "name": "UnguardedPublish",
        "shortDescription": {"text": "Publish/upload operation with no protective guards"},
        "defaultConfiguration": {"level": "warning"},
        "helpUri": "https://github.com/Diplomat-ai/diplomat-agent#what-counts-as-a-tool-call",
    },
}

_PARTIALLY_GUARDED_RULE: dict = {
    "id": "DA009",
    "name": "PartiallyGuarded",
    "shortDescription": {"text": "Side-effect function with incomplete guards"},
    "defaultConfiguration": {"level": "warning"},
    "helpUri": "https://github.com/Diplomat-ai/diplomat-agent#what-counts-as-a-tool-call",
}


def _rule_id(tool: Tool) -> str:
    """Map a tool to a stable DA rule ID based on its category and verdict."""
    if tool.verdict == "PARTIALLY_GUARDED":
        return "DA009"
    categories = sorted({se.category for se in tool.side_effects})
    primary = categories[0] if categories else "unknown"
    rule = _CATEGORY_RULES.get(primary)
    if rule:
        return rule["id"]
    # Fallback for categories not in the map (file_delete, llm_call, etc.)
    return "DA007"


def _build_rules(tools: list[Tool]) -> list[dict]:
    """Return all 9 rules statically — rules declare tool capability, not scan results."""
    rules = [dict(rule) for rule in _CATEGORY_RULES.values()]
    rules.append(dict(_PARTIALLY_GUARDED_RULE))
    return sorted(rules, key=lambda r: r["id"])


_LEVEL_MAP = {
    "UNGUARDED": "error",
    "PARTIALLY_GUARDED": "warning",
    "GUARDED": "none",
    "LOW_RISK": "none",
}


def _build_result(tool: Tool) -> dict:
    """Convert a Tool into a SARIF result."""
    level = _LEVEL_MAP.get(tool.verdict, "warning")
    missing_text = ", ".join(tool.missing_hints) if tool.missing_hints else "none"
    actions_text = ", ".join(se.evidence for se in tool.side_effects)
    msg = f"{tool.name}() calls {actions_text} with {missing_text}."

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
    }
    if tool.exposure == "mcp_tool":
        result["properties"] = {"exposure": "mcp_tool"}
    return result


def generate_sarif(result: ScanResult, scanned_path: str = ".") -> dict:
    """Build the complete SARIF 2.1.0 log object."""
    relevant = [t for t in result.tools if t.verdict not in ("LOW_RISK", "GUARDED")]

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
