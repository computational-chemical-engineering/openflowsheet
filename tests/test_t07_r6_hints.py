"""T07 ruling round 6, B2 (R6-W3): every missing pin and every specification refusal names what is
accepted, beside an unchanged code (gate G-R6-5).

Design note `docs/design/T07-jobs-and-bindings.md`, "Ruling round 6", B2 items 1–2.

- **(i) Repair.** For every model in `MODEL_BUILDERS`, every pin and choice option, and every
  encoding `pin_encodings` gives it: a corpus revision that pins it (or the named synthetic one
  below), its specifications that fix the encoding's pins removed, is refused
  `specification_missing` with a hint that renders the encoding; the encoding rendered with the
  removed value binds to the same declaration (`spec.variable_ids`, row ids, every instance's
  pins). Every (model, pin, encoding) triple is listed as covered.
- **(ii) The T05-2 chain**, on the `v17-c1` T05-2 agent's own `rev-000002`.
- **(iii)** The code tokens are the registered ones (`9165894`'s; the whole-corpus comparison is
  in `docs/T07_DECISIONS.md`, rf3a), and every hint is at most 512 code points.
"""

from __future__ import annotations

import copy
import re
from pathlib import Path
from typing import Any

import pytest
from t07_corpus import CORPUS
from t07_v17_c1_documents import c1_document

from openflowsheet.application.binding import HINT_LIMIT, Unbound
from openflowsheet.application.policies import DEFAULT_POLICY_ID, resolve_policy
from openflowsheet.application.revision_binding import (
    MODEL_BUILDERS,
    MODEL_SIGNATURES,
    Encoding,
    ModelSignature,
    PinColumn,
    RevisionBinding,
    bind_revision_flowsheet,
    pin_encodings,
    render_encoding,
)
from openflowsheet.application.revision_binding import _columns as _columns
from openflowsheet.application.revision_run import Route, run_revision_session, select_route
from openflowsheet.application.validation import validate
from openflowsheet.models.revision_flowsheet import (
    InstanceView,
    RevisionError,
    convert_specification,
    parse_revision,
    pin_specifications,
)
from openflowsheet.verify.certificate import CheckPolicy

Document = dict[str, Any]


def _options(signature: ModelSignature) -> tuple[PinColumn, ...]:
    return (*signature.pins, *(option for choice in signature.choices for option in choice.options))


#: Every (model, pin, encoding) triple the revision binder reads.
TRIPLES = [
    (model_id, pin.name, index)
    for model_id in sorted(MODEL_BUILDERS)
    for pin in _options(MODEL_SIGNATURES[model_id])
    for index in range(len(pin_encodings(MODEL_SIGNATURES[model_id], pin)))
]


def test_every_model_has_a_signature_and_the_triples_are_counted() -> None:
    assert set(MODEL_SIGNATURES) == set(MODEL_BUILDERS)
    # feed 5, TP heater 2, TP flash 8, PH flash 1, valve 2, pump 2, reactor 2, exchanger 3.
    assert len(TRIPLES) == 25


def _view(document: Document, unit: str) -> InstanceView:
    (view,) = [view for view in parse_revision(document).instances if view.unit_id == unit]
    return view


def _same_declaration(before: Document, after: Document) -> None:
    first, second = bind_revision_flowsheet(before), bind_revision_flowsheet(after)
    assert isinstance(first, RevisionBinding), first
    assert isinstance(second, RevisionBinding), second
    assert second.spec.variable_ids == first.spec.variable_ids
    assert sorted(second.row_units) == sorted(first.row_units)
    pins = {view.unit_id: dict(view.pins) for view in parse_revision(before).instances}
    assert {view.unit_id: dict(view.pins) for view in parse_revision(after).instances} == pins


def _columns_of(view: InstanceView, signature: ModelSignature, name: str) -> tuple[str, ...]:
    """The column ids of the pin or option `name` on this instance."""
    (pin,) = [option for option in _options(signature) if option.name == name]
    return _columns(view, pin, ("A", "B", "C"))


