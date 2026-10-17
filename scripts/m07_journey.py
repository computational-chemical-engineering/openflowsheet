#!/usr/bin/env python3
"""M07 — the reference journey (M07 spec §4–§6; ADR 0041; R-331 to R-337).

One decision, SPEC-S3-T of `C1-LOOP-M02-v1` (the reactor-inlet temperature, box
[653.15, 693.15] K), taken through four rungs of reactor fidelity:

- **R0** the synthetic stand-in on the nine-point grid (in process; the default gate runs it);
- **R1** the parent (`c1.reactor` v3) on the same grid, each point with M05's noise floor e_k and
  M05 P3's constraint values;
- **R2** M04's committed verdict for the bound parent: `SURROGATE_NOT_PROMOTABLE` evaluates
  nothing; a `PROMOTABLE` verdict needs nine surrogate-backed loop evaluations;
- **R3** M05's REAL study record (carried by identity, spec §4.6).

The rules of spec §4.4 (rung decision, indifference set, before/after pairs and their
fidelity-effect class, the truth check TC-1, bound activity, the journey's decision) are
implemented here again, independently of the reference generator
`docs/derivations/scripts/m07_reference.py`; the tests compare the two on the registered fixtures.

Usage (``PYTHONPATH=src``)::

    python scripts/m07_journey.py run --out benchmarks/m07/journey/<J> --artifacts <dir> \\
        [--m05-record <path>] [--dry-run]
    python scripts/m07_journey.py check  benchmarks/m07/journey/<J>
    python scripts/m07_journey.py render benchmarks/m07/journey/<J>
    python scripts/m07_journey.py replay benchmarks/m07/journey/<J>

Exit codes: 0 done (or `check` accepts); 1 `check` rejects; 2 usage, or `replay` (WO-4, not
implemented: it refuses rather than pretends); 3 a rung is `UNSUPPORTED` — the record and the
report are written all the same (spec §4.6, A14).

`--dry-run` plays R1 with the stand-in (spec §11 A10). Such a record carries
`synthetic_dry_run: true` and is never W25 evidence. Build decisions: `docs/design/M07-build-
decisions.md` (J1…).
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import os
import platform
import re
import subprocess
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final, Protocol

ROOT: Final = Path(__file__).resolve().parent.parent
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

REGISTRATION_PATH: Final = ROOT / "benchmarks" / "m07" / "registration.json"
REG: Final[dict[str, Any]] = json.loads(REGISTRATION_PATH.read_text(encoding="utf-8"))
JOURNEY: Final[dict[str, Any]] = REG["journey"]
REPORT: Final[dict[str, Any]] = REG["report"]
DECISION: Final[dict[str, Any]] = JOURNEY["decision"]

SCHEMA: Final = "m07-journey-v1"
RECORD_NAME: Final = "journey.json"
REPORT_NAME: Final = "journey.md"
GRID_LITERALS: Final[tuple[str, ...]] = tuple(DECISION["grid_literals"])
BOX_LITERALS: Final = (GRID_LITERALS[0], GRID_LITERALS[-1])
T_NOMINAL: Final = float(DECISION["t_nominal_K"])
DELTA_T: Final = float(DECISION["delta_T_K"])
HALF_WIDTH: Final = float(DECISION["half_width_K"])
BOUND_TOL: Final = float(DECISION["bound_tol_scaled"])
SPEC_ID: Final = str(DECISION["spec_id"])
FLAT_TOL: Final = float(JOURNEY["rung_flatness_tol_rel"])
RUNGS: Final = ("R0", "R1", "R2", "R3")
GRID_RUNGS: Final = ("R0", "R1")
UNSUPPORTED_REASONS: Final[tuple[str, ...]] = tuple(JOURNEY["unsupported_reasons"])
REACTOR_UNAVAILABLE: Final = "reactor_environment_unavailable"
M05_UNAVAILABLE: Final = "m05_study_unavailable"
#: R2 under a PROMOTABLE verdict with no surrogate-backed loop to evaluate (registered: spec
#: Amendment 1 A1.3, R-422; ADR 0041 D6).
SURROGATE_LOOP_UNAVAILABLE: Final = "surrogate_loop_unavailable"
PARENT_LOCAL_EVIDENCE: Final = "PARENT_LOCAL_EVIDENCE"
#: The flash liquid NH3 flow is the objective `c1-obj-nh3-liquid-v1` (M05 §7.1).
LIQUID: Final = "S6"
STREAMS: Final = {"inlet": "S3", "outlet": "S4", "recycle": "S8", "purge": "S7"}
UNITS: Final = {"preheater": "preheater", "flash": "flash", "reactor": "reactor"}
COMPONENTS: Final = ("H2", "N2", "NH3", "Ar", "CH4")
#: R1's first-evaluation estimate of cold reactor experiments: M02 G12's 4 per loop (spec §3 F3).
R1_FIRST_ESTIMATE: Final = int(JOURNEY["g12_facts"]["experiments_per_loop"])
#: A grid point the budget stopped before it was evaluated (§4.5).
NOT_EVALUATED_BUDGET: Final = "NOT_EVALUATED(budget)"
FORBIDDEN: Final = re.compile(
    r"\b(?:" + "|".join(re.escape(w) for w in REPORT["forbidden_tokens"]) + r")\b", re.IGNORECASE
)
GRID_ENTRY_KEYS: Final = (
    "T",
    "T_literal",
    "verified",
    "outcome",
    "certificate",
    "J",
    "e",
    "X_pass",
    "Q_preheater_W",
    "Q_flash_W",
    "n_recycle_mol_s",
    "n_purge_NH3_mol_s",
    "extrapolated",
    "experiments",
    "wall_s",
    "run_sha256",
    "constraints",
)
TOP_LEVEL: Final = (
    "schema",
    "registration_sha256",
    "commit",
    "environment",
    "case",
    "rungs",
    "pairs",
    "tc1",
    "decision",
    "accounting",
    "limitations",
    "artifacts",
    "synthetic_dry_run",
)


def unsupported(reason: str) -> str:
    return f"UNSUPPORTED({reason})"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# == the rules (spec §4.4) =========================================================================


def best_point(points: Sequence[Mapping[str, Any]]) -> Mapping[str, Any] | None:
    """The verified point with the largest J; an exact tie goes to the lowest T (§4.4.1)."""
    best: Mapping[str, Any] | None = None
    for point in points:
        if not point["verified"]:
            continue
        if (
            best is None
            or point["J"] > best["J"]
            or (point["J"] == best["J"] and point["T"] < best["T"])
        ):
            best = point
    return best


def rung_decision(points: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """§4.4.1 over a rung's grid evaluations (each {T, J, verified})."""
    best = best_point(points)
    if len(points) < len(GRID_LITERALS) or not all(p["verified"] for p in points):
        return {"outcome": "INCOMPLETE", "decision": None if best is None else best["T"]}
    values = [p["J"] for p in points]
    spread = max(values) - min(values)
    if spread <= FLAT_TOL * max(abs(v) for v in values):
        return {"outcome": "INDIFFERENT", "decision": T_NOMINAL}
    assert best is not None
    return {"outcome": "DECIDED", "decision": best["T"]}


def indifference_set(points: Sequence[Mapping[str, Any]]) -> list[float]:
    """§4.4.2: the verified T_k with J_k >= J_best - (e_k + e_best), ascending."""
    best = best_point(points)
    if best is None:
        return []
    return sorted(
        p["T"] for p in points if p["verified"] and p["J"] >= best["J"] - (p["e"] + best["e"])
    )


def fe_class(pair: Mapping[str, Any]) -> str:
    """§4.4.4 in its precedence; boundaries inclusive as written."""
    if pair["t_after"] is None:
        return "FE_NOT_DETERMINED"
    gain = pair["j_after"] - pair["j_before"]
    resolution = pair["e_before"] + pair["e_after"]
    if gain < -resolution:
        return "FE_WORSE"
    if abs(pair["t_after"] - pair["t_before"]) <= DELTA_T:
        return "FE_UNCHANGED"
    if gain > resolution:
        return "FE_CHANGED"
    return "FE_WITHIN_RESOLUTION"


