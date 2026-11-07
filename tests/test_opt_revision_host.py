"""OPT WO-2: the revision NLP host (OPT design §4.2; gates G4, G5, G6).

- **G4** — on TH-R1, TH-C1, TH-V1, M1, M1-recycle, J1, C-MW, and a duty-specified SYN-001 PH flash
  held LIQUID (the one case with held columns): the held system is square, its columns partition
  the problem's, the plan's alias rows are not in it, and the compiled residual selected by it at
  the certified state is the converged attempt's final residual **bit for bit** (design §7 F1);
  the host's cached twin reproduces the point's compiled residual and Jacobian bitwise.
- **G5** — the decision map by bind probes, and its refusals.
- **G6** — held-system sensitivities against central differences of certified production
  re-solves (step `1e-4·scale`, E01 A30's `1e-5` relative), forward = adjoint to `1e-10`; and Q4′
  QUALIFIED on a PH-type split held LIQUID, whose margin is the closure's own test (F2).

Every solve here is a production solve on the recorded route from the registered initializer.
"""

from __future__ import annotations

import copy
import json
from collections.abc import Mapping
from functools import cache
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from t05_w12_support import Feed, Outlet, duty_pin, mini_revision, unit_instance

from openflowsheet.application.policies import DEFAULT_POLICY_ID, resolve_policy
from openflowsheet.application.revision_run import (
    Route,
    run_revision_session,
    select_route,
    solve_route,
)
from openflowsheet.compiled import EvaluationContext
from openflowsheet.orchestrator import region as region_module
from openflowsheet.orchestrator.region import _admissible
from openflowsheet.orchestrator.revision import instances_of
from openflowsheet.orchestrator.splits import region_splits
from openflowsheet.studies.nlp import revision_host
from openflowsheet.studies.nlp.host import CertifiedPoint, DecisionRefusedError, NlpHost
from openflowsheet.studies.nlp.revision_host import (
    DecisionBox,
    DecisionMap,
    DecisionRefusal,
    RevisionNlpHost,
    decision_map,
    document_at,
)
from openflowsheet.studies.sensitivity import TAU_REGIME, OutputFunctional, StudyParameter
from openflowsheet.verify.certificate import CheckPolicy

REPO = Path(__file__).resolve().parents[1]
S11 = REPO / "benchmarks" / "s11"
POLICY = resolve_policy(DEFAULT_POLICY_ID, "revision_eo")
assert POLICY is not None


def _ph_flash_document(duty: float = 1000.0) -> dict[str, Any]:
    """Feed (A, B, C liquid, 1 mol/s each, 300 K, 1 bar) → `syn001.ph_flash` (duty `Q`) → two
    sinks: at 1 kW the flash stays LIQUID, a PH-type lifted split with its vapour side held."""
    return mini_revision(
        "opt-phf",
        unit_instance("SYN-001-UL-C1", "U-PHF"),
        [Feed("inlet", "S1", "liquid", (1.0, 1.0, 1.0), 300.0, 1.0e5)],
        [Outlet("vapor", "S2", "vapor"), Outlet("liquid", "S3", "liquid")],
        [duty_pin("SPEC-phf-Q", "U-PHF", duty)],
    )


def _document(case: str) -> dict[str, Any]:
    if case == "PHF":
        return _ph_flash_document()
    folder = "thermal" if case.startswith("TH-") else "flowsheets"
    document: dict[str, Any] = json.loads((S11 / folder / f"{case}.json").read_bytes())
    return document


#: Case → the decision its host is built with (G4 needs one; any `role: fixed` value will do).
G4_CASES: Mapping[str, str] = {
    "TH-R1": "SPEC-H-Q",
    "TH-C1": "SPEC-B-T",
    "TH-V1": "SPEC-S1-T",
    "M1": "SPEC-S-IN1-T",
    "M1-recycle": "SPEC-S-IN1-T",
    "J1": "SPEC-S-IN1-T",
    "C-MW": "SPEC-S-IN1-T",
    "PHF": "SPEC-phf-Q",
}


def _value(document: Mapping[str, Any], specification_id: str) -> float:
    (entry,) = (s for s in document["specifications"] if s["id"] == specification_id)
    return float(entry["value"])


