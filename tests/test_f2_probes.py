"""F2-WO5: E-F2-4 on the probe flowsheets (ADR 0062; foundation rulings Q1.A5, Q6.A1 to A5, O-9).

- **Kinds.** The three probe kinds (`tests/f2/probes.py`) are schema-valid D5 payloads, and the
  context and layout tests register the same facts under the same ids (F2 decision WO5-1).
- **Q1.A5.** feed -> mixer <- dormant feed; dormant branch -> heater -> splitter: every dormant
  stream exactly `+0.0` (amounts, attributes, ṁ, Ḣ), derived T null with reason `zero_flow`, `ĥ`
  bitwise its label, the label rows in the zero-flow form; the flowing outlet's `ĥ` as without the
  dormant feed; a stream whose only amount is 5e-324 flowing.
- **Q6.A1** **[gen]** conservation <= 1e-14 relative per carried amount and attribute through
  mixers of 1 to 8 inlets and splitters; **Q6.A2** the partition alone admitted, a second one on
  its component refused, its parent sum bitwise reproducible; **Q6.A3** attributes `+0.0` with a
  dormant parent, defined intensives with one zero class; **Q6.A4** a grid mismatch refused, the
  same grid admitted; **Q6.A5** **[gen]** monodisperse feeds, their mixtures and splits admitted,
  one failing the strict test, none above τ_mono/100, the three invalid trials stored unclipped.
- **O-9.** The worst moment deficit, a recycle of loop gain 100 included, at least 10x below
  τ_mono.
- **Q7.A2** ṁ bitwise and **E-F2-6** the layout read bitwise on every probe state.
"""

from __future__ import annotations

import copy
import dataclasses
import math
import random
import struct
from collections.abc import Iterator
from typing import Any

import pytest
import yaml
from f2.probes import (
    COMPONENTS,
    DEFINITION,
    FACTS,
    KINDS,
    PAYLOADS,
    TAU_MONO,
    Flowsheet,
    Key,
    ProbeUnresolvedError,
    admissible,
    conservation,
    deficit,
    definition,
)
from test_f2_revision_v2 import V2, _independent_masses, context
from test_f2_vid_layout import KINDS as LAYOUT_KINDS
from test_f2_vid_layout import _bits, _expected, _expected_state

from openflowsheet.material.definitions import definition_sha256, instance_problems
from openflowsheet.material.layout import ConnectionInput, MaterialLayout, MaterialState
from openflowsheet.registry.descriptor import schema_problem
from openflowsheet.registry.tokens import Coded
from openflowsheet.revision_v2 import parse, validate

PLUS_ZERO = struct.pack("<d", 0.0)
H1, P1 = 2.5e5, 2.0e5
DPS = (1.0, 2.0, 3.0, 7.0, 100.0, 1e4, 1e6)
AMOUNTS = (0.1, 1.0 / 3.0)


def _flowing() -> dict[Key, float]:
    """A flowing feed's slots: A, B, P with λ0 and λ2 of a DP-100 chain, C in four size classes
    (one empty) with particle counts."""
    values: dict[Key, float] = {
        ("liq", "n", ("A",)): 2.0,
        ("liq", "n", ("B",)): 0.5,
        ("liq", "n", ("P",)): 3.0,
        ("liq", "a", ("probe.moments", "P", 1)): 0.03,
        ("liq", "a", ("probe.moments", "P", 2)): 300.0,
    }
    for k, (amount, count) in enumerate(((0.1, 1e6), (0.2, 5e5), (0.0, 0.0), (0.05, 1e4)), 1):
        values["cryst", "n", ("C", k)] = amount
        values["cryst", "a", ("probe.classes", k)] = count
    return values


