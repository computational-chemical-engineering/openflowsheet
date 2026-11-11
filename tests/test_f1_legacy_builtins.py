"""F1-WO2 (ADR 0060 D6, D8): the legacy built-ins, and exit tests E-F1-1 to E-F1-4.

- **E-F1-1** Legacy admission: the registered universe is pinned (31 units, 7 methods); over
  31 × 7 on `nTP-v1` the admitted set equals `MODEL_BASES` exactly, 54 admitted and 163 refused
  (156 `capability_missing` naming the legacy clause, 7 `model_unsupported(syn001.cascade)`).
  Mutation controls: a clause losing `legacy:wilson-ig-v2` fails naming the pair; an extension
  providing `legacy:syn001` is quarantined and changes nothing.
- **E-F1-2** No leakage: a method providing every registered non-`legacy` token (and every static
  one) is admitted to none of the 31; an extension unit requiring `legacy:pr-c1-v1` is
  quarantined `reserved_capability`.
- **E-F1-3** Payload faithfulness, against providers constructed here by their own classes (not
  the generator's `basis_provider` route): `describe()`, `PROVIDER_ID`, `DERIVATIVE_INPUTS`,
  `selectable_bases()`, `FRESH_PROVIDERS`, all 123 CoolProp fluids; each unit's `signature` is its
  `list_models` entry; each factory resolves.
- **E-F1-4** Self-hash: the union of the 38 implementation sets, `src/`-prefixed, is F0's M9 set
  (35 paths); every self-hash recomputes with `hashlib`; a CRLF copy hashes the same.

Also: `scripts/registry_builtin.py --check` is clean and reports a changed table by pointer; the
legacy payloads apply to the `legacy` table only; `default_registry()` is built once and closed.
"""

from __future__ import annotations

import ast
import copy
import hashlib
import importlib
import inspect
import json
import sys
import threading
import tomllib
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pytest
from conftest import REPO_ROOT

from openflowsheet.application.local import LocalApplication
from openflowsheet.application.revision_binding import MODEL_BASES
from openflowsheet.models.revision_flowsheet import selectable_bases
from openflowsheet.registry import (
    ExtensionPackage,
    Registered,
    Registry,
    RegistryBuildError,
    default_registry,
    legacy,
)
from openflowsheet.registry.selfhash import self_sha256
from openflowsheet.registry.tokens import STATIC_SPACES, parse
from openflowsheet.verify.certificate import FRESH_PROVIDERS

sys.path.insert(0, str(REPO_ROOT / "scripts"))
import corpus_identity  # noqa: E402
import registry_builtin  # noqa: E402

SOURCE = REPO_ROOT / "src"
DEFINITION = "nTP-v1"
CASCADE = "syn001.cascade"
#: D6's seven legacy provider ids, pinned here.
METHODS = (
    "coolprop-heos-v1",
    "iapws95-v1",
    "pr-c1-v1",
    "pr-lib-v1",
    "syn001",
    "wilson-ig-v1",
    "wilson-ig-v2",
)


def _build(table: Sequence[Mapping[str, Any]] | None = None, **kwargs: Any) -> Registry:
    rows = legacy.table() if table is None else table
    return Registry.build(builtin_tables={legacy.TABLE_NAME: rows}, **kwargs)


@pytest.fixture(scope="module")
def registry() -> Registry:
    return _build()


def _ids(registry: Registry, kind: str) -> set[str]:
    return {entry.id for entry in registry.descriptors((kind,)) if entry.origin == "builtin"}


def _package(namespace: str, descriptors: list[dict[str, Any]]) -> ExtensionPackage:
    return ExtensionPackage(
        distribution=f"{namespace}-dist",
        distribution_version="1.0.0",
        entry_point=namespace,
        import_root=SOURCE,
        document={
            "package_format": "openflowsheet-extension-package-v1",
            "namespace": namespace,
            "descriptors": descriptors,
        },
    )


