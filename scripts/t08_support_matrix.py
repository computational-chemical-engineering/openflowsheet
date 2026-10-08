"""The v0.1 supported envelope and its support matrix (T08 release spec §5; T08 W2.1, W2.2).

`benchmarks/t08/support_envelope.yaml` is the machine-readable envelope; `docs/support-matrix.md` is
its rendering. This script renders the one from the other and checks both against the code and the
evidence tree:

- **T08.A20** — the enumerated axes equal the code: the twenty operations of `OPERATIONS` (with
  their transports), the thirteen models of `MODEL_BUILDERS`, the offered policies
  (`APPLICATION_POLICIES`), the unit spellings of `CONVERSION_ROWS` *and* of ADR 0016's table, the
  providers of `openflowsheet.thermo` (by `PROVIDER_ID`), the provider's components and domain,
  and the platform facts (the lock's hash, the CI matrix's Python and architectures).
- **T08.A21** — the harvest: every `limitations[]` entry and every non-`pass` check of every
  manifest under `evidence/` is classified exactly once (E, S, P or B), each keyed by manifest
  path, list and index and the SHA-256 of its text; an unmapped item, a dangling pointer or a
  changed text fails.
- **T08.A22** — every `unsupported` row names a typed outcome and at least one test node, and
  every test node the envelope cites is collected by pytest. That the nodes *pass* is
  `tests/test_t08_w2_support_envelope.py`'s, which runs them.
- **T08.A23** — `docs/support-matrix.md` equals the rendering byte for byte.

Every evidence string must resolve: a pytest node id (`tests/<file>.py::<name>` with an optional
`[<param>]`; an unparametrized name covers all its parameters), `check:<id>` (present in some
manifest — an `unsupported` check is evidence of a recorded absence; a harvest `S` pointer's check
must `pass`), or `doc:<path>` with an optional ` §<section>` (the path must exist).

Usage:
    PYTHONPATH=src .venv/bin/python scripts/t08_support_matrix.py --check
    PYTHONPATH=src .venv/bin/python scripts/t08_support_matrix.py --emit
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import pkgutil
import re
import subprocess
import sys
from collections import Counter
from collections.abc import Iterable, Iterator, Mapping, Sequence
from pathlib import Path
from typing import Any, Final

import yaml

ROOT: Final = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

ENVELOPE: Final = ROOT / "benchmarks" / "t08" / "support_envelope.yaml"
MATRIX: Final = ROOT / "docs" / "support-matrix.md"
SPEC: Final = ROOT / "docs" / "derivations" / "T08-release-spec.md"
ADR_0016: Final = ROOT / "docs" / "adr" / "0016-unit-conversion-v2.md"
LOCK: Final = ROOT / "requirements.lock"
CI: Final = ROOT / ".github" / "workflows" / "ci.yml"

#: Spec §5.1: the envelope's top-level keys, in order.
TOP_LEVEL: Final = ("envelope_id", "release", "axes", "unsupported", "limitations", "harvest")
ENVELOPE_ID: Final = "v0.1-envelope-1"
#: The CI runners and the architecture each is (`.github/workflows/ci.yml`'s matrix).
RUNNER_ARCHITECTURE: Final[Mapping[str, str]] = {
    "ubuntu-latest": "x86-64",
    "ubuntu-24.04-arm": "aarch64",
}
#: Spec §5.7's classes.
CLASSES: Final = ("E", "S", "P", "B")

_NODE = re.compile(r"^tests/[^:]+\.py::[^\s]+$")


# ------------------------------------------------------------------------------------ loading


def load(path: Path = ENVELOPE) -> dict[str, Any]:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict), path
    return loaded


def evidence_strings(envelope: Mapping[str, Any]) -> Iterator[tuple[str, str]]:
    """(row id, evidence string) for every evidence entry of the axes, rows and limitations."""
    for section in ("axes", "unsupported", "limitations"):
        for row in envelope.get(section) or ():
            for item in row.get("evidence") or ():
                yield f"{section}.{row['id']}", item


# ------------------------------------------------------------------------- facts from the code


def _adr_0016_spellings() -> list[list[str]]:
    """ADR 0016 D3's table: (required kind, unit) for every unit a row names."""
    found: set[tuple[str, str]] = set()
    rows = False
    for line in ADR_0016.read_text(encoding="utf-8").splitlines():
        if line.startswith("| Required kind | Unit |"):
            rows = True
            continue
        if rows and not line.startswith("|"):
            break
        if rows and not line.startswith("| ---"):
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            kind = re.findall(r"`([^`]+)`", cells[0])[0]
            for unit in re.findall(r"`([^`]+)`", cells[1]):
                found.add((kind, unit))
    return sorted([kind, unit] for kind, unit in found)


