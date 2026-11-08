"""MSG's catalogue tools (design note §3.2, §4.2.7–§4.2.9; gates MSG-G1, G2, G4, G5).

    python scripts/msg_catalogue.py scan [--json FILE]          # G2: code literals without an entry
    python scripts/msg_catalogue.py vocabularies                # G1: closed vocabularies
    python scripts/msg_catalogue.py sync-limitations [--check]  # G5: limitations.yaml
    python scripts/msg_catalogue.py freeze                      # released-codes.txt
    python scripts/msg_catalogue.py check                       # G1 + G2 + G4 + G5 + released

Each command prints one summary line and exits 0 only on a pass.

**G2, the static scan** (§3.2), over `src/openflowsheet/**/*.py`, finds code literals at emission
sites: the code argument of `api_error(...)`, `_refuse(...)` and `Failure(...)` (the first
code-shaped string constant among the first two positional args); the code of
`RunUnsupportedError(...)` and the `code=` keyword of `StoreError(...)`; string constants in
assignments to names ending `_CODES`; the string arguments of a `Literal[...]` assigned to a name
ending `Code`; and every string constant or f-string head that begins `snake_case(` (a lower-snake
token with at least one underscore, then `(`). A found code must have an entry or be listed in
`catalogue/scan-allow.yaml` with a reason. Codes built at run time escape it; G3 catches those.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from collections.abc import Iterable, Iterator, Mapping
from pathlib import Path
from typing import Any, Final, get_args

import yaml

ROOT: Final = Path(__file__).resolve().parent.parent
SOURCE: Final = ROOT / "src" / "openflowsheet"
CATALOGUE_DIR: Final = SOURCE / "messages" / "catalogue"
LIMITATIONS: Final = CATALOGUE_DIR / "limitations.yaml"
RELEASED: Final = CATALOGUE_DIR / "released-codes.txt"
SCAN_ALLOW: Final = CATALOGUE_DIR / "scan-allow.yaml"

_CALL_HEAD: Final = re.compile(r"^([a-z][a-z0-9]*(?:_[a-z0-9]+)+)\(")
_CODE_SHAPED: Final = re.compile(r"^[A-Za-z][A-Za-z0-9]*(?:_[A-Za-z0-9]+)+$")
#: Calls whose code is one of their first two positional args.
_CODE_CALLS: Final = frozenset({"api_error", "_refuse", "Failure", "RunUnsupportedError"})


def _modules() -> None:
    for entry in (str(ROOT / "src"), str(ROOT / "scripts")):
        if entry not in sys.path:
            sys.path.insert(0, entry)


# -- G2: the static scan -----------------------------------------------------------------------


def _name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _string(node: ast.expr) -> str | None:
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def _strings(node: ast.AST) -> Iterator[str]:
    for child in ast.walk(node):
        text = _string(child) if isinstance(child, ast.expr) else None
        if text is not None:
            yield text


def scan_source(text: str) -> Iterator[tuple[str, int]]:
    """`(code, line)` for each code literal at an emission site of one module."""
    tree = ast.parse(text)
    heads: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = _name(node.func)
            if name in _CODE_CALLS:
                for argument in node.args[:2]:
                    value = _string(argument)
                    if value is not None and _CODE_SHAPED.match(value):
                        yield value, node.lineno
                        break
            for keyword in node.keywords:
                if keyword.arg == "code" and name in (*_CODE_CALLS, "StoreError"):
                    value = _string(keyword.value)
                    if value is not None:
                        yield value, node.lineno
        elif isinstance(node, ast.Assign | ast.AnnAssign):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            names = {_name(target) for target in targets}
            assigned = node.value
            if assigned is None:
                continue
            if any(n is not None and n.endswith("_CODES") for n in names):
                for text_value in _strings(assigned):
                    yield text_value, node.lineno
            if any(n is not None and n.endswith("Code") for n in names) and (
                isinstance(assigned, ast.Subscript) and _name(assigned.value) == "Literal"
            ):
                for text_value in _strings(assigned.slice):
                    yield text_value, node.lineno
        elif isinstance(node, ast.JoinedStr) and node.values:
            first = node.values[0]
            heads.add(id(first))
            value = _string(first) if isinstance(first, ast.expr) else None
            match = _CALL_HEAD.match(value or "")
            if match:
                yield match.group(1), node.lineno
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and id(node) not in heads:
            value = _string(node)
            match = _CALL_HEAD.match(value or "")
            if match:
                yield match.group(1), node.lineno


def scan() -> dict[str, list[str]]:
    """`{code: [path:line, …]}` over the package source."""
    found: dict[str, list[str]] = {}
    for path in sorted(SOURCE.rglob("*.py")):
        relative = path.relative_to(ROOT).as_posix()
        for code, line in scan_source(path.read_text(encoding="utf-8")):
            found.setdefault(code, []).append(f"{relative}:{line}")
    return found


def scan_allow() -> dict[str, str]:
    document = yaml.safe_load(SCAN_ALLOW.read_text(encoding="utf-8")) if SCAN_ALLOW.exists() else {}
    allowed: dict[str, str] = dict((document or {}).get("allow") or {})
    return allowed


def scan_misses(keys: Iterable[str]) -> dict[str, list[str]]:
    known = set(keys) | set(scan_allow())
    return {code: sites for code, sites in sorted(scan().items()) if code not in known}


# -- G1: the closed vocabularies ---------------------------------------------------------------


def _validation_check_ids() -> set[str]:
    """Every check id literal of `application/validation.py` (`XXX-NN`)."""
    text = (SOURCE / "application" / "validation.py").read_text(encoding="utf-8")
    return set(re.findall(r"\"([A-Z]+-\d{2})\"", text))


def vocabularies() -> dict[str, set[str]]:
    """§3.2 G1: every member of each closed vocabulary that must have an entry."""
    _modules()
    import t08_support_matrix  # noqa: PLC0415

    from openflowsheet.application.jobs.model import ENDING_REASONS, JobStatus  # noqa: PLC0415
    from openflowsheet.application.types import ApiErrorCode  # noqa: PLC0415
    from openflowsheet.application.validation import ValidationStatus  # noqa: PLC0415
    from openflowsheet.verify import RegularityStatus, VerificationStatus  # noqa: PLC0415
    from openflowsheet.verify.failure import TAXONOMY  # noqa: PLC0415

    events = json.loads((ROOT / "schemas" / "solve-event.schema.json").read_text("utf-8"))
    envelope = t08_support_matrix.load()
    return {
        "api_error": set(get_args(ApiErrorCode)),
        "outcome": set(TAXONOMY) | {"CONVERGED"} | set(events["properties"]["outcome"]["enum"]),
        "status": set(get_args(VerificationStatus))
        | set(get_args(RegularityStatus))
        | set(get_args(ValidationStatus)),
        "job": set(get_args(JobStatus)) | {r for rs in ENDING_REASONS.values() for r in rs},
        "check": _validation_check_ids(),
        "limitation": {str(row["id"]) for row in envelope.get("limitations") or ()},
    }


def vocabulary_misses(keys: Iterable[str]) -> dict[str, list[str]]:
    known = set(keys)
    return {
        family: sorted(members - known)
        for family, members in vocabularies().items()
        if members - known
    }


# -- G5: limitations.yaml ----------------------------------------------------------------------

#: The fields `sync-limitations` writes; every other field of an entry is authored and kept.
GENERATED: Final = ("code", "family", "kind", "title")


def _literal(text: str) -> str:
    """`text` as a template that renders to itself (§4.2.4: braces and brackets doubled)."""
    return text.replace("{", "{{").replace("}", "}}").replace("[", "[[").replace("]", "]]")


def limitation_rows() -> list[tuple[str, str]]:
    _modules()
    import t08_support_matrix  # noqa: PLC0415

    envelope = t08_support_matrix.load()
    return [(str(row["id"]), " ".join(str(row["text"]).split())) for row in envelope["limitations"]]


def synced_limitations(current: Mapping[str, Any]) -> dict[str, Any]:
    """The limitations document for the matrix, keeping each entry's authored fields. A complete
    entry keeps its authored `summary` (it is jargon-linted, the matrix text is not)."""
    authored = {entry["code"]: entry for entry in current.get("entries") or ()}
    entries = []
    for code, text in limitation_rows():
        old = dict(authored.get(code) or {})
        entry: dict[str, Any] = {
            "code": code,
            "family": "limitation",
            "kind": "notice",
            "complete": bool(old.get("complete", False)),
            "title": code,
            "summary": old["summary"] if old.get("complete") else _literal(text),
        }
        for name, value in old.items():
            if name not in entry:
                entry[name] = value
        entries.append(entry)
    return {"catalogue": "openflowsheet-messages-v1", "namespace": None, "entries": entries}


LIMITATIONS_HEADER: Final = (
    "# Family `limitation` (MSG design note §4.2.9): one entry per support-matrix id, written by\n"
    "# `scripts/msg_catalogue.py sync-limitations` from `benchmarks/t08/support_envelope.yaml`.\n"
    "# Generated: code, family, kind, title, and the summary of an entry that is not complete.\n"
    "# Authored and kept: everything else (complete, why, action, see_also, examples, ...).\n"
)


def limitations_text(document: Mapping[str, Any]) -> str:
    body = yaml.safe_dump(dict(document), sort_keys=False, allow_unicode=True, width=100)
    return LIMITATIONS_HEADER + body


def sync_limitations(*, check: bool) -> int:
    current = yaml.safe_load(LIMITATIONS.read_text(encoding="utf-8")) or {}
    expected = limitations_text(synced_limitations(current))
    if check:
        same = LIMITATIONS.read_text(encoding="utf-8") == expected
        print(f"MSG-G5 sync-limitations --check: {'clean' if same else 'OUT OF SYNC'}")
        return 0 if same else 1
    LIMITATIONS.write_text(expected, encoding="utf-8")
    print(f"MSG sync-limitations: wrote {len(limitation_rows())} entries to {LIMITATIONS}")
    return 0


# -- released codes ----------------------------------------------------------------------------


def released_codes() -> list[str]:
    if not RELEASED.exists():
        return []
    lines = RELEASED.read_text(encoding="utf-8").splitlines()
    return [line.strip() for line in lines if line.strip() and not line.startswith("#")]


def freeze(keys: Iterable[str]) -> int:
    codes = sorted(set(released_codes()) | set(keys))
    header = (
        "# MSG design note §3.2: every code a release has carried. A code here is never removed\n"
        "# or renamed, only deprecated with `replaced_by`. Written by `msg_catalogue.py freeze`.\n"
    )
    RELEASED.write_text(header + "".join(f"{code}\n" for code in codes), encoding="utf-8")
    print(f"MSG freeze: {len(codes)} released codes ({RELEASED})")
    return 0


# -- check -------------------------------------------------------------------------------------


def check() -> int:
    _modules()
    from openflowsheet.messages.catalogue import CATALOGUE  # noqa: PLC0415
    from openflowsheet.messages.lint import lint, review_count  # noqa: PLC0415

    keys = CATALOGUE.keys()
    g1 = vocabulary_misses(keys)
    g2 = scan_misses(keys)
    g4 = lint(released=set(released_codes()))
    unreleased = sorted(set(released_codes()) - set(keys))
    current = yaml.safe_load(LIMITATIONS.read_text(encoding="utf-8")) or {}
    g5 = LIMITATIONS.read_text(encoding="utf-8") == limitations_text(synced_limitations(current))
    complete = sum(1 for entry in CATALOGUE.entries() if entry.complete)
    passed = not g1 and not g2 and not g4 and not unreleased and g5
    print(
        f"MSG check {'PASS' if passed else 'FAIL'}: {len(keys)} entries ({complete} complete, "
        f"{len(keys) - complete} stubs, review: true on {review_count()}); "
        f"G1 {sum(map(len, g1.values()))} missing; G2 {len(g2)} missing; G4 {len(g4)} violations; "
        f"G5 {'clean' if g5 else 'out of sync'}; released-not-in-catalogue {len(unreleased)}"
    )
    for family, codes in g1.items():
        print(f"  G1 {family}: {', '.join(codes[:10])}")
    for code, sites in list(g2.items())[:10]:
        print(f"  G2 {code}: {sites[0]}")
    for problem in g4[:10]:
        print(f"  G4 {problem}")
    return 0 if passed else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    commands = parser.add_subparsers(dest="command", required=True)
    scan_command = commands.add_parser("scan")
    scan_command.add_argument("--json", type=Path, help="write every found code and its sites")
    commands.add_parser("vocabularies")
    sync = commands.add_parser("sync-limitations")
    sync.add_argument("--check", action="store_true")
    commands.add_parser("freeze")
    commands.add_parser("check")
    arguments = parser.parse_args(argv)
    _modules()
    if arguments.command == "sync-limitations":
        return sync_limitations(check=arguments.check)
    if arguments.command == "check":
        return check()
    from openflowsheet.messages.catalogue import CATALOGUE  # noqa: PLC0415

    keys = CATALOGUE.keys()
    if arguments.command == "freeze":
        return freeze(keys)
    if arguments.command == "vocabularies":
        misses = vocabulary_misses(keys)
        total = sum(map(len, misses.values()))
        verdict = "PASS" if not total else "FAIL"
        print(f"MSG-G1 {verdict}: {total} closed-vocabulary codes without an entry")
        for family, codes in misses.items():
            print(f"  {family}: {', '.join(codes)}")
        return 0 if not total else 1
    found = scan()
    if arguments.json is not None:
        arguments.json.write_text(json.dumps(found, indent=1, sort_keys=True) + "\n")
    misses = scan_misses(keys)
    print(
        f"MSG-G2 {'PASS' if not misses else 'FAIL'}: {len(found)} codes found, "
        f"{len(misses)} without an entry or an allow-list reason"
    )
    for code, sites in list(misses.items())[:20]:
        print(f"  {code}: {sites[0]}")
    return 0 if not misses else 1


if __name__ == "__main__":
    raise SystemExit(main())
