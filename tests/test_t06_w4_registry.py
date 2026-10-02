"""T06 W4: the registry's T06 sections — the corpus, its policies, the ensemble, the REF fixtures.

Spec `docs/derivations/T06-corpus-spec.md` as amended (Amendment 1) §3 (the corpus, its counting
rules and its table), §6.1 (eligibility), §6.6 (the policies), §9.2 (the reference fixtures) and
§17 W4; ADR 0014, ADR 0015. `benchmarks/registry.yaml` carries four T06 sections after `cases`:
`policies`, `corpus`, `ensemble` and `reference_fixtures`, and the family `SYN-001-T06`.

T6-A01 is here: the registry's corpus is the twin's `corpus.cases` transcribed — every row's id,
class, fixture, expected kind, path, eligibility and denominator flag equal, exactly. Whether each
case's measured outcome meets its registration is W5's (`test_t06_w5_corpus.py`).
"""

from __future__ import annotations

import hashlib
from typing import Any

import pytest
from conftest import REPO_ROOT, load_yaml
from t05b_support import POLICY_V2
from t06_support import T06_CASES, T06_REVISION_POLICY, T06_REVISION_POLICY_V1
from test_t02_region import POLICY as T02_EO
from test_t04_edge3 import NONE, case_policy
from test_t05_coupled import POLICY as POLICY_W13

from openflowsheet.application.policies import T04_W12
from openflowsheet.orchestrator.trace import SolvePolicy
from openflowsheet.run.manifest import policy_sha256

REGISTRY: dict[str, Any] = load_yaml(REPO_ROOT / "benchmarks" / "registry.yaml")
TWIN_PATH = REPO_ROOT / "benchmarks" / "t06" / "reference_values.yaml"
TWIN: dict[str, Any] = load_yaml(TWIN_PATH)
TWIN_SHA256 = "e97f61ce4a7d13c3cd22edccb2fba637dbebf59fd990fd64ad32ccde970cd2d4"
CORPUS: dict[str, Any] = REGISTRY["corpus"]
CASES: list[dict[str, Any]] = CORPUS["cases"]
BY_ID: dict[str, dict[str, Any]] = {case["id"]: case for case in CASES}

#: Spec §3.1 rule 3: the kinds that make up the success denominator.
DENOMINATOR_KINDS = ("verified_at_reference", "converged_to_closed_form")
#: The twin's row fields, transcribed verbatim (A01); `expected` is `expected.outcome` here.
TWIN_FIELDS = ("id", "class", "fixture", "path", "eligible", "in_success_denominator")

#: Every registered policy, constructed where its registration constructs it.
CONSTRUCTED: dict[str, SolvePolicy] = {
    "T06-revision-v2": T06_REVISION_POLICY,
    # Run 1's revision-path policy (spec §6.6 (A4), A95), named by `ensemble.run_1`.
    "T06-revision-v1": T06_REVISION_POLICY_V1,
    "T05b-v2": POLICY_V2,
    "T05-W13": POLICY_W13,
    # `solve_tear`'s own default (`orchestrator/tear.py`), constructed as it constructs it.
    "SYN-001-K03": SolvePolicy(policy_id="SYN-001-K03", residual_tolerances={}, scales={}),
    # `scripts/t06_phase_m.py::A02_POLICY`, the policy M2 registered NET-05's solve under;
    # constructed as the application's `legacy_eo` policy (T07 design note R2.3).
    "T04-W12": T04_W12,
    "T02-eo": T02_EO,
    "T04-HOM-01": case_policy("HOM-01"),
    "T04-HOM-01-edge-off": case_policy("HOM-01", NONE),
}


def _runs(case: dict[str, Any]) -> list[tuple[str, str]]:
    """Every `(path, policy key)` a corpus case is registered to run under, controls included."""
    runs: list[tuple[str, str]] = []
    if "policy" in case:
        runs.append((case["path"], case["policy"]))
    runs += [(extra["path"], extra["policy"]) for extra in case.get("also_registered", ())]
    for control in case.get("controls", ()):
        runs += [(case["path"], policy) for policy in control["policies"]]
    return runs


def test_a01_the_corpus_is_the_twins_table() -> None:
    twin = TWIN["corpus"]["cases"]
    assert [case["id"] for case in CASES] == [row["id"] for row in twin]
    for case, row in zip(CASES, twin, strict=True):
        assert {field: case[field] for field in TWIN_FIELDS} == {
            field: row[field] for field in TWIN_FIELDS
        }, row["id"]
        assert case["expected"]["outcome"] == row["expected"], row["id"]


def test_a01_the_counts_are_the_twins_and_the_spec() -> None:
    twin = TWIN["corpus"]
    counts = (
        len(CASES),
        sum(case["in_success_denominator"] for case in CASES),
        sum(case["eligible"] for case in CASES),
    )
    assert counts == (CORPUS["counted"], CORPUS["in_success_denominator"], CORPUS["eligible"])
    assert counts == (twin["counted"], twin["in_success_denominator"], twin["eligible"])
    assert counts == (49, 30, 22)  # spec §3.2 as amended (A1: 30, was 28)
    assert len(BY_ID) == len(CASES), "ids are unique"
    fixtures = [case["fixture"] for case in CASES]
    assert len(set(fixtures)) == len(fixtures), "fixtures are unique"


