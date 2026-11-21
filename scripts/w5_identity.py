"""S19 W5: the identity tool (`docs/briefs/S19-W5-ruling.md`, sections 4 to 6; work order WO-0).

The ruling decides what a byte change of a registry-hashed file moves; this tool computes it.

    w5_identity.py sets [--check] [--step] [--base REV] [--legacy PATH] [--core PATH]
                        [--json PATH]
    w5_identity.py predict --base REV [--files PATH ...] [--against-log F0LOG]
                           [--against-tables] [--json PATH] [--max-tier N]
    w5_identity.py judge --before REV --after REV [--files PATH ...] [--max-tier N]
    w5_identity.py coverage --base REV [--head REV]
    w5_identity.py pin --base REV [--registry REV] [--json PATH] -- SCRIPT [ARGUMENT ...]

- `sets`: R (the union of the implementation `modules` of `legacy.json` and `core.json`), F (F0's
  M9 set, `corpus_identity.frozen_modules`) and the four tiers of section 4, by its rules. It
  refuses to emit, exit 1 naming the assertion, when one of them fails: S1 F subset of R; S2 the
  tables' implementation sets equal the generator's (`registry_builtin.tables`); S3 every hash
  site has a provider id and every provider one `implementation_sha256`; S4 the code's
  `[:12]` of every provider equals the one in each registered M2 label naming it (otherwise the
  tier rules would read a stale registry); S5 T-2a; S6 the tiers partition R. `--check` prints
  the one summary line only. S2 and S4 hold only at a base (B, or K once re-registered): at a
  step the held tables lag a tier 1 split and the registered labels lag a tier 3 edit. `--step`
  says the revision is a step: S2 and S4 are skipped and the summary line says so. The tiers
  printed at a step read the step's code against B's registry; a batch's admitted set is the
  one fixed at B.
- `predict`: the (measure, key) pairs of F0's registry that a comment-only change of the files
  moves, by section 3.2's reach rules, and whether `registry_sha256` moves. `--files` defaults
  to `git diff --name-only BASE..HEAD` (`--files` with no path: E is empty); files outside R
  move nothing, except B7's seven group modules, which M9 measures and the base does not
  register (section 8: M9 has 42 keys at head). `--against-log` compares
  the prediction with an unpinned F0 `--check` log, both ways, and its summary line (W5-S3).
  The prediction also names the table pointers E moves (W5-S4: a contributor's implementation
  `modules` after a tier 1 split adds or removes a module in its directory, coolprop-heos-v1's
  for B7's seven group modules, the units' factory `module` when the generator is in E, WO-N4),
  each with its expected value; a pointer whose value the ruling leaves open is `unpredicted` and
  fails. `tables.sha256` moves exactly when a table pointer does, `builtin-sha256.txt` when E
  meets R or a table pointer moves. `--against-tables` compares HEAD's generator output with
  BASE's committed registry by pointer, both ways (W5-S4 at a step).
  `predict` and `judge` refuse, exit 1 naming it, an E with a tier 4 file, a file above
  `--max-tier N` (default 3; batch N runs with 2 until FR-1 is signed) or a nonempty M7
  prediction (R1).
- `judge`: W5-K2. The changed (measure, key) pairs of `benchmarks/f0/corpus.json` from BEFORE to
  AFTER must equal `predict --base BEFORE` for E = `git diff --name-only BEFORE AFTER` (or
  `--files`), every predicted value must change, and `format`, `reference_platform`, `corpus`
  and `archived_outputs` must stay equal. The committed registry (`legacy.json`, `core.json`,
  `tables.sha256`, `builtin-sha256.txt`) is diffed from BEFORE to AFTER by pointer against the
  table prediction, both ways, as `--against-tables` does at a step.
- `coverage`: R4 and W5-S7. For each file of R at BASE that HEAD (default: the working tree)
  changes, every (`openflowsheet` module, name) pair it imports at HEAD must have been imported
  at BASE or lie in its hash scope at HEAD: the intersection of every identity set that holds
  the file (its provider hash sets from M9's scan, a unit's own `artifact_hash`, and the
  regenerated registry implementation sets), so one contributor's hash does not cover another's
  directory.
  A new name from a module the file imported at BASE is admitted only if it was importable from
  that module at BASE (code moved into it since is a hole). A new module is admitted only as a
  retarget: every name taken from it was taken at BASE from a module M0 with `M0.name is M.name`
  there. Also M9's key set must be BASE's, plus those of B7's seven group modules the diff
  changes (section 8, the one exception, as `predict` scopes it). The gate passes the step's
  commit as `--head`, so that W5-S3 and W5-S7 judge the same E.

A revision's facts are measured in a subprocess on an extracted copy (`git archive`), with that
revision's own `corpus_identity.py` and `registry_builtin.py`; the working tree's with `--tree`.
- `pin`: the identity pin (R2, W5-S2, W5-K5; acceptance W5-T3 to W5-T5). E is `git diff
  --name-only BASE` of the working tree, ∩ R at BASE. Each file of E whose hash scope
  (`hash_scope`) is BASE's is pinned: SCRIPT runs in this process, as `PYTHONPATH=<tree>/src
  python SCRIPT ...` would run it, and every binary `pathlib` read of a pinned file
  (`Path.read_bytes`, `Path.open` in a binary read mode) gets that file's bytes at BASE. Imports
  do not read through `pathlib`, so the head's code runs while the identity sites read the base.
  A file whose scope changed (B7's CoolProp files) has no base form and is left to the head
  (`PIN UNPINNED`). Each pinned read is recorded with its caller (`PIN READ <path>
  <reader><-<its caller>`, both `file:function`). It exits 3 (`PIN_FAILED`) with `PIN VACUOUS
  <path>` for a pinned path never read and `PIN FOREIGN READ <path> <caller>` for a read outside
  `PIN_SITES` (the identity sites measured at 8d31b89e); otherwise with SCRIPT's status.
  `--registry REV` serves F0's registry (`benchmarks/f0/corpus.json`, any read mode) from REV,
  for W5-K5 at K against the registry at B. `--json` writes the record, with `moved_files`: the
  unpinned files and B7's group modules, whose F0 keys the pinned run moves (W5-S2's exception).
"""

from __future__ import annotations

import argparse
import ast
import contextlib
import importlib
import io
import json
import os
import re
import runpy
import subprocess
import sys
import tarfile
import tempfile
from collections.abc import Iterable, Iterator, Mapping, Sequence
from pathlib import Path
from typing import Any, Final

ROOT: Final = Path(__file__).resolve().parent.parent
#: What a revision's facts read: the package and the data it loads at import (`benchmarks`),
#: both generators, F0's registry and M7's corpus, the extras table, and the descriptor schema
#: the table digests hash (`_data/schemas` links to `schemas`).
ARCHIVED: Final = ("src", "scripts", "benchmarks", "schemas", "tests/fixtures/f0", "pyproject.toml")
TABLES: Final = ("legacy", "core")
REGISTRY_CONSTANT: Final = "tests/fixtures/registry/builtin-sha256.txt"
CORPUS_FILE: Final = "benchmarks/f0/corpus.json"
#: W5-K2: the registry's fields outside the measures, unchanged by a re-registration.
REGISTRY_FIELDS: Final = ("format", "reference_platform", "corpus", "archived_outputs")
TIER_NAMES: Final = {
    1: "registry only",
    2: "M9 and registry",
    3: "run identity",
    4: "excluded",
}
#: The built-in registry's files (W5-S4, W5-K1): the two tables, their digests, E-F1-5's constant.
TABLE_FILES: Final = {
    "legacy": "src/openflowsheet/registry/builtin/legacy.json",
    "core": "src/openflowsheet/registry/builtin/core.json",
}
DIGEST_FILE: Final = "src/openflowsheet/registry/builtin/tables.sha256"
GENERATOR: Final = "scripts/registry_builtin.py"
#: Ruling section 9, WO-N4: the units' factory (module, attribute) the generator moves, and the
#: module it moves to. Only the units move; the methods' `basis_provider` stays.
FACTORY_SWITCH: Final = (
    "openflowsheet.application.revision_binding",
    "MODEL_BUILDERS",
    "openflowsheet.application.model_builders",
)
#: Ruling section 8, B7: the seven group modules the CoolProp fluid table is split into, which
#: the generator attributes to `coolprop-heos-v1`.
B7_PROVIDER: Final = "coolprop-heos-v1"
B7_MODULES: Final = tuple(
    f"src/openflowsheet/thermo/_coolprop_heos_fluids_{group}.py"
    for group in ("a", "b1", "b2", "b3", "b4", "b5", "b6")
)
#: A JSON pointer's value where the document has none.
ABSENT: Final = "(absent)"

