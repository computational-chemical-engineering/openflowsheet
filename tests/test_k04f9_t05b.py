"""K04-F9 W5: the verifier's projection on T05b's EO cases and SYN-001's legacy set — the new
cases and the cross-cutting assertions (spec §6, §8; ADR 0013 D1–D4).

- **X11 NP-GC**: NP-G's liquid product split in two by a splitter — D2's load-bearing case.
- **X15 INJ-F10**: SYN-001 once-through with the flash forced all-liquid — K04 §4.7's flash-outlet
  clause discharged by §4.4 in the legacy set (D4), and D2's negative control.
- **X03**: exact zeros stay exact, and the check ids do not depend on where a check is judged, at
  K04's INJ-2, SC-1 and every DZ root.
- **X01**: `transformations.projection` at those states (the grammar; `final_state` /
  `residual_not_passed` at the residual-failing injections is asserted beside each injection's
  own test).
- **X26** (as amended, ruling round Q-S1, R-063): every registered comparison's realized
  deviation `≤ 1/10` of its allowance; K04's solution-error bound `b` recorded for every case,
  never thresholded.

`ref` = `benchmarks/k04f9/reference_values.yaml`. Values marked *regression* are self-generated:
pinned beside their assertion, reported to the design lane if they move, never re-pinned.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from decimal import Decimal
from functools import cache
from typing import Any

import pytest
import yaml
from conftest import load_yaml
from t05_w12_support import bind, planned_step
from t05b_support import (
    POLICY_V2,
    REPO_ROOT,
    dz3,
    dz10,
    dz12,
    fresh_flash_ratios,
    judged_where,
    np_gc,
    revision_projection,
)
from t05b_support import REF as T05B_REF
from test_k04_checks import TRIVIAL_ROOT_OFFSET
from test_k04_injections import solved as solved_syn001
from test_t05b_contract import Solved, solve, solved
from test_t05b_dormancy import _dz10, _dz12
from test_t05b_dormancy import _solved as solved_dormant
from test_t05b_openings import realized_ratio as b31_realized_ratio
from test_t05b_zero_flow import _dz3
from test_t05b_zero_flow import _solved as solved_zero_flow

from openflowsheet.models.syn001.flowsheet import STREAMS
from openflowsheet.orchestrator.tear import Syn001TearProblem
from openflowsheet.thermo.syn001 import Syn001Provider
from openflowsheet.verify import CheckResult
from openflowsheet.verify.certificate import (
    CheckPolicy,
    SolutionCertificate,
    _project,
    _screen,
    run_checks,
    verify,
    verify_revision,
)
from openflowsheet.verify.checks import residual_checks
from openflowsheet.verify.projection import PROJECTED_CATEGORIES, Projection
from openflowsheet.verify.table import UNRESOLVED_ENTHALPY_NOTE

REF: dict[str, Any] = yaml.safe_load(
    (REPO_ROOT / "benchmarks" / "k04f9" / "reference_values.yaml").read_text()
)
#: T02 §6.4's flow allowance, the one X11 compares NP-GC's copies at.
FLOW_ALLOWANCE = 3.1e-7
#: Spec §7: the largest step component the exact-zero rule may discard.
DISCARD_BOUND = 1e-20


def _by_id(certificate: SolutionCertificate) -> dict[str, CheckResult]:
    return {check.id: check for check in certificate.checks}


def _projected_ids(checks: Sequence[CheckResult]) -> list[str]:
    return [check.id for check in checks if check.category in PROJECTED_CATEGORIES]


def _relative(got: float, expected: str) -> float:
    return float(abs(Decimal(got) - Decimal(expected)) / abs(Decimal(expected)))


# -- X11: NP-GC ------------------------------------------------------------------------------


@cache
def _np_gc() -> Solved:
    return solve(np_gc(), POLICY_V2)


def test_x11_np_gc_is_verified_with_its_copies_closed() -> None:
    """NP-GC: one ulp of bubble excess in either copy of NP-G's saturated liquid product moves the
    envelope by 0.10 `τ_E` (`ref.closed_form.kink.NP-GC`); D2 reads both copies as liquid at the
    projection, D3 routes the PH flash as NP-G's, and every balance closes."""
    result = _np_gc()
    assert result.run.outcome == "CONVERGED", result.run.message
    certificate = result.certificate
    assert certificate is not None
    assert certificate.verification_status == "VERIFIED", [
        (c.id, c.value) for c in certificate.checks if c.result == "fail"
    ]
    judged_where(certificate, "projection")
    checks = _by_id(certificate)
    split = checks["independent_split.U-PHF.S1"]
    assert (split.result, split.reason) == ("not_applicable", "fresh_flash_unresolved")
    assert not any(name.startswith("independent_split.U-PHF.S1.") for name in checks)
    assert "phase_admissibility.U-PHF.S1.saturation" not in checks
    assert checks["phase_admissibility.U-PHF.S1.closure"].result == "pass"
    for name in ("energy_balance.U-PHF", "energy_balance.U-SPLIT", "energy_balance.envelope"):
        check = checks[name]
        assert check.value is not None and check.tolerance is not None
        assert abs(check.value) <= 1e-3 * check.tolerance, (name, check.value)
    phf = checks["energy_balance.U-PHF"].independence_qualification or ""
    for stream in ("S2", "S3"):
        assert UNRESOLVED_ENTHALPY_NOTE.format(stream=stream) in phf, stream
    assert not any(c.category == "residual" and c.result == "fail" for c in certificate.checks)
    state = result.run.state
    assert state is not None
    case = REF["closed_form"]["cases"]["NP-GC"]
    for stream in ("S4", "S5"):
        for component, expected in zip("ABC", case[f"{stream}_n_mol_per_s"], strict=True):
            got = state[f"{stream}.n.{component}"]
            assert abs(Decimal(got) - Decimal(expected)) <= Decimal(FLOW_ALLOWANCE), (
                stream,
                component,
                got,
            )