def _extension(kind: str, identifier: str, **fields: Any) -> dict[str, Any]:
    document: dict[str, Any] = {
        "descriptor_format": "openflowsheet-extension-v1",
        "kind": kind,
        "id": identifier,
        "version": "1.0.0",
        "title": identifier,
        "status": "tested",
        "requires": [],
        "provides": [],
        "limitations": [],
        "platforms": ["any"],
        "pip_extra": None,
        "data_rights": None,
        "implementation": {"modules": [], "factory": None},
        "payload": {},
    }
    document.update(fields)
    return document


def _row(table: Sequence[dict[str, Any]], identifier: str) -> dict[str, Any]:
    (found,) = (row for row in table if row["id"] == identifier)
    return found


# ---------------------------------------------------------------------------------------------
# E-F1-1 Legacy admission


def test_e_f1_1_the_universe_is_pinned(registry: Registry) -> None:
    assert _ids(registry, "unit_model") == set(MODEL_BASES) | {CASCADE}
    assert len(_ids(registry, "unit_model")) == 31
    assert _ids(registry, "property_method") == set(METHODS)
    assert set().union(*MODEL_BASES.values()) <= set(METHODS)
    assert _ids(registry, "connection_definition") == {DEFINITION}
    assert len(registry.descriptors()) == 39


def _verdicts(registry: Registry) -> dict[tuple[str, str], Any]:
    return {
        (unit, method): registry.admit(unit, method, DEFINITION)
        for unit in sorted(_ids(registry, "unit_model"))
        for method in METHODS
    }


def _assert_admission_is_model_bases(registry: Registry) -> None:
    admitted = {pair for pair, verdict in _verdicts(registry).items() if verdict.admitted}
    expected = {(unit, method) for unit, methods in MODEL_BASES.items() for method in methods}
    wrong = sorted(admitted ^ expected)
    assert not wrong, f"admission differs from MODEL_BASES on (unit, method): {wrong}"


def test_e_f1_1_the_admitted_set_is_model_bases(registry: Registry) -> None:
    _assert_admission_is_model_bases(registry)
    verdicts = _verdicts(registry)
    admitted = [pair for pair, verdict in verdicts.items() if verdict.admitted]
    refused = {pair: verdict.refusal for pair, verdict in verdicts.items() if not verdict.admitted}
    assert (len(verdicts), len(admitted), len(refused)) == (217, 54, 163)
    unsupported = {pair for pair, refusal in refused.items() if refusal.code == "model_unsupported"}
    assert unsupported == {(CASCADE, method) for method in METHODS}
    for pair in unsupported:
        assert dict(refused[pair].params) == {"model": CASCADE}
    missing = {pair: refusal for pair, refusal in refused.items() if pair not in unsupported}
    assert len(missing) == 156
    for (unit, method), refusal in missing.items():
        requires = registry.resolve("unit_model", unit).requires
        (clause,) = [c for c in requires if parse(c[0]).space == "legacy"]
        assert refusal.code == "capability_missing"
        assert dict(refusal.params) == {
            "unit": unit,
            "method": method,
            "capability": "|".join(clause),
        }
    assert all(verdict.notices == () for verdict in verdicts.values())


def test_e_f1_1_mutation_a_dropped_token_fails_naming_the_pair() -> None:
    table = copy.deepcopy(legacy.table())
    flash = _row(table, "syn001.tp_flash")
    flash["requires"] = [
        [token for token in clause if token != "legacy:wilson-ig-v2"]
        for clause in flash["requires"]
    ]
    with pytest.raises(AssertionError, match=r"\[\('syn001\.tp_flash', 'wilson-ig-v2'\)\]"):
        _assert_admission_is_model_bases(_build(table))


def test_e_f1_1_mutation_an_extension_providing_legacy_is_quarantined(
    registry: Registry,
) -> None:
    method = _extension("property_method", "acme.syn", provides=["conn:nTP-v1", "legacy:syn001"])
    built = _build(packages=[_package("acme", [method])])
    (quarantine,) = built.quarantined
    assert quarantine.reason.code == "reserved_capability"
    assert dict(quarantine.reason.params) == {"token": "legacy:syn001"}
    assert _ids(built, "property_method") == set(METHODS)
    assert [entry.id for entry in built.descriptors()] == [e.id for e in registry.descriptors()]
    _assert_admission_is_model_bases(built)


