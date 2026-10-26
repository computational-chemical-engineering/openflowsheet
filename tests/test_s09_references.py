"""S09 WO-S09-3: BioSTEAM's column reference comparison, gated on the committed records (§6-§8).

Authority: `docs/derivations/S09-spec.md` §11's A01, A02, A04 (the records' half), A05 and A09-A18
and A20, as amended by §18.5. The gate never runs BioSTEAM (§10): it reads the committed tool
records, the qualification record, S03's committed our-side records, `s03_reference.json` and S03's
`comparison.json` and recomputes the document with `scripts/s09_reference_comparison.py`. From the
committed files the document must equal `benchmarks/s09/references/comparison.json` byte for byte;
from a live solve of our side its classifications must equal it exactly (A13). A03 and A06-A08 are
WO-S09-2's tool-free checks of the harness and its records, in `tests/test_s09_qualification.py`.

The expectations are independent of both sides: `s03_reference.json`'s 25-digit twin values and the
PC-LI tool model, `s09_cases.json`'s thresholds, readback values and pre-registered X31 outcomes,
and the fingerprint of `docs/reference-environments.md` §9. A02 and A16 read git history and refuse
explicitly without it (R-555's pattern). Mutations are at 2x and 0.5x of each threshold (A09-A11).
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
import subprocess
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from conftest import REPO_ROOT

sys.path.insert(0, str(REPO_ROOT / "scripts"))

import s03_references_ours as ours_side  # noqa: E402
import s09_reference_comparison as c9  # noqa: E402

s03 = c9.s03
CASES9 = json.loads(c9.CASES9_PATH.read_text(encoding="utf-8"))
CASES3 = json.loads(c9.CASES3_PATH.read_text(encoding="utf-8"))
REF = json.loads(c9.TWIN_PATH.read_text(encoding="utf-8"))
CMP3 = json.loads(c9.CMP3_PATH.read_text(encoding="utf-8"))
PAIRS = tuple(CASES9["pairs"])
GENERATOR9 = REPO_ROOT / "docs" / "derivations" / "scripts" / "s09_reference.py"
#: A01 (§18.5): the claim count and `s09_cases.json`'s SHA-256 after Amendment 1.
CLAIMS = 181
CASES9_SHA256 = "760ab27f88a4f16320dd66da2218b815d60bff2e8752ec3b5601fa42d29a813c"
#: A02: S03 as merged (`main` at `390e0af5`).
S03_BASE = "390e0af5"
S03_PATHS = (
    "benchmarks/s03/references",
    "docs/derivations/scripts/s03_cases.json",
    "docs/derivations/scripts/s03_reference.json",
    "scripts/s03_reference_comparison.py",
)
QUAL = c9.QUALIFICATION / "biosteam.json"
HISTORY = "S09 A02 and A16 need the repository's history (a full clone; R-555's pattern)"


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True, text=True)


def require_history(*commits: str) -> None:
    shallow = git("rev-parse", "--is-shallow-repository").stdout.strip()
    missing = [c for c in commits if git("cat-file", "-e", f"{c}^{{commit}}").returncode != 0]
    if shallow != "false" or missing:
        pytest.fail(f"{HISTORY}: shallow={shallow}, missing {missing}")


@pytest.fixture(scope="module")
def table() -> dict[str, Any]:
    return load(c9.TABLE)


@pytest.fixture(scope="module")
def records() -> dict[str, Any]:
    return c9.load_records(CASES9)


@pytest.fixture(scope="module")
def ours() -> dict[str, Any]:
    return c9.load_ours(CASES9, CASES3)


def rows(document: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {r["case"]: r for r in document["rows"]}


def selected_rung(record: dict[str, Any]) -> dict[str, Any]:
    level = record["levels"][record["level"]]
    return next(r for r in level["rungs"] if r["rung"] == record["selected_rung"])


def selected_run(record: dict[str, Any]) -> dict[str, Any]:
    return dict(selected_rung(record)["run"])


def classify(cid: str, record: dict[str, Any], ours: dict[str, Any]) -> dict[str, Any]:
    return c9.classify(cid, record, ours[cid], CASES3, CASES9, REF)


def case_of(cid: str) -> dict[str, Any]:
    return dict(CASES3["cases"][c9.inputs_case(cid, CASES9)])


def tol(cid: str, q: str) -> float:
    twin = s03.twin_quantities(REF, c9.twin_case(cid, CASES9))
    return float(s03.tolerance(dict(case_of(cid)["quantities"])[q], Decimal(twin[q]["value"])))


def shift_product(run: dict[str, Any], component: str, delta: float, case: dict[str, Any]) -> None:
    """Move `delta` mol/s of one component from the bottom product to the top product (so that the
    overall balance, the stage balances and every specification stay unchanged)."""
    products = run["profile"]["products"]
    top = products[2] if case["condenser"] == "total" else products[0]
    top["mol_per_s"][component] += delta
    products[1]["mol_per_s"][component] -= delta


# -- A01, A02 --------------------------------------------------------------------------------------


def test_a01_the_generator_checks_and_the_cases_file_is_amendment_1s() -> None:
    """A01 (§18.5): `s09_reference.py --check` re-derives 181 claims and byte-compares
    `s09_cases.json` (SHA-256 `760ab27f…a813c`); S03's three pins hold."""
    done = subprocess.run(
        [sys.executable, str(GENERATOR9), "--check"], capture_output=True, text=True, cwd=REPO_ROOT
    )
    assert done.returncode == 0, done.stdout + done.stderr
    assert CASES9["claim_count"] == CLAIMS == len(CASES9["claims"])
    assert hashlib.sha256(c9.CASES9_PATH.read_bytes()).hexdigest() == CASES9_SHA256
    assert c9.verify_s03_pins(CASES9) == CASES9["s03_pins"]


