"""M02 WO-8.4: the verifier's `pr-c1-v1` forms and their wiring (design note §14.2 B15; ADR 0013
Amendment 3; register R-257; gates G2 (i), G7 (j), (k)).

- The fresh provider by the revision's basis, from the verifier's own table.
- G7 (j): every C1 certificate carries the registered check policy and records where its
  fresh-flash categories were judged; on constructed states each PR form fails on its far side
  (`.dew` and a declared vapour port at `l/n = 1e-8`; `.closure` 1e-4 K off a TWO_PHASE root) and
  passes at the root (`|value| ≤ τ_T / 10`).
- G7 (k): the solver's and the verifier's copies of the band rule agree as data.
- G2 (i): `view.components` is SYN-001's at every T07 corpus revision that parses.
- R-016: `verify/pr_c1.py` imports by the table's rule, plus `models.c1.TAU_DEW` alone.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

import pytest
from conftest import REPO_ROOT, load_yaml
from m02_wo8_support import bind, flash_revision, solve
from t07_corpus import CORPUS
from test_m02_wo8_region import FLOWSHEETS
from test_t05_table_independence import violations

from openflowsheet.compiled import EvaluationContext
from openflowsheet.models.c1.phase import classify
from openflowsheet.models.revision_flowsheet import RevisionError, parse_revision
from openflowsheet.orchestrator.region import LiftedSplit
from openflowsheet.orchestrator.revision import instances_of
from openflowsheet.orchestrator.splits import lifted_splits
from openflowsheet.thermo import FlashRequest, StreamState
from openflowsheet.thermo.pr_c1 import COMPONENTS, PrC1Provider
from openflowsheet.thermo.syn001 import Syn001Provider
from openflowsheet.verify import pr_c1
from openflowsheet.verify.certificate import FRESH_PROVIDERS, fresh_provider, verify_revision
from openflowsheet.verify.checks import KIND_TOLERANCE, VerifierError, qualification

CHECK_POLICY_SHA256 = "21c44e105a1b78428047258af3030b8502957aab5d27f0389c2f143bcb3cf390"
FLASH: Mapping[str, Any] = load_yaml(REPO_ROOT / "benchmarks" / "m01" / "reference_values.yaml")[
    "closed_form"
]["flash_states"]
CONTEXT = EvaluationContext(model_version="m02-wo8-verifier", constants_sha256="0" * 64)
PROVIDER = PrC1Provider()
NOTE = qualification(PROVIDER)
TOLERANCES = dict(KIND_TOLERANCE)
F1 = tuple(FLASH["F1"]["n_mol_s"])
F4 = tuple(FLASH["F4"]["n_mol_s"])


def _raised(n: tuple[float, ...], delta: float) -> tuple[float, ...]:
    return (*n[:2], n[2] * (1.0 + delta), *n[3:])


# -- the fresh provider -------------------------------------------------------------------------


def test_the_verifier_builds_its_fresh_provider_from_the_basis() -> None:
    assert FRESH_PROVIDERS == ("syn001", "pr-c1-v1")
    assert isinstance(fresh_provider("syn001"), Syn001Provider)
    assert isinstance(fresh_provider("pr-c1-v1"), PrC1Provider)
    with pytest.raises(VerifierError, match=r"^provider_unknown\(other\)$"):
        fresh_provider("other")


def test_the_verifier_module_does_not_import_the_binders_constructor() -> None:
    source = (REPO_ROOT / "src" / "openflowsheet" / "verify" / "certificate.py").read_text()
    assert "basis_provider(" not in source and "import basis_provider" not in source


# -- R-016: pr_c1.py's imports ------------------------------------------------------------------


def test_pr_c1_imports_by_the_tables_rule_and_tau_dew_alone() -> None:
    """B15: ids, views, thermo types, verify primitives and `models.c1.TAU_DEW`; nothing of the
    solver's (`test_t05_table_independence`'s rule, its one exception named)."""
    source = (REPO_ROOT / "src" / "openflowsheet" / "verify" / "pr_c1.py").read_text()
    found = violations(source)
    assert len(found) == 1 and found[0].endswith("from openflowsheet.models.c1 import TAU_DEW")
    for smuggled in (
        "from openflowsheet.models.c1.phase import classify",
        "from openflowsheet.models.c1.blocks import VapourEnthalpyFlow",
        "from openflowsheet.orchestrator.region import _kernel",
    ):
        extra = violations(source + f"\n\ndef _smuggled() -> None:\n    {smuggled}\n")
        assert len(extra) == 2, smuggled


# -- G7 (k): the two copies of the band rule ----------------------------------------------------


def _cases() -> list[tuple[str, tuple[float, ...], float, float]]:
    cases = [
        (fid, tuple(state["n_mol_s"]), state["T_K"], state["P_Pa"]) for fid, state in FLASH.items()
    ]
    f4 = FLASH["F4"]
    for delta in (8.1e-10, 3.2e-9):
        cases.append((f"F4x(1+{delta:g})", _raised(F4, delta), f4["T_K"], f4["P_Pa"]))
    return cases


@pytest.mark.parametrize(("case", "n", "t", "p"), _cases(), ids=[c[0] for c in _cases()])
def test_g7k_the_solvers_and_the_verifiers_band_agree_as_data(
    case: str, n: tuple[float, ...], t: float, p: float
) -> None:
    regime, value, _ = classify(PROVIDER, CONTEXT, n, t, p)
    assert pr_c1.band(PROVIDER, CONTEXT, n, t, p, COMPONENTS) == (regime, value)


def test_g7k_the_band_cases_straddle_tau_dew() -> None:
    """δ ≈ 8.1e-10 and 3.2e-9 put `l/n_tot` at about 0.5 τ_dew and 2 τ_dew (`≈ 0.0616 δ`)."""
    f4 = FLASH["F4"]
    inside = pr_c1.band(PROVIDER, CONTEXT, _raised(F4, 8.1e-10), f4["T_K"], f4["P_Pa"], COMPONENTS)
    past = pr_c1.band(PROVIDER, CONTEXT, _raised(F4, 3.2e-9), f4["T_K"], f4["P_Pa"], COMPONENTS)
    assert inside[0] == "VAPOR" and 0.3e-10 < inside[1] < 0.7e-10
    assert past[0] == "TWO_PHASE" and 1.5e-10 < past[1] < 2.5e-10


# -- G7 (j): constructed states -----------------------------------------------------------------


def _split() -> LiftedSplit:
    binding = bind(flash_revision(F1, 268.15))
    (split,) = lifted_splits(instances_of(binding.flowsheet), COMPONENTS)
    return split


def _vapour_state(split: LiftedSplit, n: tuple[float, ...], t: float) -> dict[str, float]:
    """A VAPOR branch: the feed as vapour, the liquid `+0.0`."""
    state = dict(zip(split.feed, n, strict=True))
    state.update(zip(split.vapor, n, strict=True))
    state.update(dict.fromkeys(split.liquid, 0.0))
    state[split.vapor_total], state[split.liquid_total] = float(sum(n)), 0.0
    state[split.temperature] = t
    state[split.pressure] = 1.0e7
    return state


def _two_phase_state(split: LiftedSplit, n: tuple[float, ...], t: float) -> dict[str, float]:
    """The provider's TWO_PHASE root of `n` at `t`, written into the split."""
    flashed = PROVIDER.flash(
        FlashRequest(state=StreamState(n=n, temperature=t, pressure=1.0e7)), CONTEXT
    )
    assert flashed.phase_signature == "TWO_PHASE" and flashed.vapor and flashed.liquid
    state = dict(zip(split.feed, n, strict=True))
    state.update(zip(split.vapor, flashed.vapor.n, strict=True))
    state.update(zip(split.liquid, flashed.liquid.n, strict=True))
    state[split.vapor_total] = float(sum(flashed.vapor.n))
    state[split.liquid_total] = float(sum(flashed.liquid.n))
    state[split.temperature] = t
    state[split.pressure] = 1.0e7
    return state


