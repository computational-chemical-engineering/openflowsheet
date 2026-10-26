"""S10-C WO-1 probe: the constant-β point's cost and its agreement with the design's prototype.

Runs `gamma_phi.band_point` on the design note's measured sets (`docs/derivations/scripts/
s10c_design/measured.txt` §2, M-a: real records, 11 feeds × β ∈ {0, 0.1, 0.5, 0.9, 1}; §3, M-b: the
13 E-2 states, β ∈ {0, 0.25, 0.5, 0.75, 1}) and prints one line per set: the largest number of
successive-substitution steps, the largest and median `evaluate_phase` count per point, the median
and largest wall time, and the largest |T − T_prototype| over the points whose prototype temperature
`measured.txt` prints (the prototype is an independent bisection implementation, 9 or 12
decimals). Informative, not a gate; the numbers go into `docs/S10C_DECISIONS.md`.

Usage (repository root):
    PYTHONPATH=src:tests .venv/bin/python scripts/s10c_band_point_probe.py
"""

from __future__ import annotations

import re
import statistics
import time
from pathlib import Path
from typing import Any

from test_s10_flash import NEAR_AZEOTROPE

from openflowsheet.compiled import EvaluationContext
from openflowsheet.models.syn001 import gamma_phi
from openflowsheet.thermo.wilson_ig import WilsonIdealGasProvider

ROOT = Path(__file__).resolve().parent.parent
MEASURED = ROOT / "docs" / "derivations" / "scripts" / "s10c_design" / "measured.txt"
CONTEXT = EvaluationContext(model_version="S10C-probe@" + "0" * 64, constants_sha256="0" * 64)
P_ATM = 101325.0
#: M-f's model azeotrope of ethanol–water (x_E = 0.88144), the two feeds 1e-4 either side of it.
AZEOTROPE_E = 0.88144


def _run(provider: Any, flows: tuple[float, ...], beta: float) -> tuple[Any, int, float]:
    steps = 0
    original = gamma_phi._Point.temperature

    def counted(self: Any, *args: Any) -> Any:
        nonlocal steps
        steps += 1
        return original(self, *args)

    gamma_phi._Point.temperature = counted  # type: ignore[method-assign]
    try:
        start = time.perf_counter()
        point = gamma_phi.band_point(provider, flows, P_ATM, beta, CONTEXT)
        elapsed = time.perf_counter() - start
    finally:
        gamma_phi._Point.temperature = original  # type: ignore[method-assign]
    return point, steps, elapsed


def _summary(label: str, rows: list[tuple[Any, int, float]], deviation: float) -> str:
    evaluations = [point.evaluations for point, _, _ in rows]
    times = [elapsed for _, _, elapsed in rows]
    return (
        f"{label}: points {len(rows)}, max steps {max(steps for _, steps, _ in rows)}, "
        f"evaluations max {max(evaluations)} median {statistics.median(evaluations)}, "
        f"wall median {statistics.median(times) * 1e3:.2f} ms max {max(times) * 1e3:.2f} ms, "
        f"max |T - T_prototype| {deviation:.2e} K"
    )


def main() -> int:
    text = MEASURED.read_text("utf-8")
    real = WilsonIdealGasProvider()
    verification = WilsonIdealGasProvider(ROOT / "benchmarks" / "s10" / "verification-records.yaml")

    prototype: dict[tuple[str, str], float] = {}
    for z, beta, t in re.findall(r"z (\[[^]]*\]) beta ([0-9.]+) T ([0-9.]+)", text):
        prototype[(z, beta)] = float(t)
    feeds = [(0.0, ze, 1.0 - ze) for ze in (0.2, 0.5, 0.8, AZEOTROPE_E - 1e-4, AZEOTROPE_E + 1e-4)]
    feeds += [(zm, 0.0, 1.0 - zm) for zm in (0.4, 0.994, 0.0039, 1.0 - 1e-10, 1e-10)]
    feeds += [(0.3, 0.2, 0.5)]
    rows, deviation = [], 0.0
    for flows in feeds:
        for beta in (0.0, 0.1, 0.5, 0.9, 1.0):
            row = _run(real, flows, beta)
            rows.append(row)
            key = (str([f"{v:.6g}" for v in flows]), f"{beta:.1f}")
            exact = all(float(f"{v:.6g}") == v for v in flows)
            if exact and key in prototype and row[0].temperature is not None:
                deviation = max(deviation, abs(row[0].temperature - prototype[key]))
    print(_summary("M-a real records", rows, deviation))

    ends = [(float(b), float(d)) for b, d in re.findall(r"T_b ([0-9.]+) T_d ([0-9.]+)", text)]
    rows, deviation = [], 0.0
    for ((nb, nc), _), (t_b, t_d) in zip(NEAR_AZEOTROPE, ends, strict=True):
        for beta in (0.0, 0.25, 0.5, 0.75, 1.0):
            row = _run(verification, (0.0, nb, nc), beta)
            rows.append(row)
            if beta in (0.0, 1.0) and row[0].temperature is not None:
                reference = t_b if beta == 0.0 else t_d
                deviation = max(deviation, abs(row[0].temperature - reference))
    print(_summary("M-b E-2 states", rows, deviation))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