def test_a02_s03_is_untouched_since_its_merge() -> None:
    """A02: S03's cases, twin, comparison, SHA256SUMS, every file under `benchmarks/s03/references/`
    and S03's classifier are byte-identical to `main` at `390e0af5`; `s03_reference.py --check`
    passes; the S09 classifier writes only under `benchmarks/s09/references/`."""
    require_history(S03_BASE)
    diff = git("diff", "--name-only", S03_BASE, "--", *S03_PATHS)
    assert diff.returncode == 0 and diff.stdout == "", diff.stdout
    untracked = git("status", "--porcelain", "--", *S03_PATHS)
    assert untracked.stdout == "", untracked.stdout
    generator = REPO_ROOT / "docs" / "derivations" / "scripts" / "s03_reference.py"
    done = subprocess.run([sys.executable, str(generator), "--check"], capture_output=True)
    assert done.returncode == 0, done.stdout
    for written in (c9.TABLE, c9.SUMS):
        assert written.is_relative_to(c9.REFERENCES)
        assert not written.is_relative_to(s03.REFERENCES)


# -- A04 (the records' half), A05 ------------------------------------------------------------------


@pytest.mark.parametrize("cid", PAIRS)
def test_a04_every_record_carries_section_9s_fingerprint(cid: str, records: dict) -> None:
    """A04: every record's pip-freeze fingerprint equals `docs/reference-environments.md` §9's and
    its versions S09 §2.1's (rule 1 recomputed)."""
    assert c9.documented_fingerprint() == load(QUAL)["environment_fingerprint"]["pip_freeze_sha256"]
    assert c9.rule1(records[cid], CASES9) is None


@pytest.mark.parametrize("cid", PAIRS)
def test_a05_every_record_passes_the_property_readback(cid: str, records: dict) -> None:
    """A05: §4.3's readback in every record within its thresholds, against `s09_cases.json`."""
    assert c9.property_readback(records[cid], cid, CASES9) is None


@pytest.mark.parametrize(
    ("item", "factor", "fires"),
    [("Psat", 1e-12, True), ("Psat", 1e-15, False), ("latent", 1e-9, True)],
)
def test_a05_the_readback_fires_at_its_thresholds(
    item: str, factor: float, fires: bool, records: dict, ours: dict
) -> None:
    """A05: `Psat` moved by 1e-12 relative → rule 2c `property_mapping`; by 1e-15 → not fired;
    `h^V − h^L` moved by 1e-9 relative to `Hvap` → rule 2c."""
    record = copy.deepcopy(records["RC1"])
    items = record["property_package"]["readback"]["items"]
    if item == "Psat":
        row = items["Psat"]["values"]["B"][1]
        row["tool"] *= 1 + factor
    else:
        row = items["latent"]["values"]["B"][1]
        row["hV_minus_hL_minus_Hvap"] += factor * items["latent"]["Hvap_J_per_mol"]["B"]
    got = classify("RC1", record, ours)
    if fires:
        assert (got["rule"], got["reason"]) == ("2c", f"property_mapping({item})"), got["label"]
    else:
        assert got["classification"] == "AGREE", got["label"]


# -- A09: rule 2 -----------------------------------------------------------------------------------


