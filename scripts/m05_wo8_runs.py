"""M05 WO-8: the `nlp`-tier study runs on known truths and their same-machine replay (design note
§5.2, §5.3, §12 WO-8, §13 G5-G10, §19; register R-384, R-385, R-387).

The composition root of a study (R-387): it imports `studies.trust_region` (`run_study`,
`C1Parent`, `TrfStage`) and `application.trust_region_parent` (`C1_PARENT_SERVICES`) and wires
them. Each case is the stand-in loop `C1-LOOP-M02-v1` with its reactor pinned to a test-only,
in-process variant (registered for this process only, as M02's and M04's tests do), solved on one
`ExperimentRunner` over a fresh, empty experiment store (F-18):

- `TR-E2`: `m05-synthetic-interior-v1` with its closed-form gradient (§5.2);
- `TR-E2-FD`: the same variant through `ParentExperimentTruth`, FD gradients and the once-per-study
  `M05-fd-v2` check at the start inlet (§5.3, §17.2);
- `LOOP-R`: M04's `m04-synthetic-rough-v1` (not promotable): stage A skipped, stage C with FD
  gradients and the no-surrogate basis.

Every case: start 673.15 K, `IN_PROCESS_BUDGET`, `M05-trf-config-v1` with σ = 0.0125, and the
no-surrogate basis `M05-basis-v2` (`m05_basis_v2`, R-400: v1's affine Taylor basis plus the truth's
curvature along the decision path, from M02's pinned inner solve at d₀ ± t); `run_case` takes
`basis_policy="M05-basis-v1"` for the v1 runs of 6a9d29d (F-15's evidence). The FD truths'
`M05-fd-v2` check runs inside the first stage-C run (R-406).
`LOOP-S` needs stage A on M04's promoted surrogate (`SurrogateTruth`, §6.4), which this branch does
not carry; it is not a case here (WO-8 build log).

Writes, beside `<record>.json`: `<record>.coupling/<solve_id>.json`, the canonical bytes of every
M02 coupling record a solve digested (R-385), and `<record>.ledger.json`, every holder request in
order without its `wall_s` (its sha256 is `artifacts.ledger`). `--replay` re-runs the case from a
fresh store and compares with the committed files (G10, §19.4): the record by
`m05_replay.replay_differences`, the ledger exactly, and every persisted coupling record by
integrity and content. Prints one summary line; exit 0 iff the run (or the replay) is clean.

    .venv-nlp/bin/python scripts/m05_wo8_runs.py TR-E2 [--replay]
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import platform
import sys
import tempfile
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

REPO_ROOT: Final = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "tests" / "support"))

import m04_synthetic_parents as m04_parents  # noqa: E402
import m05_replay as replay  # noqa: E402
import m05_synthetic as synthetic  # noqa: E402

from openflowsheet.adapters import variants  # noqa: E402
from openflowsheet.adapters.experiments.runner import ExperimentRunner  # noqa: E402
from openflowsheet.adapters.experiments.store import ExperimentStore  # noqa: E402
from openflowsheet.application.trust_region_parent import C1_PARENT_SERVICES  # noqa: E402
from openflowsheet.canonical import canonical_json, document_sha256  # noqa: E402
from openflowsheet.compiled import EvaluationContext  # noqa: E402
from openflowsheet.studies.trust_region.basis import (  # noqa: E402
    BASIS_POLICY_V2,
    m05_basis,
    m05_basis_v2,
)
from openflowsheet.studies.trust_region.parent import DECISION_TOLERANCE_K, C1Parent  # noqa: E402
from openflowsheet.studies.trust_region.study import (  # noqa: E402
    IN_PROCESS_BUDGET,
    OBJECTIVE_ID,
    TR_E2_BOX,
    StudyBudget,
    TrfStage,
    run_study,
)
from openflowsheet.studies.trust_region.trf_state import (  # noqa: E402
    PYOMO_VERSION,
    TRF_CONFIG_ID,
    TRF_MODULE_SHA256,
    TRSP_OPTIONS_ID,
    file_sha256,
    step_size_termination,
    trf_config_v1,
    trsp_executable,
)
from openflowsheet.studies.trust_region.truths import (  # noqa: E402
    FD_POLICY_ID,
    GradientCheck,
    ParentExperimentTruth,
    gradient_check,
)
from openflowsheet.thermo.pr_c1 import PrC1Provider  # noqa: E402

LOOP_PATH: Final = REPO_ROOT / "benchmarks" / "m02" / "c1-loop-standin.json"
INVENTORY_PATH: Final = REPO_ROOT / "benchmarks" / "m05" / "trsp-inventory-x86_64.json"
RECORDS: Final = REPO_ROOT / "benchmarks" / "m05" / "records"
#: §7.2: S0's nominal decision, K.
START_K: Final = 673.15

HOLDS: Final = "holds_by_construction"
#: §5.2's TR-E2 column of A1-A7 (A3 holds: the gradient is analytic).
TR_E2_ASSUMPTIONS: Final = (
    {"id": "A1", "status": HOLDS},
    {"id": "A2", "status": HOLDS},
    {"id": "A3", "status": HOLDS},
    {"id": "A4", "status": "limitation"},
    {"id": "A5", "status": HOLDS},
    {"id": "A6", "status": "limitation"},
    {"id": "A7", "status": "limitation"},
)
#: A smooth synthetic truth with FD gradients: A3 is qualified (§5.2's real-reactor A3 row).
FD_ASSUMPTIONS: Final = tuple(
    {"id": "A3", "status": "qualified(fd_gradient)"} if item["id"] == "A3" else item
    for item in TR_E2_ASSUMPTIONS
)


@dataclass(frozen=True)
class Case:
    name: str
    variant: Callable[[], variants.Variant]
    backend_for: Callable[[variants.Variant], Any]
    truth_class: type[ParentExperimentTruth]

    @property
    def finite_difference(self) -> bool:
        return self.truth_class is ParentExperimentTruth

    @property
    def stem(self) -> Path:
        return RECORDS / f"trust-region-study-{self.name.lower()}"


CASES: Final = {
    case.name: case
    for case in (
        Case("TR-E2", synthetic.synthetic_variant, synthetic.backend_for, synthetic.SyntheticTruth),
        Case("TR-E2-FD", synthetic.synthetic_variant, synthetic.backend_for, ParentExperimentTruth),
        Case(
            "LOOP-R",
            lambda: m04_parents.synthetic_variant(m04_parents.ROUGH_ID),
            m04_parents.backend_for(),
            ParentExperimentTruth,
        ),
    )
}


def register(variant: variants.Variant) -> None:
    """The test-only variant registered for this process (`tests/m02_variant_support.py`'s
    patch, without pytest)."""
    registry, registered = variants.registry, variants.registered_variant
    variants.registry = lambda: {**registry(), variant.variant_id: variant.sha256}  # type: ignore[assignment]
    variants.registered_variant = lambda variant_id: (  # type: ignore[assignment]
        variant if variant_id == variant.variant_id else registered(variant_id)
    )


def pinned(document: Mapping[str, Any], variant: variants.Variant) -> dict[str, Any]:
    """`document` with its reactor pinned to `variant` (M02's test helper)."""
    edited = copy.deepcopy(dict(document))
    for item in edited["instances"]:
        if item["id"] == "reactor":
            item["model"] = {
                "id": variant.model_id,
                "version": variant.variant_id,
                "artifact_ref": variant.sha256,
            }
    return edited


def link_start(projection: Any) -> tuple[Any, list[float]]:
    """The reactor link holder and its start inlet w₀ (the projection's start state at the link's
    inputs, as `basis._links` reads it)."""
    start = projection.state_of()
    holders = {holder.name: holder for holder in projection.holders}
    (entry, *_) = projection.source_map["external_links"]
    return holders[f"link:{entry['unit_id']}"], [start[i] for i in entry["input_variable_ids"]]


def environment() -> dict[str, Any]:
    import pyomo.contrib.trustregion as trustregion
    import pyomo.version

    inventory = json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))
    packages = {item["name"]: item["version"] for item in inventory["conda_packages"]}
    directory = Path(trustregion.__file__).parent
    return {
        "pyomo_version": pyomo.version.version,
        "trf_module_sha256": {name: file_sha256(directory / name) for name in TRF_MODULE_SHA256},
        "ipopt_version": packages["ipopt"],
        "mumps_version": packages["mumps-seq"] if "mumps-seq" in packages else packages["mumps"],
        "trsp_executable_sha256": file_sha256(trsp_executable()),
        "platform": f"{sys.platform}-{platform.machine()}",
    }


