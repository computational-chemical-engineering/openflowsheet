"""`ProcessRevision` v2 documents (ADR 0062 D9 to D11): parse, validate and canonicalise.

This layer was introduced by package F2 (ADR 0062, work order F2-WO4). A v2 document has
`schema_version: 2` and is never read as v1 (ADR 0002 D7.5); v1 documents keep the untouched v1
reader. `parse` reads and schema-checks a document (`schemas/process-revision-v2.schema.json`,
with `specification-v2.schema.json`), `validate` applies the rules a schema cannot state with
ADR 0062's typed codes, and `canonical` gives the normal form and the `content_hash` (v1's rule,
ADR 0002 D4). Lowering to v1 and the operations dispatch are F2-WO6's. It sits directly above
`material`, whose definitions and layout it reads, and imports nothing of `thermo` or above.
"""

from __future__ import annotations

from openflowsheet.revision_v2.canonical import (
    CONTENT_HASH_EXCLUDED,
    canonical_bytes,
    canonical_document,
    content_hash,
)
from openflowsheet.revision_v2.parse import RevisionV2, RevisionV2Error, parse
from openflowsheet.revision_v2.validate import (
    ModelFacts,
    PortFacts,
    ValidationContext,
    mixed_solid_candidates,
    state_refusals,
    validate,
)

__all__ = [
    "CONTENT_HASH_EXCLUDED",
    "ModelFacts",
    "PortFacts",
    "RevisionV2",
    "RevisionV2Error",
    "ValidationContext",
    "canonical_bytes",
    "canonical_document",
    "content_hash",
    "mixed_solid_candidates",
    "parse",
    "state_refusals",
    "validate",
]