@pytest.mark.parametrize(("delta", "fires"), [(6.2e-8, True), (1.55e-8, False)])
def test_a09_b3_fires_at_twice_its_threshold(
    delta: float, fires: bool, records: dict, ours: dict
) -> None:
    """A09: one stage's component flow +6.2e-8 mol/s → B3; +1.55e-8 → not (rule 4)."""
    record = copy.deepcopy(records["RC1"])
    selected_rung(record)["run"]["profile"]["stages"][3]["out_mol_per_s"][1]["B"] += delta
    got = classify("RC1", record, ours)
    if fires:
        assert got["rule"] == 2 and got["reason"].startswith("B3("), got["label"]
    else:
        assert got["rule"] == 4 and got["classification"] == "AGREE", got["label"]


def test_a09_b3_keeps_a_nan_in_the_first_flow_it_reads(records: dict, ours: dict) -> None:
    """A09 (§19.5, R-752): RC1's selected run with the first stage flow B3 reads (stage 0, first
    inlet, A) set to NaN → B3; a later finite residual must not replace the NaN."""
    assert s03.fx.COMPONENTS[0] == "A"
    record = copy.deepcopy(records["RC1"])
    selected_rung(record)["run"]["profile"]["stages"][0]["in_mol_per_s"][0]["A"] = math.nan
    got = classify("RC1", record, ours)
    assert got["rule"] == 2 and got["reason"].startswith("B3(nan"), got["label"]


@pytest.mark.parametrize(("delta", "fires"), [(2e-8, True), (5e-9, False)])
def test_a09_b4_fires_at_twice_its_threshold(
    delta: float, fires: bool, records: dict, ours: dict
) -> None:
    """A09: one stage's y_c +2e-8 → B4; +5e-9 → not."""
    record = copy.deepcopy(records["RC1"])
    selected_rung(record)["run"]["profile"]["stages"][3]["y"]["A"] += delta
    got = classify("RC1", record, ours)
    if fires:
        assert got["rule"] == 2 and got["reason"].startswith("B4("), got["label"]
    else:
        assert got["rule"] == 4, got["label"]


@pytest.mark.parametrize(("count", "fires"), [(500, True), (499, False)])
def test_a09_b2_on_a_fixed_point_rung_reads_iter(
    count: int, fires: bool, records: dict, ours: dict
) -> None:
    """A09 (§18.5): a pass with `iter == maxiter` → B2; `maxiter − 1` → not fired."""
    record = copy.deepcopy(records["RC1"])
    assert selected_rung(record)["rung"] == "R1"
    selected_rung(record)["run"]["path"]["pass2"]["iter"] = count
    got = classify("RC1", record, ours)
    if fires:
        assert got["rule"] == 2 and got["reason"].startswith("B2("), got["label"]
    else:
        assert got["rule"] == 4, got["label"]


def test_a09_b2_on_r3_reads_fsolves_evaluation_count(records: dict) -> None:
    """A09 (§18.5): a passing run relabelled R3 with `fsolve = {ran: true, nfev: 499, ier: 1}` on
    both passes → B2 not fired; pass 2's `nfev = 500` → B2; pass 2's `ran = false` → B2. On a
    fixed-point rung an `fsolve` block with `nfev = 500` → not fired (B2 reads `iter` there)."""
    case = case_of("RC1")
    r3 = CASES9["tool_settings"]["BioSTEAM"]["rungs"].index(["simultaneous correction", "hybr"])
    assert r3 == 2

    def run_with(pass2: dict[str, Any]) -> dict[str, Any]:
        run = copy.deepcopy(selected_run(records["RC1"]))
        for name in ("pass1", "pass2"):
            run["path"][name]["fsolve"] = {"ran": True, "nfev": 499, "ier": 1, "mesg": "x"}
        run["path"]["pass2"]["fsolve"].update(pass2)
        return run

    assert c9.rule2(run_with({}), r3, case, CASES9)[0] is None
    problem = c9.rule2(run_with({"nfev": 500}), r3, case, CASES9)[0]
    assert problem is not None and problem.startswith("B2(")
    problem = c9.rule2(run_with({"ran": False, "nfev": None}), r3, case, CASES9)[0]
    assert problem is not None and problem.startswith("B2(")
    assert c9.rule2(run_with({"nfev": 500}), 0, case, CASES9)[0] is None


def test_a09_b1_fires_on_an_exception_and_the_unaltered_record_reaches_rule_4(
    records: dict, ours: dict
) -> None:
    """A09: an exception on pass 1 → B1; the unaltered record → rule 4."""
    assert classify("RC1", copy.deepcopy(records["RC1"]), ours)["rule"] == 4
    record = copy.deepcopy(records["RC1"])
    selected_rung(record)["run"]["path"]["pass1"]["exception"] = "RuntimeError: synthetic"
    got = classify("RC1", record, ours)
    assert got["rule"] == 2 and got["reason"].startswith("B1("), got["label"]


# -- A10: rule 2c and 2d ---------------------------------------------------------------------------


