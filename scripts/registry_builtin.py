"""F1-WO2, F1-WO3 (ADR 0060 D6, D7): the built-in tables, generated from the code they describe.

    python scripts/registry_builtin.py --write   # writes the tables
    python scripts/registry_builtin.py --check   # regenerates them in memory and compares

The tables are package data under `src/openflowsheet/registry/builtin/`: `legacy.json` (D6) and
`core.json` (D7: the E01 contributors). `--check` fails with the JSON pointers at which a
committed table differs from the regenerated one.

Each prints one summary line and exits 0 only on success. `--check` also builds a registry from
the committed tables, so a table the registry would refuse fails it. `--write` never builds the
process registry, so it runs with a stale or missing table (signatures come from the binder's
tables through `local._model_view`, the function `list_models` maps them with).

The table holds D6's 39 legacy descriptors: the connection definition `nTP-v1`, the 7 legacy
property methods and the 31 legacy units. What the generator reads:

- **methods**: a constructed provider's `describe()` (through the binder's `basis_provider` for
  each selectable basis, CoolProp once per fluid; `pr-lib-v1` and `wilson-ig-v1`, which no basis
  selects, by their own constructors), the provider module's `PROVIDER_ID`, `selectable_bases()`,
  the verifier's `FRESH_PROVIDERS`, and the extra in `pyproject.toml` that installs CoolProp;
- **units**: `list_models` (30 entries) plus `syn001.cascade`, which has no signature, and the
  legacy clause of `FAMILY_TABLE` below, a transcription of the design notes D6 cites;
- **implementation sets**: the files F0's M9 scan (`scripts/corpus_identity.py`) attributes to a
  provider module (its `implementation_sha256` hash set) or to a model id (the legacy unit modules
  declaring it as `MODEL_ID` or in `MODEL_IDS`, F0's own cross-check rule).

It never reads `MODEL_BASES`, so E-F1-1's comparison of the admitted set with it is independent.

`core.json` holds D1's three built-in `functional_contributor` descriptors, E01's `cost`, `lca` and
`derived` (ADR 0052): read from `CONTRIBUTOR_ORDER`, `CONTRIBUTOR_MODULES` and each module's
`register_contributor(<name>, <factory>)` call (by AST, so nothing is registered or constructed);
the implementation set is every `*.py` under the directory of the module defining the factory
(D6). They are listed only: the registry never calls `register_contributor` (D1, risk 4).
"""

from __future__ import annotations

import argparse
import ast
import importlib
import importlib.util
import json
import re
import sys
import tomllib
from collections.abc import Callable, Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any, Final

ROOT: Final = Path(__file__).resolve().parent.parent
SOURCE: Final = ROOT / "src"
TABLE: Final = SOURCE / "openflowsheet" / "registry" / "builtin" / "legacy.json"
CORE_TABLE: Final = SOURCE / "openflowsheet" / "registry" / "builtin" / "core.json"