def _pinning(document: Document, unit: str, model_id: str, pin: PinColumn) -> bool:
    signature = MODEL_SIGNATURES[model_id]
    view = _view(document, unit)
    return all(column in view.pins for column in _columns_of(view, signature, pin.name))


def _synthetic_reactor_duty() -> tuple[str, Document]:
    """SYN-001-T06-NET09 with its reactor's energy specification switched from the outlet
    temperature to the duty (0 W, adiabatic): no corpus revision pins a reactor duty."""
    document = CORPUS["SYN-001-T06-NET09"]()
    (spec,) = [
        entry for entry in document["specifications"] if entry["target"]["object_id"] == "S3"
    ]
    spec.update(
        id="SPEC-RX-duty",
        kind="heat_rate",
        unit="W",
        value=0.0,
        target={"object_type": "instance", "object_id": "U-RX", "path": "duty.Q"},
    )
    return "synthetic:NET09-reactor-duty", document


def _synthetic_exchanger_cold() -> tuple[str, Document]:
    """SYN-001-T06-NET06 with its exchanger's specification switched from the hot outlet's
    temperature (S5) to the cold outlet's (S2), at 300 K: no corpus revision pins the cold side."""
    document = CORPUS["SYN-001-T06-NET06"]()
    (spec,) = [e for e in document["specifications"] if e["id"] == "SPEC-hx-hot-outlet-T"]
    spec.update(id="SPEC-hx-cold-outlet-T", value=300.0)
    spec["target"]["object_id"] = "S2"
    return "synthetic:NET06-exchanger-cold", document


def _bases() -> list[tuple[str, Document]]:
    bases = [(name, CORPUS[name]()) for name in sorted(CORPUS)]
    bases.append(_synthetic_reactor_duty())
    bases.append(_synthetic_exchanger_cold())
    # Every corpus TP flash is pinned in the instance form, which fixes both outlets; the
    # `v17-c1` T02-1 agent's revision pins each outlet's T and P on its connection.
    bases.append(("v17-c1:T02-1/rev-000002", c1_document("T02-1", "rev-000002")))
    return [
        (name, document)
        for name, document in bases
        if isinstance(bind_revision_flowsheet(copy.deepcopy(document)), RevisionBinding)
    ]


BASES = _bases()


def _base(model_id: str, pin: PinColumn, fixes: tuple[str, ...]) -> tuple[str, Document, str]:
    """The first base that pins every pin `fixes` names on an instance of `model_id`, with every
    specification that pins one of those columns pinning only those columns, in SI."""
    signature = MODEL_SIGNATURES[model_id]
    for name, document in BASES:
        sources = pin_specifications(document)
        for instance in document["instances"]:
            if instance["model"]["id"] != model_id:
                continue
            unit = instance["id"]
            view = _view(document, unit)
            columns = {c for f in fixes for c in _columns_of(view, signature, f)}
            if not columns <= set(view.pins):
                continue
            removed = {spec for column in columns for spec in sources[column]}
            reach = {column for column, specs in sources.items() if set(specs) & removed}
            by_id = {entry["id"]: entry for entry in document["specifications"]}
            in_si = all(by_id[spec]["unit"] in ("K", "Pa", "mol/s", "W") for spec in removed)
            if reach == columns and in_si:
                return name, document, unit
    raise LookupError(f"no base pins {model_id} {pin.name} {fixes}")


_RENDERED = re.compile(
    r"kind (?P<kind>\S+), unit (?P<unit>\S+), target \{object_type: (?P<object_type>\w+), "
    r"object_id: (?P<object_id>[^,]+), path: (?P<path>[^,}]+)"
    r"(?:, component: (?P<component>\w+))?\}"
)