def test_a10_a_stored_specification_one_ulp_off_is_a_readback_failure(
    records: dict, ours: dict
) -> None:
    """A10: stored B ≠ 1/RR by one ulp → `specification_readback`."""
    record = copy.deepcopy(records["RC1"])
    rows_ = selected_rung(record)["run"]["rule2c"]["checks"]["specification_readback"]["rows"]
    row = next(r for r in rows_ if r["specification"] == "Reflux")
    row["stored"] = math.nextafter(row["stored"], 1.0)
    got = classify("RC1", record, ours)
    assert got["rule"] == "2c" and got["reason"].startswith("specification_readback("), got


@pytest.mark.parametrize(("delta", "fires"), [(6.2e-8, True), (1.55e-8, False)])
def test_a10_total_condenser_vapour_fires_at_twice_its_threshold(
    delta: float, fires: bool, records: dict, ours: dict
) -> None:
    """A10: total-condenser vapour 6.2e-8 mol/s → fired; 1.55e-8 → not (RC2; the vapour is taken
    from the bottom product, so that rule 2 is unchanged)."""
    record = copy.deepcopy(records["RC2"])
    products = selected_rung(record)["run"]["profile"]["products"]
    products[0]["mol_per_s"]["A"] += delta
    products[1]["mol_per_s"]["A"] -= delta
    got = classify("RC2", record, ours)
    if fires:
        assert got["rule"] == "2c" and got["reason"].startswith("total_condenser_vapour("), got
    else:
        assert got["rule"] == 4, got["label"]


def test_a10_s03_a12s_four_on_biosteams_rc1_record(records: dict, ours: dict) -> None:
    """A10 (S03 A12's four): `L[1]` × (1 + 2e-4) → 2c; × (1 + 2e-8) → 2d; a pressure + 0.01 Pa →
    2c (a product's, which B4 does not read); a rerun quantity moved 0.2 tolerance → 2d."""
    base = records["RC1"]

    def mutated(change: Any) -> dict[str, Any]:
        record = copy.deepcopy(base)
        change(selected_rung(record))
        return classify("RC1", record, ours)

    def l1(factor: float) -> Any:
        return lambda r: r["run"]["profile"]["stages"][0].__setitem__(
            "L_mol_per_s", r["run"]["profile"]["stages"][0]["L_mol_per_s"] * factor
        )

    got = mutated(l1(1 + 2e-4))
    assert got["rule"] == "2c" and got["reason"].startswith("specification_condenser"), got
    got = mutated(l1(1 + 2e-8))
    assert got["rule"] == "2d" and got["reason"].startswith("specification_residual_condenser")

    def pressure(r: dict[str, Any]) -> None:
        r["run"]["profile"]["products"][0]["P_Pa"] += 0.01

    got = mutated(pressure)
    assert got["rule"] == "2c" and got["reason"].startswith("pressure("), got["label"]

    def rerun(r: dict[str, Any]) -> None:
        shift_product(r["accuracy_rerun"]["run"], "C", 0.2 * tol("RC1", "top[C]"), case_of("RC1"))

    got = mutated(rerun)
    assert got["rule"] == "2d" and got["reason"].startswith("rerun_movement("), got["label"]


#: S03 §17.9's specification kinds, each on a BioSTEAM record that carries it: (case, end).
SPEC_KINDS = {
    "RR partial": ("RC1", "condenser"),
    "RR total": ("RC2", "condenser"),
    "BR": ("RC1", "reboiler"),
    "D partial": ("RC4", "condenser"),
    "B": ("RC2", "reboiler"),
    "duty": ("RC3", "reboiler"),
    "purity": ("RC5", "condenser"),
    "recovery": ("RC6", "reboiler"),
    "temperature": ("RC7", "reboiler"),
}


@pytest.mark.parametrize("name", list(SPEC_KINDS))
def test_a10_each_specification_kind_meets_its_thresholds(name: str, records: dict) -> None:
    """A10 (S03 §17.9): on BioSTEAM's view of a record carrying the kind, a registered value whose
    residual is 2× rule 2c's 1e-4 → 2c; 2× the kind's rule 2d threshold → 2d; 0.5× → neither.
    (No BioSTEAM record carries a total condenser's distillate rate.)"""
    cid, end = SPEC_KINDS[name]
    case = case_of(cid)
    v = c9.view(selected_run(records[cid]), case)
    got = Decimal(repr(s03.specification_values(v, case)[end]["tool"]))
    kind = case["specifications"][end]["kind"]
    threshold, basis = s03.RULE2D_SPEC[kind]

    def at(residual: Decimal, relative: bool) -> dict[str, Any]:
        registered = got / (1 + residual) if relative else got - residual
        shifted = copy.deepcopy(case)
        shifted["specifications"][end]["value"] = str(registered)
        return s03.specification_values(v, shifted)[end]

    assert not at(2 * s03.RULE2C_SPEC_RELATIVE, True)["rule2c_passes"]
    two_d = at(2 * threshold, basis == "relative")
    assert two_d["rule2c_passes"] and not two_d["rule2d_passes"], two_d
    neither = at(threshold / 2, basis == "relative")
    assert neither["rule2c_passes"] and neither["rule2d_passes"], neither


