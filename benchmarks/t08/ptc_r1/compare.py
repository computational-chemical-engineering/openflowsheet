"""PTC-R1's comparison harness: 441 registered starts, each run by both arms (build-first §A4.5).

Spec `docs/derivations/T08-build-first-spec.md` Part A: §A4.2 (the starts), §A4.3 (classes), §A4.5
(arms and harness), §A4.6 (the git order), as amended by Amendment 1 (§Am1.1: `(A, B, C)` with an
inert `2⁻¹⁰` mol/s `C` trace; B21's trace clause). ADR 0023.

**Committed not run.** This file lands at `C_case` with `revision.json` and `case.json`; nothing
here was executed on the PTC-R1 flowsheet before or at that commit (§A4.6). `python -m
benchmarks.t08.ptc_r1.compare --run` is W5's command, run only after the design-lane review and
Frank's go-ahead. It refuses to start unless `case.json` recomputes from the code and files it
names (`case_differences`).

**One run.** For each start and arm the harness makes exactly T06's revision-path calls
(`benchmarks/t06/ensemble.py`, `_run_revision`): `bind_revision_flowsheet` → `plan_revision` →
`execute_plan(user_start=start)` → `verify_revision` when the plan ends `CONVERGED`. A fresh
binding per run, so no provider state or cache crosses runs. The one thing added is a capture of
the Newton core's `blocked_by` on `BOUND_BLOCKED` (a shim that calls through unchanged, like the
T06 harness's timing shims), because the region keeps a PTC attempt's rejections
(`RegionAttempt.ptc`) but not Newton's blocking set, and B21 asks whether any blocker is a `C`
column.

**Per run** (§A4.5, B21): arm, `(i, j)`, outcome, each attempt's outcome and accepted steps, the
final state in `variable_ids` order, the class (§A4.3), the certificate's verdict and check ids,
the property-call meter, which budget a `BUDGET_EXHAUSTED` run spent (`RegionResult.budget`), the
final `S1.n.C` and `S2.n.C`, and every bound block with the columns it names. The machine class
and the run's provenance are the document's (T06's `machine_class`, `provenance`).

**Preconditions of `--run`** (review S3): `case.json` recomputes, the tree is clean, and
`results-<machine class>.json` does not exist yet — a result is never overwritten, as a
registration is never rewritten.

**Outputs:** `results-<machine class>.json` (the records and the summary) and
`results-<machine class>.md` (the summary with both 21 × 21 maps). The summary reports; it
judges nothing. B21–B23 are judged by the design lane's `verdict` against §A4.4.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import time
from collections import Counter
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import asdict, replace
from functools import cache
from pathlib import Path
from typing import Any, Final

import yaml

import openflowsheet.orchestrator.region as region_module
from benchmarks.t06.ensemble import host, provenance
from openflowsheet.application.policies import T06_REVISION_V2, T08_PTC_V1, T08_WARM_V1
from openflowsheet.application.revision_binding import RevisionBinding, bind_revision_flowsheet
from openflowsheet.application.revisions import content_hash
from openflowsheet.orchestrator import revision
from openflowsheet.orchestrator.execution import ExecutionPlan
from openflowsheet.orchestrator.executor import PlanResult, execute_plan
from openflowsheet.orchestrator.region import RegionResult
from openflowsheet.orchestrator.trace import SolvePolicy
from openflowsheet.run.manifest import policy_sha256
from openflowsheet.verify.certificate import verify_revision

__all__ = [
    "ARMS",
    "CASE_FILE",
    "C_A1",
    "C_REG",
    "NEWTON_ARM",
    "PTC_ARM",
    "REVISION_FILE",
    "case_differences",
    "case_document",
    "classify",
    "registered_policies",
    "render",
    "run_start",
    "start_rows",
    "start_vector",
    "starts_sha256",
    "summarize",
]

CASE_DIR: Final = Path(__file__).resolve().parent
REPO_ROOT: Final = CASE_DIR.parents[2]
REVISION_FILE: Final = CASE_DIR / "revision.json"
CASE_FILE: Final = CASE_DIR / "case.json"
REFERENCE_FILE: Final = REPO_ROOT / "benchmarks" / "t08" / "build_first_reference.yaml"
CASE_FORMAT: Final = "t08-ptc-r1-case-v1"
RESULTS_FORMAT: Final = "t08-ptc-r1-results-v1"

#: §A4.6 as amended: the design commits that precede `C_case` (`C_reg → C_A1 → C_case → C_res`).
C_REG: Final = "9f5f29d7063ae5102c535d94d5f18f20db6480c2"
C_A1: Final = "30243f9c9956fb7ec6970f62156f864cd35d0aa0"

#: §A4.5: the two arms, not offered — `T06-revision-v2` with `eo_recovery = "none"` and the core
#: set; the comparison is of cores, not of recoveries (T04 §8.3). PTC at T04 §7.7's constants.
NEWTON_ARM: Final[SolvePolicy] = replace(
    T06_REVISION_V2,
    policy_id="T08-PTC-R1-newton",
    globalization=replace(T06_REVISION_V2.globalization, eo_core="newton", eo_recovery="none"),
)
PTC_ARM: Final[SolvePolicy] = replace(
    T06_REVISION_V2,
    policy_id="T08-PTC-R1-ptc",
    globalization=replace(T06_REVISION_V2.globalization, eo_core="ptc", eo_recovery="none"),
)
ARMS: Final[Mapping[str, SolvePolicy]] = {"newton": NEWTON_ARM, "ptc": PTC_ARM}

#: The revision's streams and unit (`revision.json`): feed `S1` → `U-CSTR` → `S2` → sink.
INLET, OUTLET, UNIT = "S1", "S2", "U-CSTR"
COMPONENTS: Final = ("A", "B", "C")
#: Amendment 1: the trace's two columns, which B21 follows through every run.
C_COLUMNS: Final = (f"{INLET}.n.C", f"{OUTLET}.n.C")
CLASSES: Final = ("LOW", "MID", "HIGH", "FAIL")
ROOTS: Final = ("LOW", "MID", "HIGH")


def registered_policies() -> dict[str, SolvePolicy]:
    """The four policies `case.json` registers (build-first §I W3): the offered `T08-ptc-v1` and
    `T08-warm-v1`, and the two arms."""
    return {policy.policy_id: policy for policy in (T08_PTC_V1, T08_WARM_V1, NEWTON_ARM, PTC_ARM)}


# -- the registered inputs --------------------------------------------------------------------


@cache
def reference() -> Mapping[str, Any]:
    """The design lane's YAML (`t08_build_first_reference.py`), read once."""
    loaded: Mapping[str, Any] = yaml.safe_load(REFERENCE_FILE.read_text(encoding="utf-8"))
    return loaded


