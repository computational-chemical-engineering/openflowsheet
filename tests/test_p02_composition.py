"""P02 composition test: run the judge and the SuperLU evidence on the committed artifacts.

Specification: `docs/derivations/P02-composition-spec.md` §6, §9, §11. These tests run in the
repository environment with no backend installed: the harnesses under `spikes/p02/` produced the
artifacts, and everything judged here is judged against `benchmarks/p02/expected.py` and the
40-digit reference.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from benchmarks.p02 import expected as closed_form
from benchmarks.p02.judge import (
    DRAFT_SCHEMAS,
    FAIL,
    NOT_APPLICABLE,
    PASS,
    SCHEMA_ROOT,
    UNSUPPORTED,
    check_a00,
    judge_backend,
    load_artifacts,
    verdict,
)
from benchmarks.p02.linear_solve import SUPERLU_OPTIONS, evidence
from benchmarks.p02.reference import load_reference

RESULTS_ROOT = Path(__file__).resolve().parents[1] / "spikes" / "p02" / "results"
BACKENDS = ("casadi", "pyomo")


def _artifacts_or_skip(backend: str) -> None:
    if not load_artifacts(RESULTS_ROOT, backend).jacobians:
        pytest.skip(f"P02 artifacts for {backend} not present at {RESULTS_ROOT / backend}")


def test_judge_self_test_reproduces_the_reference() -> None:
    """A00: the judge's closed forms agree with the independent 40-digit reference."""
    check = check_a00()
    assert check.result == PASS, check.message


def test_expected_patterns_have_the_specified_sizes() -> None:
    """Specification §2.5 and §2.6: 60 structural nonzeros lifted, 43 inlined."""
    assert len(closed_form.PATTERN_L) == 60
    assert len(closed_form.PATTERN_I) == 43
    assert len(closed_form.VARIABLE_IDS_L) == len(closed_form.EQUATION_IDS_L) == 17
    assert len(closed_form.VARIABLE_IDS_I) == len(closed_form.EQUATION_IDS_I) == 11


def test_reference_pattern_matches_the_closed_forms() -> None:
    """The generated reference and the judge's transcription agree on the structure."""
    reference = load_reference()
    assert reference.pattern_l == closed_form.PATTERN_L
    assert reference.pattern_i == closed_form.PATTERN_I


@pytest.mark.parametrize("backend", BACKENDS)
def test_composition_assertions(backend: str) -> None:
    """A01-A24 for one backend, from its committed artifacts."""
    _artifacts_or_skip(backend)
    checks = judge_backend(RESULTS_ROOT, backend)
    failures = [check for check in checks if check.result == FAIL]
    assert not failures, "\n".join(
        f"{check.id}: value={check.value!r} expected={check.expected} ({check.message})"
        for check in failures
    )


@pytest.mark.parametrize("backend", BACKENDS)
def test_no_assertion_is_silently_missing(backend: str) -> None:
    """Every assertion of the catalogue is reported, including as unsupported."""
    _artifacts_or_skip(backend)
    reported = {check.id.split(".")[1] for check in judge_backend(RESULTS_ROOT, backend)}
    required = {f"A{index:02d}" for index in range(1, 23)} - {"A21"}
    missing = sorted(required - reported)
    assert not missing, f"{backend}: no result reported for {missing}"


@pytest.mark.parametrize("backend", BACKENDS)
def test_linear_solve_evidence(backend: str) -> None:
    """A23: the common SuperLU solve on the matrices this backend exported."""
    _artifacts_or_skip(backend)
    checks, records = evidence(RESULTS_ROOT, backend)
    failures = [check for check in checks if check.result == FAIL]
    assert not failures, "\n".join(
        f"{check.id}: {check.value!r} {check.message}" for check in failures
    )
    assert records["superlu"] == SUPERLU_OPTIONS


@pytest.mark.parametrize("backend", BACKENDS)
def test_verdict_is_recorded(backend: str) -> None:
    """Specification §11.1: the verdict is one of the three named outcomes."""
    _artifacts_or_skip(backend)
    checks = judge_backend(RESULTS_ROOT, backend)
    assert verdict(checks, backend) in {
        "PASS-composition",
        "FAIL-composition",
        "BLOCKED-unsupported",
    }