# -- A11: path dependence --------------------------------------------------------------------------


@pytest.mark.parametrize(("fraction", "fires"), [(0.2, True), (0.05, False)])
def test_a11_path_dependence_fires_at_two_tenths_not_at_five_hundredths(
    fraction: float, fires: bool, records: dict, ours: dict
) -> None:
    """A11: a second passing rung equal to the selected one except one quantity moved 0.2
    tolerance → `path_dependence`; 0.05 → not (RC1: R2 replaced by R1's run so moved)."""
    record = copy.deepcopy(records["RC1"])
    rungs = record["levels"]["L1"]["rungs"]
    second = copy.deepcopy(rungs[0]["run"])
    shift_product(second, "C", fraction * tol("RC1", "top[C]"), case_of("RC1"))
    rungs[1]["run"] = second
    got = classify("RC1", record, ours)
    path = got["rule2d"]["path_dependence"]
    assert path["compared_rungs"] == ["R1", "R2", "R4"]
    if fires:
        assert got["rule"] == "2d" and got["reason"].startswith("path_dependence("), got["label"]
    else:
        assert got["rule"] == 4 and 0.04 < path["max_ratio"] < 0.1, (got["label"], path)


# -- A12: controls ---------------------------------------------------------------------------------


def test_a12_no_control_agrees_and_biosteams_pairs_count(table: dict[str, Any]) -> None:
    """A12: no control `AGREE`; at least one `DISAGREE` (the committed outcome is both); (PC-L,
    BioSTEAM) and (PC-LI, BioSTEAM) `not_applicable` with no record."""
    by = rows(table)
    summary = table["controls"]["per_tool"]["BioSTEAM"]
    assert set(summary["controls"]) == set(CASES9["controls"]) == {"PC-P", "PC-LB"}
    assert all(by[c]["classification"] != "AGREE" for c in CASES9["controls"])
    assert summary["disagree"] and summary["pairs_count"] and not table["comparison_stopped"]
    for cid in CASES9["not_applicable"]:
        assert by[cid]["label"] == "not_applicable"
        assert not (c9.RESULTS / f"biosteam-{cid}.json").exists()


def unavailable(record: dict[str, Any]) -> dict[str, Any]:
    return {**copy.deepcopy(record), "available": False, "not_available_reason": "synthetic"}


def test_a12_without_a_disagreeing_control_every_pair_is_lost(records: dict) -> None:
    """A12 (§17.3(b)): both controls replaced by `NOT_COMPARABLE` copies → every BioSTEAM pair
    `NOT_COMPARABLE(control_not_comparable: …)`."""
    mutated = dict(records)
    for c in CASES9["controls"]:
        mutated[c] = unavailable(records[c])
    document = c9.compute(records=mutated)
    for cid in PAIRS:
        row = rows(document)[cid]
        if cid in CASES9["controls"]:
            assert row["rule"] == 0
        else:
            assert row["category"] == "control_not_comparable", row["label"]
            assert row["before_control_rule"]["rule"] == 4
    assert document["x31_three_tool"]["clause"] == "not met"


@pytest.mark.parametrize("lost", ["PC-P", "PC-LB"])
def test_a12_one_disagreeing_control_is_enough(
    lost: str, records: dict, table: dict[str, Any]
) -> None:
    """A12: one control replaced while the other is `DISAGREE` → no other pair changes."""
    mutated = {**records, lost: unavailable(records[lost])}
    document = c9.compute(records=mutated)
    before, after = rows(table), rows(document)
    for cid in [*PAIRS, *CASES9["not_applicable"]]:
        if cid != lost:
            assert after[cid]["label"] == before[cid]["label"], cid


