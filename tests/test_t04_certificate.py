"""T04 W12: K04 on the bound declaration (T04 §4.8; ADR 0010 D9; register R-035).

A30 (the five registered certificate states `VERIFIED` through the bound verifier), A31 (the
identity guard's refusals, before any check), A32 (the promoted specification judged against the
revision, both ways), A33 (F9's evidence), and the certificate clauses of A03, A04 and A08.
Expectations are `benchmarks/t04/reference_values.yaml`'s `bound_declaration_certificate` (the
design lane's twin) and the revision documents; tolerances are T04 §12's.

K04-F9 (ADR 0013; spec `docs/derivations/K04-F9-spec.md` §10.1–§10.2) amends A30 (the certificate
records `transformations.projection`), A32's 5e-4 W half (X06: its two energy balances are judged
at the verifier's projection, where the flash duty is back on its specification) and A33 (X05: the
verdict is `VERIFIED` and promised; F9's raw values stay registered through the unprojected check
functions at `x_final`), and adds X23 (`run_checks` is never projected) and X24 (determinism).

The states are the plan runs' own: HOM-01, HOM-02 and HOM-05's recovery region solve at λ = 1
(`test_t04_edge3.full_run`), and T02's `SYN-001-A02-360`, `-365` and `-355` solved by the region
Newton from their registered 358 K guess.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import yaml
from k04f9_support import PROJECTED, PROJECTED_BOUND, refused, s3_ratios
from test_t04_edge3 import case_document, full_run, plan_run, region_step

import openflowsheet.orchestrator.tear as tear_module
import openflowsheet.verify.certificate as certificate_module
from openflowsheet.application.binding import Binding, bind_revision
from openflowsheet.orchestrator.trace import SolvePolicy
from openflowsheet.verify.certificate import (
    SolutionCertificate,
    alias_document,
    verify,
    verify_bound,
)
from openflowsheet.verify.checks import VerifierError, admissibility_checks, energy_checks

REPO_ROOT = Path(__file__).resolve().parents[1]
CASES = REPO_ROOT / "benchmarks" / "syn001" / "cases"
REF: dict[str, Any] = yaml.safe_load(
    (REPO_ROOT / "benchmarks" / "t04" / "reference_values.yaml").read_text()
)
BOUND = REF["bound_declaration_certificate"]
HOM = ("HOM-01", "HOM-02", "HOM-05")
T02 = ("SYN-001-A02-360", "SYN-001-A02-365")
STATES = (*HOM, *T02)
NORMS = 1e-6
ALIASES = {"U-FLASH:FLASH-P:inlet", "U-SPLIT:SPLIT-P:recycle"}
DECLARATION = {
    "removed_specification_rows": ["U-HEAT:HEAT-T"],
    "freed": {"U-HEAT:HEAT-T": "S3.T"},
    "promoted": {"SPEC:SPEC-flash-duty": "U-FLASH.Q"},
}


@dataclass
class Solved:
    """A converged A02 region solve with everything its certificate is judged against."""

    name: str
    document: dict[str, Any]
    binding: Binding
    result: Any
    solve_plan: Any
    failed: Any = None


_SOLVED: dict[str, Solved] = {}


def solved(name: str) -> Solved:
    if name not in _SOLVED:
        if name in HOM:
            document = case_document(name)
            run = full_run(name)
        else:
            document = yaml.safe_load((CASES / f"{name}.yaml").read_text())
            run = plan_run(
                document, SolvePolicy(policy_id="T04-W12", residual_tolerances={}, scales={})
            )
        step = region_step(run.result)
        assert step.outcome == "CONVERGED"
        (planned,) = [s for s in run.plan.steps if s.kind == "solve_eo"]
        binding = bind_revision(document)
        assert isinstance(binding, Binding)
        _SOLVED[name] = Solved(
            name, document, binding, step.detail, planned.solve_plan, step.recovered_from
        )
    return _SOLVED[name]


_CERTIFICATES: dict[str, SolutionCertificate] = {}


def certificate(name: str) -> SolutionCertificate:
    if name not in _CERTIFICATES:
        item = solved(name)
        _CERTIFICATES[name] = verify_bound(
            item.binding, item.document, item.result, solve_plan=item.solve_plan
        )
    return _CERTIFICATES[name]


def by_id(document: SolutionCertificate) -> dict[str, Any]:
    return {check.id: check for check in document.checks}


# ------------------------------------------------------------------ A30 and A03, A04, A08


@pytest.mark.parametrize("name", STATES)
def test_a30_the_registered_states_are_verified_on_the_bound_declaration(name: str) -> None:
    """T04 §4.8 at HOM-01 (A04), HOM-02, HOM-05 (A08) and T02's A02-360/-365: `VERIFIED`, no
    false success, and no `fail`, `unsupported` or `near_threshold` anywhere — every thresholded
    value is outside ADR 0007 D2.4's band, which is what makes the verdict promisable."""
    issued = certificate(name)
    assert BOUND["certificate_states"][name]["verdict_promised"] is True
    assert (issued.verification_status, issued.false_success_detected) == ("VERIFIED", False)
    assert [c.id for c in issued.checks if c.result in ("fail", "unsupported")] == []
    assert [c.id for c in issued.checks if c.near_threshold] == []
    assert not [limit for limit in issued.limitations if limit.kind != "near_threshold"]


