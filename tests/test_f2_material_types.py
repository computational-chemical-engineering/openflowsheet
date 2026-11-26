"""F2-WO1: the provider-level types of ADR 0062 D2 and the phase ids of D6.

E-F2-1 (Q1.A8): every `StreamState` built while the corpus runs (F0's `run_corpus`: RC step 4's
enumeration and the basis cases) goes through `EvaluationState` and back bitwise. The phase-id part
of E-F2-5: on 10^4 generated phases and phase sets with adversarial ids, the test-only parser
(`tests/f2/phase_id_parse.py`) inverts the rendering, no two structures render alike, and no
rendering equals a legacy phase or signature id unless it is that very phase. D2's exact-cache keys:
a `StreamState` key is byte-unchanged (F0 M6 pins the digests), an `EvaluationState` keys by n, T, P
and its attributes, a `PhaseId` by its rendering.
"""

from __future__ import annotations

import dataclasses
import json
import random
import struct
import sys
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from f2.phase_id_parse import parse_phase_id, parse_phase_set

from openflowsheet.material import phase_id as phase_ids
from openflowsheet.material import state as material_state
from openflowsheet.material.phase_id import FAMILIES, PhaseId, phase_set, render_phase_set
from openflowsheet.registry.tokens import ID_PATTERN
from openflowsheet.thermo import (
    EvaluationState,
    StreamState,
)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import corpus_identity as gate  # noqa: E402


def _bits(value: float) -> bytes:
    return struct.pack("<d", value)


def _stream_bits(s: StreamState) -> tuple[tuple[bytes, ...], bytes, bytes]:
    return tuple(_bits(x) for x in s.n), _bits(s.temperature), _bits(s.pressure)


# -- D2: EvaluationState ------------------------------------------------------------------------