def _zero_flow_sheet(*, dormant_feed: bool = True) -> Flowsheet:
    """Q1.A5's probe: feed -> mixer <- dormant feed; dormant branch -> heater -> splitter; a
    dormant source -> heater -> splitter; two dormant feeds mixed; the 5e-324 stream mixed."""
    sheet = Flowsheet()
    sheet.feed("F1", _flowing(), H1, P1)
    dormant = {key: -0.0 for key in _flowing()}
    if dormant_feed:
        sheet.feed("F2", dormant, 9.9e5, P1)
        sheet.mix("M1", ["F1", "F2"])
    else:
        sheet.mix("M1", ["F1"])
    sheet.split("M1", ["D", "K"], [0.0])
    sheet.heat("DH", "D", 0.0)
    sheet.split("DH", ["DX", "DY"], [0.3])
    sheet.feed("F3", {}, -4.0e5, P1)
    sheet.heat("F3H", "F3", 0.0)
    sheet.split("F3H", ["G1", "G2"], [0.6])
    sheet.feed("F4", {("liq", "n", ("A",)): 5e-324}, H1, P1)
    sheet.mix("M3", ["F4", "F1"])
    if dormant_feed:
        sheet.mix("M2", ["F2", "F3"])
    return sheet


#: Each dormant stream of the Q1.A5 sheet and the stream whose `ĥ` is its label.
LABELS = {"F2": None, "D": "M1", "DH": "D", "DX": "DH", "DY": "DH", "F3": None, "F3H": "F3"}
LABELS |= {"G1": "F3H", "G2": "F3H", "M2": "F2"}


def _slots(state: MaterialState) -> list[float]:
    return [v for sub in state.substreams for v in (*sub.carried, *sub.attributes)]


# ------------------------------------------------------------------------------------ the kinds


def test_probe_kinds_are_d5_payloads_registered_alike_everywhere() -> None:
    for kind, payload in PAYLOADS.items():
        assert schema_problem(payload, "/$defs/payload_attribute_kind") is None, kind
    found = yaml.safe_load((V2 / "context.yaml").read_text(encoding="utf-8"))["attribute_kinds"]
    for kind, facts in KINDS.items():
        assert dataclasses.asdict(facts) == found[kind] and LAYOUT_KINDS[kind] == facts
    assert (KINDS["probe.moments"].scope, KINDS["probe.classes"].scope) == (
        "component",
        "substream",
    )
    assert [k for k, v in KINDS.items() if v.partition] == ["probe.partition"]
    assert instance_problems(DEFINITION) == []


# -------------------------------------------------------------------------------- Q1.A5, Q6.A3


def test_q1_a5_dormant_streams_are_exact_zero_with_their_labels() -> None:
    sheet = _zero_flow_sheet()
    assert {n for n, s in sheet.streams.items() if s.is_dormant} == set(LABELS)
    for name, source in LABELS.items():
        state = sheet.streams[name]
        assert {struct.pack("<d", v) for v in _slots(state)} == {PLUS_ZERO}, name
        assert struct.pack("<d", sheet.mass_flow(state)) == PLUS_ZERO
        assert struct.pack("<d", sheet.enthalpy_flow(state)) == PLUS_ZERO
        label = 0.0 if source is None else sheet.streams[source].thermal
        assert struct.pack("<d", state.thermal) == struct.pack("<d", label), name
        derived = sheet.derived(state)
        assert derived["T"] == (None, "zero_flow")
        assert set(derived.values()) == {(None, "zero_flow")}, name
    # The rows that lose rank in ĥ at a dormant outlet are in the zero-flow form; the splitter's
    # ĥ row never loses rank and copies its inlet's.
    assert {sheet.forms[n] for n in ("F2", "F3", "DH", "F3H", "M2")} == {"zero_flow"}
    assert {sheet.forms[n] for n in ("D", "DX", "DY", "G1", "G2", "K")} == {"copy"}
    assert sheet.forms["M1"] == sheet.forms["M3"] == "balance"
    assert (
        sheet.streams["F3"].thermal == 0.0
        and sheet.streams["DH"].thermal == sheet.streams["M1"].thermal
    )


def test_q1_a5_the_flowing_outlet_is_as_without_the_dormant_branch() -> None:
    with_branch = _zero_flow_sheet().streams["M1"]
    without = _zero_flow_sheet(dormant_feed=False).streams["M1"]
    assert not with_branch.is_dormant
    assert abs(with_branch.thermal - without.thermal) <= 1e-14 * abs(without.thermal)
    assert _bits(with_branch) == _bits(without)  # measured: bitwise