@dataclass
class Run:
    record: dict[str, Any]
    couplings: dict[str, bytes]
    ledger: bytes
    check: GradientCheck | None


def c1_parent(
    case: Case, root: Path, sink: Callable[[str, Mapping[str, Any]], None] | None = None
) -> tuple[C1Parent, dict[str, Any]]:
    """The case's C1 parent on a fresh experiment store under `root`, and its revision."""
    variant = case.variant()
    register(variant)
    document = pinned(json.loads(LOOP_PATH.read_text(encoding="utf-8")), variant)
    runner = ExperimentRunner(
        ExperimentStore(root),
        PrC1Provider(),
        EvaluationContext(model_version="m05-wo8", constants_sha256="0" * 64),
        backend_for=case.backend_for,
    )
    parent = C1Parent(
        document,
        runner,
        TR_E2_BOX,
        services=C1_PARENT_SERVICES,
        coupling_sink=sink,
        truth_class=case.truth_class,
    )
    return parent, document


def run_case(case: Case, root: Path, basis_policy: str = BASIS_POLICY_V2) -> Run:
    couplings: dict[str, bytes] = {}

    def sink(solve_id: str, record: Mapping[str, Any]) -> None:
        if solve_id in couplings:
            raise ValueError(f"duplicate solve id {solve_id!r}")
        couplings[solve_id] = canonical_json(record)

    parent, document = c1_parent(case, root, sink)
    projections: list[Any] = []
    checks: list[GradientCheck] = []

    def project_at(start: Any) -> Any:
        projection = parent.project_at(start)
        projections.append(projection)
        return projection

    def check_once(projection: Any) -> GradientCheck | None:
        """R-406: the study's `M05-fd-v2` check, inside the first stage-C run (its w₀)."""
        if checks:
            return None
        holder, w0 = link_start(projection)
        checks.append(gradient_check(holder, w0))
        return checks[0]

    (decision,) = parent.decisions
    sigma = step_size_termination((decision.tolerance,), (0.5 * (decision.upper - decision.lower),))
    assumptions = FD_ASSUMPTIONS if case.finite_difference else TR_E2_ASSUMPTIONS
    v2 = basis_policy == BASIS_POLICY_V2
    stage = TrfStage(
        project_at,
        m05_basis_v2 if v2 else m05_basis,
        trf_config_v1(sigma),
        assumptions,
        gradient_check=check_once if case.finite_difference else None,
        path_for=parent.decision_path if v2 else None,
    )
    limitations = ("fd_gradient",) if case.finite_difference else ()
    result = run_study(
        parent,
        decisions=parent.decisions,
        start={decision.name: START_K},
        stage_c=stage,
        budget=StudyBudget(IN_PROCESS_BUDGET),
        projection_check=parent.project_at,
        limitations=limitations,
    )
    ledger = canonical_json(
        [
            {
                "projection": index,
                "holder": holder.name,
                "requests": [
                    {k: v for k, v in entry.as_document().items() if k != "wall_s"}
                    for entry in holder.ledger
                ],
            }
            for index, projection in enumerate(projections)
            for holder in projection.holders
        ]
    )
    truth = parent.truth.describe()
    spec = {
        "case": case.name,
        "revision_sha256": document_sha256(document),
        "decisions": [{"id": decision.name, "lower": decision.lower, "upper": decision.upper}],
        "objective": {"id": OBJECTIVE_ID, "sense": parent.sense},
        "inequalities": sorted(item.inequality_id for item in parent.formulation.inequalities),
        "decision_tolerances": {decision.name: DECISION_TOLERANCE_K},
        "budgets": IN_PROCESS_BUDGET.as_document(),
        "configs": {
            "trf": TRF_CONFIG_ID,
            "trsp": TRSP_OPTIONS_ID,
            "fd": FD_POLICY_ID,
            "basis": basis_policy,
            "checks": "M05-checks-v1",
        },
        "truth": {key: truth[key] for key in ("kind", "id", "sha256", "synthetic", "gradient")},
        "surrogate": None,
    }
    check = checks[0] if checks else None
    record = result.as_document(
        spec=spec,
        environment=environment(),
        trf_theory="qualified(A3)" if case.finite_difference else "assumptions_hold",
        limitations=limitations,
        artifacts={"ledger": hashlib.sha256(ledger).hexdigest()},
        fd_check=None if check is None else check.as_document(),
    )
    assert PYOMO_VERSION == record["environment"]["pyomo_version"]
    return Run(record, couplings, ledger, check)