def _box(document: Mapping[str, Any], specification_id: str, unit: str) -> DecisionBox:
    value = _value(document, specification_id)
    spread = 0.01 * abs(value) if value else 1.0
    return DecisionBox(specification_id, value - spread, value + spread, unit)


def _unit(document: Mapping[str, Any], specification_id: str) -> str:
    (entry,) = (s for s in document["specifications"] if s["id"] == specification_id)
    return str(entry["unit"])


def _host(document: Mapping[str, Any], *specifications: str, **kwargs: Any) -> RevisionNlpHost:
    found = decision_map(
        document, [_box(document, name, _unit(document, name)) for name in specifications]
    )
    assert isinstance(found, DecisionMap), found
    return RevisionNlpHost(
        document, found, solve_policy=POLICY, check_policy=CheckPolicy(), **kwargs
    )


@cache
def _certified(case: str) -> tuple[RevisionNlpHost, CertifiedPoint, tuple[float, ...]]:
    """The case's host, its point at the base decision, and the last Newton residual the region
    computed (the converged attempt's final one)."""
    document = _document(case)
    host = _host(document, G4_CASES[case])
    (parameter,) = host.decisions.parameters.values()
    residuals: list[tuple[float, ...]] = []
    original = region_module.solve_newton

    def spy(*args: Any, **kwargs: Any) -> Any:
        result = original(*args, **kwargs)
        residuals.append(tuple(result.residual))
        return result

    region_module.solve_newton = spy  # type: ignore[assignment]
    try:
        point = host.certify({parameter: host.base_spec().parameters[parameter]})
    finally:
        region_module.solve_newton = original  # type: ignore[assignment]
    assert point.verified, (case, point.outcome, point.message)
    return host, point, residuals[-1]


# -- G4: the held system (design §4.2.1, §7 F1) --------------------------------------------------


@pytest.mark.parametrize("case", list(G4_CASES))
def test_g4_the_held_system_is_the_converged_attempt_bitwise(case: str) -> None:
    host, point, final_residual = _certified(case)
    typed: NlpHost = host  # the protocol, checked by mypy
    assert typed.kind == "revision-eo" and not typed.require_every_start
    system = host.held_system(point)
    assert point.spec is not None and point.state is not None
    spec = point.spec
    # Square, disjoint, alias rows excluded (also asserted by `HeldSystem` at construction).
    assert len(system.rows) + len(system.labels) == len(system.free)
    assert set(system.free).isdisjoint(system.held)
    assert set(system.free) | set(system.held) == set(spec.variable_ids)
    assert set(system.rows).isdisjoint(system.eliminated)
    assert system.signature == point.signature
    # The held columns are the certified state's, exactly.
    assert all(
        np.float64(point.state[name]).tobytes() == np.float64(value).tobytes()
        for name, value in system.held.items()
    )
    compiled = host._compiled_at(point)
    context = EvaluationContext(
        model_version=compiled.metadata.model_version,
        constants_sha256=compiled.metadata.constants_sha256,
        phase_signature=None,
    )
    x = np.array([point.state[name] for name in spec.variable_ids], dtype=np.float64)
    evaluation = compiled.residual(x, context)
    assert evaluation.status == "ok" and evaluation.values is not None
    by_id = dict(zip(evaluation.equation_ids, evaluation.values, strict=True))
    at = {name: index for index, name in enumerate(spec.variable_ids)}
    # The converged attempt's own system (C-MW's zero subsystem, §9 A-2, adds its rows back).
    zero = system.zero
    rows = system.rows
    if zero is not None and zero.status == "held":
        attempt = revision_host._handle(point).region.final_system  # type: ignore[union-attr]
        assert attempt is not None
        assert set(attempt.rows) == set(rows) | set(zero.rows)
        rows = tuple(attempt.rows)
    selected = [float(by_id[row]) for row in rows] + [
        float(x[at[outlet]]) - float(x[at[source]]) for _, outlet, source in system.labels
    ]
    assert np.array(selected).tobytes() == np.array(final_residual).tobytes(), case
    # The cached twin (base problem, decision symbolic) is the point's compiled function.
    twin = host.twin(tuple(host.decisions.parameters.values()))
    p0 = {name: point.parameters[name] for name in twin.parameter_ids}
    assert (np.asarray(twin.residual(x, p0)) + 0.0).tobytes() == (
        np.asarray(evaluation.values) + 0.0
    ).tobytes()
    jacobian = compiled.jacobian(x, context)
    twin_jacobian = twin.jacobian_x(x, p0)
    assert list(twin_jacobian.indptr) == list(jacobian.indptr)
    assert list(twin_jacobian.indices) == list(jacobian.indices)
    assert (np.asarray(twin_jacobian.data) + 0.0).tobytes() == (
        np.asarray(jacobian.data) + 0.0
    ).tobytes()


