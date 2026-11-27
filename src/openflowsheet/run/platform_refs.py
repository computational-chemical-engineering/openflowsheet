"""Per-platform reference records (ADR 0067 D7; F8-WO5, exit E-F8-8).

R0 is identical on every registered platform. A reference case is one record file
`<dir>/<case>.json` (the reference platform's, `{"artifacts": {...}, ...}`); only where a float
exceeds the numerical policy on another registered platform, a per-platform record
`<dir>/<case>.<platform-id>.json` lies beside it. The comparator uses the current platform's
record if one exists, else the reference's, and reports `platform_reference_used(<platform>)`.
The invariant (`invariant_problems`) is that a per-platform record's R0 projection is the
reference's, that it was made against the reference record it names, and that each departure's
`path` (an RFC 6901 JSON Pointer into `artifacts`) holds its `reference_value` in the reference
record and its `platform_value` in the per-platform record.
"""

from __future__ import annotations

import hashlib
import json
import platform
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any, Final

from openflowsheet.canonical import canonical_json
from openflowsheet.registry.tokens import Coded
from openflowsheet.run import replay
from openflowsheet.run.compare import differences
from openflowsheet.run.identity import r0_projection

#: ADR 0060 D2's platform vocabulary, keyed by `(platform.machine(), platform.system())`.
PLATFORM_IDS: dict[tuple[str, str], str] = {
    ("x86_64", "Linux"): "linux-x86_64",
    ("aarch64", "Linux"): "linux-aarch64",
    ("arm64", "Darwin"): "macos-arm64",
    ("AMD64", "Windows"): "windows-x86_64",
}
REFERENCE_PLATFORM: Final = "linux-x86_64"
FORMAT: Final = "openflowsheet-platform-reference-v1"
_MEMBERS: Final = frozenset(
    {
        "platform_reference_format",
        "case",
        "platform",
        "reference_platform",
        "reference_sha256",
        "departures",
        "artifacts",
        "self_sha256",
    }
)
_DEPARTURE_MEMBERS: Final = frozenset(
    {"path", "reference_value", "platform_value", "bound", "ratio", "near_threshold"}
)


def current_platform() -> str | None:
    """This process's platform id, or `None` when its (machine, system) is unmapped."""
    return PLATFORM_IDS.get((platform.machine(), platform.system()))


def registered_platform_ids() -> frozenset[str]:
    """The registered platforms (`run.replay.REGISTERED_PLATFORMS`) as ids."""
    return frozenset(
        PLATFORM_IDS[pair] for pair in replay.REGISTERED_PLATFORMS if pair in PLATFORM_IDS
    )


def platform_record_path(case_path: Path, platform_id: str) -> Path:
    """`<dir>/<case>.<platform-id>.json` for the reference record `<dir>/<case>.json`."""
    case_path = Path(case_path)
    return case_path.with_name(f"{case_path.stem}.{platform_id}.json")


def record_artifacts(record: Mapping[str, Any]) -> Mapping[str, Any]:
    """The artifacts of a reference or per-platform record (the one accessor, F8-WO5-1)."""
    return record["artifacts"]  # type: ignore[no-any-return]


def record_sha256(record: Mapping[str, Any]) -> str:
    """SHA-256 of a record's canonical JSON (line endings do not matter, ADR 0060 D3)."""
    return hashlib.sha256(canonical_json(record)).hexdigest()


def self_sha256(document: Mapping[str, Any]) -> str:
    """The document's hash over its canonical JSON without `self_sha256`."""
    body = {name: value for name, value in document.items() if name != "self_sha256"}
    return record_sha256(body)


