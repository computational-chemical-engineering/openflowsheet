"""M05 WO-10a: a re-take of a committed study record against the record it replaces (R-432,
design note §21.3; build log S70), with `noise_ratio` and `provenance` masked.

- **The record** by G10's comparator (`m05_replay.replay_differences`: every leaf bitwise by
  `float.hex`, except the registered `excluded` timings — the solves' `wall_s`, positive on both
  sides — and the coupling-record digests, compared by shape). Each raw differing leaf is also
  counted by class (timing, digest, other); any "other" leaf is a difference, except
  `artifacts.experiment_store` when the experiments archive differs only in timings (below).
- **The coupling records** by `m05_replay.content_differences` (M02's `excluded` attempt timings
  removed), plus the reactor's own diagnostic timings (`execution.diagnostics.**.wall_s`), which a
  cold re-run measures again; the re-take's coupling files by `persisted_violations`.
- **The sidecars**: ledger, store index and environment bytewise; REAL's experiments archive
  (`<stem>.experiments.json`) file by file, request and result files bytewise, attempt records
  leaf by leaf with their timings (`execution.timing.*`, `execution.diagnostics.**.wall_s`)
  removed.

The committed side is read from a directory holding the replaced files, for example
`git archive <rev> benchmarks/m05/records | tar -x -C <dir>`. Prints one summary line, then each
noise ratio (old, new, and new/old, which is η·s_k/√2) and each difference; exit 0 iff none.

    python scripts/m05_retake_diff.py <committed-stem> <retake-stem>

**`--digest-only`** (R-458; rulings `docs/design/V02-alpha-main-rulings.md` §3 E5) proves a re-take
in which nothing but digests moved, as after a change to an input of the in-process environment
fingerprint (`__version__`, `models/c1/boundary.py`, a variant's evaluation module). It walks every
leaf of the record (without `provenance`), the ledger, every coupling record (paired by name, a
digest in the name relabelled) and the store index, and classifies each differing leaf as a timing
(the registered patterns: the M05 addendum's `excluded` paths in the record, M02's and `TIMING` in
the coupling records), a digest (both sides 64 lowercase hex) or other. The old->new map is built
over every digest leaf, equal ones included. The store index is sorted by `(experiment_key,
attempt)`, so a relabelling reorders it: its entries are paired by the image of the old key under
the map the other documents built, not by position. It passes iff (a) no leaf is other, (b) the map
is a function, (c) the map is injective, and (d) the environment files are byte-equal, or differ
only in `distributions_sha256` and the running environment's distribution list with the
`openflowsheet==` line set to `--old-version` reproduces the committed hash.

A class `version` admits one leaf (R-458 A1; rulings §3 E5a): the coupling records' clear
`frozen.reactor.fingerprint.openflowsheet_version`, at exactly that path. On every coupling pair the
committed side equals `--old-version` and the re-take side the running `openflowsheet.__version__`
(without `--old-version`, the two sides are equal); a pair that breaks this, or lacks the leaf, is
other. On both sides of every coupling pair, each frozen unit's `fingerprint_sha256` is
`document_sha256` of its `fingerprint` (the binding: the clear leaf cannot move unless the key's
fingerprint digest moves with it, and that digest is held to (b) and (c)); a mismatch is other. The
same text at any other path stays other. It prints one line: PASS/FAIL, the changed digests
(distinct old values whose new value differs) and each class count, then each problem.

    python scripts/m05_retake_diff.py --digest-only <committed-stem> <retake-stem> \
        [--old-version <v>]
"""

from __future__ import annotations

import argparse
import collections
import dataclasses
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "tests" / "support"))
import m05_replay as replay  # noqa: E402

import openflowsheet  # noqa: E402
from openflowsheet.canonical import document_sha256  # noqa: E402

#: A cold re-run measures these again: M02's attempt timings and the reactor's diagnostic timings.
TIMING = re.compile(r"(.*\.execution\.timing\.[a-z_]+|.*\.execution\.diagnostics\..*\.wall_s)")


