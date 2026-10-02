"""PTC-R1's saddle diagnostic: per-pseudo-step histories of the PTC arm's `MID` runs and controls.

**Diagnostic after `C_res`; not a result of the registered comparison; changes no verdict (R-118).**
Brief `docs/briefs/T08-ptc-r1-diagnostic.md`; context `docs/reviews/T08-verdict-V14b.md` §7, which
names the hypothesis (build-first spec §A3.6's risk): with T04 §7.7's SER settings Δτ passes
`2/s₊` within a few steps, after which a pseudo-step contracts toward the saddle `MID`.

**What it runs.** Only the PTC arm (`compare.PTC_ARM`), on the starts the committed
`results-<machine class>.json` classes `MID` under that arm, and, as controls, the PTC runs at the
starts PTC reaches and Newton does not (`summary.ptc_reached_newton_not`; every one of them ends
`LOW` or `HIGH`). Each run is `compare.run_start("ptc", row)` itself — the registered harness,
called unchanged.

**How the steps are captured (no numerics change).** Two pass-through shims, restored whatever
happens, like `compare._newton_blocks`:

- `region.solve_ptc` is wrapped to keep the `PtcRecord` it returns (T04 §7.8: every accepted
  pseudo-step with its `Δτ` and iterate, every rejected trial) and the problem's `variable_ids`,
  which the record's vectors are ordered by. The record is in memory only and the harness drops
  it, so it is read here.
- `ptc.solve_linear` is wrapped to take `sign det(M̂/Δτ + Ĵ_σ)` of the matrix it is handed, by a
  dense `slogdet` of a copy, before calling through with the same arguments. Each trial of the core
  calls it exactly once, in trial order; a call past the trials is the polish's Newton step.

Every re-run's record must equal the committed record exactly (`json.dumps` of both, so every float
byte-equal, the final state and outcome included); the first that does not stops the script and
nothing is written.

**Outputs:** `diagnostic-<machine class>.json` and `.md`, never overwritten. The summary reports
first crossings of `1/s₊` and `2/s₊` and the distance to `MID` along each run; it judges nothing.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import statistics
import sys
import time
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Final

import numpy as np

import openflowsheet.numerics.ptc as ptc_module
import openflowsheet.orchestrator.region as region_module
from benchmarks.t06.ensemble import host, provenance
from benchmarks.t08.ptc_r1 import compare
from openflowsheet.numerics.ptc import PtcRecord

__all__ = ["LABEL", "diagnose_run", "main", "render", "saddle_thresholds", "selection", "summarize"]

DIAGNOSTIC_FORMAT: Final = "t08-ptc-r1-diagnostic-v1"
#: Distances at which the summary counts the iterate a first `Δτ > 2/s₊` step starts from. Bins
#: for reporting only: no registered document defines the saddle's neighbourhood.
REPORTING_BINS: Final = (0.01, 0.1, 0.3, 1.0)
#: How many iterates (the start and the first pseudo-steps) the per-iterate medians cover.
REPORTED_ITERATES: Final = 9
LABEL: Final = (
    "Diagnostic after C_res; not a result of the registered comparison; changes no verdict (R-118)."
)


def saddle_thresholds() -> dict[str, float]:
    """`1/s₊` and `2/s₊` in seconds: the reference's `dtau_*_over_theta` times `θ` (build-first
    §A3.6; `θ = 1 s` on PTC-R1)."""
    reference = compare.reference()
    theta = float(reference["case"]["realization"]["theta_s"])
    saddle = reference["closed_form"]["saddle"]
    return {
        "singular_s": float(saddle["dtau_singular_over_theta"]) * theta,
        "contracting_s": float(saddle["dtau_contracting_over_theta"]) * theta,
    }


def _mapped(state: Mapping[str, float]) -> dict[str, float]:
    """§A1.5's map to `(x₁, x₂)` and the dimensionless ∞-distance to each root — the arithmetic of
    `compare.classify`, kept per root."""
    closed = compare.reference()["closed_form"]
    realization = compare.reference()["case"]["realization"]
    key_feed = float(realization["feed_B_mol_s"])
    t_f, t_s = float(realization["feed_T_K"]), float(realization["T_scale_K"])
    x1 = 1.0 - state[f"{compare.OUTLET}.n.B"] / key_feed
    x2 = (state[f"{compare.OUTLET}.T"] - t_f) / t_s
    out = {"x1": x1, "x2": x2}
    for name in compare.ROOTS:
        root = closed["steady_states"][name]
        out[f"d_{name}"] = max(abs(x1 - float(root["x1"])), abs(x2 - float(root["x2"])))
    return out


# -- the capture ------------------------------------------------------------------------------


@contextmanager
def _capture(
    records: list[tuple[tuple[str, ...], PtcRecord]], signs: list[list[int]]
) -> Iterator[None]:
    """The two pass-through shims (module docstring). `signs[a]` holds attempt `a`'s determinant
    signs in call order. Both originals are restored whatever happens."""
    original_solve: Callable[..., Any] = getattr(region_module, "solve_ptc")  # noqa: B009
    original_linear: Callable[..., Any] = getattr(ptc_module, "solve_linear")  # noqa: B009

    def solving(problem: Any, *args: Any, **kwargs: Any) -> Any:
        signs.append([])
        result, record = original_solve(problem, *args, **kwargs)
        records.append((tuple(problem.problem.variable_ids), record))
        return result, record

    def linear(matrix: Any, *args: Any, **kwargs: Any) -> Any:
        sign, _ = np.linalg.slogdet(np.array(matrix.toarray(), dtype=np.float64))
        if signs:
            signs[-1].append(int(sign))
        return original_linear(matrix, *args, **kwargs)

    setattr(region_module, "solve_ptc", solving)  # noqa: B010 - a module attribute
    setattr(ptc_module, "solve_linear", linear)  # noqa: B010
    try:
        yield
    finally:
        setattr(region_module, "solve_ptc", original_solve)  # noqa: B010
        setattr(ptc_module, "solve_linear", original_linear)  # noqa: B010


def _strict(record: Mapping[str, Any]) -> str:
    """A record as the committed file holds it: `compare._finite`, then compact sorted JSON."""
    return json.dumps(compare._finite(record), sort_keys=True, allow_nan=False)


def _attempt_history(
    variable_ids: Sequence[str], record: PtcRecord, signs: Sequence[int]
) -> dict[str, Any]:
    """One PTC attempt's trials in order — each pseudo-step's rejections, then its accepted trial —
    with `Δτ`, the verdict, the accepted iterate mapped by §A1.5 and the determinant sign."""

    def named(vector: Any) -> dict[str, float]:
        return dict(zip(variable_ids, (float(value) for value in vector), strict=True))

    trials: list[dict[str, Any]] = []
    rejections = list(record.rejections)
    for step in record.steps:
        while rejections and rejections[0].index == step.index:
            rejection = rejections.pop(0)
            trials.append(
                {"k": rejection.index, "tau_s": rejection.tau, "accepted": False}
                | {"reason": rejection.reason}
            )
        accepted = {"k": step.index, "tau_s": step.tau, "accepted": True}
        trials.append(accepted | _mapped(named(step.x)))
    trials.extend(
        {"k": r.index, "tau_s": r.tau, "accepted": False, "reason": r.reason} for r in rejections
    )
    if len(signs) - len(trials) not in (0, 1):
        raise AssertionError(f"{len(signs)} linear solves for {len(trials)} trials")
    for trial, sign in zip(trials, signs, strict=False):
        trial["det_sign"] = sign
    start = record.steps[0].x_before if record.steps else None
    return {
        "start": None if start is None else _mapped(named(start)),
        "trials": trials,
        "polish": record.polish,
        "polish_det_sign": signs[len(trials)] if len(signs) > len(trials) else None,
        "tau_end_s": record.tau_end,
    }


def diagnose_run(row: Sequence[Any], committed: Mapping[str, Any]) -> dict[str, Any]:
    """Re-run one start under the PTC arm with the capture, prove it reproduces `committed`
    byte-for-byte, and return its per-step history. Raises `AssertionError` if it does not."""
    records: list[tuple[tuple[str, ...], PtcRecord]] = []
    signs: list[list[int]] = []
    with _capture(records, signs):
        rerun = compare.run_start("ptc", row)
    if _strict(rerun) != _strict(committed):
        raise AssertionError(f"start ({row[0]}, {row[1]}) does not reproduce its committed record")
    return {
        "i": rerun["i"],
        "j": rerun["j"],
        "class": rerun["class"],
        "outcome": rerun["outcome"],
        "accepted_steps": rerun["accepted_steps"],
        "attempts": [
            _attempt_history(variable_ids, record, attempt_signs)
            for (variable_ids, record), attempt_signs in zip(records, signs, strict=True)
        ],
    }


def selection(results: Mapping[str, Any]) -> dict[str, list[Mapping[str, Any]]]:
    """The committed PTC records to re-run: the `MID` runs, and the controls at the starts PTC
    reaches and Newton does not."""
    ptc = {(r["i"], r["j"]): r for r in results["records"] if r["arm"] == "ptc"}
    mid = [ptc[(i, j)] for i, j in results["summary"]["ptc_mid_starts"]]
    controls = [ptc[(i, j)] for i, j in results["summary"]["ptc_reached_newton_not"]]
    if any(r["class"] not in ("LOW", "HIGH") for r in controls):
        raise AssertionError("a control does not end LOW or HIGH")
    return {"MID": mid, "control": controls}


# -- the summary (reports; judges nothing) ----------------------------------------------------


def _crossing(run: Mapping[str, Any], threshold: float) -> dict[str, Any] | None:
    """The first accepted pseudo-step of attempt 0 with `Δτ > threshold`: its index, `Δτ`, the
    distance to `MID` of the iterate it started from and of the one it reached; `None` if none."""
    attempt = run["attempts"][0]
    before = attempt["start"]
    for trial in attempt["trials"]:
        if not trial["accepted"]:
            continue
        if trial["tau_s"] > threshold:
            return {
                "k": trial["k"],
                "tau_s": trial["tau_s"],
                "d_MID_before": before["d_MID"],
                "d_MID_after": trial["d_MID"],
            }
        before = trial
    return None


def _stats(values: Sequence[float]) -> dict[str, float] | None:
    if not values:
        return None
    return {
        "min": min(values),
        "median": statistics.median(values),
        "max": max(values),
    }


def summarize(runs: Sequence[Mapping[str, Any]], thresholds: Mapping[str, float]) -> dict[str, Any]:
    """Per set (`MID`, control): the first crossings of `1/s₊` and `2/s₊`, the distance to `MID`
    along the run, determinant sign changes, rejections and polish verdicts."""
    out: dict[str, Any] = {}
    for group in ("MID", "control"):
        mine = [r for r in runs if r["set"] == group]
        entry: dict[str, Any] = {
            "runs": len(mine),
            "attempts_per_run": sorted({len(r["attempts"]) for r in mine}),
        }
        for name, threshold in thresholds.items():
            crossings = [_crossing(r, threshold) for r in mine]
            found = [c for c in crossings if c is not None]
            entry[f"first_exceeds_{name}"] = {
                "runs_crossing": len(found),
                "k_counts": dict(sorted(_count(c["k"] for c in found).items())),
                "tau_s": _stats([c["tau_s"] for c in found]),
                "d_MID_before": _stats([c["d_MID_before"] for c in found]),
                "d_MID_after": _stats([c["d_MID_after"] for c in found]),
            }
        accepted = [
            [t for t in r["attempts"][0]["trials"] if t["accepted"]] for r in mine if r["attempts"]
        ]
        entry["d_MID_start"] = _stats([r["attempts"][0]["start"]["d_MID"] for r in mine])
        entry["d_MID_min_over_run"] = _stats([min(t["d_MID"] for t in a) for a in accepted if a])
        entry["d_MID_final_accepted"] = _stats([a[-1]["d_MID"] for a in accepted if a])
        entry["max_tau_s"] = _stats([max(t["tau_s"] for t in a) for a in accepted if a])
        # The iterates' distance to `MID`: index 0 the start, index k + 1 after pseudo-step k.
        paths = [
            [r["attempts"][0]["start"]["d_MID"]] + [t["d_MID"] for t in a]
            for r, a in zip(mine, accepted, strict=True)
        ]
        entry["d_MID_median_by_iterate"] = [
            statistics.median(path[n] for path in paths if len(path) > n)
            for n in range(REPORTED_ITERATES)
        ]
        first = [_first_above(r, thresholds["contracting_s"]) for r in mine]
        before = [path[n] for path, n in zip(paths, first, strict=True) if n is not None]
        entry["d_MID_before_first_2s_step_at_most"] = {
            str(radius): sum(value <= radius for value in before) for radius in REPORTING_BINS
        }
        entry["d_MID_nonincreasing_from_first_2s_step"] = sum(
            all(b <= a for a, b in itertools.pairwise(path[n:]))
            for path, n in zip(paths, first, strict=True)
            if n is not None
        )
        entry["rejections_total"] = sum(
            not t["accepted"] for r in mine for a in r["attempts"] for t in a["trials"]
        )
        polish = _count(str(r["attempts"][-1]["polish"]) for r in mine)
        entry["polish"] = dict(sorted(polish.items()))
        entry["runs_with_det_sign_change"] = sum(
            len({t["det_sign"] for t in r["attempts"][0]["trials"]}) > 1 for r in mine
        )
        entry["first_det_sign_change_k"] = dict(
            sorted(_count(k for k in (_sign_change(r) for r in mine) if k is not None).items())
        )
        out[group] = entry
    return out


def _first_above(run: Mapping[str, Any], threshold: float) -> int | None:
    """The position among attempt 0's accepted pseudo-steps of the first with `Δτ > threshold`
    (so also the index, in the iterate path, of the iterate that step starts from)."""
    accepted = [t for t in run["attempts"][0]["trials"] if t["accepted"]]
    return next((n for n, t in enumerate(accepted) if t["tau_s"] > threshold), None)


def _count(items: Any) -> dict[Any, int]:
    counts: dict[Any, int] = {}
    for item in items:
        counts[item] = counts.get(item, 0) + 1
    return counts


def _sign_change(run: Mapping[str, Any]) -> int | None:
    """The pseudo-step index of the first trial whose determinant sign differs from trial 0's."""
    trials = run["attempts"][0]["trials"]
    for trial in trials:
        if trial["det_sign"] != trials[0]["det_sign"]:
            return int(trial["k"])
    return None


