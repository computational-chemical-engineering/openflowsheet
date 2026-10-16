"""G10's same-machine replay comparison of M05 study records and the referent check of their
persisted coupling records (design note §9.3, §19.1; register R-384, R-385). Test support only:
M05 adds no product-level replay or compare (R-253, R-271).

- `replay_differences(recorded, fresh)`: every float that the M05 addendum does not classify
  `excluded` is bitwise equal (`float.hex`); every other leaf and the structure are exact. The
  coupling-record digests (`start.coupling_record_sha256`,
  `candidates[i].solves[j].coupling_record_sha256`, `artifacts.coupled_runs[k].sha256`) are
  compared for shape only: both null, or both 64 lowercase hex (R-384, R-318's rule for M02's
  `constants_sha256`). `artifacts.coupled_runs[k].check_id` stays exact. An excluded float
  (`wall_s`) must be positive on both sides (§9.3).
- `persisted_violations(record, directory)`: *integrity* — `directory` holds exactly one file
  `<check_id>.json` per `artifacts.coupled_runs` entry and nothing else, and each file's sha256
  is its recorded digest (R-385).
- `store_bijection_violations(store, ledger, couplings)`: §8.3's store bijection (G7) of a run's
  experiment-store attempts against its ledger and coupling records.
- `content_differences(persisted, fresh)`: *content* — a fresh coupling record against the
  persisted one with every path M02's `rules.coupling` classifies `excluded` removed (read from
  `benchmarks/m02/numerical_policy_external.yaml`, never restated here), floats by `float.hex`.

The record file's own sha256 is a provenance digest; it is never compared between runs.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterator, Mapping
from functools import cache
from pathlib import Path
from typing import Any, Final

import yaml

REPO_ROOT: Final = Path(__file__).resolve().parents[2]
M05_ADDENDUM: Final = REPO_ROOT / "benchmarks" / "m05" / "numerical_policy_external.yaml"
M02_ADDENDUM: Final = REPO_ROOT / "benchmarks" / "m02" / "numerical_policy_external.yaml"

#: R-384: the record paths whose coupling-record digest is compared for shape, not value.
DIGEST_PATHS: Final = (
    re.compile(r"\.start\.coupling_record_sha256"),
    re.compile(r"\.candidates\[\d+\]\.solves\[\d+\]\.coupling_record_sha256"),
    re.compile(r"\.artifacts\.coupled_runs\[\d+\]\.sha256"),
)
HEX64: Final = re.compile(r"[0-9a-f]{64}")


def _excluded(path: Path, table: str) -> tuple[re.Pattern[str], ...]:
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    rules = document["numerical_policy_external"]["rules"][table]
    return tuple(re.compile(rule["path"]) for rule in rules if rule["class"] == "excluded")


@cache
def m05_excluded() -> tuple[re.Pattern[str], ...]:
    """The M05 addendum's `excluded` float paths (the solves' `wall_s`)."""
    return _excluded(M05_ADDENDUM, "trust_region_study")


@cache
def m02_coupling_excluded() -> tuple[re.Pattern[str], ...]:
    """M02's `rules.coupling` paths classified `excluded` (the attempts' timings)."""
    return _excluded(M02_ADDENDUM, "coupling")


def _float(value: Any) -> bool:
    return isinstance(value, float)


def _walk_pair(a: Any, b: Any, path: str) -> Iterator[tuple[str, Any, Any]]:
    """Leaves of `a` and `b` side by side, with a structural mismatch yielded at its path."""
    if isinstance(a, dict) and isinstance(b, dict):
        if list(a) != list(b):
            yield path, sorted(a), sorted(b)
            return
        for key in a:
            yield from _walk_pair(a[key], b[key], f"{path}.{key}")
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            yield f"{path}[len]", len(a), len(b)
            return
        for index, (x, y) in enumerate(zip(a, b, strict=True)):
            yield from _walk_pair(x, y, f"{path}[{index}]")
    else:
        yield path, a, b


def _same_leaf(a: Any, b: Any) -> bool:
    if _float(a) or _float(b):
        return _float(a) and _float(b) and a.hex() == b.hex()
    return type(a) is type(b) and a == b


def replay_differences(recorded: Mapping[str, Any], fresh: Mapping[str, Any]) -> list[str]:
    """G10 (same machine, §19.4): the differences between two M05 records, as lines."""
    found: list[str] = []
    excluded = m05_excluded()
    for path, a, b in _walk_pair(recorded, fresh, ""):
        if any(pattern.fullmatch(path) for pattern in DIGEST_PATHS):
            shapes = (a is None, b is None)
            if shapes == (True, True):
                continue
            if shapes == (False, False) and all(
                isinstance(v, str) and HEX64.fullmatch(v) for v in (a, b)
            ):
                continue
            found.append(f"{path}: digest shape {a!r} vs {b!r}")
        elif _float(a) and _float(b) and any(pattern.fullmatch(path) for pattern in excluded):
            if not (a > 0.0 and b > 0.0):
                found.append(f"{path}: excluded timing not positive ({a!r}, {b!r})")
        elif not _same_leaf(a, b):
            found.append(f"{path}: {a!r} vs {b!r}")
    return found


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def persisted_violations(record: Mapping[str, Any], directory: Path) -> list[str]:
    """R-385's integrity check of `<record stem>.coupling/` against `artifacts.coupled_runs`."""
    runs = list(record["artifacts"]["coupled_runs"])
    expected = {f"{run['check_id']}.json": run["sha256"] for run in runs}
    found: list[str] = []
    if len(expected) != len(runs):
        found.append(f"duplicate check_id among {len(runs)} coupled runs")
    present = sorted(p.name for p in directory.iterdir()) if directory.is_dir() else []
    if present != sorted(expected):
        found.append(f"files {present} != coupled runs {sorted(expected)}")
    for name, digest in sorted(expected.items()):
        file = directory / name
        if file.is_file() and _sha256(file) != digest:
            found.append(f"{name}: sha256 {_sha256(file)} != recorded {digest}")
    return found