def test_the_denominator_is_the_preregistered_kinds() -> None:
    """Spec §3.1 rule 3: membership is decided by the expected kind, and by nothing else."""
    for case in CASES:
        assert case["in_success_denominator"] == (
            case["expected"]["outcome"] in DENOMINATOR_KINDS
        ), case["id"]


def test_eligibility_follows_section_6_1() -> None:
    """(a) eligible only if `verified_at_reference`; (e) a metamorphic restatement is ineligible
    while the case it restates is eligible (A1); every denominator case left out says why."""
    restatements = TWIN["closed_form"]["metamorphic_restatements"]
    assert restatements == {"NUM-04": "NET-01", "STA-03": "NET-01", "STA-04": "NET-08"}
    for restated, original in restatements.items():
        assert BY_ID[restated]["eligible"] is False, restated
        assert BY_ID[original]["eligible"] is True, original
    for case in CASES:
        if case["eligible"]:
            assert case["expected"]["outcome"] == "verified_at_reference", case["id"]
            assert case["path"] in ("revision_eo", "tear", "legacy_eo"), case["id"]
        elif case["in_success_denominator"]:
            assert case["ineligible_because"], case["id"]
    assert sorted(case["id"] for case in CASES if case["eligible"]) == sorted(
        REGISTRY["ensemble"]["cases"]
    )


# -- the policies, by canonical hash (§6.6; A65's hash) -----------------------------------------


@pytest.mark.parametrize("key", sorted(REGISTRY["policies"]))
def test_every_registered_policy_is_the_constructed_one(key: str) -> None:
    entry = REGISTRY["policies"][key]
    policy = CONSTRUCTED[key]
    assert policy.policy_id == entry["policy_id"]
    assert policy_sha256(policy) == entry["sha256"]


def test_every_policy_a_registration_names_is_registered() -> None:
    assert sorted(REGISTRY["policies"]) == sorted(CONSTRUCTED)
    named = {policy for case in CASES for _, policy in _runs(case)}
    named |= set(REGISTRY["ensemble"]["policies"].values())
    named |= set(REGISTRY["ensemble"]["run_1"]["policies"].values())
    named.add(REGISTRY["reference_fixtures"]["policy"])
    assert named == set(REGISTRY["policies"])


def test_the_policy_per_path_is_section_6_6s() -> None:
    """A4 (§6.6, A02): every revision-built `verified_at_reference` case under `T06-revision-v2`,
    the tear path under `SYN-001-K03`, NET-05 under its A02 policy."""
    for case in CASES:
        if case["expected"]["outcome"] != "verified_at_reference":
            continue
        expected = {"revision_eo": "T06-revision-v2", "tear": "SYN-001-K03"}.get(case["path"])
        if expected is not None:
            assert case["policy"] == expected, case["id"]
    assert BY_ID["NET-05"]["policy"] == REGISTRY["ensemble"]["policies"]["legacy_eo"] == "T04-W12"
    assert REGISTRY["ensemble"]["policies"] == {
        "revision_eo": "T06-revision-v2",
        "tear": "SYN-001-K03",
        "legacy_eo": "T04-W12",
    }
    # A4 (A95): run 1's revision path ran `T06-revision-v1`; its record stands.
    assert REGISTRY["ensemble"]["run_1"]["policies"] == {
        "revision_eo": "T06-revision-v1",
        "tear": "SYN-001-K03",
        "legacy_eo": "T04-W12",
    }


def test_net02s_two_entries_and_the_edge_off_controls() -> None:
    """A1: NET-02 `verified_at_reference` under `T06-revision-v2`, and its control `BOUND_BLOCKED`
    under `T05b-v2` and `T05-W13` (A63); ADV-01's HOM-N control with edge 3 off (A14)."""
    net02 = BY_ID["NET-02"]
    assert (net02["policy"], net02["expected"]["outcome"]) == (
        "T06-revision-v2",
        "verified_at_reference",
    )
    assert net02["expected"]["items"] == [
        ["initializer", "traversal-G0-v1", "BOUND_BLOCKED"],
        ["eo_recovery_start", "traversal-G0-pass8-v1", "CONVERGED"],
    ]
    (control,) = net02["controls"]
    assert (control["policies"], control["outcome"], control["code"]) == (
        ["T05b-v2", "T05-W13"],
        "typed_failure",
        "BOUND_BLOCKED",
    )
    assert (control["eo_recovery"], control["eo_recovery_unsupported"]) == (
        "unsupported",
        "no_continuation_parameter",
    )
    (hom_n,) = BY_ID["ADV-01"]["controls"]
    assert (hom_n["policies"], hom_n["code"]) == (["T04-HOM-01-edge-off"], "ACTIVE_SET_CYCLING")
    assert CONSTRUCTED["T04-HOM-01-edge-off"].globalization.eo_recovery == "none"
    assert CONSTRUCTED["T04-HOM-01"].globalization.eo_recovery == "homotopy"


