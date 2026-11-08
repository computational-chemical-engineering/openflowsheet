"""RRC WO-4 (ADR 0072; design note `docs/design/RRC-revision-region-continuation.md` §5.3, §5.4,
§5.8, §5.9, §8.2): revision continuation's application half.

- **A3** (§5.4): the registered allowlist of continuable differences, default deny, on the
  registered documents (NET-02, S11's M1-recycle, T08's kinetic CSTR).
- **The member and the R0 branch** (§5.8): a bundle without the member projects exactly as
  before, and the branch carries no float.
"""

from __future__ import annotations

import copy
from typing import Any

import pytest
from s11_column_support import RECYCLE_CASE, committed_case
from t06_support import case_document
from t08_cstr_support import liquid_variant_revision

from openflowsheet.application.revision_continuation import (
    CONTINUABLE_SPECIFICATION_PATHS,
    not_continuable,
)
from openflowsheet.models.revision_flowsheet import TARGET_PATH_KINDS

NET02 = "SYN-001-T06-NET02"


def _instance(document: dict[str, Any], unit: str) -> dict[str, Any]:
    (item,) = [item for item in document["instances"] if item["id"] == unit]
    found: dict[str, Any] = item
    return found


def _edited(document: dict[str, Any], edit: Any) -> dict[str, Any]:
    edited = copy.deepcopy(document)
    edit(edited)
    return edited


# -- A3: continuable differences (§5.4) -----------------------------------------------------------


def test_the_specification_paths_are_all_of_the_binders_target_paths() -> None:
    assert set(TARGET_PATH_KINDS) == CONTINUABLE_SPECIFICATION_PATHS


def _split(value: float) -> Any:
    def edit(document: dict[str, Any]) -> None:
        _instance(document, "U-SPLIT")["parameters"]["split_fraction"]["value"] = value

    return edit


def _spec_value(document: dict[str, Any]) -> None:
    document["specifications"][0]["value"] = 1.25


def _spec_tolerance(document: dict[str, Any]) -> None:
    document["specifications"][0]["tolerance"]["absolute"] = 1e-10


def _connection_notes(document: dict[str, Any]) -> None:
    document["connections"][0]["notes"] = "edited"


def _retitled(document: dict[str, Any]) -> None:
    document["title"] = "another title"
    document["description"] = "another description"


def _component_set(document: dict[str, Any]) -> None:
    document["component_set"] = {**document["component_set"], "extra": True}


def _added_instance(document: dict[str, Any]) -> None:
    document["instances"].append({**_instance(document, "U-SINK-P"), "id": "U-SINK-Q"})


def _model(document: dict[str, Any]) -> None:
    _instance(document, "U-HEAT")["model"]["version"] = "0.0.1-declared"


def _meaning(document: dict[str, Any]) -> None:
    _instance(document, "U-SPLIT")["parameters"]["split_fraction"]["meaning"] = "edited"


def _bounds(document: dict[str, Any]) -> None:
    _instance(document, "U-SPLIT")["parameters"]["split_fraction"]["bounds"]["upper"] = 0.99


#: (edit of NET-02, A3's verdict): `None` is continuable.
A3_NET02 = {
    "split_fraction": (_split(0.5), None),
    "split_and_title": (lambda d: (_split(0.5)(d), _retitled(d)), None),
    "specification_value": (_spec_value, None),
    "parameter_meaning": (_meaning, None),
    "specification_tolerance": (
        _spec_tolerance,
        "not_continuable(specifications:SPEC-S1-n-A:tolerance.absolute)",
    ),
    "parameter_bounds": (
        _bounds,
        "not_continuable(instances:U-SPLIT:parameters.split_fraction.bounds.upper)",
    ),
    "connection_notes": (_connection_notes, "not_continuable(connections:S1:notes)"),
    "component_set": (_component_set, "not_continuable(component_set)"),
    "added_instance": (_added_instance, "not_continuable(instances:U-SINK-Q)"),
    "model": (_model, "not_continuable(instances:U-HEAT:model.version)"),
}


@pytest.mark.parametrize("case", list(A3_NET02))
def test_a3_on_net02(case: str) -> None:
    edit, expected = A3_NET02[case]
    source = case_document(NET02)
    assert not_continuable(source, _edited(source, edit)) == expected


def test_a3_the_first_offence_is_reported_in_element_diff_order() -> None:
    """Top-level members first, then `instances`, `connections`, `specifications` (§5.3 A3)."""
    source = case_document(NET02)

    def everything(document: dict[str, Any]) -> None:
        _spec_tolerance(document)
        _connection_notes(document)
        _model(document)

    assert not_continuable(source, _edited(source, everything)) == (
        "not_continuable(instances:U-HEAT:model.version)"
    )
    both = _edited(source, lambda d: (everything(d), _component_set(d)))
    assert not_continuable(source, both) == "not_continuable(component_set)"


def test_a3_a_column_stage_count_is_not_continuable_and_its_end_specifications_are() -> None:
    """G6 (d)'s reason; F1's change (reflux and boil-up) and a stage pressure are continuable."""
    source = committed_case(RECYCLE_CASE)
    column = _instance(source, "S02")["parameters"]

    def stages(document: dict[str, Any]) -> None:
        _instance(document, "S02")["parameters"]["stage_count"]["value"] = 8

    def ends(document: dict[str, Any]) -> None:
        parameters = _instance(document, "S02")["parameters"]
        parameters["condenser_reflux_ratio"]["value"] = 4.0
        parameters["reboiler_boilup_ratio"]["value"] = 3.0
        parameters["stage_pressure.3"]["value"] = column["stage_pressure.3"]["value"] * 1.01

    def feed_stage(document: dict[str, Any]) -> None:
        entry = _instance(document, "S02")["parameters"]["feed_stage.S-IN1"]
        entry["value"] = entry["value"] - 1

    assert not_continuable(source, _edited(source, stages)) == (
        "not_continuable(instances:S02:parameters.stage_count.value)"
    )
    assert not_continuable(source, _edited(source, ends)) is None
    assert not_continuable(source, _edited(source, feed_stage)) == (
        "not_continuable(instances:S02:parameters.feed_stage.S-IN1.value)"
    )


def test_a3_a_kinetic_constant_is_not_continuable_and_the_coolant_is() -> None:
    """G6 (k)'s reason on T08's kinetic CSTR; `coolant_flow` and `T_coolant` are continuable,
    `coolant_cp`, `nu`, `T_ref` and `T_scale` are not."""
    source = liquid_variant_revision()

    def setting(key: str, factor: float) -> Any:
        def edit(document: dict[str, Any]) -> None:
            entry = _instance(document, "U-CSTR")["parameters"][key]
            entry["value"] = entry["value"] * factor

        return edit

    assert not_continuable(source, _edited(source, setting("damkohler.B", 2.0))) == (
        "not_continuable(instances:U-CSTR:parameters.damkohler.B.value)"
    )
    for key in ("coolant_flow", "T_coolant"):
        assert not_continuable(source, _edited(source, setting(key, 1.01))) is None, key
    for key in ("coolant_cp", "nu.A", "T_ref", "T_scale"):
        assert not_continuable(source, _edited(source, setting(key, 1.01))) == (
            f"not_continuable(instances:U-CSTR:parameters.{key}.value)"
        ), key
