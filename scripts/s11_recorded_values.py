"""Measure the values S11's evidence manifest records beside its tests. S11 WO-I2.

The tests assert these quantities against their bounds; the manifest also records the numbers
(design note §6.2 G4; `docs/reviews/S11-rulings.md` §5 row I2), so they are measured here, at the
checked-out commit, by the tests' own helpers:

- **G4** (S11.A07–A08): `wilson_premises.minima` on the real and the verification records, with
  the S10-C `positivity` entry each minimum rounds to (3 significant figures), and the first
  violation of the real records widened to T in [300, 800] K.
- **Rulings item 2** (R-831): for C-MW, C-EW and the stripper, |Z|, the one-sided worst (Z
  differenced alone, forward five-point stencil), the central worst (every other column; Z left
  undifferenced) and the smallest nonzero scaled AD entry in a Z column.
- **Finding F-1**: C-MW's central worst at the relative steps 3e-5, 1e-5 (registered), 3e-6 and
  1e-6 (`checks.FD_RELATIVE_STEP` patched for the call, restored after).
- **Rulings item 5** (R-834): the worst value of each S11.A46 test (`_fd_worst`'s scaled error;
  the two identities relative), at the tests' own states and steps.

One JSON object is printed. Nothing here is a gate: the bounds are the tests'.

Usage:
    PYTHONPATH=src:tests:. .venv/bin/python scripts/s11_recorded_values.py
"""

from __future__ import annotations

import dataclasses
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
for _path in (ROOT / "src", ROOT / "tests", ROOT):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

#: F-1's steps (`docs/reviews/S11-rulings.md` §6 F-1), the registered one second.
F1_STEPS = (3e-5, 1e-5, 3e-6, 1e-6)


def premises() -> dict[str, Any]:
    """G4: S11.A07's minima per record set and S11.A08's first violation."""
    from test_s11_bases import _KEYS, _POSITIVITY, _three

    from openflowsheet.thermo import wilson_ig, wilson_premises

    recorded: dict[str, Any] = {}
    for which, path in (
        ("real", None),
        ("verification", "benchmarks/s10/verification-records.yaml"),
    ):
        records = wilson_ig.load_records(None if path is None else ROOT / path)
        recorded[which] = [
            {
                "component": minimum.component,
                "premise": minimum.premise,
                "value": minimum.value,
                "value_3sf": _three(minimum.value),
                "registered": _POSITIVITY[which][minimum.component][_KEYS[minimum.premise]],
                "temperature_K": minimum.temperature,
                "where": minimum.where,
            }
            for minimum in wilson_premises.minima(records)
        ]
    widened = dataclasses.replace(wilson_ig.load_records(), temperature_domain=(300.0, 800.0))
    first = wilson_premises.violations(widened)[0]
    recorded["a08_widened_300_800_K"] = {
        "premise": first.premise,
        "component": first.component,
        "value": first.value,
        "temperature_K": first.temperature,
    }
    return recorded


def witness() -> dict[str, Any]:
    """Rulings item 2's table and F-1's step series."""
    import numpy as np
    from s11_column_support import WILSON_CASES, WILSON_STRIPPER
    from test_s11_column_verifier import _target

    from openflowsheet.compile.reference import state_vector
    from openflowsheet.verify import checks

    def worst(results: list[Any]) -> float:
        return max(result.value or 0.0 for result in results)

    table: dict[str, Any] = {}
    for name in (*WILSON_CASES, WILSON_STRIPPER):
        target, state, z = _target(name)
        rest = frozenset(target.spec.variable_ids) - z
        one_sided = checks.derivative_witness(target, state, unstenciled=rest, one_sided=z)
        central = checks.derivative_witness(target, state, unstenciled=z)
        jacobian = target.compiled.jacobian(
            np.array(state_vector(target.spec, state)), target.context
        )
        smallest = min(
            abs(jacobian.data[offset])
            * target.scaling.column[column_id]
            / target.scaling.row[jacobian.row_ids[jacobian.indices[offset]]]
            for column, column_id in enumerate(jacobian.col_ids)
            if column_id in z
            for offset in range(jacobian.indptr[column], jacobian.indptr[column + 1])
            if jacobian.data[offset] != 0.0
        )
        table[name] = {
            "Z": len(z),
            "one_sided_worst": worst(one_sided),
            "one_sided_results": [result.result for result in one_sided],
            "central_worst": worst(central),
            "central_results": [result.result for result in central],
            "smallest_nonzero_scaled_ad_entry_in_Z": smallest,
        }

    target, state, z = _target("C-MW")
    registered = checks.FD_RELATIVE_STEP
    series: dict[str, float] = {}
    try:
        for step in F1_STEPS:
            checks.FD_RELATIVE_STEP = step  # type: ignore[misc]
            series[f"{step:g}"] = worst(checks.derivative_witness(target, state, unstenciled=z))
    finally:
        checks.FD_RELATIVE_STEP = registered  # type: ignore[misc]
    return {
        "item2": table,
        "derivative_tolerance": checks.DERIVATIVE_TOLERANCE,
        "f1_cmw_central_worst_by_step": series,
        "registered_step": registered,
    }