def test_sta03_and_sta04_are_solved_cases() -> None:
    """A1 (A1.3): STA-03 and STA-04 are `verified_at_reference`, in the denominator, ineligible."""
    sta03, sta04 = BY_ID["STA-03"], BY_ID["STA-04"]
    assert [variant["fixture"] for variant in sta03["variants"]] == [
        "SYN-001-T06-STA03-kgs",
        "SYN-001-T06-STA03-degC",
    ]
    assert _runs(sta03) == [("tear", "SYN-001-K03"), ("revision_eo", "T06-revision-v2")]
    assert _runs(sta04) == [("revision_eo", "T06-revision-v2"), ("revision_eo", "T05b-v2")]
    for case in (sta03, sta04):
        assert case["expected"]["outcome"] == "verified_at_reference"
        assert (case["in_success_denominator"], case["eligible"]) == (True, False)


# -- the fixtures ------------------------------------------------------------------------------


def _revisions() -> list[str]:
    paths = [case["revision"] for case in CASES if case.get("revision")]
    paths += [variant["revision"] for case in CASES for variant in case.get("variants", ())]
    paths += [fixture["revision"] for fixture in REGISTRY["reference_fixtures"]["fixtures"]]
    paths += [
        control["revision"]
        for control in REGISTRY["reference_fixtures"].get("positive_controls", ())
    ]
    return paths


def test_every_named_revision_exists_and_every_case_file_is_named() -> None:
    for case in CASES:
        assert case.get("revision") or case["revision_absent_reason"], case["id"]
    for path in _revisions():
        assert (REPO_ROOT / path).is_file(), path
    named = {path for path in _revisions() if path.startswith("benchmarks/t06/cases/")}
    on_disk = {f"benchmarks/t06/cases/{path.name}" for path in sorted(T06_CASES.glob("*.yaml"))}
    assert named == on_disk


def test_the_t06_family() -> None:
    families = {family["id"]: family for family in REGISTRY["families"]}
    family, syn001 = families["SYN-001-T06"], families["SYN-001"]
    assert family["kind"] == "synthetic"
    assert family["specification"] == family["derivation"] == "docs/derivations/T06-corpus-spec.md"
    assert family["reference"] == "benchmarks/t06/reference_values.yaml"
    digest = hashlib.sha256(TWIN_PATH.read_bytes()).hexdigest()
    assert family["reference_sha256"] == CORPUS["reference_sha256"] == TWIN_SHA256 == digest
    for semantics in family["semantics"]:
        assert (REPO_ROOT / semantics).is_file(), semantics
    for key in ("components", "property_domain", "reference_convention", "state_definition"):
        assert family[key] == syn001[key], key
    for key in ("component_balance", "energy_balance", "temperature", "pressure"):
        assert family["tolerances"][key] == syn001["tolerances"][key], key
    for key in ("tear_component_flow", "temperature", "pressure", "duty"):
        assert family["scales"][key] == syn001["scales"][key], key
    budgets = ("property_calls", "newton_iterations_per_attempt", "attempts")
    assert {k: family["budgets"][k] for k in budgets} == {k: syn001["budgets"][k] for k in budgets}


def test_the_ensemble_definition_is_the_twins() -> None:
    ensemble, gate = REGISTRY["ensemble"], TWIN["closed_form"]["gate"]
    assert len(ensemble["cases"]) == gate["eligible_cases"] == 22
    assert ensemble["starts_per_case"] == gate["starts_per_case"] == 20
    assert ensemble["N"] == gate["N"] == 22 * 20
    assert ensemble["gate"]["S_min"] == gate["S_min"] == 418
    assert ensemble["gate"]["fraction"] == gate["fraction"]
    assert ensemble["law"]["rng"] == "sha256-counter-v1"
    assert ensemble["caps"] == {"coordinate_attempts": 64, "joint_attempts": 64}
    assert ensemble["time_ceiling_s"] == 60
    # §6.5: the starts file is generated once (M7) before any solve and its hash recorded here;
    # T6-A25 (`test_t06_w6_generator.py`) regenerates it.
    starts = REPO_ROOT / ensemble["starts_file"]
    assert ensemble["starts_sha256"] == hashlib.sha256(starts.read_bytes()).hexdigest()
    assert "starts_sha256_absent_reason" not in ensemble


def test_the_reference_fixtures_are_the_twins() -> None:
    fixtures = REGISTRY["reference_fixtures"]["fixtures"]
    assert [fixture["id"] for fixture in fixtures] == list(
        TWIN["closed_form"]["reference_fixtures"]
    )
    assert fixtures[-1]["revision"] == "benchmarks/syn001/cases/SYN-001-nominal.yaml"  # REF-08