# ---------------------------------------------------------------------------------------------
# E-F1-2 No leakage


def test_e_f1_2_a_method_providing_every_non_legacy_token_is_admitted_to_none(
    registry: Registry,
) -> None:
    registered = {
        token
        for entry in registry.descriptors()
        for token in (*entry.provides, *(t for clause in entry.requires for t in clause))
        if parse(token).space != "legacy"
    }
    static = {
        f"{space}:{name}"
        for space, names in STATIC_SPACES.items()
        if space != "legacy"
        for name in names
    }
    assert "conn:nTP-v1" in registered
    tokens = sorted(registered | static)
    method = _extension("property_method", "probe.everything", provides=tokens)
    built = _build(packages=[_package("probe", [method])])
    assert built.quarantined == ()
    assert set(built.resolve("property_method", "probe.everything").provides) == set(tokens)
    for unit in sorted(_ids(built, "unit_model")):
        verdict = built.admit(unit, "probe.everything", DEFINITION)
        assert not verdict.admitted, unit
        expected = "model_unsupported" if unit == CASCADE else "capability_missing"
        assert verdict.refusal is not None and verdict.refusal.code == expected, unit


def test_e_f1_2_an_extension_unit_requiring_legacy_is_quarantined() -> None:
    unit = _extension(
        "unit_model",
        "acme.unit",
        requires=[["conn:nTP-v1"], ["legacy:pr-c1-v1"]],
        payload={"bindable": True},
    )
    built = _build(packages=[_package("acme", [unit])])
    (quarantine,) = built.quarantined
    assert quarantine.reason.code == "reserved_capability"
    assert dict(quarantine.reason.params) == {"token": "legacy:pr-c1-v1"}
    assert "acme.unit" not in {entry.id for entry in built.descriptors()}


# ---------------------------------------------------------------------------------------------
# E-F1-3 Payload faithfulness


def _constructed() -> dict[str, list[Any]]:
    """Each legacy provider, constructed by its own class (CoolProp: one per fluid)."""
    from openflowsheet import resources
    from openflowsheet.thermo import _coolprop_heos_fluids as fluids
    from openflowsheet.thermo import wilson_ig
    from openflowsheet.thermo.coolprop_heos import CoolPropHeosProvider
    from openflowsheet.thermo.iapws95 import Iapws95Provider
    from openflowsheet.thermo.pr_c1 import PrC1Provider
    from openflowsheet.thermo.pr_lib import PrLibProvider
    from openflowsheet.thermo.syn001 import Syn001Provider
    from openflowsheet.thermo.wilson_ig_v2 import WilsonIdealGasProviderV2

    records = resources.packaged_path(wilson_ig.RECORDS_PATH)
    return {
        "syn001": [Syn001Provider()],
        "pr-c1-v1": [PrC1Provider()],
        "pr-lib-v1": [PrLibProvider()],
        "iapws95-v1": [Iapws95Provider()],
        "wilson-ig-v1": [wilson_ig.WilsonIdealGasProvider(records)],
        "wilson-ig-v2": [WilsonIdealGasProviderV2(records)],
        "coolprop-heos-v1": [CoolPropHeosProvider(row["id"]) for row in fluids.FLUIDS],
    }