def test_q1_a5_a_stream_whose_only_amount_is_5e_324_flows() -> None:
    sheet = _zero_flow_sheet()
    tiny = sheet.streams["F4"]
    assert not tiny.is_dormant and sheet.forms["F4"] == "specified"
    assert sheet.mass_flow(tiny) == 0.0  # 0.018015 x 5e-324 underflows: dormancy is on amounts
    assert "T" not in sheet.derived(tiny) and sheet.derived(tiny)["x[A]"] == (1.0, None)
    assert conservation([sheet.streams["F4"], sheet.streams["F1"]], [sheet.streams["M3"]]) == 0.0
    # Alone in a mixer its energy row has rank 0 in ĥ without being a zero-flow form: unresolved.
    with pytest.raises(ProbeUnresolvedError):
        sheet.mix("M4", ["F4", "F2"])
    assert sheet.streams.get("M4") is None


def test_q6_a3_attributes_stay_zero_with_a_dormant_parent() -> None:
    sheet = Flowsheet()
    liquid_only = {k: v for k, v in _flowing().items() if k[0] == "liq"}
    sheet.feed("L1", liquid_only, H1, P1)
    sheet.feed("L2", {**liquid_only, ("liq", "n", ("A",)): 7.0}, 3.0e5, P1)
    sheet.mix("LM", ["L1", "L2"])
    sheet.split("LM", ["LA", "LB"], [0.25])
    sheet.heat("LH", "LA", 1.0e3)
    for name in ("L1", "L2", "LM", "LA", "LB", "LH"):
        state = sheet.streams[name]
        cryst = state.substreams[1]
        assert cryst.is_dormant and not state.is_dormant
        assert {struct.pack("<d", v) for v in (*cryst.carried, *cryst.attributes)} == {PLUS_ZERO}
        derived = sheet.derived(state)
        assert derived["mean_class[cryst]"] == (None, "zero_flow")
        assert derived["class_fraction[C][1]"] == (None, "zero_flow")
        assert derived["segments_per_chain[P]"][1] is None
    # A dormant feed with a non-zero attribute is an invalid state.
    with pytest.raises(ValueError, match="attribute_on_zero_parent"):
        sheet.feed("bad", {("cryst", "a", ("probe.classes", 1)): 1.0}, H1, P1)
    # Non-vanishing control: a flowing parent with one zero class has defined intensives.
    flowing = _zero_flow_sheet().streams["M1"]
    derived = Flowsheet().derived(flowing)
    assert derived["class_fraction[C][3]"] == (0.0, None)
    assert all(reason is None for _, reason in derived.values())


# ------------------------------------------------------------------------------- Q6.A1, Q6.A5


def _random_feed(sheet: Flowsheet, name: str, rng: random.Random) -> None:
    values = {
        key: (0.0 if rng.random() < 0.15 else 10.0 ** rng.uniform(-6.0, 6.0))
        for sub in sheet.keys()
        for part in sub
        for key in part
    }
    sheet.feed(name, values, rng.uniform(-1e6, 1e6), rng.uniform(1e4, 1e7))


def conservation_worst(seed: int = 6401, trials: int = 400) -> tuple[float, int]:
    """Q6.A1 [gen]: the worst relative residual over random mixers (1 to 8 inlets), splitters
    (2 to 4 outlets) and the remix of each split, and the number of units checked."""
    rng = random.Random(seed)
    worst, units = 0.0, 0
    for t in range(trials):
        sheet = Flowsheet()
        inlets = [f"F{t}_{k}" for k in range(rng.randint(1, 8))]
        for name in inlets:
            _random_feed(sheet, name, rng)
        sheet.mix("M", inlets)
        outs = [f"S{j}" for j in range(rng.randint(2, 4))]
        sheet.split("M", outs, [rng.uniform(0.0, 1.0 / len(outs)) for _ in outs[1:]])
        sheet.mix("R", outs)
        streams = sheet.streams
        worst = max(
            worst,
            conservation([streams[i] for i in inlets], [streams["M"]]),
            conservation([streams["M"]], [streams[o] for o in outs]),
            conservation([streams[o] for o in outs], [streams["R"]]),
        )
        units += 3
    return worst, units


def test_q6_a1_conservation_through_mixers_and_splitters() -> None:
    worst, units = conservation_worst()
    assert units == 1200
    assert worst <= 1e-14
    assert worst > 0.0  # the measurement sees rounding (a vacuous zero would hide a broken metric)


