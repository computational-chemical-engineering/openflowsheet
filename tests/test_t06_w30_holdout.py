"""T06 W30: the holdout's starts, before any holdout solve (A99 (a); A22–A24, A85 (a)–(b) over it).

Spec `docs/derivations/T06-corpus-spec.md` §7.6 (A5), A99; register R-089. `holdout1` is the
frozen generator's own output at start indices 20…39 (`generator.generate_start`), committed alone
as `benchmarks/t06/ensemble/starts-nominal-holdout1.json` with the registry's `ensemble.holdout`.
The nominal law is unchanged, so every case's coordinates, boxes, `x_init` and held-zero columns
equal the nominal file's, which A22's rule checks (`test_t06_w6_generator`); what differs is the
start index, hence the keys. Each start is recomputed here from its recorded `u` and key (A80's
rule), its split columns from its own stream columns (A85 (b)), and the file regenerates byte for
byte on `ref-x86-64` (A25's rule). A85 (a)'s margins are reported, never a stop: a holdout start
inside the degeneracy window is scored as generated, not re-drawn.
"""

from __future__ import annotations

import hashlib
import json
import math
from functools import cache
from typing import Any

import pytest
from conftest import REPO_ROOT, load_yaml
from t06_ensemble_support import HOLDOUT_FILE, ensemble_cases
from t08_rename_substitution import renamed_back_sha256, renamed_back_starts
from test_t06_w6_a85 import REVISION_CASES, _binding, _same, _splits, _stream
from test_t06_w6_generator import PUBLISHED

from benchmarks.t06 import ensemble, generator
from openflowsheet.canonical import canonical_json
from openflowsheet.models.syn001 import TEMPERATURE_TOLERANCE
from openflowsheet.models.syn001.saturation_band import degeneracy_distance
from openflowsheet.models.syn001.tp_state import tp_state
from openflowsheet.run.compare import differences

REGISTRY: dict[str, Any] = load_yaml(REPO_ROOT / "benchmarks" / "registry.yaml")
ENTRY: dict[str, Any] = REGISTRY["ensemble"]["holdout"]
HOLDOUT_BYTES = HOLDOUT_FILE.read_bytes()
HOLDOUT: dict[str, Any] = json.loads(HOLDOUT_BYTES)
BY_CASE = {entry["case"]: entry for entry in HOLDOUT["cases"]}
NOMINAL = {entry["case"]: entry for entry in PUBLISHED["cases"]}
CASES = {case.case: case for case in ensemble_cases()}
INDICES = list(range(20, 40))


def test_a99a_the_file_is_the_registered_one() -> None:
    assert hashlib.sha256(HOLDOUT_BYTES).hexdigest() == ENTRY["starts_sha256"]
    assert canonical_json(HOLDOUT) == HOLDOUT_BYTES
    assert ENTRY["starts_file"] == str(HOLDOUT_FILE.relative_to(REPO_ROOT))
    assert ENTRY["run_id"] == ensemble.HOLDOUT_RUN_ID == "holdout1"
    assert (ENTRY["start_indices"]["first"], ENTRY["start_indices"]["last"]) == (20, 39)
    assert list(ensemble.HOLDOUT_INDICES) == INDICES
    assert ENTRY["gated"] is False
    counts = HOLDOUT["counts"]
    assert {key: counts[key] for key in ENTRY["counts"]} == ENTRY["counts"]


def test_a99a_the_generator_provider_and_law_are_the_nominal_files() -> None:
    for field in ("format", "rng", "key_prefix", "profile", "key", "arithmetic", "caps"):
        assert HOLDOUT[field] == PUBLISHED[field], field
    assert HOLDOUT["generator"] == PUBLISHED["generator"] == "benchmarks/t06/generator.py"
    assert HOLDOUT["generator_sha256"] == PUBLISHED["generator_sha256"]
    # Generated before the rename: the generator's bytes with the old package name (R-149).
    assert HOLDOUT["generator_sha256"] == renamed_back_sha256(REPO_ROOT / HOLDOUT["generator"])
    assert HOLDOUT["provider"] == PUBLISHED["provider"]
    assert HOLDOUT["host"]["machine_class"] == ensemble.REFERENCE_CLASS


