"""K05's two schemas and their fixtures, generated from real runs and real replays.

The valuable fixtures are the two that did not match. A clean `exact_replay`/`MATCH` proves the
happy path; `changed_dependency.json` and `tampered_archive.json` are what a reader consults
when something has gone wrong, and they are the documents that must be right.
"""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path
from typing import Any

import pytest
from conftest import REPO_ROOT, load_json
from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

from openflowsheet.run.compare import (
    PROVENANCE_SUBTREES,
    VOLATILE_FIELDS,
    differences,
)

SCHEMA_DIR = REPO_ROOT / "schemas"
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "schemas"

K05_SCHEMAS = {
    "run_manifest": "run-manifest.schema.json",
    "replay_report": "replay-report.schema.json",
}


def _registry() -> Registry:
    resources = []
    for path in sorted(SCHEMA_DIR.glob("*.schema.json")):
        document = load_json(path)
        resources.append((document["$id"], Resource(contents=document, specification=DRAFT202012)))
    return Registry().with_resources(resources)


REGISTRY = _registry()


def errors_for(name: str, document: Any) -> list[str]:
    validator = Draft202012Validator(load_json(SCHEMA_DIR / K05_SCHEMAS[name]), registry=REGISTRY)
    return [
        f"{list(error.absolute_path)}: {error.message}"
        for error in sorted(validator.iter_errors(document), key=lambda e: list(e.absolute_path))
    ]


def fixtures(name: str) -> list[Path]:
    return sorted((FIXTURE_DIR / name / "valid").glob("*.json"))


@pytest.mark.parametrize("name", sorted(K05_SCHEMAS))
def test_the_schema_is_itself_valid(name: str) -> None:
    Draft202012Validator.check_schema(load_json(SCHEMA_DIR / K05_SCHEMAS[name]))


@pytest.mark.parametrize(
    ("name", "path"),
    [(name, path) for name in sorted(K05_SCHEMAS) for path in fixtures(name)],
    ids=lambda value: value.stem if isinstance(value, Path) else str(value),
)
def test_the_fixtures_validate_and_round_trip(name: str, path: Path) -> None:
    document = load_json(path)
    assert errors_for(name, document) == [], f"{path.name}: {errors_for(name, document)}"
    reloaded = json.loads(json.dumps(document))
    assert reloaded == document
    assert errors_for(name, reloaded) == []


@cache
def _emitted() -> dict[str, Any]:
    """The generator's documents from a live run (one run per session; R-015)."""
    import sys

    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    from k05_schema_fixtures import documents

    return documents()


def test_the_fixtures_are_what_a_real_run_emits_today() -> None:
    """Generated, not written (R-015), and compared with provenance excluded.

    A run manifest cannot be compared field for field against a committed copy: it records
    `elapsed_seconds`, which differs between two runs on the same machine within a second of
    each other, and an environment that differs between the two CI architectures by design.
    Those are provenance — recorded precisely *because* they vary — and the comparison checks
    their shape while leaving their values alone.

    **What "regenerates identically" means for the run manifest** (T06 spec A81 (b), register
    R-015's annotation): `run.compare.differences` is empty with `VOLATILE_FIELDS` excluded —
    this test — and Q-S7's certificate-hash check passes on the fixture's platform — the next
    one. A byte comparison is not the definition: `elapsed_seconds` alone makes every
    regeneration byte-different, so `scripts/k05_schema_fixtures.py` always reports the file as
    differing. The fixture is rewritten only when one of these two checks fails, never for a
    volatile field.
    """
    emitted = _emitted()
    assert set(emitted) == {
        str(path.relative_to(FIXTURE_DIR)) for name in K05_SCHEMAS for path in fixtures(name)
    }
    for name, document in emitted.items():
        found = differences(
            document, load_json(FIXTURE_DIR / name), policy_id="K04-numerical-policy-v1"
        )
        assert not found, (
            f"{name} is not what a run emits:\n  "
            + "\n  ".join(found)
            + "\nIf intended, regenerate with `python scripts/k05_schema_fixtures.py --write`."
        )


def _platform(environment: dict[str, Any]) -> tuple[str, str, str, str]:
    """`Environment.identity()` of a recorded environment (ADR 0007 D3.3's platform tuple)."""
    return (
        environment["architecture"],
        environment["os_name"],
        environment["python_version"],
        str(environment["blas"].get("name", "")),
    )


def test_the_manifest_fixtures_certificate_hash_is_the_emitted_one() -> None:
    """Q-S7 (ruled 2026-09-25; closes R-015's gap): the fixture's `solution-certificate.json`
    hash equals the one a live run emits. The comparison above leaves `artifacts` alone because
    their documents carry floats, so a stale certificate hash went unseen there.

    Exact on the platform the fixture records: a certificate carries the converged state's
    floats, which ADR 0007 measured one to three ulps apart between x86-64 and aarch64 (the
    SuperLU factorization, Context 2), and blueprint §8.3 makes no cross-platform bitwise promise
    for them. On another platform the hash is not compared, and the skip says so."""
    name = "run_manifest/valid/syn001_nominal.json"
    committed = load_json(FIXTURE_DIR / name)
    emitted = _emitted()[name]
    if _platform(emitted["environment"]) != _platform(committed["environment"]):
        pytest.skip(
            f"the fixture records platform {_platform(committed['environment'])}, this run is "
            f"{_platform(emitted['environment'])}: certificate floats are not promised bitwise "
            "across platforms (ADR 0007, blueprint §8.3)"
        )
    certificate = "solution-certificate.json"
    assert committed["artifacts"][certificate] == emitted["artifacts"][certificate], (
        f"{name}'s {certificate} hash is stale; regenerate with "
        "`python scripts/k05_schema_fixtures.py --write`"
    )


