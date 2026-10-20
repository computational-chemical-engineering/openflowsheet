"""M05 WO-9: the REAL study — `C1-LOOP-M02-v1` with the real reactor v3 (`c1-loop-real.json`,
`pymrm-6089593-g2-nz800-s123-v3`), its record, and its replay from the record (design note §12
WO-9 as amended by §20.7, §13 G10 and G11, §7.5 `M05-budget-v1`, §17.2 `M05-fd-v2`; facts F-9,
F-13, F-20, F-21).

Opt-in evidence (the `pymrm` tier): it needs the audited `nlp` environment (`.venv-nlp`, TRF and
the TRSP executable) for this process and the pinned reactor environment
(`python -m openflowsheet.adapters.pymrm.env build --variant pymrm-6089593-g2-nz800-s123-v3`) for
the reactor's child processes, which `ExperimentRunner` launches out of process.

**The run.** The composition root is `scripts/m05_wo8_runs.py`'s (R-387), with REAL's settings:
the real revision, unedited (the script checks that `benchmarks/m02/c1-loop-real.json` has the
same bytes after the run); `REAL_BOX` = [653.15, 693.15] K from S0's nominal 673.15 K;
`REAL_BUDGET` (≤ 400 cold experiments and ≤ 4 h for the study, ≤ 250 cold and ≤ 30 iterations per
TRF run); `ParentExperimentTruth` (FD gradients) with the study's `M05-fd-v2` check inside the
first stage-C run at its start inlet (R-406); `M05-basis-v2` (R-400) on `parent.decision_path`.
Stages A and B are skipped: M04's real surrogate is NOT_PROMOTABLE (§7.6's N6 branch), so the
study records stage A `surrogate_not_promoted` as LOOP-R does. The assumptions block is §5.2's
real-reactor column (A2 `assumed`, A3 `qualified(fd_gradient)`), and `claims.trf_theory` is
`qualified(A2,A3)` (§6.9; build log S66).

Writes, beside `<stem>.json`, the WO-8 sidecars (`.coupling/`, `.ledger.json`, `.store.json`,
`.environment.json`) and `<stem>.experiments.json`: every `request.json`, `result.json` and
`attempts/<n>.json` of the study's experiment store, by path relative to the store, as their exact
text (canonical JSON; the attempts' working directories and the locks are not kept). Its sha256 is
`artifacts.experiment_store` (build log S67). The record carries `provenance` (build log S65,
M07's FD-3): the commit, whether the tree was clean (the run refuses a dirty tree), and the study's
spent wall time.

**The replay** (`--replay`; G10's REAL part, F-20). The study is run again, the same way, over a
fresh store restored from `<stem>.experiments.json`, with a backend that handshakes like the real
one (the request's key carries the environment fingerprint) and refuses to execute: every reactor
request is served from the record, and a request the record cannot serve is a difference
(`replay diverged`). Served from the record, cold requests become store hits by design (F-20), so
the comparison (`m05_replay.real_replay_differences`, build log S68) is:

- the record: `m05_replay.replay_differences` with the counts that a store hit changes by design
  removed (`STORE_SERVED_COUNTS`), the ledger file's digest compared for shape, and the fresh
  study's cold counts all zero;
- the ledger: entry by entry, exact except that a recorded `cold` request with an experiment key
  is a `store_hit` with no execution in the replay;
- the store: no attempt added;
- each coupling record: M02's `iterate_differences` and `record_differences` (R-317 (b), under
  `T08-numerical-policy-v2`), then content equality of the rest without the unit entries'
  `attempts` and `cache_hit` (a store hit's), M02's `excluded` paths removed.

Prints one summary line; exit 0 iff the run's store bijection holds (G7, judged on the run: a
replay executes nothing), or the replay has no difference. Runs need `OMP_NUM_THREADS=1` (build
log S59):

    OMP_NUM_THREADS=1 PYOMO_CONFIG_DIR=.venv-nlp/share/pyomo PYTHONNOUSERSITE=1 \\
        PYTHONPATH=src:.reference-downloads/m03-ipopt/nlp-test-tools \\
        .venv-nlp/bin/python scripts/m05_wo9_real.py [--replay]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

import m05_wo8_runs as wo8

from openflowsheet.adapters.experiments.backends import OutOfProcessBackend, tube_document
from openflowsheet.adapters.experiments.runner import ExperimentRunner
from openflowsheet.adapters.experiments.store import ExperimentStore
from openflowsheet.application.trust_region_parent import C1_PARENT_SERVICES
from openflowsheet.canonical import canonical_json, document_sha256
from openflowsheet.compiled import EvaluationContext
from openflowsheet.studies.trust_region.basis import BASIS_POLICY_V2, m05_basis_v2
from openflowsheet.studies.trust_region.parent import DECISION_TOLERANCE_K, C1Parent
from openflowsheet.studies.trust_region.study import (
    OBJECTIVE_ID,
    REAL_BOX,
    REAL_BUDGET,
    StudyBudget,
    TrfStage,
    run_study,
)
from openflowsheet.studies.trust_region.trf_state import (
    PYOMO_VERSION,
    TRF_CONFIG_ID,
    TRSP_OPTIONS_ID,
    step_size_termination,
    trf_config_v1,
)
from openflowsheet.studies.trust_region.truths import (
    FD_POLICY_ID,
    GradientCheck,
    ParentExperimentTruth,
    gradient_check,
)
from openflowsheet.thermo.pr_c1 import PrC1Provider

replay = wo8.replay

REAL_LOOP_PATH: Final = wo8.REPO_ROOT / "benchmarks" / "m02" / "c1-loop-real.json"
STEM: Final = wo8.RECORDS / "trust-region-study-real"
CASE: Final = "REAL"
VARIANT_ID: Final = "pymrm-6089593-g2-nz800-s123-v3"
CONTEXT: Final = EvaluationContext(model_version="m05-wo9", constants_sha256="0" * 64)
#: §5.2's real-reactor column (stage C): A1, A4-A7 as TR-E2's ("Same"); A2 assumed (a
#: deterministic fixed-grid march, not proven C²); A3 qualified by FD gradients (build log S66).
REAL_ASSUMPTIONS: Final = (
    {"id": "A1", "status": wo8.HOLDS},
    {"id": "A2", "status": "assumed"},
    {"id": "A3", "status": "qualified(fd_gradient)"},
    {"id": "A4", "status": "limitation"},
    {"id": "A5", "status": wo8.HOLDS},
    {"id": "A6", "status": "limitation"},
    {"id": "A7", "status": "limitation"},
)
TRF_THEORY: Final = "qualified(A2,A3)"
LIMITATIONS: Final = ("fd_gradient",)
#: The experiment-store files the archive keeps, by their place under `<key[:2]>/<key>/`.
KEPT_FILES: Final = ("request.json", "result.json")


class ReplayDivergedError(RuntimeError):
    """A replay asked the reactor for a point its record does not hold."""


class RecordOnlyBackend:
    """The replay's backend: the real backend's handshake and identity (the request key carries
    the environment fingerprint), and no execution — a request that reaches `evaluate` missed
    the restored store, which is a divergence from the record."""

    def __init__(self, inner: OutOfProcessBackend, found: list[str]) -> None:
        self.inner = inner
        self.kind = inner.kind
        self.found = found

    def environment(self, directory: Path) -> Any:
        return self.inner.environment(directory)

    def identity(self, n_tubes: float) -> Mapping[str, Any]:
        return self.inner.identity(n_tubes)

    def evaluate(self, tube: Any, directory: Path, progress: Any, check: Any) -> Any:
        self.found.append(f"replay diverged: a cold execution at {tube_document(tube)!r}")
        raise ReplayDivergedError(self.found[-1])


def store_archive(root: Path) -> bytes:
    """`<stem>.experiments.json`: the exact text of every request, result and attempt record of
    the experiment store under `root`, by path relative to the store (module docstring)."""
    base = ExperimentStore(root).base
    kept: dict[str, str] = {}
    for path in sorted(base.glob("*/*/*.json")) + sorted(base.glob("*/*/attempts/*.json")):
        relative = path.relative_to(base)
        if relative.parts[0] == "locks":
            continue
        if len(relative.parts) == 3 and relative.name not in KEPT_FILES:
            continue
        kept[relative.as_posix()] = path.read_text(encoding="utf-8")
    return canonical_json(dict(sorted(kept.items())))


def restore_store(archive: bytes, root: Path) -> None:
    """The experiment store under `root` as `store_archive` kept it."""
    base = ExperimentStore(root).base
    for relative, text in json.loads(archive).items():
        path = base / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


@dataclass
class RealRun:
    run: wo8.Run
    archive: bytes
    diverged: list[str]


def run_real(root: Path, *, archive: bytes | None = None) -> RealRun:
    """The REAL study on the experiment store under `root`: fresh and empty for the run
    (F-18), restored from `archive` with the record-only backend for the replay."""
    state = wo8.git_state()
    if archive is None and not state[1]:
        raise SystemExit("the REAL run needs a clean tree: its record anchors the run commit (S65)")
    loop_bytes = REAL_LOOP_PATH.read_bytes()
    document = json.loads(loop_bytes)
    diverged: list[str] = []
    backend_for: Callable[[Any], Any] | None = None
    if archive is not None:
        restore_store(archive, root)

        def backend_for(variant: Any) -> Any:
            return RecordOnlyBackend(OutOfProcessBackend(variant), diverged)

    couplings: dict[str, bytes] = {}

    def sink(solve_id: str, record: Mapping[str, Any]) -> None:
        if solve_id in couplings:
            raise ValueError(f"duplicate solve id {solve_id!r}")
        couplings[solve_id] = canonical_json(record)

    runner = ExperimentRunner(
        ExperimentStore(root), PrC1Provider(), CONTEXT, backend_for=backend_for
    )
    parent = C1Parent(
        document,
        runner,
        REAL_BOX,
        services=C1_PARENT_SERVICES,
        coupling_sink=sink,
        truth_class=ParentExperimentTruth,
    )
    if parent.variant.variant_id != VARIANT_ID:
        raise SystemExit(f"the REAL revision binds {parent.variant.variant_id}, not {VARIANT_ID}")
    projections: list[Any] = []
    checks: list[GradientCheck] = []

    def project_at(start: Any, truth: Any = None) -> Any:
        projection = parent.project_at(start, truth=truth)
        projections.append(projection)
        return projection

    def check_once(projection: Any) -> GradientCheck | None:
        """R-406: the study's `M05-fd-v2` check, inside the first stage-C run (its w₀)."""
        if checks:
            return None
        holder, w0 = wo8.link_start(projection)
        checks.append(gradient_check(holder, w0))
        return checks[0]

    (decision,) = parent.decisions
    sigma = step_size_termination((decision.tolerance,), (0.5 * (decision.upper - decision.lower),))
    stage = TrfStage(
        project_at,
        m05_basis_v2,
        trf_config_v1(sigma),
        REAL_ASSUMPTIONS,
        gradient_check=check_once,
        path_for=parent.decision_path,
    )
    budget = StudyBudget(REAL_BUDGET)
    result = run_study(
        parent,
        decisions=parent.decisions,
        start={decision.name: wo8.START_K},
        stage_c=stage,
        budget=budget,
        projection_check=parent.project_at,
        limitations=LIMITATIONS,
    )
    wall_s = budget.wall_s
    if REAL_LOOP_PATH.read_bytes() != loop_bytes:
        raise SystemExit(f"{REAL_LOOP_PATH} changed during the run (AQ2: it must not)")
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
    stored = store_archive(root)
    truth = parent.truth.describe()
    spec = {
        "case": CASE,
        "revision_sha256": document_sha256(document),
        "decisions": [{"id": decision.name, "lower": decision.lower, "upper": decision.upper}],
        "objective": {"id": OBJECTIVE_ID, "sense": parent.sense},
        "inequalities": sorted(item.inequality_id for item in parent.formulation.inequalities),
        "decision_tolerances": {decision.name: DECISION_TOLERANCE_K},
        "budgets": REAL_BUDGET.as_document(),
        "configs": {
            "trf": TRF_CONFIG_ID,
            "trsp": TRSP_OPTIONS_ID,
            "fd": FD_POLICY_ID,
            "basis": BASIS_POLICY_V2,
            "checks": "M05-checks-v1",
        },
        "truth": {key: truth[key] for key in ("kind", "id", "sha256", "synthetic", "gradient")},
        "surrogate": None,
    }
    check = checks[0] if checks else None
    record = result.as_document(
        spec=spec,
        environment=wo8.environment(),
        trf_theory=TRF_THEORY,
        limitations=LIMITATIONS,
        artifacts={
            "ledger": hashlib.sha256(ledger).hexdigest(),
            "experiment_store": hashlib.sha256(stored).hexdigest(),
        },
        fd_check=None if check is None else check.as_document(),
    )
    assert PYOMO_VERSION == record["environment"]["pyomo_version"]
    index = wo8.store_index(root)
    bijection = replay.store_bijection_violations(
        index,
        json.loads(ledger),
        {solve_id: json.loads(data) for solve_id, data in couplings.items()},
    )
    run = wo8.Run(
        record,
        couplings,
        ledger,
        check,
        canonical_json(index),
        bijection,
        wo8.provenance(state, wall_s),
    )
    return RealRun(run, stored, diverged)


