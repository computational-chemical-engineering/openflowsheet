"""Shared support for T06's tests and its ensemble runner. Not collected as tests.

`T06_REVISION_POLICY` is the policy the T06 ensemble's revision path runs — **(A4)**
`T06-revision-v2` (spec §6.6 (A4), ADR 0018 D6): `T06_REVISION_POLICY_V1` with only
`globalization.eo_core` changed, to `newton_refined`. `T06_REVISION_POLICY_V1` is
`T06-revision-v1`, run 1's policy, which stays defined (spec §6.6 as amended by design note
`docs/design/T06-F4-recovery.md` §5.6 and §6.1; ADR 0015): `T05b-v2` with only
`globalization.eo_recovery` changed, to `homotopy_or_sequential_restart`. Both are constructed
once, with `T05b-v2`, in `openflowsheet.application.policies` (T07 W3a);
`test_t06_f4_policy.py` checks v1 (A65) and `test_t06_w18_policy.py` v2 (A86).

`registered_root` and `worst_ratio` compare a state with a twin root at T02 §6.4's allowances
(flows 3.1e-7 mol/s, `T` 1e-5 K, `P` 0.1 Pa, duty and work 1e-2 W), at the registered strings'
full precision.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml
from conftest import load_yaml

from openflowsheet.application.policies import T06_REVISION_V1, T06_REVISION_V2
from openflowsheet.orchestrator.trace import SolvePolicy

__all__ = [
    "ALLOWANCE",
    "CORPUS",
    "T05_COUPLED",
    "T06_CASES",
    "T06_REVISION_POLICY",
    "T06_REVISION_POLICY_V1",
    "case_document",
    "registered_root",
    "worst_ratio",
]

REPO_ROOT = Path(__file__).resolve().parents[1]
T06_CASES = REPO_ROOT / "benchmarks" / "t06" / "cases"
_T06_REFERENCE = load_yaml(REPO_ROOT / "benchmarks" / "t06" / "reference_values.yaml")
_T05_REFERENCE = load_yaml(REPO_ROOT / "benchmarks" / "t05" / "reference_values.yaml")
#: `ref.closed_form.corpus_cases` (T06 spec §4.3): the twin roots of the new corpus flowsheets.
CORPUS: dict[str, Any] = _T06_REFERENCE["closed_form"]["corpus_cases"]
#: `ref.coupled_cases` of T05 (C1, C2, C3).
T05_COUPLED: dict[str, Any] = _T05_REFERENCE["coupled_cases"]
#: T02 §6.4's allowances by column suffix: flows, `T`, `P`, duty, work, extent.
ALLOWANCE: Mapping[str, float] = {
    "n": 3.1e-7,
    "T": 1e-5,
    "P": 0.1,
    "Q": 1e-2,
    "W": 1e-2,
    "xi": 3.1e-7,
}

#: Constructed in `openflowsheet.application.policies`, where T07 W3a moved the chain (W0 flag
#: E6; design note §12.2): the application's registered policy is the ensemble's, one object.
T06_REVISION_POLICY_V1: SolvePolicy = T06_REVISION_V1
T06_REVISION_POLICY: SolvePolicy = T06_REVISION_V2


def case_document(case: str) -> dict[str, Any]:
    """A fresh copy of a T06 case revision (`benchmarks/t06/cases/<case>.yaml`)."""
    loaded: dict[str, Any] = yaml.safe_load((T06_CASES / f"{case}.yaml").read_text("utf-8"))
    return loaded


def registered_root(entry: Mapping[str, Any]) -> dict[str, tuple[Decimal, float]]:
    """Every registered coordinate of a twin root, `column -> (value, allowance)`: stream flows,
    `T` and `P`, a lifted stream's phase flows, duties, work and extents. Reads both spellings of
    the phase-flow keys (T05's `vapor_n_mol_per_s`, T06's `vapor_mol_per_s`)."""
    out: dict[str, tuple[Decimal, float]] = {}
    for stream, state in entry["streams"].items():
        for component, value in zip("ABC", state["n_mol_per_s"], strict=True):
            out[f"{stream}.n.{component}"] = (Decimal(value), ALLOWANCE["n"])
        out[f"{stream}.T"] = (Decimal(state["T_K"]), ALLOWANCE["T"])
        out[f"{stream}.P"] = (Decimal(state["P_Pa"]), ALLOWANCE["P"])
        for phase, keys in (
            ("vap", ("vapor_mol_per_s", "vapor_n_mol_per_s")),
            ("liq", ("liquid_mol_per_s", "liquid_n_mol_per_s")),
        ):
            for key in (key for key in keys if key in state):
                for component, value in zip("ABC", state[key], strict=True):
                    out[f"{stream}.{phase}.{component}"] = (Decimal(value), ALLOWANCE["n"])
    for field, suffix in (("duty_W", "Q"), ("work_W", "W"), ("extent_mol_per_s", "xi")):
        for unit, value in (entry.get(field) or {}).items():
            out[f"{unit}.{suffix}"] = (Decimal(value), ALLOWANCE[suffix])
    return out


def worst_ratio(
    state: Mapping[str, float], expected: Mapping[str, tuple[Decimal, float]]
) -> tuple[float, str]:
    """The largest `|x - x_ref| / allowance` over the registered coordinates, and where. A
    registered coordinate missing from the state is a defect of the comparison (`KeyError`)."""
    return max(
        (float(abs(Decimal(state[column]) - value) / Decimal(allowance)), column)
        for column, (value, allowance) in expected.items()
    )