def write(case: Case, run: Run) -> None:
    stem = case.stem
    stem.parent.mkdir(parents=True, exist_ok=True)
    coupling = stem.with_suffix(".coupling")
    if coupling.exists():
        raise SystemExit(f"{coupling} exists: a committed run is never overwritten in place")
    coupling.mkdir()
    for solve_id, data in run.couplings.items():
        (coupling / f"{solve_id}.json").write_bytes(data)
    stem.with_suffix(".ledger.json").write_bytes(run.ledger)
    stem.with_suffix(".json").write_text(
        json.dumps(run.record, indent=1, sort_keys=False) + "\n", encoding="utf-8"
    )


def compare(case: Case, run: Run) -> list[str]:
    """G10 (§19.4): the fresh run against the committed files."""
    stem = case.stem
    recorded = json.loads(stem.with_suffix(".json").read_text(encoding="utf-8"))
    found = replay.replay_differences(recorded, run.record)
    if stem.with_suffix(".ledger.json").read_bytes() != run.ledger:
        found.append("ledger: the request sequence differs")
    directory = stem.with_suffix(".coupling")
    found += replay.persisted_violations(recorded, directory)
    for solve_id, data in run.couplings.items():
        persisted = directory / f"{solve_id}.json"
        if not persisted.is_file():
            found.append(f"coupling {solve_id}: not persisted")
            continue
        found += [
            f"coupling {solve_id}{line}"
            for line in replay.content_differences(
                json.loads(persisted.read_bytes()), json.loads(data)
            )
        ]
    if len(run.couplings) != len(recorded["artifacts"]["coupled_runs"]):
        found.append(f"{len(run.couplings)} fresh coupling records")
    return found