@pytest.mark.parametrize("name", STATES)
def test_a30_the_checks_are_the_bound_declarations(name: str) -> None:
    """The residual rows are the declaration's 49 (`SPEC:SPEC-flash-duty` in, `U-HEAT:HEAT-T`
    out); the aliases exactly the two pressure certificates with `m_e = 0`, equal to the region
    plan's; the specification list K04 §4.5's with `S3.T` `not_applicable(freed(...))` and
    `U-FLASH.Q` added, every evaluated one `pass`."""
    issued = certificate(name)
    item = solved(name)
    residuals = {c.subject for c in issued.checks if c.category == "residual"}
    assert residuals == set(item.binding.spec.equation_ids) and len(residuals) == 49
    assert "SPEC:SPEC-flash-duty" in residuals and "U-HEAT:HEAT-T" not in residuals
    assert by_id(issued)["residual.SPEC:SPEC-flash-duty"].tolerance == pytest.approx(1.01e-3)

    eliminated = issued.transformations["eliminated_rows"]
    assert {row["row_id"] for row in eliminated} == ALIASES
    assert all(row["constant_mismatch"] == 0.0 for row in eliminated)
    recorded = [
        {**row, "equals": sorted(row["equals"])} for row in eliminated
    ]  # the same signed terms; K03 lists them in path order, the plan by id
    assert recorded == [alias_document(row) for row in item.solve_plan.eliminated_rows]
    aliases = {c.subject for c in issued.checks if c.category == "alias_certificate"}
    assert aliases == ALIASES

    specifications = {c.id: c for c in issued.checks if c.category == "specification"}
    evaluated = {"S1.T", "S1.P", "S1.n.A", "S1.n.B", "S1.n.C", "S4.T", "S5.T", "U-FLASH.Q"}
    assert set(specifications) == {f"specification.{c}" for c in (*evaluated, "S3.T")}
    for column in evaluated:
        assert specifications[f"specification.{column}"].result == "pass"
    freed = specifications["specification.S3.T"]
    assert (freed.result, freed.scope) == ("not_applicable", "not_applicable")
    assert freed.reason == "freed(GUESS-heater-outlet-T)"
    assert (freed.value, freed.tolerance, freed.reference) == (None, None, None)
    q_spec = next(
        e["value"] for e in item.document["specifications"] if e["id"] == "SPEC-flash-duty"
    )
    assert specifications["specification.U-FLASH.Q"].value == pytest.approx(
        item.result.state["U-FLASH.Q"] - q_spec, abs=0.0
    )