#: One F0 log line for a judged key that moved (`corpus_identity.compare`).
F0_KEY_LINE: Final = re.compile(r"^(M[1-9]): (\S+): (?:registered|measured)")

#: F0's measures (`MEASURES`, checked when it is loaded).
MEASURES: Final = ("M1", "M2", "M3", "M4", "M5", "M6", "M7", "M8", "M9")

Facts = dict[str, Any]
Moved = dict[str, set[str]]
#: A revision's built-in registry: the `legacy` and `core` rows, the `digest` record
#: (`tables.sha256`) and the `constant` (`builtin-sha256.txt`), stripped.
Tables = dict[str, Any]


def corpus_identity(root: Path = ROOT) -> Any:
    """F0's module of `root`: the head's in this process, the measured revision's in the facts
    subprocess (loaded there first, so the two never meet in one interpreter)."""
    module = sys.modules.get("corpus_identity")
    if module is None:
        if str(root / "scripts") not in sys.path:
            sys.path.insert(0, str(root / "scripts"))
        module = importlib.import_module("corpus_identity")
    if Path(str(module.__file__)).resolve().parent != (root / "scripts").resolve():
        raise RuntimeError(f"corpus_identity is {module.__file__}, not {root}'s")
    if tuple(module.MEASURES) != MEASURES:
        raise RuntimeError(f"F0 measures {module.MEASURES}, this tool knows {MEASURES}")
    return module


class RuleError(Exception):
    """A rule of section 4 does not hold at the measured revision: nothing is emitted."""


# -- facts at one revision, in a subprocess --------------------------------------------------------