def test_a12_control_tool_model_distances(table: dict[str, Any], records: dict) -> None:
    """A12: PC-LB's distance is against `ref.controls.PC-LI.tool_model` (recomputed here); PC-P's
    is `not_applicable(tool_model_differs)`."""
    distance = table["control_tool_model_distance"]
    assert distance["PC-P/BioSTEAM"]["reason"] == "not_applicable(tool_model_differs)"
    assert distance["PC-P/BioSTEAM"]["max_ratio"] is None
    lb = distance["PC-LB/BioSTEAM"]
    model = REF["controls"]["PC-LI"]
    assert lb["registered_discrimination"] == model["max_ratio"]
    case = case_of("PC-LB")
    values = s03.tool_quantities(c9.view(selected_run(records["PC-LB"]), case), case)
    ratios = {
        q: float(
            abs(Decimal(repr(v)) - Decimal(model["tool_model"][q]["value"]))
            / s03.tolerance(
                model["tool_model"][q]["kind"], Decimal(model["tool_model"][q]["value"])
            )
        )
        for q, v in values.items()
    }
    worst = max(ratios, key=lambda q: (ratios[q], q))
    assert (lb["argmax"], lb["max_ratio"]) == (worst, pytest.approx(ratios[worst], rel=1e-12))


# -- A13 -------------------------------------------------------------------------------------------


def test_a13_the_comparison_recomputes_identically_from_the_committed_files() -> None:
    """A13: `comparison.json` and `SHA256SUMS` are what the classifier computes from the committed
    records, S03's `ours-*.json`, both cases files and the twin, byte for byte."""
    assert c9.TABLE.read_text(encoding="utf-8") == c9.dumps(c9.compute())
    assert c9.SUMS.read_text(encoding="utf-8") == c9.sums_text()


def classifications(document: dict[str, Any]) -> dict[str, Any]:
    """A13 (S03 §19.1's rule): every pair's classification, category, rule, label,
    `within_tolerance` and `quantities_outside`, the controls block and every X31 class, row and
    outcome; floats that depend on our values are left out."""

    def pair(row: dict[str, Any]) -> dict[str, Any]:
        quantities = row.get("quantities")
        return {
            "classification": row["classification"],
            "category": row["category"],
            "rule": row["rule"],
            "label": row["label"],
            "quantities_outside": row.get("quantities_outside"),
            "within_tolerance": None
            if quantities is None
            else {q["quantity"]: q["within_tolerance"] for q in quantities},
        }

    def x31_case(case: dict[str, Any]) -> dict[str, Any]:
        return {
            "row": case["row"],
            "outcome": case["outcome"],
            "pairs": {tool: p["class"] for tool, p in case["pairs"].items()},
        }

    x31 = document["x31_three_tool"]
    return {
        "rows": {row["case"]: pair(row) for row in document["rows"]},
        "controls": document["controls"],
        "comparison_stopped": document["comparison_stopped"],
        "x31": {
            "cases": {cid: x31_case(case) for cid, case in x31["cases"].items()},
            "inverse_kinds": {k: x31_case(case) for k, case in x31["inverse_kinds"].items()},
            "clause": x31["clause"],
        },
    }


def test_a13_the_comparison_recomputes_from_a_live_solve_of_our_side(
    table: dict[str, Any],
) -> None:
    """A13: recomputed with a live solve of our side, every classification equals `cmp9`'s."""
    solved = {cid: ours_side.solve(cid) for cid in ours_side.OURS_CASES}
    live_ours = {cid: solved.get(c9.inputs_case(cid, CASES9)) for cid in [*PAIRS, *CASES3["cases"]]}
    live = json.loads(c9.dumps(c9.compute(ours=live_ours)))
    expected = classifications(table)
    assert len(expected["rows"]) == len(table["rows"]) == len(live["rows"]) == 21
    assert classifications(live) == expected


# -- A14 -------------------------------------------------------------------------------------------


@pytest.mark.parametrize("kind", ["T", "flow", "duty"])
@pytest.mark.parametrize(("fraction", "word"), [(0.999, "AGREE"), (1.001, "DISAGREE")])
def test_a14_the_tolerance_is_s03s_formula_unrounded(kind: str, fraction: float, word: str) -> None:
    """A14: synthetic pairs at 0.999 and 1.001 tolerance for each kind → `AGREE` / `DISAGREE`."""
    twin_value = {"T": "352.123456789", "flow": "0.654321", "duty": "-20031.97"}[kind]
    tol_ = s03.tolerance(kind, Decimal(twin_value))
    tool = float(twin_value)
    ours_value = float(Decimal(repr(tool)) + Decimal(repr(fraction)) * tol_)
    twin = {"q": {"value": twin_value}}
    got, _ = s03.rule4({"q": tool}, {"q": ours_value}, twin, {"q": kind})
    assert got == word


