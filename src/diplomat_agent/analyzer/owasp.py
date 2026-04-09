"""Map tools to OWASP Top 10 for Agentic Applications (2025)."""

from __future__ import annotations

from diplomat_agent.models import Tool

# Effect category → OWASP codes
EFFECT_MAPPING: dict[str, list[str]] = {
    "payment": ["ASI-02", "ASI-03"],
    "database_write": ["ASI-02"],
    "database_delete": ["ASI-02", "ASI-03"],
    "http_write": ["ASI-02"],
    "llm_call": ["ASI-02", "ASI-05"],
    "agent_invocation": ["ASI-02", "ASI-04", "ASI-10"],
    "email": ["ASI-02"],
    "messaging": ["ASI-02"],
    "publish": ["ASI-02"],
    "dynamic_code": ["ASI-02", "ASI-03"],
    "file_delete": ["ASI-02", "ASI-03"],
    "repository_method": ["ASI-02"],
    "destructive": ["ASI-02", "ASI-03"],
}

# Missing check hint substring → additional OWASP codes
MISSING_CHECK_MAPPING: dict[str, list[str]] = {
    "no rate limit": ["ASI-06"],
    "no auth check": ["ASI-01"],
    "no confirmation": ["ASI-03"],
    "no retry bound": ["ASI-06"],
}


def map_tool_to_owasp(tool: Tool) -> list[str]:
    """Return deduplicated, sorted OWASP codes for a Tool."""
    codes: set[str] = set()

    for effect in tool.side_effects:
        if effect.category in EFFECT_MAPPING:
            codes.update(EFFECT_MAPPING[effect.category])

    for hint in tool.missing_hints:
        for pattern, owasp_codes in MISSING_CHECK_MAPPING.items():
            if pattern in hint:
                codes.update(owasp_codes)

    return sorted(codes)


def apply_owasp(tools: list[Tool]) -> None:
    """Populate owasp_agentic on all tools in-place."""
    for tool in tools:
        tool.owasp_agentic = map_tool_to_owasp(tool)
