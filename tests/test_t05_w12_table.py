"""T05 W12: the verifier table's T05 entries at the twin's coupled states, and A20's second branch.

Spec `docs/derivations/T05-unit-models-spec.md` §12.2 (errata applied), §15 A20 and A21's check
half; design note `docs/design/T05-generalization.md` §4.3 (ids, order, conventions, one-sided
semantics, declared-phase ports, qualifications) and §8 (W12). The states are the design lane's
40-digit twin (`ref.coupled_cases`) as doubles, judged by `verify_revision` on a `CONVERGED`
region solve started there (`t05_w12_support.solve_from`; no new API). The certificates of the
actual coupled solves are W13's.

The ids below are written out from §12.2 per case, not copied from a run: a check the table
drops, renames or reorders fails the pinned list.
"""

from __future__ import annotations

import copy
from typing import Any

import pytest
from t05_w12_support import bind, duty_pin, solve_from
from test_t05_w11_cases import case_document, reference_state

from openflowsheet.compiled import EvaluationContext
from openflowsheet.models.revision_flowsheet import parse_revision
from openflowsheet.orchestrator.splits import lifted_splits
from openflowsheet.thermo.syn001 import Syn001Provider
from openflowsheet.verify import CheckResult
from openflowsheet.verify.certificate import CheckPolicy, SolutionCertificate, verify_revision
from openflowsheet.verify.checks import qualification
from openflowsheet.verify.table import REACTION_DATUM_NOTE, revision_checks

SOLVABLE = ("SYN-001-UL-C1", "SYN-001-UL-C2", "SYN-001-UL-C3")
CONTEXT = EvaluationContext(model_version="t05-w12", constants_sha256="0" * 64)
#: The one-sided checks (§4.3): passes iff `value <= τ`; the rest are two-sided `|value| <= τ`.
ONE_SIDED_SUFFIXES = (".direction", ".heat_flow", ".hot_end", ".cold_end", ".bubble", ".dew")


def _abc(prefix: str) -> list[str]:
    return [f"{prefix}.{c}" for c in "ABC"]


def _split(unit: str, stream: str, closure: str) -> list[str]:
    return [
        f"phase_admissibility.{unit}.{stream}.{closure}",
        f"independent_split.{unit}.{stream}.total",
        *_abc(f"independent_split.{unit}.{stream}"),
    ]


_FEED_SPECIFICATION = [
    *_abc("specification.U-FEED.n"),
    "specification.U-FEED.T",
    "specification.U-FEED.P",
]