# -- X15: INJ-F10 ----------------------------------------------------------------------------


def inj_f10() -> tuple[Any, Any, dict[str, float]]:
    """K04-F9 INJ-F10 (`ref.closed_form.injections.INJ-F10`): SYN-001 once-through `x(t*)` with the
    flash's split forced all-liquid — `S4 = 0`, `S4.N = 0`, `S5 = S3.n`, `S5.N = 3`, `S7 = S5`,
    `S6 = 0` — and `U-FLASH.Q` closed (`Q_flash_forced_W`) so `FLASH-duty` holds."""
    variants = {
        entry["case_id"]: entry
        for entry in load_yaml(REPO_ROOT / "benchmarks" / "syn001" / "reference_values.yaml")[
            "variants"
        ]
    }
    flowsheet, result, base = solved_syn001(variants, "SYN-001-once-through")
    state = dict(base)
    for component in "ABC":
        state[f"S4.n.{component}"] = 0.0
        state[f"S5.n.{component}"] = state[f"S3.n.{component}"]
        state[f"S6.n.{component}"] = 0.0
        state[f"S7.n.{component}"] = state[f"S5.n.{component}"]
    state["S4.N"] = 0.0
    state["S5.N"] = sum(state[f"S5.n.{component}"] for component in "ABC")
    state["U-FLASH.Q"] = float(
        Decimal(REF["closed_form"]["injections"]["INJ-F10"]["Q_flash_forced_W"])
    )
    return flowsheet, result, state


def test_x15_inj_f10_a_wrong_flash_branch_fails_the_flash_and_envelope_balances() -> None:
    """A wrong flash branch is a root of the compiled rows whose products are not at their
    saturation points: the fresh flash of S5 (0.384 past its bubble point, far outside D2's
    `ε_adm`) forms the missing vapour, and exactly the two balances that read it fail by its
    latent heat — at the projection, which leaves a root where it is."""
    entry = REF["closed_form"]["injections"]["INJ-F10"]
    flowsheet, result, state = inj_f10()
    certificate = verify(flowsheet, result, state=state)
    assert certificate.verification_status == "FAILED"
    assert certificate.false_success_detected
    judged_where(certificate, "projection")
    failing = {c.id for c in certificate.checks if c.result == "fail"}
    assert failing == {"energy_balance.flash", "energy_balance.envelope"}
    checks = _by_id(certificate)
    for name in failing:
        value = checks[name].value
        assert value is not None
        assert _relative(value, entry["energy_balance_flash_W"]) <= 1e-9, (name, value)
    assert all(c.result == "pass" for c in certificate.checks if c.category == "residual")
    assert certificate.regularity is not None
    assert certificate.regularity.status == "NO_RANK_LOSS_DETECTED"


# -- X03 and X01 at the certificate --------------------------------------------------------------


def _legacy_projection(flowsheet: Any, state: Mapping[str, float]) -> Projection:
    """The verifier's projection on SYN-001's nominal declaration (`verify`'s path)."""
    policy = CheckPolicy()
    target = Syn001TearProblem(flowsheet)
    rows, _ = residual_checks(
        target.compiled,
        target.spec,
        state,
        target.context,
        target.spec.row_kinds,
        policy.tolerances,
    )
    return _project(
        target,
        state,
        rows,
        _screen(target, state),
        zero_flow=(),
        streams=STREAMS,
        provider=Syn001Provider(),
        policy=policy,
    )