def test_unsupported_is_reported_not_skipped() -> None:
    """A backend with no artifacts is reported as unsupported, never as a pass."""
    checks = judge_backend(RESULTS_ROOT, "no-such-backend")
    assert [check.result for check in checks] == [UNSUPPORTED]
    assert checks[0].result != NOT_APPLICABLE


def _draft_schema(name: str) -> dict[str, object]:
    import json

    path = SCHEMA_ROOT / DRAFT_SCHEMAS[name]
    with path.open(encoding="utf-8") as handle:
        loaded: dict[str, object] = json.load(handle)
    return loaded


@pytest.mark.parametrize(
    ("kind", "mutation", "reason"),
    [
        ("residual", {"status": "ok", "values": None}, "ok status with no numbers"),
        ("residual", {"status": "invalid_trial_state"}, "failure status carrying numbers"),
        ("residual", {"constants_sha256": "not-a-hash"}, "malformed hash"),
        ("residual", {"phase_signature": "SUPERCRITICAL"}, "unregistered phase signature"),
        ("jacobian", {"pattern_provenance": "guessed"}, "unknown pattern provenance"),
        ("jacobian", {"format": "coo"}, "non-CSC format"),
        ("jacobian", {"nnz": -1}, "negative nnz"),
    ],
)
def test_draft_schemas_reject_malformed_documents(
    kind: str, mutation: dict[str, object], reason: str
) -> None:
    """A schema that accepts everything proves nothing: each of these must be rejected."""
    jsonschema = pytest.importorskip("jsonschema")
    _artifacts_or_skip("casadi")
    artifacts = load_artifacts(RESULTS_ROOT, "casadi")
    source = (
        artifacts.residuals[("S1", "L")] if kind == "residual" else artifacts.jacobians[("S1", "L")]
    )
    document = dict(source)
    document.update(mutation)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(document, _draft_schema(kind))


def test_draft_schemas_accept_the_emitted_documents() -> None:
    """The same schemas accept every document the harness actually wrote."""
    jsonschema = pytest.importorskip("jsonschema")
    _artifacts_or_skip("casadi")
    artifacts = load_artifacts(RESULTS_ROOT, "casadi")
    for payload in artifacts.residuals.values():
        jsonschema.validate(payload, _draft_schema("residual"))
    for payload in artifacts.jacobians.values():
        jsonschema.validate(payload, _draft_schema("jacobian"))
    for payload in artifacts.metadata.values():
        jsonschema.validate(payload, _draft_schema("metadata"))


def _mutated_results(tmp_path: Path, mutate: object) -> Path:
    """Copy the CasADi result set into `tmp_path` and apply `mutate` to one Jacobian document."""
    import json
    import shutil

    destination = tmp_path / "results"
    shutil.copytree(RESULTS_ROOT, destination)
    assert callable(mutate)
    mutate(destination / "casadi" / "states")
    del json
    return destination


def test_judge_detects_a_perturbed_jacobian_entry(tmp_path: Path) -> None:
    """A10 and A14 must fail on a one-part-in-1e9 change to a single assembled entry.

    A check that cannot fail is not evidence: this is the question of what would still pass if the
    backend were subtly wrong.
    """
    import json

    _artifacts_or_skip("casadi")

    def mutate(states: Path) -> None:
        path = states / "S1" / "jacobian_L.json"
        document = json.loads(path.read_text(encoding="utf-8"))
        index = next(i for i, value in enumerate(document["data"]) if value != 0.0)
        document["data"][index] *= 1.0 + 1e-9
        path.write_text(json.dumps(document), encoding="utf-8")

    checks = judge_backend(_mutated_results(tmp_path, mutate), "casadi")
    failed = {check.id for check in checks if check.result == FAIL}
    assert "P02.A10.casadi.L" in failed, sorted(failed)


