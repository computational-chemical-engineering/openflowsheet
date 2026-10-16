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

**REAL's replay from the record** (WO-9, F-20, build log S68): the study is re-run over its
restored experiment store, so every reactor request is served from the record and the counts a
store hit changes differ by design.

- `real_replay_differences(recorded, fresh)`: `replay_differences` without `provenance` and
  without the paths of `STORE_SERVED_COUNTS`; the fresh study executed nothing (its cold counts
  are 0) and served as many requests from the store as the record served cold or from the store.
- `served_ledger_differences(recorded, fresh)`: the ledgers entry by entry, exact except that a
  recorded `cold` request is a `store_hit` without executions in the replay.
- `served_coupling_differences(persisted, fresh)`: M02's `iterate_differences` and
  `record_differences` (R-317 (b)) under `T08-numerical-policy-v2`, then `content_differences`
  without the unit entries' `attempts` and `cache_hit`; every fresh reactor answer is a store hit.
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


# -- REAL: the replay from the record (WO-9, F-20, build log S68) ---------------------------------

#: The record paths whose counts a store hit changes by design: cold requests and parent
#: executions become store hits when the reactor is served from the record.
STORE_SERVED_COUNTS: Final = (
    re.compile(r"\.accounting\.budgets\.cold_used"),
    re.compile(r"\.accounting\.by_candidate\.[^.]+\.(check_parent_executions|produce_trf_cold)"),
    re.compile(
        r"\.accounting\.(by_iteration\.[^.]+|by_stage\.[^.]+|totals)\."
        r"(parent_executions|store_hits|trf_cold)"
    ),
    re.compile(r"\.(start|candidates\[\d+\]\.solves\[\d+\])\.experiments\.(executions|store_hits)"),
    re.compile(r"\.runs\[\d+\]\.(cold|ledger\.cold_parent)"),
    re.compile(r"\.runs\[\d+\]\.ledger\.summary\.[^.]+\.(value|jacobian)_(cold|store_hit)"),
)
#: M02's registered policy, under which REAL's coupling records are compared (G10, F-20).
REAL_POLICY_ID: Final = "T08-numerical-policy-v2"


def _dropped(node: Any, path: str, patterns: tuple[re.Pattern[str], ...]) -> Any:
    """`node` without the leaves whose path a pattern matches (floats kept as floats)."""
    if isinstance(node, dict):
        return {
            key: _dropped(value, f"{path}.{key}", patterns)
            for key, value in node.items()
            if isinstance(value, dict | list)
            or not any(p.fullmatch(f"{path}.{key}") for p in patterns)
        }
    if isinstance(node, list):
        return [_dropped(value, f"{path}[{i}]", patterns) for i, value in enumerate(node)]
    return node


def real_replay_differences(recorded: Mapping[str, Any], fresh: Mapping[str, Any]) -> list[str]:
    """REAL's record against its replay from the record (module docstring)."""
    a = {key: value for key, value in recorded.items() if key != "provenance"}
    b = {key: value for key, value in fresh.items() if key != "provenance"}
    found = replay_differences(
        _dropped(a, "", STORE_SERVED_COUNTS), _dropped(b, "", STORE_SERVED_COUNTS)
    )
    totals = fresh["accounting"]["totals"]
    executed = {
        "trf_cold": totals["trf_cold"],
        "parent_executions": totals["parent_executions"],
        "cold_used": fresh["accounting"]["budgets"]["cold_used"],
    }
    found += [f"replay executed: {name} = {count}" for name, count in executed.items() if count]
    for mine, theirs in zip(fresh["runs"], recorded["runs"], strict=False):
        for holder, summary in theirs["ledger"]["summary"].items():
            replayed = mine["ledger"]["summary"].get(holder, {})
            for call in ("value", "jacobian"):
                served = (f"{call}_cold", f"{call}_store_hit")
                want = sum(summary[name] for name in served)
                got = sum(replayed.get(name, 0) for name in served)
                if got != want:
                    found.append(
                        f".runs[{theirs['run_id']}].ledger.summary.{holder}: {got} {call} "
                        f"requests served cold or from the store, {want} recorded"
                    )
    return found


def served_ledger_differences(
    recorded: list[Mapping[str, Any]], fresh: list[Mapping[str, Any]]
) -> list[str]:
    """REAL's ledger against its replay's (module docstring)."""
    if len(recorded) != len(fresh):
        return [f"ledger: {len(fresh)} holder blocks, {len(recorded)} recorded"]
    found: list[str] = []
    for theirs, mine in zip(recorded, fresh, strict=True):
        where = f"ledger {theirs['holder']} (projection {theirs['projection']})"
        if (theirs["holder"], theirs["projection"]) != (mine["holder"], mine["projection"]):
            found.append(f"{where}: block is {mine['holder']} (projection {mine['projection']})")
            continue
        if len(theirs["requests"]) != len(mine["requests"]):
            found.append(f"{where}: {len(mine['requests'])} requests, {len(theirs['requests'])}")
            continue
        for a, b in zip(theirs["requests"], mine["requests"], strict=True):
            expected = dict(a)
            if a["served"] == "cold":
                expected.update(served="store_hit", executions=0)
            if dict(b) != expected:
                keys = sorted(k for k in set(expected) | set(b) if expected.get(k) != b.get(k))
                found.append(f"{where} seq {a['seq']}: differs in {keys}")
    return found


def _unserved(record: Mapping[str, Any]) -> dict[str, Any]:
    """A coupling record without its unit entries' `attempts` and `cache_hit`."""
    shaped = dict(record)
    shaped["iterations"] = [
        {
            **item,
            "units": {
                unit: {k: v for k, v in entry.items() if k not in ("attempts", "cache_hit")}
                for unit, entry in (item.get("units") or {}).items()
            },
        }
        for item in record.get("iterations") or ()
    ]
    return shaped


def served_coupling_differences(
    persisted: Mapping[str, Any], fresh: Mapping[str, Any]
) -> list[str]:
    """A REAL coupling record against its replay's (module docstring)."""
    from openflowsheet.application.coupled_run import iterate_differences, record_differences

    found = iterate_differences(fresh, persisted, REAL_POLICY_ID)
    shaped, floored = record_differences(fresh, persisted, REAL_POLICY_ID)
    found += floored
    found += content_differences(_unserved(persisted), _unserved(shaped))
    for item in fresh.get("iterations") or ():
        for unit, entry in (item.get("units") or {}).items():
            if entry.get("request") is not None and not (
                entry["cache_hit"] is True and entry["attempts"] == []
            ):
                found.append(f".iterations[k={item['k']}].units.{unit}: not served from the store")
    return found
