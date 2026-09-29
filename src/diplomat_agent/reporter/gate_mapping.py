"""Scanner category -> diplomat-gate policy family, as data, not logic.

Pure lookup table: no generation logic belongs here (see
``--emit-gate-config`` for that). This is deliberately duplicated rather than
imported from diplomat-gate, per both repos' zero-dependency rule — kept in
sync by ``tests/test_gate_mapping.py``, which locks every ``suggested`` id
against a hardcoded copy of diplomat-gate's ``_POLICY_MAP`` keys and every
map key against the categories the scanner actually produces.

diplomat-gate's `_POLICY_MAP` as of diplomat-gate commit 63dfa8c
(src/diplomat_gate/policies/loader.py:22-31) has exactly these 9 ids:
payment.amount_limit, payment.velocity, payment.daily_limit,
payment.duplicate_detection, payment.recipient_blocklist,
email.domain_blocklist, email.rate_limit, email.business_hours,
email.content_scan.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class GateFamily:
    """What a scanner category maps to on the diplomat-gate side.

    ``family`` is the gate policy domain prefix ("payment", "email") when one
    exists, or ``None`` when no policy family is implemented yet.
    ``issue`` is the diplomat-gate tracking issue number for an unimplemented
    family (``None`` once implemented, or when no issue exists yet).
    ``suggested`` lists concrete diplomat-gate policy ids to seed a generated
    config with; empty when there is no family to suggest from.
    """

    family: str | None
    issue: int | None
    suggested: list[str] = field(default_factory=list)


# category (as produced by scanner/patterns.py) -> GateFamily
GATE_FAMILY_MAP: dict[str, GateFamily] = {
    "payment": GateFamily(
        family="payment",
        issue=None,
        suggested=["payment.amount_limit", "payment.velocity"],
    ),
    "email": GateFamily(
        family="email",
        issue=None,
        suggested=["email.domain_blocklist", "email.rate_limit"],
    ),
    "destructive": GateFamily(family=None, issue=9, suggested=[]),
    "database_delete": GateFamily(family=None, issue=10, suggested=[]),
    "file_delete": GateFamily(family=None, issue=12, suggested=[]),
    "http_write": GateFamily(family=None, issue=13, suggested=[]),
    "agent_invocation": GateFamily(family=None, issue=14, suggested=[]),
    "llm_call": GateFamily(family=None, issue=15, suggested=[]),
    "database_write": GateFamily(family=None, issue=17, suggested=[]),
    "publish": GateFamily(family=None, issue=18, suggested=[]),
}
