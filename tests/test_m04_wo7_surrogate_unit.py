"""M04 WO-7: the unit `c1.reactor_surrogate` in a flowsheet (spec §3.2–§3.7, §8.1, §8.2, §8.6;
ADR 0037 D1, D2, D5): M04.A12–A15 at the unit level, A13 and A26 on the stand-in loop.

The function-level assertions (the basis, the chain rule, the causal outlet) are
`test_m04_quadratic.py`'s; here the same registered states (`reference_values.json` →
`jacobian_states`) go through the binder, the compiler, the unit's causal evaluation and the
certificate. The fixture manifests are the A19 manifest (`tests/fixtures/schemas/
surrogate_manifest/valid/a19_smooth_prefix.json`, the smooth parent's prefix study) with its
coefficients replaced where an assertion names other ones (A12's fixture coefficients, A15's
constant predictors): TEST INPUTS, which the manifest checker accepts because it reads no records.
"""

from __future__ import annotations

import copy
import json
import math
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np
import pytest
import scipy.sparse as sp
from conftest import REPO_ROOT, load_json
from m02_c1_support import (
    DIMENSIONLESS,
    connection,
    feed_specifications,
    instance,
    revision,
)
from m02_wo8_support import POLICY
from test_schemas_p01 import validator_for

from openflowsheet.application import revision_binding as rb
from openflowsheet.application.binding import Unbound
from openflowsheet.application.revision_binding import RevisionBinding, bind_revision_flowsheet
from openflowsheet.canonical import document_sha256
from openflowsheet.compile.casadi_backend import compile_problem
from openflowsheet.compiled import EvaluationContext
from openflowsheet.models.c1 import ELEMENT_MATRIX, NU
from openflowsheet.models.revision_flowsheet import parse_revision
from openflowsheet.orchestrator.execution import declaration_identity
from openflowsheet.orchestrator.executor import PlanResult, execute_plan
from openflowsheet.orchestrator.revision import plan_revision
from openflowsheet.studies.surrogate import plan as spl
from openflowsheet.studies.surrogate import reactor as sr
from openflowsheet.thermo import StreamState
from openflowsheet.thermo.pr_c1 import COMPONENTS, PrC1Provider
from openflowsheet.verify import CheckResult, Limitation
from openflowsheet.verify.certificate import SolutionCertificate, verify_revision
from openflowsheet.verify.surrogate import surrogate_items

REFERENCE: Mapping[str, Any] = load_json(REPO_ROOT / "benchmarks" / "m04" / "reference_values.json")
STATES: Mapping[str, Mapping[str, Any]] = {s["id"]: s for s in REFERENCE["jacobian_states"]}
A19: Mapping[str, Any] = load_json(
    REPO_ROOT
    / "tests"
    / "fixtures"
    / "schemas"
    / "surrogate_manifest"
    / "valid"
    / "a19_smooth_prefix.json"
)
LOOP_PATH: Path = REPO_ROOT / "benchmarks" / "m02" / "c1-loop-standin.json"
#: `pipeline.smooth_prefix.band`: (q̂ w_X, q̂ w_ΔT) of the A19 surrogate (M04.A26).
BAND = REFERENCE["pipeline"]["smooth_prefix"]["band"]
UNIT = "R"


def with_coefficients(x: Sequence[float], dt: Sequence[float]) -> dict[str, Any]:
    """The A19 manifest with its predictor's coefficients replaced (a TEST INPUT)."""
    manifest = copy.deepcopy(dict(A19))
    manifest["predictor"]["coefficients"] = {"X": list(x), "dT_K": list(dt)}
    return manifest


def constant(x: float = 0.0, dt: float = 0.0) -> dict[str, Any]:
    """Spec M04.A15's fixture manifests: constant predictors, every other coefficient 0."""
    return with_coefficients([x] + [0.0] * 35, [dt] + [0.0] * 35)


FIXTURE = with_coefficients(
    REFERENCE["fixture_coefficients"]["X"], REFERENCE["fixture_coefficients"]["dT"]
)