def summary(case: Case, run: Run) -> str:
    record = run.record
    outcomes = ",".join(f"{r['run_id']}:{r['outcome']}" for r in record["runs"])
    iterations = ",".join(str(len(r["iterations"])) for r in record["runs"])
    theta = ",".join(f"{r['theta_recheck']:.3g}" for r in record["runs"])
    statuses = ",".join(f"{c['candidate_id']}:{c['status']}" for c in record["candidates"])
    best = record["best"]
    decision = None if best is None else next(iter(best["decisions"].values()))
    check = run.check
    fd = "" if check is None else f" fd={check.selected_class}@{check.eta!r}/{check.status}"
    return (
        f"{case.name} status={record['status']} runs={outcomes} iterations={iterations} "
        f"theta_recheck={theta} candidates={statuses} T*={decision!r} "
        f"cold={record['accounting']['totals']['trf_cold']} "
        f"couplings={len(run.couplings)}{fd}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("case", choices=sorted(CASES))
    parser.add_argument("--replay", action="store_true", help="compare with the committed run")
    args = parser.parse_args(argv)
    case = CASES[args.case]
    with tempfile.TemporaryDirectory(prefix=f"m05-wo8-{case.name}-") as root:
        run = run_case(case, Path(root))
    if args.replay:
        found = compare(case, run)
        print(f"REPLAY {'PASS' if not found else 'FAIL'} {case.name} differences={len(found)}")
        for line in found[:40]:
            print(f"  {line}")
        return 0 if not found else 1
    write(case, run)
    print(summary(case, run))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