def _fmt(stats: Mapping[str, float] | None, spec: str = ".3g") -> str:
    if stats is None:
        return "—"
    return " / ".join(format(stats[key], spec) for key in ("min", "median", "max"))


def render(document: Mapping[str, Any]) -> str:
    """The summary as Markdown. The reading at the end is written by hand from these numbers."""
    summary = document["summary"]
    thresholds = document["thresholds"]
    lines = [
        f"# PTC-R1 saddle diagnostic — {document['host']['machine_class']}",
        "",
        f"**{LABEL}**",
        "",
        f"Commit `{document['provenance']['commit']}` (tree clean: "
        f"{document['provenance']['tree_clean']}); source `{document['source']['path']}` "
        f"(sha256 `{document['source']['sha256'][:16]}…`). Every re-run reproduced its committed "
        f"record byte-for-byte ({document['reproduced']} of {len(document['runs'])}).",
        f"Thresholds: `1/s₊ = {thresholds['singular_s']:.6g} s`, "
        f"`2/s₊ = {thresholds['contracting_s']:.6g} s`. Statistics are min / median / max.",
        "",
        "| set | runs | crosses 1/s₊ | first k (count) | Δτ there [s] | crosses 2/s₊ | "
        "first k (count) | Δτ there [s] |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for group, entry in summary.items():
        one, two = entry["first_exceeds_singular_s"], entry["first_exceeds_contracting_s"]
        lines.append(
            f"| {group} | {entry['runs']} | {one['runs_crossing']} | {_counts(one['k_counts'])} | "
            f"{_fmt(one['tau_s'])} | {two['runs_crossing']} | {_counts(two['k_counts'])} | "
            f"{_fmt(two['tau_s'])} |"
        )
    lines += [
        "",
        "Distance to `MID` (dimensionless ∞-norm, §A1.5):",
        "",
        "| set | at the start | before first Δτ > 2/s₊ step | after it | min over run | "
        "last accepted step (pre-polish) |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for group, entry in summary.items():
        two = entry["first_exceeds_contracting_s"]
        lines.append(
            f"| {group} | {_fmt(entry['d_MID_start'])} | {_fmt(two['d_MID_before'])} | "
            f"{_fmt(two['d_MID_after'])} | {_fmt(entry['d_MID_min_over_run'])} | "
            f"{_fmt(entry['d_MID_final_accepted'])} |"
        )
    lines += [
        "",
        "Median distance to `MID` by iterate (0 = the start, n = after pseudo-step n − 1):",
        "",
        "| set | " + " | ".join(str(n) for n in range(REPORTED_ITERATES)) + " |",
        "| --- |" + " --- |" * REPORTED_ITERATES,
    ]
    for group, entry in summary.items():
        medians = " | ".join(format(value, ".3g") for value in entry["d_MID_median_by_iterate"])
        lines.append(f"| {group} | {medians} |")
    lines += [
        "",
        "The iterate each run's first `Δτ > 2/s₊` step starts from, counted by its distance to "
        "`MID` (reporting bins, not a registered neighbourhood), and the runs whose distance to "
        "`MID` never increases from that iterate on:",
        "",
    ]
    for group, entry in summary.items():
        bins = ", ".join(
            f"≤ {radius}: {count}"
            for radius, count in entry["d_MID_before_first_2s_step_at_most"].items()
        )
        lines.append(
            f"- {group} ({entry['runs']}): {bins}; non-increasing from there: "
            f"{entry['d_MID_nonincreasing_from_first_2s_step']}."
        )
    lines += ["", "Other facts:", ""]
    for group, entry in summary.items():
        lines.append(
            f"- {group}: attempts per run {entry['attempts_per_run']}; largest Δτ "
            f"{_fmt(entry['max_tau_s'])} s; rejected trials {entry['rejections_total']}; polish "
            f"{entry['polish']}; runs whose `sign det(M̂/Δτ + Ĵ_σ)` changes "
            f"{entry['runs_with_det_sign_change']} (first change at k: "
            f"{_counts(entry['first_det_sign_change_k'])})."
        )
    return "\n".join(lines) + "\n"


def _counts(counts: Mapping[Any, int]) -> str:
    return ", ".join(f"{key} ({value})" for key, value in counts.items()) or "—"


# -- the command ------------------------------------------------------------------------------


def _run(out_dir: Path) -> int:
    machine = host()
    stem = out_dir / f"diagnostic-{machine['machine_class']}"
    if stem.with_suffix(".json").exists() or stem.with_suffix(".md").exists():
        print(f"{stem}.json/.md exists; a diagnostic is never overwritten", file=sys.stderr)
        return 1
    differences = compare.case_differences()
    if differences:
        print(f"case.json does not recompute: {differences}; nothing run", file=sys.stderr)
        return 1
    origin = provenance(compare.REPO_ROOT)
    if not origin["tree_clean"]:
        print("the tree is not clean; a diagnostic must be attributable", file=sys.stderr)
        return 1
    source = compare.CASE_DIR / f"results-{machine['machine_class']}.json"
    if not source.exists():
        print(f"{source} does not exist; nothing to diagnose", file=sys.stderr)
        return 1
    results = json.loads(source.read_text(encoding="utf-8"))
    rows = {(int(row[0]), int(row[1])): row for row in compare.start_rows()}
    began = time.perf_counter()
    runs = [
        {"set": group} | diagnose_run(rows[(r["i"], r["j"])], r)
        for group, committed in selection(results).items()
        for r in committed
    ]
    thresholds = saddle_thresholds()
    document: dict[str, Any] = {
        "format": DIAGNOSTIC_FORMAT,
        "label": LABEL,
        "provenance": origin,
        "host": machine,
        "source": {
            "path": source.relative_to(compare.REPO_ROOT).as_posix(),
            "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        },
        "thresholds": thresholds,
        "reproduced": len(runs),
        "wall_time_s": time.perf_counter() - began,
        "summary": summarize(runs, thresholds),
        "runs": runs,
    }
    stem.with_suffix(".json").write_text(
        json.dumps(compare._finite(document), indent=1, allow_nan=False) + "\n", encoding="utf-8"
    )
    stem.with_suffix(".md").write_text(render(document), encoding="utf-8")
    print(f"wrote {stem}.json and {stem}.md")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--run", action="store_true", required=True, help="run and write")
    parser.add_argument("--out-dir", type=Path, default=compare.CASE_DIR)
    arguments = parser.parse_args(argv)
    return _run(arguments.out_dir)


if __name__ == "__main__":
    sys.exit(main())