def _masked(path: Path) -> tuple[dict[str, Any], list[tuple[str, str, Any]]]:
    document = json.loads(path.read_text(encoding="utf-8"))
    document.pop("provenance", None)
    ratios = []
    for run in document["runs"]:
        links = (run.get("basis") or {}).get("links") or {}
        for name, link in links.items():
            ratios.append((run["run_id"], name, link.get("noise_ratio")))
            link["noise_ratio"] = "<masked>"
    return document, ratios


def _leaves(a: Any, b: Any, path: str = "") -> list[str]:
    """Paths whose leaves differ (floats by hex), timings removed."""
    return [
        where
        for where, x, y in replay._walk_pair(a, b, path)
        if not replay._same_leaf(x, y) and not TIMING.fullmatch(where)
    ]


def _experiments(old: Path, new: Path) -> tuple[list[str], int]:
    """REAL's experiments archive: (differences, attempt files that differ only in timings)."""
    a = json.loads(old.read_text(encoding="utf-8"))
    b = json.loads(new.read_text(encoding="utf-8"))
    if list(a) != list(b):
        return ["experiments: the file sets differ"], 0
    found: list[str] = []
    timing_only = 0
    for name in a:
        if a[name] == b[name]:
            continue
        if "/attempts/" not in name:
            found.append(f"experiments {name}: bytes differ")
            continue
        lines = _leaves(json.loads(a[name]), json.loads(b[name]), "")
        found += [f"experiments {name}{line}" for line in lines]
        timing_only += not lines
    return found, timing_only


# -- `--digest-only` (R-458): a re-take in which nothing but digests moved ----------------------

#: A digest: a leaf that is one on both sides is in the map (R-458); one in a coupling file name is
#: relabelled.
DIGEST = re.compile(r"[0-9a-f]{64}")

#: The one leaf the class `version` admits, in a coupling record only (R-458 A1): exact, not a
#: pattern, so a new frozen unit or nesting fails closed.
VERSION_PATH = ".frozen.reactor.fingerprint.openflowsheet_version"


@dataclasses.dataclass
class DigestOnly:
    """The leaf walk of one case: each differing leaf's class, and the old->new digest map over
    every leaf that is a digest on both sides, equal ones included."""

    classes: collections.Counter[str] = dataclasses.field(default_factory=collections.Counter)
    pairs: dict[str, set[str]] = dataclasses.field(default_factory=dict)
    other: list[str] = dataclasses.field(default_factory=list)

    def walk(
        self,
        a: Any,
        b: Any,
        where: str,
        timing: tuple[re.Pattern[str], ...] = (),
        version: bool | None = None,
    ) -> None:
        """`version` is given for a coupling pair only: whether its `VERSION_PATH` rule held (each
        breach already counted as other by `_version_rule`)."""
        for path, x, y in replay._walk_pair(a, b, ""):
            digests = all(isinstance(v, str) and DIGEST.fullmatch(v) for v in (x, y))
            if digests:
                self.pairs.setdefault(x, set()).add(y)
            if replay._same_leaf(x, y):
                continue
            if version is not None and path == VERSION_PATH:
                if version:
                    self.classes["version"] += 1
                continue
            if digests:
                self.classes["digest"] += 1
            elif _number(x) and _number(y) and any(p.fullmatch(path) for p in timing):
                self.classes["timing"] += 1
            else:
                self.classes["other"] += 1
                self.other.append(f"{where}{path}: {x!r} vs {y!r}")

    def flag(self, line: str) -> None:
        self.classes["other"] += 1
        self.other.append(line)

    def relabel(self, old: str) -> str | None:
        """`old`'s image under the map so far, if the map holds `old` and is a function there."""
        images = self.pairs.get(old, set())
        return next(iter(images)) if len(images) == 1 else None

    def not_a_function(self) -> list[str]:
        return sorted(old for old, images in self.pairs.items() if len(images) > 1)

    def not_injective(self) -> list[str]:
        seen: collections.defaultdict[str, list[str]] = collections.defaultdict(list)
        for old, images in self.pairs.items():
            for new in images:
                seen[new].append(old)
        return sorted(new for new, olds in seen.items() if len(olds) > 1)

    def changed(self) -> int:
        return sum(1 for old, images in self.pairs.items() if images != {old})


