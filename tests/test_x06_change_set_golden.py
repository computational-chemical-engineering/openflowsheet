"""E-X06-7 (ADR 0078 D2.4): every recorded ChangeSet request normalizes to the bytes and the
`request_sha256` it had before X06's branches.

The golden list `tests/fixtures/x06/change_set_golden.json` was written by this module's
`main` at `main` `aa5822ac` (the commit before X06) and committed before any branch code
(X06-WO2's first commit). Its sources: every JSON file under `tests/fixtures/` that validates
against `change-set.schema.json` (none at `aa5822ac`), and every `commit_change` and
`preview_change` tool input recorded in the committed agent transcripts under `benchmarks/`
(the V17 and OpenIDAES-450 runs), each normalized as the operation normalizes it
(`operations._decode_commit`, `_decode_preview`: `Change.from_change_set`, then
`as_change_set`; a preview completed by the placeholder key `preview`). X06 decision WO2-1
records why the transcripts are in the set.

Regenerate (only at a commit where the normalization is meant to be the pre-X06 one):
`python tests/test_x06_change_set_golden.py --write tests/fixtures/x06/change_set_golden.json`.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

from openflowsheet.application.transaction_types import Change
from openflowsheet.canonical import canonical_json, document_sha256
from openflowsheet.schema_check import DocumentSchemaError, validate_document

ROOT = Path(__file__).resolve().parents[1]
GOLDEN = ROOT / "tests" / "fixtures" / "x06" / "change_set_golden.json"
SCHEMA = "change-set.schema.json"
PREVIEW_KEY = "preview"
OPERATIONS = ("commit_change", "preview_change")


def _validates(document: object) -> bool:
    try:
        validate_document(SCHEMA, document)
    except DocumentSchemaError:
        return False
    return True


def _fixture_requests() -> Iterator[tuple[str, str, Mapping[str, Any]]]:
    for path in sorted((ROOT / "tests" / "fixtures").rglob("*.json")):
        if path == GOLDEN:
            continue
        try:
            document = json.loads(path.read_bytes())
        except ValueError:
            continue
        if _validates(document):
            yield path.relative_to(ROOT).as_posix(), "commit_change", document


def _transcript_requests() -> Iterator[tuple[str, str, Mapping[str, Any]]]:
    for path in sorted((ROOT / "benchmarks").rglob("transcript.jsonl")):
        relpath = path.relative_to(ROOT).as_posix()
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            message = entry.get("message") if isinstance(entry, dict) else None
            content = message.get("content") if isinstance(message, dict) else None
            for item in content if isinstance(content, list) else ():
                if not isinstance(item, dict) or item.get("type") != "tool_use":
                    continue
                operation = str(item.get("name", "")).rsplit("__", 1)[-1]
                document = item.get("input")
                if operation not in OPERATIONS or not isinstance(document, dict):
                    continue
                if operation == "preview_change":
                    document = {**document, "idempotency_key": PREVIEW_KEY}
                if _validates(document):
                    yield f"{relpath}:{number}:{item.get('id')}", operation, document


def normalized(document: Mapping[str, Any]) -> dict[str, Any]:
    """The request the operation hashes: the ChangeSet read and written back."""
    change, expected_revision, idempotency_key = Change.from_change_set(document)
    return change.as_change_set(expected_revision, idempotency_key)


def entries() -> list[dict[str, str]]:
    """The golden list's entries, from the sources as they stand, in source order."""
    found = []
    for source, operation, document in (*_fixture_requests(), *_transcript_requests()):
        request = normalized(document)
        found.append(
            {
                "source": source,
                "operation": operation,
                "normalized": canonical_json(request).decode("utf-8"),
                "request_sha256": document_sha256(request),
            }
        )
    return found


def _golden() -> list[dict[str, str]]:
    golden: list[dict[str, str]] = json.loads(GOLDEN.read_text(encoding="utf-8"))
    return golden


def test_the_golden_list_is_not_empty() -> None:
    assert len(_golden()) > 0


def test_every_recorded_request_normalizes_as_before() -> None:
    golden = _golden()
    assert golden, "the golden list holds no request"
    assert entries() == golden


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[0] != "--write":
        print("usage: test_x06_change_set_golden.py --write <golden.json>", file=sys.stderr)
        return 2
    found = entries()
    if not found:
        print("FAIL no request found", file=sys.stderr)
        return 1
    Path(argv[1]).write_text(json.dumps(found, indent=1, ensure_ascii=False) + "\n", "utf-8")
    print(f"PASS wrote {len(found)} entries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