def _admissibility(split: LiftedSplit, state: Mapping[str, float]) -> Any:
    (check,) = [
        c
        for c in pr_c1.split_checks(split, COMPONENTS, state, PROVIDER, CONTEXT, TOLERANCES, NOTE)
        if c.category == "phase_admissibility"
    ]
    return check


def test_g7j_dew_passes_in_the_band_and_fails_at_1e_8() -> None:
    split = _split()
    t = FLASH["F4"]["T_K"]
    at_dew = _admissibility(split, _vapour_state(split, F4, t))
    assert (at_dew.id, at_dew.result, at_dew.value) == ("phase_admissibility.U.S1.dew", "pass", 0.0)
    assert at_dew.tolerance == 1e-10 and at_dew.reference == 1.0
    assert at_dew.independence_qualification == (
        NOTE + "; pr-c1-v1 form (M01 §7; design note §14.2 B15): dew band, liquid NH3 fraction "
        "of a fresh TP flash"
    )
    delta = 1e-8 / 0.06155  # l/n_tot ≈ 0.0616 δ
    far = _admissibility(split, _vapour_state(split, _raised(F4, delta), t))
    assert far.result == "fail" and 0.9e-8 < far.value < 1.1e-8
    assert not far.near_threshold  # 100 τ_dew: past ADR 0007 D2.4's margin