def a46() -> dict[str, Any]:
    """Rulings item 5: each S11.A46 test's worst value, as the test computes it."""
    import test_s11_thermal_kernel as t

    from openflowsheet.models.thermal import kernel as k
    from openflowsheet.thermo.iapws95 import _tsat_bounds

    low, high = _tsat_bounds()
    rows: dict[str, Any] = {}
    for phase, states in (("LIQUID", t.LIQUID_STATES), ("VAPOR", t.VAPOR_STATES)):
        block = t.PhaseFlowBlock(
            t.WATER, "H2O", phase, t.CONTEXT, block_id=t.phase_block_id("S1", phase)
        )
        rows[f"phase flow block, {phase} (20 states)"] = (
            max(t._fd_worst(block, state) for state in states),
            t.FD_TOL,
        )
    saturated = t.SaturatedFlowBlock(t.WATER, "H2O", t.CONTEXT, block_id=t.saturated_block_id("S1"))
    pressures = [low * 1.5 * 1.6**i for i in range(18)]
    rows["saturated, 18 interior states"] = (
        max(
            t._fd_worst(saturated, (0.3 + 0.1 * i, 1.2 - 0.05 * i, p))
            for i, p in enumerate(pressures)
        ),
        t.FD_TOL,
    )
    rows["saturated, p_sigma(T_t)(1 + 1e-6), step 5e-7"] = (
        t._fd_worst(saturated, (0.7, 0.4, low * (1.0 + 1e-6)), step=0.5 * t.FD_STEP),
        t.FD_TOL,
    )
    for below in (1e-6, 1e-4):
        rows[f"saturated, p_sigma(647.0 K)(1 - {below:g}), step 1e-6"] = (
            t._fd_worst(saturated, (0.7, 0.4, high * (1.0 - below)), step=t.FD_STEP),
            t.FD_TOL_TOP,
        )
    rows["isentropic (20 states)"] = (
        max(t._fd_worst(t._isentropic(phase), state) for phase, *state in t.ISENTROPIC_STATES),
        t.FD_TOL,
    )
    identity = 0.0
    for phase, states in (("LIQUID", t.LIQUID_STATES), ("VAPOR", t.VAPOR_STATES)):
        block = t.PhaseFlowBlock(
            t.WATER, "H2O", phase, t.CONTEXT, block_id=t.phase_block_id("S1", phase)
        )
        for total, temperature, pressure in states:
            entries = {(i, j): v for i, j, v in block.jacobian((total, temperature, pressure))}
            v = t._ok(k.phase_properties(t.WATER, t.CONTEXT, temperature, pressure, phase, ("v",)))[
                "v"
            ]
            expected = total * (v[0] - temperature * v[1])
            identity = max(identity, abs(entries[(0, 2)] - expected) / abs(expected))
    rows["identity dh/dP = v - T dv/dT (40 states)"] = (identity, 1e-9)
    identity = 0.0
    for phase, total, t_in, p_in, p_out in t.ISENTROPIC_STATES:
        block = t._isentropic(phase)
        entries = {(i, j): v for i, j, v in block.jacobian((total, t_in, p_in, p_out))}
        t_s = block.state(t_in, p_in, p_out).temperature
        v = t._ok(k.phase_properties(t.WATER, t.CONTEXT, t_in, p_in, phase, ("v",)))["v"]
        expected = -total * t_s * v[1]
        identity = max(identity, abs(entries[(0, 2)] - expected) / abs(expected))
    rows["identity dHs/dP_I = -n T_s (dv/dT)_I (20 states)"] = (identity, 1e-9)
    return {name: {"worst": value, "bound": bound} for name, (value, bound) in rows.items()}


def main() -> int:
    print(json.dumps({"g4": premises(), "witness": witness(), "a46": a46()}, sort_keys=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