def _zeros_kept(
    kinds: Mapping[str, str], state: Mapping[str, float], projection: Projection
) -> int:
    """X03: every molar-flow column exactly `0.0` at `x_final` is `0.0` at `x̃`; the count."""
    zeros = [c for c, v in state.items() if kinds.get(c) == "molar_flow" and v == 0.0]
    assert all(projection.state[column] == 0.0 for column in zeros), [
        (c, projection.state[c]) for c in zeros if projection.state[c] != 0.0
    ]
    assert projection.discarded <= DISCARD_BOUND, projection.discarded
    return len(zeros)


def test_x03_inj_2_the_trivial_root_projects_onto_itself() -> None:
    """K04's INJ-2 (A18): S3 forced all-liquid, `S3.vap = 0`, `S3.V = 0`, both duties closed. A root
    of the compiled rows: the projection is applied, holds the exact zeros, and the fresh-flash
    ids are the unprojected ones (`.bubble`, never `.closure`)."""
    variants = {
        entry["case_id"]: entry
        for entry in load_yaml(REPO_ROOT / "benchmarks" / "syn001" / "reference_values.yaml")[
            "variants"
        ]
    }
    flowsheet, result, base = solved_syn001(variants, "SYN-001-once-through")
    state = dict(base)
    for component in "ABC":
        state[f"S3.liq.{component}"] = state[f"S3.n.{component}"]
        state[f"S3.vap.{component}"] = 0.0
    state["S3.L"] = sum(state[f"S3.n.{c}"] for c in "ABC")
    state["S3.V"] = 0.0
    state["U-HEAT.Q"] -= TRIVIAL_ROOT_OFFSET
    state["U-FLASH.Q"] += TRIVIAL_ROOT_OFFSET
    certificate = verify(flowsheet, result, state=state)
    assert certificate.verification_status == "FAILED"
    judged_where(certificate, "projection")
    projection = _legacy_projection(flowsheet, state)
    assert projection.judged_at == "projection"
    kinds = Syn001TearProblem(flowsheet).spec.variable_kinds
    assert _zeros_kept(kinds, state, projection) >= 4  # S3.vap.{A,B,C}, S3.V at least
    unprojected, _ = run_checks(flowsheet, state)
    assert _projected_ids(certificate.checks) == _projected_ids(unprojected)
    assert "phase_admissibility.S3.bubble" in _by_id(certificate)


def _dz_root(case: str) -> tuple[Any, dict[str, Any], dict[str, float], SolutionCertificate]:
    """`(binding, document, x_final, certificate)` of a DZ case's v2 root."""
    regions: dict[str, tuple[Callable[[], dict[str, Any]], Any]] = {
        "DZ-3": (dz3, lambda: _dz3()[1]),
        "DZ-10": (dz10, lambda: _dz10()[0]),
        "DZ-12": (dz12, lambda: _dz12()[0]),
    }
    if case in regions:
        builder, region = regions[case]
        document = builder()
        binding = bind(document)
        result = region()
        certificate = verify_revision(
            binding,
            document,
            result,
            state=dict(result.state),
            solve_plan=planned_step(binding, POLICY_V2).solve_plan,
        )
        return binding, document, dict(result.state), certificate
    solved_case = (
        solved_zero_flow(case)
        if case in ("DZ-1", "DZ-2", "DZ-4", "DZ-5")
        else solved_dormant(case, "v2")
    )
    assert solved_case.certificate is not None and solved_case.run.state is not None
    return (
        solved_case.binding,
        solved_case.document,
        dict(solved_case.run.state),
        solved_case.certificate,
    )


DZ_ROOTS = (
    "DZ-1",
    "DZ-2",
    "DZ-3",
    "DZ-4",
    "DZ-5",
    "DZ-6",
    "DZ-7",
    "DZ-8",
    "DZ-9",
    "DZ-10",
    "DZ-12",
)


