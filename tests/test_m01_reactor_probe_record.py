"""M01.A52: the reactor probe record holds spec §8.15's record halves (Amendment 1, §9.10).

`benchmarks/m01/reactor-probe.json` (version 2) is what `benchmarks/m01/reactor_probe.py` measured
once, in its own environment, of the group's reactor at the pin (spec §8.1, §10). Its bytes are
pinned by M01.A34 (`derived_from_measured.probe_sha256`); these tests check that its numbers hold
what §8.15's record column states for A41-A46 and A48, so the specification and the record cannot
drift apart. The gate never runs the reactor. The record is a regression of the group's model on
one machine, never an expectation for this repository's code; the adapter halves are M02's.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

import pytest
from conftest import REPO_ROOT, load_json

from openflowsheet.models.c1.boundary import tube_inlet
from openflowsheet.thermo import StreamState

RECORD: Mapping[str, Any] = load_json(REPO_ROOT / "benchmarks" / "m01" / "reactor-probe.json")
PINNED: Mapping[str, Any] = RECORD["pinned"]
GRID: Sequence[Mapping[str, Any]] = RECORD["grid"]
NEIGHBOURS: Sequence[Mapping[str, Any]] = RECORD["neighbouring_inlet_temperatures"]
#: Every solved entry: the grid, the pinned design-grid run and both neighbouring inlets.
ENTRIES: Sequence[Mapping[str, Any]] = (*GRID, PINNED, *NEIGHBOURS)
ENTRY_IDS = (
    *(f"grid_{entry['num_z']}" for entry in GRID),
    "pinned",
    *(f"neighbour_{entry['T_in_K']}" for entry in NEIGHBOURS),
)
#: Spec §8.1's pin.
REACTOR_COMMIT = "6089593464fc9bc2c0a0cb58e30ad5433ece6332"
DESIGN_NUM_Z = 800


def test_a52_the_records_identity() -> None:
    assert RECORD["version"] == 2
    assert RECORD["reactor_commit"] == REACTOR_COMMIT
    assert RECORD["environment"]["packages"]["pymrm"] == "2.5.0"
    assert RECORD["pinned_num_z"] == PINNED["num_z"] == DESIGN_NUM_Z


def test_a52_a41_the_start_strategy_accepted_at_the_design_grid_and_the_cold_start_rejected() -> (
    None
):
    accepted = [PINNED, *NEIGHBOURS]
    assert sorted(entry["T_in_K"] for entry in accepted) == [653.15, 673.15, 693.15]
    for entry in accepted:
        assert entry["num_z"] == DESIGN_NUM_Z
        assert entry["m01_accepted"] is True
    cold = RECORD["cold_start_true_inlet"]
    assert sorted(entry["dt_init"] for entry in cold) == [1e-6, 1e-3, 1e-1]
    assert len(cold) == 3
    for entry in cold:
        assert entry["num_z"] == 100
        assert entry["accepted"] is False


def test_a52_a42_path_independence() -> None:
    assert RECORD["path_independence"]["max_rel_diff"] <= 1e-6


def test_a52_a43_two_repeats_bitwise_identical() -> None:
    assert RECORD["repeats"]["runs"] == 2
    assert RECORD["repeats"]["bitwise_identical"] is True


def test_a52_a44_the_backflow_override_is_inert() -> None:
    assert RECORD["backflow_override"]["bitwise_identical"] is True
    assert RECORD["backflow_override"]["alternative_backflow"] == [0.0, 0.0, 0.0, 1.0, 0.0]


@pytest.mark.parametrize("entry", ENTRIES, ids=ENTRY_IDS)
def test_a52_a44_the_retentate_velocity_is_positive(entry: Mapping[str, Any]) -> None:
    assert entry["u_ret_min"] > 0.0


@pytest.mark.parametrize(
    "entry",
    [entry for entry in ENTRIES if entry["m01_accepted"]],
    ids=[name for name, entry in zip(ENTRY_IDS, ENTRIES, strict=True) if entry["m01_accepted"]],
)
def test_a52_a45_element_defects_of_every_accepted_entry(entry: Mapping[str, Any]) -> None:
    defects = entry["element_defect_rel"]
    assert set(defects) == {"H", "N", "C", "Ar"}
    assert max(abs(value) for value in defects.values()) <= 1e-7


@pytest.mark.parametrize("entry", ENTRIES, ids=ENTRY_IDS)
def test_a52_a46_the_pressure_drop_of_every_entry(entry: Mapping[str, Any]) -> None:
    assert abs(entry["dP_over_P"]) <= 1e-3


def test_a52_a48_the_grid_sequence_accepted_exactly_up_to_the_design_grid() -> None:
    assert [entry["num_z"] for entry in GRID] == [100, 200, 400, 800, 1600, 3200]
    assert [entry["m01_accepted"] for entry in GRID] == [True] * 4 + [False] * 2


def test_a52_spec_10_1s_design_grid_row_is_the_record_to_its_printed_digits() -> None:
    (design,) = (entry for entry in GRID if entry["num_z"] == DESIGN_NUM_Z)
    for entry in (design, PINNED):
        assert f"{entry['outlet_n_mol_s'][2]:.12e}" == "7.451757058514e-04"
        assert f"{entry['T_out_K']:.6f}" == "757.335312"


def _ulps(value: float, expected: float) -> float:
    return abs(value - expected) / math.ulp(expected)


def test_a52_the_boundarys_mapping_of_the_recorded_n_is_within_2_ulp_of_the_recorded_tube() -> None:
    # Why A47 (a) is stated at the evaluation (Amendment 1): the record was made from (F, y), and
    # §8.3's mapping of the recorded n differs from F by 1 ulp and from y by 1 ulp in four places.
    inlet = StreamState(
        n=tuple(PINNED["inlet_n_mol_s"]), temperature=PINNED["T_in_K"], pressure=PINNED["P_in_Pa"]
    )
    tube = tube_inlet(inlet, n_tubes=1.0)
    assert _ulps(tube.flow, PINNED["F_ret_in_mol_s"]) <= 2.0
    assert len(tube.composition) == len(PINNED["y_in"]) == 5
    for got, expected in zip(tube.composition, PINNED["y_in"], strict=True):
        assert _ulps(got, expected) <= 2.0
    assert (tube.temperature, tube.outlet_pressure) == (PINNED["T_in_K"], PINNED["P_in_Pa"])