def _without_excluded(node: Any, path: str, excluded: tuple[re.Pattern[str], ...]) -> Any:
    """`node` with every leaf whose path an `excluded` rule matches removed, floats as hex."""
    if isinstance(node, dict):
        kept = {}
        for key, value in node.items():
            child = f"{path}.{key}"
            if not isinstance(value, dict | list) and any(p.fullmatch(child) for p in excluded):
                continue
            kept[key] = _without_excluded(value, child, excluded)
        return kept
    if isinstance(node, list):
        return [_without_excluded(value, f"{path}[{i}]", excluded) for i, value in enumerate(node)]
    if _float(node):
        return ("float", node.hex())
    return node


def content_differences(persisted: Mapping[str, Any], fresh: Mapping[str, Any]) -> list[str]:
    """R-385's content check (same machine): the two coupling records equal, M02's `excluded`
    paths removed, floats compared by `float.hex`."""
    excluded = m02_coupling_excluded()
    a = _without_excluded(persisted, "", excluded)
    b = _without_excluded(fresh, "", excluded)
    return [f"{path}: {x!r} vs {y!r}" for path, x, y in _walk_pair(a, b, "") if x != y]


def _coupling_attempts(record: Mapping[str, Any]) -> Iterator[tuple[str, int]]:
    """(experiment_key, attempt) of every attempt a coupling record embeds (ADR 0034 D6), the
    pairs `parent.coupling_counts` counts as executions."""
    for iteration in record.get("iterations") or ():
        for entry in (iteration.get("units") or {}).values():
            for attempt in entry.get("attempts") or ():
                yield attempt["experiment_key"], attempt["attempt"]


def store_bijection_violations(
    store: list[Mapping[str, Any]],
    ledger: list[Mapping[str, Any]],
    couplings: Mapping[str, Mapping[str, Any]],
) -> list[str]:
    """§8.3's store bijection (G7): every attempt record in the study's experiment store
    (`store`, one `{experiment_key, attempt}` per `attempts/<n>.json`) is attributed to exactly
    one ledger entry or coupled solve. A coupling record names its attempts as (key, attempt)
    pairs; a holder ledger entry names its key and the attempts it wrote (`executions`), not their
    numbers, so a key's attempts that no coupling record names must be exactly as many as the
    ledger's executions at that key."""
    found: list[str] = []
    stored = [(item["experiment_key"], item["attempt"]) for item in store]
    stored_set = set(stored)
    if len(stored_set) != len(stored):
        found.append("store: an attempt is listed twice")
    remaining: dict[str, int] = {}
    for key, _ in stored:
        remaining[key] = remaining.get(key, 0) + 1
    claimed: dict[tuple[str, int], str] = {}
    for solve_id, record in couplings.items():
        for pair in _coupling_attempts(record):
            if pair in claimed:
                found.append(f"attempt {pair}: claimed by {claimed[pair]} and coupling {solve_id}")
                continue
            claimed[pair] = f"coupling {solve_id}"
            if pair not in stored_set:
                found.append(f"attempt {pair}: coupling {solve_id} names an attempt not stored")
                continue
            remaining[pair[0]] -= 1
    executions: dict[str, int] = {}
    for block in ledger:
        for entry in block["requests"]:
            count = entry["executions"]
            if not count:
                continue
            key = entry["experiment_key"]
            if key is None:
                found.append(f"{block['holder']} seq {entry['seq']}: executions without a key")
                continue
            executions[key] = executions.get(key, 0) + count
    for key in sorted(set(remaining) | set(executions)):
        if remaining.get(key, 0) != executions.get(key, 0):
            found.append(
                f"key {key[:12]}: {remaining.get(key, 0)} attempts no coupling names, "
                f"{executions.get(key, 0)} ledger executions"
            )
    return found
