"""T05b W0.5 (spec §20, B14): the degeneracy distance at the states W1.d and C1–C3 judge.

`δ` (spec §4.4) of every flowing stream at its own `(n, T, P)` and of every lifted split's feed at
the split's `(T, P)`, by both implementations — the unit layer's
(`models/syn001/saturation_band.py`) and the verifier's (`verify/saturation.py`) — at W1.d's
SYN-001-shaped root and traversal start `x⁰`, and at C1, C2 and C3's roots. B14 requires every
value `≥ 1 K`; the twin registers the roots' values (`ref.degeneracy_at_registered_states_K`).

Usage:
    PYTHONPATH=src:. .venv/bin/python scripts/t05b_degeneracy_margins.py
"""

import math
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
import test_t05_w1d_verifier as w1d  # noqa: E402
from t05_support import CONTEXT, PROVIDER  # noqa: E402
from t05_syn001_shaped import shaped_revision  # noqa: E402
from test_t05_coupled import solve  # noqa: E402

from openflowsheet.models import flow_id, pressure_id, temperature_id  # noqa: E402
from openflowsheet.models.revision_flowsheet import parse_revision  # noqa: E402
from openflowsheet.models.syn001 import saturation_band as unit  # noqa: E402
from openflowsheet.orchestrator.revision import initial_state  # noqa: E402
from openflowsheet.orchestrator.splits import lifted_splits  # noqa: E402
from openflowsheet.verify import saturation as verifier  # noqa: E402


def both(n, t, p):
    return (
        unit.degeneracy_distance(PROVIDER, n, t, p, CONTEXT),
        verifier.degeneracy_distance(PROVIDER, n, t, p, CONTEXT),
    )


def measure(label, document, state):
    view = parse_revision(document)
    comps = view.components
    splits = lifted_splits([(i.unit_id, i.model_id, i.wiring) for i in view.instances], comps)
    streams = sorted({key.rsplit(".", 1)[0] for key in state if key.endswith(".T")})
    rows = []
    for s in streams:
        n = tuple(state[flow_id(s, c)] for c in comps)
        if any(v > 0 for v in n):
            rows.append((s, *both(n, state[temperature_id(s)], state[pressure_id(s)])))
    for sp in splits:
        n = tuple(state[f] for f in sp.feed)
        if any(v > 0 for v in n):
            rows.append((f"split:{sp.unit}", *both(n, state[sp.temperature], state[sp.pressure])))
        else:
            print("   dormant split", sp.unit)
    low = min(min(a, b) for _, a, b in rows)
    diff = max((abs(a - b) for _, a, b in rows if math.isfinite(a)), default=0.0)
    print(f"{label}: {len(rows)} items, min delta {low:.6f} K, unit-verifier max |diff| {diff:.3g}")
    print("   " + " ".join(f"{name}={a:.6f}" for name, a, _ in rows))
    return low


def main() -> int:
    document = shaped_revision()
    binding, plan, result = w1d._solve(document)
    lows = [measure("W1.d root", document, result.state)]
    start = initial_state(binding.flowsheet, binding.spec.variable_ids)
    lows.append(measure("W1.d x0", document, start))
    for case in ("SYN-001-UL-C1", "SYN-001-UL-C2", "SYN-001-UL-C3"):
        solved = solve(case)
        doc = yaml.safe_load((ROOT / "benchmarks" / "t05" / "cases" / f"{case}.yaml").read_text())
        lows.append(measure(case + " root", doc, solved.run.state))
    print("overall min delta", min(lows))
    return 0 if min(lows) >= 1.0 else 1


if __name__ == "__main__":
    sys.exit(main())