@pytest.fixture(scope="module")
def corpus_streams(
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[int, list[StreamState]]:
    """Every `StreamState` constructed while each corpus run is solved, as F0 solves it."""
    built: list[StreamState] = []
    original: Callable[..., None] = StreamState.__init__

    def recording(self: StreamState, *arguments: Any, **keywords: Any) -> None:
        original(self, *arguments, **keywords)
        built.append(self)

    selection = gate.run_corpus()
    scratch = tmp_path_factory.mktemp("e-f2-1")
    with pytest.MonkeyPatch.context() as patch, gate.pinned_threads():
        patch.setattr(StreamState, "__init__", recording)
        for index, (run_set, name) in enumerate(selection):
            gate.solve(run_set, name, scratch / f"{index:03d}")
    return len(selection), built


def test_e_f2_1_every_corpus_stream_round_trips_bitwise(
    corpus_streams: tuple[int, list[StreamState]],
) -> None:
    runs, streams = corpus_streams
    distinct = {_stream_bits(s) for s in streams}
    for s in streams:
        evaluation = EvaluationState.from_stream_state(s)
        assert evaluation.n is s.n and evaluation.attributes == ()
        back = evaluation.to_stream_state()
        assert type(back) is StreamState
        assert back.n is s.n
        assert _stream_bits(back) == _stream_bits(s)
    assert runs == 61
    assert len(streams) > 0
    print(f"E-F2-1: {runs} corpus runs, {len(streams)} streams built, {len(distinct)} distinct")


def test_e_f2_1_signed_zero_and_subnormals_survive_the_round_trip() -> None:
    """The bits, not the values: -0.0 stays -0.0 and 5e-324 stays itself."""
    s = StreamState((-0.0, 5e-324, 1.0), 300.0, -0.0)
    back = EvaluationState.from_stream_state(s).to_stream_state()
    assert _stream_bits(back) == _stream_bits(s)


def test_evaluation_state_attributes_are_sorted_by_key_bytes_and_refuse_a_stream_state() -> None:
    state = EvaluationState((1.0,), 300.0, 1e5, (("probe.classes[A]", (1.0,)), ("probe.m", (2.0,))))
    with pytest.raises(ValueError, match="no StreamState"):
        state.to_stream_state()
    for unsorted in ((("b", (1.0,)), ("a", (1.0,))), (("a", (1.0,)), ("a", (2.0,)))):
        with pytest.raises(ValueError, match="strictly increasing"):
            EvaluationState((1.0,), 300.0, 1e5, unsorted)
    # UTF-8 bytes, not code points after case folding: "Z" (0x5a) sorts before "a" (0x61).
    EvaluationState((1.0,), 300.0, 1e5, (("Z", ()), ("a", ())))


def test_evaluation_state_is_frozen_and_slotted() -> None:
    state = EvaluationState((1.0,), 300.0, 1e5)
    with pytest.raises(dataclasses.FrozenInstanceError):
        state.temperature = 301.0  # type: ignore[misc]
    assert not hasattr(state, "__dict__")
    assert [f.name for f in dataclasses.fields(EvaluationState)] == [
        "n",
        "temperature",
        "pressure",
        "attributes",
    ]


def test_the_types_are_re_exported_by_thermo() -> None:
    import openflowsheet.thermo as thermo

    assert thermo.StreamState is material_state.StreamState
    assert thermo.EvaluationState is material_state.EvaluationState
    assert thermo.PhaseId is phase_ids.PhaseId
    assert thermo.PhaseSet is phase_ids.PhaseSet


# -- D6: phase ids ------------------------------------------------------------------------------


ADR_EXAMPLES = {
    "VAPOR": PhaseId("VAPOR", None, 1),
    "LIQUID.2": PhaseId("LIQUID", None, 2),
    "FLUID(water)": PhaseId("FLUID", "water", 1),
    "LIQUID(water).2": PhaseId("LIQUID", "water", 2),
    "SOLID(CaCO3,calcite)": PhaseId("SOLID", "CaCO3,calcite", 1),
    "SOLID(model=langmuir-co2)": PhaseId("SOLID", "model=langmuir-co2", 1),
}


@pytest.mark.parametrize(("text", "phase"), ADR_EXAMPLES.items())
def test_d6_the_adr_examples_render_and_parse(text: str, phase: PhaseId) -> None:
    assert phase.render() == text
    assert parse_phase_id(text) == phase


@pytest.mark.parametrize(
    "text",
    [
        "LIQUID.1",
        "LIQUID.02",
        "LIQUID.",
        "LIQUID()",
        "LIQUID(a",
        "TWO_PHASE",
        "ZERO_FLOW",
        "",
        "GAS",
    ]
    + ["liquid", "SOLID(a,b,c)", "SOLID(a=b)", "SOLID(model=1x)", "SOLID(a,)", "VAPOR+LIQUID"],
)
def test_d6_text_no_phase_renders_as_does_not_parse(text: str) -> None:
    with pytest.raises(ValueError):
        parse_phase_id(text)


@pytest.mark.parametrize(
    ("family", "qualifier", "ordinal"),
    [
        ("GAS", None, 1),
        ("example.FAMILY", None, 1),
        ("LIQUID", "", 1),
        ("LIQUID", "a b", 1),
        ("LIQUID", "a(b)", 1),
        ("LIQUID", "a+b", 1),
        ("LIQUID", "a~b", 1),
        ("LIQUID", None, 0),
        ("LIQUID", None, True),
        ("LIQUID", None, 2.0),
        ("SOLID", "model=", 1),
    ],
)
def test_d6_construction_refuses_what_the_grammar_excludes(
    family: str, qualifier: str | None, ordinal: int
) -> None:
    with pytest.raises(ValueError):
        PhaseId(family, qualifier, ordinal)


def test_d6_the_alphabets_are_the_registered_ones() -> None:
    """The component alphabet is the revision schema's; the model id is F1's (ADR 0060)."""
    revision = (ROOT / "schemas" / "process-revision.schema.json").read_text(encoding="utf-8")
    patterns = {found["pattern"] for found in _patterns(json.loads(revision))}
    assert f"^{phase_ids.COMPONENT_ID.pattern}$" in patterns
    assert f"^{phase_ids.MODEL_ID.pattern}$" == ID_PATTERN.pattern


def _patterns(node: object) -> Iterator[dict[str, Any]]:
    if isinstance(node, dict):
        if isinstance(node.get("pattern"), str):
            yield node
        for value in node.values():
            yield from _patterns(value)
    elif isinstance(node, list):
        for value in node:
            yield from _patterns(value)


def test_d6_phase_sets_render_in_canonical_order() -> None:
    phases = [
        PhaseId("SOLID", "b", 1),
        PhaseId("LIQUID", None, 2),
        PhaseId("SOLID", "a", 1),
        PhaseId("VAPOR", None, 1),
        PhaseId("LIQUID", None, 1),
        PhaseId("SOLID", None, 1),
        PhaseId("FLUID", "water", 1),
    ]
    ordered = phase_set(phases)
    text = render_phase_set(ordered)
    assert text == "VAPOR+LIQUID+LIQUID.2+FLUID(water)+SOLID+SOLID(a)+SOLID(b)"
    assert parse_phase_set(text) == ordered
    with pytest.raises(ValueError):
        render_phase_set(tuple(phases))
    with pytest.raises(ValueError):
        phase_set([PhaseId("VAPOR", None, 1)] * 2)
    with pytest.raises(ValueError):
        phase_set([])
    with pytest.raises(ValueError):
        parse_phase_set("LIQUID+VAPOR")


# Adversarial ids (E-F2-5): a dotted id ending in a digit, a field name, a family name, a colon,
# digits, `model`, and ids that are both a component id and a model id.
ADVERSARIAL_COMPONENTS = ["a.2", "n", "LIQUID", "x:y", "123", "0", "model", "langmuir-co2", "a.b.c"]
ADVERSARIAL_COMPONENTS += ["VAPOR.2", "LIQUID.2", "SOLID", "co2", "T", "a-", "a_"]
ADVERSARIAL_FORMS = ["calcite", "I", "II", "2", "alpha-1", "model", "a_b"]
ADVERSARIAL_MODELS = ["langmuir-co2", "model", "a.2", "LIQUID", "co2", "x.y.z", "n"]


def _random_id(rng: random.Random, first: str, rest: str) -> str:
    return rng.choice(first) + "".join(rng.choice(rest) for _ in range(rng.randint(0, 5)))


_ALNUM = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"


def _random_phase(rng: random.Random) -> PhaseId:
    family = rng.choice(FAMILIES)
    shape = rng.randrange(4)
    if shape == 0:
        qualifier = None
    elif shape == 1:
        qualifier = (
            rng.choice(ADVERSARIAL_COMPONENTS)
            if rng.random() < 0.5
            else _random_id(rng, _ALNUM, _ALNUM + "_.:-")
        )
    elif shape == 2:
        component = rng.choice(ADVERSARIAL_COMPONENTS)
        form = (
            rng.choice(ADVERSARIAL_FORMS)
            if rng.random() < 0.5
            else _random_id(rng, _ALNUM, _ALNUM + "_-")
        )
        qualifier = f"{component},{form}"
    else:
        model = (
            rng.choice(ADVERSARIAL_MODELS)
            if rng.random() < 0.5
            else _random_id(rng, _ALNUM[:52], _ALNUM + "_-")
        )
        qualifier = f"model={model}"
    ordinal = 1 if rng.random() < 0.5 else rng.choice([2, 3, 9, 10, 11, 100])
    return PhaseId(family, qualifier, ordinal)


LEGACY_PHASE_IDS = {"LIQUID": PhaseId("LIQUID", None, 1), "VAPOR": PhaseId("VAPOR", None, 1)}
LEGACY_SIGNATURES = {"TWO_PHASE", "ZERO_FLOW"}


def _structures(rng: random.Random, count: int) -> Iterator[tuple[object, str]]:
    for index in range(count):
        if index % 2 == 0:
            phase = _random_phase(rng)
            yield phase, phase.render()
        else:
            members = {_random_phase(rng) for _ in range(rng.randint(1, 4))}
            phases = phase_set(members)
            yield phases, render_phase_set(phases)


def test_e_f2_5_phase_ids_render_injectively_and_parse_back() -> None:
    """[gen] 10^4 phases and phase sets: parse inverts render; no two structures render alike (a
    one-phase set is its phase); a rendering equals a legacy phase id only for that phase, and
    never a legacy signature."""
    rng = random.Random(62)
    seen: dict[str, object] = {}
    qualified = {family: 0 for family in FAMILIES}
    for structure, text in _structures(rng, 10_000):
        if isinstance(structure, PhaseId):
            assert parse_phase_id(text) == structure, text
            if structure.qualifier is not None:
                qualified[structure.family] += 1
        else:
            assert parse_phase_set(text) == structure, text
        # A one-phase set renders as its phase: the set's id space contains the phases'.
        same = structure[0] if isinstance(structure, tuple) and len(structure) == 1 else structure
        assert seen.setdefault(text, same) == same, text
        assert text not in LEGACY_SIGNATURES
        if text in LEGACY_PHASE_IDS:
            assert same == LEGACY_PHASE_IDS[text]
    print(f"E-F2-5 (phase ids): 10000 structures, {len(seen)} distinct renderings, {qualified}")
    assert len(seen) > 5_000
    assert min(qualified.values()) > 500  # qualifiers on every family (Q4.A5)
    # A component id equal to a model id renders three different ways.
    renders = {PhaseId("SOLID", q, 1).render() for q in ("a.2", "a.2,I", "model=a.2")}
    assert len(renders) == 3
