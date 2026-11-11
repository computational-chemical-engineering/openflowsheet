"""F1-WO3 (ADR 0060 D7, D8, D9): discovery and integration, exit tests E-F1-6, E-F1-7, E-F1-12.

Every extension here is a fake distribution (`tests/f1_harness.py`) in a temporary directory, read
through `importlib.metadata` like an installed one. Built-ins are the real tables
(`registry/builtin/*.json`).

- **E-F1-6** Discovery: three permutations give byte-identical snapshots; a namespace declared by
  two distributions quarantines both, one distribution seen twice does not; a reserved namespace,
  a raising callable, a schema violation, an unknown static token and a missing self-hash file
  each quarantine exactly their package with the stated code, and the build completes; a unit
  requiring `conn:nTP-v1 | conn:acme.slurry` without `acme` is admitted with the notice
  `capability_unresolved(conn:acme.slurry)`. Also: message catalogues and limitation codes.
- **E-F1-7** Closing and MSG: `register` after build raises; an extension's entries resolve
  through `explain`; a lookup before any explicit build sees them; a lookup during build raises
  (the process paths in fresh interpreters, so this process's frozen catalogue never matters).
- **E-F1-12** Contributors: an extension `functional_contributor` is registered and listed
  `preview`; E01's `_REGISTERED` is unchanged; the built-in three are listed `core`.
- Factory resolution (W2-5), the usage recorder and the extensions-used record (D8, D9), and the
  generator's `--write` with no usable table (W2-7).
"""

from __future__ import annotations

import contextvars
import hashlib
import importlib.metadata
import importlib.util
import json
import os
import subprocess
import sys
import textwrap
import threading
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from conftest import REPO_ROOT
from f1_harness import FakeSite, descriptor

import openflowsheet.registry as registry_module
from openflowsheet.canonical import canonical_json
from openflowsheet.messages.catalogue import Catalogue
from openflowsheet.registry import (
    Coded,
    FactoryRefusedError,
    Registry,
    current_platform,
    discovery,
    usage,
)

sys.path.insert(0, str(REPO_ROOT / "scripts"))
import registry_builtin  # noqa: E402

SOURCE = REPO_ROOT / "src"
CATALOGUE_YAML = """\
catalogue: openflowsheet-messages-v1
namespace: {namespace}
entries:
  - code: {namespace}.slurry_refused
    family: refusal
    kind: input
    complete: false
    title: Slurry refused
    summary: A slurry was refused.
"""


@pytest.fixture
def site(tmp_path: Path) -> Iterator[FakeSite]:
    registry_module.default_registry()  # built before any fake site is on `sys.path`
    fake = FakeSite(tmp_path)
    try:
        yield fake
    finally:
        fake.close()


def _build(site: FakeSite, **kwargs: Any) -> Registry:
    return Registry.build(
        builtin_tables=discovery.builtin_tables(), entry_points=site.entry_points(), **kwargs
    )


def _quarantined(registry: Registry) -> dict[str, tuple[str, dict[str, str]]]:
    return {
        row.distribution: (row.reason.code, dict(row.reason.params)) for row in registry.quarantined
    }


def _installed(registry: Registry) -> set[str]:
    return {entry.id for entry in registry.descriptors() if entry.origin != "builtin"}


def _unit(identifier: str, **fields: Any) -> dict[str, Any]:
    fields.setdefault("requires", [["conn:nTP-v1"]])
    return descriptor("unit_model", identifier, **fields)


def _installed_extra(*modules: str) -> bool:
    """Whether an extra of the installed `openflowsheet` counts as present: every one of its
    `modules` imports, or no distribution metadata names its requirements (F1 review SF-3)."""
    try:
        importlib.metadata.metadata("openflowsheet")
    except importlib.metadata.PackageNotFoundError:
        return True
    return all(importlib.util.find_spec(module) is not None for module in modules)


def _good(site: FakeSite, namespace: str = "good") -> None:
    module = site.module_name(namespace)
    site.add(
        f"{namespace}-dist",
        namespace,
        [
            _unit(
                f"{namespace}.unit",
                implementation={"modules": [f"{module}/kernel.py"], "factory": None},
            )
        ],
        files={"kernel.py": "VALUE = 1\n"},
    )


# ---------------------------------------------------------------------------------------------
# E-F1-6 Discovery