#: §12.2's rows for each case, in §4.3's order: material, energy, specification, the one-sided
#: bounds (after the generic ones, which are not listed), then the lifted splits and the
#: declared-phase ports. Residual rows, aliases and the derivative witness are the generic
#: machinery's and are not listed either.
TABLE_IDS: dict[str, list[str]] = {
    "SYN-001-UL-C1": [
        *_abc("material_balance.U-PUMP"),
        *_abc("material_balance.U-HEAT"),
        *_abc("material_balance.U-HEAT.lifted_split"),
        "material_balance.U-HEAT.total.V",
        "material_balance.U-HEAT.total.L",
        *_abc("material_balance.U-VLV"),
        *_abc("material_balance.U-VLV.lifted_split"),
        "material_balance.U-VLV.total.V",
        "material_balance.U-VLV.total.L",
        *_abc("material_balance.U-PHF"),
        "material_balance.U-PHF.total.vapor",
        "material_balance.U-PHF.total.liquid",
        *_abc("material_balance.envelope"),
        "energy_balance.U-PUMP",
        "energy_balance.U-PUMP.work_relation",
        "energy_balance.U-HEAT",
        "energy_balance.U-VLV",
        "energy_balance.U-PHF",
        "energy_balance.envelope",
        *_FEED_SPECIFICATION,
        "specification.U-PUMP.outlet_pressure",
        "specification.U-HEAT.T",
        "specification.U-VLV.outlet_pressure",
        "specification.U-PHF.duty",
        "specification.U-PHF.temperature",
        "specification.U-PHF.pressure.vapor",
        "specification.U-PHF.pressure.liquid",
        "bounds_and_domain.U-PUMP.direction",
        "bounds_and_domain.U-VLV.direction",
        *_split("U-HEAT", "S3", "bubble"),
        *_split("U-VLV", "S4", "closure"),
        *_split("U-PHF", "S4", "closure"),
        "phase_admissibility.U-PUMP.inlet",
        "phase_admissibility.U-PUMP.outlet",
        "phase_admissibility.U-HEAT.inlet",
    ],
    "SYN-001-UL-C2": [
        *_abc("material_balance.U-MIX"),
        *_abc("material_balance.U-RX"),
        *_abc("material_balance.U-RX.lifted_split"),
        "material_balance.U-RX.total.V",
        "material_balance.U-RX.total.L",
        *_abc("material_balance.U-SEP"),
        *_abc("material_balance.envelope"),
        "energy_balance.U-MIX",
        "energy_balance.U-RX",
        "energy_balance.U-SEP",
        "energy_balance.envelope",
        *_FEED_SPECIFICATION,
        "specification.U-RX.conversion",
        "specification.U-RX.T",
        "specification.U-RX.pressure",
        *_abc("specification.U-SEP.split"),
        "specification.U-SEP.temperature.top",
        "specification.U-SEP.temperature.bottom",
        "specification.U-SEP.pressure.top",
        "specification.U-SEP.pressure.bottom",
        *_split("U-RX", "S3", "bubble"),
        "phase_admissibility.U-MIX.inlet.S1",
        "phase_admissibility.U-MIX.inlet.S4",
        "phase_admissibility.U-MIX.outlet",
        "phase_admissibility.U-RX.inlet",
        "phase_admissibility.U-SEP.top",
        "phase_admissibility.U-SEP.bottom",
    ],
    "SYN-001-UL-C3": [
        *_abc("material_balance.U-HX.hot"),
        *_abc("material_balance.U-HX.cold"),
        *_abc("material_balance.U-MIX"),
        *_abc("material_balance.U-PHF"),
        "material_balance.U-PHF.total.vapor",
        "material_balance.U-PHF.total.liquid",
        *_abc("material_balance.U-SPLIT"),
        *_abc("material_balance.envelope"),
        "energy_balance.U-HX.hot",
        "energy_balance.U-HX.cold",
        "energy_balance.U-MIX",
        "energy_balance.U-PHF",
        "energy_balance.U-SPLIT",
        "energy_balance.envelope",
        *_FEED_SPECIFICATION,
        "specification.U-HX.hot_outlet_temperature",
        "specification.U-HX.pressure.hot",
        "specification.U-HX.pressure.cold",
        "specification.U-PHF.duty",
        "specification.U-PHF.temperature",
        "specification.U-PHF.pressure.vapor",
        "specification.U-PHF.pressure.liquid",
        *_abc("specification.U-SPLIT.ratio"),
        "bounds_and_domain.U-HX.heat_flow",
        "bounds_and_domain.U-HX.hot_end",
        "bounds_and_domain.U-HX.cold_end",
        *_split("U-PHF", "S3", "closure"),
        "phase_admissibility.U-HX.hot_inlet",
        "phase_admissibility.U-HX.hot_outlet",
        "phase_admissibility.U-HX.cold_inlet",
        "phase_admissibility.U-HX.cold_outlet",
        "phase_admissibility.U-MIX.inlet.S2",
        "phase_admissibility.U-MIX.inlet.S6",
        "phase_admissibility.U-MIX.outlet",
        "phase_admissibility.U-PHF.inlet",
    ],
}

_GENERIC = (
    "residual.",
    "alias_certificate.",
    "bounds_and_domain.nonnegative.",
    "bounds_and_domain.domain.",
    "derivative_witness.",
)


def _twin_certificate(case: str, *, at_twin: bool = True) -> SolutionCertificate:
    document = case_document(case)
    binding = bind(document)
    twin = reference_state(case)
    result, step = solve_from(binding, twin)
    assert result.outcome == "CONVERGED", result.message
    return verify_revision(
        binding,
        document,
        result,
        state={c: twin[c] for c in binding.spec.variable_ids} if at_twin else None,
        solve_plan=step.solve_plan,
    )