def _repair(model_id: str, name: str, index: int) -> str:
    """G-R6-5 (i) for one triple; returns the base it was proved on."""
    signature = MODEL_SIGNATURES[model_id]
    (pin,) = [option for option in _options(signature) if option.name == name]
    encoding: Encoding = pin_encodings(signature, pin)[index]
    base_name, document, unit = _base(model_id, pin, encoding.fixes)
    view = _view(document, unit)
    columns = [c for f in encoding.fixes for c in _columns_of(view, signature, f)]
    sources = pin_specifications(document)
    removed_ids = {spec for column in columns for spec in sources[column]}
    template = next(e for e in document["specifications"] if e["id"] in removed_ids)

    # The specifications that fix the encoding's pins, removed: the missing pin is refused.
    removed = copy.deepcopy(document)
    removed["specifications"] = [
        entry for entry in removed["specifications"] if entry["id"] not in removed_ids
    ]
    refusal = bind_revision_flowsheet(copy.deepcopy(removed))
    assert isinstance(refusal, Unbound), base_name
    assert refusal.kind == "incomplete", refusal
    column = refusal.detail.removeprefix("specification_missing(").removesuffix(")")
    choice = next((c for c in signature.choices if pin in c.options), None)
    reported: PinColumn
    if choice is not None:
        # A choice option: the choice is reported, with each option's first encoding.
        assert column == f"{unit}.{choice.name}"
        reported, component = pin, None
    else:
        assert column in columns, (refusal.detail, columns)
        (reported,) = [
            signature.pin(f) for f in encoding.fixes if column in _columns_of(view, signature, f)
        ]
        component = column.rsplit(".", 1)[1] if reported.quantity == "flow" else None
    assert refusal.hint is not None and len(refusal.hint) <= HINT_LIMIT
    # The reported pin's encoding of this form, which pins the same columns, is in the hint.
    (same,) = [
        e
        for e in pin_encodings(signature, reported)
        if (e.object_type, e.path) == (encoding.object_type, encoding.path)
    ]
    assert set(same.fixes) == set(encoding.fixes)
    text = render_encoding(same, view, signature, ("A", "B", "C"), component)
    assert text in refusal.hint, (base_name, refusal.hint)

    # The hint's encoding rendered, with the removed value, binds to the same declaration.
    match = _RENDERED.match(text)
    assert match is not None, text
    repaired = copy.deepcopy(removed)
    for each in ("A", "B", "C") if encoding.component is not None else (None,):
        pinned = [c for c in columns if each is None or c.endswith(f".{each}")]
        (value,) = {view.pins[c] for c in pinned}
        entry = copy.deepcopy(template)
        entry.update(
            id=f"{template['id']}-repair{'' if each is None else '-' + each}",
            kind=match["kind"],
            unit=match["unit"],
            value=value,
            target={
                "object_type": match["object_type"],
                "object_id": match["object_id"],
                "path": match["path"],
                "component": each,
            },
        )
        repaired["specifications"].append(entry)
    _same_declaration(document, repaired)
    return base_name


@pytest.mark.parametrize(("model_id", "name", "index"), TRIPLES)
def test_g_r6_5_i_the_hint_repairs_the_removed_pin(model_id: str, name: str, index: int) -> None:
    _repair(model_id, name, index)


#: G-R6-5 (i): the base each (model, pin, encoding) triple is proved on.
COVERED = {
    "syn001.conversion_reactor/outlet_temperature/0": "SYN-001-T06-NET09",
    "syn001.conversion_reactor/duty/0": "synthetic:NET09-reactor-duty",
    "syn001.feed_source/flows/0": "SYN-001-T06-NET02",
    "syn001.feed_source/temperature/0": "SYN-001-T06-NET02",
    "syn001.feed_source/temperature/1": "SYN-001-T06-NET02",
    "syn001.feed_source/pressure/0": "SYN-001-T06-NET02",
    "syn001.feed_source/pressure/1": "SYN-001-T06-NET02",
    "syn001.heat_exchanger/hot_outlet_temperature/0": "SYN-001-T06-NET06",
    "syn001.heat_exchanger/cold_outlet_temperature/0": "synthetic:NET06-exchanger-cold",
    "syn001.heat_exchanger/duty/0": "T05b:DZ-7",
    "syn001.liquid_pump/outlet_pressure/0": "SYN-001-T06-NET11",
    "syn001.liquid_pump/outlet_pressure/1": "SYN-001-T06-NET11",
    "syn001.ph_flash/duty/0": "SYN-001-T06-NET02",
    "syn001.tp_flash/temperature/0": "v17-c1:T02-1/rev-000002",
    "syn001.tp_flash/temperature/1": "SYN-001-T06-NET03",
    "syn001.tp_flash/pressure/0": "v17-c1:T02-1/rev-000002",
    "syn001.tp_flash/pressure/1": "SYN-001-T06-NET03",
    "syn001.tp_flash/liquid_temperature/0": "v17-c1:T02-1/rev-000002",
    "syn001.tp_flash/liquid_temperature/1": "SYN-001-T06-NET03",
    "syn001.tp_flash/liquid_pressure/0": "v17-c1:T02-1/rev-000002",
    "syn001.tp_flash/liquid_pressure/1": "SYN-001-T06-NET03",
    "syn001.tp_heater/outlet_temperature/0": "SYN-001-T06-NET02",
    "syn001.tp_heater/outlet_temperature/1": "SYN-001-T06-NET02",
    "syn001.valve/outlet_pressure/0": "SYN-001-T06-NET11",
    "syn001.valve/outlet_pressure/1": "SYN-001-T06-NET11",
}