def resolver(*manifests: Mapping[str, Any]) -> Callable[[str], Mapping[str, Any] | None]:
    """An in-memory artifact store of SurrogateManifests, by canonical SHA-256."""
    return {document_sha256(m): m for m in manifests}.get


def _n_tubes(value: float) -> dict[str, Any]:
    return {
        "value": value,
        "unit": "1",
        "dimension": list(DIMENSIONLESS),
        "kind": "dimensionless",
        "meaning": "test",
        "role": "fixed",
    }


def surrogate_instance(
    manifest: Mapping[str, Any],
    n_tubes: float = 1.0,
    *,
    unit: str = UNIT,
    version: str | None = None,
    artifact_ref: str | None = None,
) -> dict[str, Any]:
    return instance(
        unit,
        sr.MODEL_ID,
        {"n_tubes": _n_tubes(n_tubes)},
        version=manifest["surrogate_id"] if version is None else version,
        artifact_ref=document_sha256(manifest) if artifact_ref is None else artifact_ref,
    )


def reactor_revision(inlet: StreamState, reactor: Mapping[str, Any]) -> dict[str, Any]:
    """F → R → K: a feed fully specified at `inlet` into the surrogate, its outlet a sink."""
    return revision(
        [instance("F", "c1.feed_source"), dict(reactor), instance("K", "c1.product_sink")],
        [
            connection("S1", ("F", "outlet"), (UNIT, "inlet")),
            connection("S2", (UNIT, "outlet"), ("K", "inlet")),
        ],
        feed_specifications("S1", inlet.n, inlet.temperature, inlet.pressure),
    )


def bound(
    inlet: StreamState, manifest: Mapping[str, Any], n_tubes: float = 1.0
) -> tuple[dict[str, Any], RevisionBinding]:
    document = reactor_revision(inlet, surrogate_instance(manifest, n_tubes))
    binding = bind_revision_flowsheet(document, surrogates=resolver(manifest))
    assert isinstance(binding, RevisionBinding), binding
    return document, binding


def inlet_of(state: Mapping[str, Any]) -> StreamState:
    inlet = state["inlet"]
    return StreamState(n=tuple(inlet["n"]), temperature=inlet["T"], pressure=inlet["P"])


def unit_of(binding: RevisionBinding) -> sr.C1ReactorSurrogate:
    (found,) = (u for u in binding.flowsheet.instances if u.unit_id == UNIT)
    assert isinstance(found, sr.C1ReactorSurrogate)
    return found


def at_registered_outlet(state: Mapping[str, Any], duty: float = 0.0) -> dict[str, float]:
    """The flowsheet state with S2 the registered causal outlet (ξ, T_out) of `state`."""
    inlet = inlet_of(state)
    xi = float(state["outlet"]["xi"])
    values: dict[str, float] = {}
    for c, n, nu in zip(COMPONENTS, inlet.n, NU, strict=True):
        values[f"S1.n.{c}"] = n
        values[f"S2.n.{c}"] = n + nu * xi if nu else n
    values.update(
        {
            "S1.T": inlet.temperature,
            "S1.P": inlet.pressure,
            "S2.T": float(state["outlet"]["T_out"]),
            "S2.P": inlet.pressure,
            f"{UNIT}.xi": xi,
            f"{UNIT}.Q": duty,
        }
    )
    return values


def _context(compiled: Any) -> EvaluationContext:
    return EvaluationContext(
        model_version=compiled.metadata.model_version,
        constants_sha256=compiled.metadata.constants_sha256,
    )


def _vector(binding: RevisionBinding, values: Mapping[str, float]) -> np.ndarray:
    return np.array([values[name] for name in binding.spec.variable_ids], dtype=np.float64)


def residual_rows(binding: RevisionBinding, values: Mapping[str, float]) -> dict[str, float]:
    compiled = compile_problem(binding.spec)
    result = compiled.residual(_vector(binding, values), _context(compiled))
    assert result.status == "ok" and result.values is not None, result.message
    return dict(zip(result.equation_ids, result.values, strict=True))