def revision_document() -> dict[str, Any]:
    document: dict[str, Any] = json.loads(REVISION_FILE.read_text(encoding="utf-8"))
    return document


def start_rows() -> list[list[Any]]:
    """§A4.2's 441 rows `[i, j, n_A, n_B, T, Q]`, as the YAML writes them (j outer, i inner)."""
    rows: list[list[Any]] = reference()["starts"]["rows"]
    return rows


def starts_sha256(rows: Sequence[Sequence[Any]]) -> str:
    """The generator's digest of the rows: SHA-256 of their compact JSON (B07)."""
    return hashlib.sha256(json.dumps(rows, separators=(",", ":")).encode("ascii")).hexdigest()


def start_vector(row: Sequence[Any]) -> dict[str, float]:
    """§A4.2 as amended: a start over every declaration variable. The outlet's `n_A`, `n_B`, `T`
    and the duty `Q` are the row's; `n_C` and `P` are `starts.fixed`'s; every feed coordinate is
    at its fixed value (the realization's feed, `T_f`, `P`)."""
    realization = reference()["case"]["realization"]
    fixed = reference()["starts"]["fixed"]
    vector = {f"{INLET}.n.{c}": float(realization[f"feed_{c}_mol_s"]) for c in COMPONENTS}
    vector[f"{INLET}.T"] = float(realization["feed_T_K"])
    vector[f"{INLET}.P"] = float(realization["feed_P_Pa"])
    vector[f"{OUTLET}.n.A"] = float(row[2])
    vector[f"{OUTLET}.n.B"] = float(row[3])
    vector[f"{OUTLET}.n.C"] = float(fixed["n_C_mol_s"])
    vector[f"{OUTLET}.T"] = float(row[4])
    vector[f"{OUTLET}.P"] = float(fixed["P_Pa"])
    vector[f"{UNIT}.Q"] = float(row[5])
    return vector


