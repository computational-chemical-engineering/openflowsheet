"""T04 W10: the registry's globalization cases and the two new revisions (T04 §11, §13.1; Q7).

Every T04 entry of `benchmarks/registry.yaml` is run from what the registry says — its revision
document and its `solve_policy_overrides` — through the plan executor, and must give the outcome it
registers and the one `benchmarks/t04/reference_values.yaml` gives under its `reference_key`. The
two new revision documents are checked to be the A02 base with only the registered guess and duty
changed. PHS-05's re-registration closes T03's handover: `CONVERGED` via edge 3 under the default
policy, and still T03 A12's `ACTIVE_SET_CYCLING` with the edge off.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml
from test_t04_edge3 import plan_run, region_step

from openflowsheet.orchestrator.trace import GlobalizationPolicy, RecyclePolicy, SolvePolicy

REPO_ROOT = Path(__file__).resolve().parents[1]
REGISTRY: dict[str, Any] = yaml.safe_load((REPO_ROOT / "benchmarks" / "registry.yaml").read_text())
CASES = {case["case_id"]: case for case in REGISTRY["cases"]}
T04: dict[str, Any] = yaml.safe_load(
    (REPO_ROOT / "benchmarks" / "t04" / "reference_values.yaml").read_text()
)
GLOBALIZATION = sorted(
    case_id
    for case_id, case in CASES.items()
    if str(case["class"]).startswith("globalization case")
)
HOM = {
    entry["registry_id"]: name for name, entry in T04["policy_simulation"]["homotopy_cases"].items()
}


def resolve(key: str) -> Any:
    node: Any = T04
    for part in key.split("."):
        node = node[part]
    return node


def policy_for(case: dict[str, Any], **globalization: Any) -> SolvePolicy:
    """The registry's `solve_policy_overrides` as a `SolvePolicy` — nothing else."""
    overrides = dict(case.get("solve_policy_overrides") or {})
    recycle = overrides.pop("recycle", None)
    overrides.pop("globalization", None)
    return SolvePolicy(
        policy_id=f"T04-{case['case_id']}",
        residual_tolerances={},
        scales={},
        recycle=RecyclePolicy(**recycle) if recycle else RecyclePolicy(),
        globalization=GlobalizationPolicy(**globalization),
        **overrides,
    )


def revision(case: dict[str, Any]) -> dict[str, Any]:
    loaded: dict[str, Any] = yaml.safe_load((REPO_ROOT / case["revision"]).read_text())
    return loaded


def test_the_registered_globalization_cases_are_t04_s() -> None:
    """T04 §13.1: PHS-05 re-registered, two new revisions, three policy-override entries and the
    basin study — class `globalization case`, all outside the success denominator (Q7)."""
    assert GLOBALIZATION == sorted(
        [
            "SYN-001-A02-355-dew-guess",
            "SYN-001-A02-355-dew-guess-377",
            "SYN-001-A02-352-vapor-guess-410",
            "SYN-001-A02-340-two-phase-guess-capped",
            "SYN-001-A02-360-iteration-capped",
            "SYN-001-nominal-eo-iteration-capped",
            "SYN-001-high-recycle-ptc-basin",
        ]
    )
    for case_id in GLOBALIZATION:
        case = CASES[case_id]
        assert case["expected"]["in_success_denominator"] is False
        assert (REPO_ROOT / case["revision"]).is_file()
        if case.get("reference"):
            assert case["reference"] == "benchmarks/t04/reference_values.yaml"
            resolve(case["reference_key"])
    assert set(HOM) <= set(GLOBALIZATION)


@pytest.mark.parametrize(
    ("case_id", "guess", "duty"),
    [
        ("SYN-001-A02-355-dew-guess-377", "HOM-02", "HOM-02"),
        ("SYN-001-A02-352-vapor-guess-410", "HOM-03", "HOM-03"),
    ],
)
def test_the_new_revisions_differ_from_their_base_only_in_guess_and_duty(
    case_id: str, guess: str, duty: str
) -> None:
    registered = T04["policy_simulation"]["homotopy_cases"]
    base = revision(CASES["SYN-001-A02-355-dew-guess"])
    derived = revision(CASES[case_id])
    values = {s["id"]: s for s in derived["specifications"]}
    assert values["GUESS-heater-outlet-T"]["value"] == float(registered[guess]["guess_S3_T_K"])
    assert values["SPEC-flash-duty"]["value"] == float(registered[duty]["Q_flash_spec_W"])
    for field in ("instances", "connections", "component_set"):
        assert derived[field] == base[field], field
    others = {s["id"]: s for s in base["specifications"]}
    for name, entry in values.items():
        if name in ("GUESS-heater-outlet-T", "SPEC-flash-duty"):
            continue
        assert entry == others[name], name
    assert set(values) == set(others)