@pytest.mark.parametrize("cid", [c for c in PAIRS])
def test_a14_no_per_case_or_per_tool_factor(cid: str, table: dict[str, Any]) -> None:
    """A14: every rule 4 tolerance in `cmp9` is S03 §6's `a_k + 1e-6 |v_twin|`, unrounded."""
    row = rows(table)[cid]
    twin = s03.twin_quantities(REF, c9.twin_case(cid, CASES9))
    assert row["rule"] == 4
    for q in row["quantities"]:
        assert q["tolerance"] == float(
            s03.tolerance(q["kind"], Decimal(twin[q["quantity"]]["value"]))
        )
        assert q["twin"] == twin[q["quantity"]]["value"]


# -- A15 -------------------------------------------------------------------------------------------


def class_key(pair: dict[str, Any]) -> str:
    """`s09_cases.json → x31_three_tool.pre_registered`'s key for BioSTEAM's pair."""
    if pair["classification"] in ("AGREE", "DISAGREE"):
        return str(pair["classification"])
    return str(pair["class"])


def test_a15_the_three_tool_table_equals_the_pre_registered_outcomes(table: dict[str, Any]) -> None:
    """A15: for RC1-RC4 and per inverse kind, `cmp9` holds the three classes (IDAES and DWSIM from
    `cmp3`), the row and the outcome; they equal `pre_registered` at BioSTEAM's committed classes,
    and the clause follows §8.2 from those rows."""
    x31 = table["x31_three_tool"]
    pre = CASES9["x31_three_tool"]["pre_registered"]
    s03_cases = {**CMP3["x31"]["cases"]}
    s03_cases |= {v["case"]: v for v in CMP3["x31"]["inverse_kinds"].values()}
    s03_rows = {(r["case"], r["tool"]): r for r in CMP3["rows"]}
    entries = {**x31["cases"], **{v["case"]: v for v in x31["inverse_kinds"].values()}}
    assert set(entries) == set(pre) == {*c9.X31_CASES, *c9.INVERSE_KINDS}
    for cid, entry in entries.items():
        assert set(entry["pairs"]) == {"BioSTEAM", "DWSIM", "IDAES"}
        for tool in c9.S03_TOOLS:
            p = entry["pairs"][tool]
            assert p["class"] == s03_cases[cid]["pairs"][tool]["class"]
            assert p["label"] == s03_rows[cid, tool]["label"]
            assert [p["class"], p["classification"]] == pre[cid]["S03"][tool]
        key = class_key(entry["pairs"]["BioSTEAM"])
        assert [entry["row"], entry["outcome"]] == pre[cid][key], cid
    rows_hit = [x31["cases"][c]["row"] for c in c9.X31_CASES]
    assert x31["clause"] == c9.clause(rows_hit, False)
    assert x31["count_row_5"] == rows_hit.count(5)


def test_a15_without_biosteam_the_table_is_s03s(table: dict[str, Any]) -> None:
    """A15 (claim C9): with BioSTEAM omitted the rows and the clause equal `cmp3`'s."""
    red = table["x31_reduction_to_s03"]
    assert red["equal"] is True
    assert red["rows"] == red["s03_rows"] and red["clause"] == red["s03_clause"] == "not met"
    recomputed = c9.reduction(table["rows"], CMP3, False)
    assert recomputed == red


# -- A16, A17 --------------------------------------------------------------------------------------


def commit_of(path: Path) -> str:
    return git("log", "-1", "--format=%H", "--", str(path.relative_to(REPO_ROOT))).stdout.strip()


def test_a16_the_qualification_commit_precedes_the_comparison() -> None:
    """A16: the qualification commit (the last touching `qualification/biosteam.json`) is an
    ancestor of the commit that holds `comparison.json` (HEAD while it is uncommitted)."""
    qualification = commit_of(QUAL)
    assert qualification, HISTORY
    require_history(qualification)
    status = git("status", "--porcelain", "--", str(c9.TABLE.relative_to(REPO_ROOT)))
    holder = "HEAD" if status.stdout.strip() or not commit_of(c9.TABLE) else commit_of(c9.TABLE)
    assert git("merge-base", "--is-ancestor", qualification, holder).returncode == 0
    assert qualification != git("rev-parse", holder).stdout.strip()
    for cid in PAIRS:
        record = c9.RESULTS / f"biosteam-{cid}.json"
        assert git("merge-base", "--is-ancestor", commit_of(record), holder).returncode == 0


def strip_wall(x: Any) -> Any:
    if isinstance(x, dict):
        return {k: strip_wall(v) for k, v in x.items() if not k.startswith("wall_time")}
    if isinstance(x, list):
        return [strip_wall(v) for v in x]
    return x