def _providers() -> list[str]:
    import openflowsheet.thermo as thermo

    found = set()
    for module in pkgutil.iter_modules(thermo.__path__):
        provider_id = getattr(
            importlib.import_module(f"openflowsheet.thermo.{module.name}"), "PROVIDER_ID", None
        )
        if isinstance(provider_id, str):
            found.add(provider_id)
    return sorted(found)


def _ci() -> tuple[list[str], list[str]]:
    text = CI.read_text(encoding="utf-8")
    pythons = sorted(set(re.findall(r'python-version:\s*"([^"]+)"', text)))
    runners: set[str] = set()
    for matrix in re.findall(r"runner:\s*\[([^\]]*)\]", text):
        runners.update(item.strip() for item in matrix.split(",") if item.strip())
    return pythons, sorted(RUNNER_ARCHITECTURE.get(runner, runner) for runner in runners)


def code_facts() -> dict[str, Any]:
    """What the enumerated axes are compared with (T08.A20)."""
    from openflowsheet.application.operations import OPERATIONS
    from openflowsheet.application.policies import APPLICATION_POLICIES
    from openflowsheet.application.revision_binding import MODEL_BUILDERS
    from openflowsheet.thermo.syn001 import Syn001Provider
    from openflowsheet.units import CONVERSION_ROWS

    described = Syn001Provider().describe()
    pythons, architectures = _ci()
    return {
        "operations": {name: list(row.transports) for name, row in OPERATIONS.items()},
        "models": sorted(MODEL_BUILDERS),
        "policies": sorted(APPLICATION_POLICIES),
        "unit_spellings": sorted([kind, unit] for kind, unit in CONVERSION_ROWS),
        "adr_0016_spellings": _adr_0016_spellings(),
        "providers": _providers(),
        "components": list(described.components),
        "reference_convention": described.reference_convention,
        "temperature_K": list(described.domain["T"]),
        "pressure_Pa": list(described.domain["P"]),
        "lock_sha256": hashlib.sha256(LOCK.read_bytes()).hexdigest(),
        "pythons": pythons,
        "architectures": architectures,
    }


# ------------------------------------------------------------------------------------- checks


def _axis(envelope: Mapping[str, Any], axis_id: str) -> Mapping[str, Any]:
    (axis,) = (axis for axis in envelope["axes"] if axis["id"] == axis_id)
    return axis


def check_structure(envelope: Mapping[str, Any]) -> list[str]:
    problems: list[str] = []
    if tuple(envelope) != TOP_LEVEL:
        problems.append(f"top-level keys {list(envelope)} are not spec §5.1's {list(TOP_LEVEL)}")
    if envelope.get("envelope_id") != ENVELOPE_ID:
        problems.append(f"envelope_id {envelope.get('envelope_id')!r} is not {ENVELOPE_ID!r}")
    for section in ("axes", "unsupported", "limitations"):
        ids = [row.get("id") for row in envelope.get(section) or ()]
        if len(ids) != len(set(ids)):
            repeated = sorted({i for i in ids if ids.count(i) > 1})
            problems.append(f"{section}: duplicate ids {repeated}")
        for row in envelope.get(section) or ():
            if not row.get("evidence"):
                problems.append(f"{section}.{row.get('id')}: no evidence (spec §5.1)")
    limitations = {row.get("id") for row in envelope.get("limitations") or ()}
    property_model = [a for a in envelope.get("axes") or () if a.get("id") == "property_model"]
    for axis in property_model:
        for provider in axis.get("unbound_providers") or ():
            where = f"property_model.unbound_providers.{provider.get('id')}"
            if provider.get("id") not in axis.get("providers", ()):
                problems.append(f"{where}: not a listed provider")
            if provider.get("limitation") not in limitations:
                problems.append(f"{where}: no limitation row {provider.get('limitation')!r}")
            if not str(provider.get("caveat", "")).strip():
                problems.append(f"{where}: no caveat")
    return problems


