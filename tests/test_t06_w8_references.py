"""T06 W8: the reference comparisons, gated on the committed records (spec §9, A47–A54).

The gate never runs DWSIM or IDAES (spec §9.6). It reads the committed tool records
`benchmarks/t06/references/results/<tool>-<fixture>.json`, our committed records
`ours-<fixture>.json` and the twin, recomputes the comparison table with
`scripts/t06_reference_comparison.py`, and requires it to equal the committed
`benchmarks/t06/references/comparison.json` byte for byte (A50); it also solves our side live and
requires the committed records to be what a solve produces today. The classification is
mechanical; the recorded verdict is the `verdict` agent's.

The expectations are independent of both sides: the twin's 20-digit values and preregistered
tolerances (`ref.closed_form.reference_fixtures`), the twin's predicted effects of the two
positive controls (`ref.closed_form.positive_controls`), the registered tool settings
(`ref.closed_form.reference_tool_settings`, `.dwsim_input_mapping`) and the environment
fingerprint printed in `docs/reference-environments.md` §3.
"""

from __future__ import annotations

import ast
import copy
import json
import math
import re
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from conftest import REPO_ROOT, load_yaml, sha256_of

sys.path.insert(0, str(REPO_ROOT / "scripts"))
sys.path.insert(0, str(REPO_ROOT / "spikes" / "references"))

import t06_fixtures as fx  # noqa: E402
import t06_reference_comparison as comparison  # noqa: E402
import t06_references_ours as ours_side  # noqa: E402

REFERENCES = REPO_ROOT / "benchmarks" / "t06" / "references"
RESULTS = REFERENCES / "results"
TWIN = load_yaml(REPO_ROOT / "benchmarks" / "t06" / "reference_values.yaml")["closed_form"]
SETTINGS = TWIN["reference_tool_settings"]

TOOL_RECORDS = [(tool, fixture) for tool in comparison.TOOLS for fixture in comparison.FIXTURES]


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def record(tool: str, fixture: str) -> dict[str, Any]:
    loaded: dict[str, Any] = load(RESULTS / f"{tool.lower()}-{fixture}.json")
    return loaded


def ran(tool: str, fixture: str) -> bool:
    return "not_applicable" not in record(tool, fixture)


@pytest.fixture(scope="module")
def table() -> dict[str, Any]:
    committed: dict[str, Any] = load(REFERENCES / "comparison.json")
    return committed