#: D6's connection definition, which every legacy method provides and every legacy unit requires.
CONNECTION: Final = "nTP-v1"
#: D6: every legacy descriptor's version and status.
VERSION: Final = "1.0.0"
STATUS: Final = "released"
#: D6's family table: (rule and source, units, legacy clause). A transcription of the design
#: notes D6 cites, never of `MODEL_BASES`.
FAMILY_TABLE: Final[tuple[tuple[str, tuple[str, ...], tuple[str, ...]], ...]] = (
    (
        "SYN-001 basis only (R-288, design note §14.4 D3)",
        (
            "syn001.liquid_pump",
            "syn001.conversion_reactor",
            "syn001.component_separator",
            "syn001.heat_exchanger",
            "syn001.kinetic_cstr",
        ),
        ("legacy:syn001",),
    ),
    (
        "C1 basis only (R-288)",
        (
            "c1.feed_source",
            "c1.adiabatic_mixer",
            "c1.tp_heater",
            "c1.tp_flash",
            "c1.stream_splitter",
            "c1.product_sink",
            "c1.reactor",
            "c1.reactor_standin",
            "c1.reactor_surrogate",
        ),
        ("legacy:pr-c1-v1",),
    ),
    (
        "routing on every basis but C1's (S11 §4.4, ADR 0050 D3)",
        ("syn001.feed_source", "syn001.product_sink", "syn001.stream_splitter"),
        ("legacy:syn001", "legacy:iapws95-v1", "legacy:coolprop-heos-v1", "legacy:wilson-ig-v2"),
    ),
    (
        "γ–φ faces (units design §4.5, §4.7)",
        (
            "syn001.tp_heater",
            "syn001.tp_flash",
            "syn001.ph_flash",
            "syn001.valve",
            "syn001.adiabatic_mixer",
        ),
        ("legacy:syn001", "legacy:wilson-ig-v2"),
    ),
    (
        "column (S11 §4.7, §9 I1)",
        ("syn001.column",),
        ("legacy:syn001", "legacy:wilson-ig-v2"),
    ),
    (
        "pure-fluid thermal (units design §4.7 I1b)",
        ("thermal.heater", "thermal.valve", "thermal.mixer", "thermal.flash", "thermal.pump"),
        ("legacy:iapws95-v1", "legacy:coolprop-heos-v1"),
    ),
    (
        "vapour machines (L-GP-2)",
        ("thermal.compressor", "thermal.turbine"),
        ("legacy:iapws95-v1", "legacy:coolprop-heos-v1", "legacy:wilson-ig-v2"),
    ),
    ("not bindable (revision_binding.py:1819)", ("syn001.cascade",), ()),
)
#: D6: the unit with no signature, which `list_models` does not list; it is not bindable.
NOT_BINDABLE: Final = "syn001.cascade"
#: D6 (R-301): the id F0 attributes no file to takes the files of the model it is the surrogate of.
SURROGATE_OF: Final[Mapping[str, str]] = {"c1.reactor_surrogate": "c1.reactor"}
#: D6: the optional dependency whose `pyproject.toml` extra is a method's `pip_extra`.
OPTIONAL_DEPENDENCY: Final[Mapping[str, str]] = {"coolprop-heos-v1": "CoolProp"}
#: D6's factories (`implementation.factory`).
BINDER: Final = "openflowsheet.application.revision_binding"
METHOD_FACTORY: Final = {"module": BINDER, "attribute": "basis_provider", "key": None}
#: The `reference_convention` of a provider constructed once per component (D6).
PER_COMPONENT: Final = "per_component"
#: E01's contributors whose implementation needs an extra of `pyproject.toml` (Brightway, `lca`).
CONTRIBUTOR_EXTRA: Final[Mapping[str, str]] = {"lca": "lca"}


def _modules() -> None:
    for entry in (str(SOURCE), str(ROOT / "scripts")):
        if entry not in sys.path:
            sys.path.insert(0, entry)


def _import_path(module: str) -> str:
    """The import-root-relative POSIX path of `module`'s file (`openflowsheet/thermo/x.py`)."""
    spec = importlib.util.find_spec(module)
    if spec is None or spec.origin is None:
        raise ValueError(f"{module}: no file")
    return Path(spec.origin).resolve().relative_to(SOURCE).as_posix()


def _descriptor(
    kind: str,
    identifier: str,
    title: str,
    *,
    requires: Sequence[Sequence[str]],
    provides: Sequence[str],
    modules: Iterable[str],
    factory: Mapping[str, Any] | None,
    payload: Mapping[str, Any],
    pip_extra: str | None = None,
) -> dict[str, Any]:
    return {
        "descriptor_format": "openflowsheet-extension-v1",
        "kind": kind,
        "id": identifier,
        "version": VERSION,
        "title": title,
        "status": STATUS,
        "requires": [list(clause) for clause in requires],
        "provides": list(provides),
        "limitations": [],
        "platforms": ["any"],
        "pip_extra": pip_extra,
        "data_rights": None,
        "implementation": {
            "modules": sorted(modules, key=lambda path: path.encode("utf-8")),
            "factory": None if factory is None else dict(factory),
        },
        "payload": dict(payload),
    }


# -- methods ---------------------------------------------------------------------------------


def _providers() -> dict[str, list[Any]]:
    """Provider id -> its constructed providers: one per selectable basis (CoolProp: one per
    fluid) through the binder's factory, and the two providers no basis selects."""
    from openflowsheet import resources
    from openflowsheet.application.revision_binding import basis_provider
    from openflowsheet.models.revision_flowsheet import selectable_bases
    from openflowsheet.thermo import wilson_ig
    from openflowsheet.thermo.pr_lib import PrLibProvider

    unselectable: dict[str, Callable[[], Any]] = {
        "pr-lib-v1": PrLibProvider,
        "wilson-ig-v1": lambda: wilson_ig.WilsonIdealGasProvider(
            resources.packaged_path(wilson_ig.RECORDS_PATH)
        ),
    }
    found: dict[str, list[Any]] = {}
    for basis in selectable_bases():
        found.setdefault(basis.provider_id, []).append(basis_provider(basis))
    for provider_id, construct in unselectable.items():
        if provider_id in found:
            raise ValueError(f"{provider_id} is selectable now: D6's table needs a re-read")
        found[provider_id] = [construct()]
    return found