@pytest.mark.parametrize("case", ["SC-1", *DZ_ROOTS])
def test_x03_x01_exact_zeros_and_ids_at_the_zero_flow_roots(case: str) -> None:
    """SC-1 (`S*.n.A`, `S*.n.C = 0`) and every DZ root: `VERIFIED` at the projection, every exact
    zero held, the fresh-flash ids those of the table at `x_final`."""
    if case == "SC-1":
        result = solved("SC-1")
        assert result.certificate is not None and result.run.state is not None
        binding, document = result.binding, result.document
        state, certificate = dict(result.run.state), result.certificate
    else:
        binding, document, state, certificate = _dz_root(case)
    assert certificate.verification_status == "VERIFIED"
    judged_where(certificate, "projection")
    projection, unprojected = revision_projection(binding, document, state)
    assert projection.judged_at == "projection", projection.reason
    _zeros_kept(binding.spec.variable_kinds, state, projection)
    assert _projected_ids(certificate.checks) == _projected_ids(unprojected)


# -- X26: W0.9's rule, amended -------------------------------------------------------------------

#: *Regression* (measured 2026-09-25, F9 W5): K04's `solution_error_bound_scaled` per case.
#: A recorded bound below this is set by roundoff, not by where Newton stopped (the truncation-set
#: values here are >= 3.8e-10; the roundoff-set ones <= 3.3e-15 on both CI platforms).
ROUNDOFF_FLOOR = 1e-12

SOLUTION_ERROR_BOUNDS = {
    "SC-1": 8.568e-16,
    "SC-2": 0.0,
    "SC-3": 2.563e-15,
    "SC-4": 1.051e-15,
    "NP-1": 2.130e-16,
    "NP-2": 1.306e-15,
    "NP-3": 3.840e-10,
    "NP-G": 6.978e-8,
    "DZ-1": 0.0,
    "DZ-2": 0.0,
    "DZ-3": 3.679e-8,
    "DZ-4": 0.0,
    "DZ-5": 0.0,
    "DZ-6": 0.0,
    "DZ-7": 0.0,
    "DZ-8": 0.0,
    "DZ-9": 0.0,
    "DZ-10": 3.679e-8,
    "DZ-12": 3.255e-15,
    "NP-GC": 1.212e-7,
}
#: K04-F9 X26 (a) as amended (Q-S1, R-063): every registered comparison's realized deviation is at
#: most this fraction of its allowance — ADR 0007 D2.4's band edge. A ratio above it is reported to
#: the design lane, never absorbed by widening the allowance.
REALIZED_FRACTION = 0.1
#: T02 §6.4's allowances, as `ref.tolerances.coupled_allowances` (T05b) states them.
ALLOWANCE: Mapping[str, float] = {
    kind: float(Decimal(value))
    for kind, value in T05B_REF["tolerances"]["coupled_allowances"].items()
}
#: X26 (a)'s population: every case whose final state is compared with `ref` at those allowances.
#: NP-G registers no comparison (its `b` is recorded only); DZ-1, DZ-2, DZ-4…DZ-9 are compared
#: exactly and are not in it.
REALIZED_CASES = (
    "SC-1",
    "SC-2",
    "SC-3",
    "SC-4",
    "NP-1",
    "NP-2",
    "NP-3",
    "DZ-3",
    "DZ-10",
    "DZ-12",
    "NP-GC",
    # T05b B31 (b)–(c) (ruling round Q-S9): the closed forms of `test_t05b_openings`.
    "CH-UP",
    "CH-DZ12",
    "CH-3",
    "CH-DOWN",
)


def _allowance(column: str) -> float:
    """The allowance of a state column by its kind (`T`, `P`, a duty, else a flow)."""
    kind = column.rsplit(".", 1)[-1]
    return {"T": ALLOWANCE["T"], "P": ALLOWANCE["P"], "Q": ALLOWANCE["duty"]}.get(
        kind, ALLOWANCE["flow"]
    )