def rows(table: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    return {(r["fixture"], r["tool"]): r for r in table["rows"]}


# -- A50: the table recomputes from the committed files --------------------------------------------


def test_a50_the_table_recomputes_identically_from_the_committed_json() -> None:
    recomputed = comparison.dumps(comparison.compute())
    assert recomputed == (REFERENCES / "comparison.json").read_text(encoding="utf-8")


def test_a50_the_committed_files_are_the_hashed_ones(table: dict[str, Any]) -> None:
    for name, digest in table["inputs_sha256"].items():
        path = REPO_ROOT / "benchmarks" / "t06" / name
        assert sha256_of(path) == digest, name
    sums = (RESULTS / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
    listed = {}
    for line in sums:
        digest, name = line.split("  ", 1)
        listed[name] = digest
    assert sorted(listed) == sorted(p.name for p in RESULTS.iterdir() if p.name != "SHA256SUMS")
    for name, digest in listed.items():
        assert sha256_of(RESULTS / name) == digest, name


@pytest.mark.parametrize("fixture", list(ours_side.SOURCES))
def test_a50_our_committed_record_is_what_a_live_solve_produces(fixture: str) -> None:
    """A50 (b) (A5): our committed record is what a live solve produces — the same set of keys,
    every non-float value exactly (outcome, verdict, limitations, non-passing checks, ids, hashes
    of inputs), every float of the state and of the compared quantities to roundoff (relative
    `ROUNDOFF_REL`, `abs_tol = 0`). **No field is exempt**, and the records carry no
    `certificate_sha256` (§9.6 (A5)): a certificate's roundoff-level floats differ between
    machines. Measured on CI (`d0797f6`, `93472b6`): REF-08's iterated recycle state differs in its
    last bits (x86-64 and aarch64 runners vs the reference machine; up to 1.2e-15 relative) —
    ADR 0007: such floats are not a cross-platform promise, and every comparison tolerance is at
    least 1e6 times wider."""
    committed = load(RESULTS / f"ours-{fixture}.json")
    assert "certificate_sha256" not in committed
    live = json.loads(json.dumps(ours_side.solve(fixture), sort_keys=True))
    _assert_equal_to_roundoff(live, committed, fixture)


#: The float tolerance of A50's cross-machine comparison: roundoff, far inside every §9.4 tolerance.
ROUNDOFF_REL = 1e-12


def _assert_equal_to_roundoff(live: Any, committed: Any, where: str) -> None:
    if isinstance(committed, dict):
        assert isinstance(live, dict) and set(live) == set(committed), where
        for key in committed:
            _assert_equal_to_roundoff(live[key], committed[key], f"{where}.{key}")
    elif isinstance(committed, list):
        assert isinstance(live, list) and len(live) == len(committed), where
        for index, (a, b) in enumerate(zip(live, committed, strict=True)):
            _assert_equal_to_roundoff(a, b, f"{where}[{index}]")
    elif isinstance(committed, float) and not isinstance(committed, bool):
        assert isinstance(live, float), where
        assert math.isclose(live, committed, rel_tol=ROUNDOFF_REL, abs_tol=0.0), (
            where,
            live,
            committed,
        )
    else:
        assert type(live) is type(committed) and live == committed, where


def test_a50s_roundoff_bound_still_catches_a_real_change() -> None:
    """A change beyond roundoff fails A50's comparison (the bound is not a loophole)."""
    with pytest.raises(AssertionError):
        _assert_equal_to_roundoff({"x": 1.0 + 1e-9}, {"x": 1.0}, "probe")
    _assert_equal_to_roundoff({"x": 1.0 + 2e-16}, {"x": 1.0}, "probe")
    with pytest.raises(AssertionError):  # `abs_tol = 0`: a zero stays a zero
        _assert_equal_to_roundoff({"x": 1e-300}, {"x": 0.0}, "probe")


@pytest.mark.parametrize("edit", ["add", "remove", "edit_string", "edit_list", "retype"])
def test_a50_adding_or_editing_any_field_of_a_committed_record_fails(edit: str) -> None:
    """A50 (A5): no field is exempt — a committed record with a field added (the dropped
    `certificate_sha256`), removed, or edited (a string, a list, a float written as an integer)
    no longer matches the record a live solve produces."""
    live = load(RESULTS / "ours-REF-01.json")
    committed = json.loads(json.dumps(live))
    if edit == "add":
        committed["certificate_sha256"] = "0" * 64
    elif edit == "remove":
        del committed["revision_id"]
    elif edit == "edit_string":
        committed["verification_status"] = "UNVERIFIED"
    elif edit == "edit_list":
        committed["limitations"] = [*committed["limitations"], "an added limitation"]
    else:
        committed["compared_quantities"]["S3.T"] = int(committed["compared_quantities"]["S3.T"])
    _assert_equal_to_roundoff(live, json.loads(json.dumps(live)), "unedited")
    with pytest.raises(AssertionError):
        _assert_equal_to_roundoff(live, committed, edit)


# -- A47: our side ---------------------------------------------------------------------------------


@pytest.mark.parametrize("fixture", [*comparison.REF_FIXTURES, "PC-2"])
def test_a47_our_side_is_verified_at_the_twin_within_a_tenth_of_the_tolerance(
    fixture: str,
) -> None:
    ours = load(RESULTS / f"ours-{fixture}.json")
    assert ours["outcome"] == "CONVERGED"
    assert ours["verification_status"] == "VERIFIED"
    assert ours["non_passing_checks"] == []
    quantities = comparison.registered({"closed_form": TWIN}, fixture)
    for quantity, entry in quantities.items():
        error = abs(Decimal(repr(ours["compared_quantities"][quantity])) - Decimal(entry["value"]))
        assert error <= Decimal(entry["tolerance"]) / 10, quantity


def test_the_revision_path_runs_the_registered_policies() -> None:
    for fixture, (_, path) in ours_side.SOURCES.items():
        ours = load(RESULTS / f"ours-{fixture}.json")
        assert ours["policy_id"] == ("SYN-001-K03" if path == "tear" else "T06-revision-v2")


# -- the registration the table is computed against ------------------------------------------------


@pytest.mark.parametrize("fixture", comparison.FIXTURES)
def test_the_tools_report_exactly_the_registered_quantities(fixture: str) -> None:
    registered = set(comparison.registered({"closed_form": TWIN}, fixture))
    if fixture == "PC-1":
        assert registered == {TWIN["positive_controls"]["PC-1"]["quantity"]}
        assert registered <= set(fx.COMPARED[fixture])
    else:
        assert set(fx.COMPARED[fixture]) == registered
    for tool in comparison.TOOLS:
        if ran(tool, fixture):
            assert list(record(tool, fixture)["compared_quantities"]) == list(fx.COMPARED[fixture])


@pytest.mark.parametrize("fixture", comparison.REF_FIXTURES)
def test_every_registered_tolerance_is_the_spec_formula(fixture: str) -> None:
    """§9.4: `a_k + 1e-6 |v|`, registered by the twin to six significant digits."""
    for quantity, entry in comparison.registered({"closed_form": TWIN}, fixture).items():
        exact = comparison.tolerance(entry["kind"], Decimal(entry["value"]))
        assert Decimal(entry["tolerance"]) == Decimal(f"{exact:.6g}"), quantity


def test_dwsim_compared_quantities_recompute_from_the_raw_output() -> None:
    for fixture in comparison.FIXTURES:
        rec = record("DWSIM", fixture)
        recomputed = fx.dwsim_compared_quantities(fixture, rec["raw_output"])
        assert recomputed == rec["compared_quantities"], fixture


# -- A48: fingerprints -----------------------------------------------------------------------------

_DOC_KEYS = {
    ("idaes", "pip freeze sha256"): "pip_freeze_sha256",
    ("idaes", "idaes-data/bin tree"): "idaes_data_bin_tree",
    ("idaes", "ipopt sha256"): "ipopt_sha256",
    ("dwsim", "pip freeze sha256"): "pip_freeze_sha256",
    ("dwsim", "dotnet tree"): "dotnet_tree",
    ("dwsim", "dwsim tree"): "dwsim_tree",
    ("dwsim", "DWSIM.Automation.dll sha256"): "automation_dll_sha256",
}


def documented_fingerprint() -> dict[str, dict[str, str]]:
    text = (REPO_ROOT / "docs" / "reference-environments.md").read_text(encoding="utf-8")
    out: dict[str, dict[str, str]] = {"idaes": {}, "dwsim": {}}
    for tool, label, digest in re.findall(r"^\[\.venv-(\w+)\] (.+): ([0-9a-f]{64})$", text, re.M):
        key = _DOC_KEYS[tool, label]
        assert out[tool].setdefault(key, digest) == digest, (tool, label)
    return out


def test_a48_the_expected_fingerprint_is_the_documented_one() -> None:
    assert documented_fingerprint() == fx.EXPECTED_FINGERPRINT


@pytest.mark.parametrize(("tool", "fixture"), TOOL_RECORDS)
def test_a48_every_record_ran_in_the_documented_environment(tool: str, fixture: str) -> None:
    rec = record(tool, fixture)
    measured = rec["environment_fingerprint"]["measured"]
    assert measured == documented_fingerprint()[tool.lower()]
    assert rec["environment_fingerprint"]["matches"] is True


# -- A49: settings and mappings --------------------------------------------------------------------


@pytest.mark.parametrize("fixture", [f for f in comparison.FIXTURES if f != "PC-1"])
def test_a49_idaes_settings_are_the_registered_ones(fixture: str) -> None:
    rec = record("IDAES", fixture)
    final = SETTINGS["IDAES"]["final_solve"]
    used = rec["final_solve_ipopt_options_used"]
    assert used == rec["settings"]["final_solve_ipopt_options"]
    assert used["linear_solver"] == final["linear_solver"] == "mumps"
    for option in ("tol", "constr_viol_tol", "max_iter"):
        assert float(used[option]) == float(final[option]), option
    assert float(used["constr_viol_tol"]) == 1e-9
    assert rec["adjustments"] == []
    assert rec["settings"]["initializer_ipopt_options"]["linear_solver"] == "mumps"
    assert SETTINGS["IDAES"]["initializers"]["linear_solver"] == "mumps"
    assert rec["ipopt"]["linear_solver"] == "mumps"
    optimal = rec["ipopt"]["exit"] == comparison.IPOPT_OPTIMAL
    assert SETTINGS["IDAES"]["converged_iff_termination"] + "." == comparison.IPOPT_OPTIMAL
    assert rec["converged"] is optimal


@pytest.mark.parametrize("fixture", comparison.FIXTURES)
def test_a49_dwsim_settings_and_mappings_are_the_registered_ones(fixture: str) -> None:
    rec = record("DWSIM", fixture)
    registered = SETTINGS["DWSIM"]
    readback = rec["settings_readback"]
    # §9.3: PT and PH flash, external and internal loops, as DWSIM reads them back.
    loops = [
        f"{flash}Flash_{kind}"
        for flash in ("PT", "PH")
        for kind in (
            "External_Loop_Tolerance",
            "Internal_Loop_Tolerance",
            "Maximum_Number_Of_External_Iterations",
            "Maximum_Number_Of_Internal_Iterations",
        )
    ]
    for key in loops:
        value = readback["flash_settings"][key]
        if "Tolerance" in key:
            assert float(value) == float(registered["flash_loop_tolerances"]), key
        else:
            assert int(value) == registered["flash_loop_iterations"], key
    assert readback["LiquidDensity_CorrectExpDataForPressure"] is False
    mapping = TWIN["dwsim_input_mapping"]
    offset = [Decimal(v) for v in mapping["unmapped_latent_offset_J_per_mol"]]
    for i, c in enumerate(fx.COMPONENTS):
        compound = readback["compounds"][c]
        latent = Decimal(repr(compound["HVap_A_J_per_kmol"])) / 1000
        expected = Decimal(mapping["dH_vap_J_per_mol"][i]) + (offset[i] if fixture == "PC-1" else 0)
        assert latent == expected, c
        formation = Decimal(repr(compound["IG_Enthalpy_of_Formation_25C_kJ_per_kg"]))
        assert abs(formation * 100 - Decimal(mapping["dH_f_ig_J_per_mol"][i])) <= Decimal("1e-9")
        assert compound["Critical_Temperature"] == 1000.0
        assert compound["Critical_Pressure"] == 1.0e7
        assert compound["Acentric_Factor"] == 0.0
    if fixture == "REF-08":
        recycle = rec["raw_output"]["units"]["REC"]
        spec = registered["recycle"]
        assert recycle["tolerances_used"] == {
            "mass_flow_kg_per_s": float(spec["mass_flow_kg_per_s"]),
            "temperature_K": float(spec["temperature_K"]),
            "pressure_Pa": float(spec["pressure_Pa"]),
        }
        assert recycle["MaximumIterations"] == spec["iterations"]
        assert recycle["AccelerationMethod"].lower() == spec["acceleration"]
        assert recycle["LegacyMode"] is spec["legacy_mode"] is True


@pytest.mark.parametrize("tool", comparison.TOOLS)
def test_a49_the_recycle_guess_and_the_pc2_feed_are_the_registered_ones(tool: str) -> None:
    guess = SETTINGS["REF-08_tool_recycle_guess"]
    tear = record(tool, "REF-08")["definition"]["tear_guess"]
    assert [tear["flows"][c] for c in fx.COMPONENTS] == [float(v) for v in guess["n_mol_per_s"]]
    assert (tear["T"], tear["P"]) == (float(guess["T_K"]), float(guess["P_Pa"]))
    feed = SETTINGS["PC-2"]["feed"]
    definition = record(tool, "PC-2")["definition"]
    s1 = definition["feeds"]["S1"]
    assert [s1["flows"][c] for c in fx.COMPONENTS] == [float(v) for v in feed["n_mol_per_s"]]
    assert (s1["T"], s1["P"]) == (float(feed["T_K"]), float(feed["P_Pa"]))
    assert (definition["flash_T"], definition["flash_P"]) == (370.0, 1.5e5)
    assert SETTINGS["PC-2"]["fixture_ours"] == "SYN-001-T06-PC2"


def test_the_pc2_fixture_is_ref04_with_the_three_registered_changes() -> None:
    ref04 = load_yaml(REPO_ROOT / "benchmarks" / "t06" / "cases" / "SYN-001-T06-REF04.yaml")
    pc2 = load_yaml(REPO_ROOT / "benchmarks" / "t06" / "cases" / "SYN-001-T06-PC2.yaml")
    expected = copy.deepcopy(ref04["specifications"])
    for spec in expected:
        spec["value"] = {"SPEC-S1-P": 1.5e5, "SPEC-flash-P": 1.5e5, "SPEC-flash-T": 370.0}.get(
            spec["id"], spec["value"]
        )
    assert pc2["specifications"] == expected
    assert pc2["component_set"] == ref04["component_set"]
    assert pc2["instances"] == ref04["instances"]

    def wiring(document: dict[str, Any]) -> list[dict[str, Any]]:
        return [{k: v for k, v in c.items() if k != "notes"} for c in document["connections"]]

    assert wiring(pc2) == wiring(ref04)


# -- A51: the positive controls --------------------------------------------------------------------


def test_a51_the_positive_controls_disagree(table: dict[str, Any]) -> None:
    by = rows(table)
    assert by["PC-1", "DWSIM"]["classification"] == "DISAGREE"
    assert by["PC-2", "DWSIM"]["classification"] == "DISAGREE"
    assert by["PC-2", "IDAES"]["classification"] == "DISAGREE"
    assert by["PC-1", "IDAES"]["classification"] == "not_applicable"
    assert SETTINGS["PC-1"]["IDAES"] == "not_applicable"
    assert table["positive_controls"]["all_as_required"] is True


def test_a51_each_control_moves_its_quantity_by_the_predicted_effect(table: dict[str, Any]) -> None:
    """The tool's shift from the twin is the twin's predicted effect, to within the tolerance:
    the controls see the effect they exist to see, and nothing else."""
    by = rows(table)
    pc1 = TWIN["positive_controls"]["PC-1"]
    (row,) = by["PC-1", "DWSIM"]["quantities"]
    shift = Decimal(repr(row["tool"])) - Decimal(row["twin"])
    assert abs(shift - Decimal(pc1["effect_W"])) <= Decimal(pc1["tolerance_W"])
    pc2 = TWIN["positive_controls"]["PC-2"]
    for tool in comparison.TOOLS:
        for q in by["PC-2", tool]["quantities"]:
            i = fx.COMPONENTS.index(q["quantity"][-1])
            predicted = Decimal(pc2["no_poynting_vapor_mol_per_s"][i])
            assert abs(Decimal(repr(q["tool"])) - predicted) <= Decimal(q["tolerance"]), (tool, q)
        worst = by["PC-2", tool]
        assert worst["worst_quantity"] == pc2["worst_quantity"]


# -- A52: blindness --------------------------------------------------------------------------------

_TOOL_SIDE = (
    "t06_fixtures.py",
    "t06_qualify_idaes.py",
    "t06_qualify_dwsim.py",
    "idaes_representability.py",
    "dwsim_representability.py",
    "dwsim_runtime.py",
)


@pytest.mark.parametrize("name", _TOOL_SIDE)
def test_a52_the_tool_scripts_read_neither_our_results_nor_the_twin(name: str) -> None:
    source = (REPO_ROOT / "spikes" / "references" / name).read_text(encoding="utf-8")
    imported = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imported |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert not imported & {"openflowsheet", "benchmarks", "t06_reference", "t05_reference"}
    for forbidden in ("reference_values", "ours-", "comparison.json", "corpus_cases"):
        assert forbidden not in source, forbidden


# -- A53, A54: counts and reasons ------------------------------------------------------------------


def test_a53_v16_counts_are_computed_from_the_classifications(table: dict[str, Any]) -> None:
    by = rows(table)
    compared = {"AGREE", "DISAGREE"}
    one = [
        f
        for f in comparison.REF_FIXTURES
        if any(by[f, t]["classification"] in compared for t in comparison.TOOLS)
    ]
    both = [
        f
        for f in comparison.REF_FIXTURES
        if all(by[f, t]["classification"] in compared for t in comparison.TOOLS)
    ]
    counts = table["v16_counts"]
    assert counts["at_least_one"] == one and counts["both"] == both
    assert counts["fixtures_compared_by_at_least_one_tool"] == len(one)
    assert counts["fixtures_compared_by_both_tools"] == len(both)
    assert counts["of"] == 8


def test_a54_every_classification_carries_its_reason(table: dict[str, Any]) -> None:
    assert len(table["rows"]) == len(TOOL_RECORDS)
    for row in table["rows"]:
        assert row["reason"], row["label"]
        assert row["classification"] in {"AGREE", "DISAGREE", "NOT_COMPARABLE", "not_applicable"}
        if row["classification"] == "NOT_COMPARABLE":
            assert row["category"] in {
                "access",
                "reference_accuracy",
                "semantics",
                "ours_not_verified",
            }
        if row["classification"] in {"AGREE", "DISAGREE"}:
            within = [q["within_tolerance"] for q in row["quantities"]]
            assert (row["classification"] == "AGREE") is all(within)


# -- the rules, on mutated copies of the committed records -----------------------------------------


def _mutated(tmp_path: Path, name: str, change: Any) -> dict[tuple[str, str], dict[str, Any]]:
    for path in RESULTS.glob("*.json"):
        (tmp_path / path.name).write_bytes(path.read_bytes())
    target = tmp_path / name
    document = load(target)
    change(document)
    target.write_text(json.dumps(document), encoding="utf-8")
    return rows(comparison.compute(results=tmp_path))


def _fingerprint(document: dict[str, Any]) -> None:
    document["environment_fingerprint"]["measured"]["ipopt_sha256"] = "0" * 64


def _acceptable_level(document: dict[str, Any]) -> None:
    document["ipopt"]["exit"] = "Solved To Acceptable Level."


def _balance(document: dict[str, Any]) -> None:
    document["self_check"]["rule2_component_balance"]["residual_mol_per_s"]["B"] = 3.2e-8


def _recycle(document: dict[str, Any]) -> None:
    document["raw_output"]["units"]["REC"]["IterationsTaken"] = 1000


def _unverified(document: dict[str, Any]) -> None:
    document["verification_status"] = "UNVERIFIED"


def _default_eps_1(document: dict[str, Any]) -> None:
    """IDAES's default eps_1 on one state block, every number unchanged."""
    name = "fs.unit.control_volume.properties_out[0.0].eps_1_Vap_Liq"
    document["raw_output"]["smooth_vle_parameters"][name] = 0.01


def _acceptable_level_and_default_eps(document: dict[str, Any]) -> None:
    _acceptable_level(document)
    _default_eps_1(document)


@pytest.mark.parametrize(
    ("name", "change", "row", "category", "rule"),
    [
        ("idaes-REF-01.json", _fingerprint, ("REF-01", "IDAES"), "access", 1),
        ("idaes-REF-06.json", _acceptable_level, ("REF-06", "IDAES"), "reference_accuracy", 2),
        ("idaes-REF-03.json", _default_eps_1, ("REF-03", "IDAES"), "semantics", "2b"),
        (
            "idaes-REF-04.json",
            _acceptable_level_and_default_eps,
            ("REF-04", "IDAES"),
            "reference_accuracy",
            2,
        ),
        ("dwsim-REF-02.json", _balance, ("REF-02", "DWSIM"), "reference_accuracy", 2),
        ("dwsim-REF-08.json", _recycle, ("REF-08", "DWSIM"), "reference_accuracy", 2),
        ("dwsim-PC-1.json", _balance, ("REF-04", "DWSIM"), "reference_accuracy", 2),
        ("ours-REF-05.json", _unverified, ("REF-05", "DWSIM"), "ours_not_verified", 3),
    ],
)
def test_the_rules_fire_in_order_on_mutated_records(
    tmp_path: Path,
    name: str,
    change: Any,
    row: tuple[str, str],
    category: str,
    rule: int | str,
) -> None:
    by = _mutated(tmp_path, name, change)
    assert by[row]["classification"] == "NOT_COMPARABLE"
    assert (by[row]["category"], by[row]["rule"]) == (category, rule)


@pytest.mark.parametrize(("shift", "expected"), [(1e-4, "AGREE"), (1e-3, "DISAGREE")])
def test_rule4_decides_on_the_tolerance(tmp_path: Path, shift: float, expected: str) -> None:
    """Our REF-01 `S3.T` moved by 1e-4 K stays inside its 3.3e-4 K tolerance against both tools;
    moved by 1e-3 K it is outside against both."""

    def change(document: dict[str, Any]) -> None:
        document["compared_quantities"]["S3.T"] += shift

    by = _mutated(tmp_path, "ours-REF-01.json", change)
    for tool in comparison.TOOLS:
        assert by["REF-01", tool]["classification"] == expected
        if expected == "DISAGREE":
            assert by["REF-01", tool]["worst_quantity"] == "S3.T"


# -- A83: IDAES's SmoothVLE smoothing (spec §9.3, §9.5 rule 2b, Amendment 2) -----------------------

IDAES_RAN = [f for f in comparison.FIXTURES if f != "PC-1"]
SMOOTH_VLE = SETTINGS["IDAES"]["smooth_vle"]
EPS = {which: Decimal(str(SMOOTH_VLE[f"{which}_K"])) for which in ("eps_1", "eps_2")}
BOUND = Decimal(TWIN["smooth_vle"]["self_check_bound_K"])


def test_a83_the_registered_smoothing_is_the_tool_script_input() -> None:
    assert EPS == {"eps_1": Decimal("1e-8"), "eps_2": Decimal("1e-8")}
    assert [Decimal(v) for v in TWIN["smooth_vle"]["registered_eps_K"]] == list(EPS.values())
    assert BOUND == Decimal("1e-7") == Decimal(fx.RULE2B_SHIFT_BOUND_K)
    assert {k: Decimal(repr(v)) for k, v in fx.IDAES_SMOOTH_VLE_EPS_K.items()} == EPS


@pytest.mark.parametrize("fixture", IDAES_RAN)
def test_a83_every_smooth_vle_block_carries_the_registered_eps(fixture: str) -> None:
    """Every state block with SmoothVLE's `_teq` in the record's variables carries eps_1 = eps_2 =
    1e-8 K as the model held them after the solve, and the script set them on exactly those."""
    rec = record("IDAES", fixture)
    assert {k: Decimal(repr(v)) for k, v in rec["settings"]["smooth_vle_eps_K"].items()} == EPS
    shift = fx.smooth_vle_shift(
        rec["raw_output"]["variables"], rec["raw_output"]["smooth_vle_parameters"]
    )
    assert shift["blocks"]
    assert sorted(rec["smooth_vle_eps_set_on"]) == sorted(shift["blocks"])
    for block, entry in shift["blocks"].items():
        for which, value in EPS.items():
            assert Decimal(repr(entry[f"{which}_K"])) == value, (block, which)
    parameters = rec["raw_output"]["smooth_vle_parameters"]
    assert len(parameters) == 2 * len(shift["blocks"])


@pytest.mark.parametrize("fixture", IDAES_RAN)
def test_a83_rule_2b_recomputed_from_each_record_is_within_the_bound(
    fixture: str, table: dict[str, Any]
) -> None:
    rec = record("IDAES", fixture)
    shift = fx.smooth_vle_shift(
        rec["raw_output"]["variables"], rec["raw_output"]["smooth_vle_parameters"]
    )
    worst = shift["max_shift_K"]
    assert worst is not None and worst <= BOUND
    # The registered eps bounds the shift by (eps_1 + eps_2)/2 = 1e-8 K (spec §9.3 (A2)).
    assert worst <= (EPS["eps_1"] + EPS["eps_2"]) / 2
    tool_side = rec["self_check"]["rule2b_smooth_vle"]
    assert tool_side["passes"] is True
    assert tool_side["max_shift_K"] == float(worst)
    row = rows(table)[fixture, "IDAES"]
    assert row["smooth_vle"]["max_shift_K"] == float(worst)
    assert row["smooth_vle"]["blocks_without_the_registered_eps"] == []
    assert row["category"] != "semantics"


def test_a83_rule_2b_on_a_saturated_stream_is_eps1_over_2() -> None:
    """REF-08's recycle is a flash liquid at its bubble point: the shift is eps_1/2 there
    (spec §9.3 (A2)), 5e-9 K, to within the tool's convergence."""
    rec = record("IDAES", "REF-08")
    shift = fx.smooth_vle_shift(
        rec["raw_output"]["variables"], rec["raw_output"]["smooth_vle_parameters"]
    )
    assert shift["max_shift_K"] is not None
    assert abs(shift["max_shift_K"] - EPS["eps_1"] / 2) <= Decimal("1e-10")


RETAINED = [*comparison.REF_FIXTURES, "PC-2"]


def test_a83_the_default_eps_records_are_retained(table: dict[str, Any]) -> None:
    superseded = table["superseded_default_eps"]["rows"]
    assert [r["fixture"] for r in superseded] == RETAINED
    for row in superseded:
        rec = load(RESULTS / f"{comparison.DEFAULT_EPS_PREFIX}{row['fixture']}.json")
        assert row["record"] == f"references/results/idaes-default-eps-{row['fixture']}.json"
        # Run at IDAES's defaults: the W8 records carry no eps, so rule 2b's second clause fires
        # too; the shift alone already exceeds the bound on every one.
        assert "smooth_vle_parameters" not in rec["raw_output"]
        assert "smooth_vle_eps_K" not in rec["settings"]
        assert (row["classification"], row["category"], row["rule"]) == (
            "NOT_COMPARABLE",
            "semantics",
            "2b",
        )
        assert row["label"] == f"NOT_COMPARABLE(semantics: {row['reason']})"
        assert re.fullmatch(r"smooth_vle_shift\(\d\.\d{3}e-\d\d K\)", row["reason"])
        assert Decimal(repr(row["smooth_vle"]["max_shift_K"])) > BOUND
        assert row["smooth_vle"]["blocks_without_the_registered_eps"]
    by = {r["fixture"]: r for r in superseded}
    assert f"{by['REF-08']['smooth_vle']['max_shift_K']:.1e}" == "5.0e-03"
    assert f"{by['REF-03']['smooth_vle']['max_shift_K']:.1e}" == "9.8e-06"


def test_a83_the_default_eps_records_keep_the_table_they_produced(table: dict[str, Any]) -> None:
    """W8's table: REF-03 (1.36) and REF-08 (302) DISAGREE in IDAES, PC-2 DISAGREE (4 581)."""
    before = {r["fixture"]: r["without_rule_2b"] for r in table["superseded_default_eps"]["rows"]}
    disagree = sorted(f for f, r in before.items() if r["classification"] == "DISAGREE")
    assert disagree == ["PC-2", "REF-03", "REF-08"]
    assert all(before[f]["classification"] == "AGREE" for f in RETAINED if f not in disagree)
    assert f"{before['REF-03']['worst_ratio']:.3g}" == "1.36"
    assert f"{before['REF-08']['worst_ratio']:.3g}" == "302"
    assert "smooth_vle" not in before["REF-08"]


def test_a83_no_committed_row_counts_a_default_eps_record(table: dict[str, Any]) -> None:
    by = rows(table)
    for fixture in IDAES_RAN:
        assert "smooth_vle" in by[fixture, "IDAES"]
    assert table["rule2b"] == {
        "registered_eps_K": {k: str(v) for k, v in EPS.items()},
        "shift_bound_K": str(BOUND),
    }


@pytest.mark.parametrize(
    ("offset", "expected"), [(Decimal("5e-8"), "AGREE"), (Decimal("2e-7"), "NOT_COMPARABLE")]
)
def test_rule_2b_decides_on_the_bound(tmp_path: Path, offset: Decimal, expected: str) -> None:
    """REF-08's recycle `_teq` moved up by 5e-8 K stays within rule 2b's 1e-7 K (5.5e-8 K in all);
    moved by 2e-7 K it is outside, and the fixture is not comparable in IDAES."""
    name = "fs.mix.recycle_state[0.0]._teq[Vap,Liq]"

    def change(document: dict[str, Any]) -> None:
        document["raw_output"]["variables"][name] += float(offset)

    by = _mutated(tmp_path, "idaes-REF-08.json", change)
    row = by["REF-08", "IDAES"]
    assert row["classification"] == expected
    if expected == "NOT_COMPARABLE":
        assert (row["category"], row["rule"]) == ("semantics", "2b")
        assert row["smooth_vle"]["argmax"] == "fs.mix.recycle_state[0.0][Vap,Liq]"
    assert by["REF-08", "DWSIM"]["classification"] == "AGREE"


def test_rule_2b_needs_the_eps_on_every_block(tmp_path: Path) -> None:
    def change(document: dict[str, Any]) -> None:
        del document["raw_output"]["smooth_vle_parameters"][
            "fs.unit.control_volume.properties_in[0.0].eps_2_Vap_Liq"
        ]

    row = _mutated(tmp_path, "idaes-PC-2.json", change)["PC-2", "IDAES"]
    assert (row["category"], row["rule"]) == ("semantics", "2b")
    assert row["smooth_vle"]["blocks_without_the_registered_eps"] == [
        "fs.unit.control_volume.properties_in[0.0][Vap,Liq]"
    ]