def test_a99a_the_cases_are_the_nominal_files_in_its_order_with_the_same_law() -> None:
    """A22 over the holdout: the law's per-case inputs equal the nominal file's (A22 checks those
    against the rule); the policy is each case's current registered one (§7.6 (A5))."""
    assert list(BY_CASE) == list(NOMINAL) == REGISTRY["ensemble"]["cases"]
    for case_id, entry in BY_CASE.items():
        nominal = NOMINAL[case_id]
        for field in ("fixture", "path", "initializer", "x_init", "coordinates", "held_zero"):
            assert entry[field] == nominal[field], (case_id, field)
        assert entry["policy"] == REGISTRY["ensemble"]["policies"][entry["path"]]
        assert entry["policy"] == CASES[case_id].policy.policy_id


def test_a99a_indices_20_to_39_and_keys_disjoint_from_the_gates() -> None:
    nominal_prefixes = {s["key_prefix"] for e in PUBLISHED["cases"] for s in e["starts"]}
    holdout_prefixes = set()
    for case_id, entry in BY_CASE.items():
        drawn = [s["start"] for s in entry["starts"]]
        failed = [f["start"] for f in entry["generation_failures"]]
        assert sorted(drawn + failed) == INDICES, case_id
        for start in entry["starts"]:
            prefix = f"T06-ens-v1|nominal|{entry['fixture']}|{start['start']:02d}"
            assert start["key_prefix"] == prefix
            holdout_prefixes.add(prefix)
    assert len(holdout_prefixes) == HOLDOUT["counts"]["starts_accepted"]
    assert not holdout_prefixes & nominal_prefixes
    # Every gate key has start field 00…19 and no field contains `|` (A21), so no holdout key —
    # start field 20…39 — can equal one.
    assert all(int(p.rsplit("|", 1)[1]) < 20 for p in nominal_prefixes)


def test_a26_the_holdouts_counts_recompute_from_its_records() -> None:
    accepted = coordinate = joint = failures = 0
    for entry in HOLDOUT["cases"]:
        failures += len(entry["generation_failures"])
        for start in entry["starts"]:
            accepted += 1
            coordinate += sum(len(draw["rejected"]) for draw in start["draws"])
            coordinate += sum(r["coordinate_rejections"] for r in start["joint_rejections"])
            joint += len(start["joint_rejections"])
            assert start["joint_attempts"] == len(start["joint_rejections"]) + 1
    counts = HOLDOUT["counts"]
    assert (counts["starts_accepted"], counts["generation_failures"]) == (accepted, failures)
    assert (counts["coordinate_rejections"], counts["joint_rejections"]) == (coordinate, joint)
    assert counts["cases"] == 22


@pytest.mark.parametrize("case_id", sorted(BY_CASE))
def test_a23_a80_every_holdout_start_is_its_draws_recomputed_bit_for_bit(case_id: str) -> None:
    """A80's rule at indices 20…39: each selected coordinate is `x_init + S*δ` from its recorded
    `u`, whose key is its accepted attempt's; each earlier attempt fell outside the box on the
    recorded side; every accepted value is in its box (A23); no other column moved."""
    entry = BY_CASE[case_id]
    coordinates = {c["id"]: c for c in entry["coordinates"]}
    for start in entry["starts"]:
        joint = start["joint_attempts"] - 1
        assert [draw["coordinate"] for draw in start["draws"]] == list(coordinates)
        for draw in start["draws"]:
            coordinate = coordinates[draw["coordinate"]]
            low = -math.inf if coordinate["lower"] is None else float(coordinate["lower"])
            high = math.inf if coordinate["upper"] is None else float(coordinate["upper"])
            x_init = float(entry["x_init"][draw["coordinate"]])
            scale = float(coordinate["scale"])
            for attempt, side in enumerate(draw["rejected"]):
                key = generator.draw_key(
                    entry["fixture"], start["start"], joint, draw["coordinate"], attempt
                )
                value = x_init + scale * ((2.0 * generator.uniform(key) - 1.0) / 5.0)
                assert (value < low) if side == "below" else (value > high)
            key = generator.draw_key(
                entry["fixture"], start["start"], joint, draw["coordinate"], draw["attempt"]
            )
            assert key.startswith(start["key_prefix"] + "|")
            u = float(draw["u"])
            assert u == generator.k53(key) * 2.0**-53
            value = x_init + scale * ((2.0 * u - 1.0) / 5.0)
            recorded = float(start["vector"][draw["coordinate"]])
            assert value.hex() == recorded.hex() or value == 0.0 == recorded, draw
            assert low <= recorded <= high
        for column, value in start["vector"].items():
            parts = column.split(".")
            lifted = parts[1] in ("vap", "liq") or parts[-1] in ("V", "L", "N")
            if column in coordinates or column in entry["held_zero"] or lifted:
                continue
            assert float(value) == float(entry["x_init"][column]), (case_id, column)