def test_g7j_closure_passes_at_the_root_and_fails_1e_4_k_off_it() -> None:
    split = _split()
    t = FLASH["F1"]["T_K"]
    root = _two_phase_state(split, F1, t)
    at_root = _admissibility(split, root)
    assert at_root.id == "phase_admissibility.U.S1.closure" and at_root.result == "pass"
    assert abs(at_root.value) <= TOLERANCES["temperature"] / 10
    assert at_root.tolerance == TOLERANCES["temperature"] and at_root.reference == 100.0
    assert at_root.independence_qualification.endswith(
        "first-order distance in K from the vapour's NH3 dew point"
    )
    moved = {**root, split.temperature: t + 1e-4}
    off = _admissibility(split, moved)
    assert off.result == "fail" and off.value == pytest.approx(1e-4, rel=1e-2)


def test_g7j_a_liquid_branch_is_unsupported() -> None:
    split = _split()
    state = _vapour_state(split, (0.0, 0.0, 1.0, 0.0, 0.0), 268.15)
    state.update(zip(split.liquid, (0.0, 0.0, 1.0, 0.0, 0.0), strict=True))
    state.update(dict.fromkeys(split.vapor, 0.0))
    state[split.vapor_total], state[split.liquid_total] = 0.0, 1.0
    check = _admissibility(split, state)
    assert (check.id, check.result, check.reason) == (
        "phase_admissibility.U.S1.bubble",
        "unsupported",
        "pr_liquid_regime_unsupported",
    )


def test_g7j_a_declared_vapour_port_fails_at_1e_8_and_a_declared_liquid_is_unsupported() -> None:
    document = flash_revision(_raised(F4, 1e-8 / 0.06155), 268.15)
    view = parse_revision(document)
    t = FLASH["F4"]["T_K"]
    state = {f"S1.n.{c}": v for c, v in zip(COMPONENTS, _raised(F4, 1e-8 / 0.06155), strict=True)}
    state.update({"S1.T": t, "S1.P": 1.0e7})
    ports = {"c1.tp_flash": (("inlet", False),)}
    (check,) = pr_c1.declared_port_checks(view, state, PROVIDER, CONTEXT, NOTE, ports)
    assert check.id == "phase_admissibility.U.inlet"
    assert check.result == "fail" and 0.9e-8 < check.value < 1.1e-8
    liquid = {"c1.tp_flash": (("liquid", False),)}
    state.update(
        {f"S3.n.{c}": v for c, v in zip(COMPONENTS, (0.0, 0.0, 1.0, 0.0, 0.0), strict=True)}
    )
    state.update({"S3.T": t, "S3.P": 1.0e7})
    (unsupported,) = pr_c1.declared_port_checks(view, state, PROVIDER, CONTEXT, NOTE, liquid)
    assert (unsupported.result, unsupported.reason) == (
        "unsupported",
        "pr_declared_liquid_unsupported",
    )


def test_the_enthalpy_reads_a_band_two_phase_stream_as_vapour() -> None:
    """B15 item 2: F4 × (1 + 8.1e-10) flashes TWO_PHASE inside the band; its fresh-flash
    enthalpy is the whole stream's vapour enthalpy, at its own state."""
    from openflowsheet.thermo import PropertyRequest

    n = _raised(F4, 8.1e-10)
    stream = StreamState(n=n, temperature=268.15, pressure=1.0e7)
    h = PROVIDER.evaluate_phase(
        PropertyRequest(state=stream, phase="VAPOR", properties=("h",)), CONTEXT
    ).values["h"]
    assert pr_c1.enthalpy_flow(PROVIDER, stream, CONTEXT, COMPONENTS) == 0.0 + sum(n) * h


def test_the_enthalpy_of_a_two_phase_stream_sums_its_phases() -> None:
    from openflowsheet.thermo import PropertyRequest

    stream = StreamState(n=F1, temperature=268.15, pressure=1.0e7)
    flashed = PROVIDER.flash(FlashRequest(state=stream), CONTEXT)
    assert flashed.vapor and flashed.liquid
    total = 0.0
    for phase, outlet in (("VAPOR", flashed.vapor), ("LIQUID", flashed.liquid)):
        h = PROVIDER.evaluate_phase(
            PropertyRequest(state=outlet, phase=phase, properties=("h",)),  # type: ignore[arg-type]
            CONTEXT,
        ).values["h"]
        total += sum(outlet.n) * h
    assert pr_c1.enthalpy_flow(PROVIDER, stream, CONTEXT, COMPONENTS) == total


# -- G7 (j): the C1 certificates ----------------------------------------------------------------


