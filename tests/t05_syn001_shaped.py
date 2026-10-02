"""The SYN-001-shaped revision: SYN-001's physics in the general machinery (T05 design note §7).

Not collected as tests. `benchmarks/syn001/cases/SYN-001-nominal.yaml` with its instance ids
renamed to the legacy flowsheet's unit ids — in `instances`, in connection endpoints and in
specification targets — and nothing else changed. Bound by `bind_revision_flowsheet`, it must
reproduce `Syn001Flowsheet`'s declaration and traversal, which is the reference every W1 seam is
tested against before any T05 model exists.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from conftest import load_yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
NOMINAL = REPO_ROOT / "benchmarks" / "syn001" / "cases" / "SYN-001-nominal.yaml"

#: Revision instance id -> the legacy flowsheet's unit id.
RENAMES: dict[str, str] = {
    "feed": "U-FEED",
    "mixer": "U-MIX",
    "heater": "U-HEAT",
    "flash": "U-FLASH",
    "splitter": "U-SPLIT",
    "vapor_product": "U-PROD",
    "purge": "U-PURGE",
}

_NOMINAL: dict[str, Any] = load_yaml(NOMINAL)


def shaped_revision() -> dict[str, Any]:
    """A fresh copy of the SYN-001-shaped revision; callers may mutate it."""
    document = copy.deepcopy(_NOMINAL)
    for instance in document["instances"]:
        instance["id"] = RENAMES[instance["id"]]
    for connection in document["connections"]:
        for end in ("from", "to"):
            connection[end]["instance"] = RENAMES[connection[end]["instance"]]
    for specification in document["specifications"]:
        target = specification["target"]
        if target["object_type"] == "instance":
            target["object_id"] = RENAMES[target["object_id"]]
    return document
