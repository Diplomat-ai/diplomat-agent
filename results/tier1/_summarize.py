"""Tier-1 scan summarizer."""
from __future__ import annotations

import json
import re
from pathlib import Path

HERE = Path(__file__).parent

destructive_pat = re.compile(
    r"(delete|remove|scale|apply|create|exec|drain|cordon|patch|edit|kill|stop|restart)",
    re.IGNORECASE,
)

for repo in ["kubectl-mcp-server", "k8s-mcp-server", "docker-mcp"]:
    with open(HERE / f"{repo}.json") as f:
        d = json.load(f)
    s = d["summary"]
    findings = d["findings"]
    destructive = [f for f in findings if destructive_pat.search(f["function"])]
    viols = [f for f in findings if f.get("contract_violation", "NONE") != "NONE"]
    print(f"=== {repo} ===")
    print(f"  summary: {s}")
    print(f"  destructive-by-name: {len(destructive)}")
    print(f"  contract_violations: {len(viols)}")
    if viols:
        verdicts = {}
        for v in viols:
            verdicts[v["verdict"]] = verdicts.get(v["verdict"], 0) + 1
        print(f"  contract_violation verdicts: {verdicts}")
    print()
