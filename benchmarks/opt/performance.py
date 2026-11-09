"""OPT's performance record on the S11 revision flowsheets TH-R1, M1 and C-MW (OPT design §4.14,
§6 G17, §7 F5; WO-4). A record, not a pass/fail gate: per start, the wall time of the start's
certify, of the twin build, of Ipopt and of the V1-V6 verification; Ipopt's iterations and status;
the twin's residual, Jacobian and property-block calls; and the primal size.

Requests (`requests/perf/*.json`; decisions are the revision's own `role: fixed` specifications,
boxes kept inside the base regime, measured by certifying the box ends; objectives smooth
quadratic trackings with an interior optimum):
- **TH-R1**: decisions heater duty `SPEC-H-Q` ∈ [15, 35] kW and flash duty `SPEC-D-Q` ∈ [−5, 5]
  kW; min ((S5.n.H2O − 0.5 mol/s)/0.05)² + (Q_D/5 kW)²: a vapour make of 0.5 mol/s with an
  adiabatic flash preferred (the make depends on Q_H + Q_D only, so the second term fixes Q_D).
- **M1**: decision feed temperature `SPEC-S-IN1-T` ∈ [320, 348] K (feed bubble point 350.06 K);
  min ((S-DISTILLATE.n.B − 0.06 mol/s)/0.005)²: the distillate's B slip.
- **C-MW**: decision feed temperature `SPEC-S-IN1-T` ∈ [335 K, the revision's 348.6156 K] (the
  revision's feed is a saturated liquid, so the box ends there); min ((COL.stage.20.Q − 38.5 kW)/
  1 kW)²: the reboiler duty. Ipopt at the default `max_iter` 500 and `max_wall_time_s` 120 (F5).
Each request has two starts: the revision's own values, then one explicit point.

Phase times come from `optimize_revision`'s `progress` and `check` callbacks: `certify` is
`progress("start", k)` to the next `check()`; `twin` + `ipopt` is `progress("optimize", k)` to
the `check()` the record writer's `before_verification` makes (Ipopt's own time is the start
record's `wall_time_s`); `verify` runs from there to the next start's `check()`, or, for the last
start, to the return of `optimize_revision`, so it also holds the report's assembly and the
record writing.

Usage: `python benchmarks/opt/performance.py [--write | --check | RECORDS_DIR]`. `--write` and
`--check` write or check `requests/perf/*.json` (no solver needed); otherwise the requests run in
the audited NLP environment (`scripts/m03_nlp_check.sh`, `OMP_NUM_THREADS=1`), records go under
`RECORDS_DIR` (default a new temporary directory), one summary line per case is printed and the
numbers are written to `RECORDS_DIR/performance.json`.
"""

from __future__ import annotations

import json
import os
import platform
import sys
import tempfile
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
S11 = HERE.parents[1] / "benchmarks" / "s11"
REQUESTS = HERE / "requests" / "perf"
#: Case → the revision document, relative to `benchmarks/s11/`.
CASES = {
    "TH-R1": "thermal/TH-R1.json",
    "M1": "flowsheets/M1.json",
    "C-MW": "flowsheets/C-MW.json",
}
#: C-MW's feed temperature as committed (a saturated liquid at 101 325 Pa).
C_MW_FEED_T = 348.6155803604359


def _round(value: float) -> float:
    """12 significant digits: the tracking coefficients as written, not their binary noise."""
    return float(f"{value:.12g}")


def _tracking(text: str, terms: list[tuple[str, float, float]]) -> dict[str, Any]:
    """Σ weight·(name − target)² as the request's quadratic expression."""
    constant = 0.0
    linear: dict[str, float] = {}
    quadratic = []
    for name, target, weight in terms:
        constant += weight * target * target
        if target:
            linear[name] = _round(-2.0 * weight * target)
        quadratic.append({"a": name, "b": name, "coefficient": weight})
    return {
        "expression": {
            "constant": _round(constant),
            "linear": linear,
            "quadratic": quadratic,
            "text": text,
        },
        "sense": "minimize",
    }


