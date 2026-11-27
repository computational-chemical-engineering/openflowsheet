"""The canonical form and `content_hash` of a v2 revision (ADR 0062 D11, ADR 0002 D4).

The normal form is the document with each `materials.definitions` entry in ADR 0062 D3's normal
form (`material.definitions.normalise_instance`: groups by id, attributes by (kind, components));
every other list keeps its order, which is meaningful (component order, allocation order).
`canonical_bytes` is ADR 0002's canonical JSON of it, so key order never matters.

`content_hash` is v1's rule applied to the v2 document: SHA-256 of the canonical JSON of its
semantic content, `CONTENT_HASH_EXCLUDED` left out. The set is v1's
(`application.revisions.CONTENT_HASH_EXCLUDED`), unchanged in name and members; it is repeated here
because this layer sits below `application`, and a test holds the two equal. The hash is taken
over the normal form, so two spellings of one definition share it (F2 decision WO4-3).
"""

from __future__ import annotations

import copy
import hashlib
from collections.abc import Mapping
from typing import Any, Final

from openflowsheet.canonical import canonical_json
from openflowsheet.material.definitions import normalise_instance

__all__ = ["CONTENT_HASH_EXCLUDED", "canonical_bytes", "canonical_document", "content_hash"]

#: ADR 0002 D4's excluded fields, as `application.revisions` holds them (a test pins equality).
CONTENT_HASH_EXCLUDED: Final[frozenset[str]] = frozenset(
    {"content_hash", "revision_id", "parent_revision", "title", "description", "provenance"}
)


def canonical_document(document: Mapping[str, Any]) -> dict[str, Any]:
    """The normal form of a schema-valid v2 document (idempotent; `document` is not changed)."""
    normal = copy.deepcopy(dict(document))
    materials = normal.get("materials")
    if isinstance(materials, dict):
        materials["definitions"] = [normalise_instance(d) for d in materials["definitions"]]
    return normal


def canonical_bytes(document: Mapping[str, Any]) -> bytes:
    """ADR 0002's canonical JSON of the normal form."""
    return canonical_json(canonical_document(document))


def content_hash(document: Mapping[str, Any]) -> str:
    """v1's content hash (ADR 0002 D4) over the normal form of a v2 document."""
    normal = canonical_document(document)
    content = {key: value for key, value in normal.items() if key not in CONTENT_HASH_EXCLUDED}
    return hashlib.sha256(canonical_json(content)).hexdigest()