def _monodisperse(sheet: Flowsheet, name: str, dp: float, amount: float) -> None:
    segments = dp * amount
    values: dict[Key, float] = {
        ("liq", "n", ("A",)): 1.0,
        ("liq", "n", ("P",)): segments,
        ("liq", "a", ("probe.moments", "P", 1)): amount,
        ("liq", "a", ("probe.moments", "P", 2)): dp * segments,
    }
    sheet.feed(name, values, H1, P1)


def _amount(rng: random.Random) -> float:
    return rng.choice([*AMOUNTS, rng.uniform(1e-3, 1e3)])


def moment_states(seed: int = 6505, trials: int = 300) -> Iterator[MaterialState]:
    """Q6.A5 [gen]: every monodisperse feed of DPS x AMOUNTS, and per trial up to 8 monodisperse
    feeds of one DP or of several, their mixture, and its split into 2 to 4 outlets."""
    rng = random.Random(seed)
    sheet = Flowsheet()
    for i, dp in enumerate(DPS):
        for j, amount in enumerate(AMOUNTS):
            _monodisperse(sheet, f"F{i}_{j}", dp, amount)
    yield from sheet.streams.values()
    for t in range(trials):
        sheet = Flowsheet()
        one = rng.choice(DPS)
        inlets = [f"F{k}" for k in range(rng.randint(1, 8))]
        for name in inlets:
            dp = one if t % 2 == 0 else rng.choice(DPS)
            _monodisperse(sheet, name, dp, _amount(rng))
        sheet.mix("M", inlets)
        outs = [f"S{j}" for j in range(rng.randint(2, 4))]
        sheet.split("M", outs, [rng.uniform(0.0, 1.0 / len(outs)) for _ in outs[1:]])
        yield from (sheet.streams[n] for n in ("M", *outs))


def test_q6_a5_monodisperse_mixtures_and_splits_are_admitted() -> None:
    probe = Flowsheet()
    deficits = []
    for state in moment_states():
        moments = probe.moments(state)
        assert admissible(*moments)
        found = deficit(*moments)
        assert found is not None
        deficits.append(found)
    assert len(deficits) > 1000
    assert sum(d > 0.0 for d in deficits) >= 1  # the strict test fails somewhere
    assert max(deficits) <= TAU_MONO / 100


def test_q6_a5_invalid_trials_are_refused_and_stored_unclipped() -> None:
    lambda0 = 0.1
    lambda1 = 100.0 * lambda0
    trials = {
        "cauchy_schwarz": (lambda0, lambda1, lambda1 * lambda1 * (1.0 - 1e-9) / lambda0),
        "one_segment_1e-9": (lambda1 * (1.0 + 1e-9), lambda1, 1e5),
        "one_segment_1e-3": (lambda1 * (1.0 + 1e-3), lambda1, 1e5),
    }
    for name, moments in trials.items():
        assert not admissible(*moments), name
        sheet = Flowsheet()
        values = {
            ("liq", "n", ("P",)): moments[1],
            ("liq", "a", ("probe.moments", "P", 1)): moments[0],
            ("liq", "a", ("probe.moments", "P", 2)): moments[2],
        }
        sheet.feed("T", values, H1, P1)
        sheet.feed("Z", {}, H1, P1)
        sheet.mix("M", ["T", "Z"])
        for state in (sheet.streams["T"], sheet.streams["M"]):
            assert [struct.pack("<d", v) for v in sheet.moments(state)] == [
                struct.pack("<d", v) for v in moments
            ]
        assert placed_reads_back(sheet)


# ------------------------------------------------------------------------------------- O-9


