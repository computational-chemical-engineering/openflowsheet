"""D6's legacy built-ins, read from generated package data (ADR 0060 D6).

`builtin/legacy.json` is written by `scripts/registry_builtin.py --write` and checked by its
`--check`; it is never edited by hand. It holds the connection definition `nTP-v1`, the seven
legacy property methods and the 31 legacy units, each with its legacy-form payload
(`descriptor.LEGACY_PAYLOAD_DEFS`). The registry reads the JSON at build: it never imports
`application.revision_binding`, a provider module or CoolProp to register them.

Legacy admission is an allow-list by design: each legacy unit requires `conn:nTP-v1` and a clause
of `legacy:<provider id>` tokens, which only these built-ins may name (D4's reserved `legacy`
space), so no extension can join a closed legacy family.
"""

from __future__ import annotations

import json
from importlib import resources
from typing import Any, Final

#: The built-in table whose descriptors are D6's legacy forms (`stability` core for their kinds).
TABLE_NAME: Final = "legacy"
#: The table's package-data path, relative to `openflowsheet.registry`.
TABLE_PATH: Final = "builtin/legacy.json"
#: D6: the connection definition every legacy method provides and every legacy unit requires.
CONNECTION_DEFINITION: Final = "nTP-v1"


def table() -> list[dict[str, Any]]:
    """The legacy table's descriptors, sorted by (kind, id), read through `importlib.resources`."""
    path = resources.files("openflowsheet.registry").joinpath(*TABLE_PATH.split("/"))
    loaded: list[dict[str, Any]] = json.loads(path.read_text(encoding="utf-8"))
    return loaded