def test_e_f1_6_three_permutations_give_byte_identical_snapshots(site: FakeSite) -> None:
    for namespace in ("alpha", "beta", "gamma"):
        _good(site, namespace)
    site.add("broken-dist", "broken", body="def package():\n    raise ValueError('boom')\n")
    found = list(site.entry_points())
    assert len(found) == 4
    snapshots = {
        canonical_json(
            Registry.build(builtin_tables=discovery.builtin_tables(), entry_points=order).snapshot()
        )
        for order in (found, found[::-1], found[1:] + found[:1])
    }
    assert len(snapshots) == 1
    (snapshot,) = snapshots
    document = json.loads(snapshot)
    assert {row["id"] for row in document["extensions"] if row["origin"] != "builtin"} == {
        "alpha.unit",
        "beta.unit",
        "gamma.unit",
    }
    assert [row["code"] for row in document["quarantined"]] == ["extension_load_failed"]


def test_e_f1_6_a_namespace_of_two_distributions_quarantines_both(site: FakeSite) -> None:
    site.add("acme-one", "acme", [_unit("acme.one")], module="acme_one_" + site.module_name("x"))
    site.add("acme-two", "acme", [_unit("acme.two")], module="acme_two_" + site.module_name("x"))
    _good(site)
    built = _build(site)
    conflict = ("namespace_conflict", {"namespace": "acme"})
    assert _quarantined(built) == {"acme-one": conflict, "acme-two": conflict}
    assert _installed(built) == {"good.unit"}


def test_e_f1_6_one_distribution_seen_twice_is_deduplicated(site: FakeSite) -> None:
    module = site.module_name("twice")
    for directory in (0, 1):
        site.add("Twice_Dist", "twice", [_unit("twice.unit")], module=module, directory=directory)
    assert len(site.entry_points()) == 2
    built = _build(site)
    assert (built.quarantined, _installed(built)) == ((), {"twice.unit"})
    entry = built.resolve("unit_model", "twice.unit")
    assert (entry.distribution, entry.entry_point, entry.origin) == (
        "twice-dist",
        "twice",
        "installed",
    )


def test_e_f1_6_each_bad_package_is_quarantined_alone_and_the_build_completes(
    site: FakeSite,
) -> None:
    _good(site)
    site.add("std-dist", "std", [_unit("std.unit")])
    site.add("syn-dist", "syn001", [_unit("syn001.extra")])
    site.add("raises-dist", "raises", body="def package():\n    raise RuntimeError('no')\n")
    site.add("schema-dist", "schema", [_unit("schema.unit", title="")])
    site.add("token-dist", "token", [_unit("token.unit", requires=[["flash:XY"]])])
    site.add(
        "hash-dist",
        "hashed",
        [_unit("hashed.unit", implementation={"modules": ["absent/kernel.py"], "factory": None})],
    )
    site.add("named-dist", "named", [_unit("named.unit")], document_namespace="other")
    built = _build(site)
    assert _quarantined(built) == {
        "std-dist": ("reserved_namespace", {"namespace": "std"}),
        "syn-dist": ("reserved_namespace", {"namespace": "syn001"}),
        "raises-dist": ("extension_load_failed", {"entry_point": "raises"}),
        "schema-dist": (
            "extension_invalid",
            {"entry_point": "schema", "pointer": "/descriptors/0/title"},
        ),
        "token-dist": ("capability_unknown", {"token": "flash:XY"}),
        "hash-dist": ("self_hash_unavailable", {"id": "hashed.unit", "path": "absent/kernel.py"}),
        "named-dist": ("extension_invalid", {"entry_point": "named", "pointer": "/namespace"}),
    }
    assert _installed(built) == {"good.unit"} and built.closed
    assert built.resolve("unit_model", "good.unit").self_sha256 != hashlib.sha256(b"[]").hexdigest()


@pytest.mark.skipif(
    sys.platform == "win32" or os.geteuid() == 0, reason="mode 000 does not stop this reader"
)
def test_a_module_file_it_cannot_read_quarantines_its_package(site: FakeSite) -> None:
    """F1 review SF-2: an unreadable module file (mode 000) is `self_hash_unavailable` for its
    package, never a build failure (D7: a broken extension is never fatal)."""
    _good(site)
    module = site.module_name("locked")
    site.add(
        "locked-dist",
        "locked",
        [
            _unit(
                "locked.unit",
                implementation={"modules": [f"{module}/kernel.py"], "factory": None},
            )
        ],
        files={"kernel.py": "VALUE = 1\n"},
    )
    kernel = site.directory() / module / "kernel.py"
    kernel.chmod(0)
    try:
        built = _build(site)
    finally:
        kernel.chmod(0o644)
    assert _quarantined(built) == {
        "locked-dist": (
            "self_hash_unavailable",
            {"id": "locked.unit", "path": f"{module}/kernel.py"},
        )
    }
    assert _installed(built) == {"good.unit"} and built.closed