# -- the registration record (B20) ------------------------------------------------------------


def case_document() -> dict[str, Any]:
    """What `case.json` holds, recomputed from the code and the files it names (§A4.6, B20)."""
    rows = start_rows()
    document = revision_document()
    return {
        "format": CASE_FORMAT,
        "case": "PTC-R1",
        "specification": (
            "docs/derivations/T08-build-first-spec.md §A4.6 as amended by Amendment 1 (§Am1.1); "
            "ADR 0023 D5 (Amendment 1)"
        ),
        "git_order": {"C_reg": C_REG, "C_A1": C_A1},
        "reference": {
            "path": REFERENCE_FILE.relative_to(REPO_ROOT).as_posix(),
            "sha256": hashlib.sha256(REFERENCE_FILE.read_bytes()).hexdigest(),
        },
        "starts": {"count": len(rows), "sha256_of_compact_json": starts_sha256(rows)},
        "revision": {
            "path": REVISION_FILE.relative_to(REPO_ROOT).as_posix(),
            "revision_id": document["revision_id"],
            "content_sha256": content_hash(document),
        },
        "policies": {
            policy_id: policy_sha256(policy)
            for policy_id, policy in sorted(registered_policies().items())
        },
        "arms": {arm: policy.policy_id for arm, policy in ARMS.items()},
        "harness": Path(__file__).resolve().relative_to(REPO_ROOT).as_posix(),
    }


def case_differences() -> list[str]:
    """The members where the committed `case.json` differs from `case_document()`; empty when
    the registration recomputes."""
    committed = json.loads(CASE_FILE.read_text(encoding="utf-8"))
    expected = case_document()
    return sorted(
        key for key in set(committed) | set(expected) if committed.get(key) != expected.get(key)
    )


# -- one run ----------------------------------------------------------------------------------


def classify(outcome: str, state: Mapping[str, float] | None) -> tuple[str, float | None]:
    """§A4.3: `LOW`, `MID` or `HIGH` when the plan ended `CONVERGED` within the radius of that
    root (dimensionless ∞-norm, §A1.5's map), otherwise `FAIL`; with the distance to the nearest
    root (`None` when there is no state)."""
    if state is None:
        return "FAIL", None
    closed = reference()["closed_form"]
    radius = float(closed["classification"]["radius_dimensionless_inf_norm"])
    realization = reference()["case"]["realization"]
    key_feed = float(realization["feed_B_mol_s"])
    t_f, t_s = float(realization["feed_T_K"]), float(realization["T_scale_K"])
    x1 = 1.0 - state[f"{OUTLET}.n.B"] / key_feed
    x2 = (state[f"{OUTLET}.T"] - t_f) / t_s
    distances = {
        name: max(
            abs(x1 - float(closed["steady_states"][name]["x1"])),
            abs(x2 - float(closed["steady_states"][name]["x2"])),
        )
        for name in ROOTS
    }
    nearest = min(ROOTS, key=lambda name: distances[name])
    if outcome == "CONVERGED" and distances[nearest] <= radius:
        return nearest, distances[nearest]
    return "FAIL", distances[nearest]


@contextmanager
def _newton_blocks(captured: list[tuple[str, ...]]) -> Iterator[None]:
    """Capture `blocked_by` of every Newton core result that ends `BOUND_BLOCKED`. Calls through
    unchanged; the original is restored whatever happens."""
    original: Callable[..., Any] = getattr(region_module, "solve_newton")  # noqa: B009

    def capturing(*args: Any, **kwargs: Any) -> Any:
        result = original(*args, **kwargs)
        if result.outcome == "BOUND_BLOCKED":
            captured.append(tuple(result.blocked_by))
        return result

    setattr(region_module, "solve_newton", capturing)  # noqa: B010 - a module attribute
    try:
        yield
    finally:
        setattr(region_module, "solve_newton", original)  # noqa: B010


