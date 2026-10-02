"""T08.A10 (D1): STR-03, STR-04 and STR-05 name the revision's instance ids, not the binder's ids.

T08 release spec §6.1 D1, §9 A10. The legacy SYN-001 binder assembles the heater as unit `U-HEAT`;
STR-03's message named that id, which the caller never wrote. State (i) is the registered
`SYN-001-conflicting-heater-spec` (its registered fields, T01 A09, must not move); state (ii) is the
same revision with the heater instance renamed `h-2` and the specifications that point at it
re-pointed, which catches a fix that hard-codes `heater`.

STR-04 follows the T08 review's §3.3 (P-STR04): row ids `<unit>:<equation>[:<port>]` and
parameter ids `<unit>.<parameter>` are named by the instance, through the helper STR-03 and STR-05
use (`binding.instance_named`), on T01's two conflict states with the flash renamed `f-2`.
"""

from __future__ import annotations

import ast
import copy
import re
from typing import Any

import pytest
from t07_corpus import CORPUS

from openflowsheet.application.validation import validate

_UNITS = re.compile(r"over-specified units (\[[^\]]*\])")


def _renamed(document: dict[str, Any], old: str, new: str) -> dict[str, Any]:
    """`document` with instance `old` renamed `new`, and every connection end and specification
    target that names it re-pointed."""
    renamed = copy.deepcopy(document)
    for instance in renamed["instances"]:
        if instance["id"] == old:
            instance["id"] = new
    for connection in renamed["connections"]:
        for end in ("from", "to"):
            if connection[end]["instance"] == old:
                connection[end]["instance"] = new
    for specification in renamed["specifications"]:
        target = specification["target"]
        if target["object_type"] == "instance" and target["object_id"] == old:
            target["object_id"] = new
    return renamed


@pytest.mark.parametrize("instance_id", ["heater", "h-2"])
def test_a10_str03_names_the_revision_instance(instance_id: str) -> None:
    document = CORPUS["SYN-001-conflicting-heater-spec"]()
    if instance_id != "heater":
        document = _renamed(document, "heater", instance_id)
        assert not any(i["id"] == "heater" for i in document["instances"])

    report = validate(document)

    assert report.status == "INVALID"
    [check] = [c for c in report.checks if c.id == "STR-03"]
    assert check.result == "FAIL"
    assert check.message.startswith("STRUCTURAL_OVER_SPECIFICATION: excess 1; ")
    assert check.implicated_objects == ("SPEC-heater-outlet-T", "SPEC-heater-duty", instance_id)
    units = _UNITS.search(check.message)
    assert units is not None, check.message
    assert ast.literal_eval(units.group(1)) == [instance_id]
    assert "U-HEAT" not in check.message
    if instance_id != "heater":
        # The specification ids keep their names (`SPEC-heater-…`); no instance named `heater`.
        assert "'heater'" not in check.message


# -- D1 extended to STR-05 (Frank, 2026-09-29, Q-P1-2) ------------------------------------------

_LOOP = re.compile(r"loop (\[[^\]]*\]) torn at")
_SIGNATURE = re.compile(r"attempt signature (\[[^\]]*\])")
BINDER_UNITS = ("U-MIX", "U-HEAT", "U-FLASH", "U-SPLIT")


@pytest.mark.parametrize("flash_id", ["flash", "f-2"])
def test_str05_names_the_loop_and_the_attempt_signature_by_instance(flash_id: str) -> None:
    """SYN-001-nominal binds through the legacy binder (units `U-MIX`, `U-HEAT`, `U-FLASH`,
    `U-SPLIT`); STR-05 names the loop's units and the attempt signature by the revision's
    instances, and follows a renamed flash instance (which catches a hard-coded `flash`)."""
    document = CORPUS["SYN-001-nominal"]()
    if flash_id != "flash":
        document = _renamed(document, "flash", flash_id)
        assert not any(i["id"] == "flash" for i in document["instances"])

    report = validate(document)

    assert report.status == "READY_FOR_SIMULATION"
    [check] = [c for c in report.checks if c.id == "STR-05"]
    assert check.result == "PASS"
    loop, signature = _LOOP.search(check.message), _SIGNATURE.search(check.message)
    assert loop is not None and signature is not None, check.message
    assert ast.literal_eval(loop.group(1)) == ["mixer", "heater", flash_id, "splitter"]
    assert ast.literal_eval(signature.group(1)) == [flash_id]
    assert not any(unit in check.message for unit in BINDER_UNITS)


# -- P-STR04: one rule for STR-03, STR-04 and STR-05 (T08 review §3.3) --------------------------

