"""S03 WO-S03-1: our side of the column reference comparisons (`docs/derivations/S03-spec.md` §3,
§4, §8; assertions A02 (our half), A06, A07 and A16 of §11).

Our side is `scripts/s03_references_ours.py`: it maps `s03_cases.json` (inputs only) to a
`ColumnSpec`, solves with `solve_column` and the SYN-001 provider, and writes
`benchmarks/s03/references/results/ours-<case>.json`. Expectations are `s03_reference.json`'s
50-digit twin values (the design lane's generator `s03_reference.py`, which imports nothing from
`src/`), compared unrounded in `Decimal`; nothing here imports tool code.
"""

from __future__ import annotations

import functools
import hashlib
import json
import math
import re
import subprocess
import sys
from dataclasses import replace
from decimal import Decimal, getcontext
from pathlib import Path
from typing import Any

import pytest
from test_s02_column_wo1 import SPECS as S02_SPECS

from openflowsheet.models.syn001.cascade import InletState, SideFeed

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import s03_references_ours as ours_side  # noqa: E402

SCRIPTS = REPO_ROOT / "docs" / "derivations" / "scripts"
CASES: dict[str, Any] = json.loads((SCRIPTS / "s03_cases.json").read_bytes())
REFERENCE: dict[str, Any] = json.loads((SCRIPTS / "s03_reference.json").read_bytes())
RESULTS = REPO_ROOT / "benchmarks" / "s03" / "references" / "results"

getcontext().prec = 60

#: §6: T02 §6.4's allowance per kind; the tolerance is `a_k + 1e-6 |v|` with v the twin value.
ALLOWANCE = {"flow": Decimal("3.1e-7"), "T": Decimal("1e-5"), "duty": Decimal("1e-2")}
RELATIVE = Decimal("1e-6")
#: §6 / rule 3 / A06: our side sits within this fraction of a tolerance of the twin.
OURS_FRACTION = Decimal("0.1")
#: A07: T06 A50's rule — non-floats exact, floats to roundoff across architectures.
ROUNDOFF_REL = 1e-12

#: S02's M1–M4 are RC1–RC4 with every pressure at `P_r` (§3).
P_R = 1.0e5
FROM_S02 = {"RC1": "M1", "RC2": "M2", "RC3": "M3", "RC4": "M4"}


def _expected(case: str) -> dict[str, Any]:
    """The twin quantities our side is judged against: `ref.twin.<case>`, and for PC-P the
    SYN-001 root at 1.5e5 Pa, `ref.controls.PC-P.ours` (A06)."""
    if case == "PC-P":
        found: dict[str, Any] = REFERENCE["controls"]["PC-P"]["ours"]
    else:
        found = REFERENCE["twin"][case]["quantities"]
    return found


def tolerance(kind: str, value: str) -> Decimal:
    """§6's formula, evaluated unrounded from the 25-digit twin string."""
    return ALLOWANCE[kind] + RELATIVE * abs(Decimal(value))


@functools.cache
def live(case: str) -> dict[str, Any]:
    """A live solve's record, as JSON round-trips it (the committed file's form)."""
    record: dict[str, Any] = json.loads(json.dumps(ours_side.solve(case), sort_keys=True))
    return record


def _load(case: str) -> dict[str, Any]:
    record: dict[str, Any] = json.loads((RESULTS / f"ours-{case}.json").read_bytes())
    return record


# -- A02 (our half) ------------------------------------------------------------------------------


def test_a02_the_inputs_are_the_registered_file() -> None:
    """A02: our side reads `s03_cases.json`, whose SHA-256 is the one `ref` was derived from."""
    digest = hashlib.sha256((SCRIPTS / "s03_cases.json").read_bytes()).hexdigest()
    assert ours_side.CASES_PATH == SCRIPTS / "s03_cases.json"
    assert ours_side.cases_sha256() == digest == REFERENCE["cases_sha256"]