def _number(value: Any) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _leaf(document: Any, path: str) -> tuple[bool, Any]:
    """(present, value) of the leaf at a dotted `path` (leading dot) of nested objects."""
    for key in path.split(".")[1:]:
        if not isinstance(document, dict) or key not in document:
            return False, None
        document = document[key]
    return True, document


def _version_rule(walk: DigestOnly, a: Any, b: Any, where: str, old_version: str | None) -> bool:
    """R-458 A1 on one coupling pair: the `VERSION_PATH` values, and the binding of each frozen
    unit's `fingerprint_sha256` to its `fingerprint` on both sides. Each breach is other; returns
    whether the values held (the binding is checked, and counted, regardless)."""
    for side, document in (("committed", a), ("re-take", b)):
        frozen = document.get("frozen") if isinstance(document, dict) else None
        if not isinstance(frozen, dict):
            walk.flag(f"{where} ({side}): no frozen units to bind")
            continue
        for unit, entry in frozen.items():
            if not (isinstance(entry, dict) and "fingerprint" in entry):
                walk.flag(f"{where} ({side}): frozen.{unit} has no fingerprint")
                continue
            if entry.get("fingerprint_sha256") != document_sha256(entry["fingerprint"]):
                walk.flag(
                    f"{where} ({side}): frozen.{unit}.fingerprint_sha256 "
                    f"{entry.get('fingerprint_sha256')!r} is not document_sha256 of its fingerprint"
                )
    (had, x), (has, y) = _leaf(a, VERSION_PATH), _leaf(b, VERSION_PATH)
    if not (had and has):
        walk.flag(
            f"{where}{VERSION_PATH}: missing on the {'committed' if not had else 're-take'} side"
        )
        return False
    held = True
    if old_version is None:
        if not replay._same_leaf(x, y):
            walk.flag(f"{where}{VERSION_PATH}: {x!r} vs {y!r} (no --old-version)")
            held = False
    else:
        if x != old_version:
            walk.flag(
                f"{where}{VERSION_PATH}: committed {x!r} is not --old-version {old_version!r}"
            )
            held = False
        running = openflowsheet.__version__
        if y != running:
            walk.flag(f"{where}{VERSION_PATH}: re-take {y!r} is not the running {running!r}")
            held = False
    return held


def _store_pairs(walk: DigestOnly, a: list[Any], b: list[Any]) -> list[tuple[Any, Any]] | None:
    """The store index's entries paired by relabelled key: the index is sorted by `(experiment_key,
    attempt)`, so a relabelling reorders it, and position is not identity. Each old entry is paired
    with the new entry of its key's image under the map the record, the ledger and the coupling
    records built; None, with an `other` line, when an old key has no image or the pairing is not
    one-to-one."""
    new = {(entry["experiment_key"], entry["attempt"]): entry for entry in b}
    pairs = []
    for entry in a:
        image = walk.relabel(entry["experiment_key"])
        partner = new.pop((image, entry["attempt"]), None) if image else None
        if partner is None:
            walk.classes["other"] += 1
            walk.other.append(f"store: {entry} has no partner under the map")
            return None
        pairs.append((entry, partner))
    if new or len(a) != len(b):
        walk.classes["other"] += 1
        walk.other.append(f"store: entries {sorted(new)} have no partner under the map")
        return None
    return pairs