def test_e_f1_3_method_payloads_equal_the_providers(registry: Registry) -> None:
    constructed = _constructed()
    assert len(constructed["coolprop-heos-v1"]) == 123
    bases = selectable_bases()
    assert len(bases) == 127
    listed_bases = 0
    for provider_id in METHODS:
        payload = registry.resolve("property_method", provider_id).payload
        providers = constructed[provider_id]
        module = importlib.import_module(type(providers[0]).__module__)
        assert payload["legacy_provider_id"] == module.PROVIDER_ID == provider_id
        described = [provider.describe() for provider in providers]
        for d in described:
            assert d.provider_id == provider_id and d.state_definition == DEFINITION
            assert payload["phases"] == list(d.phases)
            assert payload["flashes"] == list(d.flashes)
        if provider_id == "coolprop-heos-v1":
            assert payload["reference_convention"] == "per_component"
            per_component = payload["per_component"]
            assert len(per_component) == 123
            for d in described:
                (fluid,) = d.components
                assert per_component[fluid] == {
                    "reference_convention": d.reference_convention,
                    "properties": list(d.properties),
                    "derivative_inputs": list(d.derivative_order),
                }, fluid
            for member, of in (("properties", "properties"), ("derivative_inputs", None)):
                lists = [list(d.properties) if of else list(d.derivative_order) for d in described]
                assert payload[member] == [n for n in lists[0] if all(n in x for x in lists)]
            assert payload["properties"] == ["h", "s", "v", "Z", "cp", "Psat", "Tsat"]
            assert payload["derivative_inputs"] == ["T", "P"]
        else:
            (d,) = described
            assert payload["per_component"] is None
            assert payload["properties"] == list(d.properties)
            assert payload["reference_convention"] == d.reference_convention
            assert payload["derivative_inputs"] == list(d.derivative_order)
            declared = getattr(module, "DERIVATIVE_INPUTS", None)
            if declared is not None:
                assert payload["derivative_inputs"] == list(declared)
        own = [
            {"record_source": basis.record_source, "components": list(basis.components)}
            for basis in bases
            if basis.provider_id == provider_id
        ]
        assert payload["bases"] == own
        listed_bases += len(own)
        assert payload["selectable"] is bool(own)
        assert payload["verifier_fresh"] is (provider_id in FRESH_PROVIDERS)
    assert listed_bases == 127
    unselectable = {
        p for p in METHODS if not registry.resolve("property_method", p).payload["selectable"]
    }
    assert unselectable == {"pr-lib-v1", "wilson-ig-v1"}


def test_e_f1_3_pip_extra_and_factories_resolve(registry: Registry) -> None:
    extras = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"][
        "optional-dependencies"
    ]
    for entry in registry.descriptors():
        if entry.kind == "property_method":
            expected = "coolprop" if entry.id == "coolprop-heos-v1" else None
            assert entry.document["pip_extra"] == expected
        else:
            assert entry.document["pip_extra"] is None
        factory = entry.document["implementation"]["factory"]
        if factory is None:
            assert entry.id in {CASCADE, DEFINITION}
            continue
        target = getattr(importlib.import_module(factory["module"]), factory["attribute"])
        if factory["key"] is not None:
            target = target[factory["key"]]
        assert callable(target), entry.id
    assert any(r.startswith("CoolProp") for r in extras["coolprop"])


def test_e_f1_3_unit_payloads_are_the_list_models_entries(registry: Registry) -> None:
    from openflowsheet.application.revision_binding import MODEL_BUILDERS

    listed = {
        model["model_id"]: model
        for model in LocalApplication.in_memory().list_models().as_document()["models"]
    }
    assert len(listed) == 30
    for entry in registry.descriptors(("unit_model",)):
        payload = entry.payload
        assert payload["family"] == entry.id.split(".")[0]
        if entry.id == CASCADE:
            assert payload == {"family": "syn001", "bindable": False, "signature": None}
            assert entry.document["implementation"] == {"modules": [], "factory": None}
            continue
        assert payload["bindable"] is True
        assert payload["signature"] == listed[entry.id]
        assert entry.document["implementation"]["factory"] == {
            "module": "openflowsheet.application.revision_binding",
            "attribute": "MODEL_BUILDERS",
            "key": entry.id,
        }
        assert entry.id in MODEL_BUILDERS


def test_every_legacy_descriptor_is_released_core_and_builtin(registry: Registry) -> None:
    for entry in registry.descriptors():
        assert (entry.status, entry.effective_status, entry.evidence_class) == (
            "released",
            "released",
            "core",
        )
        assert (entry.origin, entry.stability, entry.version) == ("builtin", "core", "1.0.0")
        assert entry.evidence_notices() == () and entry.unresolved == ()


