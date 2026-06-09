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

_CONTRACT_VIOLATION_RULE: dict = {
    "id": "DA010",
    "name": "ContractViolation",
    "shortDescription": {"text": "MCP tool annotation contradicts detected behaviour"},
    "fullDescription": {
        "text": (
            "The tool is annotated (e.g. readOnlyHint=True or destructiveHint=False) "
            "but static analysis detected side effects that contradict the annotation. "
            "The annotation cannot be trusted as a safety signal."
        )
    },
    "defaultConfiguration": {"level": "error"},
    "helpUri": "https://github.com/Diplomat-ai/diplomat-agent#contract-violation",
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
    """Return all 10 rules statically — rules declare tool capability, not scan results."""
    rules = [dict(rule) for rule in _CATEGORY_RULES.values()]
    rules.append(dict(_PARTIALLY_GUARDED_RULE))
    rules.append(dict(_CONTRACT_VIOLATION_RULE))
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
    props: dict = {}
    if tool.exposure == "mcp_tool":
        props["exposure"] = "mcp_tool"
    if tool.contract_violation != "NONE":
        props["contractViolation"] = tool.contract_violation
    if props:
        result["properties"] = props
    # Emit an additional DA010 result when a contract violation is present
    return result


def _build_contract_violation_result(tool: Tool) -> "dict | None":
    """Return a DA010 SARIF result if the tool has a contract violation, else None."""
    if tool.contract_violation == "NONE":
        return None
    cv_msg = tool.contract_violation.replace("_", " ").lower()
    return {
        "ruleId": "DA010",
        "level": "error",
        "message": {"text": f"Contract violation: {cv_msg} in '{tool.name}'"},
        "locations": [{
            "physicalLocation": {
                "artifactLocation": {"uri": tool.file},
                "region": {"startLine": tool.line},
            }
        }],
    }


def generate_sarif(result: ScanResult, scanned_path: str = ".") -> dict:
    """Build the complete SARIF 2.1.0 log object."""
    relevant = [t for t in result.tools if t.verdict not in ("LOW_RISK", "GUARDED")]

    sarif_results = [_build_result(t) for t in relevant]
    # Append DA010 contract-violation results (one per violating tool)
    for t in result.tools:
        cv_result = _build_contract_violation_result(t)
        if cv_result is not None:
            sarif_results.append(cv_result)

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
                "results": sarif_results,
            }
        ],
    }
    return sarif


def render_sarif(result: ScanResult, scanned_path: str = ".") -> str:
    """Return SARIF JSON string."""
    return json.dumps(generate_sarif(result, scanned_path), indent=2)