def test_r148_the_fixtures_moved_by_the_v2_recording_switch_only() -> None:
    """R-148: reversed, every fixture the switch moved is its pre-switch bytes again (after the
    rename's reversal, R-149)."""
    import hashlib

    from t08_rename_substitution import renamed_back_fixture_text
    from t08_v2_substitution import FIXTURES_V1_SHA256, v2_reversed_fixture_text

    for name, registered in FIXTURES_V1_SHA256.items():
        text = renamed_back_fixture_text((FIXTURE_DIR / name).read_text(encoding="utf-8"))
        reversed_text = v2_reversed_fixture_text(text)
        assert reversed_text != text, name
        assert hashlib.sha256(reversed_text.encode("utf-8")).hexdigest() == registered, name


def test_r148_with_v1_recorded_a_run_emits_the_pre_switch_fixtures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """R-148's substitution proof: with the switch undone, the fixtures' own generators (K05's,
    K04's, T04's) emit the pre-switch fixtures under the generated-fixture tests' comparison, and
    (on the fixture's platform) the manifest's certificate hash."""
    import sys

    from t08_rename_substitution import record_process_runtime, renamed_back_fixture_text
    from t08_v2_substitution import FIXTURES_V1_SHA256, record_v1, v2_reversed_fixture_text

    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    import k04_schema_fixtures
    import k05_schema_fixtures
    import t04_schema_fixtures

    def before_text(name: str) -> str:
        text = (FIXTURE_DIR / name).read_text("utf-8")
        return v2_reversed_fixture_text(renamed_back_fixture_text(text))

    record_process_runtime(monkeypatch)
    record_v1(monkeypatch)
    emitted = {
        name: document
        for generator in (k05_schema_fixtures, k04_schema_fixtures, t04_schema_fixtures)
        for name, document in generator.documents().items()
        if name in FIXTURES_V1_SHA256
    }
    assert set(emitted) == set(FIXTURES_V1_SHA256)
    for name in FIXTURES_V1_SHA256:
        before = json.loads(before_text(name))
        found = differences(emitted[name], before, policy_id="K04-numerical-policy-v1")
        assert not found, (name, found)
    name = "run_manifest/valid/syn001_nominal.json"
    before = json.loads(before_text(name))
    assert emitted[name]["structural_sha256"] == before["structural_sha256"]
    if _platform(emitted[name]["environment"]) == _platform(before["environment"]):
        certificate = "solution-certificate.json"
        assert emitted[name]["artifacts"][certificate] == before["artifacts"][certificate]


def test_the_changed_dependency_report_is_unambiguous() -> None:
    """G05's first clause, serialized. Both fields say it, and neither stands for the other."""
    document = load_json(FIXTURE_DIR / "replay_report" / "valid" / "changed_dependency.json")
    assert document["mode"] == "inspected_archived_results"
    assert document["verdict"] == "NOT_RUN"
    assert any("lock file differs" in reason for reason in document["reasons"])
    assert document["integrity"]["ok"] is True, (
        "the archive is intact; it is the environment that moved, and the report must not "
        "conflate the two"
    )
    assert document["differences"] == []
    assert document["bitwise_floats"] is None, "nothing was re-run, so nothing was observed"


def test_the_tampered_archive_report_is_unambiguous() -> None:
    """A tampered archive is not re-run at all — matching on what survived is a false success."""
    document = load_json(FIXTURE_DIR / "replay_report" / "valid" / "tampered_archive.json")
    assert document["mode"] == "inspected_archived_results"
    assert document["verdict"] == "NOT_RUN"
    assert document["integrity"]["ok"] is False
    assert "solve-events.json" in document["integrity"]["tampered"]
    assert any("integrity" in reason for reason in document["reasons"])


def test_the_clean_replay_report_records_bitwise_without_promising_it() -> None:
    """ADR 0007 D3 and Frank's F1 ruling: observed, never promised."""
    document = load_json(FIXTURE_DIR / "replay_report" / "valid" / "exact_match.json")
    assert document["mode"] == "exact_replay"
    assert document["verdict"] == "MATCH"
    assert document["bitwise_floats"] is True
    assert document["differences"] == []
    assert document["verdict_changed_near_threshold"] == []


def test_the_manifest_fixture_separates_identity_from_provenance() -> None:
    """The distinction the whole package turns on, visible in one document."""
    document = load_json(FIXTURE_DIR / "run_manifest" / "valid" / "syn001_nominal.json")

    assert document["outcome"] == "CONVERGED"
    assert document["verification_status"] == "VERIFIED"
    assert document["numerical_policy_id"] == "T08-numerical-policy-v2"
    assert document["reproducibility_class"] in ("R0", "R1", "R2", "R3")

    # Provenance is present and complete — D6 requires every pin recorded.
    environment = document["environment"]
    assert environment["architecture"] and environment["os_name"]
    assert environment["blas"]["name"] and environment["blas"]["version"]
    assert set(environment["threads"]) == {
        "OPENBLAS_NUM_THREADS",
        "OMP_NUM_THREADS",
        "MKL_NUM_THREADS",
    }
    assert environment["superlu_options_ref"] == "ADR 0004 D1"

    # And the identity is blind to all of it.
    assert "environment" in PROVENANCE_SUBTREES
    for field in ("run_id", "started_at", "elapsed_seconds", "hostname", "artifacts"):
        assert field in VOLATILE_FIELDS, field
        assert field in document, f"{field} is recorded even though it is not compared"