def test_a02_every_registered_case_has_our_record_or_an_alias() -> None:
    """A02: RC1–RC7, the ten perturbed cases and PC-P have a record each; PC-L's and PC-LI's
    are RC1's (§3.3, §18.3); every committed `ours-*.json` is one of them."""
    assert set(ours_side.OURS_CASES) | set(ours_side.OURS_ALIASES) == set(CASES["cases"])
    assert not set(ours_side.OURS_CASES) & set(ours_side.OURS_ALIASES)
    assert ours_side.OURS_ALIASES == {"PC-L": "RC1", "PC-LI": "RC1"}
    committed = {path.name for path in RESULTS.glob("ours-*.json")}
    assert committed == {f"ours-{case}.json" for case in ours_side.OURS_CASES}


@pytest.mark.parametrize("case", ours_side.OURS_CASES)
def test_a02_the_spec_is_the_registered_case(case: str) -> None:
    """A02: the `ColumnSpec` our side solves carries `cases`'s inputs exactly: N, ends, one
    pressure per stage, every inlet (port, stage, phase, flows, T, P), the end specifications,
    and `Q_j* = 0` exactly on every stage without an end specification."""
    registered = CASES["cases"][case]
    spec = ours_side.column_spec(registered, tuple(CASES["components"]))
    assert spec.stage_count == registered["stage_count"]
    assert (spec.condenser, spec.reboiler) == (registered["condenser"], registered["reboiler"])
    assert spec.pressures == tuple(float(p) for p in registered["stage_pressures_Pa"])
    slot_stages = set(spec.slot_stages())
    for stage, duty in enumerate(spec.duties, start=1):
        assert (duty is None) if stage in slot_stages else (duty == 0.0)
    placed = {inlet.port: inlet for inlet in spec.inlets()}
    assert set(placed) == {inlet["port"] for inlet in registered["inlets"]}
    for inlet in registered["inlets"]:
        found = placed[inlet["port"]]
        assert found.stage == inlet["stage"]
        assert found.state == InletState(
            tuple(float(a) for a in inlet["n_mol_per_s"]),
            float(inlet["T_K"]),
            float(inlet["P_Pa"]),
            inlet["phase"],
        )
    for end, entry in registered["specifications"].items():
        given = spec.end_specification(end)
        assert given is not None
        assert (given.kind, given.value, given.component) == (
            entry["kind"],
            float(entry["value"]),
            entry.get("component"),
        )
    assert set(registered["specifications"]) == set(spec.ends())


@pytest.mark.parametrize("case", sorted(FROM_S02))
def test_a02_rc1_to_rc4_are_s02s_cases_at_p_r(case: str) -> None:
    """§3: RC1–RC4 are S02's M1–M4 (transcribed independently in S02's tests) with every stage
    and inlet pressure at `P_r` exactly."""
    base = S02_SPECS[FROM_S02[case]]

    def at_p_r(state: InletState | None) -> InletState | None:
        return None if state is None else replace(state, pressure=P_R)

    expected = replace(
        base,
        unit_id=ours_side.UNIT,
        pressures=(P_R,) * base.stage_count,
        top=at_p_r(base.top),
        bottom=at_p_r(base.bottom),
        sides=tuple(
            SideFeed(side.port, side.stage, replace(side.state, pressure=P_R))
            for side in base.sides
        ),
    )
    assert ours_side.column_spec(CASES["cases"][case], tuple(CASES["components"])) == expected


@pytest.mark.parametrize("case", ours_side.OURS_CASES)
def test_a02_our_quantity_list_is_the_registered_one(case: str) -> None:
    """A02: our record carries exactly `cases.cases.<case>.quantities`, and the twin has a value
    of the same kind for each."""
    names = {name: kind for name, kind in CASES["cases"][case]["quantities"]}
    assert set(_load(case)["quantities"]) == set(names)
    expected = _expected(case)
    assert {name: entry["kind"] for name, entry in expected.items()} == names


def test_a02_quantity_names_outside_section_4_are_refused() -> None:
    """§4 is the whole list: a name it does not define, a stage outside 1..N, a component the
    column does not carry, or `reflux` away from a total condenser is refused, not guessed."""
    spec = ours_side.column_spec(CASES["cases"]["RC1"], tuple(CASES["components"]))
    for bad in ("T[0]", "T[8]", "reflux", "top[D]", "Q_total", "H[1]"):
        with pytest.raises((ValueError, KeyError)):
            ours_side.quantity(spec, {}, bad)