def _blocks(detail: RegionResult, newton: Sequence[tuple[str, ...]]) -> list[dict[str, Any]]:
    """Every bound block of the run: each PTC rejection `bound_blocked` (with its columns), each
    PTC polish rejected on a bound (its columns are not recorded by the core), and each Newton
    `BOUND_BLOCKED` (its `blocked_by`)."""
    blocks: list[dict[str, Any]] = []
    for index, attempt in enumerate(detail.attempts):
        if attempt.ptc is None:
            continue
        for rejection in attempt.ptc.rejections:
            if rejection.reason == "bound_blocked":
                blocks.append(
                    {
                        "core": "ptc",
                        "attempt": index,
                        "pseudo_step": rejection.index,
                        "retry": rejection.retry,
                        "columns": list(rejection.blocked_by),
                    }
                )
        if attempt.ptc.polish == "rejected:bound_blocked":
            blocks.append({"core": "ptc_polish", "attempt": index, "columns": None})
    blocks.extend({"core": "newton", "columns": list(columns)} for columns in newton)
    return blocks


def run_start(arm: str, row: Sequence[Any]) -> dict[str, Any]:
    """One registered start under one arm, cold (§A4.5). An exception that is not a typed outcome
    is recorded as a crash and never propagates; B21 counts it."""
    policy = ARMS[arm]
    out: dict[str, Any] = {
        "arm": arm,
        "i": int(row[0]),
        "j": int(row[1]),
        "outcome": None,
        "message": "",
        "attempts": [],
        "accepted_steps": None,
        "state": None,
        "class": "FAIL",
        "distance": None,
        "certificate": None,
        "counters": None,
        "budget": None,
        "c_final": None,
        "bound_blocks": [],
        "c_blockers": [],
        "crash": None,
    }
    try:
        document = revision_document()
        binding = bind_revision_flowsheet(document)
        if not isinstance(binding, RevisionBinding):
            raise TypeError(f"revision.json does not bind: {binding}")
        plan, _ = revision.plan_revision(binding, policy)
        if not isinstance(plan, ExecutionPlan):
            raise TypeError(f"revision.json does not plan: {plan}")
        newton: list[tuple[str, ...]] = []
        with _newton_blocks(newton):
            run: PlanResult = execute_plan(
                plan=plan,
                flowsheet=binding.flowsheet,
                spec=binding.spec,
                policy=policy,
                user_start=start_vector(row),
            )
        # The typed end is recorded before anything else is read (review S1): a plan without
        # exactly one `solve_eo` step is still a crash below, but keeps its outcome and meter.
        out.update(
            outcome=run.outcome,
            message=(run.message or "").splitlines()[0] if run.message else "",
            counters=asdict(run.counters),
        )
        (step,) = [step for step in run.steps if step.kind == "solve_eo"]
        detail = step.detail
        final: Mapping[str, float] | None = run.state
        if isinstance(detail, RegionResult):
            final = detail.state
            out["attempts"] = [
                [attempt.outcome, attempt.solver_outcome, attempt.iterations]
                for attempt in detail.attempts
            ]
            out["bound_blocks"] = _blocks(detail, newton)
            out["budget"] = detail.budget
        out["accepted_steps"] = step.iterations
        if final is not None:
            out["state"] = [[name, final[name]] for name in binding.spec.variable_ids]
            out["c_final"] = {column: final[column] for column in C_COLUMNS}
        out["c_blockers"] = [
            block
            for block in out["bound_blocks"]
            if block["columns"] is not None and set(block["columns"]) & set(C_COLUMNS)
        ]
        out["class"], out["distance"] = classify(run.outcome, final)
        if run.outcome == "CONVERGED" and run.state is not None:
            certificate = verify_revision(
                binding, document, run, solve_plan=plan.steps[-1].solve_plan
            )
            out["certificate"] = {
                "verdict": certificate.verification_status,
                "check_ids": [check.id for check in certificate.checks],
                "not_passed": sorted(
                    check.id
                    for check in certificate.checks
                    if check.result not in ("pass", "not_applicable")
                ),
            }
    except Exception as error:  # recorded, never handled: B21 requires every run to end typed
        out["crash"] = f"{type(error).__name__}: {str(error).splitlines()[0] if str(error) else ''}"
    return out