def test_judge_detects_a_structural_zero_that_is_not_exactly_zero(tmp_path: Path) -> None:
    """A11 must fail when an entry that should be exactly 0.0 comes back as 1e-13."""
    import json

    _artifacts_or_skip("casadi")

    def mutate(states: Path) -> None:
        path = states / "S3" / "jacobian_L.json"
        document = json.loads(path.read_text(encoding="utf-8"))
        index = next(i for i, value in enumerate(document["data"]) if value == 0.0)
        document["data"][index] = 1e-13
        path.write_text(json.dumps(document), encoding="utf-8")

    checks = judge_backend(_mutated_results(tmp_path, mutate), "casadi")
    failed = {check.id for check in checks if check.result == FAIL}
    assert "P02.A11.casadi.L" in failed, sorted(failed)


def test_absent_evidence_is_unsupported_never_a_pass(tmp_path: Path) -> None:
    """Deleting an artifact must turn its checks unsupported, not leave them passing.

    A check whose evidence is missing once reported `pass` here, because its deviation list was
    empty and the worst of nothing is zero. That is the failure mode this test exists for.
    """
    import shutil

    _artifacts_or_skip("casadi")
    destination = tmp_path / "results"
    shutil.copytree(RESULTS_ROOT, destination)
    removals = {
        "block_records.json": {"A02", "A04", "A05", "A06", "A07"},
        "directional_stencils.json": {"A15"},
        "second_order.json": {"A22"},
    }
    for filename, affected in removals.items():
        target = destination / "casadi" / filename
        assert target.exists(), f"{filename} is not in the result set; this test would pass blindly"
        target.unlink()
        checks = judge_backend(destination, "casadi")
        for check in checks:
            identifier = check.id.split(".")[1]
            if identifier in affected:
                assert check.result != PASS, (
                    f"{check.id} passed with {filename} deleted: {check.value!r}"
                )


def test_states_that_failed_to_evaluate_cannot_pass(tmp_path: Path) -> None:
    """A backend that could not evaluate the single-phase states must not be PASS-composition.

    The per-state loops skip a record whose status is not `ok`, and the worst deviation over an
    empty list is zero, so before the coverage guard a backend could fail S3 and S4 entirely and
    still be reported as passing. S3 and S4 are registered precisely because entries vanish there.
    """
    import json
    import shutil

    _artifacts_or_skip("casadi")
    destination = tmp_path / "results"
    shutil.copytree(RESULTS_ROOT, destination)
    for state_id in ("S3", "S4"):
        for form in ("L", "I"):
            for kind in ("residual", "jacobian"):
                path = destination / "casadi" / "states" / state_id / f"{kind}_{form}.json"
                if not path.exists():
                    continue
                document = json.loads(path.read_text(encoding="utf-8"))
                document["status"] = "error"
                document["message"] = "simulated backend failure"
                if kind == "residual":
                    document["values"] = None
                else:
                    document.update({"indptr": [], "indices": [], "data": [], "nnz": 0})
                path.write_text(json.dumps(document), encoding="utf-8")

    checks = judge_backend(destination, "casadi")
    assert verdict(checks, "casadi") == "FAIL-composition"
    failed = {check.id for check in checks if check.result == FAIL}
    for identifier in ("A08", "A10", "A11", "A12"):
        assert any(identifier in check_id for check_id in failed), (identifier, sorted(failed))


def test_missing_state_records_are_unsupported(tmp_path: Path) -> None:
    """Deleting the single-phase state directories must block the verdict, not pass it."""
    import shutil

    _artifacts_or_skip("casadi")
    destination = tmp_path / "results"
    shutil.copytree(RESULTS_ROOT, destination)
    for state_id in ("S3", "S4"):
        shutil.rmtree(destination / "casadi" / "states" / state_id)
    checks = judge_backend(destination, "casadi")
    assert verdict(checks, "casadi") == "BLOCKED-unsupported"
    assert not any(
        check.result == PASS and check.id.split(".")[1] in {"A08", "A10", "A11", "A12"}
        for check in checks
    )