@pytest.mark.parametrize("name", STATES)
def test_a30_regularity_witness_and_records(name: str) -> None:
    """Regularity on the declaration's 47 × 47 target, `NO_RANK_LOSS_DETECTED`; the witness of the
    compiled 49-row function ≤ 1e-7 on and off the pattern, path `assembled_schur`;
    `transformations` with an empty tear and §4.8 item 4's declaration; the revision's identity
    (the failed solve's too, for HOM-*); the solve's own provenance and fingerprint."""
    issued = certificate(name)
    item = solved(name)
    regularity = issued.regularity
    assert regularity.status == "NO_RANK_LOSS_DETECTED" and regularity.dimension == 47
    witness = by_id(issued)
    for side in ("on_pattern", "off_pattern"):
        check = witness[f"derivative_witness.{side}"]
        assert check.result == "pass" and check.value is not None and check.value <= 1e-7
    assert issued.derivative_provenance["path"] == "assembled_schur"
    assert issued.transformations["tear"] == {"variable_ids": [], "row_ids": []}
    assert issued.transformations["declaration"] == DECLARATION
    # K04-F9 §5.5 (X01): where the fresh-flash categories were judged, R0 and float-free.
    assert set(issued.transformations) == {
        "scales",
        "eliminated_rows",
        "tear",
        "declaration",
        "projection",
    }
    assert issued.transformations["projection"] == PROJECTED

    from openflowsheet.compile.casadi_backend import compile_problem

    metadata = compile_problem(item.binding.spec).metadata
    assert (issued.model_version, issued.constants_sha256) == (
        metadata.model_version,
        metadata.constants_sha256,
    )
    if item.failed is not None:
        failed = item.failed.contexts[0].evaluation_context
        assert (failed.model_version, failed.constants_sha256) == (
            issued.model_version,
            issued.constants_sha256,
        )
    assert issued.root_fingerprint == item.result.root_fingerprint
    assert issued.branch_provenance == tuple(dict(i) for i in item.result.branch_provenance)
    if name == "HOM-01":
        assert [i["core"] for i in issued.branch_provenance] == ["newton", "newton", "homotopy"]


@pytest.mark.parametrize("name", ["HOM-01", "HOM-05", "SYN-001-A02-365"])
def test_a30_the_target_norms_are_the_twins(name: str) -> None:
    """`one_norm`, `inverse_one_norm_estimate` and `rcond_1` equal `ref`'s 40-digit values to
    1e-6 relative; the nominal declaration at the same state differs by ≥ 20% in `rcond_1`, so the
    comparison tells the two declarations apart."""
    regularity = certificate(name).regularity
    registered = BOUND["target_regularity"][name]
    for field, reference in (
        ("one_norm", "one_norm"),
        ("inverse_one_norm_estimate", "inverse_one_norm"),
        ("rcond_1", "rcond_1"),
    ):
        value, target = getattr(regularity, field), float(registered[reference])
        assert abs(value - target) <= NORMS * target, (field, value, target)
    nominal = float(registered["nominal_declaration_rcond_1_same_state"])
    assert abs(regularity.rcond_1 - nominal) >= 0.2 * regularity.rcond_1


# ------------------------------------------------------------------ A31: the refusals


class _CountingCompiled:
    def __init__(self, inner: Any, calls: list[str]) -> None:
        self._inner, self._calls = inner, calls
        self.metadata = inner.metadata

    def residual(self, x: Any, context: Any) -> Any:
        self._calls.append("residual")
        return self._inner.residual(x, context)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)


