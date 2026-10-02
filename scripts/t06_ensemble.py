"""T06's robustness ensemble: generate the published starts, run them, report, replay (M7, W6).

Spec `docs/derivations/T06-corpus-spec.md` §6–§7, §10 (Amendments 1, 2 and 5). Run from the
repository root with the project environment (`PYTHONPATH=src:.`).

    python scripts/t06_ensemble.py generate [--holdout]    # the starts file, once, on ref-x86-64
    python scripts/t06_ensemble.py check [--holdout]       # regenerates; bytes on ref-x86-64
    python scripts/t06_ensemble.py run --run-id ID --out R.json [--allow-dirty]
                                       [--cases NET-01 …] [--starts 0 1 …]
    python scripts/t06_ensemble.py report R.json [--out report.txt] [--require-gate]
    python scripts/t06_ensemble.py replay R.json [--cases …] [--starts …]
    python scripts/t06_ensemble.py compare R-a.json R-b.json [R-c.json …]   # A35, reported
    python scripts/t06_ensemble.py a98 run2r-<class>.json [--against run2-<class>.json]

`generate` is the only command that writes a starts file; it writes on `ref-x86-64` only (§6.5,
§7.5 (A5)) and refuses to overwrite one (`--force`, for the nominal file only, is for a
design-lane amendment, §6.4, or a re-emission for a moved provider identity, §6.5 (A3), whose
only differing path must be that identity). `--holdout` draws `holdout1` (§7.6 (A5)): the frozen
generator at start indices 20…39, never re-drawn. `run` scores a published file and never
regenerates it; it writes format `t06-ensemble-results-v2` (§6.6 (A5)) and refuses a dirty tree
without `--allow-dirty`. The run id `holdout1` scores the holdout file and every other id the
nominal one. `report` renders the holdout with its header and no gate line. `replay` re-runs
recorded starts and compares with `run.compare.differences` under `K04-numerical-policy-v1` (R0
exactly, floats within the policy, wall times excluded); by default it replays each case's first
recorded start and every recorded failure (§10, §7.6 (A5)). `a98` compares run 2r with run 2's
same-class file (A98).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT))

from t06_ensemble_support import HOLDOUT_FILE, STARTS_FILE, ensemble_cases  # noqa: E402

from benchmarks.t06 import ensemble, generator  # noqa: E402
from openflowsheet.canonical import canonical_json  # noqa: E402
from openflowsheet.run.compare import differences  # noqa: E402
from openflowsheet.thermo.syn001 import Syn001Provider  # noqa: E402


def _starts_file(holdout: bool) -> Path:
    return HOLDOUT_FILE if holdout else STARTS_FILE


def _generate(holdout: bool) -> dict[str, Any]:
    """The starts document as `generate` writes it. The nominal file records the policies it was
    generated under (run 1's, `ensemble.run_1`; §6.6 (A4)); the holdout records each case's
    current registered policy and is `generator.generate_start` at 20…39 (§7.6 (A5))."""
    cases = ensemble_cases()
    generated = []
    for case in cases:
        setup = ensemble.setup(case)
        if holdout:
            starts: list[generator.Start] = []
            failures: list[generator.GenerationFailure] = []
            for index in ensemble.HOLDOUT_INDICES:
                drawn = generator.generate_start(setup, index)
                if isinstance(drawn, generator.Start):
                    starts.append(drawn)
                else:
                    failures.append(drawn)
        else:
            starts, failures = generator.generate_case(setup)
        print(
            f"{case.case:7} {case.path:11} {len(setup.coordinates):3} coordinates, "
            f"{len(starts)} starts, {len(failures)} F-GEN",
            flush=True,
        )
        generated.append((setup, starts, failures))
    generated_under = ensemble.registered()["run_1"]["policies"]
    described = Syn001Provider().describe()
    return generator.document(
        generated,
        policies={
            case.case: case.policy.policy_id if holdout else generated_under[case.path]
            for case in cases
        },
        provider={
            "provider_id": described.provider_id,
            "implementation_sha256": described.implementation_sha256,
            "data_sha256": described.data_sha256,
        },
        machine=ensemble.host(),
    )


def generate(arguments: argparse.Namespace) -> int:
    machine = ensemble.machine_class()
    if machine != ensemble.REFERENCE_CLASS:
        print(f"machine class {machine}: starts are generated on {ensemble.REFERENCE_CLASS} only")
        return 2
    if arguments.holdout and arguments.force:
        print("the holdout is drawn once and never re-drawn (spec §7.6 (A5)); --force refused")
        return 2
    out = Path(arguments.out) if arguments.out else _starts_file(arguments.holdout)
    if out.exists() and not arguments.force:
        print(f"{out} exists: the published starts are generated once (spec §6.5, §7.6 (A5))")
        return 2
    starts = _generate(arguments.holdout)
    digest = generator.write(out, starts)
    print(json.dumps(starts["counts"], indent=1, sort_keys=True))
    print(f"wrote {out} ({out.stat().st_size} bytes), sha256 {digest}")
    return 1 if starts["counts"]["generation_failures"] and not arguments.holdout else 0


def check(arguments: argparse.Namespace) -> int:
    """§6.5: on the reference machine class the regeneration is byte-identical; elsewhere the
    regenerated document is reported against the file under the numerical policy."""
    path = Path(arguments.file) if arguments.file else _starts_file(arguments.holdout)
    published = path.read_bytes()
    recorded = json.loads(published)
    regenerated = _generate(arguments.holdout)
    raw = canonical_json(regenerated)
    print(f"published sha256 {hashlib.sha256(published).hexdigest()}")
    print(f"regenerated sha256 {hashlib.sha256(raw).hexdigest()}")
    if raw == published:
        print("byte-identical")
        return 0
    found = differences(regenerated, recorded, policy_id="K04-numerical-policy-v1")
    same_host = regenerated["host"] == recorded["host"]
    print(
        f"not byte-identical; {len(found)} differences under the numerical policy "
        f"({'same host: a defect' if same_host else 'another host: reported'})"
    )
    for line in found[:50]:
        print("  " + line)
    return 1 if same_host else 0


def _selected(case: ensemble.EnsembleCase, arguments: argparse.Namespace) -> bool:
    return not arguments.cases or case.case in arguments.cases


def _fired(record: dict[str, Any]) -> str:
    fired = [entry["result"] for entry in record["refinements"] if entry["fired"]]
    return f" refined={','.join(fired)}" if fired else ""


def run(arguments: argparse.Namespace) -> int:
    holdout = arguments.run_id == ensemble.HOLDOUT_RUN_ID
    path = Path(arguments.file) if arguments.file else _starts_file(holdout)
    if holdout != (path.resolve() == HOLDOUT_FILE.resolve()):
        print(
            f"run id {arguments.run_id!r} with {path}: `{ensemble.HOLDOUT_RUN_ID}` scores the "
            "holdout file, and only it does (spec §7.6 (A5))"
        )
        return 2
    provenance = ensemble.provenance(ROOT)
    if not provenance["tree_clean"] and not arguments.allow_dirty:
        print("the working tree is not clean: a run record from a dirty tree is never evidence")
        print("(spec §6.6 (A5)); commit first, or pass --allow-dirty for a record that is not")
        return 2
    published = json.loads(path.read_bytes())
    by_case = {entry["case"]: entry for entry in published["cases"]}
    cases = [case for case in ensemble_cases() if _selected(case, arguments)]
    records: list[dict[str, Any]] = []
    meta: dict[str, Any] = {}
    for case in cases:
        entry = by_case[case.case]
        meta[case.case] = ensemble.facts(case)
        chosen = [
            s for s in entry["starts"] if not arguments.starts or s["start"] in arguments.starts
        ]
        for start in chosen:
            record = ensemble.run_start(case, start)
            records.append(record)
            print(
                f"{case.case:7} {start['start']:02d} {ensemble.classify(record):32} "
                f"{record['outcome']!s:22} "
                f"{(record['certificate'] or {}).get('verdict')!s:10} "
                f"rescued={ensemble.rescued(record)!s:5} {record['times']['total']:.3f} s"
                f"{_fired(record)}",
                flush=True,
            )
        for failure in entry["generation_failures"]:
            if not arguments.starts or failure["start"] in arguments.starts:
                records.append(ensemble.generation_failure_record(case, failure))
    results = {
        "format": ensemble.RESULTS_FORMAT,
        "run_id": arguments.run_id,
        **provenance,
        "starts_file": str(path.resolve().relative_to(ROOT)),
        "starts_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "policies": ensemble.policies(cases),
        "host": ensemble.host(),
        "cases": meta,
        "records": records,
    }
    Path(arguments.out).write_text(json.dumps(results, indent=1, sort_keys=True) + "\n")
    summary = ensemble.report(records, meta, published)
    print(
        f"S = {summary['S']} of {summary['N']} (first {summary['S_first']}, rescued "
        f"{summary['S_rescued']}); classes {summary['classes']}"
    )
    return 0


def _registered_run2(machine: str) -> dict[str, Any] | None:
    """The registry's `ensemble.runs` entry of run 2 on the class, if any (W29)."""
    for entry in ensemble.registered().get("runs", []):
        if entry["run_id"] == "run2" and entry["machine_class"] == machine:
            return dict(entry)
    return None


def render(results: dict[str, Any]) -> tuple[str, dict[str, Any], bool]:
    """The report's text for a run document, its summary, and whether it is the holdout's."""
    published = json.loads((ROOT / results["starts_file"]).read_bytes())
    summary = ensemble.report(results["records"], results["cases"], published)
    holdout = None
    if results["starts_file"] == str(HOLDOUT_FILE.relative_to(ROOT)):
        machine = results["host"]["machine_class"]
        run2 = _registered_run2(machine)
        holdout = {
            "run_id": results.get("run_id", ensemble.HOLDOUT_RUN_ID),
            "machine_class": machine,
            "s_run2": None if run2 is None else int(run2["S"]),
        }
    run = None
    if results["format"] == ensemble.RESULTS_FORMAT:
        run = {
            "run_id": results["run_id"],
            "commit": results["commit"],
            "tree_clean": results["tree_clean"],
            "machine_class": results["host"]["machine_class"],
            "starts_sha256": results["starts_sha256"],
        }
    return ensemble.render(summary, run=run, holdout=holdout), summary, holdout is not None


def report(arguments: argparse.Namespace) -> int:
    results = json.loads(Path(arguments.results).read_text())
    text, summary, holdout = render(results)
    if holdout and arguments.require_gate:
        print("the holdout is reported and never gated (spec §7.6 (A5)); --require-gate refused")
        return 2
    if arguments.out:
        Path(arguments.out).write_text(text)
    print(text)
    if arguments.require_gate and not summary["gate"]["pass"]:
        print("GATE FAILED (spec §7.3): a failed gate is reported as failed")
        return 1
    return 0


def _label(results: dict[str, Any]) -> str:
    """A run's machine class: the v2 record's; a v1 file's `machine_class` is the pre-A5 literal
    (the verdicts' P2), so it is labelled by its `architecture`."""
    if results["format"] == ensemble.RESULTS_FORMAT:
        return f"{results['run_id']}@{results['host']['machine_class']}"
    return f"v1@{results['host']['architecture']}"


def compare(arguments: argparse.Namespace) -> int:
    """§10, A35: the per-start success classification of runs of the same published starts on
    different machine classes, pairwise; disagreements are counted and listed — reported, not
    promised."""
    runs = [json.loads(Path(path).read_text()) for path in arguments.results]
    if len({run["starts_sha256"] for run in runs}) != 1:
        print("the runs scored different starts files")
        return 2
    labels = [_label(run) for run in runs]
    classified = [
        {(r["case"], r["start"]): ensemble.classify(r) for r in run["records"]} for run in runs
    ]
    for i in range(len(runs)):
        for j in range(i + 1, len(runs)):
            keys = sorted(set(classified[i]) | set(classified[j]))
            disagreements = [
                (key, classified[i].get(key), classified[j].get(key))
                for key in keys
                if classified[i].get(key) != classified[j].get(key)
            ]
            print(
                f"{len(keys)} starts; {len(disagreements)} classification disagreements "
                f"({labels[i]} vs {labels[j]})"
            )
            for (case, start), left, right in disagreements:
                print(f"  {case} {start:02d}: {left} vs {right}")
    return 0


def replay(arguments: argparse.Namespace) -> int:
    results = json.loads(Path(arguments.results).read_text())
    published = json.loads((ROOT / results["starts_file"]).read_bytes())
    starts = {
        (entry["case"], start["start"]): start
        for entry in published["cases"]
        for start in entry["starts"]
    }
    cases = {case.case: case for case in ensemble_cases()}
    first: dict[str, int] = {}
    for record in results["records"]:
        first.setdefault(record["case"], record["start"])
    mismatches = 0
    for record in results["records"]:
        key = (record["case"], record["start"])
        if arguments.cases and record["case"] not in arguments.cases:
            continue
        if arguments.starts:
            if record["start"] not in arguments.starts:
                continue
        elif record["start"] != first[record["case"]] and ensemble.classify(record) == "SUCCESS":
            continue
        if key not in starts:
            print(f"{key}: not generated (F-GEN); nothing to replay")
            continue
        emitted = ensemble.run_start(cases[record["case"]], starts[key])
        found = ensemble.replay_differences(record, emitted)
        mismatches += bool(found)
        print(f"{record['case']:7} {record['start']:02d} {'MATCH' if not found else 'DIFFER'}")
        for line in found[:10]:
            print("    " + line)
    return 1 if mismatches else 0


def a98(arguments: argparse.Namespace) -> int:
    """A98 (b)–(c): run 2r against run 2's same-class committed file (the registry's
    `ensemble.runs`), with A90 (A5)'s expected refinements on `ref-x86-64`. Exit 1 on any
    discrepancy — reported to the design lane and the `verdict` agent, never resolved by editing
    a record."""
    rerun = json.loads(Path(arguments.results).read_text())
    machine = rerun["host"]["machine_class"]
    if arguments.against:
        against = Path(arguments.against)
    else:
        entry = _registered_run2(machine)
        if entry is None:
            print(f"no registered run 2 file on {machine}")
            return 2
        against = ROOT / entry["file"]
    run2 = json.loads(against.read_text())
    expected = ensemble.A90_EXPECTED_REF_X86_64 if machine == ensemble.REFERENCE_CLASS else None
    found = ensemble.a98_discrepancies(rerun, run2, expected)
    print(f"A98: {rerun.get('run_id')} on {machine} ({rerun.get('commit')}) against {against}")
    print(
        f"{found['starts']} starts; S {found['S'][0]} vs run 2 {found['S'][1]}; S^first "
        f"{found['S_first'][0]} vs {found['S_first'][1]}"
    )
    print(
        f"refinements {found['refinements']}"
        + ("" if expected is not None else " (reported; no expectation on this class)")
    )
    states = found["state_bitwise_differences"]
    print(
        f"final states differing bitwise (reported): {len(states)}"
        + "".join(f"; {s}" for s in states)
    )
    for line in found["discrepancies"]:
        print(f"DISCREPANCY {line}")
    print(f"{len(found['discrepancies'])} discrepancies")
    return 1 if found["discrepancies"] else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    g = commands.add_parser("generate")
    g.add_argument("--holdout", action="store_true")
    g.add_argument("--out", default="")
    g.add_argument("--force", action="store_true")
    g.set_defaults(handler=generate)
    c = commands.add_parser("check")
    c.add_argument("--holdout", action="store_true")
    c.add_argument("--file", default="")
    c.set_defaults(handler=check)
    r = commands.add_parser("run")
    r.add_argument("--run-id", required=True)
    r.add_argument("--file", default="")
    r.add_argument("--out", required=True)
    r.add_argument("--allow-dirty", action="store_true")
    r.add_argument("--cases", nargs="*", default=[])
    r.add_argument("--starts", nargs="*", type=int, default=[])
    r.set_defaults(handler=run)
    p = commands.add_parser("report")
    p.add_argument("results")
    p.add_argument("--out", default="")
    p.add_argument("--require-gate", action="store_true")
    p.set_defaults(handler=report)
    k = commands.add_parser("compare")
    k.add_argument("results", nargs="+")
    k.set_defaults(handler=compare)
    y = commands.add_parser("replay")
    y.add_argument("results")
    y.add_argument("--cases", nargs="*", default=[])
    y.add_argument("--starts", nargs="*", type=int, default=[])
    y.set_defaults(handler=replay)
    a = commands.add_parser("a98")
    a.add_argument("results")
    a.add_argument("--against", default="")
    a.set_defaults(handler=a98)
    arguments = parser.parse_args()
    if arguments.command == "compare" and len(arguments.results) < 2:
        parser.error("compare needs at least two run files")
    return int(arguments.handler(arguments))


if __name__ == "__main__":
    sys.exit(main())