@pytest.mark.parametrize("name", list(FLOWSHEETS))
def test_g7j_every_c1_certificate_carries_the_registered_policy_and_its_judged_at(
    name: str,
) -> None:
    document = FLOWSHEETS[name]()
    solved = solve(document)
    certificate = verify_revision(
        solved.binding, document, solved.run, solve_plan=solved.plan.steps[-1].solve_plan
    )
    assert certificate.check_policy_sha256 == CHECK_POLICY_SHA256
    assert certificate.transformations["projection"]["judged_at"] in ("projection", "final_state")
    qualified = {q["provider_id"] for q in certificate.independence_qualifications}
    assert qualified == {"pr-c1-v1"}
    ids = [check.id for check in certificate.checks]
    if name != "zero":
        assert "material_balance.U.liquid.H2" in ids
    assert not any("model_unsupported" in check.reason for check in certificate.checks)


# -- G2 (i) ---------------------------------------------------------------------------------------


def test_g2i_view_components_are_syn001s_at_every_t07_corpus_revision() -> None:
    parsed = 0
    for name, build in CORPUS.items():
        try:
            view = parse_revision(build())
        except RevisionError:
            continue  # a legacy-binder revision `parse_revision` refuses; it has no view
        parsed += 1
        assert view.components == ("A", "B", "C"), name
        assert view.basis.provider_id == "syn001", name
    assert (len(CORPUS), parsed) == (50, 38)


def test_the_witness_does_not_difference_exactly_zero_pr_flow_columns() -> None:
    """§14.2 B17 *Consequence* as narrowed by §14.3 C2 (R-281): V1's certificate is VERIFIED with
    its witness run over every column but the exactly-zero stream component flows (`<S>.n.<c>`);
    differencing those leaves the provider's domain. The skip is recorded: both witness checks
    name the count, and one `derivative_witness_partial` limitation lists the columns."""
    from openflowsheet.compile.casadi_backend import compile_problem
    from openflowsheet.models import flow_id
    from openflowsheet.verify.certificate import BoundDeclaration
    from openflowsheet.verify.checks import derivative_witness

    document = FLOWSHEETS["V1"]()
    solved = solve(document)
    assert solved.run.state is not None
    state = solved.run.state
    target = BoundDeclaration(
        solved.binding.spec,
        compile_problem(solved.binding.spec),
        state,
        pressure_domain=PROVIDER.describe().domain["P"],
    )
    view = parse_revision(document)
    zero = frozenset(
        name
        for stream in view.streams
        for c in view.components
        if state[name := flow_id(stream, c)] == 0.0
    )
    assert zero >= {f"S3.n.{c}" for c in COMPONENTS}
    # The scope is the stream component flows: no other column is skipped, flow-kind or not.
    flow_kind = {
        name
        for name in solved.binding.spec.variable_ids
        if solved.binding.spec.variable_kinds.get(name) == "molar_flow" and state[name] == 0.0
    }
    assert zero <= flow_kind
    full = derivative_witness(target, state)
    assert {c.result for c in full} == {"unsupported"}
    witnessed = derivative_witness(target, state, unstenciled=zero)
    note = (
        f"not differenced: {len(zero)} exactly-zero pr-c1-v1 stream-flow columns "
        "(design note §14.3 C2)"
    )
    assert [(c.id, c.result, c.independence_qualification) for c in witnessed] == [
        ("derivative_witness.on_pattern", "pass", note),
        ("derivative_witness.off_pattern", "pass", note),
    ]
    certificate = verify_revision(
        solved.binding, document, solved.run, solve_plan=solved.plan.steps[-1].solve_plan
    )
    assert certificate.verification_status == "VERIFIED"
    assert math.isfinite(certificate.regularity.rcond_1)  # type: ignore[union-attr]
    witness = [c for c in certificate.checks if c.category == "derivative_witness"]
    assert [c.independence_qualification for c in witness] == [note, note]
    partial = [
        item.as_document()
        for item in certificate.limitations
        if item.kind == "derivative_witness_partial"
    ]
    assert partial == [
        {
            "kind": "derivative_witness_partial",
            "columns": sorted(zero),
            "reason": "pr_c1_zero_flow_columns",
        }
    ]


def test_the_witness_skips_nothing_and_records_nothing_without_unstenciled_columns() -> None:
    """§14.3 C2: when nothing is excluded, neither the qualification nor the limitation is
    written; G2 (ii)'s dump holds every T07 corpus certificate byte-identical."""
    from openflowsheet.verify.checks import witness_skipped_columns

    assert witness_skipped_columns(("a", "b"), frozenset()) == []
    assert witness_skipped_columns(("b", "a", "c"), frozenset({"a", "b", "z"})) == ["a", "b"]