@pytest.fixture(scope="module")
def certificates() -> dict[str, SolutionCertificate]:
    return {case: _twin_certificate(case) for case in SOLVABLE}


def _ratio(check: CheckResult) -> float:
    """`|value| / τ` for a two-sided check, `value / τ` (signed) for a one-sided one."""
    assert check.value is not None and check.tolerance
    if check.id.endswith(ONE_SIDED_SUFFIXES):
        return check.value / check.tolerance
    return abs(check.value) / check.tolerance


def worst_ratios(certificate: SolutionCertificate) -> tuple[tuple[float, str], tuple[float, str]]:
    """The worst two-sided `|value|/τ` and the worst one-sided `value/τ`, over every check with a
    value and a tolerance but the generic nonnegativity and domain checks (their tolerance is a
    bound, not a `τ`). Recorded in `docs/t05-measurements.md` (W12)."""
    judged = [
        check
        for check in certificate.checks
        if check.value is not None
        and check.tolerance
        and not check.id.startswith(("bounds_and_domain.nonnegative.", "bounds_and_domain.domain."))
    ]
    two = max((_ratio(c), c.id) for c in judged if not c.id.endswith(ONE_SIDED_SUFFIXES))
    one = max((_ratio(c), c.id) for c in judged if c.id.endswith(ONE_SIDED_SUFFIXES))
    return two, one


@pytest.mark.parametrize("case", SOLVABLE)
def test_every_check_passes_at_the_twin_state(
    case: str, certificates: dict[str, SolutionCertificate]
) -> None:
    """A21's check half: `VERIFIED` with no limitation, every check `pass` and none
    `near_threshold`, every §12.2 id that applies present, in §4.3's order."""
    certificate = certificates[case]
    assert certificate.verification_status == "VERIFIED", certificate.limitations
    assert not certificate.limitations
    assert not certificate.false_success_detected
    assert [(c.id, c.result) for c in certificate.checks if c.result != "pass"] == []
    assert [c.id for c in certificate.checks if c.near_threshold] == []
    table = [c.id for c in certificate.checks if not c.id.startswith(_GENERIC)]
    assert table == TABLE_IDS[case]
    (two, _), (one, _) = worst_ratios(certificate)
    assert two < 1.0 / 10 and one < 1.0 / 10  # outside the near-threshold band by construction


@pytest.mark.parametrize("case", SOLVABLE)
def test_energy_and_phase_checks_carry_the_qualification(
    case: str, certificates: dict[str, SolutionCertificate]
) -> None:
    """[A09] on every energy, admissibility and independent-split check and on nothing else; ADR
    0011 D2's note on the reactor's energy balance and, with a reactor present, the envelope's."""
    provider = Syn001Provider()
    note = qualification(provider)
    reaction = note + REACTION_DATUM_NOTE.format(
        convention=provider.describe().reference_convention
    )
    reacting = case == "SYN-001-UL-C2"
    for check in certificates[case].checks:
        shares = check.category in ("energy_balance", "phase_admissibility", "independent_split")
        assert (check.independence_qualification is not None) == shares, check.id
        if check.category != "energy_balance" or check.result == "not_applicable":
            continue
        carries = check.id in ("energy_balance.U-RX", "energy_balance.envelope") and reacting
        assert check.independence_qualification == (reaction if carries else note), check.id
    if reacting:
        assert "ADR 0011 D2" in REACTION_DATUM_NOTE and "SYN-001-ref-v1" in reaction


# -- A20's second branch: C3X converged, and its certificate FAILED ---------------------------


