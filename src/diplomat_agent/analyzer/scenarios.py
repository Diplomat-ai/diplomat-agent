"""Risk scenario generation for unguarded or partially-guarded tools.

Scenarios are conservative order-of-magnitude estimates, not precise calculations.
"""

from __future__ import annotations

from diplomat_agent.models import Scenario, Tool

# Conservative constants for scenario generation
_N_ACTIONS = 200        # actions an agent loop might take in 10 minutes
_TIME_WINDOW = "10min"
_MAX_PLAUSIBLE = 999    # plausible amount per transaction ($)
_EXTREME_AMOUNT = 99_999  # extreme single-call amount ($)


def _make_scenario(
    tool: Tool,
    description: str,
    risk_category: str,
    estimated_impact: str,
) -> Scenario:
    return Scenario(
        tool_name=tool.name,
        description=description,
        risk_category=risk_category,
        estimated_impact=estimated_impact,
    )


def _scenarios_for_payment(tool: Tool) -> list[Scenario]:
    total = _N_ACTIONS * _MAX_PLAUSIBLE
    return [
        _make_scenario(
            tool,
            f"Agent loop could execute {_N_ACTIONS} transactions"
            f" of ${_MAX_PLAUSIBLE} each in {_TIME_WINDOW}",
            "financial",
            f"${total:,} in <{_TIME_WINDOW}",
        ),
        _make_scenario(
            tool,
            f"Single prompt could trigger a transaction of ${_EXTREME_AMOUNT:,}"
            " with no upper limit on amount",
            "financial",
            f"${_EXTREME_AMOUNT:,} per call",
        ),
    ]


def _scenarios_for_database_delete(tool: Tool) -> list[Scenario]:
    return [
        _make_scenario(
            tool,
            "Single prompt could trigger mass deletion of records"
            " — no confirmation required",
            "data_loss",
            "Irreversible data loss",
        ),
        _make_scenario(
            tool,
            f"Agent loop could delete {_N_ACTIONS} records"
            f" in {_TIME_WINDOW} with no batch protection",
            "data_loss",
            f"{_N_ACTIONS} records deleted in <{_TIME_WINDOW}",
        ),
    ]


def _scenarios_for_database_write(tool: Tool) -> list[Scenario]:
    return [
        _make_scenario(
            tool,
            f"Agent loop could write {_N_ACTIONS} records"
            f" in {_TIME_WINDOW} with no rate limit",
            "operational",
            f"{_N_ACTIONS} unvalidated writes in <{_TIME_WINDOW}",
        ),
    ]


def _scenarios_for_http_write(tool: Tool) -> list[Scenario]:
    return [
        _make_scenario(
            tool,
            f"Agent could make {_N_ACTIONS} external API calls"
            f" in {_TIME_WINDOW} with no throttling",
            "operational",
            f"{_N_ACTIONS} external calls in <{_TIME_WINDOW}",
        ),
        _make_scenario(
            tool,
            "Failed calls with no retry bound could cascade"
            f" into {_N_ACTIONS} retries and exhaust API quota",
            "operational",
            "API quota exhaustion, rate-ban risk",
        ),
    ]


def _scenarios_for_email(tool: Tool) -> list[Scenario]:
    return [
        _make_scenario(
            tool,
            f"Agent could send {_N_ACTIONS} messages"
            f" in {_TIME_WINDOW} — spam risk, reputation damage",
            "reputation",
            f"{_N_ACTIONS} unsolicited messages in <{_TIME_WINDOW}",
        ),
    ]


def _scenarios_for_publish(tool: Tool) -> list[Scenario]:
    return [
        _make_scenario(
            tool,
            "Agent could publish content to production"
            " without any human review or approval",
            "reputation",
            "Unreviewed content published publicly",
        ),
    ]


def _scenarios_for_file_delete(tool: Tool) -> list[Scenario]:
    return [
        _make_scenario(
            tool,
            "Single prompt could trigger deletion of critical files"
            " — no confirmation required",
            "data_loss",
            "Irreversible file loss",
        ),
    ]


def _scenarios_for_agent_invocation(tool: Tool) -> list[Scenario]:
    return [
        _make_scenario(
            tool,
            f"Agent sub-invocation could trigger a full LLM pipeline"
            f" — no guardrails on nested actions",
            "operational",
            f"Unbounded nested agent execution",
        ),
    ]


def _scenarios_for_llm_call(tool: Tool) -> list[Scenario]:
    return [
        _make_scenario(
            tool,
            "Unguarded LLM call — each invocation costs money, may hallucinate,"
            " and could trigger downstream actions without review",
            "financial",
            "Unbounded LLM spend + potential hallucination",
        ),
    ]


_CATEGORY_HANDLERS: dict[str, callable] = {
    "payment": _scenarios_for_payment,
    "database_delete": _scenarios_for_database_delete,
    "database_write": _scenarios_for_database_write,
    "http_write": _scenarios_for_http_write,
    "email": _scenarios_for_email,
    "publish": _scenarios_for_publish,
    "file_delete": _scenarios_for_file_delete,
    "agent_invocation": _scenarios_for_agent_invocation,
    "llm_call": _scenarios_for_llm_call,
}


def generate_scenarios(tools: list[Tool]) -> list[Scenario]:
    """Generate risk scenarios for all unguarded or partially-guarded tools."""
    scenarios: list[Scenario] = []
    for tool in tools:
        if tool.verdict not in ("UNGUARDED", "PARTIALLY_GUARDED"):
            continue
        seen_categories: set[str] = set()
        for se in tool.side_effects:
            if se.category in seen_categories:
                continue
            seen_categories.add(se.category)
            handler = _CATEGORY_HANDLERS.get(se.category)
            if handler:
                # For PARTIALLY_GUARDED, only show the first (most severe) scenario
                new_scenarios = handler(tool)
                if tool.verdict == "PARTIALLY_GUARDED" and new_scenarios:
                    scenarios.append(new_scenarios[0])
                else:
                    scenarios.extend(new_scenarios)
    return scenarios


def estimate_total_financial_exposure(scenarios: list[Scenario]) -> int:
    """Return a rough total financial exposure from financial scenarios (integer $)."""
    total = 0
    for sc in scenarios:
        if sc.risk_category == "financial":
            # Parse numbers from estimated_impact
            impact = sc.estimated_impact.replace(",", "").replace("$", "")
            parts = impact.split()
            for part in parts:
                try:
                    total += int(part)
                    break
                except ValueError:
                    continue
    return total
