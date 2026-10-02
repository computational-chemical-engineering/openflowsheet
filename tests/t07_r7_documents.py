"""The documents of gates G-R6-7 and G-R7-3 (T07 design note, ruling rounds 6 and 7). Not collected.

Each is `SYN-001-A02-360` (on `legacy_eo`, `VERIFIED` at W3a) or `SYN-001-nominal` with one edit,
under the ids the ruling's table gives. m1–m4 are round 6's (R6-W6); m5–m16 are `READY` on
`legacy_eo` at `86ab418` (the round-7 ruling measured it), and ruling round 7 refuses each:

- **m1** the flash's `pressure_drop` set to 50000 Pa (`syn001.tp_flash` admits only 0);
- **m2** `S3` declared `liquid` (the heater's outlet takes `vapor_liquid`);
- **m3** the heater given `efficiency` 0.9 (`syn001.tp_heater` reads no such parameter);
- **m4** one more specification, with role `decision` (outside the class: `legacy_answers`);
- **m5** `SPEC-flash-P` removed (the drum pressure unpinned);
- **m6** a fixed `X-eff` on the heater's `parameters.efficiency`, 0.9;
- **m7** a fixed `X-x` on `S2` `state.x`, 300 K (an unknown path);
- **m8** `SYN-001-nominal` plus a free `X-f6` on `S6` `state.T`, 355 K (it frees nothing);
- **m9** `SYN-001-nominal` plus a free `X-f3` on `S3` `state.T`, 358 K (a coordinate a fixed one
  pins);
- **m10** the flash's `pressure_drop` parameter removed and a fixed `X-flash-dp` on the flash's
  `parameters.pressure_drop`, 50000 Pa;
- **m11** a fixed `X-mixQ` on the mixer's `duty.Q`, 5 W (the legacy binder drops it);
- **m12** a free `X-f6` on `S6` `state.T`, 355 K;
- **m13** as m9, at 350 K (the fixed value);
- **m14** `SPEC-flash-T` replaced by a fixed `X-S4T` on `S4` `state.T`, 360 K (`S5.T` unpinned);
- **m15** `SPEC-flash-T` and `SPEC-flash-P` removed and the fixed `X-S4T` added (T02-2's shape);
- **m16** a free `X-fr` on the splitter's `parameters.split_fraction`, 0.4.
"""

from __future__ import annotations

import copy
from collections.abc import Callable
from typing import Any

from t07_corpus import CORPUS

Document = dict[str, Any]
BASE = "SYN-001-A02-360"
NOMINAL = "SYN-001-nominal"


def _instance(document: Document, unit: str) -> Document:
    found: Document = next(entry for entry in document["instances"] if entry["id"] == unit)
    return found


def _without(document: Document, *names: str) -> Document:
    document["specifications"] = [
        entry for entry in document["specifications"] if entry["id"] not in names
    ]
    return document


def _with(
    document: Document,
    name: str,
    role: str,
    target: tuple[str, str, str],
    value: float,
    kind: str = "temperature",
    unit: str = "K",
) -> Document:
    """`document` with one more specification, shaped like its first fixed one."""
    object_type, object_id, path = target
    added = copy.deepcopy(next(e for e in document["specifications"] if e["role"] == "fixed"))
    added.update(id=name, role=role, value=value, kind=kind, unit=unit)
    added["target"] = {
        "object_type": object_type,
        "object_id": object_id,
        "path": path,
        "component": None,
    }
    document["specifications"].append(added)
    return document


def m1(document: Document) -> Document:
    _instance(document, "flash")["parameters"]["pressure_drop"]["value"] = 50000.0
    return document


def m2(document: Document) -> Document:
    (s3,) = [entry for entry in document["connections"] if entry["id"] == "S3"]
    s3["phase_capability"] = "liquid"
    return document


def m3(document: Document) -> Document:
    efficiency = copy.deepcopy(_instance(document, "splitter")["parameters"]["split_fraction"])
    efficiency.update(value=0.9, meaning="A heater efficiency the model does not read.")
    efficiency.pop("bounds", None)
    _instance(document, "heater")["parameters"]["efficiency"] = efficiency
    return document


def m4(document: Document) -> Document:
    (feed_t,) = [entry for entry in document["specifications"] if entry["id"] == "SPEC-feed-T"]
    decision = copy.deepcopy(feed_t)
    decision.update(id="DECISION-feed-T", role="decision")
    document["specifications"].append(decision)
    return document


def m5(document: Document) -> Document:
    return _without(document, "SPEC-flash-P")


def m6(document: Document) -> Document:
    return _with(
        document,
        "X-eff",
        "fixed",
        ("instance", "heater", "parameters.efficiency"),
        0.9,
        "dimensionless",
        "1",
    )


def m7(document: Document) -> Document:
    return _with(document, "X-x", "fixed", ("connection", "S2", "state.x"), 300.0)


def m8(document: Document) -> Document:
    return _with(document, "X-f6", "free", ("connection", "S6", "state.T"), 355.0)


def m9(document: Document) -> Document:
    return _with(document, "X-f3", "free", ("connection", "S3", "state.T"), 358.0)


def m10(document: Document) -> Document:
    del _instance(document, "flash")["parameters"]["pressure_drop"]
    return _with(
        document,
        "X-flash-dp",
        "fixed",
        ("instance", "flash", "parameters.pressure_drop"),
        50000.0,
        "pressure",
        "Pa",
    )


def m11(document: Document) -> Document:
    return _with(
        document, "X-mixQ", "fixed", ("instance", "mixer", "duty.Q"), 5.0, "heat_rate", "W"
    )


def m12(document: Document) -> Document:
    return _with(document, "X-f6", "free", ("connection", "S6", "state.T"), 355.0)


def m13(document: Document) -> Document:
    return _with(document, "X-f3", "free", ("connection", "S3", "state.T"), 350.0)


def m14(document: Document) -> Document:
    return _with(
        _without(document, "SPEC-flash-T"), "X-S4T", "fixed", ("connection", "S4", "state.T"), 360.0
    )


def m15(document: Document) -> Document:
    return _with(
        _without(document, "SPEC-flash-T", "SPEC-flash-P"),
        "X-S4T",
        "fixed",
        ("connection", "S4", "state.T"),
        360.0,
    )


def m16(document: Document) -> Document:
    return _with(
        document,
        "X-fr",
        "free",
        ("instance", "splitter", "parameters.split_fraction"),
        0.4,
        "dimensionless",
        "1",
    )


#: Mutation -> (the corpus revision it edits, its edit).
MUTATIONS: dict[str, tuple[str, Callable[[Document], Document]]] = {
    "m1": (BASE, m1),
    "m2": (BASE, m2),
    "m3": (BASE, m3),
    "m4": (BASE, m4),
    "m5": (BASE, m5),
    "m6": (BASE, m6),
    "m7": (BASE, m7),
    "m8": (NOMINAL, m8),
    "m9": (NOMINAL, m9),
    "m10": (BASE, m10),
    "m11": (BASE, m11),
    "m12": (BASE, m12),
    "m13": (NOMINAL, m13),
    "m14": (BASE, m14),
    "m15": (BASE, m15),
    "m16": (BASE, m16),
}


def mutated(name: str) -> Document:
    """A fresh copy of mutation `name`'s document."""
    base, edit = MUTATIONS[name]
    return edit(CORPUS[base]())