# -- the summary (reports; judges nothing) ----------------------------------------------------


def summarize(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Per arm: class counts, the 21 × 21 class map (rows `j` = 0…20, columns `i`), outcomes,
    accepted steps, property calls and agreement with the physical label (B08); B21's facts; the
    reached sets' difference and PTC's `MID` starts, as facts for the verdict (§A4.4).

    B21's facts include what the P-budget ruling and the C-blocker clause need (review S2, §3.1):
    runs with a bound block whose columns are not recorded (a PTC polish), `BUDGET_EXHAUSTED`
    runs by budget, and the most attempts and property calls of any run."""
    labels = reference()["geometry"]["physical_basin_labels_rows_j0_to_j20"]
    trace = float(reference()["starts"]["fixed"]["n_C_mol_s"])
    arms: dict[str, Any] = {}
    reached: dict[str, set[tuple[int, int]]] = {}
    for arm in ARMS:
        mine = [r for r in records if r["arm"] == arm]
        grid = [["." for _ in range(21)] for _ in range(21)]
        for r in mine:
            grid[r["j"]][r["i"]] = r["class"][0]
        reached[arm] = {(r["i"], r["j"]) for r in mine if r["class"] in ("LOW", "HIGH")}
        steps = [r["accepted_steps"] for r in mine if r["accepted_steps"] is not None]
        arms[arm] = {
            "policy_id": ARMS[arm].policy_id,
            "runs": len(mine),
            "classes": {name: sum(r["class"] == name for r in mine) for name in CLASSES},
            "map_rows_j0_to_j20": ["".join(row) for row in grid],
            "outcomes": dict(sorted(Counter(str(r["outcome"]) for r in mine).items())),
            "accepted_steps_total": sum(steps),
            "accepted_steps_max": max(steps, default=None),
            "property_calls_total": sum(
                r["counters"]["property_calls"] for r in mine if r["counters"] is not None
            ),
            "agrees_with_physical_label": sum(
                r["class"] in ("LOW", "HIGH") and r["class"][0] == labels[r["j"]][r["i"]]
                for r in mine
            ),
        }
    deviations = [
        abs(value - trace)
        for r in records
        if r["c_final"] is not None
        for value in r["c_final"].values()
    ]
    b21 = {
        "runs": len(records),
        "crashes": sum(r["crash"] is not None for r in records),
        "converged_unclassified": sum(
            r["outcome"] == "CONVERGED" and r["class"] == "FAIL" for r in records
        ),
        "converged_not_verified": sum(
            r["outcome"] == "CONVERGED"
            and (r["certificate"] is None or r["certificate"]["verdict"] != "VERIFIED")
            for r in records
        ),
        "runs_without_c_final": sum(r["c_final"] is None for r in records),
        "c_final_max_abs_deviation_mol_s": max(deviations, default=None),
        "runs_with_c_blockers": sum(bool(r["c_blockers"]) for r in records),
        "runs_with_unattributed_bound_blocks": sum(
            any(block["columns"] is None for block in r["bound_blocks"]) for r in records
        ),
        "budget_exhausted": dict(
            sorted(
                Counter(
                    str(r["budget"]) for r in records if r["outcome"] == "BUDGET_EXHAUSTED"
                ).items()
            )
        ),
        "runs_without_exactly_one_attempt": sum(len(r["attempts"]) != 1 for r in records),
        "crashes_with_typed_outcome": sum(
            r["crash"] is not None and r["outcome"] is not None for r in records
        ),
        "max_attempts_per_run": max((len(r["attempts"]) for r in records), default=None),
        "max_property_calls_per_run": max(
            (r["counters"]["property_calls"] for r in records if r["counters"] is not None),
            default=None,
        ),
    }
    ptc_only = sorted(reached["ptc"] - reached["newton"])
    return {
        "arms": arms,
        "b21": b21,
        "ptc_reached_newton_not": [list(start) for start in ptc_only],
        "ptc_mid_starts": sorted(
            [r["i"], r["j"]] for r in records if r["arm"] == "ptc" and r["class"] == "MID"
        ),
    }


def _finite(value: Any) -> Any:
    """Strict JSON (review N7): a non-finite float is written as ``null``, never as ``NaN``."""
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, Mapping):
        return {key: _finite(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_finite(item) for item in value]
    return value


def render(document: Mapping[str, Any]) -> str:
    """The summary as Markdown: provenance, class counts, B21's facts and both maps."""
    summary = document["summary"]
    lines = [
        f"# PTC-R1 comparison — {document['host']['machine_class']}",
        "",
        f"Commit `{document['provenance']['commit']}` (tree clean: "
        f"{document['provenance']['tree_clean']}); case `{document['case_sha256']}`.",
        "Reported, not judged: B21–B23 are the design lane's `verdict` against build-first §A4.4.",
        "",
        "| arm | policy | LOW | MID | HIGH | FAIL | accepted steps | property calls |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for arm, entry in summary["arms"].items():
        classes = entry["classes"]
        lines.append(
            f"| {arm} | `{entry['policy_id']}` | {classes['LOW']} | {classes['MID']} | "
            f"{classes['HIGH']} | {classes['FAIL']} | {entry['accepted_steps_total']} | "
            f"{entry['property_calls_total']} |"
        )
    lines += ["", "B21 facts:", ""]
    lines += [f"- `{key}`: {value}" for key, value in summary["b21"].items()]
    lines += [
        "",
        f"Starts PTC reaches and Newton does not: {len(summary['ptc_reached_newton_not'])}; "
        f"PTC `MID` starts: {len(summary['ptc_mid_starts'])}.",
    ]
    for arm, entry in summary["arms"].items():
        title = f"{arm} class map (rows j = 20…0 from the top, columns i = 0…20):"
        lines += ["", title, "", "```"]
        lines += list(reversed(entry["map_rows_j0_to_j20"]))
        lines += ["```"]
    return "\n".join(lines) + "\n"


# -- the command ------------------------------------------------------------------------------


def _write_case() -> int:
    if CASE_FILE.exists():
        print(f"{CASE_FILE} exists; a registration is never rewritten (§A4.6)", file=sys.stderr)
        return 1
    CASE_FILE.write_text(json.dumps(case_document(), indent=2) + "\n", encoding="utf-8")
    print(f"wrote {CASE_FILE}")
    return 0


def _run(out_dir: Path) -> int:
    differences = case_differences()
    if differences:
        print(f"case.json does not recompute: {differences}; nothing run", file=sys.stderr)
        return 1
    origin = provenance(REPO_ROOT)
    if not origin["tree_clean"]:
        print("the tree is not clean; a result must be attributable to its commit", file=sys.stderr)
        return 1
    machine = host()
    stem = out_dir / f"results-{machine['machine_class']}"
    if stem.with_suffix(".json").exists():
        print(f"{stem}.json exists; a result is never overwritten", file=sys.stderr)
        return 1
    document: dict[str, Any] = {
        "format": RESULTS_FORMAT,
        "provenance": origin,
        "host": machine,
        "case_sha256": hashlib.sha256(CASE_FILE.read_bytes()).hexdigest(),
    }
    began = time.perf_counter()
    records = [run_start(arm, row) for row in start_rows() for arm in ARMS]
    document["wall_time_s"] = time.perf_counter() - began
    document["summary"] = summarize(records)
    document["records"] = records
    stem.with_suffix(".json").write_text(
        json.dumps(_finite(document), indent=1, allow_nan=False) + "\n", encoding="utf-8"
    )
    stem.with_suffix(".md").write_text(render(document), encoding="utf-8")
    print(f"wrote {stem}.json and {stem}.md")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--run", action="store_true", help="W5: run the 882 runs and write results")
    action.add_argument("--check-case", action="store_true", help="recompute case.json")
    action.add_argument("--write-case", action="store_true", help="write case.json once (C_case)")
    parser.add_argument("--out-dir", type=Path, default=CASE_DIR)
    arguments = parser.parse_args(argv)
    if arguments.write_case:
        return _write_case()
    if arguments.check_case:
        differences = case_differences()
        print("case.json recomputes" if not differences else f"differs: {differences}")
        return 1 if differences else 0
    return _run(arguments.out_dir)


if __name__ == "__main__":
    sys.exit(main())