@cache
def _regenerated() -> dict[str, Any]:
    """`generate --holdout`'s document, regenerated in memory (A24 checks the sign of each held
    zero here, because canonical JSON spells ±0.0 alike)."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "t06_ensemble_script", REPO_ROOT / "scripts" / "t06_ensemble.py"
    )
    assert spec is not None and spec.loader is not None
    script = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(script)
    document: dict[str, Any] = script._generate(holdout=True)
    return document


def test_a24_absent_components_are_held_at_positive_zero_in_the_holdout() -> None:
    for entry in _regenerated()["cases"]:
        for start in entry["starts"]:
            for column in entry["held_zero"]:
                value = start["vector"][column]
                assert value == 0.0 and math.copysign(1.0, value) > 0.0, (entry["case"], column)
    for entry in HOLDOUT["cases"]:
        for start in entry["starts"]:
            assert all(start["vector"][column] == 0 for column in entry["held_zero"])


def test_a99a_the_holdout_regenerates_byte_for_byte_on_the_reference_machine_class() -> None:
    """A25's rule (`check --holdout`): bytes on the generating host; elsewhere reported. The two
    self-hashes are compared as before the rename (R-149)."""
    regenerated = renamed_back_starts(_regenerated())
    if regenerated["host"] == HOLDOUT["host"]:
        assert canonical_json(regenerated) == HOLDOUT_BYTES
    else:
        found = differences(regenerated, HOLDOUT, policy_id="K04-numerical-policy-v1")
        print(f"A99 (a) on {regenerated['host']}: {len(found)} differences from the holdout")
        for line in found[:20]:
            print("  " + line)


@pytest.mark.parametrize("case_id", REVISION_CASES)
def test_a85a_the_holdouts_margins_are_reported(case_id: str) -> None:
    """A85 (a) over the holdout, reported and never a stop (§7.6 (A5)): the smallest degeneracy
    distance over its heater-style splits, printed; a start inside the window is scored as
    generated. *Measured (W30, `ref-x86-64`):* 0.3 K on THM-08 (start 25, the valve), 1.99 K on
    THM-09 (start 24), ≥ 9.93 K on every other case; every such stream flowing — no violation."""
    flowsheet = _binding(case_id).flowsheet
    smallest: tuple[float, int, str, float] | None = None
    for split, style in _splits(case_id):
        if style != "outlet":
            continue
        for start in BY_CASE[case_id]["starts"]:
            stream = _stream(case_id, split, start["vector"])
            distance = degeneracy_distance(
                flowsheet.provider, stream.n, stream.temperature, stream.pressure, flowsheet.context
            )
            if smallest is None or distance < smallest[0]:
                smallest = (distance, start["start"], split.unit, sum(stream.n))
    if smallest is not None:
        inside = smallest[0] <= TEMPERATURE_TOLERANCE or smallest[3] <= 0.0
        print(
            f"A85 (a) holdout {case_id}: {smallest[0]:.3g} K at start {smallest[1]:02d} "
            f"({smallest[2]}), flow {smallest[3]:.3g} mol/s"
            + (" — INSIDE the window or dormant: reported, not re-drawn" if inside else "")
        )


@pytest.mark.parametrize("case_id", REVISION_CASES)
def test_a85b_every_holdout_split_column_is_the_rule_applied_to_its_stream(case_id: str) -> None:
    """A85 (b)'s rule, without `lifted_split_values`: heater style, `tp_state` of the start's own
    `(n, T, P)` (status `ok`); products style, the sums of the product streams' recorded flows."""
    flowsheet = _binding(case_id).flowsheet
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