# -- A06 -----------------------------------------------------------------------------------------


@pytest.mark.parametrize("case", ours_side.OURS_CASES)
def test_a06_our_side_is_within_a_tenth_of_a_tolerance_of_the_twin(case: str) -> None:
    """A06 (rule 3): `CONVERGED` (so S02 §8 and S06 §8 accepted: `solve_column` raises on a
    `CONVERGED` answer that fails them), every equilibrium stage `TWO_PHASE` (RC2 and RC6: the total
    condenser plus six), and every registered quantity within 0.1 × §6's tolerance of `ref`."""
    record = live(case)
    assert record["outcome"] == "CONVERGED", record
    spec = ours_side.column_spec(CASES["cases"][case], tuple(CASES["components"]))
    assert record["signature"] == ["TWO_PHASE"] * len(spec.equilibrium_stages())
    if spec.total_condenser:
        assert len(record["signature"]) == spec.stage_count - 1
    expected = _expected(case)
    worst = Decimal(0)
    for name, kind in CASES["cases"][case]["quantities"]:
        value = record["quantities"][name]
        assert math.isfinite(value)
        entry = expected[name]
        allowed = tolerance(kind, entry["value"])
        # `ref`'s tolerance string is the same formula rounded to 25 significant digits.
        assert abs(allowed - Decimal(entry["tolerance"])) <= Decimal("1e-24") * allowed
        ratio = abs(Decimal(repr(value)) - Decimal(entry["value"])) / allowed
        worst = max(worst, ratio)
        assert ratio <= OURS_FRACTION, (case, name, value, entry["value"], float(ratio))
    # Measured 2026-10-24 (WO-S03-1): worst 3.5e-3 of a tolerance (RC3 `bottom[B]`).
    # WO-S03-1b: RC6 worst 2.0e-2 (`bottom[A]`), RC7 worst 1.1e-6 (`top[B]`); both under 0.1.
    assert worst <= OURS_FRACTION


# -- A07 -----------------------------------------------------------------------------------------


def _assert_equal_to_roundoff(live_value: Any, committed: Any, where: str) -> None:
    if isinstance(committed, float) and isinstance(live_value, float):
        assert math.isclose(live_value, committed, rel_tol=ROUNDOFF_REL, abs_tol=0.0), where
    elif isinstance(committed, dict):
        assert isinstance(live_value, dict) and set(live_value) == set(committed), where
        for key in committed:
            _assert_equal_to_roundoff(live_value[key], committed[key], f"{where}.{key}")
    elif isinstance(committed, list):
        assert isinstance(live_value, list) and len(live_value) == len(committed), where
        for k, (a, b) in enumerate(zip(live_value, committed, strict=True)):
            _assert_equal_to_roundoff(a, b, f"{where}[{k}]")
    else:
        assert type(live_value) is type(committed) and live_value == committed, where


@pytest.mark.parametrize("case", ours_side.OURS_CASES)
def test_a07_our_committed_record_is_what_a_live_solve_produces(case: str) -> None:
    """A07: `ours-<case>.json` reproduces from a live solve — the same keys, every non-float
    exactly, every float to `ROUNDOFF_REL` relative (`abs_tol = 0`); no field is exempt."""
    _assert_equal_to_roundoff(live(case), _load(case), case)


# -- A16 -----------------------------------------------------------------------------------------


def test_a16_the_s02_and_s06_generators_still_check() -> None:
    """A16: S03's generator imports S02's and S06's, so both `--check`s must still pass (every
    claim re-derived, the committed reference byte-identical). Run concurrently."""
    generators = ("s02_reference", "s06_reference")
    running = {
        name: subprocess.Popen(
            [sys.executable, "-I", str(SCRIPTS / f"{name}.py"), "--check"],
            cwd=REPO_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        for name in generators
    }
    for name, process in running.items():
        output, _ = process.communicate(timeout=1800)
        assert process.returncode == 0, output
        assert re.search(
            rf"{re.escape(name)}\.json is byte-identical to the generator's output$",
            output,
            re.MULTILINE,
        ), output