def _decision(spec: str, box: tuple[float, float], scale: float, unit: str) -> dict[str, Any]:
    return {
        "lower": box[0],
        "scale": scale,
        "specification_id": spec,
        "unit": unit,
        "upper": box[1],
    }


def _request(
    case: str,
    decisions: list[dict[str, Any]],
    objective: dict[str, Any],
    explicit: list[list[float]],
) -> dict[str, Any]:
    return {
        "constraints": [],
        "decisions": decisions,
        "objective": objective,
        "problem_id": f"OPT-PERF-{case}",
        "request_format": "openflowsheet-optimization-request-v1",
        "starts": {"explicit": explicit, "halton": 0, "include_revision": True},
    }


def requests() -> dict[str, dict[str, Any]]:
    return {
        "TH-R1": _request(
            "TH-R1",
            [
                _decision("SPEC-H-Q", (15000.0, 35000.0), 10000.0, "W"),
                _decision("SPEC-D-Q", (-5000.0, 5000.0), 1000.0, "W"),
            ],
            _tracking(
                "((S5.n.H2O - 0.5)/0.05)^2 + (Q_D/5000)^2",
                [("S5.n.H2O", 0.5, 400.0), ("decision:SPEC-D-Q", 0.0, 4.0e-8)],
            ),
            [[32000.0, -2000.0]],
        ),
        "M1": _request(
            "M1",
            [_decision("SPEC-S-IN1-T", (320.0, 348.0), 10.0, "K")],
            _tracking(
                "((S-DISTILLATE.n.B - 0.06)/0.005)^2",
                [("S-DISTILLATE.n.B", 0.06, 40000.0)],
            ),
            [[325.0]],
        ),
        "C-MW": _request(
            "C-MW",
            [_decision("SPEC-S-IN1-T", (335.0, C_MW_FEED_T), 10.0, "K")],
            _tracking(
                "((COL.stage.20.Q - 38500)/1000)^2",
                [("COL.stage.20.Q", 38500.0, 1.0e-6)],
            ),
            [[338.0]],
        ),
    }


def _bytes(document: Any) -> bytes:
    return (json.dumps(document, indent=2, sort_keys=True) + "\n").encode()


def _phases(
    events: list[tuple[str, int | None, float]], starts: int, ended: float
) -> list[dict[str, float | None]]:
    """Per start: `certify`, `to_verification` (twin build + Ipopt) and `verify` seconds, from
    the callback events (module docstring)."""
    phases: list[dict[str, float | None]] = [
        {"certify_s": None, "to_verification_s": None, "verify_s": None} for _ in range(starts)
    ]
    for position, (stage, index, began) in enumerate(events):
        if stage == "start" and index is not None:
            following = events[position + 1][2] if position + 1 < len(events) else ended
            phases[index]["certify_s"] = following - began
        if stage != "optimize" or index is None:
            continue
        rest = events[position + 1 :]
        end = ended
        placed = None
        for offset, (later, _, at) in enumerate(rest):
            nxt = rest[offset + 1] if offset + 1 < len(rest) else None
            if later == "check" and nxt is not None and nxt[0] == "optimize":
                end = at
                break
            if later == "check" and placed is None:
                placed = at
        if placed is not None:
            phases[index]["to_verification_s"] = placed - began
            phases[index]["verify_s"] = end - placed
        else:
            phases[index]["to_verification_s"] = end - began
    return phases


def _primal_size(record_dir: Path | None, index: int) -> int | None:
    if record_dir is None:
        return None
    path = record_dir / "starts" / str(index) / "optimizer.json"
    if not path.exists():
        return None
    primal = json.loads(path.read_bytes()).get("final_primal")
    return len(primal) if primal is not None else None