def test_an_unexpected_failure_in_a_package_quarantines_it_alone(
    site: FakeSite, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """F1 review SF-2: an exception no check anticipates, raised while a package is added,
    quarantines that package `extension_invalid(<entry point>, "")` with the class logged."""
    _good(site)
    site.add("odd-dist", "odd", [_unit("odd.unit")])
    original = registry_module._registered

    def registered(document: Any, *args: Any) -> Any:
        if str(document["id"]).startswith("odd."):
            raise LookupError("unforeseen")
        return original(document, *args)

    monkeypatch.setattr(registry_module, "_registered", registered)
    with caplog.at_level("WARNING", logger="openflowsheet.registry"):
        built = _build(site)
    assert _quarantined(built) == {
        "odd-dist": ("extension_invalid", {"entry_point": "odd", "pointer": ""})
    }
    assert _installed(built) == {"good.unit"} and built.closed
    assert "LookupError" in caplog.text and "unforeseen" not in caplog.text


def test_a_distribution_whose_metadata_cannot_be_read_is_skipped(
    site: FakeSite, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """F1 review SF-2: a distribution on the path whose metadata raises names no entry point to
    quarantine; it is skipped with its class logged, and discovery of the others completes."""

    class Unreadable:
        @property
        def metadata(self) -> Any:
            raise PermissionError("metadata")

    _good(site)
    distributions = discovery.importlib.metadata.distributions

    def with_unreadable(**kwargs: Any) -> list[Any]:
        return [Unreadable(), *distributions(**kwargs)]

    monkeypatch.setattr(discovery.importlib.metadata, "distributions", with_unreadable)
    with caplog.at_level("WARNING", logger="openflowsheet.registry"):
        built = _build(site)
    assert (built.quarantined, _installed(built)) == ((), {"good.unit"})
    assert "PermissionError" in caplog.text


def test_e_f1_6_an_unresolved_alternative_is_admitted_with_a_notice(site: FakeSite) -> None:
    site.add(
        "beta-dist", "beta", [_unit("beta.unit", requires=[["conn:nTP-v1", "conn:acme.slurry"]])]
    )
    built = _build(site)
    verdict = built.admit("beta.unit", "syn001", "nTP-v1")
    assert verdict.admitted and verdict.refusal is None
    assert Coded("capability_unresolved", {"token": "conn:acme.slurry"}) in verdict.notices
    assert built.resolve("unit_model", "beta.unit").unresolved == ("conn:acme.slurry",)


def test_message_catalogues_and_limitation_codes_are_validated(site: FakeSite) -> None:
    def entries(namespace: str, path: str = "messages.yaml") -> dict[str, Any]:
        module = site.module_name(namespace)
        return descriptor(
            "message_entries",
            f"{namespace}.messages",
            payload={"catalogue": {"package": module, "path": path}},
        )

    own = {"code": "slurry.slurry_refused", "params": {}}
    core = {"code": "model_unsupported", "params": {"model": "x"}}
    site.add(
        "slurry-dist",
        "slurry",
        [_unit("slurry.unit", limitations=[own, core]), entries("slurry")],
        files={"messages.yaml": CATALOGUE_YAML.format(namespace="slurry")},
    )
    site.add(
        "wrongns-dist",
        "wrongns",
        [entries("wrongns")],
        files={"messages.yaml": CATALOGUE_YAML.format(namespace="slurry")},
    )
    site.add("nofile-dist", "nofile", [entries("nofile", "absent.yaml")])
    site.add(
        "limit-dist",
        "limit",
        [_unit("limit.unit", limitations=[core, {"code": "limit.unknown", "params": {}}])],
    )
    registered: list[tuple[str, dict[str, Any]]] = []
    built = _build(
        site, catalogue_register=lambda d, *, namespace: registered.append((namespace, d))
    )
    catalogue_pointer = "/descriptors/0/payload/catalogue"
    assert _quarantined(built) == {
        "wrongns-dist": (
            "extension_invalid",
            {"entry_point": "wrongns", "pointer": catalogue_pointer},
        ),
        "nofile-dist": (
            "extension_invalid",
            {"entry_point": "nofile", "pointer": catalogue_pointer},
        ),
        "limit-dist": (
            "extension_invalid",
            {"entry_point": "limit", "pointer": "/descriptors/0/limitations/1/code"},
        ),
    }
    assert _installed(built) == {"slurry.unit", "slurry.messages"}
    assert [(namespace, [e["code"] for e in d["entries"]]) for namespace, d in registered] == [
        ("slurry", ["slurry.slurry_refused"])
    ]


# ---------------------------------------------------------------------------------------------
# E-F1-7 Closing and MSG


def test_e_f1_7_register_after_build_raises_and_entries_reach_the_catalogue(
    site: FakeSite,
) -> None:
    site.add(
        "slurry-dist",
        "slurry",
        [
            descriptor(
                "message_entries",
                "slurry.messages",
                payload={"catalogue": {"package": site.module_name("slurry"), "path": "m.yaml"}},
            )
        ],
        files={"m.yaml": CATALOGUE_YAML.format(namespace="slurry")},
    )
    catalogue = Catalogue()
    built = _build(site, catalogue_register=catalogue.register)
    with pytest.raises(RuntimeError, match="registry_closed"):
        built.register(built.resolve("message_entries", "slurry.messages"))
    entry = catalogue.entry("slurry.slurry_refused")
    assert entry is not None and entry.namespace == "slurry"


def test_e_f1_7_a_catalogue_lookup_on_a_building_thread_raises(site: FakeSite) -> None:
    site.add(
        "peek-dist",
        "peek",
        body=textwrap.dedent(
            """\
            SEEN = []


            def package():
                from openflowsheet.registry import before_catalogue_freeze

                try:
                    before_catalogue_freeze()
                except RuntimeError as error:
                    SEEN.append(str(error))
                return {"package_format": "openflowsheet-extension-package-v1",
                        "namespace": "peek", "descriptors": []}
            """
        ),
    )
    built = _build(site)
    assert built.quarantined == ()
    assert sys.modules[site.module_name("peek")].SEEN == ["catalogue lookup during registry build"]


def _fresh(site: FakeSite, script: str) -> dict[str, Any]:
    """Run `script` in a fresh interpreter with the fake site on its path; it prints JSON."""
    environment = dict(os.environ)
    environment["PYTHONPATH"] = os.pathsep.join(
        [*(str(path) for path in site.directories), str(SOURCE)]
    )
    done = subprocess.run(
        [sys.executable, "-c", textwrap.dedent(script)],
        capture_output=True,
        text=True,
        env=environment,
        check=False,
        timeout=300,
    )
    assert done.returncode == 0, done.stderr[-2000:]
    found: dict[str, Any] = json.loads(done.stdout.splitlines()[-1])
    return found


def _slurry_with_peek(site: FakeSite) -> None:
    module = site.module_name("slurry")
    reference = {"catalogue": {"package": module, "path": "m.yaml"}}
    spelled = json.dumps(
        json.dumps(descriptor("message_entries", "slurry.messages", payload=reference))
    )
    body = textwrap.dedent(
        f"""\
        import json
        from pathlib import Path

        SEEN = []


        def package():
            from openflowsheet.messages.catalogue import CATALOGUE

            try:
                CATALOGUE.entry("model_unsupported")
            except RuntimeError as error:
                SEEN.append(str(error))
            return {{"package_format": "openflowsheet-extension-package-v1",
                    "namespace": "slurry",
                    "descriptors": [json.loads({spelled})]}}
        """
    )
    site.add(
        "slurry-dist",
        "slurry",
        body=body,
        files={"m.yaml": CATALOGUE_YAML.format(namespace="slurry")},
    )


def test_e_f1_7_a_lookup_before_any_build_sees_extension_entries(site: FakeSite) -> None:
    _slurry_with_peek(site)
    found = _fresh(
        site,
        f"""
        import json, sys
        from openflowsheet.messages.catalogue import CATALOGUE
        import openflowsheet.registry as registry

        assert registry._process_registry is None
        entry = CATALOGUE.entry("slurry.slurry_refused")
        built = registry._process_registry
        print(json.dumps({{
            "entry": entry is not None and entry.namespace,
            "built": built is not None and built.closed,
            "seen": sys.modules["{site.module_name("slurry")}"].SEEN,
            "quarantined": [q.as_document() for q in built.quarantined],
        }}))
        """,
    )
    assert found == {
        "entry": "slurry",
        "built": True,
        "seen": ["catalogue lookup during registry build"],
        "quarantined": [],
    }


def test_e_f1_7_an_extensions_entry_resolves_through_explain(site: FakeSite) -> None:
    _slurry_with_peek(site)
    found = _fresh(
        site,
        """
        import json
        from openflowsheet.application.local import LocalApplication

        with LocalApplication.in_memory() as application:
            entry = application.explain("slurry.slurry_refused").as_document()
        print(json.dumps({"code": entry["code"], "title": entry["title"]}))
        """,
    )
    assert found == {"code": "slurry.slurry_refused", "title": "Slurry refused"}


# ---------------------------------------------------------------------------------------------
# E-F1-12 Contributors


def test_e_f1_12_an_extension_contributor_is_listed_preview_and_never_reaches_e01(
    site: FakeSite,
) -> None:
    from openflowsheet.assessment import program

    program._registered()  # E01's own three, imported as E01 imports them
    before = dict(program._REGISTERED)
    site.add("water-dist", "water", [descriptor("functional_contributor", "water.footprint")])
    built = _build(site)
    entry = built.resolve("functional_contributor", "water.footprint")
    assert (entry.stability, entry.evidence_class, entry.origin) == (
        "preview",
        "unreviewed",
        "installed",
    )
    listed = {e.id: e.stability for e in built.descriptors(("functional_contributor",))}
    assert listed == {
        "cost": "core",
        "lca": "core",
        "derived": "core",
        "water.footprint": "preview",
    }
    assert program._REGISTERED == before and set(before) == set(program.CONTRIBUTOR_ORDER)
    for name in program.CONTRIBUTOR_ORDER:
        builtin = built.resolve("functional_contributor", name)
        assert builtin.evidence_class == "core"
        assert built.factory("functional_contributor", name) is before[name]
    assert program._REGISTERED == before


def test_the_lca_contributor_resolves_without_brightway(monkeypatch: pytest.MonkeyPatch) -> None:
    """F1-WO6 F-4: E01's `LcaContributor` runs without the `lca` extra (Brightway serves only the
    offline adapter), so its descriptor names no `pip_extra` and its factory resolves."""
    from openflowsheet.assessment import program
    from openflowsheet.assessment.lca.section import LcaContributor

    program._registered()
    monkeypatch.setitem(sys.modules, "bw2data", None)
    monkeypatch.setitem(sys.modules, "bw2calc", None)
    built = Registry.build(builtin_tables=discovery.builtin_tables())
    factory = built.factory("functional_contributor", "lca")
    assert factory is LcaContributor and factory is program._REGISTERED["lca"]


# ---------------------------------------------------------------------------------------------
# Factory resolution, usage, extensions used


@pytest.fixture(scope="module")
def builtins() -> Registry:
    return Registry.build(builtin_tables=discovery.builtin_tables())


def test_factory_resolution_of_the_legacy_built_ins(builtins: Registry) -> None:
    from openflowsheet.application import revision_binding

    refused = {}
    for entry in builtins.descriptors(("property_method", "unit_model")):
        try:
            found = builtins.factory(entry.kind, entry.id)
        except FactoryRefusedError as error:
            refused[entry.id] = error.reason
            continue
        expected = (
            revision_binding.basis_provider
            if entry.kind == "property_method"
            else revision_binding.MODEL_BUILDERS[entry.id]
        )
        assert found is expected, entry.id
    # Without CoolProp installed, its method is refused before its factory (F1 review SF-3).
    coolprop = (
        {}
        if _installed_extra("CoolProp")
        else {
            "coolprop-heos-v1": Coded(
                "dependency_missing", {"id": "coolprop-heos-v1", "extra": "coolprop"}
            )
        }
    )
    assert refused == {
        **coolprop,
        "pr-lib-v1": Coded("factory_unavailable", {"kind": "property_method", "id": "pr-lib-v1"}),
        "wilson-ig-v1": Coded(
            "factory_unavailable", {"kind": "property_method", "id": "wilson-ig-v1"}
        ),
        "syn001.cascade": Coded(
            "factory_unavailable", {"kind": "unit_model", "id": "syn001.cascade"}
        ),
    }


def test_factory_refuses_platform_and_dependency(site: FakeSite) -> None:
    module = site.module_name("needs")
    elsewhere = sorted(
        {"linux-x86_64", "linux-aarch64", "windows-x86_64", "macos-arm64"} - {current_platform()}
    )
    site.add(
        "needs-dist",
        "needs",
        [
            _unit(
                "needs.platform",
                platforms=elsewhere,
                implementation={
                    "modules": [],
                    "factory": {"module": f"{module}.kernel", "attribute": "BUILD", "key": None},
                },
            ),
            _unit(
                "needs.extra",
                pip_extra="needs-extra",
                implementation={
                    "modules": [],
                    "factory": {"module": f"{module}.missing", "attribute": "BUILD", "key": None},
                },
            ),
            _unit(
                "needs.keyed",
                implementation={
                    "modules": [],
                    "factory": {"module": f"{module}.kernel", "attribute": "TABLE", "key": "b"},
                },
            ),
        ],
        files={
            "kernel.py": "BUILD = object()\nTABLE = {'a': 1, 'b': 2}\n",
            "missing.py": "import needs_absent_dependency_x\n",
        },
    )
    built = _build(site)
    with pytest.raises(FactoryRefusedError) as raised:
        built.factory("unit_model", "needs.platform")
    assert raised.value.reason == Coded(
        "platform_unsupported", {"id": "needs.platform", "platform": current_platform()}
    )
    with pytest.raises(FactoryRefusedError) as raised:
        built.factory("unit_model", "needs.extra")
    assert raised.value.reason == Coded(
        "dependency_missing", {"id": "needs.extra", "extra": "needs-extra"}
    )
    assert built.factory("unit_model", "needs.keyed") == 2


def test_a_missing_extra_is_dependency_missing_before_the_factory_returns(
    builtins: Registry, monkeypatch: pytest.MonkeyPatch
) -> None:
    """F1 review SF-3: `coolprop-heos-v1`'s factory module imports CoolProp lazily, so an import
    check alone returned `basis_provider` without CoolProp. The extra's requirements, read from
    the declaring distribution's metadata, are checked first."""
    try:
        importlib.metadata.metadata("openflowsheet")
    except importlib.metadata.PackageNotFoundError:
        pytest.skip("openflowsheet is not installed: no metadata names the extra's requirements")
    distribution = importlib.metadata.distribution

    def masked(name: str) -> importlib.metadata.Distribution:
        if discovery.normalised_name(name) == "coolprop":
            raise importlib.metadata.PackageNotFoundError(name)
        return distribution(name)

    monkeypatch.setattr(importlib.metadata, "distribution", masked)
    monkeypatch.setitem(sys.modules, "CoolProp", None)
    with pytest.raises(FactoryRefusedError) as raised:
        builtins.factory("property_method", "coolprop-heos-v1")
    assert raised.value.reason == Coded(
        "dependency_missing", {"id": "coolprop-heos-v1", "extra": "coolprop"}
    )
    from openflowsheet.application import revision_binding

    assert builtins.factory("property_method", "iapws95-v1") is revision_binding.basis_provider


def test_the_usage_recorder_records_resolve_and_factory_in_its_context(builtins: Registry) -> None:
    builtins.resolve("unit_model", "syn001.valve")  # no record active: nothing to record
    with usage() as record:
        builtins.resolve("unit_model", "syn001.valve")
        builtins.factory("unit_model", "syn001.tp_flash")
        builtins.admit("syn001.liquid_pump", "pr-c1-v1", "nTP-v1")  # a query, not a use
        builtins.extensions_used([("property_method", "iapws95-v1", None)])  # derived, not used
        outside: list[object] = []
        thread = threading.Thread(target=lambda: builtins.resolve("property_method", "syn001"))
        thread.start()
        thread.join()
        copied = contextvars.copy_context()
        worker = threading.Thread(
            target=lambda: outside.append(
                copied.run(builtins.resolve, "property_method", "pr-c1-v1")
            )
        )
        worker.start()
        worker.join()
        with usage() as inner:
            builtins.resolve("connection_definition", "nTP-v1")
    assert record.sorted() == (
        ("property_method", "pr-c1-v1", "1.0.0"),
        ("unit_model", "syn001.tp_flash", "1.0.0"),
        ("unit_model", "syn001.valve", "1.0.0"),
    )
    assert inner.sorted() == (("connection_definition", "nTP-v1", "1.0.0"),)


def test_extensions_used_carry_the_d9_flag(site: FakeSite) -> None:
    _good(site)
    built = _build(site)
    used = built.extensions_used(
        [
            ("unit_model", "good.unit", None),
            ("unit_model", "syn001.valve", "1.0.0"),
            ("property_method", "syn001", None),
            ("functional_contributor", "cost", None),
            ("unit_model", "absent.unit", None),
            ("unit_model", "good.unit", "1.0.0"),
        ]
    )
    assert [(row["kind"], row["id"], row["evidence_class"]) for row in used.rows()] == [
        ("functional_contributor", "cost", "core"),
        ("property_method", "syn001", "core"),
        ("unit_model", "good.unit", "unreviewed"),
        ("unit_model", "syn001.valve", "core"),
    ]
    assert used.unregistered == (("unit_model", "absent.unit", None),)
    assert used.notices() == (
        Coded("extension_unreviewed", {"id": "good.unit", "origin": "installed"}),
        Coded("preview_kind", {"kind": "unit_model", "id": "good.unit"}),
    )


# ---------------------------------------------------------------------------------------------
# The generator with no usable table (W2-7) and the process registry


def test_the_generator_writes_without_building_the_process_registry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def refuse() -> None:
        raise AssertionError("the generator built the process registry")

    monkeypatch.setattr(registry_module, "_process_registry", None)
    monkeypatch.setattr(registry_module.discovery, "builtin_tables", refuse)
    legacy, core = tmp_path / "legacy.json", tmp_path / "core.json"
    monkeypatch.setattr(registry_builtin, "TABLE", legacy)
    monkeypatch.setattr(registry_builtin, "CORE_TABLE", core)
    record, constant = tmp_path / "tables.sha256", tmp_path / "builtin-sha256.txt"
    monkeypatch.setattr(registry_builtin, "DIGEST_RECORD", record)
    monkeypatch.setattr(registry_builtin, "CONSTANT", constant)
    assert registry_builtin.write() == 0
    builtin = SOURCE / "openflowsheet" / "registry" / "builtin"
    assert legacy.read_bytes() == (builtin / "legacy.json").read_bytes()
    assert core.read_bytes() == (builtin / "core.json").read_bytes()
    assert record.read_bytes() == (builtin / "tables.sha256").read_bytes()
    fixture = REPO_ROOT / "tests" / "fixtures" / "registry" / "builtin-sha256.txt"
    assert constant.read_bytes() == fixture.read_bytes()


def test_the_generators_signatures_are_list_models() -> None:
    from openflowsheet.application.local import LocalApplication

    with LocalApplication.in_memory() as application:
        models = application.list_models().as_document()["models"]
    assert registry_builtin._signatures() == models


def test_the_process_registry_holds_every_builtin_table() -> None:
    built = registry_module.default_registry()
    assert (
        built.registry_sha256
        == Registry.build(builtin_tables=discovery.builtin_tables()).registry_sha256
    )
    assert {e.id for e in built.descriptors(("functional_contributor",))} == {
        "cost",
        "lca",
        "derived",
    }


def test_the_generator_refuses_a_core_kind_without_a_payload_schema(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """F1-WO6 F-5: a built-in descriptor of a core kind (ADR 0060 D1) whose payload schema is not
    installed is refused by `--write` and `--check`, one line per descriptor, exit 1."""
    committed = {path.stem: rows for path, rows in registry_builtin.tables().items()}
    assert registry_builtin.payload_schema_problems(committed) == []
    synthetic = {"records": [descriptor("record_type", "syn.record")]}
    assert registry_builtin.payload_schema_problems(synthetic) == [
        "built-in records/record_type/syn.record: kind record_type is core (ADR 0060 D1) but its "
        "payload schema is not installed"
    ]
    monkeypatch.setattr(
        registry_builtin, "tables", lambda: {Path("records.json"): synthetic["records"]}
    )
    for mode in ("--write", "--check"):
        assert registry_builtin.main([mode]) == 1
        assert capsys.readouterr().out.splitlines() == [
            "built-in records/record_type/syn.record: kind record_type is core (ADR 0060 D1) but "
            "its payload schema is not installed"
        ]