def check_a20(envelope: Mapping[str, Any], facts: Mapping[str, Any] | None = None) -> list[str]:
    """The enumerated axes against the code, as exact set (and, for transports, list) equality."""
    facts = code_facts() if facts is None else facts
    claimed = {
        "operations": {
            name: list(transports)
            for name, transports in _axis(envelope, "interfaces")["operations"].items()
        },
        "models": sorted(_axis(envelope, "unit_models")["members"]),
        "policies": sorted(_axis(envelope, "solve_policies")["members"]),
        "unit_spellings": sorted(_axis(envelope, "specifications")["unit_spellings"]),
        "adr_0016_spellings": sorted(_axis(envelope, "specifications")["unit_spellings"]),
        "providers": sorted(_axis(envelope, "property_model")["providers"]),
        "components": list(_axis(envelope, "components")["members"]),
        "reference_convention": _axis(envelope, "property_model")["reference_convention"],
        "temperature_K": list(_axis(envelope, "domain")["temperature_K"]),
        "pressure_Pa": list(_axis(envelope, "domain")["pressure_Pa"]),
        "lock_sha256": _axis(envelope, "platforms")["lock_sha256"],
        "pythons": [_axis(envelope, "platforms")["python"]],
        "architectures": sorted(_axis(envelope, "platforms")["architectures"]),
    }
    problems = [
        f"A20 {key}: envelope {claimed[key]!r} != code {facts[key]!r}"
        for key in claimed
        if claimed[key] != facts[key]
    ]
    if len(claimed["operations"]) != 20 or len(claimed["models"]) != 13:
        problems.append("A20: spec §9 registers 20 operations and 13 models")
    return problems


def _manifests() -> dict[str, dict[str, Any]]:
    return {
        path.relative_to(ROOT).as_posix(): json.loads(path.read_text(encoding="utf-8"))
        for path in sorted((ROOT / "evidence").glob("**/manifest.json"))
    }


def manifest_checks(
    manifests: Mapping[str, Mapping[str, Any]] | None = None, *, passing: bool = False
) -> set[str]:
    """Every check id of every manifest, or only those whose result is `pass`."""
    manifests = _manifests() if manifests is None else manifests
    return {
        check["id"]
        for manifest in manifests.values()
        for check in manifest.get("checks", ())
        if not passing or check.get("result") == "pass"
    }


def collected_nodes(nodes: Iterable[str]) -> set[str]:
    """The node ids pytest collects from the files `nodes` name."""
    files = sorted({node.split("::", 1)[0] for node in nodes})
    if not files:
        return set()
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider", *files],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return {line.strip() for line in completed.stdout.splitlines() if "::" in line}


def node_is_collected(node: str, collected: set[str]) -> bool:
    return node in collected or any(item.startswith(node + "[") for item in collected)


def unresolved(
    references: Iterable[tuple[str, str]], collected: set[str], checks: set[str]
) -> list[str]:
    """Every (where, reference) whose reference does not resolve."""
    problems: list[str] = []
    for where, reference in references:
        if _NODE.match(reference):
            if not node_is_collected(reference, collected):
                problems.append(f"{where}: test node not collected: {reference}")
        elif reference.startswith("check:"):
            if reference.removeprefix("check:") not in checks:
                problems.append(f"{where}: no manifest check {reference}")
        elif reference.startswith("doc:"):
            path = reference.removeprefix("doc:").split(" §", 1)[0]
            if not (ROOT / path).is_file():
                problems.append(f"{where}: document does not exist: {path}")
        else:
            problems.append(f"{where}: unreadable evidence {reference!r}")
    return problems


def test_nodes(references: Iterable[tuple[str, str]]) -> list[str]:
    return [reference for _, reference in references if _NODE.match(reference)]


def unsupported_nodes(envelope: Mapping[str, Any]) -> list[str]:
    """Every test node an `unsupported` row cites (T08.A22 runs them)."""
    return [
        item for row in envelope["unsupported"] for item in row["evidence"] if _NODE.match(item)
    ]