def run_case(case: str, request: dict[str, Any], records: Path) -> dict[str, Any]:
    from openflowsheet.application.policies import DEFAULT_POLICY_ID, resolve_policy
    from openflowsheet.application.revision_routes import REVISION_ROUTES
    from openflowsheet.studies.nlp.revision import optimize_revision
    from openflowsheet.verify.certificate import CheckPolicy

    policy = resolve_policy(DEFAULT_POLICY_ID, "revision_eo")
    assert policy is not None
    document = json.loads((S11 / CASES[case]).read_bytes())
    events: list[tuple[str, int | None, float]] = []

    def progress(stage: str, info: Mapping[str, Any]) -> None:
        events.append((stage, info.get("start"), time.perf_counter()))

    def check() -> None:
        events.append(("check", None, time.perf_counter()))

    began = time.perf_counter()
    outcome = optimize_revision(
        document,
        request,
        directory=records / case,
        routes=REVISION_ROUTES,
        solve_policy=policy,
        check_policy=CheckPolicy(),
        check=check,
        progress=progress,
    )
    ended = time.perf_counter()
    report = outcome.report.as_document()
    starts = report["starts"]
    phases = _phases(events, len(starts), ended)
    decisions = len(request["decisions"])
    rows = []
    for index, (start, phase) in enumerate(zip(starts, phases, strict=True)):
        ipopt_s = start.get("wall_time_s")
        primal = _primal_size(outcome.record_dir, index)
        twin_s = None
        if phase["to_verification_s"] is not None and ipopt_s is not None:
            twin_s = phase["to_verification_s"] - ipopt_s
        rows.append(
            {
                "start": start.get("start"),
                "final_decisions": start.get("final_decisions"),
                "ipopt_status": start.get("ipopt_status"),
                "ipopt_message": start.get("ipopt_message"),
                "iterations": start.get("iterations"),
                "classification": start.get("classification"),
                "evaluations": start.get("evaluations"),
                "certify_s": phase["certify_s"],
                "twin_build_s": twin_s,
                "ipopt_s": ipopt_s,
                "verify_s": phase["verify_s"],
                "primal_size": primal,
                "free_columns": primal - decisions if primal is not None else None,
                "decisions": decisions,
                "ipopt_final": start.get("ipopt_final"),
            }
        )
    return {
        "status": report["status"],
        "reasons": [
            reason.get("code") if isinstance(reason, dict) else reason
            for reason in report.get("reasons", [])
        ],
        "total_s": ended - began,
        "record_dir": str(outcome.record_dir) if outcome.record_dir else None,
        "starts": rows,
    }


def _seconds(value: float | None) -> str:
    return "-" if value is None else f"{value:.2f}"


def _summary(case: str, result: dict[str, Any]) -> str:
    parts = []
    for index, row in enumerate(result["starts"]):
        calls = row["evaluations"] or {}
        parts.append(
            f"s{index} ipopt={row['ipopt_status']} it={row['iterations']} "
            f"cert={_seconds(row['certify_s'])} twin={_seconds(row['twin_build_s'])} "
            f"ipopt={_seconds(row['ipopt_s'])} verify={_seconds(row['verify_s'])} s "
            f"res={calls.get('residual_calls')} jac={calls.get('jacobian_calls')} "
            f"prop={calls.get('property_calls')} n={row['primal_size']}"
        )
    return (
        f"OPT perf {case}: {result['status']} {result['reasons']}; "
        + "; ".join(parts)
        + f"; total {result['total_s']:.2f} s"
    )


def main(argv: list[str]) -> int:
    files = {REQUESTS / f"{case}.json": _bytes(request) for case, request in requests().items()}
    if "--write" in argv or "--check" in argv:
        stale = []
        for path, payload in files.items():
            if "--write" in argv:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(payload)
            elif not path.exists() or path.read_bytes() != payload:
                stale.append(path.name)
        if stale:
            print(f"OPT performance: stale {stale}; run with --write")
            return 1
        print(f"OPT performance: {'written' if '--write' in argv else 'current'} requests")
        return 0
    records = Path(argv[0]) if argv else Path(tempfile.mkdtemp(prefix="opt-performance-"))
    records.mkdir(parents=True, exist_ok=True)
    results: dict[str, Any] = {
        "environment": {
            "python": platform.python_version(),
            "machine": platform.node(),
            "omp_num_threads": os.environ.get("OMP_NUM_THREADS"),
        },
        "cases": {},
    }
    for case in CASES:
        request = json.loads((REQUESTS / f"{case}.json").read_bytes())
        result = run_case(case, request, records)
        results["cases"][case] = result
        print(_summary(case, result), flush=True)
    (records / "performance.json").write_bytes(_bytes(results))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