def jacobian_rows(
    binding: RevisionBinding, values: Mapping[str, float], rows: Sequence[str]
) -> dict[str, dict[str, float]]:
    compiled = compile_problem(binding.spec)
    result = compiled.jacobian(_vector(binding, values), _context(compiled))
    assert result.status == "ok", result.message
    matrix = sp.csc_matrix(
        (result.data, result.indices, result.indptr),
        shape=(len(result.row_ids), len(result.col_ids)),
    ).toarray()
    index = {row: k for k, row in enumerate(result.row_ids)}
    return {
        row: {column: float(matrix[index[row], j]) for j, column in enumerate(result.col_ids)}
        for row in rows
    }


def evaluated(binding: RevisionBinding, inlet: StreamState) -> Any:
    unit = unit_of(binding)
    return unit.evaluate({"inlet": (inlet,)}, unit.context)


# == the unit, its manifest and its binding ======================================================


def test_the_manifest_is_explicit_reduced_with_analytic_derivatives_and_q0_to_q7() -> None:
    """Spec §8.1: `explicit_reduced`, `cheap`, M02's ports and accumulation declarations, both
    derivatives `analytic`, the parent's hard domain, and the limitations Q0 (synthetic) to Q7."""
    _, binding = bound(inlet_of(STATES["J1"]), A19)
    unit = unit_of(binding)
    manifest = unit.manifest()
    assert [e.message for e in validator_for("model_manifest").iter_errors(manifest)] == []
    assert manifest["id"] == "c1.reactor_surrogate" and manifest["introduced_by_package"] == "M04"
    requirements = manifest["execution_requirements"]
    assert requirements["execution_class"] == "explicit_reduced"
    assert requirements["evaluation_cost_class"] == "cheap"
    assert [(d["output"], d["with_respect_to"], d["method"]) for d in manifest["derivatives"]] == [
        ("residuals", ["free_variables"], "analytic"),
        ("outlet.state", ["inlet.state"], "analytic"),
    ]
    assert manifest["derivatives"][1]["notes"] == (
        "derivative of the surrogate; agreement with the parent is the gradient metric of its "
        "manifest"
    )
    assert manifest["validity"]["limitations"] == A19["qualifications"]
    assert len(A19["qualifications"]) == 8 and A19["qualifications"][0].startswith("SYNTHETIC")
    assert manifest["validity"]["domain"]["temperature_K"] == {"min": 573.15, "max": 773.15}
    from openflowsheet.models.c1 import reactor as embedded  # noqa: PLC0415

    assert unit.ports() == embedded.PORTS
    assert [(e.equation_id, e.accumulation) for e in unit.declared_equations()] == [
        (e.equation_id, e.accumulation) for e in embedded.EQUATIONS
    ]
    assert unit.surrogate_id == "m04q7-m04-synthetic-smooth-v1-it1-prefix"
    assert unit.manifest_sha256 == document_sha256(A19)


def test_the_rows_are_m02s_with_the_extent_and_rise_the_surrogates() -> None:
    _, binding = bound(inlet_of(STATES["J1"]), A19)
    rows = [e for e in binding.spec.equation_ids if e.startswith(f"{UNIT}:")]
    assert rows == [
        *(f"R:C1RX-mole:{c}" for c in COMPONENTS),
        "R:C1RX-extent",
        "R:C1RX-temperature",
        "R:C1RX-pressure",
        "R:C1RX-duty",
    ]
    # Only the stoichiometry is a pinned input: the coefficients and N_tubes are the block's
    # compile-time constants, carried by the configuration digest (build log, WO-7).
    assert [p for p in binding.spec.parameter_ids if p.startswith(f"{UNIT}.")] == [
        f"R.nu.{c}" for c in COMPONENTS
    ]
    assert binding.surrogate_manifests == {UNIT: A19}


def test_the_manifest_and_n_tubes_enter_the_identity() -> None:
    """ADR 0002 D2.7: the same ids with another manifest or another N_tubes are another
    `model_version` (the label carries the configuration digest); the constants are unchanged."""
    inlet = inlet_of(STATES["J1"])
    _, a = bound(inlet, A19)
    _, b = bound(inlet, FIXTURE)
    _, c = bound(inlet, A19, n_tubes=2.0)
    identities = [declaration_identity(x.spec) for x in (a, b, c)]
    assert a.spec.equation_ids == b.spec.equation_ids == c.spec.equation_ids
    assert len({version for version, _ in identities}) == 3
    assert len({constants for _, constants in identities}) == 1