def spied_compile(patch: pytest.MonkeyPatch) -> list[str]:
    """Every problem the verifier compiles — its own and the nominal tear problem's — counts its
    residual calls."""
    calls: list[str] = []
    original = certificate_module.compile_problem

    def compile_and_count(spec: Any) -> Any:
        return _CountingCompiled(original(spec), calls)

    patch.setattr(certificate_module, "compile_problem", compile_and_count)
    patch.setattr(tear_module, "compile_problem", compile_and_count)
    return calls


@pytest.mark.parametrize("name", ["HOM-01", "SYN-001-A02-360"])
def test_a31_i_the_nominal_verifier_refuses_a_bound_solve_before_any_check(name: str) -> None:
    """A bound solve handed to the nominal entry point is `declaration_mismatch(model_version)`:
    no certificate object and no residual call by the verifier."""
    item = solved(name)
    with pytest.MonkeyPatch.context() as patch:
        calls = spied_compile(patch)
        with pytest.raises(VerifierError, match=r"^declaration_mismatch\(model_version\)$"):
            verify(item.binding.flowsheet, item.result)
    assert calls == []


def test_a31_ii_another_revisions_solve_is_a_constants_mismatch() -> None:
    """A02-360's declaration handed A02-365's result: the same `model_version`, another `Q_spec`."""
    declared, other = solved("SYN-001-A02-360"), solved("SYN-001-A02-365")
    with pytest.MonkeyPatch.context() as patch:
        calls = spied_compile(patch)
        with pytest.raises(VerifierError, match=r"^declaration_mismatch\(constants_sha256\)$"):
            verify_bound(declared.binding, declared.document, other.result)
    assert calls == []


def test_a31_iii_a_state_that_is_not_the_fingerprinted_one_is_refused() -> None:
    """A constructed result whose `state` no longer hashes to its fingerprint: refused without
    `state=`; with it (K04 §9's injection path) the hash comparison is skipped."""
    item = solved("SYN-001-A02-360")
    moved = dict(item.result.state)
    moved["S3.T"] += 1e-9
    constructed = replace(item.result, state=moved)
    with pytest.raises(VerifierError, match=r"^state_mismatch\(full_state_sha256\)$"):
        verify_bound(item.binding, item.document, constructed)
    injected = verify_bound(item.binding, item.document, item.result, state=moved)
    assert injected.verification_status in ("VERIFIED", "FAILED", "UNVERIFIED", "RELAXED")


def test_a31_iv_a_converged_result_without_identity_is_refused() -> None:
    """(iv), as amended: refused with or without a caller-supplied `solve_plan` (review S1)."""
    item = solved("SYN-001-A02-360")
    anonymous = SimpleNamespace(outcome="CONVERGED", state=dict(item.result.state))
    for plan in (None, item.solve_plan):
        with pytest.raises(VerifierError, match=r"^declaration_unidentified$"):
            verify_bound(item.binding, item.document, anonymous, solve_plan=plan)
    with pytest.raises(VerifierError, match=r"^declaration_unidentified$"):
        verify(item.binding.flowsheet, anonymous)


def test_a31_vi_the_revision_document_must_be_the_bindings() -> None:
    """(vi), added with review S2: A02-360's binding with A02-365's revision document and A02-360's
    own result is `declaration_mismatch(revision)`, before any check (no residual call); the same
    binding with its own document is `VERIFIED`."""
    a360, a365 = solved("SYN-001-A02-360"), solved("SYN-001-A02-365")
    with pytest.MonkeyPatch.context() as patch:
        calls = spied_compile(patch)
        with pytest.raises(VerifierError, match=r"^declaration_mismatch\(revision\)$"):
            verify_bound(a360.binding, a365.document, a360.result, solve_plan=a360.solve_plan)
    assert calls == []
    assert certificate("SYN-001-A02-360").verification_status == "VERIFIED"


# ------------------------------------------------------------------ A32: both ways


