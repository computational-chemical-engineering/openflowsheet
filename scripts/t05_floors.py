"""Measure T05's implementation floors W0.3 and W0.4 (T05 spec §14, §22) and print them.

W0.3: at each registered trial state of a model, the worst row error as a fraction of its
tolerance (`1e-12 x term_scale`) and the worst Jacobian error as a fraction of its tolerance
(`1e-11` relative, a cancelling partial `1e-11 x` its partial scale). Spec §14 requires the
tolerances to sit at least 100x above the floors, i.e. every ratio here at most `1e-2`.

W0.4: the PH kernel's `|T* - T_ref|` on the PH-type cases, against the 40-digit roots.

The measurement reuses the gate's own harness (`tests/t05_trial_states.py`) and the builders the
model tests pass it, so the numbers are the ones the gate checks. Models whose tests do not exist
yet are skipped and named.

Usage:
    PYTHONPATH=src:. .venv/bin/python scripts/t05_floors.py
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT))

#: Model id -> the test module whose `build_trial` assembles it.
MODELS = {
    "syn001.ph_flash": "test_t05_ph_flash",
    "syn001.valve": "test_t05_valve",
    "syn001.liquid_pump": "test_t05_pump",
    "syn001.conversion_reactor": "test_t05_reactor",
    "syn001.component_separator": "test_t05_separator",
    "syn001.heat_exchanger": "test_t05_exchanger",
}


def main() -> int:
    from t05_support import CONTEXT, PROVIDER, REF, error  # noqa: PLC0415
    from t05_trial_states import compare_trial_state, trial_states  # noqa: PLC0415

    from openflowsheet.models.syn001.ph_kernel import ph_state  # noqa: PLC0415

    failed = False
    print("W0.3 (worst error / tolerance per model; spec §14 requires <= 1e-2)")
    for model_id, module_name in MODELS.items():
        try:
            module = importlib.import_module(module_name)
        except ModuleNotFoundError:
            print(f"  {model_id}: not implemented yet (no {module_name})")
            continue
        rows = jacobian = 0.0
        twin = REF["measured"]["floors_53_bit"]
        for state_id in trial_states(model_id):
            comparison = compare_trial_state(model_id, state_id, module.build_trial)
            failed |= bool(comparison.failures)
            rows = max(rows, comparison.worst_row_ratio)
            jacobian = max(jacobian, comparison.worst_jacobian_ratio)
            print(f"  {comparison.summary()}")
        print(
            f"  {model_id}: rows {rows:.3g}, Jacobian {jacobian:.3g} of tolerance "
            f"(as relative errors {rows * 1e-12:.3g} and {jacobian * 1e-11:.3g}; twin's 53-bit "
            f"floors {twin['rows_relative_to_term_scale'][model_id]} and "
            f"{twin['jacobian_relative'][model_id]})"
        )
        failed |= rows > 1e-2 or jacobian > 1e-2

    print("W0.4 (PH kernel |T* - T_ref|, K)")
    kernel = importlib.import_module("test_t05_ph_kernel")
    for case_id in kernel.PH_TYPE:
        n, pressure, target = kernel.kernel_target(case_id)
        answer = ph_state(PROVIDER, n, pressure, target, CONTEXT)
        assert answer.status == "ok" and answer.temperature is not None, case_id
        expected = REF["unit_cases"][case_id]["expected"]
        registered = expected["T_K"] if "T_K" in expected else expected["outlet"]["T_K"]
        twin_floor = REF["measured"]["floors_53_bit"]["ph_kernel_T_K"][case_id]
        print(
            f"  {case_id}: {error(answer.temperature, registered):.3g} "
            f"(twin {twin_floor}; {answer.route}, {answer.evaluations} evaluations)"
        )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