def check_a22(envelope: Mapping[str, Any]) -> list[str]:
    problems: list[str] = []
    for row in envelope["unsupported"]:
        if not str(row.get("outcome") or "").strip():
            problems.append(f"A22 {row['id']}: no typed outcome")
        if not any(_NODE.match(item) for item in row["evidence"]):
            problems.append(f"A22 {row['id']}: no test node")
    return problems


# ----------------------------------------------------------------------------------- render


def _cell(text: object) -> str:
    return " ".join(str(text).split()).replace("|", "\\|")


def _evidence(items: Sequence[str]) -> str:
    return "<br>".join(f"`{_cell(item)}`" for item in items)


def render(envelope: Mapping[str, Any]) -> str:
    """`docs/support-matrix.md`, from the envelope alone (T08.A23)."""
    lines = [
        "<!-- Generated by scripts/t08_support_matrix.py --emit from "
        "benchmarks/t08/support_envelope.yaml. Do not edit; --check compares. -->",
        "",
        f"# Support matrix — v{envelope['release']}",
        "",
        f"Envelope `{envelope['envelope_id']}` (T08 release spec §5). **Unlisted is unsupported** "
        "(blueprint §2.2). Every row carries its evidence: a test node, a manifest check "
        "(`check:`), or a document (`doc:`). Numerical verification only — nothing here is "
        "empirical validation (L18).",
        "",
        "## Supported",
        "",
        "| Axis | v0.1 statement | Evidence |",
        "| --- | --- | --- |",
    ]
    for axis in envelope["axes"]:
        lines.append(
            f"| {_cell(axis['title'])} | {_cell(axis['statement'])} | "
            f"{_evidence(axis['evidence'])} |"
        )
    lines += ["", "### Enumerated (checked against the code, T08.A20)", ""]
    models = _axis(envelope, "unit_models")["members"]
    lines.append("- **Unit models:** " + ", ".join(f"`{m}`" for m in models))
    lines.append(
        "- **Solve policies:** "
        + ", ".join(f"`{p}`" for p in _axis(envelope, "solve_policies")["members"])
    )
    property_model = _axis(envelope, "property_model")
    unbound = property_model.get("unbound_providers") or ()
    bound = [p for p in property_model["providers"] if p not in {u["id"] for u in unbound}]
    lines.append(
        "- **Components:** "
        + ", ".join(f"`{c}`" for c in _axis(envelope, "components")["members"])
        + f"; provider `{', '.join(bound)}`"
    )
    domain = _axis(envelope, "domain")
    lines.append(
        f"- **Domain:** T in [{domain['temperature_K'][0]:g}, {domain['temperature_K'][1]:g}] K, "
        f"P in [{domain['pressure_Pa'][0]:g}, {domain['pressure_Pa'][1]:g}] Pa"
    )
    for provider in unbound:
        # M01 review F1: a shipped provider no model binds is not the axes' provider.
        lines.append(
            f"- **Shipped, bound by no model:** `{provider['id']}`, with {provider['caveat']} "
            f"({provider['limitation']})"
        )
    lines.append(
        "- **Unit spellings (ADR 0016):** "
        + "; ".join(
            f"{kind} `{unit}`" for kind, unit in _axis(envelope, "specifications")["unit_spellings"]
        )
    )
    platforms = _axis(envelope, "platforms")
    lines.append(
        f"- **Platforms:** {', '.join(platforms['architectures'])}; Python {platforms['python']}; "
        f"lock `{platforms['lock_sha256']}`"
    )
    lines += ["", "| Operation | Transports |", "| --- | --- |"]
    for name, transports in _axis(envelope, "interfaces")["operations"].items():
        lines.append(f"| `{name}` | {', '.join(transports)} |")
    lines += [
        "",
        "## Unsupported, and how each fails",
        "",
        "| Id | Capability | Typed outcome | Evidence |",
        "| --- | --- | --- | --- |",
    ]
    for row in envelope["unsupported"]:
        lines.append(
            f"| {row['id']} | {_cell(row['capability'])} | {_cell(row['outcome'])} | "
            f"{_evidence(row['evidence'])} |"
        )
    lines += [
        "",
        "## Registered limitations",
        "",
        "| Id | Limitation | Evidence |",
        "| --- | --- | --- |",
    ]
    for row in envelope["limitations"]:
        lines.append(f"| {row['id']} | {_cell(row['text'])} | {_evidence(row['evidence'])} |")
    lines += _render_harvest(envelope.get("harvest") or [])
    return "\n".join(lines) + "\n"


