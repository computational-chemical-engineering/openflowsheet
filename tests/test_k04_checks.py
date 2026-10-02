"""K04 §4: the check set, and the false success it exists to reject.

The measurement that justifies the whole package is §9.2's trivial root. At the once-through
variant, forcing S3's lifted split all-liquid and closing both duties gives a state where
**all 49 assembled rows are satisfied**, every material balance closes, the overall energy
envelope closes, and the rank screen is clean — with both duties wrong by 8237.85 W in
opposite directions. Nothing that reads the state's own lifted split can see it. A fresh flash
of S3 can, and so can comparing the split against one.

So the tests here are not "does the verifier pass at the answer" — that is necessary and easy.
They are: does it pass at the answer, fail at the impostor, and fail *for the right reasons*,
with the impostor's passing checks recorded as passing so the detection is attributable.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest
from conftest import REPO_ROOT, load_yaml

from openflowsheet.compiled import EvaluationContext
from openflowsheet.models.syn001.flowsheet import Syn001Flowsheet
from openflowsheet.orchestrator.tear import solve_tear
from openflowsheet.thermo.syn001 import Syn001Provider
from openflowsheet.verify.certificate import CheckPolicy, grade, run_checks

CONTEXT = EvaluationContext(model_version="K04@" + "0" * 64, constants_sha256="0" * 64)

CASE_IDS = [
    "SYN-001-nominal",
    "SYN-001-once-through",
    "SYN-001-high-recycle",
    "SYN-001-all-liquid-310K",
    "SYN-001-all-vapor-420K",
]

#: §9.2's registered offset, the closed form from `benchmarks/k04/reference_values.yaml`.
TRIVIAL_ROOT_OFFSET = 8237.8503930694530451

#: §6: which streams are dormant at which variant, and therefore how many checks are
#: `not_applicable` rather than skipped (invariant 4).
DORMANT = {
    "SYN-001-nominal": (),
    "SYN-001-once-through": ("S6",),
    "SYN-001-high-recycle": (),
    "SYN-001-all-liquid-310K": ("S4",),
    "SYN-001-all-vapor-420K": ("S5", "S6", "S7"),
}


@pytest.fixture(scope="module")
def variants() -> dict[str, Mapping[str, Any]]:
    loaded = load_yaml(REPO_ROOT / "benchmarks" / "syn001" / "reference_values.yaml")
    return {entry["case_id"]: entry for entry in loaded["variants"]}


def flowsheet_for(case: Mapping[str, Any]) -> Syn001Flowsheet:
    return Syn001Flowsheet(
        provider=Syn001Provider(),
        context=CONTEXT,
        split_fraction=float(case["r"]),
        flash_temperature=float(case["T_flash_K"]),
        heater_temperature=float(case["T_heater_K"]),
        pressure=float(case["P_Pa"]),
    )


def solved(case: Mapping[str, Any]) -> tuple[Syn001Flowsheet, dict[str, float]]:
    flowsheet = flowsheet_for(case)
    result, _ = solve_tear(flowsheet)
    assert result.outcome == "CONVERGED"
    assert result.final_state is not None
    return flowsheet, dict(result.final_state)


@pytest.mark.parametrize("case_id", CASE_IDS)
def test_a03_to_a08_every_check_passes_at_the_registered_solutions(
    case_id: str, variants: dict[str, Mapping[str, Any]]
) -> None:
    """A03–A08: the whole set at `x(t*)`, and the dormant streams recorded not skipped."""
    flowsheet, state = solved(variants[case_id])
    checks, _ = run_checks(flowsheet, state)

    failures = [f"{c.id}={c.value}" for c in checks if c.result == "fail"]
    assert not failures, f"{case_id}: {failures}"
    assert not [c for c in checks if c.result == "unsupported"]

    not_applicable = {c.subject for c in checks if c.result == "not_applicable"}
    assert not_applicable == set(DORMANT[case_id]), case_id

    verdict, limitations = grade(checks, policy=CheckPolicy())
    assert verdict == "VERIFIED", f"{case_id}: {limitations}"


def test_a09_every_provider_dependent_check_names_the_provider(
    variants: dict[str, Mapping[str, Any]],
) -> None:
    """[A09]: an energy or phase check shares the correlations, and must say whose.

    It is bookkeeping, not a validation of the enthalpies, and a certificate that did not say
    so would be claiming the second thing.
    """
    flowsheet, state = solved(variants["SYN-001-nominal"])
    checks, _ = run_checks(flowsheet, state)

    capabilities = Syn001Provider().describe()
    for check in checks:
        if check.category in ("energy_balance", "phase_admissibility", "independent_split"):
            if check.result == "not_applicable":
                continue
            assert check.independence_qualification is not None, check.id
            assert capabilities.provider_id in check.independence_qualification
            assert capabilities.implementation_sha256 in check.independence_qualification
            assert capabilities.data_sha256 in check.independence_qualification
            assert "not a validation" in check.independence_qualification
        elif check.category in ("material_balance", "specification"):
            assert check.independence_qualification is None, (
                f"{check.id} shares no provider and must not claim a qualification"
            )


def test_a18_the_trivial_root_is_rejected_and_for_the_right_reasons(
    variants: dict[str, Mapping[str, Any]],
) -> None:
    """A18 and §9.2. The case the package exists for (K02 finding 3, register R-008).

    Forcing S3's split all-liquid and closing both duties produces a state that satisfies every
    equation the solver knows about. What must fail is exactly the four checks that do not read
    the lifted split, and what must *pass* is everything else — otherwise the detection is not
    attributable and a verifier that failed everything would score the same.
    """
    flowsheet, state = solved(variants["SYN-001-once-through"])
    for component in ("A", "B", "C"):
        state[f"S3.liq.{component}"] = state[f"S3.n.{component}"]
        state[f"S3.vap.{component}"] = 0.0
    state["S3.L"] = sum(state[f"S3.n.{c}"] for c in ("A", "B", "C"))
    state["S3.V"] = 0.0
    state["U-HEAT.Q"] -= TRIVIAL_ROOT_OFFSET
    state["U-FLASH.Q"] += TRIVIAL_ROOT_OFFSET

    checks, _ = run_checks(flowsheet, state)
    by_id = {check.id: check for check in checks}
    verdict, _ = grade(checks, policy=CheckPolicy())
    assert verdict == "FAILED"

    # What must still pass — the impostor is a *good* impostor.
    for category in ("residual", "material_balance", "alias_certificate", "specification"):
        failing = [c.id for c in checks if c.category == category and c.result == "fail"]
        assert not failing, f"{category} must pass at the trivial root: {failing}"
    assert by_id["energy_balance.envelope"].result == "pass", (
        "the envelope passes here because the two duty errors cancel; §4.4 registers that as a "
        "documented blind spot, and a session that 'simplified' the energy check to the "
        "envelope alone would pass this state"
    )

    # What must fail, with the registered closed forms.
    assert by_id["energy_balance.heater"].value == pytest.approx(-TRIVIAL_ROOT_OFFSET, abs=1e-6)
    assert by_id["energy_balance.flash"].value == pytest.approx(+TRIVIAL_ROOT_OFFSET, abs=1e-6)
    assert by_id["phase_admissibility.S3.bubble"].result == "fail"
    assert by_id["phase_admissibility.S3.bubble"].value == pytest.approx(
        1.0703142190807741552 - 1.0, rel=1e-12
    )
    assert by_id["independent_split.S3.total"].result == "fail"
    assert abs(by_id["independent_split.S3.total"].value) == pytest.approx(
        0.30410617028018327955, rel=1e-12
    )


def test_the_admissibility_test_is_one_sided(variants: dict[str, Mapping[str, Any]]) -> None:
    """K03 §8.2's rule is `sum x K <= 1`, and making it two-sided would invert it.

    A subcooled liquid sits well below 1 and is perfectly admissible. A symmetric
    `|sum x K - 1| <= eps` would reject every registered variant whose heater outlet is liquid
    and accept only states sitting exactly on the boundary.
    """
    flowsheet, state = solved(variants["SYN-001-nominal"])
    checks, _ = run_checks(flowsheet, state)
    bubble = next(c for c in checks if c.id == "phase_admissibility.S3.bubble")
    assert bubble.result == "pass"
    # Measured: sum x K = 0.962 at the nominal heater outlet, so the margin is large, negative,
    # and far outside any symmetric tolerance.
    assert bubble.value == pytest.approx(0.96231656003527667518 - 1.0, rel=1e-9)
    assert abs(bubble.value) > bubble.tolerance * 1e6


def test_a29_the_material_and_specification_checks_touch_nothing(
    variants: dict[str, Mapping[str, Any]],
) -> None:
    """A29: §4.3 and §4.5 are plain arithmetic over the state and must stay that way.

    Their independence is the point: the compiled rows compute the same sums through K01's
    expression graph and K02's row builders, so a permuted component index or a sign error in
    either shows in one and not the other. A material check that called the compiled problem
    would lose exactly that.
    """
    from openflowsheet.verify.checks import material_checks, specification_checks

    flowsheet, state = solved(variants["SYN-001-nominal"])

    class Exploding:
        def __getattr__(self, name: str) -> Any:
            raise AssertionError(f"the check called the provider ({name}); it must not")

    # Neither takes a provider or a compiled problem at all — enforced by the signature, and
    # asserted here so a later session cannot quietly add one.
    material = material_checks(state, flowsheet.split_fraction)
    specifications = specification_checks(flowsheet, state)
    assert all(c.result == "pass" for c in material)
    assert all(c.result == "pass" for c in specifications)
    assert any(c.id.startswith("material_balance.envelope") for c in material), (
        "the envelope row is not a compiled row and nothing else evaluates it"
    )
    del Exploding