_RUNS: dict[str, Any] = {}


def run(case_id: str, **globalization: Any) -> Any:
    key = f"{case_id}/{sorted(globalization.items())}"
    if key not in _RUNS:
        case = CASES[case_id]
        _RUNS[key] = plan_run(revision(case), policy_for(case, **globalization)).result
    return _RUNS[key]


@pytest.mark.parametrize("case_id", sorted(HOM))
def test_each_continuation_case_runs_to_its_registered_outcome(case_id: str) -> None:
    """A04–A08 from the registry: the plan run of the registered revision under the registered
    overrides ends as the registry and `ref.hom` say, with edge 3 taken and the registered λ."""
    case = CASES[case_id]
    registered = resolve(case["reference_key"])
    result = run(case_id)
    step = region_step(result)
    assert step.outcome == case["expected"]["code"] == registered["outcome"]
    assert step.eo_recovery == case["expected"]["recovery"] == "taken"
    record = step.detail.homotopy
    if "lambda_reached" in case["expected"]:
        assert str(record.lambda_reached) == case["expected"]["lambda_reached"]
        assert record.inferred_cause == case["expected"]["inferred_cause"]
    else:
        assert str(record.lambda_reached) == "1"


def test_phs_05_is_converged_by_edge_3_and_t03_a12_stands_with_the_edge_off() -> None:
    """T04 §11.1: PHS-05 re-registered to `CONVERGED` under the default policy; `handed_to: T04`
    closed; with `eo_recovery: none` the contract's `ACTIVE_SET_CYCLING` is T03's, unchanged."""
    case = CASES["SYN-001-A02-355-dew-guess"]
    assert "handed_to" not in case["expected"] and case["expected"]["resolved_by"] == "T04"
    assert region_step(run(case["case_id"])).outcome == "CONVERGED"
    without = case["expected"]["without_recovery"]
    off = region_step(run(case["case_id"], eo_recovery="none"))
    assert off.outcome == without["code"] == "ACTIVE_SET_CYCLING"
    assert off.eo_recovery is None
    t03 = yaml.safe_load((REPO_ROOT / without["reference"]).read_text())
    node: Any = t03
    for part in without["reference_key"].split("."):
        node = node[part]
    assert node["outcome"] == "ACTIVE_SET_CYCLING"


def test_hom_u_from_the_registry_is_unsupported() -> None:
    """A09's HOM-U: the nominal revision under `eo` with one Newton iteration per attempt."""
    case = CASES["SYN-001-nominal-eo-iteration-capped"]
    result = run(case["case_id"])
    (step,) = [s for s in result.steps if s.kind == "solve_eo"]
    assert step.outcome == case["expected"]["code"] == "BUDGET_EXHAUSTED"
    assert step.detail.budget == case["expected"]["budget"]
    assert step.eo_recovery == case["expected"]["recovery"] == "unsupported"
    assert step.eo_recovery_unsupported == case["expected"]["recovery_unsupported"]


def test_the_basin_study_entry_names_the_registered_family() -> None:
    """The study entry points at the harness and the re-registered comparison: 45 guesses, 27
    refused, the verdict `experimental`."""
    case = CASES["SYN-001-high-recycle-ptc-basin"]
    registered = resolve(case["reference_key"])
    assert len(registered) == 45
    assert sum(1 for entry in registered if entry.get("start") == "refused_by_the_mixer") == 27
    assert (REPO_ROOT / case["study"]["harness"]).is_file()
    assert case["expected"]["verdict"] == "experimental"
    assert case["expected"]["v14_qualified_ptc_clause"] == "incomplete"