def _distributions_sha256(old_version: str) -> str:
    """`m05_wo8_runs.environment_fingerprint()`'s distribution digest in the running environment,
    with the `openflowsheet==` line set to `old_version`; raises when there is no such line."""
    import importlib.metadata  # noqa: PLC0415

    found = sorted(
        {f"{d.metadata['Name']}=={d.version}" for d in importlib.metadata.distributions()}
    )
    ours = [line for line in found if line.startswith("openflowsheet==")]
    if len(ours) != 1:
        raise LookupError(f"{len(ours)} openflowsheet distributions in this environment")
    found = sorted(f"openflowsheet=={old_version}" if line in ours else line for line in found)
    return hashlib.sha256("\n".join(found).encode()).hexdigest()


def _environment(old: Path, new: Path, old_version: str | None) -> tuple[str, list[str]]:
    """Condition (d): ('equal' | 'distributions', problems)."""
    before, after = old.read_bytes(), new.read_bytes()
    if before == after:
        return "equal", []
    a, b = json.loads(before), json.loads(after)
    if list(a) != list(b) or [k for k in a if a[k] != b[k]] != ["distributions_sha256"]:
        keys = sorted(set(a) ^ set(b) | {k for k in set(a) & set(b) if a[k] != b[k]})
        return "differs", [f"environment: differs outside distributions_sha256 ({keys})"]
    if (
        before.replace(a["distributions_sha256"].encode(), b["distributions_sha256"].encode())
        != after
    ):
        return "differs", ["environment: the bytes differ beyond distributions_sha256"]
    if old_version is None:
        return "distributions", [
            "environment: distributions_sha256 differs; --old-version is required"
        ]
    try:
        recomputed = _distributions_sha256(old_version)
    except LookupError as error:
        return "distributions", [f"environment: {error}"]
    if recomputed != a["distributions_sha256"]:
        return "distributions", [
            f"environment: openflowsheet=={old_version} gives {recomputed}, "
            f"not the committed {a['distributions_sha256']}"
        ]
    return "distributions", []


def digest_only(old: Path, new: Path, old_version: str | None = None) -> tuple[bool, list[str]]:
    """R-458: whether the re-take `new` of the committed `old` differs only in digests, under a
    one-to-one relabelling. Returns (passed, lines): the summary line, then each problem."""
    walk = DigestOnly()
    a, b = _load(old.with_suffix(".json")), _load(new.with_suffix(".json"))
    a.pop("provenance", None)
    b.pop("provenance", None)
    walk.walk(a, b, "record", replay.m05_excluded())
    walk.walk(
        _load(old.with_suffix(".ledger.json")), _load(new.with_suffix(".ledger.json")), "ledger"
    )
    coupling_timing = (*replay.m02_coupling_excluded(), TIMING)
    old_dir, new_dir = old.with_suffix(".coupling"), new.with_suffix(".coupling")
    old_files = sorted(p.name for p in old_dir.glob("*.json"))
    new_files = {p.name for p in new_dir.glob("*.json")}
    for name in old_files:
        partner = DIGEST.sub(lambda m: walk.relabel(m.group(0)) or m.group(0), name)
        if partner not in new_files:
            walk.classes["other"] += 1
            walk.other.append(f"coupling {name}: no re-taken file {partner}")
            continue
        new_files.discard(partner)
        x, y, where = _load(old_dir / name), _load(new_dir / partner), f"coupling {name}"
        held = _version_rule(walk, x, y, where, old_version)
        walk.walk(x, y, where, coupling_timing, version=held)
    for name in sorted(new_files):
        walk.classes["other"] += 1
        walk.other.append(f"coupling {name}: no committed file")
    old_store = _load(old.with_suffix(".store.json"))
    pairs = _store_pairs(walk, old_store, _load(new.with_suffix(".store.json")))
    for index, (x, y) in enumerate(pairs or ()):
        walk.walk(x, y, f"store[{index}]")
    environment, problems = _environment(
        old.with_suffix(".environment.json"), new.with_suffix(".environment.json"), old_version
    )
    problems = walk.other + problems
    problems += [
        f"map: {old} has two images {sorted(walk.pairs[old])}" for old in walk.not_a_function()
    ]
    problems += [f"map: {new} is the image of two digests" for new in walk.not_injective()]
    passed = not problems
    summary = (
        f"RETAKE-DIGEST-ONLY {'PASS' if passed else 'FAIL'} {old.name}: "
        f"changed-digests={walk.changed()} digest={walk.classes['digest']} "
        f"timing={walk.classes['timing']} version={walk.classes['version']} "
        f"other={walk.classes['other']} environment={environment}"
    )
    return passed, [summary, *(f"  {line}" for line in problems)]