def _provider_modules(module: str) -> list[str]:
    """F0's M9 attribution: the files of `module`'s `implementation_sha256` hash set."""
    import corpus_identity

    path = SOURCE / _import_path(module)
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    hashed = corpus_identity._hashed_files(path, tree)
    return sorted(file.resolve().relative_to(SOURCE).as_posix() for file in hashed)


def _pip_extra(provider_id: str) -> str | None:
    dependency = OPTIONAL_DEPENDENCY.get(provider_id)
    if dependency is None:
        return None
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    extras = [
        extra
        for extra, requirements in project.get("optional-dependencies", {}).items()
        if any(
            re.split(r"[\s\[<>=!~;]", requirement, maxsplit=1)[0].lower() == dependency.lower()
            for requirement in requirements
        )
    ]
    if len(extras) != 1:
        raise ValueError(f"{dependency}: expected one extra in pyproject.toml, found {extras}")
    return str(extras[0])


def _described(providers: Sequence[Any]) -> dict[str, Any]:
    """D6's `describe()` members of one provider id: one describe, or one per component."""
    described = [provider.describe() for provider in providers]
    for member in ("phases", "flashes", "state_definition", "provider_id"):
        if len({getattr(d, member) for d in described}) != 1:
            raise ValueError(f"{described[0].provider_id}: {member} varies by component")
    if described[0].state_definition != CONNECTION:
        raise ValueError(f"{described[0].provider_id}: state definition is not {CONNECTION}")
    members: dict[str, Any] = {
        "phases": list(described[0].phases),
        "flashes": list(described[0].flashes),
    }
    if len(described) == 1:
        (only,) = described
        members["properties"] = list(only.properties)
        members["reference_convention"] = only.reference_convention
        members["per_component"] = None
        members["derivative_inputs"] = list(only.derivative_order)
        return members
    per_component: dict[str, Any] = {}
    for d in described:
        (component,) = d.components
        per_component[component] = {
            "reference_convention": d.reference_convention,
            "properties": list(d.properties),
            "derivative_inputs": list(d.derivative_order),
        }
    rows = list(per_component.values())
    members["properties"] = [
        name for name in rows[0]["properties"] if all(name in row["properties"] for row in rows)
    ]
    members["reference_convention"] = PER_COMPONENT
    members["per_component"] = per_component
    members["derivative_inputs"] = [
        name
        for name in rows[0]["derivative_inputs"]
        if all(name in row["derivative_inputs"] for row in rows)
    ]
    return members


def methods() -> list[dict[str, Any]]:
    """D6's 7 legacy property methods."""
    from openflowsheet.models.revision_flowsheet import selectable_bases
    from openflowsheet.registry.tokens import LEGACY_PROVIDERS
    from openflowsheet.verify.certificate import FRESH_PROVIDERS

    providers = _providers()
    if set(providers) != LEGACY_PROVIDERS:
        raise ValueError(f"providers {sorted(providers)} are not D6's seven")
    bases = selectable_bases()
    found = []
    for provider_id in sorted(providers):
        module = type(providers[provider_id][0]).__module__
        declared = importlib.import_module(module).PROVIDER_ID
        if declared != provider_id:
            raise ValueError(f"{module}.PROVIDER_ID is {declared!r}, not {provider_id!r}")
        own = [
            {"record_source": basis.record_source, "components": list(basis.components)}
            for basis in bases
            if basis.provider_id == provider_id
        ]
        payload = {
            "legacy_provider_id": declared,
            **_described(providers[provider_id]),
            "bases": own,
            "selectable": bool(own),
            "verifier_fresh": provider_id in FRESH_PROVIDERS,
        }
        found.append(
            _descriptor(
                "property_method",
                provider_id,
                f"Legacy property method {provider_id}",
                requires=[],
                provides=[f"conn:{CONNECTION}", f"legacy:{provider_id}"],
                modules=_provider_modules(module),
                factory=METHOD_FACTORY,
                payload=payload,
                pip_extra=_pip_extra(provider_id),
            )
        )
    return found


# -- units -----------------------------------------------------------------------------------


