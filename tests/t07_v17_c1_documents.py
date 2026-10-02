"""The `v17-c1` agents' own revision documents that T07 ruling round 6 replays (G-R6-3, G-R6-4).
Not collected.

Each is read from the committed campaign record, `benchmarks/t07/v17/runs/v17-c1/V17-<run>/
store-export.json` (`revisions[].document`), unedited. **Two of them no longer pass `SCHEMA-01`**:
ruling round 5, S3 applied `process-revision.schema.json` in `validate()` after the campaign ran at
`1ed044d`, and the T02-2 and T02-3 agents wrote an instance `semantic_role` of `purge_sink` (not in
the schema's enum), and T02-2 an empty specification `provenance`. As committed they validate
`INVALID` on `SCHEMA-01` before any structural stage, at `9165894` as at every later commit, so they
cannot exercise B1. `schema_conformant` makes exactly those two edits — `purge_sink` to the
schema's `product_sink` (the model is `syn001.product_sink`) and an empty `provenance` to the
fixture's own `"V17 fixture."` — and nothing that a binder reads, so the structural stage sees
the document the agent wrote. Both forms are replayed (rf3a decision, `docs/T07_DECISIONS.md`).
"""

from __future__ import annotations

import copy
import json
from functools import cache
from typing import Any

from conftest import REPO_ROOT

CAMPAIGN = REPO_ROOT / "benchmarks" / "t07" / "v17" / "runs" / "v17-c1"
Document = dict[str, Any]

#: G-R6-3's V17 documents, (run, revision id), as committed.
G_R6_3 = (
    ("T02-1", "rev-000002"),
    ("T02-2", "rev-000002"),
    ("T02-3", "rev-000002"),
    ("T02-3", "rev-000003"),
    ("T05-2", "rev-000002"),
)
#: The fixture's specification provenance, which the agents' other specifications carry.
FIXTURE_PROVENANCE = "V17 fixture."


@cache
def _export(run: str) -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads(
        (CAMPAIGN / f"V17-{run}" / "store-export.json").read_text("utf-8")
    )
    return loaded


def c1_document(run: str, revision_id: str) -> Document:
    """A fresh copy of the stored document of `revision_id` in `run`'s store export."""
    (document,) = [
        row["document"] for row in _export(run)["revisions"] if row["revision_id"] == revision_id
    ]
    copied: Document = copy.deepcopy(document)
    return copied


def schema_conformant(document: Document) -> Document:
    """`document` with the two `SCHEMA-01` refusals of the module docstring repaired, and nothing
    else changed."""
    repaired = copy.deepcopy(document)
    for instance in repaired.get("instances") or ():
        if instance.get("semantic_role") == "purge_sink":
            instance["semantic_role"] = "product_sink"
    for specification in repaired.get("specifications") or ():
        if specification.get("provenance") == "":
            specification["provenance"] = FIXTURE_PROVENANCE
    return repaired


def t05_2_corrected(document: Document) -> Document:
    """T05-2 `rev-000002` with its duty specification's kind and path corrected, to the encoding
    the revision binder reads (`heat_rate` at instance path `duty.Q`, ruling round 6, B2)."""
    corrected = copy.deepcopy(document)
    for specification in corrected["specifications"]:
        if specification["id"] == "SPEC-flash-duty":
            specification["kind"] = "heat_rate"
            specification["target"]["path"] = "duty.Q"
    return corrected


def g_r6_3_documents() -> dict[str, Document]:
    """Every G-R6-3 document, keyed `<run>/<revision>[/<form>]`: as committed, schema-conformant
    where that differs, and T05-2 with kind and path corrected."""
    documents: dict[str, Document] = {}
    for run, revision_id in G_R6_3:
        document = c1_document(run, revision_id)
        documents[f"{run}/{revision_id}"] = document
        conformant = schema_conformant(document)
        if conformant != document:
            documents[f"{run}/{revision_id}/schema-conformant"] = conformant
    documents["T05-2/rev-000002/corrected"] = t05_2_corrected(c1_document("T05-2", "rev-000002"))
    return documents