def _render_harvest(harvest: Sequence[Mapping[str, Any]]) -> list[str]:
    lines = ["", "## Harvest (T08.A21)", ""]
    if not harvest:
        return [*lines, "Not yet classified (W2.2)."]
    packages = sorted({item["manifest"].split("/")[1] for item in harvest})
    tally = Counter((item["manifest"].split("/")[1], item["class"]) for item in harvest)
    lines += [
        f"{len(harvest)} items — every `limitations[]` entry and non-`pass` check of the "
        f"{len(packages)} manifests under `evidence/` — each classified once: **E** user-facing "
        "(a row above), **S** superseded or closed, **P** provenance or process note (stays in "
        "its manifest), **B** v0.2 backlog (spec §6.3). The classification is a build-lane draft "
        "for the design-lane review.",
        "",
        "| Package | E | S | P | B |",
        "| --- | --- | --- | --- | --- |",
    ]
    for package in packages:
        counts = " | ".join(str(tally[(package, name)]) for name in CLASSES)
        lines.append(f"| {package} | {counts} |")
    totals = Counter(item["class"] for item in harvest)
    lines.append("| **all** | " + " | ".join(str(totals[name]) for name in CLASSES) + " |")
    return lines


# -------------------------------------------------------------------------------- the harvest


def text_sha256(item: str | Mapping[str, Any]) -> str:
    """Spec §5.7's text key. A limitation is its UTF-8 text; a check is its canonical JSON (sorted
    keys, no whitespace), so a change to any member of the check — its result too — is a change."""
    if isinstance(item, str):
        data = item.encode("utf-8")
    else:
        data = json.dumps(item, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(data).hexdigest()


#: Manifests the harvest does not read: T08's own (written at T08 close, after `C`). Its
#: limitations are drawn from this envelope's L-rows and the verdicts, so harvesting it into the
#: envelope would be circular, and its classification could only be written into `benchmarks/`
#: after `C`, which ADR 0021 D2.4 forbids. The harvest is P00–T07's, as spec §5.7 counts it
#: ("today 18 manifests") and `t08_reference.py`'s `HARVEST_PACKAGES` reads it.
HARVEST_EXCLUDED = ("evidence/T08/",)


def harvest_items(
    manifests: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[tuple[str, str], dict[str, str]]:
    """What the harvest must classify: (manifest, `limitations[i]` / `checks[i]`) -> its key."""
    if manifests is None:
        manifests = {
            path: manifest
            for path, manifest in _manifests().items()
            if not path.startswith(HARVEST_EXCLUDED)
        }
    items: dict[tuple[str, str], dict[str, str]] = {}
    for path, manifest in manifests.items():
        for index, text in enumerate(manifest.get("limitations", ())):
            items[(path, f"limitations[{index}]")] = {"sha256": text_sha256(text)}
        for index, check_entry in enumerate(manifest.get("checks", ())):
            if check_entry.get("result") != "pass":
                items[(path, f"checks[{index}]")] = {
                    "sha256": text_sha256(check_entry),
                    "check_id": check_entry["id"],
                }
    return items


def backlog_ids() -> set[str]:
    """Spec §6.3's v0.2 backlog ids (B1…)."""
    text = SPEC.read_text(encoding="utf-8")
    section = text[text.index("### 6.3") : text.index("\n## 7.")]
    return set(re.findall(r"\bB\d+\b", section))


def harvest_references(envelope: Mapping[str, Any]) -> list[tuple[str, str]]:
    return [
        (f"harvest {entry.get('manifest')} {entry.get('item')}", pointer)
        for entry in envelope.get("harvest") or ()
        if entry.get("class") == "S"
        for pointer in entry.get("to") or ()
    ]


def check_a21(
    envelope: Mapping[str, Any],
    items: Mapping[tuple[str, str], Mapping[str, str]] | None = None,
    collected: set[str] | None = None,
    passing: set[str] | None = None,
) -> list[str]:
    """Every item classified exactly once, every pointer resolving, every text hash current."""
    items = harvest_items() if items is None else items
    passing = manifest_checks(passing=True) if passing is None else passing
    harvest = list(envelope.get("harvest") or ())
    if collected is None:
        collected = collected_nodes(test_nodes(harvest_references(envelope)))
    rows = {row["id"] for row in envelope["limitations"]} | {
        row["id"] for row in envelope["unsupported"]
    }
    backlog = backlog_ids()
    problems: list[str] = []
    keys = [(entry.get("manifest"), entry.get("item")) for entry in harvest]
    for key in sorted({key for key in keys if keys.count(key) > 1}, key=str):
        problems.append(f"A21 {key[0]} {key[1]}: classified more than once")
    for key in sorted(set(items) - set(keys)):
        problems.append(f"A21 {key[0]} {key[1]}: unmapped")
    for entry in harvest:
        where = f"A21 {entry.get('manifest')} {entry.get('item')}"
        item = items.get((entry.get("manifest"), entry.get("item")))
        if item is None:
            problems.append(f"{where}: dangling (no such item)")
            continue
        if entry.get("sha256") != item["sha256"]:
            problems.append(f"{where}: text changed (sha256 {item['sha256']})")
        if entry.get("check_id") != item.get("check_id"):
            problems.append(
                f"{where}: check id {entry.get('check_id')!r} != {item.get('check_id')!r}"
            )
        kind, pointers = entry.get("class"), list(entry.get("to") or ())
        if kind not in CLASSES:
            problems.append(f"{where}: class {kind!r} not in {CLASSES}")
        elif kind == "P" and pointers:
            problems.append(f"{where}: a P item stays in its manifest and points nowhere")
        elif kind != "P" and not pointers:
            problems.append(f"{where}: class {kind} needs a pointer")
        elif kind == "E":
            # Review 2 Ruling 4: an E item may also carry the backlog id of a handed-on defect.
            problems += [
                f"{where}: no envelope row {p}"
                for p in pointers
                if p not in rows and p not in backlog
            ]
            if not any(p in rows for p in pointers):
                problems.append(f"{where}: an E item points to no envelope row")
        elif kind == "B":
            problems += [f"{where}: no §6.3 backlog id {p}" for p in pointers if p not in backlog]
        elif kind == "S":
            for pointer in pointers:
                if pointer.startswith("check:") and pointer.removeprefix("check:") not in passing:
                    problems.append(f"{where}: {pointer} is not a passing manifest check")
            problems += unresolved(
                [(where, p) for p in pointers if not p.startswith("check:")], collected, passing
            )
    return problems


def check_a23(envelope: Mapping[str, Any]) -> list[str]:
    if not MATRIX.is_file():
        return [f"A23: {MATRIX.relative_to(ROOT)} does not exist; run --emit"]
    if MATRIX.read_text(encoding="utf-8") != render(envelope):
        return [f"A23: {MATRIX.relative_to(ROOT)} differs from the rendering; run --emit"]
    return []


# -------------------------------------------------------------------------------------- main


def check(envelope: Mapping[str, Any]) -> list[str]:
    references = list(evidence_strings(envelope))
    collected = collected_nodes(test_nodes([*references, *harvest_references(envelope)]))
    return [
        *check_structure(envelope),
        *check_a20(envelope),
        *check_a21(envelope, collected=collected),
        *check_a22(envelope),
        *unresolved(references, collected, manifest_checks()),
        *check_a23(envelope),
    ]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--check", action="store_true", help="T08.A20–A23; exit 1 on a problem")
    action.add_argument("--emit", action="store_true", help=f"write {MATRIX.relative_to(ROOT)}")
    arguments = parser.parse_args(argv)
    envelope = load()
    if arguments.emit:
        MATRIX.write_text(render(envelope), encoding="utf-8")
        print(f"wrote {MATRIX.relative_to(ROOT)}")
        return 0
    problems = check(envelope)
    for problem in problems:
        print(problem)
    print(f"{len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