def tc1(
    t_after: float | None,
    j_after: float | None,
    e_after: float | None,
    grid: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """§4.4.5 on R3's candidate values (T*, J* if verified, e*) against the best verified parent
    grid point B (Amendment 1 A1.1, R-420): `TC1_NOT_APPLICABLE` when T*, J* or e* is null, then
    `TC1_NO_GRID`, then `TC1_NOT_APPLICABLE` at B's T when B has no noise floor — B is never
    replaced by a lesser point that has one — and otherwise the inequality."""
    if t_after is None or j_after is None or e_after is None:
        return {"outcome": "TC1_NOT_APPLICABLE", "best_grid_T": None}
    best = best_point(grid)
    if best is None:
        return {"outcome": "TC1_NO_GRID", "best_grid_T": None}
    if best["e"] is None:
        return {"outcome": "TC1_NOT_APPLICABLE", "best_grid_T": best["T"]}
    holds = j_after >= best["J"] - (e_after + best["e"])
    return {"outcome": "TC1_HOLDS" if holds else "TC1_CONTRADICTED", "best_grid_T": best["T"]}


def tc1_missing(
    t_after: float | None,
    j_after: float | None,
    e_after: float | None,
    grid: Sequence[Mapping[str, Any]],
) -> list[str]:
    """The `tc1` member's `missing` (A1.1): empty, or the first absent of `t_after`, `j_after`,
    `e_after` and B's floor `e_B`."""
    for name, value in (("t_after", t_after), ("j_after", j_after), ("e_after", e_after)):
        if value is None:
            return [name]
    best = best_point(grid)
    return ["e_B"] if best is not None and best["e"] is None else []


def bound_activity(t: float | None) -> str | None:
    """§4.4.6; `None` for no decision."""
    if t is None:
        return None
    low, high = float(BOX_LITERALS[0]), float(BOX_LITERALS[1])
    if abs(t - low) / HALF_WIDTH <= BOUND_TOL:
        return "BOUND_LOWER"
    if abs(t - high) / HALF_WIDTH <= BOUND_TOL:
        return "BOUND_UPPER"
    return "INTERIOR"


def bound_phrase(activity: str | None) -> str | None:
    """§6.3's bound phrase for a bound-active decision."""
    if activity == "BOUND_LOWER":
        side, value = "lower", BOX_LITERALS[0]
    elif activity == "BOUND_UPPER":
        side, value = "upper", BOX_LITERALS[1]
    else:
        return None
    return str(REPORT["bound_phrase"]).format(side=side, value=value)


def _grid_point(grid: Sequence[Mapping[str, Any]], t: float | None) -> Mapping[str, Any] | None:
    for point in grid:
        if t is not None and point["T"] == t:
            return point
    return None


def pair(
    pair_id: str,
    t_before: float | None,
    after: tuple[float | None, float | None, float | None, bool],
    grid: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """§4.4.3. `t_before` is a parent grid point; `after` is (t, j, e, verified) of the parent
    value at the after-decision. A missing value nulls t_after and says which (FE_NOT_DETERMINED);
    a null noise floor is missing, never 0 (Amendment 1 A1.1, R-420). At most one field per side,
    in the order t_before, j_before, e_before, t_after, j_after, e_after."""
    t_after, j_after, e_after, after_verified = after
    before = _grid_point(grid, t_before)
    missing: list[str] = []
    if t_before is None:
        missing.append("t_before")
    elif before is None or not before["verified"]:
        missing.append("j_before")
    elif before["e"] is None:
        missing.append("e_before")
    if t_after is None:
        missing.append("t_after")
    elif not after_verified or j_after is None:
        missing.append("j_after")
    elif e_after is None:
        missing.append("e_after")
    document = {
        "pair": pair_id,
        "t_before": t_before,
        "t_after": None if missing else t_after,
        "j_before": None if before is None or not before["verified"] else before["J"],
        "j_after": j_after if after_verified else None,
        "e_before": None if before is None or not before["verified"] else before["e"],
        "e_after": e_after if after_verified else None,
        "missing": missing,
    }
    document["fe_class"] = fe_class(document)
    return document


# == budget (spec §4.5) ============================================================================


@dataclass
class RungBudget:
    """M07-budget-v1 for one rung, checked before each evaluation (R-335).

    An evaluation would exceed the budget when the spent total plus the estimate of the next
    evaluation passes the cap; the estimate is the largest cost seen so far in the rung, and before
    the first evaluation `first_estimate` cold experiments and 0 s (Amendment 1 A1.2, R-421). Only
    out-of-process unit executions are cold reactor experiments (Amendment 1 A1.4, R-423)."""

    cold_cap: int
    wall_cap: float
    first_estimate: int = 0
    cold: int = 0
    wall_s: float = 0.0
    _next_cold: int = field(default=-1, repr=False)
    _next_wall: float = 0.0

    def __post_init__(self) -> None:
        self._next_cold = self.first_estimate

    def would_exceed(self) -> bool:
        return (
            self.cold + self._next_cold > self.cold_cap
            or self.wall_s + self._next_wall > self.wall_cap
        )

    def charge(self, cold: int, wall_s: float) -> None:
        self.cold += cold
        self.wall_s += wall_s
        self._next_cold = max(self._next_cold, cold) if self._next_cold >= 0 else cold
        self._next_wall = max(self._next_wall, wall_s)

    @property
    def overrun(self) -> bool:
        return self.cold > self.cold_cap or self.wall_s > self.wall_cap

    def as_document(self) -> dict[str, Any]:
        return {
            "cold": self.cold_cap,
            "wall_s": self.wall_cap,
            "spent": {"cold": self.cold, "wall_s": self.wall_s},
        }


def budget_for(rung: str) -> RungBudget:
    block = JOURNEY["budget"][rung]
    first = R1_FIRST_ESTIMATE if rung == "R1" else 0
    return RungBudget(int(block["cold_experiments"]), float(block["wall_s"]), first)


# == evaluation ====================================================================================


class Evaluator(Protocol):
    """One coupled loop solve at a grid temperature; returns a grid entry (§6.1) without `e` and
    `constraints`. Its `experiments.cold` is what the budget is charged (A1.4)."""

    def __call__(self, t: float, literal: str) -> dict[str, Any]: ...


class ParentExtras(Protocol):
    """M05's noise floor e_k and P3's constraint values at a verified parent grid point."""

    def __call__(self, t: float, entry: Mapping[str, Any]) -> tuple[float | None, Any]: ...


def document_at(document: Mapping[str, Any], t: float) -> dict[str, Any]:
    """The case with SPEC-S3-T at the binary64 value `t` (§4.3; M05's `document_at`)."""
    edited = copy.deepcopy(dict(document))
    (spec,) = [item for item in edited["specifications"] if item["id"] == SPEC_ID]
    spec["value"] = float(t)
    return edited


def coupling_attribution(record: Mapping[str, Any] | None) -> tuple[dict[str, int], int]:
    """A grid point's `experiments` and `extrapolated` from its coupling record (ADR 0034 D6;
    M05's `coupling_counts` convention split by unit kind, Amendment 1 A1.4, R-423).

    `cold` counts the attempts of out-of-process units' entries — the cold reactor experiments
    charged to M07-budget-v1 — and `in_process` those of in-process units' entries (a unit whose
    `frozen.<unit>.fingerprint.kind` is `in_process`), so `cold + in_process` is the record's
    executions; `store_hit` counts entries with `cache_hit` true. `extrapolated` counts the
    entries of the **last** iteration whose envelope `domain_status` is `extrapolated` (R-169;
    A1.5, R-424): those are the experiments whose outputs the certified state uses — the writer
    returns `CONVERGED` right after appending the accepted iterate (`orchestrator.coupling.couple`)
    and certifies against `iterations[-1]` (`coupling_evidence`); earlier iterations are the
    solve's path, not its result."""
    cold = hits = in_process = extrapolated = 0
    kinds = {
        unit: ((frozen.get("fingerprint") or {}).get("kind"))
        for unit, frozen in ((record or {}).get("frozen") or {}).items()
    }
    iterations = list((record or {}).get("iterations") or ())
    for iteration in iterations:
        for unit, entry in (iteration.get("units") or {}).items():
            attempts = len(entry.get("attempts") or ())
            hits += bool(entry.get("cache_hit"))
            if kinds.get(unit) == "in_process":
                in_process += attempts
            else:
                cold += attempts
    for entry in (iterations[-1].get("units") or {}).values() if iterations else ():
        envelope = (entry.get("result") or {}).get("envelope") or {}
        extrapolated += envelope.get("domain_status") == "extrapolated"
    return {"cold": cold, "store_hit": hits, "in_process": in_process}, extrapolated


@dataclass
class LoopEvaluator:
    """Grid solves of `document` through `run_revision_session` on the `revision_coupled` route
    (§4.3), one bundle per solve under `artifacts`, experiments through `runner`'s store."""

    document: Mapping[str, Any]
    runner: Any
    artifacts: Path
    label: str
    clock: Callable[[], float] = time.monotonic

    def __call__(self, t: float, literal: str) -> dict[str, Any]:
        from openflowsheet.application.coupled_run import LiveExperiments
        from openflowsheet.application.policies import T06_REVISION_V2
        from openflowsheet.application.revision_run import (
            Route,
            RunUnsupportedError,
            run_revision_session,
            select_route,
        )
        from openflowsheet.canonical import document_sha256
        from openflowsheet.run.bundle import read_artifact
        from openflowsheet.verify.certificate import CheckPolicy
        from openflowsheet.verify.checks import VerifierError

        document = document_at(self.document, t)
        entry = empty_entry(t, literal)
        started = self.clock()
        route = select_route(document)
        if not isinstance(route, Route) or route.solve_path != "revision_coupled":
            entry["outcome"] = "unsupported(not_revision_coupled)"
            entry["wall_s"] = self.clock() - started
            return entry
        directory = self.artifacts / self.label / literal
        try:
            manifest = run_revision_session(
                route,
                document,
                directory,
                run_id=f"m07-{self.label}-{literal}",
                policy=T06_REVISION_V2,
                check_policy=CheckPolicy(),
                policy_requested="default",
                experiments=LiveExperiments(self.runner),
            )
        except RunUnsupportedError as error:
            entry["outcome"] = f"unsupported({error.code})"
            entry["wall_s"] = self.clock() - started
            return entry
        except VerifierError as error:
            entry["outcome"] = f"verifier_refused({error})"
            entry["wall_s"] = self.clock() - started
            return entry
        wall = self.clock() - started
        coupling = (
            read_artifact(directory, "external-coupling.json")
            if "external-coupling.json" in manifest.artifacts
            else None
        )
        experiments, extrapolated = coupling_attribution(coupling)
        entry.update(
            outcome=manifest.outcome,
            certificate=manifest.verification_status,
            verified=manifest.outcome == "CONVERGED" and manifest.verification_status == "VERIFIED",
            extrapolated=extrapolated,
            experiments=experiments,
            wall_s=wall,
            run_sha256=manifest.artifact_r0_sha256,
            revision_sha256=document_sha256(document),
            coupling_sha256=None if coupling is None else document_sha256(coupling),
        )
        if "solution-state.json" in manifest.artifacts:
            state = read_artifact(directory, "solution-state.json")["variables"]
            entry.update(loop_quantities(state))
        if not entry["verified"]:
            entry["J"] = None
        return entry


def empty_entry(t: float, literal: str) -> dict[str, Any]:
    return {
        "T": t,
        "T_literal": literal,
        "verified": False,
        "outcome": None,
        "certificate": None,
        "J": None,
        "e": None,
        "X_pass": None,
        "Q_preheater_W": None,
        "Q_flash_W": None,
        "n_recycle_mol_s": None,
        "n_purge_NH3_mol_s": None,
        "extrapolated": 0,
        "experiments": {"cold": 0, "store_hit": 0, "in_process": 0},
        "wall_s": 0.0,
        "run_sha256": None,
        "constraints": None,
    }


def loop_quantities(state: Mapping[str, float]) -> dict[str, float]:
    """The §6.1 quantities read from a certified loop state (C1 variable names, build decision
    J7): X_pass is the reactor's per-pass N2 conversion (n_N2,in - n_N2,out) / n_N2,in."""
    n2_in = state[f"{STREAMS['inlet']}.n.N2"]
    n2_out = state[f"{STREAMS['outlet']}.n.N2"]
    return {
        "J": state[f"{LIQUID}.n.NH3"],
        "X_pass": (n2_in - n2_out) / n2_in,
        "Q_preheater_W": state[f"{UNITS['preheater']}.Q"],
        "Q_flash_W": state[f"{UNITS['flash']}.Q"],
        "n_recycle_mol_s": math.fsum(state[f"{STREAMS['recycle']}.n.{c}"] for c in COMPONENTS),
        "n_purge_NH3_mol_s": state[f"{STREAMS['purge']}.n.NH3"],
    }


def with_margin(constraint: Mapping[str, Any]) -> dict[str, Any]:
    """An M05 `ConstraintValue` document plus `margin` (Amendment 1 A1.7, R-426): bound − value
    for `<=`, value − bound for `>=`, in binary64 as written; positive when satisfied."""
    value, bound, sense = constraint["value"], constraint["bound"], constraint["sense"]
    if sense == "<=":
        margin = bound - value
    elif sense == ">=":
        margin = value - bound
    else:
        raise ValueError(f"constraint {constraint.get('constraint_id')!r}: sense {sense!r}")
    return {**constraint, "margin": margin}


def m05_parent_extras(document: Mapping[str, Any], runner: Any) -> ParentExtras | None:
    """M05's noise floor (§7.4 there: `checks.noise_floor`) and P3's constraint values at a parent
    grid point, by M05's own `C1Parent.solve` at the same decision on the application's
    `C1_PARENT_SERVICES` (store hits only; it must give the same J bit for bit, or the point's e is
    refused). `None` when M05's study package is not in this tree: R1's e_k are then null with the
    limitation `noise_floor_unavailable` (spec §14 Q2's default)."""
    try:
        from openflowsheet.application.trust_region_parent import C1_PARENT_SERVICES
        from openflowsheet.studies.trust_region.checks import noise_floor
        from openflowsheet.studies.trust_region.parent import C1Parent
    except ImportError:
        return None
    box = (float(BOX_LITERALS[0]), float(BOX_LITERALS[1]))
    parent = C1Parent(document, runner, box, services=C1_PARENT_SERVICES)
    (decision,) = parent.decisions

    def extras(t: float, entry: Mapping[str, Any]) -> tuple[float | None, Any]:
        solve = parent.solve(
            {decision.name: t}, solve_id=f"m07-grid-{entry['T_literal']}", purpose="grid"
        )
        if not solve.certified or solve.objective != entry["J"]:
            return None, None
        floor = noise_floor(parent, solve)
        e = None if floor is None else floor.e_star  # never read as 0 (Amendment 1 A1.1)
        return e, [with_margin(item.as_document()) for item in solve.constraints]

    return extras


def run_grid(
    rung: str,
    evaluate: Evaluator,
    budget: RungBudget,
    extras: ParentExtras | None = None,
    clock: Callable[[], float] = time.monotonic,
) -> tuple[list[dict[str, Any]], bool]:
    """The nine grid evaluations of a rung in grid order, the budget checked before each (§4.5,
    A1.2). A point not evaluated because the budget would be exceeded is recorded as
    `NOT_EVALUATED(budget)`. A point's `wall_s` is everything spent on it: the loop solve and its
    parent extras. Returns the entries and whether the budget ran out."""
    entries: list[dict[str, Any]] = []
    exhausted = False
    for literal in GRID_LITERALS:
        t = float(literal)
        if exhausted or budget.would_exceed():
            exhausted = True
            entry = empty_entry(t, literal)
            entry["outcome"] = NOT_EVALUATED_BUDGET
            entries.append(entry)
            continue
        entry = evaluate(t, literal)
        if extras is not None and entry["verified"]:
            started = clock()
            entry["e"], entry["constraints"] = extras(t, entry)
            entry["wall_s"] = float(entry["wall_s"]) + (clock() - started)
        budget.charge(int(entry["experiments"]["cold"]), float(entry["wall_s"]))
        entries.append(entry)
        if budget.overrun:
            exhausted = True
    return entries, exhausted


def grid_rung(entries: list[dict[str, Any]], exhausted: bool, budget: RungBudget) -> dict[str, Any]:
    decided = rung_decision(entries)
    summary: dict[str, Any] = {
        "outcome": "BUDGET_EXHAUSTED" if exhausted else decided["outcome"],
        "decision": decided["decision"],
        "bound_activity": bound_activity(decided["decision"]),
        "budget": budget.as_document(),
        "grid": entries,
    }
    return summary


def unsupported_rung(rung: str, reason: str) -> dict[str, Any]:
    budget = budget_for(rung)
    summary: dict[str, Any] = {
        "outcome": unsupported(reason),
        "decision": None,
        "bound_activity": None,
        "budget": budget.as_document(),
    }
    if rung in GRID_RUNGS:
        summary["grid"] = []
    return summary


def reactor_available(env_base: Path | None) -> bool:
    """The parent's reactor environment verifies against its pins (M02's `env.verify`). The
    manifest's `variant_id` is provenance, not a verification key (R-259: one environment serves
    every variant with its `env_id`); `env.verify` still lists it, so that line is not a
    difference here (build log J25)."""
    from openflowsheet.adapters import variants
    from openflowsheet.adapters.pymrm import env

    variant = variants.registered_variant(JOURNEY["variants"]["real"]["variant_id"])
    found = env.verify(variant, base=env_base)
    return [line for line in found if not line.startswith("variant_id:")] == []


# == R2: M04's verdict (spec §4.2, A15) ===========================================================


def r2_rung(
    manifest_path: Path,
    *,
    evaluate: Evaluator | None = None,
    parent_grid: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """R2 from M04's committed verdict for the bound parent. Not `PROMOTABLE`: zero evaluations.
    `PROMOTABLE`: nine surrogate-backed loop evaluations through `evaluate`, each compared with the
    parent grid point (surrogate - parent; band containment counted, not a coverage estimate);
    without an evaluator, `UNSUPPORTED(surrogate_loop_unavailable)` with zero evaluations (A1.3)."""
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    promotion = manifest["promotion"]
    real = JOURNEY["variants"]["real"]["variant_id"]
    if manifest.get("model_id") != "c1.reactor_surrogate" or real not in str(
        manifest.get("surrogate_id")
    ):
        raise ValueError(f"{manifest_path} is not a surrogate of the bound parent {real}")
    try:
        relative = str(manifest_path.resolve().relative_to(ROOT))
    except ValueError:
        relative = str(manifest_path)
    budget = budget_for("R2")
    summary: dict[str, Any] = {
        "m04_verdict": promotion["verdict"],
        "m04_reasons": list(promotion["not_promotable"]) + list(promotion["insufficient"]),
        "m04_record": {"path": relative, "sha256": sha256_file(manifest_path)},
        "surrogate_id": manifest["surrogate_id"],
        "evaluations": 0,
        "decision": None,
        "bound_activity": None,
        "budget": budget.as_document(),
        "discrepancy": [],
        "band_containment": None,
    }
    if promotion["verdict"] != "PROMOTABLE":
        summary["outcome"] = "SURROGATE_NOT_PROMOTABLE"
        return summary
    if evaluate is None:
        summary["outcome"] = unsupported(SURROGATE_LOOP_UNAVAILABLE)
        return summary
    entries, exhausted = run_grid("R2", evaluate, budget)
    rung = grid_rung(entries, exhausted, budget)
    summary.update(
        outcome=rung["outcome"],
        decision=rung["decision"],
        bound_activity=rung["bound_activity"],
        budget=rung["budget"],
        grid=entries,
        evaluations=sum(1 for e in entries if not str(e["outcome"]).startswith("NOT_EVALUATED")),
    )
    summary["discrepancy"], summary["band_containment"] = surrogate_discrepancy(
        entries, parent_grid
    )
    return summary


def surrogate_discrepancy(
    entries: Sequence[Mapping[str, Any]], parent_grid: Sequence[Mapping[str, Any]]
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    rows: list[dict[str, Any]] = []
    inside = judged = 0
    for entry in entries:
        parent = _grid_point(parent_grid, entry["T"])
        if not entry["verified"] or parent is None or not parent["verified"]:
            continue
        rows.append({"T": entry["T"], "dJ": entry["J"] - parent["J"]})
        band = entry.get("band")
        if band is not None:
            judged += 1
            inside += band[0] <= parent["J"] <= band[1]
    return rows, {"inside": inside, "judged": judged}


# == R3: M05's study record (spec §4.2, §4.6) =====================================================


#: M05's study schema at J (Amendment 1 A1.6 condition 1).
M05_SCHEMA: Final = ROOT / "schemas" / "trust-region-study.schema.json"
#: M05's evidence manifests, the carry anchor's second source (A1.6 item 2.2).
M05_EVIDENCE: Final = ROOT / "evidence" / "M05"
#: A1.6 conditions 2 and 3: the study, its budget and the REAL configuration.
M05_STUDY_ID: Final = str(JOURNEY["study"])
M05_BUDGET_ID: Final = "M05-budget-v1"
M05_CONFIGURATION: Final = "REAL"
RERUN: Final = "rerun"
#: The reactor environment lock (M02), the one `carry.journey_files` member named in prose.
REACTOR_LOCK: Final = "src/openflowsheet/adapters/pymrm/reactor-env.lock"
#: A re-run's record and sidecars, under the journey's directory (A1.6 item 3).
M05_RERUN_DIR: Final = "m05"


def carry_paths() -> tuple[str, ...]:
    """The registration's `carry.journey_files` as git pathspecs (spec §4.6): a `dir/**` glob is
    the directory, the reactor environment lock is `REACTOR_LOCK`, a file is itself."""
    paths = []
    for item in REG["carry"]["journey_files"]:
        if item.endswith("/**"):
            paths.append(item[: -len("/**")])
        elif item.startswith("the reactor environment lock"):
            paths.append(REACTOR_LOCK)
        else:
            paths.append(item)
    return tuple(paths)


def carry_identical(anchor: str) -> bool:
    """Spec §4.6 carry by identity: every determining file is byte-equal between the anchor commit
    and this tree (`HEAD`, with no change to those paths in the working tree). An anchor git does
    not know is not identical."""
    paths = carry_paths()
    differs = subprocess.run(
        ["git", "diff", "--quiet", anchor, "HEAD", "--", *paths],
        cwd=ROOT,
        capture_output=True,
        check=False,
    )
    return differs.returncode == 0 and _git("status", "--porcelain", "--", *paths) == ""


def tracked_unmodified(path: Path) -> bool:
    """A1.6 condition 5: `path` is tracked in this tree and unmodified at J."""
    try:
        relative = str(path.resolve().relative_to(ROOT))
    except ValueError:
        return False
    listed = subprocess.run(
        ["git", "ls-files", "--error-unmatch", "--", relative],
        cwd=ROOT,
        capture_output=True,
        check=False,
    )
    return listed.returncode == 0 and _git("status", "--porcelain", "--", relative) == ""


def m05_run_commit(record: Mapping[str, Any]) -> str | None:
    """The run commit M05's record states (A1.6 item 2.1): `provenance.run_commit`, which M05's
    REAL script writes at the start of a run from a clean tree (M05 build log S65, M07's FD-3).
    A record without it (or with a dirty tree) states none."""
    provenance = record.get("provenance") or {}
    commit = provenance.get("run_commit")
    if provenance.get("tree_clean") is not True or not isinstance(commit, str):
        return None
    return commit if re.fullmatch(r"[0-9a-f]{40}", commit) else None


def m05_spent_wall(record: Mapping[str, Any]) -> float | None:
    """The study's spent wall as M05's record states it (A1.6 item 4): `provenance.wall_s`, the
    study budget's monotonic-clock wall (S65). Never the cap `study_wall_s`, never a default."""
    wall = (record.get("provenance") or {}).get("wall_s")
    return float(wall) if isinstance(wall, int | float) and not isinstance(wall, bool) else None


def manifest_anchor(record_sha256: str, evidence: Path) -> str | None:
    """A1.6 item 2.2: the commit C_M of an `evidence/M05/<C_M>/manifest.json` with status
    `tested` whose artifacts list the record's sha256 (the first such C_M in sorted order)."""
    for path in sorted(evidence.glob("*/manifest.json")):
        manifest = json.loads(path.read_text(encoding="utf-8"))
        artifacts = manifest.get("artifacts") or []
        if manifest.get("status") == "tested" and any(
            isinstance(item, Mapping) and item.get("sha256") == record_sha256 for item in artifacts
        ):
            return path.parent.name
    return None


def _r3_refused(*codes: str) -> dict[str, Any]:
    summary = unsupported_rung("R3", M05_UNAVAILABLE)
    summary["limitations"] = list(codes)
    return summary


def _r3_condition(
    record_path: Path,
    schema_path: Path,
    tracked: Callable[[Path], bool],
) -> tuple[int | None, dict[str, Any] | None, dict[str, Any] | None]:
    """A1.6's input conditions 1–5 in order: (the first that fails or None, the record, the
    best candidate)."""
    import jsonschema

    try:
        record = json.loads(record_path.read_text(encoding="utf-8"))
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return 1, None, None
    if not isinstance(record, dict) or any(
        True for _ in jsonschema.Draft202012Validator(schema).iter_errors(record)
    ):
        return 1, None, None
    if record.get("study_id") != M05_STUDY_ID:
        return 2, record, None
    budgets = (record.get("accounting") or {}).get("budgets") or {}
    if budgets.get("budget_id") != M05_BUDGET_ID or budgets.get("configuration") != (
        M05_CONFIGURATION
    ):
        return 3, record, None
    chosen: dict[str, Any] | None = None
    best = record.get("best")
    if best is not None:
        from openflowsheet.canonical import document_sha256

        matches = [
            c
            for c in record.get("candidates") or []
            if c.get("solves") and c["solves"][0].get("check_id") == best.get("check_id")
        ]
        if len(matches) != 1 or len(matches[0].get("decisions") or {}) != 1:
            return 4, record, None
        chosen = matches[0]
        (t,) = chosen["decisions"].values()
        expected = document_sha256(document_at(load_loop("real"), float(t)))
        if chosen["solves"][0].get("revision_sha256") != expected:
            return 4, record, None
    if not tracked(record_path):
        return 5, record, chosen
    return None, record, chosen


def r3_rung(
    record_path: Path | None,
    *,
    schema_path: Path = M05_SCHEMA,
    evidence: Path = M05_EVIDENCE,
    tracked: Callable[[Path], bool] = tracked_unmodified,
    identical: Callable[[str], bool] = carry_identical,
    rerun: Callable[[], tuple[Path, float]] | None = None,
) -> dict[str, Any]:
    """R3 from M05's REAL study record passed as `--m05-record`, carried by identity (spec §4.6;
    Amendment 1 A1.6, R-425). The record is accepted iff conditions 1–5 hold; otherwise R3 is
    `UNSUPPORTED(m05_study_unavailable)` with `R3:record_rejected:<n>`, never an exception. The
    carry anchor is M05's stated run commit, else a tested M05 manifest listing the record's
    sha256. A record with no anchor, or whose `carry.journey_files` differ between the anchor and
    J, is re-run at J by `rerun` (M05's REAL entry point, A1.6 item 3), which returns the re-run
    record's path and the journey's monotonic-clock wall of the study call; without `rerun`, R3
    refuses with `R3:carry_anchor_missing` or `R3:carry_identity_differs`. A re-run record meets
    conditions 1–4 at J; condition 5 holds once it is committed with the journey record (build
    log J22). The accounting is copied from M05's record, never reconstructed or defaulted.
    Without a record, `UNSUPPORTED(m05_study_unavailable)`."""
    if record_path is None:
        return unsupported_rung("R3", M05_UNAVAILABLE)
    failed, record, chosen = _r3_condition(record_path, schema_path, tracked)
    if failed is not None or record is None:
        return _r3_refused(f"R3:record_rejected:{failed}")
    anchor = m05_run_commit(record) or manifest_anchor(sha256_file(record_path), evidence)
    if anchor is not None and identical(anchor):
        return _r3_document(record_path, record, chosen, anchor, m05_spent_wall(record))
    if rerun is None:
        return _r3_refused(
            "R3:carry_anchor_missing" if anchor is None else "R3:carry_identity_differs"
        )
    rerun_path, wall = rerun()
    failed, record, chosen = _r3_condition(rerun_path, schema_path, lambda path: True)
    if failed is not None or record is None:
        return _r3_refused(f"R3:record_rejected:{failed}")
    return _r3_document(rerun_path, record, chosen, RERUN, wall)


def _r3_document(
    record_path: Path,
    record: Mapping[str, Any],
    chosen: Mapping[str, Any] | None,
    carried_from: str,
    wall: float | None,
) -> dict[str, Any]:
    """R3's rung from an accepted M05 record: its best candidate, M05's statuses verbatim, and
    M05's spend copied (A1.6 item 4); `wall` is M05's stated wall for a carried record and the
    journey's measurement for a re-run (`wall_source`)."""
    candidate: dict[str, Any] | None = None
    if chosen is not None:
        (t,) = chosen["decisions"].values()
        floor = chosen.get("noise_floor")
        halfwidth = chosen.get("indifference_halfwidth")
        targeted = chosen["solves"][0]
        verified = targeted["outcome"] == "CONVERGED" and targeted["certificate"] == "VERIFIED"
        candidate = {
            "T": float(t),
            "status": chosen["status"],
            "J": targeted["objective"] if verified else None,
            "e": None if floor is None else floor["e_star"],
            "half_width": None if halfwidth is None else next(iter(halfwidth.values())),
            "verified": verified,
            "check_id": targeted["check_id"],
            "coupling_record_sha256": targeted.get("coupling_record_sha256"),
            "constraints": (chosen.get("checks") or {}).get("P3"),
        }
    accounting = record.get("accounting") or {}
    cold = (accounting.get("budgets") or {}).get("cold_used")
    limitations = []
    if cold is None:
        limitations.append("R3:m05_cold_unrecorded")
    if wall is None:
        limitations.append("R3:m05_wall_unrecorded")
    budget = budget_for("R3").as_document()  # M05 enforces M05-budget-v1; R3 copies its spend
    budget["spent"] = {"cold": cold, "wall_s": wall}
    budget["wall_source"] = (
        None if wall is None else "journey_measured" if carried_from == RERUN else "m05_record"
    )
    try:
        relative = str(record_path.resolve().relative_to(ROOT))
    except ValueError:
        relative = str(record_path)
    decision = None if candidate is None else candidate["T"]
    return {
        "outcome": record["status"],
        "study_status": record["status"],
        "m05_record": {
            "path": relative,
            "sha256": sha256_file(record_path),
            "carried_from": carried_from,
        },
        "candidate": candidate,
        "decision": decision,
        "bound_activity": bound_activity(decision),
        "budget": budget,
        "store_hits": (accounting.get("totals") or {}).get("store_hits"),
        "limitations": limitations,
    }


def m05_rerun(out: Path, clock: Callable[[], float] = time.monotonic) -> Callable[[], Any] | None:
    """A1.6 item 3: M05's REAL study re-run at J by M05's own entry point as merged
    (`scripts/m05_wo9_real.py`'s `run_real`, on a fresh experiment store as M05 requires), its
    record and sidecars written under `<out>/m05/` with M05's writer. `None` when M05's script
    cannot be imported here. The call refuses a dirty tree (M05's S65), so nothing of the journey
    is written before it."""
    scripts = str(ROOT / "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    try:
        import m05_wo9_real as real
    except ImportError:
        return None

    def rerun() -> tuple[Path, float]:
        import tempfile

        stem = out / M05_RERUN_DIR / real.STEM.name
        if stem.with_suffix(".json").exists():
            raise SystemExit(f"{stem}.json exists: a committed run is never overwritten in place")
        with tempfile.TemporaryDirectory(prefix="m07-r3-") as root:
            started = clock()
            result = real.run_real(Path(root))
            wall = clock() - started
        real.wo8.write_files(stem, result.run)
        stem.with_suffix(".experiments.json").write_bytes(result.archive)
        for line in result.run.bijection[:40]:
            print(f"  R3 re-run bijection: {line}", file=sys.stderr)
        print(f"R3 re-run: {real.summary(result)}", file=sys.stderr)
        return stem.with_suffix(".json"), wall

    return rerun


class TStarResolve(Protocol):
    """A parent solve at R3's decision T*: (objective or None, certified, M05 `ConstraintValue`
    documents or None, `experiments` {cold, store_hit, in_process} of its coupling record)."""

    def __call__(
        self, t: float
    ) -> tuple[float | None, bool, list[dict[str, Any]] | None, dict[str, int]]: ...


def m05_t_star_resolver(document: Mapping[str, Any], runner: Any) -> TStarResolve | None:
    """Amendment 1 A1.7 (R-426): M05's own `C1Parent.solve` at T* on the journey's case document
    and store (the mechanism of R1's grid extras), its experiments attributed like a grid point's
    (A1.4). `None` when M05's study package is not in this tree."""
    try:
        from openflowsheet.application.trust_region_parent import C1_PARENT_SERVICES
        from openflowsheet.studies.trust_region.parent import C1Parent
    except ImportError:
        return None
    records: list[Mapping[str, Any]] = []
    box = (float(BOX_LITERALS[0]), float(BOX_LITERALS[1]))
    parent = C1Parent(
        document,
        runner,
        box,
        services=C1_PARENT_SERVICES,
        coupling_sink=lambda solve_id, record: records.append(record),
    )
    (decision,) = parent.decisions

    def resolve(
        t: float,
    ) -> tuple[float | None, bool, list[dict[str, Any]] | None, dict[str, int]]:
        records.clear()
        solve = parent.solve({decision.name: t}, solve_id="m07-t-star", purpose="t_star_resolve")
        experiments, _ = coupling_attribution(records[-1] if records else None)
        if not solve.certified:
            return None, False, None, experiments
        return (
            solve.objective,
            True,
            [item.as_document() for item in solve.constraints],
            experiments,
        )

    return resolve


def apply_t_star_resolve(
    r3: dict[str, Any], resolve: TStarResolve, clock: Callable[[], float] = time.monotonic
) -> dict[str, Any]:
    """A1.7: R3's P3 values come from a journey re-solve of T*, whose objective must equal M05's
    recorded J* bit for bit; otherwise the values are null with `R3:j_star_not_reproduced` (J*
    and e* from M05's record still serve P13 and TC-1). The re-solve's cost is `t_star_resolve`
    {cold, store_hit, in_process, wall_s}: in the journey totals, not in M05's spend, never
    budget-gated. Nothing is re-solved without a verified candidate."""
    candidate = r3.get("candidate")
    if not candidate or not candidate["verified"]:
        return r3
    started = clock()
    objective, certified, constraints, experiments = resolve(candidate["T"])
    wall = clock() - started
    r3["t_star_resolve"] = {
        "cold": int(experiments["cold"]),
        "store_hit": int(experiments["store_hit"]),
        "in_process": int(experiments["in_process"]),
        "wall_s": wall,
    }
    reproduced = certified and constraints is not None and objective == candidate["J"]
    if reproduced and constraints is not None:
        candidate["constraints"] = [with_margin(item) for item in constraints]
    else:
        candidate["constraints"] = None
        r3["limitations"] = [*(r3.get("limitations") or ()), "R3:j_star_not_reproduced"]
        print(f"R3: the T* re-solve gave J = {objective!r}, not J* = {candidate['J']!r}")
    return r3


# == the record (spec §6.1) ========================================================================


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()


def environment_block() -> dict[str, Any]:
    reactor_lock = ROOT / "src" / "openflowsheet" / "adapters" / "pymrm" / "reactor-env.lock"
    return {
        "lock_sha256": sha256_file(ROOT / "requirements.lock"),
        "reactor_lock_sha256": sha256_file(reactor_lock),
        "platform": f"{platform.system()}-{platform.machine()}-py{platform.python_version()}",
        "tree_clean": _git("status", "--porcelain") == "",
        "omp_num_threads": os.environ.get("OMP_NUM_THREADS"),
    }


def case_block() -> dict[str, Any]:
    return {
        "id": JOURNEY["case"],
        "loops": {
            name: {"path": path, "sha256": sha256_file(ROOT / path)}
            for name, path in sorted(JOURNEY["loops"].items())
        },
    }


def r3_after(r3: Mapping[str, Any]) -> tuple[float | None, float | None, float | None, bool]:
    candidate = r3.get("candidate")
    if not candidate:
        return None, None, None, False
    return candidate["T"], candidate["J"], candidate["e"], bool(candidate["verified"])


def r1_after(r1: Mapping[str, Any]) -> tuple[float | None, float | None, float | None, bool]:
    point = _grid_point(r1.get("grid") or [], r1.get("decision"))
    if point is None:
        return r1.get("decision"), None, None, False
    return point["T"], point["J"], point["e"], bool(point["verified"])


def journey_decision(
    r1: Mapping[str, Any], r3: Mapping[str, Any], check: Mapping[str, Any]
) -> dict[str, Any]:
    """§4.4.7. Never from R0 or R2. The grid-only decision is R1's rung decision (§4.4.1), a
    verified grid point whenever it exists; `INSUFFICIENT_EVIDENCE` iff it is null. The fallback's
    reason: R3's candidate status when it is not `PARENT_LOCAL_EVIDENCE`, TC-1's outcome when it
    is, R3's rung outcome when R3 has no candidate (Amendment 1 A1.8, R-427)."""
    candidate = r3.get("candidate")
    if (
        candidate
        and candidate["status"] == PARENT_LOCAL_EVIDENCE
        and check["outcome"] == ("TC1_HOLDS")
    ):
        t = candidate["T"]
        return {"label": "refined", "T": t, "reason": None, "bound_activity": bound_activity(t)}
    t = r1.get("decision")
    if t is None:
        return {
            "label": "INSUFFICIENT_EVIDENCE",
            "T": None,
            "reason": r1["outcome"],
            "bound_activity": None,
        }
    if candidate and candidate["status"] == PARENT_LOCAL_EVIDENCE:
        reason = check["outcome"]
    elif candidate:
        reason = candidate["status"]
    else:
        reason = r3["outcome"]
    return {"label": "grid_only", "T": t, "reason": reason, "bound_activity": bound_activity(t)}


def discrepancy(r0: Mapping[str, Any], r1: Mapping[str, Any]) -> list[dict[str, Any]]:
    """W25 (d): per grid point J_R0 - J_R1 and its value relative to |J_R1|."""
    rows = []
    for point in r1.get("grid") or []:
        simple = _grid_point(r0.get("grid") or [], point["T"])
        if simple is None or not simple["verified"] or not point["verified"]:
            rows.append({"T": point["T"], "dJ": None, "rel": None})
            continue
        gap = simple["J"] - point["J"]
        rows.append({"T": point["T"], "dJ": gap, "rel": gap / abs(point["J"])})
    return rows


def parent_checks(record: Mapping[str, Any]) -> dict[str, Any]:
    """W25 (c), (f): for each decision, the parent evaluation it rests on and its constraint
    values (R0, R1 and a grid-only journey decision: the R1 grid point; R3 and a refined decision:
    M05's targeted check)."""
    rungs = record["rungs"]
    grid = rungs["R1"].get("grid") or []

    def at_grid(t: float | None) -> dict[str, Any] | None:
        point = _grid_point(grid, t)
        if point is None or not point["verified"]:
            return None
        return {
            "kind": "grid_point",
            "run_sha256": point["run_sha256"],
            "constraints": point["constraints"],
        }

    candidate = rungs["R3"].get("candidate")
    targeted = (
        None
        if not candidate or not candidate["verified"]
        else {
            "kind": "targeted_check",
            "run_sha256": candidate["coupling_record_sha256"],
            "check_id": candidate["check_id"],
            "constraints": candidate["constraints"],
        }
    )
    decision = record["decision"]
    return {
        "R0": at_grid(rungs["R0"]["decision"]),
        "R1": at_grid(rungs["R1"]["decision"]),
        "R3": targeted,
        "journey": targeted if decision["label"] == "refined" else at_grid(decision["T"]),
    }


def accounting(rungs: Mapping[str, Any]) -> dict[str, Any]:
    """W25 (g): per rung cold reactor experiments, in-process executions, store hits and wall
    against M07-budget-v1; the totals are the sums of the grid entries' attributions (A1.4)."""
    per: dict[str, Any] = {}
    for name in RUNGS:
        rung = rungs[name]
        grid = rung.get("grid") or []
        spent = rung["budget"]["spent"]
        experiments = {
            "cold": sum(int(e["experiments"]["cold"]) for e in grid),
            "store_hit": sum(int(e["experiments"]["store_hit"]) for e in grid),
            "in_process": sum(int(e["experiments"]["in_process"]) for e in grid),
        }
        if name == "R3" and "store_hits" in rung:  # M05's own counts, copied (A1.6 item 4)
            experiments = {"cold": spent["cold"], "store_hit": rung["store_hits"], "in_process": 0}
        per[name] = {
            "experiments": experiments,
            "reactor_cold": spent["cold"],
            "wall_s": spent["wall_s"],
            "budget": {"cold": rung["budget"]["cold"], "wall_s": rung["budget"]["wall_s"]},
            "exhausted": rung["outcome"] == "BUDGET_EXHAUSTED",
        }
    resolved = rungs["R3"].get("t_star_resolve")  # A1.7: in the totals, not in M05's spend
    per["t_star_resolve"] = None if resolved is None else dict(resolved)
    colds = [per[n]["reactor_cold"] for n in RUNGS]
    walls = [per[n]["wall_s"] for n in RUNGS]
    if resolved is not None:
        colds.append(resolved["cold"])
        walls.append(resolved["wall_s"])
    per["journey"] = {  # null when a rung's spend is unrecorded (A1.6 item 4)
        "reactor_cold": None if None in colds else sum(colds),
        "wall_s": None if None in walls else math.fsum(walls),
        "budget": {
            "cold": sum(int(JOURNEY["budget"][n]["cold_experiments"]) for n in RUNGS),
            "wall_s": math.fsum(float(JOURNEY["budget"][n]["wall_s"]) for n in RUNGS),
        },
    }
    return per


LIMITATION_TEXT: Final = {
    "synthetic_dry_run": "Synthetic dry run: R1 is played by the stand-in; this record is never "
    "W25 evidence.",
    "INCOMPLETE": "{rung} is INCOMPLETE: not every grid point is verified.",
    "BUDGET_EXHAUSTED": "{rung} stopped BUDGET_EXHAUSTED under M07-budget-v1; it reports what it "
    "has.",
    "SURROGATE_NOT_PROMOTABLE": "R2 is SURROGATE_NOT_PROMOTABLE: M04's verdict for the bound "
    "parent is {verdict} ({reasons}); no surrogate evaluation was made.",
    "UNSUPPORTED": "{rung} is {outcome}; it contributes no decision.",
    "candidate": "R3's candidate status is {status}, not PARENT_LOCAL_EVIDENCE.",
    "study": "R3's study status is {status}.",
    "TC1_CONTRADICTED": "TC1_CONTRADICTED: the refined decision is below the best parent grid "
    "point by more than the noise floors; the journey's decision falls back to the grid.",
    "FE_NOT_DETERMINED": "{pair} is FE_NOT_DETERMINED: missing {missing}.",
    "noise_floor_unavailable": "R1 noise floor unavailable at {points} verified grid point(s); "
    "e_k is null there.",
    "bound": "{who}: {phrase}",
    "R3:record_rejected": "R3's M05 record is rejected: input condition {detail} of the M07 spec "
    "Amendment 1 A1.6 does not hold.",
    "R3:carry_anchor_missing": "R3's M05 record has no carry anchor: M05 states no run commit and "
    "no tested M05 manifest lists the record.",
    "R3:carry_identity_differs": "R3's M05 record is not carried: the journey's determining files "
    "differ between its anchor commit and J, and it was not re-run.",
    "R3:m05_cold_unrecorded": "M05's record states no cold count; R3's cold is null.",
    "R3:j_star_not_reproduced": "The journey's re-solve at T* did not reproduce M05's J* bit for "
    "bit; R3's constraint values are null (a finding to the design lane).",
    "R3:m05_wall_unrecorded": "M05's record states no spent wall; R3's wall is null and W25 (g) "
    "is not met.",
}


def limitations(record: Mapping[str, Any]) -> list[dict[str, str]]:
    """Every honest outcome the record holds, stated in its registered words (A12)."""
    rungs = record["rungs"]
    out: list[dict[str, str]] = []

    def add(code: str, text: str) -> None:
        out.append({"code": code, "text": text})

    if record["synthetic_dry_run"]:
        add("synthetic_dry_run", LIMITATION_TEXT["synthetic_dry_run"])
    for name in RUNGS:
        outcome = str(rungs[name]["outcome"])
        if outcome in ("INCOMPLETE", "BUDGET_EXHAUSTED"):
            add(f"{name}:{outcome}", LIMITATION_TEXT[outcome].format(rung=name))
        elif outcome == "SURROGATE_NOT_PROMOTABLE":
            add(
                f"{name}:{outcome}",
                LIMITATION_TEXT[outcome].format(
                    verdict=rungs[name]["m04_verdict"],
                    reasons=", ".join(rungs[name]["m04_reasons"]),
                ),
            )
        elif outcome.startswith("UNSUPPORTED("):
            add(
                f"{name}:{outcome}",
                LIMITATION_TEXT["UNSUPPORTED"].format(rung=name, outcome=outcome),
            )
    r3 = rungs["R3"]
    if "study_status" in r3 and r3["study_status"] not in ("DECISION_STABLE", "BUDGET_EXHAUSTED"):
        add(
            f"R3:study:{r3['study_status']}",
            LIMITATION_TEXT["study"].format(status=r3["study_status"]),
        )
    for code in r3.get("limitations") or ():
        detail = code.partition(":record_rejected:")[2]
        key = "R3:record_rejected" if detail else code
        add(code, LIMITATION_TEXT[key].format(detail=detail))
    candidate = r3.get("candidate")
    if candidate and candidate["status"] != PARENT_LOCAL_EVIDENCE:
        add(
            f"R3:candidate:{candidate['status']}",
            LIMITATION_TEXT["candidate"].format(status=candidate["status"]),
        )
    missing_e = sum(1 for p in rungs["R1"].get("grid") or [] if p["verified"] and p["e"] is None)
    if missing_e:
        add(
            "R1:noise_floor_unavailable",
            LIMITATION_TEXT["noise_floor_unavailable"].format(points=missing_e),
        )
    for pair_id in ("P01", "P13"):
        item = record["pairs"][pair_id]
        if item["fe_class"] == "FE_NOT_DETERMINED":
            add(
                f"{pair_id}:FE_NOT_DETERMINED",
                LIMITATION_TEXT["FE_NOT_DETERMINED"].format(
                    pair=pair_id, missing=", ".join(item["missing"])
                ),
            )
    if record["tc1"]["outcome"] == "TC1_CONTRADICTED":
        add("TC1_CONTRADICTED", LIMITATION_TEXT["TC1_CONTRADICTED"])
    for who, activity in decision_activities(record):
        phrase = bound_phrase(activity)
        if phrase is not None:
            add(f"bound:{who}", LIMITATION_TEXT["bound"].format(who=who, phrase=phrase))
    return out


def decision_activities(record: Mapping[str, Any]) -> list[tuple[str, str | None]]:
    """The decisions W25 (c) names — R0, R1, R3 and the journey's — with their bound activity."""
    rungs = record["rungs"]
    return [
        ("R0", rungs["R0"]["bound_activity"]),
        ("R1", rungs["R1"]["bound_activity"]),
        ("R3", rungs["R3"]["bound_activity"]),
        ("journey", record["decision"]["bound_activity"]),
    ]


def derive(record: dict[str, Any]) -> dict[str, Any]:
    """Every derived member of the record from its rungs: discrepancy, indifference set, pairs,
    TC-1, the journey's decision, parent checks, accounting and limitations. `check` re-derives
    with the same function and requires equality."""
    rungs = record["rungs"]
    r0, r1, r3 = rungs["R0"], rungs["R1"], rungs["R3"]
    grid = r1.get("grid") or []
    r1["discrepancy"] = discrepancy(r0, r1)
    with_e = [p for p in grid if p["e"] is not None or not p["verified"]]
    r1["indifference_set"] = indifference_set(with_e) if len(with_e) == len(grid) else None
    record["pairs"] = {
        "P01": pair("P01", r0["decision"], r1_after(r1), grid),
        "P13": pair("P13", r1["decision"], r3_after(r3), grid),
    }
    t_after, j_after, e_after, verified = r3_after(r3)
    candidate = (t_after, j_after if verified else None, e_after)
    record["tc1"] = {**tc1(*candidate, grid), "missing": tc1_missing(*candidate, grid)}
    record["decision"] = journey_decision(r1, r3, record["tc1"])
    record["parent_checks"] = parent_checks(record)
    record["accounting"] = accounting(rungs)
    record["limitations"] = limitations(record)
    return record


def build_record(
    rungs: Mapping[str, Any],
    *,
    synthetic_dry_run: bool,
    commit: str | None = None,
    environment: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "schema": SCHEMA,
        "registration_sha256": sha256_file(REGISTRATION_PATH),
        "commit": commit if commit is not None else _git("rev-parse", "HEAD"),
        "environment": dict(environment) if environment is not None else environment_block(),
        "case": case_block(),
        "rungs": copy.deepcopy(dict(rungs)),
        "pairs": {},
        "tc1": {},
        "decision": {},
        "accounting": {},
        "limitations": [],
        "artifacts": {},
        "synthetic_dry_run": synthetic_dry_run,
    }
    derive(record)
    record["artifacts"] = {
        name: [
            {
                "T_literal": e["T_literal"],
                "run_sha256": e["run_sha256"],
                "coupling_sha256": e.get("coupling_sha256"),
            }
            for e in record["rungs"][name].get("grid") or []
            if e["run_sha256"] is not None
        ]
        for name in GRID_RUNGS
    }
    return record


# == the report (spec §6.2, §6.3) ==================================================================


def _n(value: Any) -> str:
    """A number as the record holds it (repr: shortest round-trip), or a dash."""
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float):
        return repr(value)
    return str(value)


def render(record: Mapping[str, Any]) -> str:
    """`journey.md` from the record only; template text from the registration plus numbers."""
    rungs = record["rungs"]
    sections: list[list[str]] = [[] for _ in REPORT["sections"]]
    decision = record["decision"]

    summary = sections[0]
    summary.append(
        f"Case `{record['case']['id']}`, decision {SPEC_ID} on [{BOX_LITERALS[0]}, "
        f"{BOX_LITERALS[1]}] K, objective `{JOURNEY['objective']}` (mol/s, maximized)."
    )
    if decision["T"] is None:
        summary.append(
            f"The journey reports no decision: {decision['label']} ({decision['reason']})."
        )
    else:
        summary.append(
            f"The journey's decision: T_in = {_n(decision['T'])} K, `{decision['label']}`"
            + (f" ({decision['reason']})" if decision["reason"] else "")
            + f", bound activity {decision['bound_activity']}."
        )
    summary.append("")
    summary.append("Limitations stated by this record:")
    summary.append("")
    if record["limitations"]:
        summary.extend(f"- `{item['code']}`: {item['text']}" for item in record["limitations"])
    else:
        summary.append("- none")

    case = sections[1]
    case.append(f"- Case: `{record['case']['id']}`")
    for name, loop in record["case"]["loops"].items():
        case.append(f"- Loop `{name}`: `{loop['path']}` sha256 `{loop['sha256']}`")
    case.append(
        f"- Decision: {SPEC_ID}, box [{BOX_LITERALS[0]}, {BOX_LITERALS[1]}] K, nominal "
        f"{_n(T_NOMINAL)} K, decision tolerance {_n(DELTA_T)} K"
    )
    real = JOURNEY["variants"]["real"]
    case.append(f"- Parent: `{real['model_id']}` `{real['variant_id']}` sha256 `{real['sha256']}`")

    rung_lines = sections[2]
    for name in RUNGS:
        rung = rungs[name]
        rung_lines.append(
            f"- {name}: outcome `{rung['outcome']}`, decision {_n(rung['decision'])} K, "
            f"bound activity {_n(rung['bound_activity'])}"
        )
    r2 = rungs["R2"]
    rung_lines.append(
        f"- R2 reads M04's verdict `{r2['m04_verdict']}` for `{r2['surrogate_id']}`, reasons "
        f"{', '.join(f'`{r}`' for r in r2['m04_reasons']) or '—'}; "
        f"record `{r2['m04_record']['path']}` "
        f"sha256 `{r2['m04_record']['sha256']}`; surrogate evaluations {r2['evaluations']}."
    )
    r3 = rungs["R3"]
    if "study_status" in r3:
        candidate = r3["candidate"] or {}
        rung_lines.append(
            f"- R3 study status `{r3['study_status']}`; record `{r3['m05_record']['path']}` sha256 "
            f"`{r3['m05_record']['sha256']}` (carried from {r3['m05_record']['carried_from']}); "
            f"candidate T* = {_n(candidate.get('T'))} K, status `{_n(candidate.get('status'))}`, "
            f"J* = {_n(candidate.get('J'))} mol/s, e* = {_n(candidate.get('e'))} mol/s."
        )
    for who, activity in decision_activities(record):
        phrase = bound_phrase(activity)
        if phrase is not None:
            rung_lines.append(f"- {who}: {phrase}")

    grid_lines = sections[3]
    grid_lines.append(
        "| T (K) | J R0 (mol/s) | J R1 (mol/s) | e R1 (mol/s) | J R0 − J R1 | relative | X_pass R1 "
        "| Q preheater R1 (W) | Q flash R1 (W) | recycle R1 (mol/s) | purge NH3 R1 (mol/s) "
        "| extrapolated R1 |"
    )
    grid_lines.append("| --- " * 12 + "|")
    r0_grid = rungs["R0"].get("grid") or []
    r1_grid = rungs["R1"].get("grid") or []
    by_t = {row["T"]: row for row in rungs["R1"].get("discrepancy") or []}
    for literal in GRID_LITERALS:
        t = float(literal)
        a = _grid_point(r0_grid, t) or {}
        b = _grid_point(r1_grid, t) or {}
        d = by_t.get(t, {})
        grid_lines.append(
            f"| {literal} | {_n(a.get('J'))} | {_n(b.get('J'))} | {_n(b.get('e'))} "
            f"| {_n(d.get('dJ'))} | {_n(d.get('rel'))} | {_n(b.get('X_pass'))} "
            f"| {_n(b.get('Q_preheater_W'))} | {_n(b.get('Q_flash_W'))} "
            f"| {_n(b.get('n_recycle_mol_s'))} | {_n(b.get('n_purge_NH3_mol_s'))} "
            f"| {_n(b.get('extrapolated'))} |"
        )
    grid_lines.append("")
    grid_lines.append(
        "Verification status per point (outcome / certificate): "
        + "; ".join(f"{e['T_literal']} R0 {e['outcome']}/{_n(e['certificate'])}" for e in r0_grid)
        + ("; " if r0_grid and r1_grid else "")
        + "; ".join(f"{e['T_literal']} R1 {e['outcome']}/{_n(e['certificate'])}" for e in r1_grid)
        + "."
    )

    surrogate = sections[4]
    if r2["evaluations"] == 0:
        surrogate.append(
            f"No surrogate evaluation: R2 is `{r2['outcome']}` (M04 verdict `{r2['m04_verdict']}`)."
        )
    else:
        surrogate.append("| T (K) | surrogate − parent (mol/s) |")
        surrogate.append("| --- | --- |")
        surrogate.extend(f"| {_n(row['T'])} | {_n(row['dJ'])} |" for row in r2["discrepancy"])
        band = r2["band_containment"] or {}
        surrogate.append("")
        surrogate.append(
            f"Band containment: {_n(band.get('inside'))} of {_n(band.get('judged'))} grid points "
            "(a count, not a coverage estimate)."
        )

    refine = sections[5]
    refine.append(
        "| pair | t_before | t_after | j_before | j_after | e_before | e_after | class | missing |"
    )
    refine.append("| --- " * 9 + "|")
    for pair_id in ("P01", "P13"):
        p = record["pairs"][pair_id]
        refine.append(
            f"| {pair_id} | {_n(p['t_before'])} | {_n(p['t_after'])} | {_n(p['j_before'])} "
            f"| {_n(p['j_after'])} | {_n(p['e_before'])} | {_n(p['e_after'])} "
            f"| `{p['fe_class']}` | {', '.join(p['missing']) or '—'} |"
        )

    truth = sections[6]
    truth.append(
        f"TC-1: `{record['tc1']['outcome']}`; best verified parent grid point "
        f"{_n(record['tc1']['best_grid_T'])} K"
        + (f"; missing {', '.join(record['tc1']['missing'])}." if record["tc1"]["missing"] else ".")
    )
    for who, check in record["parent_checks"].items():
        if check is None:
            truth.append(f"- {who}: no parent evaluation.")
        else:
            truth.append(
                f"- {who}: {check['kind']}, run sha256 `{_n(check['run_sha256'])}`, "
                "constraints "
                + ("evaluated." if check["constraints"] is not None else "not available.")
            )

    spread = sections[7]
    spread.append(f"Indifference set (R1): {_n(rungs['R1'].get('indifference_set'))}.")
    if "study_status" in r3 and r3["candidate"]:
        spread.append(
            f"R3 noise floor e* = {_n(r3['candidate']['e'])} mol/s; indifference half-width "
            f"{_n(r3['candidate']['half_width'])} K."
        )
    spread.append(REPORT["not_established"][4])

    cost = sections[8]
    cost.append(
        "| rung | cold reactor experiments | budget | wall (s) | budget (s) "
        "| experiments (cold / in-process / store hit) | exhausted |"
    )
    cost.append("| --- " * 7 + "|")
    acct = record["accounting"]
    for name in RUNGS:
        a = acct[name]
        cost.append(
            f"| {name} | {_n(a['reactor_cold'])} | {a['budget']['cold']} | {_n(a['wall_s'])} "
            f"| {_n(a['budget']['wall_s'])} | {_n(a['experiments']['cold'])} / "
            f"{_n(a['experiments']['in_process'])} / {_n(a['experiments']['store_hit'])} "
            f"| {_n(a['exhausted'])} |"
        )
    resolved = acct["t_star_resolve"]
    if resolved is not None:
        cost.append(
            f"| R3 re-solve at T* | {resolved['cold']} | — | {_n(resolved['wall_s'])} | — "
            f"| {resolved['cold']} / {resolved['in_process']} / {resolved['store_hit']} | — |"
        )
    total = acct["journey"]
    cost.append(
        f"| journey | {_n(total['reactor_cold'])} | {total['budget']['cold']} "
        f"| {_n(total['wall_s'])} "
        f"| {_n(total['budget']['wall_s'])} | | |"
    )

    kinds = sections[9]
    kinds.append(
        "- Verification: every reported J is a certified coupled loop solve (outcome CONVERGED, "
        "certificate VERIFIED) of a registered test configuration; the labels are recomputed by "
        "`check` from the record's numbers."
    )
    kinds.append("- Validation: none. No number here is compared with plant or experimental data.")
    kinds.append(
        "- Optimality: none claimed. The grid and the study give local evidence on the box only."
    )

    sections[10].extend(f"{i}. {s}" for i, s in enumerate(REPORT["not_established"], start=1))

    prov = sections[11]
    prov.append(f"- Record schema `{record['schema']}`; commit `{record['commit']}`")
    prov.append(f"- Registration sha256 `{record['registration_sha256']}`")
    env = record["environment"]
    prov.append(
        f"- Environment: lock `{env['lock_sha256']}`, reactor lock `{env['reactor_lock_sha256']}`, "
        f"{env['platform']}, tree clean {_n(env['tree_clean'])}, "
        f"OMP_NUM_THREADS {_n(env.get('omp_num_threads'))}"
    )
    if "m05_record" in r3:
        prov.append(
            f"- M05 record `{r3['m05_record']['path']}`, sha256 `{r3['m05_record']['sha256']}`, "
            f"carried from `{r3['m05_record']['carried_from']}`"
        )
    prov.append(f"- Synthetic dry run: {_n(record['synthetic_dry_run'])}")
    prov.append("- Replay: `python scripts/m07_journey.py replay <dir>`; check: `… check <dir>`.")

    lines = [f"# M07 reference journey — {record['case']['id']}", ""]
    for title, body in zip(REPORT["sections"], sections, strict=True):
        lines.extend([f"## {title}", "", *body, ""])
    return "\n".join(lines)


# == check (spec §5 (h); A10, A12) =================================================================


def check(record: Mapping[str, Any], report: str | None) -> list[str]:
    """Every problem with a journey record and its report; empty when both are accepted.

    Structure (§6.1); the registration it names; each rung's outcome, decision and bound activity
    re-derived from its grid; R2 against M04's committed verdict; every derived member (pairs,
    TC-1, decision, parent checks, accounting, limitations) re-derived and equal; budgets respected
    unless `BUDGET_EXHAUSTED` is stated; the report equal to `render(record)`, its twelve headings
    in order, §11 verbatim, and no forbidden word."""
    problems: list[str] = []
    missing = [name for name in TOP_LEVEL if name not in record]
    if missing:
        return [f"record lacks {missing}"]
    if record["schema"] != SCHEMA:
        problems.append(f"schema {record['schema']!r} is not {SCHEMA!r}")
    if record["registration_sha256"] != sha256_file(REGISTRATION_PATH):
        problems.append("registration_sha256 is not the registration's")
    rungs = record["rungs"]
    if sorted(rungs) != sorted(RUNGS):
        return [*problems, f"rungs {sorted(rungs)} are not {list(RUNGS)}"]
    for name in GRID_RUNGS:
        problems.extend(_check_grid_rung(name, rungs[name]))
    problems.extend(_check_r2(rungs["R2"]))
    problems.extend(_check_r3(rungs["R3"]))
    for name in RUNGS:
        problems.extend(_check_budget(name, rungs[name]))
    rederived = derive(copy.deepcopy(dict(record)))
    for member in ("pairs", "tc1", "decision", "parent_checks", "accounting", "limitations"):
        if record.get(member) != rederived[member]:
            problems.append(f"{member} differs from its re-derivation")
    for name in ("R1",):
        for key in ("discrepancy", "indifference_set"):
            if rungs[name].get(key) != rederived["rungs"][name][key]:
                problems.append(f"{name} {key} differs from its re-derivation")
    candidate = rungs["R3"].get("candidate")
    if (
        not record["synthetic_dry_run"]
        and candidate
        and candidate["verified"]
        and rungs["R3"].get("t_star_resolve") is None
    ):
        problems.append("R3's verified candidate has no T* re-solve (A1.7)")
    if record["decision"].get("label") not in JOURNEY["decision_labels"]:
        problems.append(f"decision label {record['decision'].get('label')!r} is not registered")
    if report is not None:
        problems.extend(check_report(record, report))
    return problems


def _check_grid_rung(name: str, rung: Mapping[str, Any]) -> list[str]:
    problems: list[str] = []
    outcome = str(rung["outcome"])
    if outcome.startswith("UNSUPPORTED("):
        reason = outcome[len("UNSUPPORTED(") : -1]
        if reason not in UNSUPPORTED_REASONS:
            problems.append(f"{name} {outcome} is not a registered refusal")
        if rung.get("grid") or rung.get("decision") is not None:
            problems.append(f"{name} is {outcome} but carries a grid or a decision")
        return problems
    grid = rung.get("grid") or []
    literals = [entry.get("T_literal") for entry in grid]
    if literals != list(GRID_LITERALS):
        return [f"{name} grid {literals} is not the registered nine literals"]
    for entry in grid:
        absent = [key for key in GRID_ENTRY_KEYS if key not in entry]
        if absent:
            problems.append(f"{name} {entry['T_literal']} lacks {absent}")
            continue
        if entry["T"] != float(entry["T_literal"]):
            problems.append(f"{name} {entry['T_literal']}: T is not the literal's binary64 value")
        verified = entry["outcome"] == "CONVERGED" and entry["certificate"] == "VERIFIED"
        if entry["verified"] != verified:
            problems.append(f"{name} {entry['T_literal']}: verified disagrees with outcome")
        if verified and not (isinstance(entry["J"], float) and math.isfinite(entry["J"])):
            problems.append(f"{name} {entry['T_literal']}: verified without a finite J")
        if verified and entry["run_sha256"] is None:
            problems.append(f"{name} {entry['T_literal']}: verified without a run sha256")
        for item in entry["constraints"] or ():
            if "margin" not in item or item != with_margin(item):
                problems.append(f"{name} {entry['T_literal']}: a constraint's margin is not A1.7's")
                break
    if problems:
        return problems
    problems.extend(_check_stop(name, rung))
    decided = rung_decision(grid)
    expected = decided["outcome"]
    if outcome != "BUDGET_EXHAUSTED" and outcome != expected:
        problems.append(f"{name} outcome {outcome} is not the rule's {expected}")
    if rung["decision"] != decided["decision"]:
        problems.append(
            f"{name} decision {rung['decision']} is not the rule's {decided['decision']}"
        )
    if rung["bound_activity"] != bound_activity(rung["decision"]):
        problems.append(f"{name} bound activity is not the rule's")
    return problems


def _check_stop(name: str, rung: Mapping[str, Any]) -> list[str]:
    """A1.2's re-derivation of where the budget stopped a grid rung, from the recorded costs in
    grid order: each point is unevaluated iff the rung had stopped or spent + estimate would pass
    a cap; the spent totals are the points' left-to-right sums exactly; the rung is
    `BUDGET_EXHAUSTED` iff it stopped."""
    problems: list[str] = []
    budget = rung["budget"]
    cap_c, cap_w = budget["cold"], budget["wall_s"]
    est_c, est_w = budget_for(name).first_estimate, 0.0
    spent_c, spent_w = 0, 0.0
    stopped = False
    for entry in rung["grid"]:
        unevaluated = entry["outcome"] == NOT_EVALUATED_BUDGET
        if stopped or spent_c + est_c > cap_c or spent_w + est_w > cap_w:
            if not unevaluated:
                problems.append(f"{name} {entry['T_literal']} was evaluated after the budget stop")
            stopped = True
            continue
        if unevaluated:
            problems.append(
                f"{name} {entry['T_literal']} is NOT_EVALUATED(budget) with budget left"
            )
            continue
        cold, wall = int(entry["experiments"]["cold"]), float(entry["wall_s"])
        spent_c += cold
        spent_w += wall
        est_c, est_w = max(est_c, cold), max(est_w, wall)
        if spent_c > cap_c or spent_w > cap_w:
            stopped = True
    if budget["spent"] != {"cold": spent_c, "wall_s": spent_w}:
        problems.append(f"{name} budget.spent is not the re-derived {spent_c} / {spent_w!r}")
    if (rung["outcome"] == "BUDGET_EXHAUSTED") != stopped:
        problems.append(f"{name} BUDGET_EXHAUSTED disagrees with the re-derived budget stop")
    return problems


def _check_r2(r2: Mapping[str, Any]) -> list[str]:
    problems: list[str] = []
    facts = JOURNEY["m04_facts"]
    path = ROOT / str(r2["m04_record"]["path"])
    if path.is_file() and r2["m04_record"]["path"] == facts["record"]:
        manifest = json.loads(path.read_text(encoding="utf-8"))
        promotion = manifest["promotion"]
        if r2["m04_verdict"] != promotion["verdict"] or r2["m04_reasons"] != list(
            promotion["not_promotable"]
        ) + list(promotion["insufficient"]):
            problems.append("R2 does not carry M04's verdict and reasons verbatim")
        if r2["m04_record"]["sha256"] != sha256_file(path):
            problems.append("R2's M04 record sha256 is not the committed record's")
    if r2["m04_verdict"] != "PROMOTABLE":
        if r2["outcome"] != "SURROGATE_NOT_PROMOTABLE" or r2["evaluations"] != 0:
            problems.append("R2 evaluated a surrogate that is not promotable")
    elif r2["outcome"] == "SURROGATE_NOT_PROMOTABLE":
        problems.append("R2 says SURROGATE_NOT_PROMOTABLE under a PROMOTABLE verdict")
    elif str(r2["outcome"]).startswith("UNSUPPORTED("):
        refusal = unsupported(SURROGATE_LOOP_UNAVAILABLE)
        if r2["outcome"] != refusal or SURROGATE_LOOP_UNAVAILABLE not in UNSUPPORTED_REASONS:
            problems.append(f"R2 {r2['outcome']} is not the registered refusal {refusal}")
        if r2["evaluations"] != 0 or r2.get("decision") is not None:
            problems.append(f"R2 is {r2['outcome']} but evaluated or decided")
    elif r2["outcome"] in ("INDIFFERENT", "DECIDED", "INCOMPLETE") and r2["evaluations"] != len(
        GRID_LITERALS
    ):
        problems.append("R2 under a PROMOTABLE verdict lacks its nine surrogate evaluations")
    return problems


def _check_r3(r3: Mapping[str, Any]) -> list[str]:
    problems: list[str] = []
    outcome = str(r3["outcome"])
    if outcome.startswith("UNSUPPORTED("):
        if outcome not in {unsupported(r) for r in UNSUPPORTED_REASONS}:
            problems.append(f"R3 {outcome} is not a registered refusal")
        if r3.get("candidate") or r3.get("decision") is not None:
            problems.append(f"R3 is {outcome} but carries a candidate or a decision")
    elif r3.get("study_status") != outcome:
        problems.append("R3's outcome is not M05's study status")
    else:
        problems.extend(_check_r3_carry(r3))
    candidate = r3.get("candidate")
    problems.extend(_check_t_star_resolve(r3))
    if r3.get("decision") != (None if not candidate else candidate["T"]):
        problems.append("R3's decision is not its candidate's T")
    if r3.get("bound_activity") != bound_activity(r3.get("decision")):
        problems.append("R3 bound activity is not the rule's")
    return problems


def _check_t_star_resolve(r3: Mapping[str, Any]) -> list[str]:
    """A1.7 on R3: a re-solve only at a verified candidate, its four cost members, constraint
    values null exactly when `R3:j_star_not_reproduced` is stated, each margin the rule's."""
    resolved = r3.get("t_star_resolve")
    if resolved is None:
        return []
    candidate = r3.get("candidate")
    if not candidate or not candidate["verified"]:
        return ["R3 has a T* re-solve without a verified candidate"]
    problems: list[str] = []
    if sorted(resolved) != ["cold", "in_process", "store_hit", "wall_s"]:
        problems.append(f"R3 t_star_resolve members {sorted(resolved)} are not A1.7's")
    stated = "R3:j_star_not_reproduced" in (r3.get("limitations") or ())
    constraints = candidate["constraints"]
    if (constraints is None) != stated:
        problems.append("R3's constraints are null iff R3:j_star_not_reproduced is stated: not so")
    if isinstance(constraints, list) and any(
        not isinstance(item, Mapping) or item.get("margin") != with_margin(item)["margin"]
        for item in constraints
    ):
        problems.append("an R3 constraint margin is not the rule's")
    return problems


def _check_r3_carry(r3: Mapping[str, Any]) -> list[str]:
    """A1.6 items 2 and 4 on a carried or re-run R3: an anchor that is a commit or `rerun`; a
    null spend exactly when its limitation is stated; a wall source exactly when a wall is."""
    problems: list[str] = []
    carried = str(r3["m05_record"]["carried_from"])
    if carried != RERUN and not re.fullmatch(r"[0-9a-f]{40}", carried):
        problems.append(f"R3 carried_from {carried!r} is neither a commit nor {RERUN!r}")
    stated = set(r3.get("limitations") or ())
    spent = r3["budget"]["spent"]
    if (spent["cold"] is None) != ("R3:m05_cold_unrecorded" in stated):
        problems.append("R3's cold is null iff R3:m05_cold_unrecorded is stated: it is not")
    if (spent["wall_s"] is None) != ("R3:m05_wall_unrecorded" in stated):
        problems.append("R3's wall is null iff R3:m05_wall_unrecorded is stated: it is not")
    source = r3["budget"].get("wall_source")
    if (source is None) != (spent["wall_s"] is None) or source not in (
        None,
        "m05_record",
        "journey_measured",
    ):
        problems.append(f"R3 wall_source {source!r} does not match its wall")
    if (source == "m05_record" and carried == RERUN) or (
        source == "journey_measured" and carried != RERUN
    ):
        problems.append("R3's wall source does not match how the record was obtained")
    return problems


def _check_budget(name: str, rung: Mapping[str, Any]) -> list[str]:
    registered = JOURNEY["budget"][name]
    budget = rung["budget"]
    problems = []
    if budget["cold"] != registered["cold_experiments"] or budget["wall_s"] != registered["wall_s"]:
        problems.append(f"{name} budget is not M07-budget-v1's")
    grid = rung.get("grid") or []
    cold = sum(int(entry["experiments"]["cold"]) for entry in grid)
    if grid and budget["spent"]["cold"] != cold:
        problems.append(
            f"{name} spent cold {budget['spent']['cold']} is not its points' sum {cold}"
        )
    spent_c, spent_w = budget["spent"]["cold"], budget["spent"]["wall_s"]
    over = (spent_c is not None and spent_c > budget["cold"]) or (
        spent_w is not None and spent_w > budget["wall_s"]
    )
    if over and rung["outcome"] != "BUDGET_EXHAUSTED":
        problems.append(f"{name} overran its budget without stating BUDGET_EXHAUSTED")
    return problems


def check_report(record: Mapping[str, Any], report: str) -> list[str]:
    problems: list[str] = []
    headings = [line[3:] for line in report.splitlines() if line.startswith("## ")]
    if headings != list(REPORT["sections"]):
        problems.append("the report's headings are not the twelve registered sections in order")
    eleven = _section(report, REPORT["sections"][10])
    expected = [f"{i}. {s}" for i, s in enumerate(REPORT["not_established"], start=1)]
    if [line for line in eleven if line] != expected:
        problems.append("section 11 is not the registered not-established list verbatim")
    found = sorted({m.group(0).lower() for m in FORBIDDEN.finditer(report)})
    if found:
        problems.append(f"forbidden words in the report: {found}")
    phrases = [bound_phrase(a) for _, a in decision_activities(record)]
    active = any(p is not None for p in phrases)
    template_head = str(REPORT["bound_phrase"]).split("{side}")[0]
    if active != (template_head in report):
        problems.append("the bound phrase is not present exactly when a decision is bound-active")
    if report != render(record):
        problems.append("the report is not the rendering of the record")
    return problems


def _section(report: str, title: str) -> list[str]:
    lines = report.splitlines()
    try:
        start = lines.index(f"## {title}") + 1
    except ValueError:
        return []
    body = []
    for line in lines[start:]:
        if line.startswith("## "):
            break
        body.append(line)
    return body


# == run ===========================================================================================


def standin_runner(store: Path, model_version: str = "m07-journey") -> Any:
    from openflowsheet.adapters.experiments.runner import ExperimentRunner
    from openflowsheet.adapters.experiments.store import ExperimentStore, ListArtifactSink
    from openflowsheet.compiled import EvaluationContext
    from openflowsheet.thermo.pr_c1 import PrC1Provider

    return ExperimentRunner(
        ExperimentStore(store, ListArtifactSink()),
        PrC1Provider(),
        EvaluationContext(model_version=model_version, constants_sha256="0" * 64),
    )


def load_loop(name: str) -> dict[str, Any]:
    document: dict[str, Any] = json.loads(
        (ROOT / JOURNEY["loops"][name]).read_text(encoding="utf-8")
    )
    return document


def run_r0(
    artifacts: Path, runner: Any, clock: Callable[[], float] = time.monotonic
) -> dict[str, Any]:
    """R0 live: the stand-in loop at the nine grid points (spec §4.2; A08)."""
    budget = budget_for("R0")
    evaluate = LoopEvaluator(load_loop("standin"), runner, artifacts, "R0", clock)
    entries, exhausted = run_grid("R0", evaluate, budget)
    return grid_rung(entries, exhausted, budget)


#: `run_r1`'s default: M05's noise floor and P3 (`m05_parent_extras`); a test passes its own.
M05_EXTRAS: Final = "m05"


def run_r1(
    artifacts: Path,
    runner: Any,
    *,
    dry_run: bool,
    reactor: bool,
    extras: ParentExtras | None | str = M05_EXTRAS,
    clock: Callable[[], float] = time.monotonic,
) -> dict[str, Any]:
    """R1: the parent on the grid, or in a dry run the stand-in playing it (A10)."""
    if not dry_run and not reactor:
        return unsupported_rung("R1", REACTOR_UNAVAILABLE)
    document = load_loop("standin" if dry_run else "real")
    if extras == M05_EXTRAS:
        extras = m05_parent_extras(document, runner)
    budget = budget_for("R1")
    evaluate = LoopEvaluator(document, runner, artifacts, "R1", clock)
    entries, exhausted = run_grid(
        "R1", evaluate, budget, extras if callable(extras) else None, clock
    )
    return grid_rung(entries, exhausted, budget)


def run_journey(
    artifacts: Path,
    *,
    dry_run: bool = False,
    m05_record: Path | None = None,
    env_base: Path | None = None,
    extras: ParentExtras | None | str = M05_EXTRAS,
    runner: Any = None,
    clock: Callable[[], float] = time.monotonic,
    commit: str | None = None,
    environment: Mapping[str, Any] | None = None,
    out: Path | None = None,
    t_star: TStarResolve | None | str = M05_EXTRAS,
) -> dict[str, Any]:
    """R0, R1, R2, R3 in that order, then the T* re-solve (A1.7) on the journey's store. A real
    run (not `dry_run`) re-runs M05's study under `out` when its record does not carry (A1.6).
    The environment block is taken before any rung runs: R3's re-run writes under `out`, which
    would otherwise read as a dirty tree (build log J26)."""
    environment = environment if environment is not None else environment_block()
    runner = runner if runner is not None else standin_runner(artifacts / "store")
    reactor = dry_run or reactor_available(env_base)
    r0 = run_r0(artifacts, runner, clock)
    r1 = run_r1(artifacts, runner, dry_run=dry_run, reactor=reactor, extras=extras, clock=clock)
    r2 = r2_rung(ROOT / JOURNEY["m04_facts"]["record"], parent_grid=r1.get("grid") or [])
    if not reactor:
        r3 = unsupported_rung("R3", REACTOR_UNAVAILABLE)
    else:
        rerun = None if dry_run or out is None else m05_rerun(out, clock)
        r3 = r3_rung(m05_record, rerun=rerun)
        if t_star == M05_EXTRAS:
            t_star = None if dry_run else m05_t_star_resolver(load_loop("real"), runner)
        if callable(t_star):
            apply_t_star_resolve(r3, t_star, clock)
    return build_record(
        {"R0": r0, "R1": r1, "R2": r2, "R3": r3},
        synthetic_dry_run=dry_run,
        commit=commit,
        environment=environment,
    )


def dumps(record: Mapping[str, Any]) -> str:
    return json.dumps(record, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n"


def write(record: Mapping[str, Any], out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    (out / RECORD_NAME).write_text(dumps(record), encoding="utf-8")
    (out / REPORT_NAME).write_text(render(record), encoding="utf-8")


def any_unsupported(record: Mapping[str, Any]) -> bool:
    return any(str(r["outcome"]).startswith("UNSUPPORTED(") for r in record["rungs"].values())


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run")
    run.add_argument("--out", type=Path, required=True)
    run.add_argument("--artifacts", type=Path, required=True)
    run.add_argument("--m05-record", type=Path)
    run.add_argument("--env-base", type=Path)
    run.add_argument("--dry-run", action="store_true")
    for name in ("check", "render", "replay"):
        sub.add_parser(name).add_argument("directory", type=Path)
    args = parser.parse_args(argv)
    if args.command == "run":
        if (
            not args.dry_run
            and os.environ.get("OMP_NUM_THREADS") != "1"
            and reactor_available(args.env_base)
        ):
            print("run: R1, R3's re-solve and replay need OMP_NUM_THREADS=1 (Amendment 1 A1.7)")
            return 2
        record = run_journey(
            args.artifacts.resolve(),
            dry_run=args.dry_run,
            m05_record=args.m05_record,
            env_base=args.env_base,
            out=args.out,
        )
        write(record, args.out)
        print(f"journey written to {args.out}: decision {record['decision']['label']}")
        return 3 if any_unsupported(record) else 0
    if args.command == "replay":
        print("replay: not implemented before WO-4 (M07 spec §13); nothing was re-derived")
        return 2
    record = json.loads((args.directory / RECORD_NAME).read_text(encoding="utf-8"))
    if args.command == "render":
        (args.directory / REPORT_NAME).write_text(render(record), encoding="utf-8")
        return 0
    report_path = args.directory / REPORT_NAME
    report = report_path.read_text(encoding="utf-8") if report_path.is_file() else ""
    problems = check(record, report)
    for problem in problems:
        print(f"REJECT: {problem}")
    print("check: ACCEPT" if not problems else f"check: REJECT ({len(problems)})")
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