def test_g4_the_ph_flash_holds_its_vapour_side() -> None:
    host, point, _ = _certified("PHF")
    system = host.held_system(point)
    assert point.signature == (("U-PHF", "LIQUID"),)
    assert dict(system.held) == {"S2.n.A": 0.0, "S2.n.B": 0.0, "S2.n.C": 0.0, "S2.N": 0.0}


def test_th_r1_has_an_alias_row_outside_its_held_system() -> None:
    host, point, _ = _certified("TH-R1")
    system = host.held_system(point)
    assert len(system.eliminated) == 1
    # §9 A-2: the flash's two exact-zero saturated flows and their fix rows are held (38 → 36).
    assert system.zero is not None and system.zero.status == "held"
    assert system.zero.columns == ("S5.sat.L", "S6.sat.V")
    assert system.zero.rows == ("D:sat-fix:vapor", "D:sat-fix:liquid")
    assert len(system.rows) == len(system.free) == 36


def test_bounds_follow_the_kinds_of_the_free_columns() -> None:
    host, point, _ = _certified("C-MW")
    bounds = host.bounds(point)
    kinds = host.held_system(point).spec.variable_kinds
    reasons = {kinds[name]: bound.reason for name, bound in bounds.items()}
    assert reasons["temperature"] == reasons["pressure"] == "provider_domain"
    assert reasons["dimensionless"] == "no_declared_bound(dimensionless)"
    flows = [bounds[name] for name in bounds if kinds[name] == "molar_flow"]
    # §9 A-2: C-MW's exact-zero ethanol flows are held, so every free flow is `[0, ∞)`.
    assert {(b.lower, b.upper) for b in flows} == {(0.0, None)}
    _, phf, _ = _certified("PHF")
    held = _certified("PHF")[0].bounds(phf)
    assert not set(held) & {"S2.n.A", "S2.n.B", "S2.n.C", "S2.N"}  # held, not primal


# -- certify: cold, on the recorded route, with the session's bundle ------------------------------


def test_certify_writes_the_bundle_run_revision_session_writes(tmp_path: Path) -> None:
    document = _document("TH-R1")
    host = _host(document, "SPEC-H-Q", sink=lambda _: (tmp_path / "host", "opt-test-s0"))
    point = host.certify({"H.Q_spec": 26000.0})
    assert point.verified and point.bundle_ref == str(tmp_path / "host")
    candidate = host.document_at({"H.Q_spec": 26000.0})
    assert candidate == document_at(document, {"SPEC-H-Q": 26000.0})
    route = select_route(candidate)
    assert isinstance(route, Route)
    run_revision_session(
        route,
        candidate,
        tmp_path / "session",
        run_id="opt-test-s0",
        policy=POLICY,
        check_policy=CheckPolicy(),
        policy_requested=DEFAULT_POLICY_ID,
    )
    written = sorted(
        str(p.relative_to(tmp_path / "host")) for p in (tmp_path / "host").rglob("*") if p.is_file()
    )
    assert written == sorted(
        str(p.relative_to(tmp_path / "session"))
        for p in (tmp_path / "session").rglob("*")
        if p.is_file()
    )
    for name in written:
        if name == "run-manifest.json":
            continue
        assert (tmp_path / "host" / name).read_bytes() == (tmp_path / "session" / name).read_bytes()
    ours = json.loads((tmp_path / "host" / "run-manifest.json").read_bytes())
    theirs = json.loads((tmp_path / "session" / "run-manifest.json").read_bytes())
    # The two stamps, and the integrity hash over the whole manifest that covers them.
    for volatile in ("started_at", "elapsed_seconds", "manifest_sha256"):
        ours.pop(volatile), theirs.pop(volatile)
    assert ours == theirs