@pytest.mark.parametrize(
    ("make", "why"),
    [
        (lambda m: (None, {}), "no resolver"),
        (lambda m: (resolver(), {}), "an unknown hash"),
        (lambda m: (lambda sha: m, {"artifact_ref": "0" * 64}), "a document of another hash"),
        (lambda m: (resolver(m), {"version": "m04q7-other"}), "another surrogate id"),
    ],
)
def test_an_unresolved_manifest_is_refused(make: Callable[..., Any], why: str) -> None:
    """Spec §8.2: an unknown id, a mismatched hash or no store is `revision_unsupported`,
    `surrogate_manifest_mismatch(<instance>)`."""
    surrogates, overrides = make(A19)
    document = reactor_revision(inlet_of(STATES["J1"]), surrogate_instance(A19, **overrides))
    refused = bind_revision_flowsheet(document, surrogates=surrogates)
    assert isinstance(refused, Unbound), why
    assert (refused.kind, refused.detail) == ("unsupported", "surrogate_manifest_mismatch(R)")


def test_a_manifest_its_checker_refuses_is_refused() -> None:
    """Spec §8.2 / M04.A24: q̂ not the k-th smallest stored score."""
    broken = copy.deepcopy(dict(A19))
    broken["calibration"]["q_hat"] = 0.5
    document = reactor_revision(inlet_of(STATES["J1"]), surrogate_instance(broken))
    refused = bind_revision_flowsheet(document, surrogates=resolver(broken))
    assert isinstance(refused, Unbound)
    assert (refused.kind, refused.detail) == ("unsupported", "surrogate_manifest_mismatch(R)")


def test_the_registered_builder_without_a_manifest_refuses() -> None:
    from openflowsheet.models.revision_flowsheet import RevisionError  # noqa: PLC0415

    document = reactor_revision(inlet_of(STATES["J1"]), surrogate_instance(A19))
    view = parse_revision(document)
    (reactor,) = (i for i in view.instances if i.unit_id == UNIT)
    with pytest.raises(RevisionError, match=r"surrogate_manifest_mismatch\(R\)"):
        rb._c1_reactor_surrogate(reactor, PrC1Provider(), rb._CONTEXT, COMPONENTS)


# -- W27 Amendment 3 §22.4 (R-302): the C1 corpus's surrogate revision ----------------------------

#: The registered C1 corpus revision with a `c1.reactor_surrogate` instance (`m02_c1_corpus`).
CORPUS_PATH: Path = REPO_ROOT / "benchmarks" / "m04" / "c1-surrogate.json"


def corpus_revision() -> dict[str, Any]:
    """F → R → K with R the A19 surrogate at the manifest's own configuration: one tube (its
    parent's requests are per tube, spec §5.1) and the inlet at the centre of its input box."""
    centre = [coordinate["centre"] for coordinate in A19["input_map"]["coordinates"]]
    return reactor_revision(spl.request_of(centre), surrogate_instance(A19, 1.0))


def test_the_corpus_revision_is_its_builder_and_binds_through_the_corpus_resolver() -> None:
    from m02_c1_corpus import C1_CORPUS, surrogates  # noqa: PLC0415

    document = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
    own = {key: document[key] for key in ("revision_id", "title", "description", "provenance")}
    assert {**corpus_revision(), **own} == document
    assert C1_CORPUS[document["revision_id"]]() == document
    binding = bind_revision_flowsheet(document, surrogates=surrogates)
    assert isinstance(binding, RevisionBinding), binding
    assert unit_of(binding).manifest_sha256 == document_sha256(A19)
    refused = bind_revision_flowsheet(document)
    assert isinstance(refused, Unbound)
    assert (refused.kind, refused.detail) == ("unsupported", "surrogate_manifest_mismatch(R)")


def test_a_nonpositive_n_tubes_is_outside_the_models_domain() -> None:
    document = reactor_revision(inlet_of(STATES["J1"]), surrogate_instance(A19, 0.0))
    refused = bind_revision_flowsheet(document, surrogates=resolver(A19))
    assert isinstance(refused, Unbound)
    assert refused.kind == "inadmissible" and refused.implicated == (UNIT,)


