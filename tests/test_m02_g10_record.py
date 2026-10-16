"""M02 G10's record in the default gate (design note §10.2; M01 spec §8.15): the gate checks the
committed record of the adapter halves of M01.A41-A48, never the reactor
(`benchmarks/m02/g10_adapter_halves.py` made it, opt-in, in the pinned environment).

The record belongs to the registered variant, the child, the lock and the probe record it was
measured against: a change to any of them leaves the record stale and fails here until G10 is run
again. Each assertion is judged against the record's own numbers, at G10's bounds.

Since §14.5 D1/D2 the child is v3's, and this record's variant (v2) is superseded: the record is
pinned to v2's own runner, which is no longer this tree's child (v2's child is in git history), and
G10v3's record (`g10-adapter-halves-v3.json`, `test_m02_g10v3_record.py`) is the current child's.
"""

from __future__ import annotations

from typing import Any

from conftest import REPO_ROOT, load_json, load_yaml

from openflowsheet.adapters import variants
from openflowsheet.adapters.pymrm import env
from openflowsheet.canonical import file_sha256

RECORD: dict[str, Any] = load_json(REPO_ROOT / "benchmarks" / "m02" / "g10-adapter-halves.json")
PROBE_PATH = REPO_ROOT / "benchmarks" / "m01" / "reactor-probe.json"
CHILD = REPO_ROOT / "src" / "openflowsheet" / "adapters" / "pymrm" / "child.py"
ASSERTIONS: dict[str, Any] = RECORD["assertions"]


def test_the_record_is_a_measurement_of_the_registered_variant_in_its_environment() -> None:
    assert (RECORD["record"], RECORD["status"], RECORD["judged"]) == (
        "m02-g10-adapter-halves",
        "measured",
        False,
    )
    variant = variants.registered_variant(RECORD["variant"]["variant_id"])
    assert RECORD["variant"]["sha256"] == variant.sha256
    environment = RECORD["environment"]
    assert environment["runner_sha256"] == variant.evaluation["runner_sha256"]
    assert environment["runner_sha256"] != file_sha256(CHILD)  # v2 is superseded (§14.5 D1/D2)
    assert environment["lock_sha256"] == file_sha256(env.packaged_lock())
    assert environment["env_id"] == variant.evaluation["environment"]["env_id"]
    assert RECORD["probe_record_sha256"] == file_sha256(PROBE_PATH)
    for name in ("fingerprint_sha256", "export_tree_sha256", "merged_database_sha256"):
        assert len(environment[name]) == 64, name
    assert environment["cpu_model"]  # the probe record lacks it (M01 spec §8.15)


def test_a41_the_start_strategy_is_accepted_at_the_three_inlet_temperatures() -> None:
    assert ASSERTIONS["A41"] == {"T_in_K": [653.15, 673.15, 693.15], "accepted": [True] * 3}


def test_a42_the_two_s2_starts_agree_within_the_path_independence_bound() -> None:
    a42 = ASSERTIONS["A42"]
    assert a42["s2_dt_init"] == [1e-6, 1e-1] and a42["bound"] == 1e-6
    assert 0.0 < a42["max_rel_diff"] <= 1e-6


def test_a43_two_bypassed_runs_are_bitwise_equal() -> None:
    assert ASSERTIONS["A43"] == {"bypassed_runs": 2, "repeat_bitwise_equal": [True, True]}


def test_a44_the_backflow_override_is_inert_and_the_flow_never_reverses() -> None:
    a44 = ASSERTIONS["A44"]
    assert a44["alternative_backflow"] == [0.0, 0.0, 0.0, 1.0, 0.0]
    assert a44["bitwise_identical"] is True
    assert len(a44["u_ret_min"]) == len(RECORD["runs"]) and min(a44["u_ret_min"]) > 0.0


def test_a45_and_a46_every_run_is_inside_the_element_and_pressure_bounds() -> None:
    accepted = [run for run in RECORD["runs"] if run["status"] == "completed" and not run["stage"]]
    assert len(accepted) == len(RECORD["runs"]) == 8
    assert ASSERTIONS["A45"]["bound"] == 1e-7
    assert len(ASSERTIONS["A45"]["element_defect_max"]) == 8
    assert max(ASSERTIONS["A45"]["element_defect_max"]) <= 1e-7
    assert ASSERTIONS["A46"]["bound"] == 1e-3
    assert max(map(abs, ASSERTIONS["A46"]["dP_over_P"])) <= 1e-3


def test_a47_the_nominal_outlet_is_the_probes_bitwise_and_through_the_boundary() -> None:
    a47 = ASSERTIONS["A47"]
    probe = load_json(PROBE_PATH)
    block = {name: RECORD["environment"][name] for name in ("python", "platform", "packages")}
    block["threads"] = RECORD["environment"]["threads"]
    assert a47["a_environment_block_equal"] is (block == probe["environment"])
    assert a47["a_bitwise"] is True  # measured; equal block and unequal bits would be a finding
    (nominal,) = [run for run in RECORD["runs"] if run["label"] == "direct nominal"]
    assert nominal["tube_outlet"]["flows"] == probe["pinned"]["outlet_n_mol_s"]
    assert nominal["tube_outlet"]["temperature"] == probe["pinned"]["T_out_K"]
    assert a47["b_bound"] == 1e-6 and 0.0 <= a47["b_max_rel_diff"] <= 1e-6


def test_a48_every_ok_result_reports_the_registered_discretization_estimate() -> None:
    assert ASSERTIONS["A48"] == {"estimates_equal_reference": [True] * 3}
    reference = load_yaml(REPO_ROOT / "benchmarks" / "m01" / "reference_values.yaml")
    estimate = reference["derived_from_measured"]["discretization_estimate"]
    for run in RECORD["runs"]:
        if run.get("envelope_status") == "ok":
            assert run["discretization_estimate"] == estimate