def write(real: RealRun) -> None:
    wo8.write_files(STEM, real.run)
    STEM.with_suffix(".experiments.json").write_bytes(real.archive)


def compare(real: RealRun, *, stem: Path = STEM) -> list[str]:
    """G10's REAL part (F-20): the replay from the record against the committed files at `stem`
    (M05's record by default; M07's journey passes its R3 re-run's, M07 spec A2.4)."""
    found = list(real.diverged)
    recorded = json.loads(stem.with_suffix(".json").read_text(encoding="utf-8"))
    found += replay.real_replay_differences(recorded, real.run.record)
    found += replay.served_ledger_differences(
        json.loads(stem.with_suffix(".ledger.json").read_bytes()), json.loads(real.run.ledger)
    )
    if stem.with_suffix(".store.json").read_bytes() != real.run.store:
        found.append("store: the replay added or lost attempt records")
    directory = stem.with_suffix(".coupling")
    found += replay.persisted_violations(recorded, directory)
    for solve_id, data in real.run.couplings.items():
        persisted = directory / f"{solve_id}.json"
        if not persisted.is_file():
            found.append(f"coupling {solve_id}: not persisted")
            continue
        found += [
            f"coupling {solve_id}{line}"
            for line in replay.served_coupling_differences(
                json.loads(persisted.read_bytes()), json.loads(data)
            )
        ]
    if len(real.run.couplings) != len(recorded["artifacts"]["coupled_runs"]):
        found.append(f"{len(real.run.couplings)} fresh coupling records")
    return found