def test_certify_refuses_a_parameter_that_is_not_a_decision() -> None:
    host, _, _ = _certified("TH-R1")
    with pytest.raises(DecisionRefusedError):
        host.certify({"P.efficiency": 0.7})


# -- G5: the decision map (design §4.2.2) ---------------------------------------------------------


def _split_fraction_as_specification() -> dict[str, Any]:
    """TH-R1 with the splitter's `split_fraction` supplied by a `parameters.split_fraction`
    specification instead of the instance."""
    document = _document("TH-R1")
    (splitter,) = (i for i in document["instances"] if i["id"] == "SP")
    del splitter["parameters"]["split_fraction"]
    (template,) = (s for s in document["specifications"] if s["id"] == "SPEC-H-Q")
    entry = copy.deepcopy(template)
    entry.update(id="SPEC-SP-r", kind="dimensionless", unit="1", value=0.5)
    entry["target"] = {
        "object_type": "instance",
        "object_id": "SP",
        "path": "parameters.split_fraction",
    }
    entry["tolerance"] = {"absolute": 1e-12, "relative": 1e-10, "scale": 1.0}
    document["specifications"].append(entry)
    return document


def test_g5_decisions_map_to_their_parameters() -> None:
    th_r1 = _document("TH-R1")
    found = decision_map(th_r1, [DecisionBox("SPEC-H-Q", 20000.0, 30000.0, "W")])
    assert isinstance(found, DecisionMap)
    assert found.as_document() == {"SPEC-H-Q": "H.Q_spec"}
    split = _split_fraction_as_specification()
    found = decision_map(split, [DecisionBox("SPEC-SP-r", 0.3, 0.7, "1")])
    assert isinstance(found, DecisionMap)
    assert found.as_document() == {"SPEC-SP-r": "SP.split_fraction"}
    m1 = _document("M1")
    found = decision_map(
        m1,
        [
            DecisionBox("SPEC-S-IN1-T", 330.0, 340.0, "K"),  # the upper end is the base value
            DecisionBox("SPEC-S-IN1-n-A", 0.2, 0.4, "mol/s"),
        ],
    )
    assert isinstance(found, DecisionMap)
    assert found.as_document() == {
        "SPEC-S-IN1-T": "U-FEED1.T_spec",
        "SPEC-S-IN1-n-A": "U-FEED1.n_spec.A",
    }


def _codes(found: DecisionMap | tuple[DecisionRefusal, ...]) -> list[tuple[str, str]]:
    assert isinstance(found, tuple), found
    return [(refusal.code, refusal.specification_id) for refusal in found]


def test_g5_refusals() -> None:
    th_r1 = _document("TH-R1")
    found = decision_map(
        th_r1,
        [
            DecisionBox("SPEC-H-Q", 20.0, 30.0, "kW"),
            DecisionBox("SPEC-NOPE", 0.0, 1.0, "W"),
            DecisionBox("SPEC-V-P", 1.5e5, 2.5e5, "Pa"),
            DecisionBox("SPEC-V-P", 1.5e5, 2.5e5, "Pa"),
        ],
    )
    assert _codes(found) == [
        ("DECISION_UNIT_NOT_INTERNAL", "SPEC-H-Q"),
        ("UNKNOWN_DECISION", "SPEC-NOPE"),
        ("DECISION_NOT_CONTINUOUS", "SPEC-V-P"),
    ]
    assert isinstance(found, tuple)
    assert "already another decision's parameter" in found[2].detail
    # A binder refusal at an end of the box: a split fraction above 1.
    split = _split_fraction_as_specification()
    found = decision_map(split, [DecisionBox("SPEC-SP-r", 0.5, 1.5, "1")])
    assert _codes(found) == [("DECISION_NOT_CONTINUOUS", "SPEC-SP-r")]
    assert isinstance(found, tuple)
    assert "split_fraction" in found[0].detail or "inadmissible" in found[0].detail, found


