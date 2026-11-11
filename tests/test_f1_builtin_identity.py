"""F1-WO5 (ADR 0060 E-F1-5; F1 review SF-8, N-6): the real built-ins' identity and the digest
short-cut of their validation.

- **E-F1-5** Determinism: `registry_sha256` of `Registry.build(builtin_tables=
  discovery.builtin_tables())` (the built-ins alone, review N-6) is the same in fresh processes
  with `PYTHONHASHSEED=0` and `=random` and equals the committed constant
  `tests/fixtures/registry/builtin-sha256.txt`. CI runs this file on both legs.
- **SF-8**: the process registry skips the schema validation of a built-in table whose bytes,
  with the descriptor schema's, have the digest the generator recorded (`tables.sha256`). The
  committed tables have it, and skipping changes no identity; a tampered table, a reformatted
  table and a changed schema do not have it, and are validated in full: the tampered table still
  fails the build. The mutation control shows the skip is real, so the digest is what catches it.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys

import pytest
from conftest import REPO_ROOT

from openflowsheet.registry import Registry, RegistryBuildError, discovery

sys.path.insert(0, str(REPO_ROOT / "scripts"))
import registry_builtin  # noqa: E402

CONSTANT = REPO_ROOT / "tests" / "fixtures" / "registry" / "builtin-sha256.txt"
BUILTIN = REPO_ROOT / "src" / "openflowsheet" / "registry" / "builtin"

_PRINT_SHA = (
    "from openflowsheet.registry import Registry, discovery\n"
    "print(Registry.build(builtin_tables=discovery.builtin_tables()).registry_sha256)\n"
    "tables, prevalidated = discovery.checked_builtin_tables()\n"
    "print(Registry.build(builtin_tables=tables, prevalidated=prevalidated).registry_sha256)\n"
    "print(','.join(sorted(prevalidated)))\n"
)


def _committed() -> str:
    held = CONSTANT.read_text(encoding="utf-8")
    assert held.endswith("\n") and len(held.strip()) == 64
    return held.strip()


def _fresh_process(seed: str) -> list[str]:
    environment = dict(os.environ, PYTHONHASHSEED=seed)
    environment["PYTHONPATH"] = os.pathsep.join(
        [str(REPO_ROOT / "src"), *filter(None, [environment.get("PYTHONPATH")])]
    )
    completed = subprocess.run(
        [sys.executable, "-c", _PRINT_SHA],
        env=environment,
        capture_output=True,
        text=True,
        check=True,
    )
    return completed.stdout.splitlines()


def test_e_f1_5_the_built_in_registry_sha256_is_the_committed_constant_in_fresh_processes() -> None:
    committed = _committed()
    expected = [committed, committed, ",".join(sorted(discovery.builtin_tables()))]
    assert _fresh_process("0") == expected
    assert _fresh_process("random") == expected
    assert _fresh_process("random") == expected


# ---------------------------------------------------------------------------------------------
# SF-8


def _tables_from(data: dict[str, bytes]) -> dict[str, list[dict[str, object]]]:
    return {name: json.loads(table.decode("utf-8")) for name, table in data.items()}


def test_sf_8_the_committed_tables_have_the_recorded_digest() -> None:
    data = discovery._builtin_bytes()
    schema = discovery.descriptor_schema_bytes()
    assert set(data) == {"core", "legacy"}
    for name, table in data.items():
        line = (
            f"{name}\n{hashlib.sha256(table).hexdigest()}\n{hashlib.sha256(schema).hexdigest()}\n"
        )
        assert (
            discovery.table_sha256(name, table, schema)
            == hashlib.sha256(line.encode("utf-8")).hexdigest()
        )
    assert discovery.recorded_table_digests() == discovery.table_digests()
    assert discovery.prevalidated_tables() == frozenset(data)
    texts = {name: table.decode("utf-8") for name, table in data.items()}
    held = (BUILTIN / "tables.sha256").read_text(encoding="utf-8")
    assert registry_builtin.digest_record(texts) == held


def test_sf_8_skipping_the_validation_changes_no_identity() -> None:
    tables, prevalidated = discovery.checked_builtin_tables()
    assert prevalidated == frozenset(tables)
    skipped = Registry.build(builtin_tables=tables, prevalidated=prevalidated)
    full = Registry.build(builtin_tables=tables)
    assert skipped.registry_sha256 == full.registry_sha256 == _committed()
    assert skipped.snapshot() == full.snapshot()


def _tampered() -> dict[str, bytes]:
    """The committed bytes with one legacy descriptor's `title` a number: a schema violation that
    only the schema validation detects."""
    data = discovery._builtin_bytes()
    rows = json.loads(data["legacy"].decode("utf-8"))
    rows[0]["title"] = 7
    data["legacy"] = registry_builtin.render(rows).encode("utf-8")
    return data


def test_sf_8_a_tampered_built_in_table_is_still_caught(monkeypatch: pytest.MonkeyPatch) -> None:
    tampered = _tampered()
    monkeypatch.setattr(discovery, "_builtin_bytes", lambda: dict(tampered))
    tables, prevalidated = discovery.checked_builtin_tables()
    assert tables["legacy"][0]["title"] == 7
    assert prevalidated == frozenset({"core"})
    with pytest.raises(RegistryBuildError) as raised:
        Registry.build(builtin_tables=tables, prevalidated=prevalidated)
    assert raised.value.reason.code == "extension_invalid"
    assert raised.value.reason.params["pointer"] == "/title"
    # Mutation control: were the tampered table taken as prevalidated, the build would accept it.
    accepted = Registry.build(builtin_tables=tables, prevalidated=frozenset(tables))
    assert accepted.registry_sha256 != _committed()


def test_sf_8_a_reformatted_table_is_validated_in_full_and_keeps_its_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data = discovery._builtin_bytes()
    data["legacy"] = json.dumps(json.loads(data["legacy"].decode("utf-8")), indent=1).encode()
    monkeypatch.setattr(discovery, "_builtin_bytes", lambda: dict(data))
    tables, prevalidated = discovery.checked_builtin_tables()
    assert prevalidated == frozenset({"core"})
    registry = Registry.build(builtin_tables=tables, prevalidated=prevalidated)
    assert registry.registry_sha256 == _committed()


def test_sf_8_a_changed_schema_or_a_missing_record_validates_every_table(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    schema = discovery.descriptor_schema_bytes()
    with monkeypatch.context() as patch:
        patch.setattr(discovery, "descriptor_schema_bytes", lambda: schema + b"\n")
        assert discovery.prevalidated_tables() == frozenset()
    monkeypatch.setattr(discovery, "recorded_table_digests", dict)
    assert discovery.prevalidated_tables() == frozenset()
    assert discovery.checked_builtin_tables()[1] == frozenset()