def extrapolated_count(ledger: list[Mapping[str, Any]]) -> tuple[int, int]:
    """(extrapolated, all) truth requests of the ledger (§7.1: counted per evaluation)."""
    entries = [entry for block in ledger for entry in block["requests"]]
    return sum(1 for entry in entries if entry["extrapolated"]), len(entries)


def summary(real: RealRun) -> str:
    run, record = real.run, real.run.record
    outcomes = ",".join(f"{r['run_id']}:{r['outcome']}" for r in record["runs"])
    iterations = ",".join(str(len(r["iterations"])) for r in record["runs"])
    cold = ",".join(str(r["cold"]) for r in record["runs"])
    basis = ",".join(
        f"{r['run_id']}:{link['status']}/{link['stencil']}"
        for r in record["runs"]
        for link in (r.get("basis") or {}).get("links", {}).values()
    )
    statuses = ",".join(f"{c['candidate_id']}:{c['status']}" for c in record["candidates"])
    best = record["best"]
    decision = None if best is None else next(iter(best["decisions"].values()))
    fd = record["fd_check"] or {}
    extrapolated, requests = extrapolated_count(json.loads(run.ledger))
    return (
        f"{CASE} status={record['status']} runs={outcomes} iterations={iterations} "
        f"run_cold={cold} basis={basis} candidates={statuses} T*={decision!r} "
        f"fd={fd.get('class')}@{fd.get('selected_eta')!r}/{fd.get('result')} "
        f"extrapolated={extrapolated}/{requests} limitations={','.join(record['limitations'])} "
        f"study_cold={record['accounting']['budgets']['cold_used']} "
        f"wall_s={run.provenance['wall_s']:.0f} couplings={len(run.couplings)} "
        f"store_bytes={len(real.archive)} bijection_violations={len(run.bijection)}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--replay", action="store_true", help="replay from the committed record")
    args = parser.parse_args(argv)
    if os.environ.get("OMP_NUM_THREADS") != "1":
        raise SystemExit("the runs need OMP_NUM_THREADS=1 (build log S59)")
    archive = STEM.with_suffix(".experiments.json").read_bytes() if args.replay else None
    if not args.replay and STEM.with_suffix(".json").exists():
        raise SystemExit(f"{STEM}.json exists: a committed run is never overwritten in place")
    with tempfile.TemporaryDirectory(prefix="m05-wo9-real-") as root:
        real = run_real(Path(root), archive=archive)
    if args.replay:
        # G7's store bijection is the record's (its ledger's executions); a replay executes
        # nothing, so its own store has attempts no replayed request claims, by design.
        found = compare(real)
        print(f"REPLAY {'PASS' if not found else 'FAIL'} {CASE} differences={len(found)}")
        for line in found[:40]:
            print(f"  {line}")
        return 0 if not found else 1
    for line in real.run.bijection[:40]:
        print(f"  bijection: {line}")
    write(real)
    print(summary(real))
    return 0 if not real.run.bijection else 1


if __name__ == "__main__":
    raise SystemExit(main())
