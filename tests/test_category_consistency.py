"""Every category cited in registry.py and owasp.py must actually be produced
by the scanner. A "phantom" category (referenced but never produced) leaks
into anything downstream that reads these tables — including the
diplomat-gate bridge, which maps each produced category to a policy family.

This is an equality-of-sets assertion, deliberately, not a negation of a
handful of suspicious names: a negation test cannot catch a phantom category
nobody has spotted yet — exactly the class of bug that let `repository_method`
slip past an earlier review of this same check.
"""

from __future__ import annotations

import re
from pathlib import Path

from diplomat_agent.analyzer.owasp import EFFECT_MAPPING
from diplomat_agent.reporter.registry import _EFFECT_PRIORITY

REPO = Path(__file__).parent.parent


def _produced() -> set[str]:
    src = (REPO / "src" / "diplomat_agent" / "scanner" / "patterns.py").read_text()
    return set(re.findall(r'"category":\s*"([a-z_]+)"', src))


def test_owasp_mapping_has_no_phantom_category():
    assert set(EFFECT_MAPPING) == _produced()


def test_effect_priority_has_no_phantom_category():
    cited = {c for _, group in _EFFECT_PRIORITY for c in group}
    assert cited <= _produced()