@pytest.mark.parametrize("at_twin", [False, True], ids=["solved-state", "twin-state"])
def test_c3x_converged_is_failed_by_the_cold_end_alone(at_twin: bool) -> None:
    """C3X's rows have a solution (spec §11.4) with the exchanger's cold end at `−10 K`. Solved
    from the twin's state, the region converges; the certificate, at the solve's own final state
    and at the twin's, is `FAILED` with exactly one failing check, `+10 K` against `1e-6 K`."""
    certificate = _twin_certificate("SYN-001-UL-C3X", at_twin=at_twin)
    assert certificate.verification_status == "FAILED"
    assert certificate.false_success_detected
    failing = [c for c in certificate.checks if c.result == "fail"]
    assert [c.id for c in failing] == ["bounds_and_domain.U-HX.cold_end"]
    (cold_end,) = failing
    assert cold_end.value is not None and abs(cold_end.value - 10.0) <= 1e-5
    assert [c.id for c in certificate.checks if c.result not in ("pass", "fail")] == []


# -- the table's branches the three cases do not take -----------------------------------------


def _checks(document: dict[str, Any], state: dict[str, float]) -> dict[str, CheckResult]:
    view = parse_revision(document)
    splits = lifted_splits(
        [(i.unit_id, i.model_id, i.wiring) for i in view.instances], view.components
    )
    checks = revision_checks(
        view,
        splits,
        state,
        provider=Syn001Provider(),
        context=CONTEXT,
        tolerances=CheckPolicy().tolerances,
    )
    return {check.id: check for check in checks}


def _without(document: dict[str, Any], specification: str) -> dict[str, Any]:
    changed = copy.deepcopy(document)
    changed["specifications"] = [s for s in changed["specifications"] if s["id"] != specification]
    return changed


def test_a_reactor_at_a_duty_is_checked_on_the_duty() -> None:
    """`specification.U-RX.duty` (`Q − Q_spec`) replaces `.T` when the revision pins the duty."""
    state = reference_state("SYN-001-UL-C2")
    document = _without(case_document("SYN-001-UL-C2"), "SPEC-reactor-outlet-T")
    document["specifications"].append(duty_pin("SPEC-rx-Q", "U-RX", state["U-RX.Q"] + 2.0))
    checks = _checks(document, state)
    assert "specification.U-RX.T" not in checks
    duty = checks["specification.U-RX.duty"]
    assert (duty.value, duty.result) == (-2.0, "fail")
    assert list(checks).index("specification.U-RX.duty") == (
        list(checks).index("specification.U-RX.conversion") + 1
    )


def test_an_exchanger_at_a_duty_is_checked_on_the_duty() -> None:
    state = reference_state("SYN-001-UL-C3")
    document = _without(case_document("SYN-001-UL-C3"), "SPEC-hx-hot-outlet-T")
    document["specifications"].append(duty_pin("SPEC-hx-Q", "U-HX", state["U-HX.Q"] - 0.5))
    checks = _checks(document, state)
    assert "specification.U-HX.hot_outlet_temperature" not in checks
    duty = checks["specification.U-HX.duty"]
    assert (duty.value, duty.result) == (0.5, "fail")


def test_one_sided_checks_are_not_applicable_at_a_dormant_inlet() -> None:
    """§4.3: a one-sided check is `dormant` when any inlet of its unit is dormant — C1's valve
    with its inlet at zero flow; the pump upstream, still flowing, is judged."""
    state = reference_state("SYN-001-UL-C1")
    state.update({f"S3.n.{c}": 0.0 for c in "ABC"})
    checks = _checks(case_document("SYN-001-UL-C1"), state)
    valve = checks["bounds_and_domain.U-VLV.direction"]
    assert (valve.result, valve.reason) == ("not_applicable", "ZERO_FLOW")
    assert checks["bounds_and_domain.U-PUMP.direction"].result == "pass"


def test_a_pressure_rise_across_the_valve_fails_its_direction() -> None:
    """`P_out − P_in ≤ τ`: the valve's outlet pressure raised above its inlet's by 1 Pa."""
    state = reference_state("SYN-001-UL-C1")
    state["S4.P"] = state["S3.P"] + 1.0
    direction = _checks(case_document("SYN-001-UL-C1"), state)["bounds_and_domain.U-VLV.direction"]
    assert (direction.value, direction.result) == (1.0, "fail")
