"""T06 W6 (A3): step 5 at a perturbed start — A85 (a)–(d), over the published file; no solve.

Spec `docs/derivations/T06-corpus-spec.md` §6.2 (A3) and A85. Every heater-style lifted split of a
perturbed revision start is the provider's TP flash of its perturbed outlet stream, PH-type
included; ADR 0012 D5's closure seed is the traversal start's rule, not the ensemble's. (a) checks
the rule's premise (no published outlet stream lies in the degeneracy window), (b) restates the
rule without the generator's `lifted_split_values` and recomputes every published split column
from the start's own stream columns, (c) pins the zero-perturbation assembly against
`traversal-G0-v1`'s start — the 17 equalities **and** THM-08's and THM-09's four-column
difference, so neither a closure seed nor a dropped re-split passes — and (d) pins the regime
census the report's readers need. A25 only proves the file is what the generator writes; this
file says what the generator must have written.
"""

from __future__ import annotations

import math
import struct
from collections import Counter
from functools import cache
from typing import Any

import pytest
from t06_ensemble_support import ensemble_cases
from test_t06_w6_generator import BY_CASE

from benchmarks.t06 import ensemble, generator
from openflowsheet.application.revision_binding import RevisionBinding, bind_revision_flowsheet
from openflowsheet.models import flow_id, pressure_id, temperature_id
from openflowsheet.models.syn001 import TEMPERATURE_TOLERANCE
from openflowsheet.models.syn001.saturation_band import degeneracy_distance
from openflowsheet.models.syn001.tp_state import tp_state
from openflowsheet.orchestrator import revision
from openflowsheet.orchestrator.splits import SPLIT_RULES, LiftedSplit, lifted_splits
from openflowsheet.thermo import StreamState

CASES = {case.case: case for case in ensemble_cases()}
REVISION_CASES = [case_id for case_id, case in CASES.items() if case.path == "revision_eo"]
#: The two cases whose valve closes by the saturation route at `T_sat` (temperature-degenerate
#: at the traversal start), and the four split columns the TP flash of pure B at `T_sat` moves.
DEGENERATE_AT_TRAVERSAL = ("THM-08", "THM-09")
VALVE_SPLIT = ("S2.vap.B", "S2.liq.B", "S2.V", "S2.L")


def _bits(value: float) -> bytes:
    return struct.pack(">d", float(value))


def _same(computed: float, published: Any) -> bool:
    """Bit for bit; canonical JSON spells `±0.0` alike, so a zero compares as a zero (A24 checks
    the sign in memory)."""
    if computed == 0.0 == float(published):
        return True
    return _bits(computed) == _bits(published)


@cache
def _binding(case_id: str) -> RevisionBinding:
    binding = bind_revision_flowsheet(CASES[case_id].document())
    assert isinstance(binding, RevisionBinding)
    return binding


def _splits(case_id: str) -> list[tuple[LiftedSplit, str]]:
    """Each lifted split of the case with its style (`outlet` or `products`), declaration order."""
    flowsheet = _binding(case_id).flowsheet
    instances = revision.instances_of(flowsheet)
    models = {unit: model for unit, model, _ in instances}
    return [
        (split, SPLIT_RULES[models[split.unit]].style)
        for split in lifted_splits(instances, flowsheet.components)
    ]


def _stream(case_id: str, split: LiftedSplit, vector: dict[str, Any]) -> StreamState:
    components = _binding(case_id).flowsheet.components
    return StreamState(
        n=tuple(float(vector[flow_id(split.stream, c)]) for c in components),
        temperature=float(vector[temperature_id(split.stream)]),
        pressure=float(vector[pressure_id(split.stream)]),
    )


def test_the_revision_cases_are_the_nineteen() -> None:
    assert len(REVISION_CASES) == 19
    assert set(DEGENERATE_AT_TRAVERSAL) <= set(REVISION_CASES)


# -- (a) the premise ------------------------------------------------------------------------------


@cache
def _smallest_distance(case_id: str) -> tuple[float, int, str] | None:
    """The smallest degeneracy distance over the case's published starts and heater-style splits,
    with where it occurs; `None` when the case has no heater-style split. Every such stream is
    asserted flowing on the way."""
    flowsheet = _binding(case_id).flowsheet
    smallest: tuple[float, int, str] | None = None
    for split, style in _splits(case_id):
        if style != "outlet":
            continue
        for start in BY_CASE[case_id]["starts"]:
            stream = _stream(case_id, split, start["vector"])
            assert sum(stream.n) > 0.0, (case_id, start["start"], split.unit)
            distance = degeneracy_distance(
                flowsheet.provider,
                stream.n,
                stream.temperature,
                stream.pressure,
                flowsheet.context,
            )
            if smallest is None or distance < smallest[0]:
                smallest = (distance, start["start"], split.unit)
    return smallest


@pytest.mark.parametrize("case_id", REVISION_CASES)
def test_a85a_every_published_outlet_stream_is_flowing_and_outside_the_window(
    case_id: str,
) -> None:
    smallest = _smallest_distance(case_id)
    if smallest is not None:
        assert smallest[0] > TEMPERATURE_TOLERANCE, (case_id, smallest)