@pytest.mark.parametrize("cid", PAIRS)
def test_a17_the_repeat_run_reproduced_every_record(cid: str, records: dict) -> None:
    """A17: `repeat_run` shows the second run reproducing the record byte for byte, wall-clock
    fields excepted, and its first-run hash is the committed record's."""
    repeat = load(QUAL)["repeat_run"]
    assert repeat["all_identical"] is True
    entry = repeat["per_case"][cid]
    canonical = (json.dumps(strip_wall(records[cid]), indent=1) + "\n").encode()
    assert entry["identical"] is True
    assert entry["sha256_run1"] == entry["sha256_run2"] == hashlib.sha256(canonical).hexdigest()


# -- A18 -------------------------------------------------------------------------------------------


def test_a18_the_document_is_complete(table: dict[str, Any], records: dict) -> None:
    """A18 (§18.5): each pair's level, rung and outer-evaluation count; each selected record's
    margin rows (exactly §18.4(c)'s), the largest and its row; the thin-margin list; the response
    table with a BioSTEAM column; every `NOT_COMPARABLE` and `DISAGREE` with its reason."""
    by = rows(table)
    margin = table["margin"]
    assert margin["rows"] == CASES9["tool_settings"]["BioSTEAM"]["margin"]["rows"]
    for cid in PAIRS:
        record, pair, row = records[cid], table["pairs"][cid], by[cid]
        assert (pair["level"], pair["rung"]) == (record["level"], record["selected_rung"])
        assert row["selection"]["recomputed"] == record["selected_rung"]
        outer = selected_rung(record)["outer"]
        assert pair["outer_evaluations"] == (len(outer["evaluations"]) if outer else 0)
        if outer:
            assert row["outer"]["final_abs_g_over_ytol"] <= 1.0
        m = margin["per_pair"][cid]
        expected = {
            "B3_stage_component",
            "B4_equilibrium",
            "B5_component",
            "B5_energy",
            "rule2c_adiabatic_duty",
            "rule2d_specification",
            "rule2d_rerun_movement",
        }
        if case_of(cid)["condenser"] == "total":
            expected.add("rule2c_total_condenser_vapour")
        if len(row["rule2d"]["path_dependence"]["compared_rungs"]) > 1:
            expected.add("rule2d_path_spread")
        assert set(m["ratios"]) == expected, cid
        assert (
            m["max_ratio"] == max(m["ratios"].values())
            and m["ratios"][m["max_row"]] == m["max_ratio"]
        )
        assert m["thin"] == (m["max_ratio"] > 0.1)
    assert margin["thin_margin"] == [
        {"case": c, "row": m["max_row"], "ratio": m["max_ratio"]}
        for c, m in margin["per_pair"].items()
        if m["thin"]
    ]
    listed = {(e["case"], e["label"]) for e in table["not_comparable_and_disagree"]}
    for r in table["rows"]:
        if r["classification"] in ("NOT_COMPARABLE", "DISAGREE"):
            assert (r["case"], r["label"]) in listed and r["reason"]
    assert set(table["perturbation_response"]) == set(REF["perturbations"])
    for entry in table["perturbation_response"].values():
        assert set(entry["both_agree"]) == {"BioSTEAM", "DWSIM", "IDAES"}
        assert all("BioSTEAM" in line for line in entry["quantities"])


def test_a18_a_thin_margin_is_a_disclosure_that_moves_no_classification(
    records: dict, ours: dict
) -> None:
    """A18 (§18.5): A09's 0.5× copy for B3 (+1.55e-8 mol/s, ratio about 0.5) is classified by
    rule 4, not `NOT_COMPARABLE`, and is in the thin-margin list with row B3."""
    mutated = copy.deepcopy(records)
    selected_rung(mutated["RC1"])["run"]["profile"]["stages"][3]["out_mol_per_s"][1]["B"] += 1.55e-8
    document = c9.compute(records=mutated)
    row = rows(document)["RC1"]
    assert row["rule"] == 4 and row["classification"] == "AGREE", row["label"]
    thin = {e["case"]: e for e in document["margin"]["thin_margin"]}
    assert thin["RC1"]["row"] == "B3_stage_component"
    assert 0.45 < thin["RC1"]["ratio"] < 0.55


# -- A20 -------------------------------------------------------------------------------------------


@pytest.mark.parametrize("generator", ["s02_reference.py", "s03_reference.py", "s06_reference.py"])
def test_a20_the_earlier_generators_check(generator: str) -> None:
    """A20: `s02_reference.py`, `s03_reference.py` and `s06_reference.py --check` pass on `wp/S09`
    (S01's, S02's, S03's and S06's suites are judged node by node in the evidence manifest)."""
    path = REPO_ROOT / "docs" / "derivations" / "scripts" / generator
    done = subprocess.run([sys.executable, str(path), "--check"], capture_output=True, text=True)
    assert done.returncode == 0, done.stdout[-2000:] + done.stderr[-2000:]