def _relative(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _dotted(path: str) -> str:
    """`src/openflowsheet/a/b.py` -> `openflowsheet.a.b`; a package's `__init__.py` -> it."""
    parts = Path(path).relative_to("src").with_suffix("").parts
    return ".".join(parts[:-1] if parts[-1] == "__init__" else parts)


def measure_facts(root: Path, legacy: Path | None, core: Path | None) -> Facts:
    """Everything the tier rules and the prediction read at `root`, as JSON-ready data. Runs in
    the subprocess, with `root`'s own scripts and package first on `sys.path`."""
    import registry_builtin  # noqa: PLC0415

    f0 = corpus_identity(root)
    held = {"legacy": legacy or registry_builtin.TABLE, "core": core or registry_builtin.CORE_TABLE}
    # F3 (ADR 0061): a root whose generator also writes records.json has S2 compare it too; a
    # root from before F3 has no such table, and its generator yields none.
    records = getattr(registry_builtin, "RECORDS_TABLE", None)
    if records is not None:
        held["records"] = records
    implementation: dict[str, list[str]] = {}
    for name, path in held.items():
        for row in json.loads(Path(path).read_text(encoding="utf-8")):
            implementation[f"{name}:{row['kind']}:{row['id']}"] = sorted(
                f"src/{module}" for module in row["implementation"]["modules"]
            )
    generated: dict[str, list[str]] = {}
    for path, rows in registry_builtin.tables().items():
        for row in rows:
            generated[f"{path.stem}:{row['kind']}:{row['id']}"] = sorted(
                f"src/{module}" for module in row["implementation"]["modules"]
            )
    sites: dict[str, dict[str, Any]] = {}
    for path in sorted((root / "src").rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        if "_implementation_sha256" in text:
            files = f0._hashed_files(path, ast.parse(text, filename=str(path)))
            module = importlib.import_module(_dotted(_relative(root, path)))
            sites[_relative(root, path)] = {
                "provider_id": getattr(module, "PROVIDER_ID", None),
                "files": sorted(_relative(root, file) for file in files),
            }
    prefixes = {
        provider_id: sorted({p.describe().implementation_sha256[:12] for p in providers})
        for provider_id, providers in registry_builtin._providers().items()
    }
    units = f0.legacy_unit_modules()
    unit_hashes = {name: f0.sha256((root / name).read_bytes()) for name in units}
    bundles = f0.V030_BUNDLES
    index = json.loads((bundles / "index.json").read_text(encoding="utf-8"))
    texts = {
        f"{entry['set']}/{entry['name']}": b"".join(
            path.read_bytes()
            for path in sorted((bundles / entry["directory"]).rglob("*"))
            if path.is_file()
        )
        for entry in index["entries"]
        if (bundles / entry["directory"]).is_dir()
    }
    needles = {
        *(prefix for found in prefixes.values() for prefix in found),
        *unit_hashes.values(),
        *(value[:12] for value in unit_hashes.values()),
    }
    return {
        "implementation": implementation,
        "generated": generated,
        "frozen": f0.frozen_modules(),
        "units": units,
        "unit_hashes": unit_hashes,
        "sites": sites,
        "prefixes": prefixes,
        "m6_providers": [provider_id for provider_id, _ in f0.M6_PROVIDERS],
        "registry": json.loads(f0.REGISTRY.read_text(encoding="utf-8")),
        "m6_entries": json.loads(f0.M6_SAMPLE.read_text(encoding="utf-8"))["entries"],
        "bundle_hits": {
            needle: sorted(key for key, data in texts.items() if needle.encode() in data)
            for needle in sorted(needles)
        },
    }


def measure_tables() -> Tables:
    """The registry the generator of the subprocess's revision writes (`--write` in memory)."""
    import registry_builtin  # noqa: PLC0415

    texts = {
        path.stem: registry_builtin.render(rows) for path, rows in registry_builtin.tables().items()
    }
    rows = {stem: json.loads(text) for stem, text in texts.items()}
    return {
        **rows,
        "digest": registry_builtin.digest_record(texts),
        "constant": registry_builtin.registry_constant(rows),
    }


def same_objects(queries: Sequence[Sequence[str]]) -> list[bool]:
    """R4's object-identity test, at the subprocess's revision: `old.name is new.name` for each
    (old module, new module, name). With old equal to new it asks whether `name` is importable
    from that module."""
    found = []
    for old, new, name in queries:
        try:
            left = getattr(importlib.import_module(old), name)
            right = getattr(importlib.import_module(new), name)
        except (ImportError, AttributeError):
            found.append(False)
            continue
        found.append(left is right)
    return found


def _facts_main(arguments: argparse.Namespace) -> int:
    root = Path(arguments.root).resolve()
    sys.path[:0] = [str(root / "scripts"), str(root / "src")]
    corpus_identity(root)
    if arguments.queries:
        result: Any = same_objects(json.loads(Path(arguments.queries).read_text(encoding="utf-8")))
    elif arguments.tables:
        result = measure_tables()
    else:
        result = measure_facts(root, arguments.legacy, arguments.core)
    Path(arguments.out).write_text(json.dumps(result, sort_keys=True), encoding="utf-8")
    return 0


def _subprocess_facts(
    root: Path,
    *,
    legacy: Path | None = None,
    core: Path | None = None,
    queries: Sequence[Sequence[str]] | None = None,
    tables: bool = False,
) -> Any:
    with tempfile.TemporaryDirectory(prefix="w5-identity-") as scratch:
        out = Path(scratch) / "facts.json"
        command = [sys.executable, str(Path(__file__).resolve()), "_facts", "--root", str(root)]
        command += ["--out", str(out)]
        if legacy:
            command += ["--legacy", str(legacy.resolve())]
        if core:
            command += ["--core", str(core.resolve())]
        if queries is not None:
            (Path(scratch) / "queries.json").write_text(json.dumps(queries), encoding="utf-8")
            command += ["--queries", str(Path(scratch) / "queries.json")]
        if tables:
            command += ["--tables"]
        environment = {**os.environ, "PYTHONPATH": str(root / "src")}
        done = subprocess.run(  # noqa: S603
            command, cwd=root, env=environment, capture_output=True, text=True, check=False
        )
        if done.returncode != 0 or not out.is_file():
            raise RuntimeError(f"facts at {root} failed:\n{done.stderr[-4000:]}")
        return json.loads(out.read_text(encoding="utf-8"))


def _git(tree: Path, *arguments: str) -> str:
    done = subprocess.run(  # noqa: S603
        ["git", "-C", str(tree), *arguments],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )
    if done.returncode != 0:
        raise RuntimeError(f"git {' '.join(arguments)}: {done.stderr.strip()}")
    return done.stdout


def resolve(tree: Path, revision: str) -> str:
    return _git(tree, "rev-parse", "--verify", f"{revision}^{{commit}}").strip()


@contextlib.contextmanager
def revision_tree(tree: Path, revision: str) -> Iterator[Path]:
    """`revision`'s `ARCHIVED` paths, extracted into a temporary directory."""
    archive = subprocess.run(  # noqa: S603
        ["git", "-C", str(tree), "archive", revision, *ARCHIVED],  # noqa: S607
        capture_output=True,
        check=True,
    ).stdout
    with tempfile.TemporaryDirectory(prefix="w5-identity-") as scratch:
        with tarfile.open(fileobj=io.BytesIO(archive)) as members:
            members.extractall(scratch, filter="data")
        yield Path(scratch)


def facts_at(
    tree: Path, revision: str | None, legacy: Path | None = None, core: Path | None = None
) -> Facts:
    """The facts of `revision` (extracted), or of `tree`'s working tree when it is None."""
    if revision is None:
        facts: Facts = _subprocess_facts(tree, legacy=legacy, core=core)
        return facts
    with revision_tree(tree, revision) as root:
        facts = _subprocess_facts(root, legacy=legacy, core=core)
        return facts


# -- the sets and the tier rules (section 4) -------------------------------------------------------


def registry_set(facts: Facts) -> list[str]:
    """R: every implementation module of the two held tables."""
    return sorted({module for modules in facts["implementation"].values() for module in modules})


def attribution(facts: Facts) -> dict[str, list[str]]:
    """File -> the provider ids whose `implementation_sha256` hashes it (directly or composed)."""
    found: dict[str, set[str]] = {}
    for site in facts["sites"].values():
        for file in site["files"]:
            found.setdefault(file, set()).add(site["provider_id"])
    return {file: sorted(ids) for file, ids in sorted(found.items())}


def prefix_of(facts: Facts, provider_id: str) -> str:
    (prefix,) = facts["prefixes"][provider_id]
    return str(prefix)


def _registered_values(facts: Facts, measures: Iterable[str]) -> str:
    measured = facts["registry"]["measures"]
    return json.dumps([measured[m] for m in measures], sort_keys=True)


#: The assertions that hold only at a base: after a tier 1 split the held tables lag the
#: generator (S2), and after a tier 3 edit the registered labels lag the code (S4), until K.
BASE_ONLY: Final = ("S2", "S4")


def assertions(facts: Facts, *, step: bool = False) -> dict[str, list[str]]:
    """S1 to S6: assertion -> its failures (empty when it holds). At a step (`step`), S2 and S4
    are not checked (`BASE_ONLY`) and hold no entry."""
    r_set, frozen = set(registry_set(facts)), set(facts["frozen"])
    failures: dict[str, list[str]] = {}
    failures["S1 F subset of R"] = [f"{file} is in F, not in R" for file in sorted(frozen - r_set)]
    held, generated = facts["implementation"], facts["generated"]
    failures["S2 implementation sets equal the generator's"] = [
        f"{key}: held {held.get(key)}, generated {generated.get(key)}"
        for key in sorted(set(held) | set(generated))
        if held.get(key) != generated.get(key)
    ]
    site_ids = {site["provider_id"] for site in facts["sites"].values()}
    attribution_problems = [
        f"{path}: hash site without PROVIDER_ID"
        for path, site in facts["sites"].items()
        if not site["provider_id"]
    ]
    attribution_problems += [
        f"{provider_id}: {len(found)} implementation_sha256 values {found}"
        for provider_id, found in facts["prefixes"].items()
        if len(found) != 1
    ]
    if site_ids - {None} != set(facts["prefixes"]):
        attribution_problems.append(
            f"hash-site providers {sorted(site_ids - {None})} differ from the constructed "
            f"providers {sorted(facts['prefixes'])}"
        )
    attributed = attribution(facts)
    attribution_problems += [
        f"{file}: in F, neither a unit module nor attributed to a provider"
        for file in sorted(frozen - set(facts["units"]) - set(attributed))
    ]
    failures["S3 attribution"] = attribution_problems
    labels: list[str] = []
    for run, value in sorted(facts["registry"]["measures"]["M2"].items()):
        for provider_id, found in facts["prefixes"].items():
            pattern = rf"-{re.escape(provider_id)}-([0-9a-f]{{12}})-"
            for match in re.finditer(pattern, value["model_version"]):
                if [match.group(1)] != found:
                    labels.append(
                        f"M2 {run}: label {provider_id}-{match.group(1)}, the code's {found}"
                    )
    failures["S4 registered labels carry the code's [:12]"] = labels
    registered = _registered_values(facts, ("M2", "M3", "M4", "M5", "M6", "M7", "M8"))
    t2a = []
    for unit, value in facts["unit_hashes"].items():
        for needle in (value, value[:12]):
            if needle in registered:
                t2a.append(f"{unit}: {needle} occurs in a registered M2 to M8 value")
            for bundle in facts["bundle_hits"].get(needle, []):
                t2a.append(f"{unit}: {needle} occurs in M7's corpus, bundle {bundle}")
    failures["S5 T-2a"] = t2a
    partition: list[str] = []
    if not failures["S3 attribution"]:
        tiered = tiers(facts)
        listed = [file for files in tiered.values() for file in files]
        if sorted(listed) != sorted(r_set):
            partition.append(f"tiers hold {len(listed)} files, R {len(r_set)}")
        if set(tiered[2]) | set(tiered[3]) | set(tiered[4]) != frozen & r_set:
            partition.append("tiers 2 to 4 are not F")
        partition += [
            f"{file}: tier {tier}, attributed to no provider"
            for tier in (3, 4)
            for file in tiered[tier]
            if file not in attributed
        ]
    failures["S6 the tiers partition R"] = partition
    if step:
        failures = {name: found for name, found in failures.items() if name[:2] not in BASE_ONLY}
    return failures


def provider_tiers(facts: Facts) -> dict[str, int]:
    """Provider id -> 4 if its `[:12]` occurs in M7's corpus, 3 if in a registered M2
    `model_version` or its id is in `M6_PROVIDERS`, else 2."""
    model_versions = [v["model_version"] for v in facts["registry"]["measures"]["M2"].values()]
    found = {}
    for provider_id in facts["prefixes"]:
        prefix = prefix_of(facts, provider_id)
        if facts["bundle_hits"].get(prefix):
            found[provider_id] = 4
        elif any(prefix in value for value in model_versions):
            found[provider_id] = 3
        elif provider_id in facts["m6_providers"]:
            found[provider_id] = 3
        else:
            found[provider_id] = 2
    return found


def tiers(facts: Facts) -> dict[int, list[str]]:
    """Section 4's tiers of R: a file of F takes the highest tier of the providers it is
    attributed to (2 when none), a file of R outside F is tier 1."""
    by_provider, attributed = provider_tiers(facts), attribution(facts)
    frozen = set(facts["frozen"])
    found: dict[int, list[str]] = {1: [], 2: [], 3: [], 4: []}
    for file in registry_set(facts):
        if file not in frozen:
            found[1].append(file)
        else:
            found[max([2, *(by_provider[p] for p in attributed.get(file, []))])].append(file)
    return found


def checked(facts: Facts, *, step: bool = False) -> None:
    """Raise `RuleError` naming every failed assertion."""
    failed = {name: problems for name, problems in assertions(facts, step=step).items() if problems}
    if failed:
        raise RuleError(
            "; ".join(f"{name}: {', '.join(problems[:5])}" for name, problems in failed.items())
        )


def sets_report(facts: Facts) -> tuple[str, list[str], dict[str, Any]]:
    """The summary line, the listing and the JSON document of `sets` (after `checked`)."""
    r_list, frozen = registry_set(facts), facts["frozen"]
    tiered, attributed = tiers(facts), attribution(facts)
    counts = "/".join(str(len(tiered[t])) for t in (1, 2, 3, 4))
    line = (
        f"sets --check PASS: |R| {len(r_list)}, |F| {len(frozen)}, F subset of R, "
        f"tiers {counts}, T-2a holds ({len(facts['unit_hashes'])} unit hashes)"
    )
    listing = [f"R: {len(r_list)} files; F: {len(frozen)} files; F subset of R"]
    for tier, files in tiered.items():
        listing.append(f"tier {tier} ({TIER_NAMES[tier]}): {len(files)}")
        listing += [
            f"  {file}" + (f"  [{', '.join(attributed[file])}]" if file in attributed else "")
            for file in files
        ]
    document = {
        "R": r_list,
        "F": frozen,
        "tiers": {str(tier): files for tier, files in tiered.items()},
        "providers": attributed,
        "provider_tiers": provider_tiers(facts),
    }
    return line, listing, document


# -- the prediction (section 3.2's reach) ----------------------------------------------------------


def normalise(name: str) -> str:
    """A file named from the repository, the import root or the package -> `src/...`; a file of
    the repository outside the package (the generator, a table) as it is."""
    if name.split("/", 1)[0] in ("src", "scripts", "tests", "benchmarks", "docs"):
        return name
    if name.startswith("openflowsheet/"):
        return f"src/{name}"
    return f"src/openflowsheet/{name}"


def predict(facts: Facts, files: Iterable[str]) -> tuple[Moved, bool]:
    """The registered (measure, key) pairs a comment-only change of `files` moves, and whether
    `registry_sha256` moves. Files outside R move nothing, except B7's group modules, which F0
    measures and the base does not register (M9, section 8)."""
    edited = set(files) & set(registry_set(facts))
    attributed = attribution(facts)
    providers = {p for file in edited for p in attributed.get(file, [])}
    prefixes = {prefix_of(facts, p) for p in providers}
    measures = facts["registry"]["measures"]
    moved: Moved = {measure: set() for measure in MEASURES}
    moved["M9"] = (edited & set(measures["M9"])) | (set(files) & set(B7_MODULES))
    moved["M2"] = {
        run
        for run, value in measures["M2"].items()
        if any(prefix in value["model_version"] for prefix in prefixes)
    }
    moved["M3"] = moved["M2"] & set(measures["M3"])
    samples = {
        name
        for name, entry in facts["m6_entries"].items()
        if entry["provider_id"] in providers
        or any(prefix in json.dumps(entry, sort_keys=True) for prefix in prefixes)
    }
    sampled_runs = {name.rsplit("#", 1)[0] for name in samples if "#" in name}
    moved["M6"] = {corpus_identity().M6_SAMPLE_PREFIX + name for name in samples} | {
        run
        for run, value in measures["M6"].items()
        if not run.startswith(corpus_identity().M6_SAMPLE_PREFIX)
        and value["n_keys"]
        and (run in moved["M2"] or run in sampled_runs)
    }
    moved["M7"] = {bundle for prefix in prefixes for bundle in facts["bundle_hits"].get(prefix, [])}
    return moved, bool(edited)


def f0_line(facts: Facts, moved: Moved) -> str:
    """The summary line an unpinned F0 `--check` prints when exactly `moved` moved."""
    results = {}
    for measure in MEASURES:
        n = corpus_identity()._coverage(measure, facts["registry"]["measures"][measure])
        count = len(moved[measure])
        results[measure] = {"status": "FAIL" if count else "PASS", "n": n, "failed": count}
    line: str = corpus_identity().summary(results)[1]
    return line


def log_moved(log: Path) -> tuple[str, Moved]:
    """An F0 `--check` log's summary line and its moved (measure, key) pairs."""
    lines = log.read_text(encoding="utf-8").splitlines()
    moved: Moved = {measure: set() for measure in MEASURES}
    for line in lines[1:]:
        match = F0_KEY_LINE.match(line)
        if match:
            moved[match.group(1)].add(match.group(2))
    return lines[0], moved


def differences(predicted: Moved, actual: Moved, verb: str) -> list[str]:
    """Both directions of a set comparison per measure."""
    found = []
    for measure in MEASURES:
        found += [
            f"{measure}: {key}: {verb}, not predicted"
            for key in sorted(actual[measure] - predicted[measure])
        ]
        found += [
            f"{measure}: {key}: predicted, not {verb}"
            for key in sorted(predicted[measure] - actual[measure])
        ]
    return found


def refusals(facts: Facts, files: Iterable[str], moved: Moved, max_tier: int) -> list[str]:
    """R1's refusals of an E: a tier 4 file, a file above `max_tier`, a nonempty M7 prediction
    (M7 is never re-registered in W5; a step that moves it goes to the design lane)."""
    tier_of = {file: tier for tier, found in tiers(facts).items() for file in found}
    problems = []
    for name in sorted(set(files)):
        tier = tier_of.get(name)
        if tier == 4:
            problems.append(f"{name}: tier 4 ({TIER_NAMES[4]}), refused by R1")
        elif tier is not None and tier > max_tier:
            problems.append(
                f"{name}: tier {tier} ({TIER_NAMES[tier]}), above --max-tier {max_tier}"
            )
    if moved["M7"]:
        problems.append(f"M7: {len(moved['M7'])} key(s) predicted to move, refused by R1")
    return problems


def counts(moved: Moved) -> str:
    return ", ".join(f"{m} {len(keys)}" for m, keys in moved.items() if keys) or "none"


# -- the registry tables (W5-S4, W5-K2) -----------------------------------------------------------


def _utf8_sorted(modules: Iterable[str]) -> list[str]:
    return sorted(modules, key=lambda path: path.encode("utf-8"))


def predict_tables(
    tables: Tables, files: Iterable[str], base_files: set[str], head_files: set[str]
) -> tuple[dict[str, Any], dict[str, str]]:
    """The table pointers E moves, by ruling 6.2 W5-S4: pointer -> its expected value, and the
    pointers whose value the ruling leaves open -> why. `base_files` and `head_files` are the
    revisions' file lists (an added or removed file of E). A pointer is `<table>.json:<pointer>`.

    - A contributor's implementation `modules` (`core.json`): every `*.py` under the directory of
      its factory's module (the generator's D6 rule), so a tier 1 split that adds or removes a
      module there moves it, to B's set plus the added minus the removed.
    - `coolprop-heos-v1`'s implementation `modules` (B7, section 8): plus its seven group modules.
    - With the generator in E (WO-N4): the units' factory `module`, to `FACTORY_SWITCH`'s target.
    - A file of R removed outside those rules: its rows' `modules`, open.
    """
    files = set(files)
    added = {f for f in files if f not in base_files and f in head_files}
    removed = {f for f in files if f in base_files and f not in head_files}
    expected: dict[str, Any] = {}
    for index, row in enumerate(tables["core"]):
        modules = set(row["implementation"]["modules"])
        home = row["implementation"]["factory"]["module"].replace(".", "/")
        directory = f"src/{home.rsplit('/', 1)[0]}/"
        if f"{home}/__init__.py" in modules:
            directory = f"src/{home}/"
        inside = {f.removeprefix("src/") for f in added | removed if f.startswith(directory)}
        inside = {f for f in inside if f.endswith(".py")}
        if inside:
            gained = {f.removeprefix("src/") for f in added} & inside
            expected[f"core.json:/{index}/implementation/modules"] = _utf8_sorted(
                (modules | gained) - {f.removeprefix("src/") for f in removed}
            )
    for index, row in enumerate(tables["legacy"]):
        groups = {f.removeprefix("src/") for f in added if f in B7_MODULES}
        if row["id"] == B7_PROVIDER and groups:
            expected[f"legacy.json:/{index}/implementation/modules"] = _utf8_sorted(
                {*row["implementation"]["modules"], *groups}
            )
    still_open: dict[str, str] = {}
    for stem in TABLES:
        for index, row in enumerate(tables[stem]):
            pointer = f"{stem}.json:/{index}/implementation/modules"
            gone = sorted(m for m in row["implementation"]["modules"] if f"src/{m}" in removed)
            if gone and pointer not in expected:
                still_open[pointer] = f"{', '.join(gone)} removed; the ruling admits no such move"
    if GENERATOR in files:
        source, attribute, target = FACTORY_SWITCH
        for index, row in enumerate(tables["legacy"]):
            factory = row["implementation"]["factory"]
            if factory and (factory["module"], factory["attribute"]) == (source, attribute):
                expected[f"legacy.json:/{index}/implementation/factory/module"] = target
    return expected, still_open


def at_pointer(document: Any, pointer: str) -> Any:
    """The value at a JSON pointer, `ABSENT` where there is none."""
    value = document
    for part in pointer.split("/")[1:]:
        part = part.replace("~1", "/").replace("~0", "~")
        if isinstance(value, list) and part.isdigit() and int(part) < len(value):
            value = value[int(part)]
        elif isinstance(value, dict) and part in value:
            value = value[part]
        else:
            return ABSENT
    return value


def table_problems(
    expected: Mapping[str, Any],
    still_open: Mapping[str, str],
    registry: bool,
    before: Tables,
    after: Tables,
) -> list[str]:
    """W5-S4 (AFTER regenerated at a step) and W5-K2's table half (AFTER committed at K), both
    ways: every pointer at which the tables differ lies under a predicted one, every predicted
    pointer holds its expected value, an open one fails, `tables.sha256` moves exactly when a
    table pointer is predicted and `builtin-sha256.txt` exactly when `registry`."""
    corpus_identity()  # this tree's scripts on `sys.path`
    import registry_builtin  # noqa: PLC0415

    problems = [f"{pointer}: unpredicted ({why})" for pointer, why in sorted(still_open.items())]
    predicted = {*expected, *still_open}
    for stem in TABLES:
        for pointer in registry_builtin.differences(before[stem], after[stem]):
            name = f"{stem}.json:{pointer}"
            if not any(name == p or name.startswith(f"{p}/") for p in predicted):
                problems.append(f"{name}: moved, not predicted")
    for name, value in sorted(expected.items()):
        stem, pointer = name.split(".json:", 1)
        old, new = at_pointer(before[stem], pointer), at_pointer(after[stem], pointer)
        if new == old:
            problems.append(f"{name}: predicted, not moved")
        elif new != value:
            problems.append(f"{name}: predicted {json.dumps(value)}, found {json.dumps(new)}")
    for label, key, moves in (
        ("tables.sha256", "digest", bool(predicted)),
        ("builtin-sha256.txt", "constant", registry),
    ):
        changed = before[key] != after[key]
        if changed != moves:
            problems.append(
                f"{label}: {'moved, not predicted' if changed else 'predicted, not moved'}"
            )
    return problems


def held_tables(tree: Path, revision: str) -> Tables:
    """The built-in registry committed at `revision`."""
    rows = {
        stem: json.loads(_git(tree, "show", f"{revision}:{path}"))
        for stem, path in TABLE_FILES.items()
    }
    return {
        **rows,
        "digest": _git(tree, "show", f"{revision}:{DIGEST_FILE}"),
        "constant": _git(tree, "show", f"{revision}:{REGISTRY_CONSTANT}").strip(),
    }


def tracked(tree: Path, revision: str) -> set[str]:
    return set(_git(tree, "ls-tree", "-r", "--name-only", revision).split())


def table_lines(expected: Mapping[str, Any], still_open: Mapping[str, str]) -> list[str]:
    lines = [f"TABLE {pointer}: {json.dumps(value)}" for pointer, value in sorted(expected.items())]
    return lines + [f"TABLE {pointer}: open" for pointer in sorted(still_open)]


# -- judge (W5-K2) ---------------------------------------------------------------------------------


def registry_moved(before: Mapping[str, Any], after: Mapping[str, Any]) -> Moved:
    """The (measure, key) pairs whose registered value differs, JSON-equal otherwise; a key
    present on one side only counts as moved."""
    moved: Moved = {}
    missing = object()
    for measure in MEASURES:
        old = before["measures"].get(measure, {})
        new = after["measures"].get(measure, {})
        moved[measure] = {
            key for key in set(old) | set(new) if old.get(key, missing) != new.get(key, missing)
        }
    return moved


def judge(before: Mapping[str, Any], after: Mapping[str, Any], predicted: Moved) -> list[str]:
    """W5-K2's problems (empty: PASS)."""
    problems = [
        f"{field}: changed" for field in REGISTRY_FIELDS if before.get(field) != after.get(field)
    ]
    return problems + differences(predicted, registry_moved(before, after), "moved")


# -- coverage (R4, W5-S7) --------------------------------------------------------------------------


def m9_key_set(
    base: Iterable[str], head: Iterable[str], changed: Iterable[str]
) -> tuple[bool, str]:
    """W5-S7's M9 rule: HEAD's key set is BASE's plus the B7 group modules in `changed` (the
    ruling's one exception, scoped as `predict` scopes it); the verdict and its summary part."""
    before, after = set(base), set(head)
    b7 = set(changed) & set(B7_MODULES) - before
    if after == before:
        return True, f"equal to base ({len(after)})"
    if after == before | b7:
        return True, f"equal to base plus {len(b7)} B7 group module(s) ({len(after)})"
    return False, (
        f"DIFFERS: added {sorted(after - before)}, removed {sorted(before - after)} ({len(after)})"
    )


def import_edges(root: Path, name: str) -> set[tuple[str, str | None]]:
    """(module file, name) of every `openflowsheet` import in `root / name`, anywhere in the
    file; name None for an imported module (a submodule taken by `from`, or `import`)."""
    path = root / name
    package = root / "src"

    def module_file(target: Path) -> str | None:
        for candidate in (target.with_suffix(".py"), target / "__init__.py"):
            if candidate.is_file():
                return _relative(root, candidate)
        return None

    found: set[tuple[str, str | None]] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"), filename=str(path))):
        if isinstance(node, ast.ImportFrom):
            if node.level:
                base = path.parent
                for _ in range(node.level - 1):
                    base = base.parent
                target = base.joinpath(*(node.module.split(".") if node.module else []))
            elif node.module and node.module.split(".")[0] == "openflowsheet":
                target = package.joinpath(*node.module.split("."))
            else:
                continue
            for alias in node.names:
                submodule = module_file(target / alias.name)
                if submodule is not None:
                    found.add((submodule, None))
                    continue
                parent = module_file(target)
                if parent is None:
                    raise RuleError(f"{name}:{node.lineno}: {node.module} does not resolve")
                found.add((parent, alias.name))
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] == "openflowsheet":
                    resolved = module_file(package.joinpath(*alias.name.split(".")))
                    if resolved is None:
                        raise RuleError(f"{name}:{node.lineno}: {alias.name} does not resolve")
                    found.add((resolved, None))
    return found


def hash_scope(head: Facts, file: str) -> set[str]:
    """The files every identity holding `file` hashes at head (their intersection): provider
    hash sets, a unit's own `artifact_hash`, the regenerated registry implementation sets."""
    identities = [set(site["files"]) for site in head["sites"].values() if file in site["files"]]
    identities += [{file}] if file in head["units"] else []
    identities += [set(m) for m in head["generated"].values() if file in m]
    if not identities:
        return {file}
    scope = set.intersection(*identities)
    return scope | {file}


def new_edges(
    edited: Sequence[str], base_root: Path, head_root: Path, head: Facts
) -> tuple[
    list[tuple[str, str, list[str]]],
    list[tuple[str, str, str, str]],
    list[tuple[str, str, str]],
]:
    """Per edited file, its new (module, name) import pairs outside its scope, sorted three ways:
    the holes (file, module, names); the retarget candidates (file, name, old module, new module)
    of a module the file did not import at base, whose names all came from a module at base; and
    the new names (file, module, name) taken from a module the file did import at base, each
    admitted only if it was importable from that module at base. A module newly taken whole
    (name None) is a hole either way: every later name of it would be reachable."""
    holes: list[tuple[str, str, list[str]]] = []
    candidates: list[tuple[str, str, str, str]] = []
    names_taken: list[tuple[str, str, str]] = []
    for file in edited:
        before = import_edges(base_root, file)
        after = import_edges(head_root, file) if (head_root / file).is_file() else set()
        scope = hash_scope(head, file)
        old_modules = {module for module, _ in before}
        for module in sorted({m for m, _ in after - before} - scope):
            taken = {n for m, n in after - before if m == module}
            names = sorted(n for n in taken if n is not None)
            if module in old_modules:
                if None in taken:
                    holes.append((file, module, [*names, "(module)"]))
                else:
                    names_taken += [(file, module, n) for n in names]
                continue
            sources = {n: sorted(m for m, old in before if old == n) for n in names}
            if None in taken or not all(sources[n] for n in names):
                holes.append((file, module, [*names, *(["(module)"] if None in taken else [])]))
                continue
            candidates += [(file, n, source, module) for n in names for source in sources[n]]
    return holes, candidates, names_taken


def importable(
    holes: list[tuple[str, str, list[str]]],
    names_taken: Sequence[tuple[str, str, str]],
    found: Sequence[bool],
) -> tuple[list[tuple[str, str, list[str]]], list[tuple[str, str, str]]]:
    """Split the new names of an already imported module by `found` (the name was importable
    from that module at base): admitted, or a hole of its (file, module)."""
    missing: dict[tuple[str, str], list[str]] = {}
    admitted = []
    for entry, ok in zip(names_taken, found, strict=True):
        if ok:
            admitted.append(entry)
        else:
            missing.setdefault(entry[:2], []).append(entry[2])
    holes += [(file, module, sorted(names)) for (file, module), names in sorted(missing.items())]
    return holes, admitted


def retargets(
    holes: list[tuple[str, str, list[str]]],
    candidates: Sequence[tuple[str, str, str, str]],
    same: Sequence[bool],
) -> tuple[list[tuple[str, str, list[str]]], list[tuple[str, str, str, str]]]:
    """Split the candidates by R4's object-identity test at base: an edge (file, module) is a
    retarget when each of its names has a source M0 with `M0.n is M.n`; else it is a hole."""
    edges: dict[tuple[str, str], dict[str, tuple[str, str, str, str] | None]] = {}
    for candidate, ok in zip(candidates, same, strict=True):
        file, name, _, module = candidate
        chosen = edges.setdefault((file, module), {})
        if chosen.get(name) is None:
            chosen[name] = candidate if ok else None
    listed: list[tuple[str, str, str, str]] = []
    for (file, module), chosen in sorted(edges.items()):
        found = [c for c in chosen.values() if c is not None]
        if len(found) == len(chosen):
            listed += sorted(found)
        else:
            holes.append((file, module, sorted(chosen)))
    return holes, listed


# -- the command line ------------------------------------------------------------------------------


def _write_json(path: Path | None, document: Any) -> None:
    if path:
        path.write_text(json.dumps(document, indent=1, sort_keys=True) + "\n", encoding="utf-8")


def command_sets(arguments: argparse.Namespace, tree: Path) -> int:
    base = resolve(tree, arguments.base) if arguments.base else None
    facts = facts_at(tree, base, legacy=arguments.legacy, core=arguments.core)
    try:
        checked(facts, step=arguments.step)
    except RuleError as error:
        print(f"sets --check FAIL: {error}")
        return 1
    line, listing, document = sets_report(facts)
    if arguments.step:
        line = line.replace("PASS: ", f"PASS at a step ({', '.join(BASE_ONLY)} not checked): ", 1)
    if not arguments.check:
        print("\n".join(listing))
    _write_json(arguments.json, {"base": base, **document})
    print(line)
    return 0


def _edited(tree: Path, base: str, files: Sequence[str] | None, head: str = "HEAD") -> list[str]:
    if files is not None:
        return sorted({normalise(name) for name in files})
    return sorted(_git(tree, "diff", "--name-only", f"{base}..{head}").split())


def tables_at(tree: Path, revision: str) -> Tables:
    """The registry `revision`'s generator writes, measured on an extracted copy."""
    with revision_tree(tree, revision) as root:
        tables: Tables = _subprocess_facts(root, tables=True)
        return tables


def _table_part(expected: Mapping[str, Any], still_open: Mapping[str, str]) -> str:
    n = len(expected) + len(still_open)
    return f"; tables {n} pointer(s)" if n else ""


def command_predict(arguments: argparse.Namespace, tree: Path) -> int:
    base = resolve(tree, arguments.base)
    facts = facts_at(tree, base)
    try:
        checked(facts)
    except RuleError as error:
        print(f"predict FAIL: the base's rules fail: {error}")
        return 1
    files = _edited(tree, base, arguments.files)
    r_set = set(registry_set(facts))
    moved, edited = predict(facts, files)
    refused = refusals(facts, files, moved, arguments.max_tier)
    if refused:
        for problem in refused:
            print(f"REFUSED {problem}")
        print(f"predict FAIL: E refused ({len(refused)} problem(s))")
        return 1
    base_tables = held_tables(tree, base)
    expected, still_open = predict_tables(
        base_tables, files, tracked(tree, base), tracked(tree, "HEAD")
    )
    registry = edited or bool(expected) or bool(still_open)
    line = f"predicted {f0_line(facts, moved)}"
    for name in files:
        print(f"{'E' if name in r_set else 'not in R (moves nothing)'}: {name}")
    for measure, keys in moved.items():
        for key in sorted(keys):
            print(f"{measure}: {key}")
    for table_line in table_lines(expected, still_open):
        print(table_line)
    print(f"registry: {REGISTRY_CONSTANT} {'moves' if registry else 'unchanged'}")
    print(f"registry: {DIGEST_FILE} {'moves' if expected or still_open else 'unchanged'}")
    _write_json(
        arguments.json,
        {
            "base": base,
            "files": files,
            "moved": {m: sorted(keys) for m, keys in moved.items()},
            "registry_sha256_moves": registry,
            "f0_line": line.removeprefix("predicted "),
            "tables": expected,
            "tables_open": still_open,
            "tables_sha256_moves": bool(expected or still_open),
        },
    )
    checks: list[str] = []
    problems: list[str] = []
    held_line = ""
    if arguments.against_log is not None:
        checks.append("--against-log")
        held_line, actual = log_moved(arguments.against_log)
        problems += differences(moved, actual, "moved")
        if held_line != line.removeprefix("predicted "):
            problems.append(f"summary line: log {held_line!r}, predicted {line!r}")
    if arguments.against_tables:
        checks.append("--against-tables")
        problems += table_problems(
            expected, still_open, registry, base_tables, tables_at(tree, "HEAD")
        )
    else:
        problems += [f"{pointer}: unpredicted ({why})" for pointer, why in still_open.items()]
    for problem in problems:
        print(problem)
    tables = _table_part(expected, still_open)
    if not checks:
        if problems:
            print(f"predict FAIL: {len(problems)} unpredicted table pointer(s); {line}")
            return 1
        print(f"predict: base {base[:12]}, |E| {len(set(files) & r_set)}; {line}{tables}")
        return 0
    verdict = "PASS" if not problems else f"FAIL ({len(problems)} difference(s))"
    log = f"; log {held_line}" if arguments.against_log is not None else ""
    print(f"predict {' '.join(checks)} {verdict}: {counts(moved)}{tables}{log}")
    return 0 if not problems else 1


def command_judge(arguments: argparse.Namespace, tree: Path) -> int:
    before, after = resolve(tree, arguments.before), resolve(tree, arguments.after)
    facts = facts_at(tree, before)
    try:
        checked(facts)
    except RuleError as error:
        print(f"judge FAIL: the base's rules fail: {error}")
        return 1
    files = _edited(tree, before, arguments.files, after)
    predicted, edited = predict(facts, files)
    refused = refusals(facts, files, predicted, arguments.max_tier)
    if refused:
        for problem in refused:
            print(f"REFUSED {problem}")
        print(f"judge FAIL: E refused ({len(refused)} problem(s))")
        return 1
    base_tables = held_tables(tree, before)
    expected, still_open = predict_tables(
        base_tables, files, tracked(tree, before), tracked(tree, after)
    )
    registry = edited or bool(expected) or bool(still_open)
    held = json.loads(_git(tree, "show", f"{after}:{CORPUS_FILE}"))
    problems = judge(facts["registry"], held, predicted)
    problems += table_problems(
        expected, still_open, registry, base_tables, held_tables(tree, after)
    )
    for problem in problems:
        print(problem)
    n_edited = len(set(files) & set(registry_set(facts)))
    verdict = "PASS" if not problems else f"FAIL ({len(problems)} problem(s))"
    print(
        f"judge {verdict}: {before[:12]}..{after[:12]}, |E| {n_edited}; "
        f"predicted {counts(predicted)}{_table_part(expected, still_open)}"
    )
    return 0 if not problems else 1


def command_coverage(arguments: argparse.Namespace, tree: Path) -> int:
    base = resolve(tree, arguments.base)
    head = resolve(tree, arguments.head) if arguments.head else None
    with contextlib.ExitStack() as stack:
        base_root = stack.enter_context(revision_tree(tree, base))
        head_root = tree if head is None else stack.enter_context(revision_tree(tree, head))
        before = _subprocess_facts(base_root)
        after = _subprocess_facts(head_root)
        changed = set(_git(tree, "diff", "--name-only", base, *([head] if head else [])).split())
        edited = sorted(changed & set(registry_set(before)))
        holes, candidates, names_taken = new_edges(edited, base_root, head_root, after)
        queries = [[_dotted(old), _dotted(new), name] for _, name, old, new in candidates]
        queries += [[_dotted(module), _dotted(module), name] for _, module, name in names_taken]
        same = _subprocess_facts(base_root, queries=queries) if queries else []
    holes, listed = retargets(holes, candidates, same[: len(candidates)])
    holes, admitted = importable(holes, names_taken, same[len(candidates) :])
    for file, module, names in holes:
        print(f"EDGE {file} -> {module} ({', '.join(str(n) for n in names)}): outside its scope")
    for file, name, old, new in listed:
        print(f"RETARGET {file}: {name} from {_dotted(old)} -> {_dotted(new)}")
    for file, module, name in admitted:
        print(f"NAME {file}: {name} from {_dotted(module)}, importable from it at base")
    m9_holds, m9 = m9_key_set(before["frozen"], after["frozen"], changed)
    print(
        f"coverage: {len(holes)} new edge(s) outside a hash scope, {len(listed)} retarget(s), "
        f"{len(edited)} edited hashed file(s); M9 key set {m9}"
    )
    return 0 if not holes and m9_holds else 1


# -- the identity pin (R2, W5-S2, W5-T3 to W5-T5) -------------------------------------------------

#: W5-T5's identity sites, measured at 8d31b89e: (file, function) of each function that reads a
#: hashed file's bytes for a registered identity. Every provider's `_implementation_sha256`, the
#: two Wilson constructors, `registry.selfhash.file_sha` and `corpus_identity.m9`.
PIN_SITES: Final = (
    ("scripts/corpus_identity.py", "m9"),
    ("src/openflowsheet/registry/selfhash.py", "file_sha"),
    ("src/openflowsheet/thermo/coolprop_heos.py", "_implementation_sha256"),
    ("src/openflowsheet/thermo/iapws95.py", "_implementation_sha256"),
    ("src/openflowsheet/thermo/pr_c1.py", "_implementation_sha256"),
    ("src/openflowsheet/thermo/pr_lib.py", "_implementation_sha256"),
    ("src/openflowsheet/thermo/syn001.py", "_implementation_sha256"),
    ("src/openflowsheet/thermo/wilson_ig.py", "WilsonIdealGasProvider.__init__"),
    ("src/openflowsheet/thermo/wilson_ig_v2.py", "WilsonIdealGasProviderV2.__init__"),
)
#: The one site that is a site only by its caller: `canonical.file_sha256` called from a unit's
#: `_artifact_hash`, in the 22 c1 and syn001 unit modules and the thermal units' common helper.
PIN_UNIT_READER: Final = ("src/openflowsheet/canonical.py", "file_sha256")
PIN_UNIT_HASH: Final = "_artifact_hash"
PIN_UNIT_CALLERS: Final = (
    *(
        f"src/openflowsheet/models/c1/{name}.py"
        for name in ("feed", "flash", "heater", "mixer", "reactor", "reactor_standin", "sink")
    ),
    "src/openflowsheet/models/c1/splitter.py",
    *(
        f"src/openflowsheet/models/syn001/{name}.py"
        for name in (
            "column_unit",
            "component_separator",
            "conversion_reactor",
            "feed",
            "flash",
            "heat_exchanger",
            "heater",
            "kinetic_cstr",
            "mixer",
            "ph_flash",
            "pump",
            "sink",
            "splitter",
            "valve",
        )
    ),
    "src/openflowsheet/models/thermal/common.py",
)
#: `pin`'s exit code when the pin itself fails (W5-T5): a pinned path never read, a foreign read.
PIN_FAILED: Final = 3
#: The CoolProp files that B7 gives a new hash scope (W5-S2's exception from the B7 step on).
COOLPROP_FILES: Final = (
    "src/openflowsheet/thermo/_coolprop_heos_fluids.py",
    "src/openflowsheet/thermo/coolprop_heos.py",
)
#: A comprehension's frame name inside its function (Python before 3.12 gives it a frame).
_COMPREHENSION: Final = re.compile(r"\.<locals>\.<(?:listcomp|dictcomp|setcomp|genexpr)>$")


def _blob(tree: Path, revision: str, path: str) -> bytes:
    done = subprocess.run(  # noqa: S603
        ["git", "-C", str(tree), "show", f"{revision}:{path}"],  # noqa: S607
        capture_output=True,
        check=False,
    )
    if done.returncode != 0:
        raise RuntimeError(f"git show {revision[:12]}:{path}: {done.stderr.decode().strip()}")
    return done.stdout


def pin_plan(
    base: Facts, head: Facts, files: Iterable[str], present: set[str]
) -> tuple[list[str], list[str]]:
    """(pinned, unpinned) of E = `files` ∩ R at the base: a file is pinned iff it is `present` at
    head and its hash scope (`hash_scope`) is the one it had at the base. A new scope (B7) has no
    base form, so its files are left to the head."""
    edited = sorted(set(files) & set(registry_set(base)))
    pinned: list[str] = []
    unpinned: list[str] = []
    for file in edited:
        same = file in present and hash_scope(base, file) == hash_scope(head, file)
        (pinned if same else unpinned).append(file)
    return pinned, unpinned


class Pin:
    """Serves the base bytes of the pinned files to every binary `pathlib` read (`Path.open` in a
    binary read mode, `Path.read_bytes`), and records each such read with its caller: the first
    frame outside `pathlib` and this module, and the frame that called it. Imports do not read
    through `pathlib`, so the head's code runs. `registry` serves F0's registry (any read mode)
    from another revision's bytes (W5-K5)."""

    def __init__(
        self, root: Path, served: Mapping[str, bytes], registry: tuple[str, bytes] | None = None
    ) -> None:
        self.root = root.resolve()
        self.served = {os.path.realpath(self.root / name): data for name, data in served.items()}
        self.names = {os.path.realpath(self.root / name): name for name in served}
        self.registry = None
        if registry is not None:
            self.registry = (os.path.realpath(self.root / registry[0]), registry[1])
            self.names[self.registry[0]] = registry[0]
        self.reads: dict[tuple[str, str], int] = {}

    def _relative(self, filename: str) -> str:
        path = os.path.realpath(filename)
        inside = path.startswith(str(self.root) + os.sep)
        return Path(path).relative_to(self.root).as_posix() if inside else filename

    def _frame(self, frame: Any) -> Any:
        while frame is not None and (
            frame.f_globals.get("__name__", "").partition(".")[0] == "pathlib"
            or frame.f_code.co_filename == __file__
        ):
            frame = frame.f_back
        return frame

    def where(self, frame: Any) -> tuple[str, str]:
        """`file:function` of the reading frame, the same of its caller ("" at the bottom)."""
        names = []
        for _ in range(2):
            frame = self._frame(frame)
            if frame is None:
                names.append("")
                break
            qualname = _COMPREHENSION.sub("", frame.f_code.co_qualname)
            names.append(f"{self._relative(frame.f_code.co_filename)}:{qualname}")
            frame = frame.f_back
        return names[0], names[1] if len(names) > 1 else ""

    def serve(self, path: Any, mode: str) -> bytes | None:
        """The bytes a read of `path` in `mode` gets, or None to read the file itself."""
        real = os.path.realpath(path)
        if self.registry is not None and real == self.registry[0] and "r" in mode:
            data: bytes | None = self.registry[1]
        elif real in self.served and "b" in mode and not set(mode) & set("wax+"):
            data = self.served[real]
        else:
            return None
        reader, caller = self.where(sys._getframe(1))  # noqa: SLF001
        key = (self.names[real], f"{reader}<-{caller}")
        self.reads[key] = self.reads.get(key, 0) + 1
        return data

    @contextlib.contextmanager
    def installed(self) -> Iterator[Pin]:
        import pathlib  # noqa: PLC0415

        original_open, original_read_bytes = pathlib.Path.open, pathlib.Path.read_bytes
        pin = self

        def open_(  # noqa: PLR0913
            path: pathlib.Path,
            mode: str = "r",
            buffering: int = -1,
            encoding: str | None = None,
            errors: str | None = None,
            newline: str | None = None,
        ) -> Any:
            data = pin.serve(path, mode)
            if data is None:
                return original_open(path, mode, buffering, encoding, errors, newline)
            if "b" in mode:
                return io.BytesIO(data)
            return io.TextIOWrapper(
                io.BytesIO(data),
                encoding=io.text_encoding(encoding),
                errors=errors,
                newline=newline,
            )

        def read_bytes(self: pathlib.Path) -> bytes:
            data = pin.serve(self, "rb")
            return original_read_bytes(self) if data is None else data

        pathlib.Path.open = open_  # type: ignore[assignment,method-assign]
        pathlib.Path.read_bytes = read_bytes  # type: ignore[method-assign]
        try:
            yield self
        finally:
            pathlib.Path.open = original_open  # type: ignore[method-assign]
            pathlib.Path.read_bytes = original_read_bytes  # type: ignore[method-assign]


def is_site(caller: str) -> bool:
    """Whether a recorded `reader<-caller` is one of W5-T5's identity sites."""
    reader, _, outer = caller.partition("<-")
    if tuple(reader.rsplit(":", 1)) in PIN_SITES:
        return True
    unit, _, function = outer.rpartition(":")
    return (
        tuple(reader.rsplit(":", 1)) == PIN_UNIT_READER
        and function == PIN_UNIT_HASH
        and unit in PIN_UNIT_CALLERS
    )


def run_script(tree: Path, command: Sequence[str]) -> int:
    """`command` (a script of `tree` and its arguments) in this process, as `python SCRIPT ...`
    with `PYTHONPATH=<tree>/src` runs it; its exit status."""
    script = (tree / command[0]).resolve()
    if script.suffix != ".py" or not script.is_file():
        raise RuntimeError(f"pin runs a Python script of the tree, not {command[0]!r}")
    for name in ("openflowsheet", "corpus_identity"):
        if name in sys.modules:
            raise RuntimeError(f"{name} is imported before the pinned command runs")
    source = str(tree.resolve() / "src")
    environment = os.environ.get("PYTHONPATH")
    os.environ["PYTHONPATH"] = os.pathsep.join([source, *([environment] if environment else [])])
    sys.argv = [str(script), *command[1:]]
    sys.path[:1] = [str(script.parent), source]
    os.chdir(tree)
    try:
        runpy.run_path(str(script), run_name="__main__")
    except SystemExit as stop:
        if stop.code is None or isinstance(stop.code, int):
            return stop.code or 0
        print(stop.code, file=sys.stderr)
        return 1
    return 0


def command_pin(arguments: argparse.Namespace, tree: Path) -> int:
    base = resolve(tree, arguments.base)
    command = list(arguments.argv)
    if command[:1] == ["--"]:
        command = command[1:]
    if not command:
        raise RuntimeError("pin: no command after --")
    files = sorted(_git(tree, "diff", "--name-only", base).split())
    with revision_tree(tree, base) as base_root:
        before = _subprocess_facts(base_root)
    after = _subprocess_facts(tree)
    pinned, unpinned = pin_plan(before, after, files, {f for f in files if (tree / f).is_file()})
    added = [f for f in files if f in B7_MODULES]
    registry = None
    if arguments.registry:
        revision = resolve(tree, arguments.registry)
        registry = (CORPUS_FILE, _blob(tree, revision, CORPUS_FILE))
    pin = Pin(tree, {name: _blob(tree, base, name) for name in pinned}, registry)
    sys.stdout.flush()
    with pin.installed():
        code = run_script(tree, command)
    sys.stdout.flush()
    for name in unpinned:
        print(f"PIN UNPINNED {name} (hash scope changed since {base[:12]})")
    for (name, caller), n in sorted(pin.reads.items()):
        print(f"PIN {'REGISTRY' if name == CORPUS_FILE else 'READ'} {name} {caller} x{n}")
    read = {name for name, _ in pin.reads}
    vacuous = [name for name in pin.names.values() if name not in read]
    foreign = sorted(
        (name, caller) for name, caller in pin.reads if name != CORPUS_FILE and not is_site(caller)
    )
    for name in sorted(vacuous):
        print(f"PIN VACUOUS {name}")
    for name, caller in foreign:
        print(f"PIN FOREIGN READ {name} {caller}")
    _write_json(
        arguments.json,
        {
            "base": base,
            "files": files,
            "pinned": pinned,
            "unpinned": unpinned,
            "moved_files": [*unpinned, *added],
            "registry": arguments.registry,
            "reads": [
                {"path": name, "caller": caller, "count": n, "site": is_site(caller)}
                for (name, caller), n in sorted(pin.reads.items())
            ],
            "vacuous": sorted(vacuous),
            "foreign": [list(pair) for pair in foreign],
            "exit": code,
        },
    )
    failed = bool(vacuous or foreign)
    sites = {caller for name, caller in pin.reads if name != CORPUS_FILE}
    print(
        f"pin {'FAIL' if failed else 'PASS'}: base {base[:12]}, |E| {len(pinned) + len(unpinned)}, "
        f"pinned {len(pinned)} ({sum(pin.reads.values())} read(s) from {len(sites)} caller(s)), "
        f"unpinned {len(unpinned)}, vacuous {len(vacuous)}, foreign {len(foreign)}; "
        f"command exit {code}"
    )
    return PIN_FAILED if failed else code


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n", 1)[0])
    parser.add_argument("--tree", type=Path, default=ROOT, help="the head tree (default: this one)")
    commands = parser.add_subparsers(dest="command", required=True)
    sets = commands.add_parser("sets")
    sets.add_argument("--check", action="store_true")
    sets.add_argument(
        "--step", action="store_true", help="the revision is a step, not a base: skip S2 and S4"
    )
    sets.add_argument("--base")
    sets.add_argument("--legacy", type=Path)
    sets.add_argument("--core", type=Path)
    sets.add_argument("--json", type=Path)
    prediction = commands.add_parser("predict")
    prediction.add_argument("--base", required=True)
    prediction.add_argument("--files", nargs="*", help="E (default: the diff); none: E empty")
    prediction.add_argument("--against-log", type=Path)
    prediction.add_argument(
        "--against-tables", action="store_true", help="W5-S4: HEAD's generator against BASE"
    )
    prediction.add_argument("--json", type=Path)
    prediction.add_argument("--max-tier", type=int, choices=(1, 2, 3), default=3)
    judgement = commands.add_parser("judge")
    judgement.add_argument("--before", required=True)
    judgement.add_argument("--after", required=True)
    judgement.add_argument("--files", nargs="+")
    judgement.add_argument("--max-tier", type=int, choices=(1, 2, 3), default=3)
    coverage = commands.add_parser("coverage")
    coverage.add_argument("--base", required=True)
    coverage.add_argument("--head", help="the step's commit (default: the working tree)")
    pinning = commands.add_parser("pin")
    pinning.add_argument("--base", required=True)
    pinning.add_argument(
        "--registry", help="serve F0's registry from this revision (W5-K5: the batch base)"
    )
    pinning.add_argument("--json", type=Path)
    pinning.add_argument("argv", nargs=argparse.REMAINDER, help="-- SCRIPT [ARGUMENT ...]")
    facts = commands.add_parser("_facts")
    facts.add_argument("--root", required=True)
    facts.add_argument("--out", required=True)
    facts.add_argument("--legacy", type=Path)
    facts.add_argument("--core", type=Path)
    facts.add_argument("--queries")
    facts.add_argument("--tables", action="store_true")
    arguments = parser.parse_args(argv)
    if arguments.command == "_facts":
        return _facts_main(arguments)
    tree = arguments.tree.resolve()
    handlers = {
        "sets": command_sets,
        "predict": command_predict,
        "judge": command_judge,
        "coverage": command_coverage,
        "pin": command_pin,
    }
    try:
        return handlers[arguments.command](arguments, tree)
    except (RuntimeError, RuleError) as error:
        print(f"w5_identity {arguments.command} ERROR: {error}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