# == M04.A12 ======================================================================================


@pytest.mark.parametrize("state_id", ["J1", "J2", "J3"])
def test_a12_the_compiled_rows_and_jacobian_at_the_registered_states(state_id: str) -> None:
    """The 14 inlet entries of R_ξ and R_T equal `jacobian_states` within 1e-10 relative per
    entry; the ξ and T_out columns are exactly (1, 0) and (0, 1); the rows vanish at the
    registered causal outlet within 1e-15 relative to (n_tot, T)."""
    state = STATES[state_id]
    inlet = inlet_of(state)
    _, binding = bound(inlet, FIXTURE, n_tubes=float(state["n_tubes"]))
    values = at_registered_outlet(state)
    rows = jacobian_rows(binding, values, ("R:C1RX-extent", "R:C1RX-temperature"))
    columns = [*(f"S1.n.{c}" for c in COMPONENTS), "S1.T", "S1.P"]
    worst = 0.0
    for r, row in enumerate(("R:C1RX-extent", "R:C1RX-temperature")):
        for c, column in enumerate(columns):
            expected = float(state["jacobian"][r][c])
            worst = max(worst, abs(rows[row][column] - expected) / abs(expected))
        # Every other column of the row is structurally zero but ξ (R_ξ) and T_out (R_T).
        others = {k: v for k, v in rows[row].items() if k not in columns and v != 0.0}
        assert others == ({"R.xi": 1.0} if r == 0 else {"S2.T": 1.0}), others
    assert worst <= 1e-10, worst
    residual = residual_rows(binding, values)
    assert abs(residual["R:C1RX-extent"]) <= 1e-15 * sum(inlet.n)
    assert abs(residual["R:C1RX-temperature"]) <= 1e-15 * inlet.temperature


def test_a12_the_block_is_the_function_its_jacobian_differentiates() -> None:
    """Central differences of the compiled residual (relative step 1e-6) against the compiled
    Jacobian at J2, where every z_k is distinct: agreement to the difference's truncation."""
    state = STATES["J2"]
    _, binding = bound(inlet_of(state), FIXTURE, n_tubes=float(state["n_tubes"]))
    values = at_registered_outlet(state)
    rows = ("R:C1RX-extent", "R:C1RX-temperature")
    analytic = jacobian_rows(binding, values, rows)
    for column in [*(f"S1.n.{c}" for c in COMPONENTS), "S1.T", "S1.P"]:
        step = 1e-6 * abs(values[column])
        moved = [dict(values, **{column: values[column] + s * step}) for s in (1.0, -1.0)]
        plus, minus = (residual_rows(binding, m) for m in moved)
        for row in rows:
            difference = (plus[row] - minus[row]) / (2.0 * step)
            assert abs(difference - analytic[row][column]) <= 1e-6 * abs(analytic[row][column])


# == M04.A13 ======================================================================================


def assert_conserved(n_in: Sequence[float], n_out: Sequence[float]) -> float:
    """|E(n_out − n_in)| ≤ 1e-14 n_tot,in per element; inerts bitwise equal. The worst ratio."""
    n_tot = sum(n_in)
    worst = 0.0
    for element in ELEMENT_MATRIX:
        change = math.fsum(e * (o - i) for e, o, i in zip(element, n_out, n_in, strict=True))
        worst = max(worst, abs(change) / n_tot)
    assert worst <= 1e-14, worst
    for k, nu in enumerate(NU):
        if nu == 0:
            assert n_out[k].hex() == n_in[k].hex()
    return worst


@pytest.mark.parametrize("state_id", ["J1", "J2", "J3"])
def test_a13_the_causal_evaluation_conserves_elements(state_id: str) -> None:
    state = STATES[state_id]
    inlet = inlet_of(state)
    _, binding = bound(inlet, FIXTURE, n_tubes=float(state["n_tubes"]))
    result = evaluated(binding, inlet)
    assert result.status == "ok", result.message
    outlet = result.outlets["outlet"]
    assert_conserved(inlet.n, outlet.n)
    assert abs(result.extent - float(state["outlet"]["xi"])) <= 1e-13 * abs(result.extent)
    assert abs(outlet.temperature - float(state["outlet"]["T_out"])) <= 1e-13 * 800.0
    assert outlet.pressure == inlet.pressure


