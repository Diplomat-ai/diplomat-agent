"""Bench analyzer per brief."""
from __future__ import annotations

import glob
import json
import os
import re

MUT = re.compile(
    r"(create|delete|update|put|post|remove|deploy|scale|apply|run|exec|write|"
    r"send|kill|stop|drain|cordon|patch|restart|rollback|terminate|destroy|modify|"
    r"upload|push|insert|drop|truncate|grant|revoke|attach|detach|start)",
    re.IGNORECASE,
)

for f in sorted(glob.glob("results/bench/*.json")):
    d = json.load(open(f))
    name = os.path.basename(f)[:-5]
    F = d.get("findings", [])
    S = d.get("summary", {})

    def has_se(t):
        return bool(t.get("actions"))

    fn = [
        t["function"]
        for t in F
        if (t["verdict"] == "LOW_RISK" or not has_se(t)) and MUT.search(t["function"])
    ]
    g = [(t["function"], t.get("checks")) for t in F if t["verdict"] in ("GUARDED", "PARTIALLY_GUARDED")]
    op = [t["function"] for t in F if t["verdict"] == "OPAQUE"]
    cv = [t["function"] for t in F if t.get("contract_violation", "NONE") != "NONE"]

    print(f"\n=== {name} ===")
    print("summary:", S)
    print(
        "files_unparsed:",
        S.get("files_unparsed_count", 0),
        S.get("files_unparsed", []),
    )
    print(f"SUSPECTED FALSE NEGATIVES ({len(fn)}):", fn[:40])
    print(f"GUARDED/PARTIAL ({len(g)}):", g[:20])
    print(f"OPAQUE ({len(op)}):", op[:20])
    print(f"CONTRACT VIOLATIONS ({len(cv)}):", cv[:20])