#: A binder unit id (`U-FLASH`, `U-FEED`, …), alone or as the prefix of a row or parameter id.
_BINDER_ID = re.compile(r"(?<![\w-])U-[A-Z]+")


def _flash_pressure_conflict() -> dict[str, Any]:
    """K03 §7.2's registered conflict (T01 M2): the flash at 150 kPa against a feed at 100 kPa.
    Two certified rows disagree, so STR-04 names row ids."""
    document = CORPUS["SYN-001-nominal"]()
    for specification in document["specifications"]:
        if specification["id"] == "SPEC-flash-P":
            specification["value"] = 150_000.0
    return document


def _vapor_temperature_conflict() -> dict[str, Any]:
    """T01's R-022 state: a second specification pins the vapour outlet at 370 K where the
    flash's pins it at 360 K. The binder refuses (`binding.py`, SPECIFICATION_CONFLICT), naming
    the flash's temperature parameter."""
    document = CORPUS["SYN-001-nominal"]()
    document["specifications"].append(
        {
            "id": "SPEC-vapor-T",
            "target": {
                "object_type": "connection",
                "object_id": "S4",
                "path": "state.T",
                "component": None,
            },
            "kind": "temperature",
            "unit": "K",
            "value": 370.0,
            "tolerance": {"absolute": 1.0e-06},
            "role": "fixed",
            "provenance": document["specifications"][0]["provenance"],
        }
    )
    return document


def _structural_messages(document: dict[str, Any]) -> dict[str, str]:
    report = validate(document)
    return {c.id: c.message for c in report.checks if c.id.startswith("STR-")}


@pytest.mark.parametrize("flash_id", ["flash", "f-2"])
def test_str04_names_certified_rows_by_instance(flash_id: str) -> None:
    """Row ids `<unit>:<equation>[:<port>]` become `<instance>:<equation>[:<port>]`; the
    equation id and the port are the model's contract and stay."""
    document = _flash_pressure_conflict()
    if flash_id != "flash":
        document = _renamed(document, "flash", flash_id)
    messages = _structural_messages(document)
    assert messages["STR-04"].startswith(
        f"SPECIFICATION_CONFLICT: {flash_id}:FLASH-P:inlet repeats "
        "['feed:FEED-P', 'heater:HEAT-pressure', 'mixer:MIX-pressure:0'] but disagrees by -50000"
    ), messages["STR-04"]
    assert (
        f"splitter:SPLIT-P:recycle repeats ['feed:FEED-P', '{flash_id}:FLASH-P:liquid'"
        in (messages["STR-04"])
    )


@pytest.mark.parametrize("flash_id", ["flash", "f-2"])
def test_str04_names_the_refused_parameter_by_instance(flash_id: str) -> None:
    """A binder-internal parameter the revision never names (SYN-001's `T_spec`) is named by the
    specification ids that set it, which the refusal already names; its token becomes
    `<instance>.<parameter>` and nothing is added."""
    document = _vapor_temperature_conflict()
    if flash_id != "flash":
        document = _renamed(document, "flash", flash_id)
    messages = _structural_messages(document)
    assert messages["STR-04"] == (
        f"SPECIFICATION_CONFLICT: SPEC-vapor-T and SPEC-flash-T both fix {flash_id}.T_spec, "
        "to 370 and 360; no state satisfies both"
    )


@pytest.mark.parametrize(
    ("state", "old", "new"),
    [
        (_flash_pressure_conflict, "flash", "f-2"),
        (_vapor_temperature_conflict, "flash", "f-2"),
        (lambda: CORPUS["SYN-001-conflicting-heater-spec"](), "heater", "h-2"),
        (lambda: CORPUS["SYN-001-nominal"](), "flash", "f-2"),
    ],
)
def test_a10_no_str_message_names_a_binder_unit_or_the_old_instance(
    state: Any, old: str, new: str
) -> None:
    """T08.A10's pattern (ii) over every STR-0x message (review §3.3): with the instance renamed,
    no message names a `U-…` binder id, and none names the old instance id as an id — alone in a
    list, or as the prefix of a row (`:`) or parameter (`.`) id. Specification ids keep their
    names (`SPEC-flash-T`), which the lookbehind excludes."""
    messages = _structural_messages(_renamed(state(), old, new))
    old_as_id = re.compile(rf"(?<![\w-]){re.escape(old)}(?=[:.'])")
    for check_id, message in messages.items():
        assert not _BINDER_ID.search(message), (check_id, message)
        assert not old_as_id.search(message), (check_id, message)
    assert any(new in message for message in messages.values())