# == M04.A14 ======================================================================================


def items_at(
    document: Mapping[str, Any], binding: RevisionBinding, values: Mapping[str, float]
) -> tuple[list[CheckResult], list[Limitation]]:
    return surrogate_items(parse_revision(document), values, binding.surrogate_manifests)


@pytest.mark.parametrize("state_id", ["J1", "J2"])
def test_a14_inside_the_box_the_check_passes_with_no_excess(state_id: str) -> None:
    state = STATES[state_id]
    document, binding = bound(inlet_of(state), FIXTURE, n_tubes=float(state["n_tubes"]))
    checks, limitations = items_at(document, binding, at_registered_outlet(state))
    (check,) = checks
    assert (check.id, check.category, check.result, check.value) == (
        "SURROGATE-DOMAIN:R",
        "bounds_and_domain",
        "pass",
        0.0,
    )
    assert check.tolerance is None
    assert [item.kind for item in limitations] == ["surrogate_model"]
    assert state["domain"]["status"] == "within_reference_domain"


def test_a14_j3_is_outside_the_reference_domain_in_t_only() -> None:
    state = STATES["J3"]
    document, binding = bound(inlet_of(state), FIXTURE, n_tubes=float(state["n_tubes"]))
    checks, limitations = items_at(document, binding, at_registered_outlet(state))
    (check,) = checks
    assert check.result == "pass" and check.value is not None
    assert abs(check.value - 0.5) <= 1e-12
    assert [item.kind for item in limitations] == [
        "surrogate_model",
        "surrogate_outside_reference_domain",
    ]
    outside = limitations[1].detail
    assert outside["unit"] == UNIT and outside["coordinates"] == ["T"]
    assert abs(outside["scaled_excess"] - 0.5) <= 1e-12
    # The unit evaluates there: J3 is inside the parent's hard domain.
    assert evaluated(binding, inlet_of(state)).status == "ok"


def test_a14_j4_is_refused_outside_the_hard_domain_in_t() -> None:
    """J1 with T_in = 780 K: refused at the causal evaluation and at the certificate's check."""
    state = STATES["J1"]
    j4 = StreamState(n=inlet_of(state).n, temperature=780.0, pressure=inlet_of(state).pressure)
    document, binding = bound(j4, FIXTURE)
    result = evaluated(binding, j4)
    assert (result.status, result.message) == (
        "out_of_domain",
        "surrogate_outside_hard_domain(R:T)",
    )
    values = at_registered_outlet(state)
    values["S1.T"] = 780.0
    values["S2.T"] = 780.0 + float(state["outlet"]["dT"])
    (check,), _ = items_at(document, binding, values)
    assert (check.result, check.reason) == ("fail", "surrogate_outside_hard_domain(R:T)")


def test_a14_j5_an_inlet_without_n2_has_no_input() -> None:
    state = STATES["J1"]
    n = inlet_of(state).n
    j5 = StreamState(n=(n[0], 0.0, *n[2:]), temperature=673.15, pressure=1.0e7)
    document, binding = bound(j5, FIXTURE)
    result = evaluated(binding, j5)
    assert (result.status, result.message) == ("out_of_domain", "surrogate_input_undefined(R)")
    values = at_registered_outlet(state)
    values["S1.n.N2"] = 0.0
    compiled = compile_problem(binding.spec)
    residual = compiled.residual(_vector(binding, values), _context(compiled))
    assert residual.status == "invalid_trial_state"
    assert "surrogate_input_undefined(R)" in residual.message
    (check,), _ = items_at(document, binding, values)
    assert (check.result, check.reason) == ("fail", "surrogate_input_undefined(R)")


