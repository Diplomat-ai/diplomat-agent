"""GATE_FAMILY_MAP must stay in sync with two independent sources of truth:
the categories the scanner actually produces, and the policy ids
diplomat-gate's loader can actually load. Both are re-derived here, not
recopied from GATE_FAMILY_MAP itself, so a stale entry on either side fails.
"""

from __future__ import annotations

import re
from pathlib import Path

from diplomat_agent.reporter.gate_mapping import GATE_FAMILY_MAP

REPO = Path(__file__).parent.parent

# Hardcoded copy of diplomat-gate's _POLICY_MAP keys
# (diplomat-gate@63dfa8c, src/diplomat_gate/policies/loader.py:22-31).
# Kept as a literal, not fetched or imported, per the zero-dependency rule
# of both repos.
GATE_POLICY_IDS = {
    "payment.amount_limit",
    "payment.velocity",
    "payment.daily_limit",
    "payment.duplicate_detection",
    "payment.recipient_blocklist",
    "email.domain_blocklist",
    "email.rate_limit",
    "email.business_hours",
    "email.content_scan",
}


def _produced() -> set[str]:
    src = (REPO / "src" / "diplomat_agent" / "scanner" / "patterns.py").read_text()
    return set(re.findall(r'"category":\s*"([a-z_]+)"', src))


def test_every_key_is_a_real_scanner_category():
    assert set(GATE_FAMILY_MAP) <= _produced()


def test_every_produced_category_is_mapped():
    """Exhaustiveness: a new pattern added to the scanner must be mapped
    here too, even if only to record an unimplemented family + issue."""
    assert _produced() <= set(GATE_FAMILY_MAP)


def test_every_suggested_id_is_a_real_gate_policy():
    for category, gate_family in GATE_FAMILY_MAP.items():
        for policy_id in gate_family.suggested:
            assert policy_id in GATE_POLICY_IDS, (
                f"{category}: suggested id {policy_id!r} is not a real diplomat-gate policy"
            )


def test_exactly_ten_categories_two_implemented_eight_tracked():
    assert len(GATE_FAMILY_MAP) == 10

    implemented = {c: f for c, f in GATE_FAMILY_MAP.items() if f.family is not None}
    assert set(implemented) == {"payment", "email"}
    for category, gate_family in implemented.items():
        assert gate_family.issue is None
        assert gate_family.suggested, f"{category}: implemented family has no suggested policies"

    unimplemented = {c: f for c, f in GATE_FAMILY_MAP.items() if f.family is None}
    assert len(unimplemented) == 8
    for category, gate_family in unimplemented.items():
        assert isinstance(gate_family.issue, int), f"{category}: missing tracking issue"
        assert gate_family.suggested == []

    expected_issues = {
        "destructive": 9,
        "database_delete": 10,
        "file_delete": 12,
        "http_write": 13,
        "agent_invocation": 14,
        "llm_call": 15,
        "database_write": 17,
        "publish": 18,
    }
    assert {c: f.issue for c, f in unimplemented.items()} == expected_issues