#: The three checks that read the flash duty at `x_final`, and the two fresh-flash balances.
AT_FINAL_STATE = {
    "residual.SPEC:SPEC-flash-duty",
    "residual.U-FLASH:FLASH-duty",
    "specification.U-FLASH.Q",
}
BALANCES = {"energy_balance.flash", "energy_balance.envelope"}
FIVE = AT_FINAL_STATE | BALANCES


@pytest.mark.parametrize(
    ("delta", "status", "failing", "near", "projection"),
    [
        (2e-3, "FAILED", FIVE, FIVE, refused("residual_not_passed")),
        (-2e-3, "FAILED", FIVE, FIVE, refused("residual_not_passed")),
        (5e-4, "VERIFIED", set(), AT_FINAL_STATE, PROJECTED),
    ],
)
def test_a32_the_promoted_specification_is_judged_against_the_revision(
    delta: float, status: str, failing: set[str], near: set[str], projection: dict[str, Any]
) -> None:
    """At A02-365's root (`Q_spec = −26 111.610 060 239 280 W`) with `U-FLASH.Q + δ` injected:
    ±2e-3 W fails exactly the five checks that read the flash duty, each by ±δ (1e-7 W), judged
    at `x_final` (two rows fail: K04-F9 precondition 1). 5e-4 W is `VERIFIED` (X06, amended): the
    two rows and the specification at `x_final` are flagged near their threshold and read δ; the
    flash and envelope balances, judged at the projection — where the duty is back on its
    specification — are ≤ 1e-3 τ_E and carry no flag (K04-F9 §10.1)."""
    item = solved("SYN-001-A02-365")
    q_spec = next(
        e["value"] for e in item.document["specifications"] if e["id"] == "SPEC-flash-duty"
    )
    assert q_spec == pytest.approx(-26111.610060239280, abs=1e-6)
    state = dict(item.result.state)
    state["U-FLASH.Q"] += delta
    issued = verify_bound(item.binding, item.document, item.result, state=state)
    assert issued.verification_status == status
    assert issued.false_success_detected is (status == "FAILED")
    assert {c.id for c in issued.checks if c.result == "fail"} == failing
    assert {c.id for c in issued.checks if c.near_threshold} == near
    assert issued.transformations["projection"] == projection
    checks = by_id(issued)
    for name in FIVE if status == "FAILED" else AT_FINAL_STATE:
        assert abs(checks[name].value - delta) <= 1e-7, (name, checks[name].value)
    if status == "VERIFIED":
        for name in BALANCES:
            check = checks[name]
            assert check.result == "pass" and not check.near_threshold
            assert abs(check.value) <= PROJECTED_BOUND * check.tolerance, (name, check.value)
            print(f"X06 {name} at the projection: {check.value!r} W")


# ------------------------------------------------------------------ A33: F9's evidence