def test_a14_j6_a_dormant_inlet_gives_zero_extent_and_t_out_t_in_exactly() -> None:
    state = STATES["J1"]
    j6 = StreamState(n=(0.0,) * 5, temperature=673.15, pressure=1.0e7)
    document, binding = bound(j6, FIXTURE)
    result = evaluated(binding, j6)
    assert result.status == "ok" and result.phase_signature == "ZERO_FLOW"
    outlet = result.outlets["outlet"]
    assert result.extent == 0.0 and result.duty == 0.0
    assert outlet.n == (0.0,) * 5 and outlet.temperature == j6.temperature
    values = {
        **{f"S{s}.n.{c}": 0.0 for s in (1, 2) for c in COMPONENTS},
        "S1.T": 673.15,
        "S2.T": 673.15,
        "S1.P": 1.0e7,
        "S2.P": 1.0e7,
        "R.xi": 0.0,
        "R.Q": 0.0,
    }
    rows = residual_rows(binding, values)
    assert rows["R:C1RX-extent"] == 0.0 and rows["R:C1RX-temperature"] == 0.0
    (check,), limitations = items_at(document, binding, values)
    assert (check.result, check.scope, check.reason) == (
        "not_applicable",
        "not_applicable",
        "ZERO_FLOW",
    )
    assert [item.kind for item in limitations] == ["surrogate_model"]
    del state


# == M04.A15 ======================================================================================


@pytest.mark.parametrize(
    ("beta_x", "beta_t", "h2_over_n2", "expected"),
    [
        (-0.01, 0.0, None, "surrogate_output_inadmissible(R:X)"),
        (0.96, 0.0, None, "surrogate_output_inadmissible(R:X)"),
        # H2/N2 = 1.2 is inside the hard domain; r/3 = 0.4 < 0.5 < 0.95: the H2 bound.
        (0.5, 0.0, 1.2, "surrogate_output_inadmissible(R:X)"),
        (0.5, 0.0, None, None),
        (0.0, 260.0, None, "surrogate_output_inadmissible(R:dT)"),
    ],
)
def test_a15_admissibility_at_the_causal_evaluation_and_the_check(
    beta_x: float, beta_t: float, h2_over_n2: float | None, expected: str | None
) -> None:
    inlet = inlet_of(STATES["J1"])
    if h2_over_n2 is not None:
        inlet = StreamState(
            n=(h2_over_n2 * inlet.n[1], *inlet.n[1:]),
            temperature=inlet.temperature,
            pressure=inlet.pressure,
        )
    manifest = constant(beta_x, beta_t)
    document, binding = bound(inlet, manifest)
    result = evaluated(binding, inlet)
    if expected is None:
        assert result.status == "ok", result.message
    else:
        assert (result.status, result.message) == ("out_of_domain", expected)
    # The certificate's check judges the state's own outputs X = ξ/n_N2, ΔT = T_out − T_in.
    xi = beta_x * inlet.n[1]
    values = {
        **{f"S1.n.{c}": n for c, n in zip(COMPONENTS, inlet.n, strict=True)},
        **{f"S2.n.{c}": n + nu * xi for c, n, nu in zip(COMPONENTS, inlet.n, NU, strict=True)},
        "S1.T": inlet.temperature,
        "S2.T": inlet.temperature + beta_t,
        "S1.P": inlet.pressure,
        "S2.P": inlet.pressure,
        "R.xi": xi,
        "R.Q": 0.0,
    }
    (check,), _ = items_at(document, binding, values)
    assert (check.result, check.reason) == (
        ("pass", "") if expected is None else ("fail", expected)
    )


# == M04.A26 and A13 on the stand-in loop ==========================================================


def surrogate_loop() -> tuple[dict[str, Any], RevisionBinding]:
    """M02's registered stand-in loop with its reactor bound to the A19 surrogate."""
    document: dict[str, Any] = json.loads(LOOP_PATH.read_text(encoding="utf-8"))
    (reactor,) = (i for i in document["instances"] if i["id"] == "reactor")
    reactor["model"] = {
        "id": sr.MODEL_ID,
        "version": A19["surrogate_id"],
        "artifact_ref": document_sha256(A19),
    }
    binding = bind_revision_flowsheet(document, surrogates=resolver(A19))
    assert isinstance(binding, RevisionBinding), binding
    return document, binding