# ---------------------------------------------------------------------------------------------
# E-F1-4 Self-hash


def _independent_self_sha(root: Path, modules: Sequence[str]) -> str:
    rows = [
        [path, hashlib.sha256((root / path).read_bytes().replace(b"\r\n", b"\n")).hexdigest()]
        for path in sorted(modules)
    ]
    return hashlib.sha256(json.dumps(rows, separators=(",", ":")).encode()).hexdigest()


def test_e_f1_4_the_implementation_sets_are_f0s_m9_set(registry: Registry) -> None:
    union = {
        "src/" + path
        for entry in registry.descriptors(("property_method", "unit_model"))
        for path in entry.document["implementation"]["modules"]
    }
    frozen = set(corpus_identity.frozen_modules())
    assert len(frozen) == 35
    assert union == frozen, f"only in the registry: {sorted(union - frozen)}; " + (
        f"only in M9: {sorted(frozen - union)}"
    )


def _declarers() -> dict[str, set[str]]:
    """Model id -> the M9 modules under `models/` that declare it as `MODEL_ID` or in
    `MODEL_IDS` (F0's rule, R-940), each module imported by its own path. D6's two exceptions:
    `c1.reactor_surrogate`, which no file declares, takes the files of `c1.reactor` (R-301), and
    `syn001.cascade` (not in M9) takes none."""
    found: dict[str, set[str]] = {CASCADE: set()}
    for path in corpus_identity.frozen_modules():
        if not path.startswith("src/openflowsheet/models/"):
            continue
        module = importlib.import_module(path[len("src/") : -len(".py")].replace("/", "."))
        declared = {getattr(module, "MODEL_ID", None), *getattr(module, "MODEL_IDS", ())}
        for model in declared - {None}:
            found.setdefault(str(model), set()).add(path[len("src/") :])
    assert "c1.reactor_surrogate" not in found
    found["c1.reactor_surrogate"] = found["c1.reactor"]
    return found


def _attribution_problems(
    modules: Mapping[tuple[str, str], Sequence[str]], declarers: Mapping[str, set[str]]
) -> list[str]:
    """The descriptors whose `modules` miss the file that holds their code: a method's provider
    class file, a unit's declaring M9 module(s)."""
    problems = []
    providers = {name: built[0] for name, built in _constructed().items()}
    for (kind, identifier), held in sorted(modules.items()):
        if kind == "property_method":
            source = Path(inspect.getfile(type(providers[identifier]))).resolve()
            expected = {source.relative_to(SOURCE.resolve()).as_posix()}
        else:
            expected = declarers[identifier]
        if not expected <= set(held):
            problems.append(f"{kind} {identifier}: {sorted(expected - set(held))}")
    return problems


def test_e_f1_4_each_descriptor_holds_its_own_modules(registry: Registry) -> None:
    """F1 review SF-6: the union check above cannot see a swap between two descriptors; this
    pins each descriptor's own file, and a swap of `pr-c1-v1`'s and `pr-lib-v1`'s sets fails."""
    modules = {
        (entry.kind, entry.id): entry.document["implementation"]["modules"]
        for entry in registry.descriptors(("property_method", "unit_model"))
    }
    declarers = _declarers()
    assert len(modules) == 38
    assert _attribution_problems(modules, declarers) == []
    assert all(declarers[i] for k, i in modules if k == "unit_model" and i != CASCADE)
    assert modules[("unit_model", CASCADE)] == []
    swapped = dict(modules)
    c1, lib = ("property_method", "pr-c1-v1"), ("property_method", "pr-lib-v1")
    swapped[c1], swapped[lib] = modules[lib], modules[c1]
    assert [problem.split(":")[0] for problem in _attribution_problems(swapped, declarers)] == [
        "property_method pr-c1-v1",
        "property_method pr-lib-v1",
    ]


def test_e_f1_4_every_self_hash_recomputes(registry: Registry) -> None:
    for entry in registry.descriptors():
        modules = entry.document["implementation"]["modules"]
        assert entry.self_sha256 == _independent_self_sha(SOURCE, modules), entry.id