@pytest.mark.parametrize("change", ["configuration", "two_parameters"])
def test_g5_a_probe_that_moves_more_than_its_parameter_is_refused(
    change: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No v1 specification's value changes the configuration or two parameters, so the probe's
    binding is altered by a test double after the real binder ran."""
    document = _document("TH-R1")
    real = revision_host.bind_route
    base = real("revision_eo", document)
    assert isinstance(base, Route)

    def altered(path: str, edited: Mapping[str, Any], **kwargs: Any) -> Any:
        route = real(path, edited, **kwargs)
        if edited == document or not isinstance(route, Route):
            return route
        binding = route.binding
        if change == "configuration":
            flowsheet = copy.copy(binding.flowsheet)
            object.__setattr__(flowsheet, "configuration_sha256", "0" * 64)
            return Route(route.solve_path, _replace(binding, flowsheet=flowsheet))
        spec = copy.copy(binding.spec)
        parameters = dict(binding.spec.parameters)
        parameters["P.efficiency"] = 0.5
        object.__setattr__(spec, "parameters", parameters)
        return Route(route.solve_path, _replace(binding, spec=spec))

    monkeypatch.setattr(revision_host, "bind_route", altered)
    found = decision_map(document, [DecisionBox("SPEC-H-Q", 20000.0, 30000.0, "W")])
    assert _codes(found) == [("DECISION_NOT_CONTINUOUS", "SPEC-H-Q")]
    assert isinstance(found, tuple)
    expected = "configuration_sha256" if change == "configuration" else "P.efficiency"
    assert expected in found[0].detail


def _replace(binding: Any, **changes: Any) -> Any:
    import dataclasses

    return dataclasses.replace(binding, **changes)


# -- G6: sensitivities on the held system ----------------------------------------------------------


def _central(resolve: Any, base: float, scale: float, outputs: list[str]) -> list[float]:
    step = 1e-4 * scale
    up, down = resolve(base + step), resolve(base - step)
    return [(up[name] - down[name]) / (2.0 * step) for name in outputs]


def _check(result: Any, columns: list[list[float]], outputs: list[str]) -> None:
    assert result.status == "QUALIFIED", result.refusals
    assert result.forward is not None and result.adjoint is not None
    for j, column in enumerate(columns):
        for i, name in enumerate(outputs):
            forward = result.forward.unscaled[i][j]
            adjoint = result.adjoint.unscaled[i][j]
            assert forward is not None and adjoint is not None
            assert abs(forward - column[i]) <= 1e-5 * abs(column[i]), (name, j, forward, column[i])
            assert abs(forward - adjoint) <= 1e-10 * max(abs(forward), abs(adjoint))


def _resolver(host: RevisionNlpHost, parameter: str) -> Any:
    def resolve(value: float) -> Mapping[str, float]:
        point = host.certify({parameter: value})
        assert point.verified and point.state is not None, point.outcome
        return point.state

    return resolve


def test_g6_th_c1_at_e01s_two_pins() -> None:
    document = _document("TH-C1")
    host = _host(document, "SPEC-B-T", "SPEC-P-P")
    pins = {"B.T_spec": 673.15, "P.P_spec": 3.0e6}
    point = host.certify(pins)
    assert point.verified
    outputs = ["S4.T", "S2.T", "S4.sat.V"]
    result = host.sensitivity(
        point,
        [StudyParameter(pin, scale, 0.5 * scale, 1.5 * scale) for pin, scale in pins.items()],
        [OutputFunctional.of_variable(name, 1.0) for name in outputs],
    )
    columns = []
    for pin, scale in pins.items():

        def resolve(value: float, pin: str = pin) -> Mapping[str, float]:
            moved = host.certify({**pins, pin: value})
            assert moved.verified and moved.state is not None
            return moved.state

        columns.append(_central(resolve, pins[pin], scale, outputs))
    _check(result, columns, outputs)


def _resolve_document(document: Mapping[str, Any]) -> Mapping[str, float]:
    route = select_route(document)
    assert isinstance(route, Route)
    result = solve_route(route, document, policy=POLICY, check_policy=CheckPolicy())
    assert result.certificate is not None and result.state is not None
    assert result.certificate.verification_status == "VERIFIED"
    return result.state


def test_g6_m1_feed_temperature_and_reflux_ratio() -> None:
    document = _document("M1")
    host = _host(document, "SPEC-S-IN1-T")
    point = host.certify({"U-FEED1.T_spec": 340.0})
    assert point.verified
    outputs = ["S-D.n.A", "S-B.n.C", "S02.stage.4.T"]
    outputs = [name for name in outputs if name in point.state] or list(point.state)[:3]
    reflux = "S02.stage.1.reflux_ratio*"
    result = host.sensitivity(
        point,
        [
            StudyParameter("U-FEED1.T_spec", 340.0, 300.0, 380.0),
            StudyParameter(reflux, 2.0, 1.0, 3.0),
        ],
        [OutputFunctional.of_variable(name, 1.0) for name in outputs],
    )

    def reflux_at(value: float) -> Mapping[str, float]:
        edited = copy.deepcopy(document)
        (column,) = (i for i in edited["instances"] if i["id"] == "S02")
        column["parameters"]["condenser_reflux_ratio"]["value"] = value
        return _resolve_document(edited)

    columns = [
        _central(_resolver(host, "U-FEED1.T_spec"), 340.0, 340.0, outputs),
        _central(reflux_at, 2.0, 2.0, outputs),
    ]
    _check(result, columns, outputs)


def test_g6_q4_prime_qualifies_a_ph_type_split_held_liquid() -> None:
    host, point, _ = _certified("PHF")
    (split,) = host.regimes(point).splits
    assert (split.unit_id, split.kind, split.regime) == ("U-PHF", "PH", "LIQUID")
    assert split.margin is not None and split.margin >= TAU_REGIME
    # F2: the margin is the closure's own test at the converged state — `_admissible`'s value
    # there is 1 − margin, bit for bit.
    route = host.route
    flowsheet = route.binding.flowsheet
    (lifted,) = region_splits(
        instances_of(flowsheet), flowsheet.units(), flowsheet.components
    ).splits
    compiled = host._compiled_at(point)
    context = EvaluationContext(
        model_version=compiled.metadata.model_version,
        constants_sha256=compiled.metadata.constants_sha256,
        phase_signature=None,
    )
    assert point.state is not None
    ok, value = _admissible(
        flowsheet.provider, context, lifted, "LIQUID", point.state, POLICY.admissibility_epsilon
    )
    assert ok and 1.0 - value == split.margin
    (parameter,) = host.decisions.parameters.values()
    duty = point.parameters[parameter]
    result = host.sensitivity(
        point,
        [StudyParameter(parameter, duty, 0.0, 2.0 * duty)],
        [OutputFunctional.of_variable(name, 1.0) for name in ("S3.T", "S3.n.A")],
    )
    assert result.outcome("Q4").outcome == "pass"
    assert result.outcome("Q4'").outcome == "pass"
    assert result.status == "QUALIFIED", result.refusals
    assert result.forward is not None and result.adjoint is not None
    (expected,) = _central(_resolver(host, parameter), duty, duty, ["S3.T"])
    forward, adjoint = result.forward.unscaled[0][0], result.adjoint.unscaled[0][0]
    assert forward is not None and adjoint is not None
    assert abs(forward - expected) <= 1e-5 * abs(expected), (forward, expected)
    assert abs(forward - adjoint) <= 1e-10 * max(abs(forward), abs(adjoint))
    # Held LIQUID: the liquid outlet carries the feed whatever the duty.
    flow = result.forward.unscaled[1][0]
    assert flow is not None and abs(flow) <= 1e-12


def test_a_provider_whose_closure_tests_otherwise_gets_no_margin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """OPT §9 A-3 (F8; supersedes D-12): `pr-c1-v1`'s closure judges a single-phase branch by
    `classify` and an exactly-zero light-gas fraction, not "value ≤ 1 + ε", so the split has no
    margin, Q4′ refuses it and the start's phase rows name it undefined — shown on the PH flash
    with the provider reported `pr-c1-v1`."""
    host, point, _ = _certified("PHF")
    monkeypatch.setattr(region_module, "_pr_c1", lambda provider: True)
    monkeypatch.setattr(revision_host._handle(point), "phase", None)
    assert host.phase_rows(point).undefined == ("U-PHF",)
    (split,) = host.regimes(point).splits
    assert (split.kind, split.regime, split.margin) == ("PH", "LIQUID", None)
    (parameter,) = host.decisions.parameters.values()
    result = host.sensitivity(
        point,
        [StudyParameter(parameter, 1000.0, 0.0, 2000.0)],
        [OutputFunctional.of_variable("S3.T", 1.0)],
    )
    assert result.status == "REFUSED"
    assert "REGIME_MARGIN_UNSUPPORTED" in result.refusal_codes
