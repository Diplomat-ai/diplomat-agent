"""Aggregate baseline."""
from __future__ import annotations

import glob
import json
import os
from pathlib import Path

HERE = Path(__file__).parent
total = 0
agg = {"unguarded": 0, "partially_guarded": 0, "guarded": 0, "low_risk": 0, "opaque": 0}
print(f"{'repo':40s} | {'total':>6s} | {'U':>4s} | {'P':>4s} | {'G':>4s} | {'LR':>4s} | {'OP':>4s}")
print("-" * 90)
for f in sorted(glob.glob(str(HERE / "*.json"))):
    d = json.load(open(f))
    s = d["summary"]
    name = os.path.basename(f)[:-5]
    opaque = sum(1 for t in d["findings"] if t["verdict"] == "OPAQUE")
    print(
        f"{name:40s} | {s['total']:>6d} | {s['unguarded']:>4d} | "
        f"{s['partially_guarded']:>4d} | {s['guarded']:>4d} | "
        f"{s['low_risk']:>4d} | {opaque:>4d}"
    )
    total += s["total"]
    agg["unguarded"] += s["unguarded"]
    agg["partially_guarded"] += s["partially_guarded"]
    agg["guarded"] += s["guarded"]
    agg["low_risk"] += s["low_risk"]
    agg["opaque"] += opaque
print("-" * 90)
print(
    f"{'TOTAL':40s} | {total:>6d} | {agg['unguarded']:>4d} | "
    f"{agg['partially_guarded']:>4d} | {agg['guarded']:>4d} | "
    f"{agg['low_risk']:>4d} | {agg['opaque']:>4d}"
)
analyzable = agg["unguarded"] + agg["partially_guarded"] + agg["guarded"] + agg["low_risk"]
if analyzable:
    print(f"\nunguarded% (analyzable): {agg['unguarded'] / analyzable * 100:.1f}%")
if total:
    print(f"opacity rate: {agg['opaque'] / total * 100:.1f}%")