def test_g_r6_5_i_every_triple_is_covered() -> None:
    covered = {f"{m}/{n}/{i}": _repair(m, n, i) for m, n, i in TRIPLES}
    assert covered == COVERED


# -- (ii) the T05-2 chain -----------------------------------------------------------------------


def _t05_2() -> Document:
    return c1_document("T05-2", "rev-000002")


def _duty(document: Document) -> Document:
    (entry,) = [e for e in document["specifications"] if e["id"] == "SPEC-flash-duty"]
    found: Document = entry
    return found


def test_g_r6_5_ii_as_committed_power_at_q_names_duty_q() -> None:
    document = _t05_2()
    assert (_duty(document)["kind"], _duty(document)["target"]["path"]) == ("power", "Q")
    refusal = bind_revision_flowsheet(document)
    assert isinstance(refusal, Unbound)
    assert (refusal.kind, refusal.detail) == (
        "unsupported",
        "specification_unsupported(SPEC-flash-duty)",
    )
    assert refusal.hint == (
        "Instance U-FLASH (syn001.ph_flash) takes path duty.Q (heat_rate, W) or "
        "parameters.pressure_drop."
    )


def test_g_r6_5_ii_power_at_duty_q_names_heat_rate() -> None:
    document = _t05_2()
    _duty(document)["target"]["path"] = "duty.Q"
    refusal = bind_revision_flowsheet(document)
    assert isinstance(refusal, Unbound)
    assert (refusal.kind, refusal.detail) == (
        "unsupported",
        "specification_kind_unsupported(SPEC-flash-duty)",
    )
    assert refusal.hint == (
        "Target path duty.Q takes kind heat_rate (SI unit W); this specification has kind power."
    )
    # DIM-01 reports the code, with its hint.
    report = validate(document)
    (dim,) = [check for check in report.checks if check.id == "DIM-01"]
    assert dim.result == "FAIL"
    assert dim.message == f"specification_kind_unsupported(SPEC-flash-duty). {refusal.hint}"


def test_g_r6_5_ii_the_pin_removed_names_kind_and_path_and_the_hint_solves(
    tmp_path: Path,
) -> None:
    document = _t05_2()
    document["specifications"] = [
        e for e in document["specifications"] if e["id"] != "SPEC-flash-duty"
    ]
    refusal = bind_revision_flowsheet(copy.deepcopy(document))
    assert isinstance(refusal, Unbound)
    assert (refusal.kind, refusal.detail) == ("incomplete", "specification_missing(U-FLASH.Q)")
    assert refusal.hint == (
        "Pin it with one fixed specification: kind heat_rate, unit W, target "
        "{object_type: instance, object_id: U-FLASH, path: duty.Q}"
    )
    # The hint followed, with the agent's value.
    followed = _t05_2()
    entry = _duty(followed)
    entry.update(kind="heat_rate", unit="W")
    entry["target"].update(object_type="instance", object_id="U-FLASH", path="duty.Q")
    assert validate(followed).status == "READY_FOR_SIMULATION"
    route = select_route(followed)
    assert isinstance(route, Route) and route.solve_path == "revision_eo"
    policy = resolve_policy(DEFAULT_POLICY_ID, route.solve_path)
    assert policy is not None
    manifest = run_revision_session(
        route,
        followed,
        tmp_path / "bundle",
        run_id="g-r6-5-ii",
        policy=policy,
        check_policy=CheckPolicy(),
        policy_requested=DEFAULT_POLICY_ID,
    )
    assert (manifest.outcome, manifest.verification_status) == ("CONVERGED", "VERIFIED")