def main(argv: list[str]) -> int:
    if argv[:1] == ["--digest-only"]:
        parser = argparse.ArgumentParser(prog="m05_retake_diff.py --digest-only")
        parser.add_argument("committed", type=Path)
        parser.add_argument("retake", type=Path)
        parser.add_argument("--old-version", help="the committed side's openflowsheet version")
        args = parser.parse_args(argv[1:])
        passed, lines = digest_only(args.committed, args.retake, args.old_version)
        print("\n".join(lines))
        return 0 if passed else 1
    old, new = Path(argv[0]), Path(argv[1])
    found: list[str] = []
    a, old_ratios = _masked(old.with_suffix(".json"))
    b, new_ratios = _masked(new.with_suffix(".json"))
    found += [f"record {line}" for line in replay.replay_differences(a, b)]
    classes: collections.Counter[str] = collections.Counter()
    other: list[str] = []
    for path, x, y in replay._walk_pair(a, b, ""):
        if replay._same_leaf(x, y):
            continue
        if any(pattern.fullmatch(path) for pattern in replay.DIGEST_PATHS):
            classes["digest"] += 1
        elif isinstance(x, float) and any(p.fullmatch(path) for p in replay.m05_excluded()):
            classes["timing"] += 1
        else:
            classes["other"] += 1
            other.append(path)
    archive_timing_only = 0
    archive = old.with_suffix(".experiments.json")
    if archive.exists() or new.with_suffix(".experiments.json").exists():
        lines, archive_timing_only = _experiments(archive, new.with_suffix(".experiments.json"))
        found += lines
        if not lines and other == [".artifacts.experiment_store"]:
            found = [line for line in found if ".artifacts.experiment_store" not in line]
            other = []
    found += [f"record raw {path}" for path in other]
    directory = new.with_suffix(".coupling")
    found += [f"re-take integrity {line}" for line in replay.persisted_violations(b, directory)]
    old_files = sorted(p.name for p in old.with_suffix(".coupling").glob("*.json"))
    new_files = sorted(p.name for p in directory.glob("*.json"))
    if old_files != new_files:
        found.append(f"coupling files {old_files} vs {new_files}")
    for name in sorted(set(old_files) & set(new_files)):
        x = json.loads((old.with_suffix(".coupling") / name).read_bytes())
        y = json.loads((directory / name).read_bytes())
        found += [
            f"coupling {name}{line}"
            for line in replay.content_differences(x, y)
            if not TIMING.fullmatch(line.split(":", 1)[0])
        ]
    for suffix in (".ledger.json", ".store.json", ".environment.json"):
        if old.with_suffix(suffix).read_bytes() != new.with_suffix(suffix).read_bytes():
            found.append(f"{suffix}: bytes differ")
    print(
        f"RETAKE-DIFF {'PASS' if not found else 'FAIL'} {old.name}: differences={len(found)} "
        f"record-raw-leaves={dict(classes)} coupling-files={len(new_files)} "
        f"experiments-attempts-timing-only={archive_timing_only}"
    )
    for (run, name, x), (_, _, y) in zip(old_ratios, new_ratios, strict=True):
        factors = None if not (x and y) else [q / p for p, q in zip(x, y, strict=True) if p and q]
        print(f"  noise_ratio {run} {name}: {x} -> {y} (new/old {factors})")
    for line in found:
        print(f"  {line}")
    return 1 if found else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
