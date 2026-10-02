"""T07 W3e: `solution-state.json`, the state a revision bundle's certificate judged.

Design note `docs/design/T07-jobs-and-bindings.md`, ruling round 2 (V17 F1): F1.1 (the document
and the writer's assertion), F1.2 (the schema), F1.3 (R0: `variable_ids` only), F1.4 (the
cross-check in `verify_bundle`), and W3e's tests (a)–(g). (e) — G5's interrupted solves — needs
the job layer and is W4's; (g)'s G6/G7 likewise.

Expectations are stated independently: the values are judged against the P01 20-digit references
at T02 §6.4's allowances (read **from the file**, G8 (f)); the forgeries are built by hand and
each is one F1.4 check's case.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import pytest
from conftest import REPO_ROOT, load_json
from jsonschema import Draft202012Validator
from t06_ensemble_support import _a02_sweep, _p01_variant
from t06_support import worst_ratio
from test_t07_w3a_revision_runs import (
    A02_SWEEP,
    BUNDLED,
    P01_VARIANTS,
    _reproduce,
    runs,  # noqa: F401  (the module-scoped fixture: every G8 bundle)
)

from openflowsheet.canonical import canonical_json
from openflowsheet.run.bundle import read_artifact, read_manifest, verify_bundle, write_bundle
from openflowsheet.run.compare import differences
from openflowsheet.run.identity import r0_projection, r0_sha256
from openflowsheet.run.solution_state import NAME, SCHEMA_VERSION, document, inconsistencies

SCHEMA = REPO_ROOT / "schemas" / "solution-state.schema.json"
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "schemas"
FIXTURE = "solution_state/valid/syn001_nominal_revision_eo.json"
#: W3e (f): the `/variables` projection's bound.
PROJECTION_BYTES = 65_536


def _state(run: dict[str, Any]) -> Any:
    return read_artifact(run["directory"], NAME)


# -- the schema and its fixture (F1.2) ----------------------------------------------------------


def test_the_schema_is_a_valid_self_contained_2020_12_schema() -> None:
    schema = load_json(SCHEMA)
    Draft202012Validator.check_schema(schema)
    assert schema["$id"].endswith("/solution-state.schema.json")
    assert schema["additionalProperties"] is False
    assert sorted(schema["required"]) == [
        "schema_version",
        "state_sha256",
        "variable_ids",
        "variables",
    ]
    assert "$ref" not in json.dumps(schema)


def test_the_fixture_validates_round_trips_and_is_consistent() -> None:
    fixture = load_json(FIXTURE_DIR / FIXTURE)
    assert list(Draft202012Validator(load_json(SCHEMA)).iter_errors(fixture)) == []
    assert json.loads(json.dumps(fixture)) == fixture
    # Consistent in itself: only the certificate is absent.
    assert inconsistencies(fixture, None) == ("certificate_missing",)
    assert inconsistencies(fixture, {"target_state_sha256": fixture["state_sha256"]}) == ()


def test_the_fixture_is_what_a_real_solve_emits_today() -> None:
    """R-015, under ADR 0007 D2: the ids exactly; the values within the float policy; the digest
    shape-checked only (a state digest is a float in disguise, `run.compare`)."""
    import sys

    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    from t07_schema_fixtures import documents

    emitted = documents()[FIXTURE]
    committed = load_json(FIXTURE_DIR / FIXTURE)
    assert emitted["variable_ids"] == committed["variable_ids"]
    assert differences(emitted, committed, policy_id="K04-numerical-policy-v1") == []


def test_the_artifact_kind_is_registered_additively() -> None:
    from openflowsheet.application.jobs.model import ARTIFACT_FILE_NAMES, ARTIFACT_KINDS

    assert ARTIFACT_FILE_NAMES["solution_state"] == NAME
    enum = load_json(REPO_ROOT / "schemas" / "job.schema.json")["$defs"]["artifact_ref"][
        "properties"
    ]["kind"]["enum"]
    assert "solution_state" in enum and list(ARTIFACT_KINDS) == enum


# -- document() --------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("ids", "vector", "why"),
    [
        (("a", "b"), (1.0,), "values for"),
        (("a", "a"), (1.0, 2.0), "repeated"),
        (("a", "b"), (1.0, math.nan), "non-finite"),
        (("a", "b"), (math.inf, 1.0), "non-finite"),
    ],
)
def test_document_refuses_a_state_that_identifies_nothing(
    ids: tuple[str, ...], vector: tuple[float, ...], why: str
) -> None:
    with pytest.raises(ValueError, match=why):
        document(ids, vector)


def test_document_hashes_as_the_boundary_does() -> None:
    """ADR 0008 D2: signed zeros normalized, so the written `0` hashes as the in-memory `-0.0`."""
    negative = document(("a", "b"), (-0.0, 1.5))
    positive = document(("a", "b"), (0.0, 1.5))
    assert negative["state_sha256"] == positive["state_sha256"]
    assert negative["schema_version"] == SCHEMA_VERSION
    written = json.loads(canonical_json(negative))
    assert inconsistencies(written, {"target_state_sha256": negative["state_sha256"]}) == ()


# -- (a) every G8 bundle; (f) sizes -------------------------------------------------------------


@pytest.mark.parametrize("name", BUNDLED)
def test_a_the_file_exists_iff_the_certificate_does_and_is_consistent(
    runs: dict[str, Any],  # noqa: F811
    name: str,
) -> None:
    run = runs[name]
    names = set(run["manifest"].artifacts)
    certified = "solution-certificate.json" in names
    assert (NAME in names) == certified
    if not certified:
        return
    state = _state(run)
    certificate = read_artifact(run["directory"], "solution-certificate.json")
    assert inconsistencies(state, certificate) == ()
    assert state["variable_ids"] == list(run["route"].binding.spec.variable_ids)
    projection = r0_projection({entry: read_artifact(run["directory"], entry) for entry in names})
    assert projection["solution_state"] == {"variable_ids": state["variable_ids"]}


def test_f_the_largest_file_fits_the_projection_bound(runs: dict[str, Any]) -> None:  # noqa: F811
    sizes = {
        name: len(canonical_json(_state(runs[name])))
        for name in BUNDLED
        if NAME in runs[name]["manifest"].artifacts
    }
    largest = max(sizes, key=sizes.__getitem__)
    assert sizes[largest] <= PROJECTION_BYTES, (largest, sizes[largest])
    # Recorded in docs/t07-measurements.md (W3e).
    assert len(sizes) == 44


# -- (b) G8 (f): the values read from the file --------------------------------------------------


def _ratio_from_file(run: dict[str, Any], root: Any) -> tuple[float, str]:
    variables = {name: float(value) for name, value in _state(run)["variables"].items()}
    if run["route"].solve_path == "revision_eo":
        renamed = {"U-HEAT.Q": "heater.Q", "U-FLASH.Q": "flash.Q"}
        root = {renamed.get(column, column): entry for column, entry in root.items()}
    return worst_ratio(variables, root)


@pytest.mark.parametrize("name", P01_VARIANTS)
def test_b_p01_variants_from_the_file_are_at_their_reference(
    runs: dict[str, Any],  # noqa: F811
    name: str,
) -> None:
    ratio, where = _ratio_from_file(runs[name], _p01_variant(name))
    assert ratio <= 1.0, (ratio, where)


@pytest.mark.parametrize("name", sorted(A02_SWEEP))
def test_b_a02_sweep_files_from_the_file_are_at_t02s_reference(
    runs: dict[str, Any],  # noqa: F811
    name: str,
) -> None:
    ratio, where = _ratio_from_file(runs[name], _a02_sweep(f"T_heater={A02_SWEEP[name]}"))
    assert ratio <= 1.0, (ratio, where)


# -- (c) forgeries -----------------------------------------------------------------------------


def _forge(source: Path, target: Path, **changes: Any) -> Path:
    """A copy with artifacts replaced (`None` drops one), index and both manifest hashes
    recomputed: only the cross-check can see it."""
    from dataclasses import replace

    manifest, _ = read_manifest(source)
    artifacts = {name: read_artifact(source, name) for name in manifest.artifacts}
    for name, value in changes.items():
        if value is None:
            artifacts.pop(name, None)
        else:
            artifacts[name] = value
    forged = replace(manifest, artifact_r0_sha256=r0_sha256(r0_projection(artifacts)))
    write_bundle(target, forged, artifacts)
    return target


def _nudged(value: float) -> float:
    return math.nextafter(value, math.inf)


FORGERIES = {
    "a value moved one ulp": ("state_sha256_mismatch", "ulp"),
    "the same with a recomputed state_sha256": ("certificate_state_mismatch", "ulp+hash"),
    "an id dropped from variables": ("variables_not_variable_ids", "drop"),
    "an id added to variables only": ("variables_not_variable_ids", "add"),
    "the certificate deleted and de-indexed": ("certificate_missing", "no-certificate"),
    "schema_version changed": ("schema(/schema_version", "version"),
}


@pytest.mark.parametrize("case", sorted(FORGERIES))
def test_c_each_forgery_is_caught_by_the_cross_check(
    runs: dict[str, Any],  # noqa: F811
    tmp_path: Path,
    case: str,
) -> None:
    from openflowsheet.canonical import state_sha256

    source = runs["SYN-001-T06-NET03"]["directory"]
    state = json.loads(json.dumps(read_artifact(source, NAME)))
    certificate = read_artifact(source, "solution-certificate.json")
    reason, how = FORGERIES[case]
    first = state["variable_ids"][0]
    changes: dict[str, Any] = {}
    if how in ("ulp", "ulp+hash"):
        state["variables"][first] = _nudged(float(state["variables"][first]))
        if how == "ulp+hash":
            state["state_sha256"] = state_sha256(
                {k: float(v) for k, v in state["variables"].items()}, state["variable_ids"]
            )
    elif how == "drop":
        del state["variables"][first]
    elif how == "add":
        state["variables"]["forged.id"] = 1.0
    elif how == "no-certificate":
        changes["solution-certificate.json"] = None
        certificate = None
    elif how == "version":
        state["schema_version"] = "solution-state-v2"
    changes[NAME] = state
    bundle = _forge(source, tmp_path / "forged", **changes)
    assert any(entry.startswith(reason) for entry in inconsistencies(state, certificate))
    integrity = verify_bundle(bundle)
    assert integrity.ok is False
    assert NAME in integrity.tampered
    assert integrity.missing == () and integrity.unexpected == ()


def test_c_the_fully_consistent_forgery_is_exposed_only_by_a_rerun(
    runs: dict[str, Any],  # noqa: F811
    tmp_path: Path,
) -> None:
    """F1.4, not caught: the certificate's `target_state_sha256` rewritten too. Integrity-clean;
    the same-host rerun re-solves and reports `MISMATCH` on `variables`."""
    from openflowsheet.canonical import state_sha256

    source = runs["SYN-001-T06-NET03"]["directory"]
    state = json.loads(json.dumps(read_artifact(source, NAME)))
    first = state["variable_ids"][0]
    state["variables"][first] = float(state["variables"][first]) * 1.001
    state["state_sha256"] = state_sha256(
        {k: float(v) for k, v in state["variables"].items()}, state["variable_ids"]
    )
    certificate = dict(read_artifact(source, "solution-certificate.json"))
    certificate["target_state_sha256"] = state["state_sha256"]
    bundle = _forge(
        source, tmp_path / "forged", **{NAME: state, "solution-certificate.json": certificate}
    )
    assert verify_bundle(bundle).ok
    report = _reproduce(bundle, tmp_path).report
    assert report.verdict == "MISMATCH"
    assert any(
        entry.startswith(f"{NAME}<root>.variables.{first}") for entry in report.differences
    ), report.differences


# -- (d) rerun ---------------------------------------------------------------------------------


@pytest.mark.parametrize("name", ["SYN-001-T06-NET03", "SYN-001-A02-360"])
def test_d_a_same_host_rerun_matches_bitwise(runs: dict[str, Any], name: str) -> None:  # noqa: F811
    run = runs[name]
    assert NAME in run["manifest"].artifacts
    report = run["reproduction"].report
    assert (report.verdict, report.bitwise_floats) == ("MATCH", True)
    assert run["reproduction"].rerun_manifest is not None
    fresh = read_artifact(_rerun_dir(run), NAME)
    assert canonical_json(fresh) == canonical_json(_state(run))


def _rerun_dir(run: dict[str, Any]) -> Path:
    return run["directory"].parent / f"{run['directory'].name}.rerun"


def test_d_an_archive_without_the_file_reruns_to_mismatch(
    runs: dict[str, Any],  # noqa: F811
    tmp_path: Path,
) -> None:
    """No compatibility path for a pre-W3e revision bundle (F1.3): the rerun writes the file."""
    bundle = _forge(runs["SYN-001-T06-NET03"]["directory"], tmp_path / "old", **{NAME: None})
    assert verify_bundle(bundle).ok
    report = _reproduce(bundle, tmp_path).report
    assert report.verdict == "MISMATCH"
    assert f"{NAME}: the rerun produced an artifact the archive does not have" in (
        report.differences
    )


# -- F1.3: tear-path bundles are unchanged -------------------------------------------------------


def test_a_tear_path_bundle_has_no_solution_state(tmp_path: Path) -> None:
    from openflowsheet.application.revision_run import registered_case, registered_flowsheet
    from openflowsheet.run.session import run_session

    case = registered_case("SYN-001-nominal")
    assert case is not None
    manifest = run_session(registered_flowsheet(case), tmp_path)
    assert NAME not in manifest.artifacts
    assert verify_bundle(tmp_path).ok
