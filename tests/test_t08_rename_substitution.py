"""R-149: the rename `process_runtime` → `openflowsheet` moved registered values by substitution
only (`tests/t08_rename_substitution.py`; Frank, 2026-10-02).

Per moved value, two halves, as for R-148: the committed value with the substitution reversed is
the pre-rename one byte for byte (a SHA-256 registered from `50602a0`), and the code with the two
self-hashes set back to their pre-rename values emits the pre-rename value. The K05 identity's
halves are in `test_t07_identity.py` and `test_t08_w1_identity_substitution.py`, the T06 start
sets' in `test_t06_w6_generator.py` and `test_t06_w30_holdout.py` (§6.5 never regenerates the
published files, so they keep the pre-rename hashes and are compared substituted back).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from conftest import REPO_ROOT
from t08_rename_substitution import (
    FIXTURES_PRE_RENAME_SHA256,
    GENERATOR_SHA256,
    PINS_PRE_RENAME_SHA256,
    PROVIDER_SHA256,
    W3A_PRE_RENAME_SHA256,
    W5C_PRE_RENAME_SHA256,
    record_process_runtime,
    renamed_back_cli_text,
    renamed_back_fixture_text,
    renamed_back_sha256,
)

import openflowsheet.thermo.syn001 as syn001
from benchmarks.t06 import generator
from openflowsheet.run.compare import differences
from openflowsheet.run.manifest import THREAD_VARIABLES

FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "schemas"
#: Fixture trees first emitted after the rename, by the current code: they carry the post-rename
#: provider hash because they were born with it, not because the rename moved them. Each entry
#: names the package that added it; the rename's claim is about every other fixture.
ADDED_AFTER_THE_RENAME = ()


# -- the two sources ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("path", "pair", "live"),
    [
        (Path(syn001.__file__), PROVIDER_SHA256, syn001._implementation_sha256),
        (Path(generator.__file__), GENERATOR_SHA256, generator.generator_sha256),
    ],
    ids=["provider", "t06_generator"],
)
def test_each_self_hash_moved_by_the_package_name_only(
    path: Path, pair: tuple[str, str], live: object
) -> None:
    """The live hash is the registered new one, and the module's bytes with `openflowsheet`
    replaced by `process_runtime` hash to the pre-rename one: the rename changed nothing else."""
    new, old = pair
    assert callable(live)
    assert live() == hashlib.sha256(path.read_bytes()).hexdigest() == new
    assert renamed_back_sha256(path) == old


# -- the schema fixtures -----------------------------------------------------------------------


def test_the_schema_fixtures_moved_by_the_rename_only() -> None:
    assert all((FIXTURE_DIR / name).is_dir() for name in ADDED_AFTER_THE_RENAME)
    moved = sorted(
        str(path.relative_to(FIXTURE_DIR))
        for path in FIXTURE_DIR.rglob("*.json")
        if path.relative_to(FIXTURE_DIR).parts[0] not in ADDED_AFTER_THE_RENAME
        and PROVIDER_SHA256[0][:12] in path.read_text(encoding="utf-8")
    )
    assert moved == sorted(FIXTURES_PRE_RENAME_SHA256)
    for name, registered in FIXTURES_PRE_RENAME_SHA256.items():
        text = (FIXTURE_DIR / name).read_text(encoding="utf-8")
        before = renamed_back_fixture_text(text)
        assert before != text, name
        assert PROVIDER_SHA256[0][:12] not in before, name
        assert hashlib.sha256(before.encode("utf-8")).hexdigest() == registered, name


def test_with_the_pre_rename_self_hashes_a_run_emits_the_pre_rename_fixtures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The fixtures' own generators (K03's, K04's, K05's, T04's) emit the pre-rename fixtures
    under the generated-fixture tests' comparison, and (on the fixture's platform) the manifest's
    certificate hash."""
    import sys

    from test_k05_schemas import _platform

    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    import k03_schema_fixtures
    import k04_schema_fixtures
    import k05_schema_fixtures
    import t04_schema_fixtures

    record_process_runtime(monkeypatch)
    emitted = {
        name: document
        for module in (
            k03_schema_fixtures,
            k04_schema_fixtures,
            k05_schema_fixtures,
            t04_schema_fixtures,
        )
        for name, document in module.documents().items()
        if name in FIXTURES_PRE_RENAME_SHA256
    }
    assert set(emitted) == set(FIXTURES_PRE_RENAME_SHA256)

    def before(name: str) -> object:
        return json.loads(renamed_back_fixture_text((FIXTURE_DIR / name).read_text("utf-8")))

    for name in FIXTURES_PRE_RENAME_SHA256:
        found = differences(emitted[name], before(name), policy_id="K04-numerical-policy-v1")
        assert not found, (name, found)
    name = "run_manifest/valid/syn001_nominal.json"
    manifest = before(name)
    assert isinstance(manifest, dict)
    assert emitted[name]["structural_sha256"] == manifest["structural_sha256"]
    if _platform(emitted[name]["environment"]) == _platform(manifest["environment"]):
        certificate = "solution-certificate.json"
        assert emitted[name]["artifacts"][certificate] == manifest["artifacts"][certificate]