def _registered_comparison(case: str) -> dict[str, str]:
    """`{column: registered value}` — exactly the columns the case's own assertion compares with
    `ref` at T02 §6.4's allowances (B08–B11's `_root`, B12's `_near_pure_root`, B16's and B26's
    `S4.T`, B27's root, X11's copies)."""
    if case.startswith("SC-"):
        compared: dict[str, str] = {}
        for key, entry in T05B_REF["single_component_cases"][case]["root"].items():
            if not isinstance(entry, dict):
                if key.endswith((".Q", ".W")):
                    compared[key] = entry
                continue
            for field, prefix in (
                ("n_mol_per_s", "n"),
                ("vapor_mol_per_s", "vap"),
                ("liquid_mol_per_s", "liq"),
            ):
                for component, value in zip("ABC", entry.get(field, ()), strict=False):
                    compared[f"{key}.{prefix}.{component}"] = value
            for field, suffix in (("T_K", "T"), ("P_Pa", "P")):
                if field in entry:
                    compared[f"{key}.{suffix}"] = entry[field]
        return compared
    if case.startswith("NP-") and case != "NP-GC":
        root = T05B_REF["near_pure_cases"][case]["root"]
        compared = {}
        for index, component in enumerate("ABC"):
            compared[f"S2.n.{component}"] = root["vapor_mol_per_s"][index]
            compared[f"S3.n.{component}"] = root["liquid_mol_per_s"][index]
        compared["S2.T"] = compared["S3.T"] = root["T_K"]
        return compared
    if case == "DZ-3":
        return {"S4.T": T05B_REF["dormant_cases"]["DZ-3"]["root"]["S4.T"]}
    if case == "DZ-10":
        return {"S4.T": T05B_REF["dormant_non_lifted_cases"]["DZ-10"]["phf1_T_K"]}
    if case == "DZ-12":
        return dict(T05B_REF["dormant_non_lifted_cases"]["DZ-12"]["root"])
    assert case == "NP-GC", case
    registered = REF["closed_form"]["cases"]["NP-GC"]
    return {
        f"{stream}.n.{component}": value
        for stream in ("S4", "S5")
        for component, value in zip("ABC", registered[f"{stream}_n_mol_per_s"], strict=True)
    }


def _certificate(case: str) -> SolutionCertificate:
    if case == "NP-GC":
        certificate = _np_gc().certificate
    elif case in DZ_ROOTS:
        certificate = _dz_root(case)[3]
    else:
        certificate = solved(case).certificate
    assert certificate is not None
    return certificate


def _final_state(case: str) -> dict[str, float]:
    if case == "NP-GC":
        state = _np_gc().run.state
    elif case in DZ_ROOTS:
        state = _dz_root(case)[2]
    else:
        state = solved(case).run.state
    assert state is not None
    return dict(state)


def realized_ratio(case: str) -> tuple[float, str]:
    """X26 (a): the largest `|x_final − ref| / allowance` over the case's registered comparison,
    and the column it is at (`ref`'s values at full precision). B31's cases compare with their
    closed forms (`test_t05b_openings.realized_ratio`)."""
    if case.startswith("CH-"):
        return b31_realized_ratio(case)
    state = _final_state(case)
    return max(
        (float(abs(Decimal(state[column]) - Decimal(value))) / _allowance(column), column)
        for column, value in _registered_comparison(case).items()
    )


@pytest.mark.parametrize("case", SOLUTION_ERROR_BOUNDS)
def test_x26_b_is_recorded(case: str) -> None:
    """X26 (b): `b` is a *regression* value, compared with no threshold (K04 §7.4: evidence, not a
    check). The values are pinned where they are set by a Newton step's truncation error, which
    reproduces across platforms; a value at roundoff (a residual of a few ulps times `||J^-1||`)
    differs in its leading digits between x86-64 and aarch64 (DZ-12: 3.255e-15 vs 3.309e-15, CI run
    on `e4e4990`), so it is held only below the roundoff floor (ADR 0007: roundoff floats are not a
    cross-platform promise)."""
    bound = _certificate(case).solution_error_bound_scaled
    assert bound is not None
    registered = SOLUTION_ERROR_BOUNDS[case]
    if registered < ROUNDOFF_FLOOR:
        assert bound < ROUNDOFF_FLOOR, bound
    else:
        assert bound == pytest.approx(registered, rel=1e-3, abs=1e-18)


@pytest.mark.parametrize("case", REALIZED_CASES)
def test_x26_the_realized_deviation_is_a_tenth_of_the_allowance(case: str) -> None:
    """X26 (a): the realized deviation of every registered comparison is `<= 1/10` of its
    allowance (*measured*, recorded in `docs/t05b-measurements.md`: NP-GC 0.022, DZ-3 and DZ-10
    0.081)."""
    ratio, column = realized_ratio(case)
    assert ratio <= REALIZED_FRACTION, (case, column, ratio)


def test_x07_x08_x11_the_fresh_flash_values_at_the_projection() -> None:
    """Spec §7 row 3 over the EO cases the projection exists for: every fresh-flash value
    `≤ 1e-3` of its tolerance at DZ-3, DZ-10, NP-G and NP-GC."""
    for certificate in (
        _certificate("DZ-3"),
        _certificate("DZ-10"),
        _certificate("NP-G"),
        _certificate("NP-GC"),
    ):
        ratios = fresh_flash_ratios(certificate.checks)
        assert ratios and max(ratios.values()) <= 1e-3, max(ratios.items(), key=lambda i: i[1])