def _load(path: Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _real(value: Any) -> bool:
    """A JSON number (a bool is not one; a non-finite one already failed the self-hash, whose
    canonical JSON has no spelling for it)."""
    return isinstance(value, int | float) and not isinstance(value, bool)


def load_platform_record(path: Path) -> dict[str, Any]:
    """The per-platform record at `path`, validated; `ValueError` names the rule it breaks."""
    document = _load(path)
    if not isinstance(document, dict) or document.get("platform_reference_format") != FORMAT:
        raise ValueError(f"{path}: wrong format: platform_reference_format must be {FORMAT!r}")
    if set(document) != _MEMBERS:
        raise ValueError(f"{path}: members must be exactly {sorted(_MEMBERS)}")
    where = document["platform"]
    if where == REFERENCE_PLATFORM:
        raise ValueError(f"{path}: the reference platform {where!r} takes no per-platform record")
    if not isinstance(where, str) or where not in registered_platform_ids():
        raise ValueError(
            f"{path}: unregistered platform {where!r}: a beyond-policy float there is a "
            "platform-difference row, never a reference record (ADR 0067 D7)"
        )
    if document["reference_platform"] != REFERENCE_PLATFORM:
        raise ValueError(f"{path}: reference_platform must be {REFERENCE_PLATFORM!r}")
    if document["self_sha256"] != self_sha256(document):
        raise ValueError(f"{path}: bad self_sha256")
    if (
        not isinstance(document["case"], str)
        or Path(path).name != f"{document['case']}.{where}.json"
    ):
        raise ValueError(
            f"{path}: the file must be named <case>.<platform>.json for its case and platform"
        )
    rows = document["departures"]
    if not isinstance(rows, list) or not rows:
        raise ValueError(f"{path}: departures must be a non-empty list")
    paths = [row.get("path") if isinstance(row, dict) else None for row in rows]
    if any(not isinstance(item, str) for item in paths) or paths != sorted(paths):  # type: ignore[type-var]
        raise ValueError(f"{path}: departures must be sorted by path")
    if not all(item.startswith("/") for item in paths):  # type: ignore[union-attr]
        raise ValueError(
            f"{path}: a departure's path is an RFC 6901 JSON Pointer into `artifacts` "
            "(it starts with '/')"
        )
    for row in rows:
        if set(row) != _DEPARTURE_MEMBERS:
            raise ValueError(f"{path}: a departure's members must be {sorted(_DEPARTURE_MEMBERS)}")
        numbers = ("reference_value", "platform_value", "bound", "ratio")
        if not all(_real(row[name]) for name in numbers) or not row["bound"] > 0:
            raise ValueError(
                f"{path}: departure {row['path']!r}: values must be numbers, the bound positive"
            )
        if not isinstance(row["near_threshold"], bool):
            raise ValueError(f"{path}: departure {row['path']!r}: near_threshold must be a boolean")
        ratio = row["ratio"]
        if not ratio > 1:
            raise ValueError(f"{path}: departure {row['path']!r}: ratio {ratio} must exceed 1")
        expected = abs(row["platform_value"] - row["reference_value"]) / row["bound"]
        if abs(ratio - expected) > 1e-12 * abs(expected):
            raise ValueError(
                f"{path}: departure {row['path']!r}: ratio {ratio} is not |platform - reference| "
                f"/ bound = {expected}"
            )
    return document


def select_reference(case_path: Path, platform_id: str) -> tuple[Mapping[str, Any], str | None]:
    """The artifacts to compare against, and the platform id if a per-platform record gave them.
    A per-platform record not made against the reference record beside it (its
    `reference_sha256` is not that record's) is refused with `ValueError`: it is stale, and the
    comparison never falls back silently (F8-FR, review F8 S5 (a))."""
    reference = _load(case_path)
    per_platform = platform_record_path(case_path, platform_id)
    if per_platform.is_file():
        record = load_platform_record(per_platform)
        if record["reference_sha256"] != record_sha256(reference):
            raise ValueError(
                f"{per_platform}: reference_sha256 is not the reference record's: the record is "
                "stale and is not used (re-make it against the reference record)"
            )
        return record_artifacts(record), platform_id
    return record_artifacts(reference), None


def compare_to_reference(
    case_path: Path,
    emitted_artifacts: Mapping[str, Any],
    platform_id: str,
    *,
    policy_id: str,
    variable_kinds: Mapping[str, str] | None = None,
) -> tuple[list[str], list[Coded]]:
    """`run.compare.differences` against the selected record, and the notice when it is
    a per-platform one."""
    selected, used = select_reference(case_path, platform_id)
    found = differences(
        emitted_artifacts, selected, policy_id=policy_id, variable_kinds=variable_kinds
    )
    notices = [] if used is None else [Coded("platform_reference_used", {"platform": used})]
    return found, notices


def invariant_problems(case_path: Path) -> list[str]:
    """ADR 0067 D7's invariant over one case's per-platform records."""
    if not Path(case_path).is_file():
        return [f"{case_path}: per-platform records without their reference record"]
    reference = _load(case_path)
    reference_sha = record_sha256(reference)
    reference_r0 = canonical_json(r0_projection(record_artifacts(reference)))
    problems: list[str] = []
    for platform_id in sorted(PLATFORM_IDS.values()):
        path = platform_record_path(case_path, platform_id)
        if not path.is_file():
            continue
        try:
            record = load_platform_record(path)
        except ValueError as error:
            problems.append(str(error))
            continue
        if record["reference_sha256"] != reference_sha:
            problems.append(f"{path}: reference_sha256 is not the reference record's")
        if canonical_json(r0_projection(record_artifacts(record))) != reference_r0:
            problems.append(f"{path}: R0 projection differs from the reference record's")
        for row in record["departures"]:
            for name, artifacts in (
                ("reference_value", record_artifacts(reference)),
                ("platform_value", record_artifacts(record)),
            ):
                value = pointer_value(artifacts, row["path"])
                if not (_real(value) and value == row[name]):
                    problems.append(
                        f"{path}: departure {row['path']!r}: the value there is not its {name}"
                    )
    return problems


def pointer_value(artifacts: Mapping[str, Any], pointer: str) -> Any:
    """The value an RFC 6901 JSON Pointer (a departure's `path`, e.g.
    `/solution-state.json/values/3`) names in `artifacts`, or `None` when it names nothing."""
    if not pointer.startswith("/"):
        return None
    node: Any = artifacts
    for token in pointer[1:].split("/"):
        token = token.replace("~1", "/").replace("~0", "~")
        if isinstance(node, dict) and token in node:
            node = node[token]
        elif isinstance(node, list) and token.isdigit() and str(int(token)) == token:
            index = int(token)
            if index >= len(node):
                return None
            node = node[index]
        else:
            return None
    return node


def all_cases(roots: Iterable[Path]) -> list[Path]:
    """The reference record path of every per-platform record (known platform id) under `roots`."""
    ids = sorted(set(PLATFORM_IDS.values()))
    found: set[Path] = set()
    for root in roots:
        root = Path(root)
        if not root.is_dir():
            continue
        for platform_id in ids:
            for path in root.rglob(f"*.{platform_id}.json"):
                found.add(path.with_name(path.name.removesuffix(f".{platform_id}.json") + ".json"))
    return sorted(found)