def _signatures() -> list[dict[str, Any]]:
    """`list_models`' entries: the operation's own mapping (`local._model_view`) of each
    `MODEL_SIGNATURES` entry, sorted by model id, into its own result type. Not through an
    application, whose construction builds the process registry from the tables written here
    (W2-7); `tests/test_f1_legacy_builtins.py` holds this equal to `list_models()`."""
    from openflowsheet.application import local
    from openflowsheet.application.revision_binding import MODEL_SIGNATURES
    from openflowsheet.application.types import ModelRegistryView

    view = ModelRegistryView(
        models=tuple(
            local._model_view(MODEL_SIGNATURES[model_id]) for model_id in sorted(MODEL_SIGNATURES)
        )
    )
    models: list[dict[str, Any]] = view.as_document()["models"]
    return models


def _unit_modules() -> dict[str, list[str]]:
    """Model id -> the legacy unit modules F0's M9 scan finds that declare it (`MODEL_ID` or
    `MODEL_IDS`, F0's cross-check rule, R-940)."""
    import corpus_identity

    found: dict[str, list[str]] = {}
    for name in corpus_identity.legacy_unit_modules():
        relative = Path(name).relative_to("src").as_posix()
        module = importlib.import_module(relative.removesuffix(".py").replace("/", "."))
        declared = {getattr(module, "MODEL_ID", None), *getattr(module, "MODEL_IDS", ())}
        for model_id in declared - {None}:
            found.setdefault(str(model_id), []).append(relative)
    return found


def units() -> list[dict[str, Any]]:
    """D6's 31 legacy units: the `list_models` entries and `syn001.cascade`."""
    signatures = {entry["model_id"]: entry for entry in _signatures()}
    if NOT_BINDABLE in signatures:
        raise ValueError(f"{NOT_BINDABLE} has a signature now: D6's table needs a re-read")
    clauses: dict[str, tuple[str, ...]] = {}
    for _, members, clause in FAMILY_TABLE:
        for model_id in members:
            if model_id in clauses:
                raise ValueError(f"{model_id} is in two families")
            clauses[model_id] = clause
    if set(clauses) != {*signatures, NOT_BINDABLE}:
        missing = sorted({*signatures, NOT_BINDABLE} ^ set(clauses))
        raise ValueError(f"the family table and list_models differ on {missing}")
    attributed = _unit_modules()
    found = []
    for model_id in sorted(clauses):
        bindable = model_id != NOT_BINDABLE
        if not bindable:
            modules: list[str] = []
        elif model_id in attributed:
            modules = attributed[model_id]
        elif model_id in SURROGATE_OF:
            modules = attributed[SURROGATE_OF[model_id]]
        else:
            raise ValueError(f"F0 attributes no file to {model_id}")
        requires = [[f"conn:{CONNECTION}"]]
        if clauses[model_id]:
            requires.append(list(clauses[model_id]))
        payload = {
            "family": model_id.split(".", 1)[0],
            "bindable": bindable,
            "signature": signatures.get(model_id),
        }
        factory = (
            {"module": BINDER, "attribute": "MODEL_BUILDERS", "key": model_id} if bindable else None
        )
        found.append(
            _descriptor(
                "unit_model",
                model_id,
                f"Legacy unit model {model_id}",
                requires=requires,
                provides=[],
                modules=modules,
                factory=factory,
                payload=payload,
            )
        )
    return found


# -- the table -------------------------------------------------------------------------------


def connection_definition() -> dict[str, Any]:
    """D6's `nTP-v1`."""
    return _descriptor(
        "connection_definition",
        CONNECTION,
        f"Legacy connection definition {CONNECTION}",
        requires=[],
        provides=[f"conn:{CONNECTION}"],
        modules=[],
        factory=None,
        payload={"legacy": True, "state_definition": CONNECTION},
    )


# -- the E01 contributors (core.json) ---------------------------------------------------------


def _registered_factory(module: str, name: str) -> str:
    """The attribute `module` passes to `register_contributor(name, <attribute>)`, by AST."""
    spec = importlib.util.find_spec(module)
    if spec is None or spec.origin is None:
        raise ValueError(f"{module}: no file")
    tree = ast.parse(Path(spec.origin).read_text(encoding="utf-8"))
    found = [
        node.args[1].id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "register_contributor"
        and len(node.args) == 2
        and isinstance(node.args[0], ast.Constant)
        and node.args[0].value == name
        and isinstance(node.args[1], ast.Name)
    ]
    if len(found) != 1:
        raise ValueError(f"{module}: {len(found)} register_contributor({name!r}, ...) calls")
    return found[0]


