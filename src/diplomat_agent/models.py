"""Shared dataclasses for diplomat-agent."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SideEffect:
    """Represents a detected side effect in a tool function."""

    category: str  # "payment", "database_write", "database_delete", "http_write", "email", "publish", "file_delete", "destructive", "agent_invocation", "llm_call"
    evidence: str  # code excerpt proving the side effect
    line: int  # line number in the source file
    file: str  # path to the file
    type: str = ""  # effect type from pattern category (same as category when set)


@dataclass
class Guard:
    """Represents a detected guard/governance mechanism in a tool function."""

    type: str  # "input_validation", "rate_limit", "auth_check", "approval_step", "idempotency_key", "retry_bound", "confirmation"
    evidence: str  # code excerpt proving the guard
    line: int
    coverage: str  # "full" or "partial"


@dataclass
class Tool:
    """Represents a tool function with its side effects and guards."""

    name: str  # function name
    file: str  # path to the file
    line: int  # starting line of the function
    params: list[dict]  # [{"name": "amount", "type": "float", "numeric": True, "has_bounds": False}, ...]
    side_effects: list[SideEffect] = field(default_factory=list)
    guards: list[Guard] = field(default_factory=list)
    verdict: str = "UNGUARDED"  # "UNGUARDED", "PARTIALLY_GUARDED", "GUARDED", "LOW_RISK"
    missing_hints: list[str] = field(default_factory=list)  # ["no bounds on amount", "no rate limit"]
    auto_retried: bool = False
    auto_retry_decorator: str = ""
    ignored: bool = False  # True when # diplomat:ok, # canary:ok, or # checked:ok is present
    ignore_reason: str = ""  # text after the marker, e.g. "validated at API layer"
    owasp_agentic: list[str] = field(default_factory=list)  # e.g. ["ASI-02", "ASI-03"]
    exposure: str = "internal"   # "internal" | "mcp_tool" | "mcp_internal" | "mcp_client"
    exposure_evidence: str = ""  # decorator proving exposure, e.g. "@mcp.tool()"
    # MCP ToolAnnotations hints — parsed from @mcp.tool(annotations=ToolAnnotations(...))
    readonly_hint: "bool | None" = None      # readOnlyHint kwarg value
    destructive_hint: "bool | None" = None   # destructiveHint kwarg value
    # Contract violation flag — orthogonal to verdict, set after verdict is computed
    contract_violation: str = "NONE"  # NONE | DECLARED_READONLY_BUT_WRITES | DECLARED_NONDESTRUCTIVE_BUT_DESTRUCTIVE
    # GATE 5 — set when a dispatcher branch handler could not be resolved; forces OPAQUE
    opaque_reason: str = ""  # non-empty → compute_verdict returns OPAQUE


@dataclass
class Scenario:
    """Represents a risk scenario for an unguarded or partially-guarded tool."""

    tool_name: str
    description: str  # human-readable risk description
    risk_category: str  # "financial", "data_loss", "data_leak", "reputation", "operational"
    estimated_impact: str  # order-of-magnitude impact, e.g. "$199,800 in <10min"


@dataclass
class ScanResult:
    """Complete result of a scan."""

    tools: list[Tool]
    scenarios: list[Scenario]
    summary: dict  # {"total_tools": 6, "unguarded": 4, "partially_guarded": 1, "guarded": 0, "low_risk": 1}