def test_a33_f9s_evidence_is_recorded_and_the_verdict_is_promised() -> None:
    """T02's `SYN-001-A02-355` from 358 K (one `TWO_PHASE` attempt, 3 iterations; worst row
    `U-HEAT:HEAT-equilibrium:A` at 0.0813 τ, under D2.4's tenth).

    K04-F9 X05 (A33 as amended, §10.2): the certificate is `VERIFIED` with no `near_threshold`
    flag anywhere — the verdict is promised — and its fresh-flash categories are judged at the
    projection, where every S3 value is ≤ 1e-3 of its tolerance. F9's evidence stays registered
    through K04 §4.4 and §4.7's check functions evaluated at `x_final`, unprojected: the
    independent split of S3 and the heater and flash balances are `ref.bound.finding_F9`'s to 1e-5
    relative, each `near_threshold` there. (T04's own file still says `verdict_promised: false`;
    it is not re-emitted, and K04-F9's reference registers the new expectation.)"""
    registered = BOUND["finding_F9"]
    item = solved_355()
    (attempt,) = item.result.attempts
    assert attempt.iterations == 3
    assert dict(attempt.signature) == {"U-HEAT": "TWO_PHASE", "U-FLASH": "TWO_PHASE"}
    issued = verify_bound(item.binding, item.document, item.result, solve_plan=item.solve_plan)
    assert (issued.verification_status, issued.false_success_detected) == ("VERIFIED", False)
    assert [c.id for c in issued.checks if c.near_threshold] == []
    assert issued.transformations["projection"] == PROJECTED
    projected = s3_ratios(issued.checks)
    assert projected and max(projected.values()) <= PROJECTED_BOUND, projected
    print(f"X05 largest S3 value over its threshold at the projection: {max(projected.values())!r}")
    residuals = [c for c in issued.checks if c.category == "residual"]
    worst = max(residuals, key=lambda c: abs(c.value) / c.tolerance)
    assert worst.subject == registered["worst_row"]
    assert abs(
        abs(worst.value) / worst.tolerance - float(registered["worst_row_over_tolerance"])
    ) <= (1e-5 * float(registered["worst_row_over_tolerance"]))

    raw = by_id_list(_unprojected(item))
    for name, key, sign in (
        ("independent_split.S3.total", "independent_split_S3_total_mol_per_s", 1.0),
        ("energy_balance.heater", "energy_heater_W", 1.0),
        ("energy_balance.flash", "energy_heater_W", -1.0),
    ):
        target = sign * float(registered[key])
        assert abs(raw[name].value - target) <= 1e-5 * abs(target), (name, raw[name].value)
        assert raw[name].near_threshold is True


def _unprojected(item: Solved) -> list[Any]:
    """K04 §4.4 and §4.7 at `x_final` on a bound solve, as the certificate evaluated them before
    ADR 0013: the unprojected check functions, a fresh provider, the declaration's context."""
    from openflowsheet.compile.casadi_backend import compile_problem
    from openflowsheet.compiled import EvaluationContext
    from openflowsheet.thermo.syn001 import Syn001Provider

    metadata = compile_problem(item.binding.spec).metadata
    context = EvaluationContext(
        model_version=metadata.model_version,
        constants_sha256=metadata.constants_sha256,
        phase_signature=None,
    )
    provider = Syn001Provider()
    state = item.result.state
    return energy_checks(provider, state, context) + admissibility_checks(provider, state, context)


def by_id_list(checks: list[Any]) -> dict[str, Any]:
    return {check.id: check for check in checks}


# ------------------------------------------------------------------ K04-F9 X23, X24


def test_x23_run_checks_is_never_projected() -> None:
    """K04-F9 X23 (ADR 0013 D5): `run_checks`, the primitive a partial checkpoint's `CheckReport`
    reads (K04 §8.3), judges every category at the state it is given. At A02-355 from 358 K its
    S3 values are F9's raw ones — the unprojected functions' at `x_final`, bit for bit — not the
    certificate's; and a `CheckReport` carries no `transformations` and no projection."""
    from openflowsheet.verify.certificate import CheckReport, run_checks

    item = solved_355()
    checks, digest = run_checks(item.binding.flowsheet, item.result.state)
    reported = by_id_list(checks)
    raw = by_id_list(_unprojected(item))
    s3 = [name for name in raw if name.startswith("independent_split.S3.")] + [
        "energy_balance.heater",
        "energy_balance.flash",
    ]
    for name in s3:
        assert reported[name].value == raw[name].value, name
    assert reported["energy_balance.heater"].near_threshold is True
    issued = by_id(
        verify_bound(item.binding, item.document, item.result, solve_plan=item.solve_plan)
    )
    total = "independent_split.S3.total"
    assert reported[total].value != issued[total].value
    report = CheckReport(checks=tuple(checks), target_state_sha256=digest)
    assert set(report.as_document()) == {"checks", "target_state_sha256"}