# -- the remaining codes of the ruling's table ---------------------------------------------------


def _nominal() -> Document:
    return CORPUS["SYN-001-T06-NET03"]()


def test_unit_unsupported_lists_the_kinds_units() -> None:
    document = _nominal()
    document["specifications"][3]["unit"] = "degR"
    entry = document["specifications"][3]
    with pytest.raises(RevisionError) as raised:
        convert_specification(entry, 300.0)
    assert raised.value.code == f"specification_unit_unsupported({entry['id']})"
    assert raised.value.hint == "Kind temperature takes the units K, degC, degF."


def test_kind_unsupported_names_the_mass_basis_of_a_flow() -> None:
    entry = copy.deepcopy(_nominal()["specifications"][0])
    assert entry["target"]["path"] == "state.n"
    entry["kind"] = "power"
    with pytest.raises(RevisionError) as raised:
        convert_specification(entry, 1.0)
    assert raised.value.hint == (
        "Target path state.n takes kind molar_flow (SI unit mol/s), or kind mass_flow (one "
        "component, mass basis); this specification has kind power."
    )


def test_a_connection_target_and_a_component_outside_the_set() -> None:
    document = _nominal()
    document["specifications"][0]["target"]["path"] = "state.x"
    refusal = bind_revision_flowsheet(document)
    assert isinstance(refusal, Unbound)
    assert refusal.hint == (
        "A connection target takes path state.T (temperature, K), state.P (pressure, Pa) or "
        "state.n with a component of A, B, C (molar_flow, mol/s)."
    )
    document = _nominal()
    document["specifications"][0]["target"]["component"] = "D"
    refusal = bind_revision_flowsheet(document)
    assert isinstance(refusal, Unbound)
    assert refusal.hint == "Component D is not in the component set A, B, C."


def test_unconsumed_names_what_the_model_reads() -> None:
    refusal = bind_revision_flowsheet(CORPUS["SYN-001-conflicting-heater-spec"]())
    assert isinstance(refusal, Unbound)
    assert refusal.detail == "specification_unconsumed(SPEC-heater-duty)"
    assert refusal.hint is not None
    assert refusal.hint.startswith("heater (syn001.tp_heater) does not read column heater.Q; ")
    assert "outlet_temperature: kind temperature, unit K" in refusal.hint


def test_a_missing_choice_names_each_option() -> None:
    document = CORPUS["SYN-001-T06-NET06"]()
    document["specifications"] = [
        e for e in document["specifications"] if e["target"]["object_id"] != "S5"
    ]
    refusal = bind_revision_flowsheet(document)
    assert isinstance(refusal, Unbound)
    assert refusal.detail == "specification_missing(U-HX.specification)"
    assert refusal.hint is not None
    assert refusal.hint.startswith("Pin exactly one of: hot_outlet_temperature: kind temperature")
    assert "cold_outlet_temperature: kind temperature" in refusal.hint
    assert (
        "duty: kind heat_rate, unit W, target "
        "{object_type: instance, object_id: U-HX, path: duty.Q}" in refusal.hint
    )


def test_a_refused_phase_names_the_accepted_one() -> None:
    document = c1_document("T02-3", "rev-000003")
    refusal = bind_revision_flowsheet(document)
    assert isinstance(refusal, Unbound)
    assert refusal.detail == "port_phase_unsupported(U-HEAT.outlet)"
    assert refusal.hint == (
        "Port outlet of syn001.tp_heater takes phase vapor_liquid; the connection declares liquid."
    )


def test_every_hint_is_bounded() -> None:
    long = Unbound("unsupported", "x(y)", hint="z" * 2000)
    assert long.hint is not None and len(long.hint) == HINT_LIMIT
    assert long == Unbound("unsupported", "x(y)")