def test_e_f1_4_a_crlf_copy_hashes_the_same(registry: Registry, tmp_path: Path) -> None:
    entry = registry.resolve("property_method", "wilson-ig-v2")
    modules = entry.document["implementation"]["modules"]
    for path in modules:
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        original = (SOURCE / path).read_bytes()
        assert b"\r\n" not in original
        target.write_bytes(original.replace(b"\n", b"\r\n"))
        assert target.read_bytes() != original
    assert len(modules) == 2
    assert self_sha256(tmp_path, modules) == entry.self_sha256


# ---------------------------------------------------------------------------------------------
# The generator, the legacy form, the process registry


def test_the_generator_check_is_clean(capsys: pytest.CaptureFixture[str]) -> None:
    assert registry_builtin.main(["--check"]) == 0
    (line,) = capsys.readouterr().out.splitlines()
    assert line.startswith("registry_builtin --check: clean, 42 descriptors in 2 tables")


def test_the_generator_check_reports_a_changed_table_by_pointer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    table = legacy.table()
    _row(table, "syn001")["title"] = "Edited by hand"
    changed = tmp_path / "legacy.json"
    changed.write_text(registry_builtin.render(table), encoding="utf-8")
    monkeypatch.setattr(registry_builtin, "TABLE", changed)
    assert registry_builtin.main(["--check"]) == 1
    (line,) = capsys.readouterr().out.splitlines()
    index = [row["id"] for row in table].index("syn001")
    assert line.endswith(f"differs at 1 pointer(s): /{index}/title")


def test_the_generator_never_reads_model_bases() -> None:
    """D6: the family table is independent of `MODEL_BASES`, so E-F1-1 is not circular."""
    tree = ast.parse((REPO_ROOT / "scripts" / "registry_builtin.py").read_text(encoding="utf-8"))
    names = {
        *(node.id for node in ast.walk(tree) if isinstance(node, ast.Name)),
        *(node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)),
        *(
            a.name
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
            for a in node.names
        ),
    }
    assert "MODEL_BASES" not in names and "MODEL_BUILDERS" not in names


def test_the_legacy_payloads_apply_to_the_legacy_table_only() -> None:
    table = legacy.table()
    other_kind = _extension("functional_contributor", "legacy-cost", status="released")
    signed = _row(table, CASCADE) | {
        "payload": {
            "family": "syn001",
            "bindable": False,
            "signature": _row(table, "syn001.valve")["payload"]["signature"],
        }
    }
    for rows, pointer in (
        ([*table, other_kind], "/kind"),
        ([signed if row["id"] == CASCADE else row for row in table], "/payload/signature"),
    ):
        with pytest.raises(RegistryBuildError) as raised:
            _build(rows)
        assert raised.value.reason.code == "extension_invalid"
        assert dict(raised.value.reason.params)["pointer"] == pointer
    method = _extension("property_method", "acme.v2", provides=["conn:nTP-v1"], payload={"v": 2})
    built = _build(packages=[_package("acme", [method])])
    entry = built.resolve("property_method", "acme.v2")
    assert (entry.stability, built.quarantined) == ("preview", ())


def test_default_registry_is_built_once_and_closed(registry: Registry) -> None:
    seen: list[Registry] = []
    threads = [threading.Thread(target=lambda: seen.append(default_registry())) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    first = default_registry()
    assert all(found is first for found in seen) and len(seen) == 8
    assert first.closed
    # The process registry holds every built-in table (F1-WO3: `core.json` too), the legacy one
    # unchanged, and no extension in this environment.
    assert first.descriptors(("unit_model", "property_method", "connection_definition")) == (
        registry.descriptors(("unit_model", "property_method", "connection_definition"))
    )
    assert isinstance(first.resolve("unit_model", "syn001.tp_flash"), Registered)
    with pytest.raises(RuntimeError, match="registry_closed"):
        first.register(first.resolve("unit_model", "syn001.tp_flash"))