def contributors() -> list[dict[str, Any]]:
    """D1's built-in `functional_contributor` descriptors: E01's contributors, in its order."""
    from openflowsheet.assessment.program import CONTRIBUTOR_MODULES, CONTRIBUTOR_ORDER

    found = []
    for name in CONTRIBUTOR_ORDER:
        module = CONTRIBUTOR_MODULES[name]
        attribute = _registered_factory(module, name)
        defining = getattr(importlib.import_module(module), attribute).__module__
        directory = (SOURCE / _import_path(defining)).parent
        modules = [path.relative_to(SOURCE).as_posix() for path in directory.rglob("*.py")]
        found.append(
            _descriptor(
                "functional_contributor",
                name,
                f"Assessment contributor {name}",
                requires=[],
                provides=[],
                modules=modules,
                factory={"module": defining, "attribute": attribute, "key": None},
                payload={},
                pip_extra=CONTRIBUTOR_EXTRA.get(name),
            )
        )
    return found


# -- the tables ------------------------------------------------------------------------------


def _sorted(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(rows, key=lambda row: (row["kind"].encode("utf-8"), row["id"].encode("utf-8")))


def table() -> list[dict[str, Any]]:
    """The legacy table, sorted by (kind, id)."""
    return _sorted([connection_definition(), *methods(), *units()])


def core_table() -> list[dict[str, Any]]:
    """The core table (`core.json`), sorted by (kind, id)."""
    return _sorted(contributors())


def tables() -> dict[Path, list[dict[str, Any]]]:
    """Each built-in table's file and its regenerated rows."""
    return {TABLE: table(), CORE_TABLE: core_table()}


def render(rows: Sequence[Mapping[str, Any]]) -> str:
    return json.dumps(list(rows), indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def differences(old: object, new: object, pointer: str = "") -> list[str]:
    """The JSON pointers at which `old` and `new` differ (a whole member when its type differs)."""
    if isinstance(old, dict) and isinstance(new, dict):
        found: list[str] = []
        for key in sorted({*old, *new}):
            where = pointer + "/" + str(key).replace("~", "~0").replace("/", "~1")
            if key not in old or key not in new:
                found.append(where)
            else:
                found.extend(differences(old[key], new[key], where))
        return found
    if isinstance(old, list) and isinstance(new, list):
        found = [
            item
            for index in range(min(len(old), len(new)))
            for item in differences(old[index], new[index], f"{pointer}/{index}")
        ]
        found.extend(
            f"{pointer}/{index}"
            for index in range(min(len(old), len(new)), max(len(old), len(new)))
        )
        return found
    return [] if type(old) is type(new) and old == new else [pointer]


def _shown(path: Path) -> str:
    return path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else str(path)


def _summary(rows: Sequence[Mapping[str, Any]]) -> str:
    kinds: dict[str, int] = {}
    for row in rows:
        kinds[row["kind"]] = kinds.get(row["kind"], 0) + 1
    return ", ".join(f"{count} {kind}" for kind, count in sorted(kinds.items()))


def check() -> int:
    from openflowsheet.registry import Registry

    committed: dict[str, list[dict[str, Any]]] = {}
    rows: list[dict[str, Any]] = []
    for path, regenerated in tables().items():
        text = render(regenerated)
        if not path.is_file():
            print(f"registry_builtin --check: FAILED, {_shown(path)} is missing")
            return 1
        held = path.read_text(encoding="utf-8")
        if held != text:
            found = differences(json.loads(held), json.loads(text))
            shown = ", ".join(found[:10]) + (
                f" (+{len(found) - 10} more)" if len(found) > 10 else ""
            )
            print(
                f"registry_builtin --check: FAILED, {_shown(path)} differs at "
                f"{len(found)} pointer(s): {shown or 'formatting only'}"
            )
            return 1
        committed[path.stem] = json.loads(held)
        rows.extend(regenerated)
    registry = Registry.build(builtin_tables=committed)
    print(
        f"registry_builtin --check: clean, {len(rows)} descriptors in {len(committed)} tables "
        f"({_summary(rows)}); registry_sha256 {registry.registry_sha256}"
    )
    return 0


def write() -> int:
    written = []
    for path, rows in tables().items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(render(rows), encoding="utf-8")
        written.append(f"{len(rows)} descriptors ({_summary(rows)}) to {_shown(path)}")
    print("registry_builtin --write: " + "; ".join(written))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n", 1)[0])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true", help="write the built-in tables")
    mode.add_argument("--check", action="store_true", help="regenerate in memory and compare")
    arguments = parser.parse_args(argv)
    _modules()
    return write() if arguments.write else check()


if __name__ == "__main__":
    sys.exit(main())