def _nominal() -> tuple[Any, Any]:
    from test_k04_checks import flowsheet_for

    from openflowsheet.orchestrator.tear import solve_tear

    loaded = yaml.safe_load(
        (REPO_ROOT / "benchmarks" / "syn001" / "reference_values.yaml").read_text()
    )
    (case,) = [entry for entry in loaded["variants"] if entry["case_id"] == "SYN-001-nominal"]
    flowsheet = flowsheet_for(case)
    result, _ = solve_tear(flowsheet)
    assert result.outcome == "CONVERGED"
    return flowsheet, result


def test_x24_a_certificate_issued_twice_is_identical() -> None:
    """K04-F9 X24: SYN-001's nominal certificate (`verify`), HOM-01's and A02-355's
    (`verify_bound`) issued twice in one process are the same document, byte for byte in canonical
    JSON — `transformations.projection` included."""
    from openflowsheet.canonical import canonical_json

    flowsheet, result = _nominal()
    pairs = [(verify(flowsheet, result), verify(flowsheet, result))]
    for item in (solved("HOM-01"), solved_355()):
        first = verify_bound(item.binding, item.document, item.result, solve_plan=item.solve_plan)
        second = verify_bound(item.binding, item.document, item.result, solve_plan=item.solve_plan)
        pairs.append((first, second))
    for first, second in pairs:
        assert first.transformations["projection"] == PROJECTED
        assert canonical_json(first.as_document()) == canonical_json(second.as_document())


def solved_355() -> Solved:
    return solved_named("SYN-001-A02-355")


def solved_named(name: str) -> Solved:
    if name not in _SOLVED:
        document = yaml.safe_load((CASES / f"{name}.yaml").read_text())
        run = plan_run(
            document, SolvePolicy(policy_id="T04-W12", residual_tolerances={}, scales={})
        )
        step = region_step(run.result)
        assert step.outcome == "CONVERGED" and step.eo_recovery is None
        (planned,) = [s for s in run.plan.steps if s.kind == "solve_eo"]
        binding = bind_revision(document)
        assert isinstance(binding, Binding)
        _SOLVED[name] = Solved(name, document, binding, step.detail, planned.solve_plan)
    return _SOLVED[name]


# ------------------------------------------------------------------ A03: λ < 1 is refused


@pytest.mark.parametrize(("case_id", "level"), [("HOM-03", "23/256"), ("HOM-04", "909/1024")])
def test_a03_a_stall_checkpoint_below_lambda_one_is_refused_before_anything(
    case_id: str, level: str
) -> None:
    """T04 §4.4: K04 refuses a checkpoint whose `continuation_lambda` is present and not `"1"`,
    with `continuation_level(<p/q>)`, before any check — whether handed the checkpoint itself, the
    stalled recovery region result, or the plan result, through either entry point. Nothing is
    compiled and no residual is evaluated."""
    run = full_run(case_id)
    step = region_step(run.result)
    recovery = step.detail
    assert recovery.outcome == "HOMOTOPY_STALLED"
    assert recovery.checkpoint.continuation_lambda == level
    document = case_document(case_id)
    binding = bind_revision(document)
    assert isinstance(binding, Binding)
    message = rf"^continuation_level\({level}\)$"
    with pytest.MonkeyPatch.context() as patch:
        calls = spied_compile(patch)
        compiled: list[Any] = []
        patch.setattr(certificate_module, "compile_problem", lambda spec: compiled.append(spec))
        for handed in (recovery.checkpoint, recovery, run.result):
            with pytest.raises(VerifierError, match=message):
                verify_bound(binding, document, handed)
            with pytest.raises(VerifierError, match=message):
                verify(binding.flowsheet, handed)
    assert calls == [] and compiled == []


def test_a03_a_lambda_one_checkpoint_is_not_refused_for_its_level() -> None:
    """A converged homotopy's checkpoint is at λ = 1, the target: nothing to refuse."""
    item = solved("HOM-01")
    assert item.result.checkpoint.continuation_lambda == "1"
    assert certificate("HOM-01").verification_status == "VERIFIED"