def solved_loop() -> tuple[dict[str, Any], RevisionBinding, PlanResult, SolutionCertificate]:
    document, binding = surrogate_loop()
    plan, _ = plan_revision(binding, POLICY)
    run = execute_plan(plan=plan, flowsheet=binding.flowsheet, spec=binding.spec, policy=POLICY)
    assert run.outcome == "CONVERGED", run.message
    certificate = verify_revision(binding, document, run, solve_plan=plan.steps[-1].solve_plan)
    return document, binding, run, certificate


def test_a26_the_surrogate_loop_solves_and_carries_the_band_and_q0_to_q7() -> None:
    """M04.A26 (spec §8.6) at the revision level: the loop solves on the revision's own rows (no
    experiment runner exists on this path) and certifies; the certificate carries
    `SURROGATE-DOMAIN:reactor` and the `surrogate_model` limitation with the band within 1e-10
    relative of `pipeline.smooth_prefix.band` and the manifest's Q0–Q7."""
    _, _, run, certificate = solved_loop()
    assert certificate.verification_status == "VERIFIED", certificate.limitations
    (check,) = (c for c in certificate.checks if c.id.startswith("SURROGATE-DOMAIN"))
    assert (check.id, check.category, check.result) == (
        "SURROGATE-DOMAIN:reactor",
        "bounds_and_domain",
        "pass",
    )
    # Category-major order: after the table's last bounds row, before any admissibility row.
    categories = [c.category for c in certificate.checks]
    at = certificate.checks.index(check)
    assert "bounds_and_domain" not in categories[at + 1 :]
    (model,) = (item for item in certificate.limitations if item.kind == "surrogate_model")
    detail = model.detail
    assert detail["unit"] == "reactor"
    assert detail["surrogate_id"] == A19["surrogate_id"]
    assert detail["manifest_sha256"] == document_sha256(A19)
    assert abs(detail["band"]["X"] / float(BAND["X"]) - 1.0) <= 1e-10
    assert abs(detail["band"]["dT_K"] / float(BAND["dT"]) - 1.0) <= 1e-10
    assert detail["qualifications"] == A19["qualifications"]
    assert len(detail["qualifications"]) == 8
    assert detail["coverage"] == {
        "nominal": 0.95,
        "finite_sample": 38 / 40,
        "lower_bound": A19["evaluation"]["lower_bound"],
        "minimum": 0.9,
        "test_draws": 60,
    }
    # The loop's reactor inlet lies outside the reference box (H2/N2 3.0 at the box's edge and
    # a per-tube flow above it): flagged, with no coverage claim, never refused.
    (outside,) = (
        item
        for item in certificate.limitations
        if item.kind == "surrogate_outside_reference_domain"
    )
    assert check.value == outside.detail["scaled_excess"] > 0.0
    assert run.state is not None


def test_a26_a13_the_rows_hold_and_elements_are_conserved_at_the_solution() -> None:
    _, binding, run, certificate = solved_loop()
    state = run.state
    assert state is not None
    n_in = tuple(state[f"S3.n.{c}"] for c in COMPONENTS)
    n_out = tuple(state[f"S4.n.{c}"] for c in COMPONENTS)
    assert_conserved(n_in, n_out)
    rows = {c.subject: c for c in certificate.checks if c.category == "residual"}
    for row in ("reactor:C1RX-extent", "reactor:C1RX-temperature"):
        assert rows[row].result == "pass", rows[row]
    # The solution is the surrogate's at the converged inlet, to the solve's tolerance.
    unit = next(u for u in binding.flowsheet.instances if u.unit_id == "reactor")
    assert isinstance(unit, sr.C1ReactorSurrogate)
    inlet = StreamState(n=n_in, temperature=state["S3.T"], pressure=state["S3.P"])
    u = spl.coordinates(inlet, 1000.0)
    assert u is not None
    x, dt = unit.surrogate.predict(spl.scaled(u))
    assert abs(state["reactor.xi"] - x * n_in[1]) <= 1e-9 * sum(n_in)
    assert abs(state["S4.T"] - state["S3.T"] - dt) <= 1e-6