# -- the CLI's pins ----------------------------------------------------------------------------


def test_the_cli_pins_moved_by_the_rename_only() -> None:
    from test_t07_w5b_cli import PINS

    text = PINS.read_text(encoding="utf-8")
    before = renamed_back_cli_text(text)
    assert before != text
    assert hashlib.sha256(before.encode("utf-8")).hexdigest() == PINS_PRE_RENAME_SHA256


def test_with_the_pre_rename_self_hashes_the_cli_prints_the_pre_rename_pins(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from test_t07_w5b_cli import PINS, capture_existing

    for variable in THREAD_VARIABLES:
        monkeypatch.setenv(variable, "1")
    pinned = json.loads(renamed_back_cli_text(PINS.read_text(encoding="utf-8")))
    record_process_runtime(monkeypatch)
    record = capture_existing(tmp_path / "run")
    assert [entry["argv"] for entry in record] == [entry["argv"] for entry in pinned]
    for now, then in zip(record, pinned, strict=True):
        assert now == then, " ".join(then["argv"][:2])


# -- T07 W5c, W3a, W3f -------------------------------------------------------------------------


def test_with_the_pre_rename_self_hashes_the_w5c_table_is_the_pre_rename_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from test_t07_w5c_signatures import EXPECTED, revision_outcomes

    record_process_runtime(monkeypatch)
    outcomes = revision_outcomes()
    assert list(outcomes) == list(EXPECTED)
    digest = hashlib.sha256(json.dumps(outcomes, sort_keys=True).encode()).hexdigest()
    assert digest == W5C_PRE_RENAME_SHA256
    # Only `binds` digests moved: every other outcome is the committed table's.
    assert all(
        outcomes[name] == value for name, value in EXPECTED.items() if not value.startswith("binds")
    )


def test_with_the_pre_rename_self_hashes_the_legacy_plans_are_the_pre_rename_ones(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import test_t07_w3a_revision_runs as w3a

    record_process_runtime(monkeypatch)
    table = []
    for (name, policy_id), expected in w3a.LEGACY_PLAN.items():
        if expected == ("raised ValueError",):
            table.append([name, policy_id, *expected])
            continue
        binding = w3a.bind_revision_or_reason(w3a.CORPUS[name]())
        plan, report = w3a.legacy_plan(binding, w3a.APPLICATION_POLICIES[policy_id])
        digests = (w3a._digest(plan.as_document()), w3a._digest(report.as_document()))
        table.append([name, policy_id, *digests])
    assert hashlib.sha256(json.dumps(table).encode()).hexdigest() == W3A_PRE_RENAME_SHA256


def test_with_the_pre_rename_self_hashes_the_failure_bundles_are_the_pre_rename_ones(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from test_t07_w3f_initializer_bundle import Q1_FILLED_PRE_RENAME, Q1_ROWS, run_sessions

    from openflowsheet.canonical import canonical_json
    from openflowsheet.run.bundle import read_artifact

    record_process_runtime(monkeypatch)
    sessions = run_sessions(tmp_path)
    for name in Q1_ROWS:
        data = canonical_json(read_artifact(sessions[name]["directory"], "failure-bundle.json"))
        assert (hashlib.sha256(data).hexdigest(), len(data)) == Q1_FILLED_PRE_RENAME[name]
