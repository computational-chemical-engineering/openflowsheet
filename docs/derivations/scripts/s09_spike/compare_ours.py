"""Informal (not evidence) comparison of the spike's BioSTEAM profiles with OpenFlowsheet's S03
'ours' records.
"""

import json

OURS = "/home/frankp/Codes/OpenFlowsheet/benchmarks/s03/references/results/ours-{}.json"
recs = {r["case"]: r for r in json.load(open("columns.json"))}
recs["RC4"] = json.load(open("rc4_blind.json"))
for case in ("RC1", "RC3", "RC4"):
    p = dict(recs[case]["profile"])
    Q = p.pop("Q_stage_W")
    p["Q_condenser"] = Q[0]
    p["Q_reboiler"] = Q[-1]
    ours = json.load(open(OURS.format(case)))["quantities"]
    worst = {}
    for kind, pre in (("T", "T["), ("flow", ("L[", "V[", "top", "bottom")), ("duty", "Q_")):
        diffs = [(abs(p[k] - v), k) for k, v in ours.items() if k.startswith(pre)]
        worst[kind] = max(diffs) if diffs else None
    print(
        case,
        " ".join(f"{k}: max|d| {v[0]:.2e} ({v[1]})" for k, v in worst.items() if v),
        f"[{len(ours)} quantities]",
    )