def test_a85a_the_margins_are_the_measured_ones() -> None:
    """*Measured (A3)*: 0.339 K on THM-08 (start 05, the valve), 0.663 K on THM-09, ≥ 7.61 K
    (three significant digits) on every other case — 5.5 decades above `τ_T = 1e-6 K`."""
    assert TEMPERATURE_TOLERANCE == 1e-6
    margins = {case_id: _smallest_distance(case_id) for case_id in REVISION_CASES}
    thm08, thm09 = margins["THM-08"], margins["THM-09"]
    assert thm08 is not None and thm09 is not None
    assert (f"{thm08[0]:.3g}", thm08[1], thm08[2]) == ("0.339", 5, "U-VLV")
    assert f"{thm09[0]:.3g}" == "0.663" and thm09[2] == "U-VLV"
    others = [m[0] for c, m in margins.items() if m is not None and c not in ("THM-08", "THM-09")]
    assert others and f"{min(others):.3g}" == "7.61"


# -- (b) the rule, restated -----------------------------------------------------------------------


@pytest.mark.parametrize("case_id", REVISION_CASES)
def test_a85b_every_published_split_column_is_the_rule_applied_to_its_stream(
    case_id: str,
) -> None:
    """Heater style: `tp_state` of the start's own `(n, T, P)` — status `ok` — with the vapour
    and liquid flows for `vap.<c>`/`liq.<c>` and their sums in component order for `V`/`L`;
    products style: the sums of the product streams' recorded flows for the totals."""
    flowsheet = _binding(case_id).flowsheet
    checked = 0
    for split, style in _splits(case_id):
        for start in BY_CASE[case_id]["starts"]:
            vector = start["vector"]
            if style == "outlet":
                result = tp_state(
                    flowsheet.provider, _stream(case_id, split, vector), flowsheet.context
                )
                assert result.status == "ok", (case_id, start["start"], split.unit)
                assert result.vapor is not None and result.liquid is not None
                expected = {
                    **dict(zip(split.vapor, result.vapor.n, strict=True)),
                    **dict(zip(split.liquid, result.liquid.n, strict=True)),
                    split.vapor_total: sum(result.vapor.n),
                    split.liquid_total: sum(result.liquid.n),
                }
            else:
                expected = {
                    split.vapor_total: sum(float(vector[column]) for column in split.vapor),
                    split.liquid_total: sum(float(vector[column]) for column in split.liquid),
                }
            for column, value in expected.items():
                assert _same(value, vector[column]), (case_id, start["start"], column)
                checked += 1
    assert checked > 0 or not _splits(case_id)


def test_a85b_the_rule_covers_the_measured_2800_values() -> None:
    total = 0
    for case_id in REVISION_CASES:
        for split, style in _splits(case_id):
            per_start = len(split.vapor) + len(split.liquid) + 2 if style == "outlet" else 2
            total += per_start * len(BY_CASE[case_id]["starts"])
    assert total == 2800


# -- (c) zero perturbation ------------------------------------------------------------------------


@pytest.mark.parametrize("case_id", REVISION_CASES)
def test_a85c_the_zero_perturbation_assembly_against_the_traversal_start(case_id: str) -> None:
    """`assemble(x_init)` equals `traversal-G0-v1`'s start bit for bit on 17 cases; on THM-08 and
    THM-09 on every column but exactly the valve's four split columns, which are the TP flash of
    pure B at `T_sat` — `LIQUID` — against `x_init`'s closure split."""
    setup = ensemble.setup(CASES[case_id])
    assert setup.initializer == revision.INITIALIZER_ID
    for column, value in BY_CASE[case_id]["x_init"].items():
        assert _same(setup.x_init[column], value), (case_id, column)
    assembled = setup.assemble(dict(setup.x_init))
    assert not isinstance(assembled, generator.JointRefusal), (case_id, assembled)
    differing = {
        column
        for column, value in assembled.vector.items()
        if _bits(value) != _bits(setup.x_init[column])
    }
    if case_id not in DEGENERATE_AT_TRAVERSAL:
        assert differing == set()
        return
    assert differing == set(VALVE_SPLIT)
    assert [setup.x_init[column] for column in VALVE_SPLIT] == [0.0672, 1.9328, 0.0672, 1.9328]
    moved = [assembled.vector[column] for column in VALVE_SPLIT]
    assert moved == [0.0, 2.0, 0.0, 2.0]
    assert math.copysign(1.0, moved[0]) > 0.0 and math.copysign(1.0, moved[2]) > 0.0
    assert assembled.regimes["U-VLV"] == "LIQUID"


# -- (d) the census -------------------------------------------------------------------------------


def test_a85d_the_valve_regime_census_from_the_file() -> None:
    census = {
        case_id: Counter(start["regimes"]["U-VLV"] for start in BY_CASE[case_id]["starts"])
        for case_id in ("THM-08", "THM-09", "STR-01", "NET-11")
    }
    assert census == {
        "THM-08": Counter({"LIQUID": 11, "VAPOR": 9}),
        "THM-09": Counter({"LIQUID": 12, "VAPOR": 8}),
        "STR-01": Counter({"TWO_PHASE": 11, "LIQUID": 9}),
        "NET-11": Counter({"TWO_PHASE": 10, "LIQUID": 10}),
    }