def recycle_worst(gain: float = 100.0, cap: int = 20_000) -> tuple[float, int]:
    """O-9: feed -> mixer <- recycle; mixer -> splitter (recycle fraction 1 - 1/gain, product by
    balance), iterated from a dormant tear to its fixed point per monodisperse feed of
    DPS x AMOUNTS. The worst deficit over every iterate's streams, and the most iterations."""
    probe = Flowsheet()
    worst, most = -math.inf, 0
    for dp in DPS:
        for amount in AMOUNTS:
            sheet = Flowsheet()
            _monodisperse(sheet, "F", dp, amount)
            sheet.feed("R", {}, H1, P1)
            steps = 0
            while steps < cap:
                steps += 1
                previous = _bits(sheet.streams["R"])
                sheet.mix("M", ["F", "R"])
                sheet.forget("R")
                sheet.split("M", ["R", "W"], [1.0 - 1.0 / gain])
                for name in ("M", "R", "W"):
                    found = deficit(*probe.moments(sheet.streams[name]))
                    assert found is not None
                    worst = max(worst, found)
                if _bits(sheet.streams["R"]) == previous:
                    break
                sheet.forget("M", "W")
            assert _bits(sheet.streams["R"]) == previous, f"DP {dp}, {amount}: no fixed point"
            most = max(most, steps)
    return worst, most


def test_o9_worst_moment_deficit_with_a_recycle_of_gain_100() -> None:
    worst, steps = recycle_worst()
    assert steps > 1000  # the loop really circulates (gain 100)
    assert worst * 10 <= TAU_MONO, f"O-9: margin {TAU_MONO / worst:.1f}x is below 10x"


# -------------------------------------------------------------------------------- Q6.A2, Q6.A4


def _revision(definitions: dict[str, Any], s2_definition: str = "probe") -> dict[str, Any]:
    """A v2 revision: two probe feeds into a `std.mixer` (one definition on all ports), a sink."""
    document = yaml.safe_load(
        (V2 / "process_revision" / "valid" / "crystallizer.yaml").read_text(encoding="utf-8")
    )
    document["component_set"]["components"] = [
        {"id": c, "record": f"{i + 1}" * 64} for i, c in enumerate(COMPONENTS)
    ]
    document["materials"]["phase_order_keys"] = ["A"]
    document["materials"]["definitions"] = [{"id": d, **body} for d, body in definitions.items()]
    document["reaction_sets"], document["specifications"], document["sections"] = [], [], {}
    keep = {"feed", "feed2", "mix", "sink"}
    document["instances"] = [i for i in document["instances"] if i["id"] in keep]

    def material(cid: str, source: str, target: str, port: str, definition: str) -> dict[str, Any]:
        return {
            "id": cid,
            "kind": "material",
            "from": {"instance": source, "port": "out"},
            "to": {"instance": target, "port": port},
            "definition": definition,
        }

    document["connections"] = [
        material("S1", "feed", "mix", "in1", "probe"),
        material("S2", "feed2", "mix", "in2", s2_definition),
        material("S3", "mix", "sink", "in", "probe"),
    ]
    return document


def _validate(document: dict[str, Any]) -> tuple[tuple[Coded, ...], tuple[Coded, ...]]:
    probe_context = dataclasses.replace(context(), components=COMPONENTS, attribute_kinds=KINDS)
    return validate(parse(copy.deepcopy(document)), probe_context)


def test_q6_a4_a_grid_mismatch_is_refused_and_the_same_grid_admitted() -> None:
    other = definition((0.0, 1e-4, 2e-4, 6e-4, 1e-3))
    # The same grid: every port on the one definition (F2 decision WO5-4 on a second id).
    assert _validate(_revision({"probe": DEFINITION})) == ((), ())
    refused, _ = _validate(_revision({"probe": DEFINITION, "probe2": other}, "probe2"))
    assert refused == (Coded("attribute_grid_mismatch", {"connection": "S2", "port": "mix.in2"}),)
    # The grid is in the definition's SHA, so a probe mixer refuses the inlet too.
    shas = [definition_sha256(d, "1.0.0", "0" * 64) for d in (DEFINITION, other)]
    assert shas[0] != shas[1]
    sheet = Flowsheet(sha=shas[0])
    sheet.feed("F1", _flowing(), H1, P1)
    foreign = Flowsheet(instance=other, sha=shas[1])
    sheet.streams["F2"] = foreign.feed("F2", _flowing(), H1, P1)
    with pytest.raises(ValueError, match="another definition"):
        sheet.mix("M", ["F1", "F2"])


def test_q6_a2_the_partition_alone_is_admitted_and_sums_to_its_parent() -> None:
    assert _validate(_revision({"probe": DEFINITION})) == ((), ())
    twice = copy.deepcopy(DEFINITION)
    twice["substreams"][1]["attributes"].append(
        copy.deepcopy(twice["substreams"][1]["attributes"][0])
    )
    refused, _ = _validate(_revision({"probe": twice}))
    params = {"definition": "probe", "substream": "cryst", "kind": "probe.partition"}
    assert refused == (Coded("attribute_redundant", params),)
    # The parent is never carried beside its partition: C has class slots only.
    sheet = _zero_flow_sheet()
    carried = [key for key in sheet.keys()[1][0]]
    assert carried == [("cryst", "n", ("C", k)) for k in (1, 2, 3, 4)]
    for state in sheet.streams.values():
        classes = sheet.classes(state, "cryst", "n", ("C",))
        expected = 0.0
        for amount in classes:
            expected += amount
        assert struct.pack("<d", sheet.parent(state)) == struct.pack("<d", expected)
        assert struct.pack("<d", sheet.parent(state)) == struct.pack(
            "<d", Flowsheet().parent(state)
        )


# ------------------------------------------------------------------------- Q7.A2 and E-F2-6


def placed_reads_back(sheet: Flowsheet, seed: int = 6206) -> int:
    """Every stream of `sheet` written into a state vector by the independently built ids
    (shuffled), then: the layout reads each state bitwise as the probe made it and as built
    independently from the definition (E-F2-6), and ṁ from the layout's masses equals the
    independent fixed-order sum bitwise (Q7.A2). Returns the number of states checked."""
    rng = random.Random(seed)
    given = [ConnectionInput(n, "probe", sheet.instance, sheet.sha) for n in sheet.streams]
    rows = {g.connection: _expected(g.connection, g.instance, FACTS) for g in given}
    value: dict[str, float] = {}
    for name, state in sheet.streams.items():
        by_substream: dict[str | None, list[float]] = {}
        for sub in state.substreams:
            by_substream[sub.substream] = [*sub.carried, *sub.attributes]
        for vid, sid, role in rows[name]:
            if role == "thermal":
                value[vid] = state.thermal
            elif role == "P":
                value[vid] = state.pressure
            else:
                value[vid] = by_substream[sid].pop(0)
    ids = list(value)
    rng.shuffle(ids)
    x = [value[vid] for vid in ids]
    layout = MaterialLayout.build(given, FACTS, ids)
    masses = _independent_masses(sheet.instance, FACTS)
    for item in given:
        state = sheet.streams[item.connection]
        read = layout.state(x, item.connection)
        built = _expected_state(
            item.connection, item.instance, item.definition_sha256, rows[item.connection], value
        )
        assert read == state == built and _bits(read) == _bits(state) == _bits(built)
        placed = layout.connection(item.connection)
        found = 0.0
        for sub in placed.substreams:
            for position, mass in zip(sub.carried, sub.molar_masses, strict=True):
                found += mass * x[placed.slots[position].variable_index]
        expected = 0.0
        carried = [vid for vid, _, role in rows[item.connection] if role == "carried"]
        for vid, mass in zip(carried, masses, strict=True):
            expected += mass * value[vid]
        assert struct.pack("<d", found) == struct.pack("<d", expected)
        assert struct.pack("<d", found) == struct.pack("<d", sheet.mass_flow(state))
    return len(given)


def test_q7_a2_and_e_f2_6_on_the_probe_states() -> None:
    checked = placed_reads_back(_zero_flow_sheet())
    rng = random.Random(6207)
    for t in range(40):
        sheet = Flowsheet()
        inlets = [f"F{k}" for k in range(rng.randint(1, 8))]
        for name in inlets:
            _random_feed(sheet, name, rng)
        sheet.mix("M", inlets)
        sheet.split("M", ["A", "B", "C"], [0.0, rng.uniform(0.0, 0.5)])
        sheet.heat("H", "B", rng.uniform(-1e3, 1e3))
        checked += placed_reads_back(sheet, seed=t)
    assert checked > 300


def test_the_probe_masses_are_the_independent_ones() -> None:
    sheet = Flowsheet()
    layout_masses = [m for masses in sheet.masses for m in masses]
    assert layout_masses == _independent_masses(DEFINITION, FACTS)
