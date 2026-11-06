"""The standing RC job's local steps 2–17 and their records (RP §6.1, §6.4–§6.6, §6.9).

The library behind `scripts/release_rc.py`'s `local`, `record`, `ci` and `records` subcommands. It
ports 0.3.0's RC runner (`evidence/S13/a3e508e3…/tools/run_local.sh` with `run_step14.sh`), the
record writers of its `tools/m07_rc_external.py.txt` (steps 11–16) and `g11record.py.txt` (step
12's `r375.audit`), `fetch_ci.sh` and `collect_records.py.txt`. Record paths and check ids are
0.3.0's (RP §6.1). What RP changed is applied, nothing else:

- step 12 runs G11 through the store-keeping wrapper in its own first run, without
  `--previous-runs`, collects one record per run and audits them with step 12's own runs file;
  `step12/experiments/rc-step12-experiments.json` holds exactly `r375.audit` (§6.4);
- step 14's `a60.w24.nlp_selection` records n and requires n ≥ 1, not 0.3.0's 190 (§6.5);
- step 15 carries the journey with `scripts/release_gate.py --line <l> --rc C --carry-journey J`;
- step 16 is §6.6's four checks; step 17 is the line's `rc_items` (`release_rc.py items`);
- the steps run are the line's `gate_set.rc_steps`; nothing runs under `strace` (D2 deferred).

Every command runs from the checkout at C (the clean nlp worktree for step 14 and the `nlp`
items), its output to `<work>/logs/<label>.log`, and one line `<label> exit <code> :: <command>`
to `<work>/summary.txt`; the record writers judge those exit codes, logs and the files the
commands wrote. The records go under `--rc`, `evidence/<pkg>/<C>/artifacts/rc` (git-ignored), as
0.3.0's did; M02's judges name the records they read relative to the checkout, so `--rc` must lie
inside it.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import threading
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parent.parent
#: The steps with a local leg (RP §6.1); 1 and 3–5 are CI's (`release_rc.py step1`, `ci`).
LOCAL_STEPS = (2, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17)
THREADS = {"OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"}
SYS_PATH = "/usr/local/bin:/usr/bin:/bin"
#: Step 12's reactor variant (M02 v3, `src/openflowsheet/adapters/variants/`).
REACTOR_VARIANT = "pymrm-6089593-g2-nz800-s123-v1"
#: Step 12's archived inputs: 0.2.0's and 0.3.0's, WO-12a′'s v3 records at `bd446ab` (RP §6.3).
STEP12_INPUTS_AT = "bd446ab"
#: Step 11's cross-check pins, as `benchmarks/m01/external_crosscheck.py` registers them.
XCHECK_PINS = (
    "chemicals==1.5.2",
    "thermo==0.6.1",
    "CoolProp==8.0.0",
    "cantera==3.2.0",
    "pyyaml==6.0.2",
)
#: §6.4: the audit's line under G11's registered coverage (variant v3), with j free.
AUDIT_LINE = re.compile(
    r"^G11 experiments audit: 2 runs, 210 boundary points, 210 results, 210 attempts, "
    r"0 without a result, 32 direct points \(no records\); 6 items \+ schema: 0 problems; "
    r"context \(job_id\): (\d+) findings: PASS$"
)
VARIANT_FILE = "benchmarks/m02/variant-v3-provisional.json"
#: §6.9: a record over this size is committed gzip-compressed beside its path.
SIZE_LIMIT = 1_000_000
RECORDS_FORMAT = "m07a-rc-records-v1"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _t08_rc() -> Any:
    sys.path.insert(0, str(ROOT / "scripts"))
    import t08_rc  # noqa: PLC0415

    return t08_rc


def _finish(out: Path, step: str, checks: list[dict[str, Any]]) -> int:
    t08_rc = _t08_rc()
    provenance = {**t08_rc.provenance(), "machine_class": t08_rc.machine_class()}
    return int(t08_rc.finish(out, step, checks, provenance=provenance))


def _check(checks: list[dict[str, Any]], check_id: str, passed: bool, **value: Any) -> None:
    checks.append({"id": check_id, "result": "pass" if passed else "fail", **value})


# -- the runner's summary and logs ----------------------------------------------------------------


def exit_codes(summary: Path) -> dict[str, int]:
    """The last exit code of each label in the runner's summary."""
    codes: dict[str, int] = {}
    if summary.is_file():
        for line in summary.read_text(encoding="utf-8").splitlines():
            match = re.match(r"^(\S+) exit (-?\d+) :: ", line)
            if match:
                codes[match[1]] = int(match[2])
    return codes


def log_text(logs: Path, label: str) -> str:
    path = logs / f"{label}.log"
    return path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""


def last_line(text: str) -> str:
    lines = [line for line in text.strip().splitlines() if line.strip()]
    return lines[-1] if lines else ""


def junit_totals(path: Path) -> dict[str, int]:
    totals = {"tests": 0, "failures": 0, "errors": 0, "skipped": 0}
    for suite in ElementTree.parse(path).getroot().iter("testsuite"):
        for key in totals:
            totals[key] += int(suite.get(key, "0"))
    return totals


@dataclass(frozen=True)
class Inputs:
    """What a record writer reads: the checkout at C, the step's directory, the runner's codes
    and logs, C, the line and the journey."""

    out: Path
    codes: Mapping[str, int]
    logs: Path
    commit: str
    line: str = ""
    journey: str = ""

    def log(self, label: str) -> str:
        return log_text(self.logs, label)


def _tests(
    checks: list[dict[str, Any]], check_id: str, i: Inputs, label: str, junit: Path, command: str
) -> None:
    totals = junit_totals(junit) if junit.is_file() else None
    _check(
        checks,
        check_id,
        i.codes.get(label) == 0
        and totals is not None
        and totals["failures"] == totals["errors"] == 0,
        exit_code=i.codes.get(label),
        junit=totals,
        junit_sha256=sha256(junit) if junit.is_file() else None,
        command=command,
    )


def _exit(checks: list[dict[str, Any]], check_id: str, i: Inputs, label: str, **value: Any) -> None:
    _check(
        checks,
        check_id,
        i.codes.get(label) == 0,
        exit_code=i.codes.get(label),
        last_line=last_line(i.log(label)),
        **value,
    )


# -- step 11: W22's external records --------------------------------------------------------------


def _differences(a: Any, b: Any) -> list[str]:
    sys.path.insert(0, str(ROOT / "scripts"))
    import m01_evidence_manifest  # noqa: PLC0415

    return sorted(m01_evidence_manifest._differences(a, b, ""))


def step11_checks(
    i: Inputs, differences: Callable[[Any, Any], list[str]] = _differences
) -> list[dict[str, Any]]:
    """`a40.*`: the cross-check exits 0; the IDAES conformance re-run exits 0 and differs from the
    committed record only in its inputs' SHA-256 members (`m01_evidence_manifest`'s comparison)."""
    checks: list[dict[str, Any]] = []
    stdout = i.out / "external-crosscheck-check.stdout.txt"
    text = stdout.read_text(encoding="utf-8") if stdout.is_file() else ""
    record = ROOT / "benchmarks/m01/external-crosscheck.json"
    freeze = i.out / "venv-xcheck.freeze.txt"
    _check(
        checks,
        "a40.crosscheck_exit",
        i.codes.get("step11-xcheck") == 0,
        exit_code=i.codes.get("step11-xcheck"),
        last_line=last_line(text),
        record_sha256=sha256(record) if record.is_file() else None,
        freeze_sha256=sha256(freeze) if freeze.is_file() else None,
    )
    committed_path = ROOT / "benchmarks/m01/idaes-conformance.json"
    rerun_path = i.out / "idaes-conformance.json"
    ran = i.codes.get("step11-idaes") == 0 and rerun_path.is_file()
    _check(checks, "a40.idaes_exit", ran, exit_code=i.codes.get("step11-idaes"))
    differing = (
        differences(
            json.loads(committed_path.read_text(encoding="utf-8")),
            json.loads(rerun_path.read_text(encoding="utf-8")),
        )
        if ran
        else None
    )
    inputs_only = differing is not None and all(
        re.fullmatch(r"inputs\.[A-Za-z0-9_]+_sha256", member) for member in differing
    )
    idaes_freeze = i.out / "venv-idaes.freeze.txt"
    _check(
        checks,
        "a40.idaes_numbers_identical",
        inputs_only,
        differing_members=differing,
        committed_sha256=sha256(committed_path),
        rerun_sha256=sha256(rerun_path) if rerun_path.is_file() else None,
        freeze_sha256=sha256(idaes_freeze) if idaes_freeze.is_file() else None,
    )
    return checks


# -- step 12: W21's reactor evidence --------------------------------------------------------------


def _m02_judges(out: Path) -> dict[str, Callable[[], tuple[dict[str, Any], bool]]]:
    sys.path.insert(0, str(ROOT / "scripts"))
    import m02_evidence_manifest as m02  # noqa: PLC0415

    m02.M02 = out  # the records this step wrote, judged by M02's own functions
    return {"g10": m02.g10, "g11": m02.g11, "g12": m02.g12}


def step12_checks(
    i: Inputs, judges: Mapping[str, Callable[[], tuple[dict[str, Any], bool]]]
) -> list[dict[str, Any]]:
    """`a41.*`, as the alpha's and 0.3.0's: the reactor environment built from C's lock, G10–G12
    judged by `scripts/m02_evidence_manifest.py`'s own functions, one thread, M02's tests."""
    checks: list[dict[str, Any]] = []
    lock = ROOT / "src/openflowsheet/adapters/pymrm/reactor-env.lock"
    manifest_path = i.out / "env-manifest.json"
    manifest = json.loads(manifest_path.read_text("utf-8")) if manifest_path.is_file() else {}
    _check(
        checks,
        "a41.environment_from_c_alpha_lock",
        i.codes.get("reactor-build") == 0
        and i.codes.get("reactor-verify") == 0
        and manifest.get("lock_sha256") == sha256(lock),
        build_exit=i.codes.get("reactor-build"),
        verify_exit=i.codes.get("reactor-verify"),
        lock_sha256=sha256(lock),
        env_manifest={k: manifest.get(k) for k in sorted(manifest) if k != "packages"},
    )
    for gate, labels in (
        ("g10", ("step12-g10",)),
        ("g11", ("step12-g11",)),
        ("g12", ("step12-g12", "step12-g12-edges")),
    ):
        exits = {label: i.codes.get(label) for label in labels}
        try:
            value, ok = judges[gate]()
        except (OSError, KeyError, ValueError, TypeError) as error:
            value, ok = {"error": f"{type(error).__name__}: {error}"}, False
        _check(
            checks,
            f"a41.{gate}",
            all(code == 0 for code in exits.values()) and ok,
            exits=exits,
            judged_by=f"scripts/m02_evidence_manifest.py:{gate}",
            value=value,
        )
    g10_path = i.out / "g10-adapter-halves-v3.json"
    g10 = json.loads(g10_path.read_text("utf-8")) if g10_path.is_file() else {}
    environment = g10.get("environment", {})
    _check(
        checks,
        "a41.one_thread_environment_recorded",
        environment.get("threads") == "OMP/OPENBLAS/MKL_NUM_THREADS=1"
        and all(environment.get(key) for key in ("python", "platform", "packages", "cpu_model")),
        environment=environment,
    )
    junit = i.out / "m02-tests.junit.xml"
    totals = junit_totals(junit) if junit.is_file() else None
    _check(
        checks,
        "a41.m02_tests_with_reactor",
        i.codes.get("step12-m02-tests") == 0
        and totals is not None
        and totals["failures"] == totals["errors"] == 0,
        exit_code=i.codes.get("step12-m02-tests"),
        junit=totals,
        command="pytest -q -p no:cacheprovider -m 'pymrm or not pymrm' tests/test_m02_*.py",
    )
    return checks


Audit = Callable[[list[str]], tuple[int, str]]


def _audit(argv: list[str]) -> tuple[int, str]:
    done = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True, check=False)
    return done.returncode, done.stdout


def audit_argv(step12: Path) -> list[str]:
    """§6.4 item 3: the audit, given step 12's own runs file."""
    experiments = step12 / "experiments"
    return [
        sys.executable,
        "scripts/m07_g11_experiments_audit.py",
        "--variant-file",
        VARIANT_FILE,
        "--runs",
        str(step12 / "g11-coverage-v3.runs.json"),
        "--out",
        str(experiments / "g11-experiments-audit.json"),
        *(str(experiments / f"g11-experiments-run{k}.json") for k in (1, 2)),
    ]


def step12_experiments_checks(i: Inputs, audit: Audit = _audit) -> list[dict[str, Any]]:
    """§6.4 item 4: exactly `r375.audit`, `pass` iff the audit exits 0 and its line is the
    registered one exactly, j recorded and not judged."""
    checks: list[dict[str, Any]] = []
    code, stdout = audit(audit_argv(i.out))
    last = stdout.splitlines()[-1] if stdout.strip() else ""
    match = AUDIT_LINE.match(last)
    _check(
        checks,
        "r375.audit",
        code == 0 and match is not None,
        exit_code=code,
        last_line=last,
        job_id_findings=int(match.group(1)) if match else None,
        runs_file="step12/g11-coverage-v3.runs.json",
        keep_exit_code=i.codes.get("step12-g11"),
        collect_exit_code=i.codes.get("step12-g11-collect"),
        command="python scripts/m07_g11_experiments_audit.py --variant-file "
        f"{VARIANT_FILE} --runs <rc>/step12/g11-coverage-v3.runs.json "
        "--out <rc>/step12/experiments/g11-experiments-audit.json "
        "<rc>/step12/experiments/g11-experiments-run1.json "
        "<rc>/step12/experiments/g11-experiments-run2.json",
    )
    return checks


# -- steps 13–16 ----------------------------------------------------------------------------------


def step13_checks(i: Inputs) -> list[dict[str, Any]]:
    """W23: M04's committed records re-checked at C."""
    checks: list[dict[str, Any]] = []
    text = i.log("step13-generator")
    _check(
        checks,
        "a60.w23.generator_check",
        i.codes.get("step13-generator") == 0 and "claims passed" in text and "differs" not in text,
        exit_code=i.codes.get("step13-generator"),
        claims_line=next((x for x in text.splitlines() if "claims passed" in x), None),
        command="python docs/derivations/scripts/m04_reference.py --check",
    )
    _exit(
        checks,
        "a60.w23.schema_fixtures",
        i,
        "step13-fixtures",
        command="python scripts/m04_schema_fixtures.py",
    )
    _tests(
        checks,
        "a60.w23.tests",
        i,
        "step13-tests",
        i.out / "m04-tests.junit.xml",
        "pytest -q -rs -p no:cacheprovider tests/test_m04_*.py tests/test_evidence_manifests.py",
    )
    return checks


NODE_LINE = re.compile(r"^tests/\S+::")


def nlp_selection(
    selected: str, everything: str, selected_exit: int | None, modules: Sequence[str]
) -> tuple[bool, dict[str, Any]]:
    """§6.5 (R-907): `-m nlp` collects the same node ids over the `mark.nlp` modules as over
    `tests/`, n ≥ 1 of them with n recorded, and the run over the modules exits 0. The exit
    status of the collection over `tests/` is not judged."""
    ids_selected = {line.strip() for line in selected.splitlines() if NODE_LINE.match(line)}
    ids_all = {line.strip() for line in everything.splitlines() if NODE_LINE.match(line)}
    equal = ids_selected == ids_all
    value = {
        "modules": list(modules),
        "selected_count": len(ids_selected),
        "all_count": len(ids_all),
        "equal": equal,
        "selected_exit_code": selected_exit,
    }
    return equal and len(ids_selected) >= 1 and selected_exit == 0 and bool(modules), value


def step14_checks(i: Inputs) -> list[dict[str, Any]]:
    """W24: M03's nlp tier A35–A42, M05 G1–G10, G12, G13, in the audited nlp environment."""
    checks: list[dict[str, Any]] = []
    text = i.log("step14-nlp-check")
    junit = i.out / "nlp.junit.xml"
    _check(
        checks,
        "a60.w24.nlp_tier_and_inventory",
        i.codes.get("step14-nlp-check") == 0
        and "--- pytest -m nlp: exit 0" in text
        and "--- inventory --check: exit 0" in text
        and "--- inventory --check (trsp-exe): exit 0" in text,
        exit_code=i.codes.get("step14-nlp-check"),
        junit=junit_totals(junit) if junit.is_file() else None,
        command="scripts/m03_nlp_check.sh PREFIX CACHE -- -o junit_family=xunit1 "
        "--junitxml=... <the mark.nlp modules>",
    )
    _tests(
        checks,
        "a60.w24.m03_m05_all_tiers",
        i,
        "step14-tests",
        i.out / "m03-m05-tests.junit.xml",
        "nlp env: pytest -q -rs -p no:cacheprovider -m 'nlp or not nlp' tests/test_m05_*.py "
        "tests/test_m03_nlp_isolation.py tests/test_m03_nlp_greybox.py",
    )
    real = i.log("step14-m05-real-replay")
    _check(
        checks,
        "a60.w24.m05_g10_real_replay",
        i.codes.get("step14-m05-real-replay") == 0 and "REPLAY PASS REAL differences=0" in real,
        exit_code=i.codes.get("step14-m05-real-replay"),
        last_line=last_line(real),
        command="nlp env: python scripts/m05_wo9_real.py --replay",
    )
    _exit(
        checks,
        "a60.w24.m03_reference_check",
        i,
        "step14-m03-reference",
        command="python docs/derivations/scripts/m03_reference.py --check",
    )
    listed = i.out / "nlp-modules.txt"
    modules = listed.read_text(encoding="utf-8").split() if listed.is_file() else []
    passed, value = nlp_selection(
        i.log("step14-nlp-collect-selected"),
        i.log("step14-nlp-collect-all"),
        i.codes.get("step14-nlp-collect-selected"),
        modules,
    )
    _check(
        checks,
        "a60.w24.nlp_selection",
        passed,
        **value,
        command="nlp env: pytest --collect-only -q -p no:cacheprovider -m nlp <the modules>; "
        "the same over tests/ (its exit status not judged)",
    )
    return checks


def step15_checks(i: Inputs) -> list[dict[str, Any]]:
    """W25 (§4.5): the journey at J carried to C; `check` and `replay` at C."""
    checks: list[dict[str, Any]] = []
    line = last_line(i.log("step15-carry"))
    _check(
        checks,
        "a21.carry_journey",
        i.codes.get("step15-carry") == 0
        and line.startswith("RC step 15: ")
        and line.endswith(" carried"),
        exit_code=i.codes.get("step15-carry"),
        line=line,
        command=f"python scripts/release_gate.py --line {i.line} --rc {i.commit} "
        f"--carry-journey {i.journey[:8]}",
    )
    for name, label, command in (
        ("check", "step15-check", f"python scripts/m07_journey.py check {i.journey[:8]}"),
        (
            "replay",
            "step15-replay",
            f"nlp env, OMP_NUM_THREADS=1: python scripts/m07_journey.py replay {i.journey[:8]}",
        ),
    ):
        _exit(checks, f"a21.{name}", i, label, command=command)
    return checks


#: §6.6 (c): the 25 registered testcases (junit classname, name).
G15_NODES: tuple[tuple[str, str], ...] = (
    ("tests.test_m06_w27_scorer", "test_the_twenty_states_are_registered"),
    *(("tests.test_m06_w27_scorer", f"test_candidate_states[W27-S{n:02d}]") for n in range(11, 17)),
    *(
        ("tests.test_m06_w27_scorer", f"test_harness_states[W27-S{n:02d}]")
        for n in (*range(1, 11), *range(17, 21))
    ),
    ("tests.test_m06_w27_harness", "test_a23_run_record"),
    ("tests.test_m06_w27_harness", "test_a79b_an_unpinned_attempt_through_the_harness"),
    ("tests.test_m06_w27_coverage", "test_s11_the_v2_snapshot_refuses_this_build"),
    (
        "tests.test_m06_w27_coverage",
        "test_committed_coverage_json_is_g14_and_this_builds_classification",
    ),
)
#: §6.6 (d): the dry run's registered refusal (W27-R63), its last non-empty line exactly.
W27_V1_REFUSAL = (
    "benchmarks.m06.w27.snapshot.SnapshotUnsupportedError: registry_snapshot: unsupported(provider "
    "'iapws95-v1': no registered records and phases, W27-R63)"
)


def g15_registered_states(junit: Path) -> tuple[bool, dict[str, Any]]:
    """§6.6 (c): (a)'s junit has 0 skipped, and each of the 25 testcases appears exactly once
    with no `failure`, `error` or `skipped` child."""
    if not junit.is_file():
        return False, {"nodes": {}, "skipped_total": None, "reason": "no junit"}
    cases = list(ElementTree.parse(junit).getroot().iter("testcase"))
    skipped_total = sum(1 for case in cases if case.find("skipped") is not None)
    nodes: dict[str, str] = {}
    for classname, name in G15_NODES:
        found = [c for c in cases if c.get("classname") == classname and c.get("name") == name]
        key = f"{classname}::{name}"
        if len(found) != 1:
            nodes[key] = "missing" if not found else f"{len(found)} times"
            continue
        tags = {child.tag for child in found[0]}
        nodes[key] = next((t for t in ("failure", "error", "skipped") if t in tags), "passed")
        if nodes[key] == "failure":
            nodes[key] = "failed"
    ok = skipped_total == 0 and len(nodes) == len(G15_NODES) and set(nodes.values()) == {"passed"}
    return ok, {"nodes": nodes, "skipped_total": skipped_total}


def w27_v1_refusal(
    exit_code: int | None, log: str, summary_written: bool
) -> tuple[bool, dict[str, Any]]:
    """§6.6 (d): the dry run exits 1, its last non-empty output line is the registered W27-R63
    refusal exactly, and it writes no `summary.json`."""
    last = last_line(log)
    value = {"exit_code": exit_code, "last_line": last, "summary_written": summary_written}
    return exit_code == 1 and last == W27_V1_REFUSAL and not summary_written, value


def dry_run_dir(commit: str) -> str:
    return f"evidence/M06/W27/artifacts/dry-run/{commit[:7]}"


def step16_checks(i: Inputs) -> list[dict[str, Any]]:
    """W26 while W27 is not claimed (§6.6): exactly (a)–(d)."""
    checks: list[dict[str, Any]] = []
    junit = i.out / "m06-tests.junit.xml"
    _tests(
        checks,
        "a60.w26.m06_tests",
        i,
        "step16-tests",
        junit,
        "OPENFLOWSHEET_REQUIRE_BROWSER=1 pytest -q -rs -p no:cacheprovider "
        "--junitxml=<rc>/step16/m06-tests.junit.xml tests/test_m06_*.py",
    )
    _exit(
        checks,
        "a60.w26.web_unit_tests",
        i,
        "step16-node",
        command='node --test --test-reporter=spec "tests/web/*.test.mjs"',
    )
    passed, value = g15_registered_states(junit)
    _check(
        checks,
        "a60.w26.g15_registered_states",
        passed,
        **value,
        junit_sha256=sha256(junit) if junit.is_file() else None,
    )
    summary = ROOT / dry_run_dir(i.commit) / "summary.json"
    passed, value = w27_v1_refusal(
        i.codes.get("step16-dryrun"), i.log("step16-dryrun"), summary.exists()
    )
    _check(
        checks,
        "a60.w26.w27_v1_refusal",
        passed,
        **value,
        command=f"python -m benchmarks.m06.w27.dryrun --out {dry_run_dir(i.commit)}",
    )
    return checks


#: The record each writer produces: (directory under `--rc`, file, step name).
RECORDS: dict[str, tuple[str, str, str]] = {
    "step11": ("step11", "rc-step11.json", "external-records"),
    "step12": ("step12", "rc-step12.json", "reactor-evidence"),
    "step12-experiments": (
        "step12/experiments",
        "rc-step12-experiments.json",
        "g11-keep-and-audit",
    ),
    "step13": ("step13", "rc-step13.json", "w23-m04-records"),
    "step14": ("step14", "rc-step14.json", "w24-nlp-trf"),
    "step15": ("step15", "rc-step15.json", "w25-journey"),
    "step16": ("step16", "rc-step16.json", "w26-web-shell"),
}


def write_record(
    step: str, rc: Path, commit: str, summary: Path, logs: Path, line: str = "", journey: str = ""
) -> int:
    """Write step `step`'s `t08-rc-v1` record from the runner's summary and logs."""
    directory, name, step_name = RECORDS[step]
    out = rc / directory.split("/")[0]
    i = Inputs(out, exit_codes(summary), logs, commit, line, journey)
    if step == "step11":
        checks = step11_checks(i)
    elif step == "step12":
        checks = step12_checks(i, _m02_judges(out))
    elif step == "step12-experiments":
        checks = step12_experiments_checks(i)
    else:
        checks = {
            "step13": step13_checks,
            "step14": step14_checks,
            "step15": step15_checks,
            "step16": step16_checks,
        }[step](i)
    return _finish(rc / directory / name, step_name, checks)


# -- rc/records.json (§6.9) -----------------------------------------------------------------------


def collect_records(
    source: Path, target: Path, cited: Sequence[str], commit: str, rc_record: str, package: str
) -> dict[str, Any]:
    """Copy the cited records from `source` (the runner's `--rc`) into `target`
    (`evidence/<pkg>/<C>/rc/`) and return `records.json`: a record of 1 MB or less byte for byte,
    a larger one gzip-compressed beside its path (`<path>.gz`; its entry the uncompressed bytes'
    size and SHA-256). Raises ValueError on a path cited twice or a cited file that is absent."""
    if len(cited) != len(set(cited)):
        raise ValueError("a path is cited twice")
    missing = [path for path in cited if not (source / path).is_file()]
    if missing:
        raise ValueError(f"cited but not under {source}: {', '.join(missing)}")
    if target.exists():
        shutil.rmtree(target)
    files = []
    for path in cited:
        data = (source / path).read_bytes()
        out = target / path
        out.parent.mkdir(parents=True, exist_ok=True)
        committed = len(data) <= SIZE_LIMIT
        if committed:
            out.write_bytes(data)
        else:
            (target / f"{path}.gz").write_bytes(gzip.compress(data, compresslevel=9, mtime=0))
        files.append(
            {
                "path": path,
                "sha256": hashlib.sha256(data).hexdigest(),
                "bytes": len(data),
                "committed": committed,
            }
        )
    index = {
        "format": RECORDS_FORMAT,
        "commit": commit,
        "rc_record": rc_record,
        "description": f"Every record {rc_record}'s per-step table cites by sha256 (RP §6.9). A "
        "committed file is under this directory at its path; a file over 1 MB (committed false) "
        "is committed gzip-compressed beside its path (<path>.gz; sha256 and bytes are the "
        f"uncompressed record's) and stays under evidence/{package}/{commit}/artifacts/rc/ at the "
        "same path, git-ignored.",
        "size_limit_bytes": SIZE_LIMIT,
        "files": files,
    }
    (target / "records.json").write_text(json.dumps(index, indent=1) + "\n", encoding="utf-8")
    return index


def keep_certificates(step12: Path) -> list[str]:
    """0.3.0's `collect.sh`: step 12's kept G12 certificates into
    `step12/certificates/<bundle path>/solution-certificate.json` (the bundle's `artifacts/`
    segment left out, R-348). Runs after step 10, which audits them where G12 wrote them."""
    target = step12 / "certificates"
    if target.exists():
        shutil.rmtree(target)
    copied = []
    for top in ("g12-bundles", "g12-edges-bundles"):
        for kept in sorted((step12 / top).rglob("solution-certificate.json")):
            bundle = kept.parent.parent.relative_to(step12)
            out = target / bundle / "solution-certificate.json"
            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(kept, out)
            copied.append(out.relative_to(step12).as_posix())
    return copied


# -- the runner -----------------------------------------------------------------------------------


Execute = Callable[[list[str], Path, Mapping[str, str], Path], int]


def _execute(argv: list[str], log: Path, env: Mapping[str, str], cwd: Path) -> int:
    with log.open("wb") as stream:
        try:
            return subprocess.run(
                argv, cwd=cwd, env=dict(env), stdout=stream, stderr=subprocess.STDOUT
            ).returncode
        except OSError as error:
            stream.write(f"{type(error).__name__}: {error}\n".encode())
            return 127


@dataclass
class Plan:
    """The runner's inputs (`release_rc.py local`)."""

    line: str
    commit: str
    rc: Path
    work: Path
    steps: tuple[int, ...]
    base_python: str = "/usr/bin/python3"
    nlp_prefix: Path | None = None
    nlp_cache: Path | None = None
    journey: str | None = None
    w27_artifacts: Path | None = None
    ci_run: int | None = None


def missing_inputs(plan: Plan) -> list[str]:
    """The inputs a selected step needs and the plan lacks; the runner refuses to start on any."""
    missing = []
    needs_nlp = {14, 15} & set(plan.steps)
    if needs_nlp and (plan.nlp_prefix is None or plan.nlp_cache is None):
        missing.append(
            f"--nlp-prefix and --nlp-cache (step {', '.join(map(str, sorted(needs_nlp)))})"
        )
    if 15 in plan.steps and not plan.journey:
        missing.append("--journey (step 15)")
    if not plan.rc.resolve().is_relative_to(ROOT):
        missing.append(
            f"--rc inside the checkout {ROOT} (M02's judges name records relative to it)"
        )
    return missing


@dataclass
class Runner:
    plan: Plan
    execute: Execute = _execute
    lock: threading.Lock = field(default_factory=threading.Lock)

    def __post_init__(self) -> None:
        self.logs = self.plan.work / "logs"
        self.summary = self.plan.work / "summary.txt"
        self.logs.mkdir(parents=True, exist_ok=True)
        self.plan.rc.mkdir(parents=True, exist_ok=True)

    # environments ------------------------------------------------------------------------------

    @property
    def py(self) -> str:
        return str(self.plan.work / "rcvenv" / "bin" / "python")

    def env(self, **extra: str) -> dict[str, str]:
        """0.3.0's `env -u PYTHONPATH` with the one-thread variables exported."""
        base = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
        return {**base, **THREADS, **extra}

    def system_env(self) -> dict[str, str]:
        """For venv builds: `env -u PYTHONPATH PATH=<system>`."""
        return self.env(PATH=SYS_PATH)

    def nlp_env(self, src: Path) -> dict[str, str]:
        """`run_step14.sh`'s `env -i` for the audited nlp environment."""
        nlp, cache = self.plan.nlp_prefix, self.plan.nlp_cache
        return {
            **self.clean_env(),
            "OMP_NUM_THREADS": "1",
            "PYTHONNOUSERSITE": "1",
            "PYOMO_CONFIG_DIR": f"{nlp}/share/pyomo",
            "PYTHONPATH": f"{src}:{cache}/nlp-test-tools",
        }

    @staticmethod
    def clean_env() -> dict[str, str]:
        """`env -i HOME PATH LANG`."""
        return {
            "HOME": os.environ.get("HOME", ""),
            "PATH": os.environ.get("PATH", SYS_PATH),
            "LANG": os.environ.get("LANG", "C.UTF-8"),
        }

    # one command ---------------------------------------------------------------------------------

    def step(
        self,
        label: str,
        argv: Sequence[object],
        env: Mapping[str, str] | None = None,
        cwd: Path = ROOT,
    ) -> int:
        words = [str(a) for a in argv]
        code = self.execute(
            words, self.logs / f"{label}.log", self.env() if env is None else env, cwd
        )
        with self.lock, self.summary.open("a", encoding="utf-8") as stream:
            stream.write(f"{label} exit {code} :: {' '.join(words)}\n")
        return code

    def keep_logs(self, directory: Path, *labels: str) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        for label in labels:
            log = self.logs / f"{label}.log"
            if log.is_file():
                shutil.copy2(log, directory / f"{label}.log")

    def copy_log(self, label: str, target: Path) -> None:
        log = self.logs / f"{label}.log"
        if log.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(log, target)

    def tree_status(self, name: str, cwd: Path = ROOT) -> None:
        status = _output(["git", "status", "--porcelain"], cwd)
        (self.logs / f"{name}.txt").write_text(status, encoding="utf-8")

    def worktree(self, name: str) -> Path:
        """A clean detached worktree at C under the work directory (0.3.0's `nlp-wt`)."""
        tree = self.plan.work / name
        if not tree.is_dir():
            self.step(
                f"{name}-add",
                ["git", "-C", ROOT, "worktree", "add", "--detach", tree, self.plan.commit],
            )
        return tree

    def head_is_c(self, tree: Path) -> bool:
        head = _output(["git", "rev-parse", "HEAD"], tree).strip()
        return head == self.plan.commit

    def venv(self, name: str, *installs: Sequence[object]) -> Path:
        """A venv under the work directory, unless it exists; then each `pip install` in order."""
        directory = self.plan.work / name
        if not (directory / "bin" / "python").exists():
            self.step(
                f"{name}-venv", [self.plan.base_python, "-m", "venv", directory], self.system_env()
            )
            for k, install in enumerate(installs):
                self.step(
                    f"{name}-install{k}",
                    [directory / "bin" / "pip", "install", *install],
                    self.system_env(),
                )
        return directory / "bin" / "python"

    # the steps -----------------------------------------------------------------------------------

    def run(self) -> int:
        plan, rc = self.plan, self.plan.rc
        steps = set(plan.steps)
        self.tree_status("tree-at-start")
        self.venv("rcvenv", ["-r", ROOT / "requirements.lock"], ["--no-deps", "-e", ROOT])
        self.tree_status("tree-after-venv")
        if plan.w27_artifacts is not None and 16 in steps:
            self.link_w27_archive(plan.w27_artifacts)
        external = str(plan.work / "external")
        ensemble = None
        if 6 in steps:  # the longest; in the background, joined before step 10
            ensemble = threading.Thread(
                target=self.step,
                args=(
                    "step06-ensemble",
                    [self.py, "scripts/t08_rc.py", "ensemble", "--out", rc / "ensemble"],
                    self.env(OPENFLOWSHEET_EXTERNAL_ROOT=external),
                ),
            )
            ensemble.start()
        if 12 in steps:
            for verb in ("build", "verify"):
                self.step(
                    f"reactor-{verb}",
                    [
                        self.py,
                        "-m",
                        "openflowsheet.adapters.pymrm.env",
                        verb,
                        "--variant",
                        REACTOR_VARIANT,
                        "--root",
                        external,
                    ],
                    self.env(OPENFLOWSHEET_EXTERNAL_ROOT=external),
                )
        if 2 in steps:
            self.step(
                "step02-identity",
                [self.py, "scripts/t08_rc.py", "identity", "--out", rc / "identity"],
            )
        if 7 in steps:
            self.step(
                "step07-corpus",
                [self.py, "scripts/t08_rc.py", "corpus", "--out", rc / "corpus-ref-x86-64.json"],
            )
        if 8 in steps:
            self.step(
                "step08-surface",
                [self.py, "scripts/m07a_rc.py", "surface", "--out", rc / "surface"],
            )
        if 9 in steps:
            (rc / "a30").mkdir(parents=True, exist_ok=True)
            self.step(
                "step09-a30",
                [
                    self.py,
                    "scripts/p03_binary_inventory.py",
                    "--a30",
                    "--out",
                    rc / "a30",
                    "--summary-dir",
                    rc / "a30",
                ],
            )
            if (self.logs / "step09-a30.log").is_file():
                shutil.copy2(self.logs / "step09-a30.log", rc / "a30.log")
        if 11 in steps:
            self.step11()
        if 12 in steps:
            self.step12(external)
        if 13 in steps:
            self.step13()
        if 14 in steps:
            self.step14()
        if 15 in steps:
            self.step15()
        if ensemble is not None:
            ensemble.join()
        if 10 in steps:
            audited = [
                rc / d for d in ("identity", "ensemble", "surface", "step12") if (rc / d).is_dir()
            ]
            self.step(
                "step10-certificates",
                [
                    self.py,
                    "scripts/t08_rc.py",
                    "certificates",
                    "--out",
                    rc / "certificates-ref-x86-64.json",
                    *audited,
                ],
            )
        if 16 in steps:
            self.step16()
        if 17 in steps:
            self.step17()
        for step in RECORDS:
            if int(step[4:6]) in steps:
                self.record(step)
        if 12 in steps:
            keep_certificates(rc / "step12")
        self.tree_status("tree-at-end")
        with self.summary.open("a", encoding="utf-8") as stream:
            stream.write("EXIT release_rc local done\n")
        return 0 if records_passed(exit_codes(self.summary)) else 1

    def link_w27_archive(self, source: Path) -> None:
        """Step 16 (c) needs the pinned archive in the tree's git-ignored W27 artifacts."""
        target = ROOT / "evidence/M06/W27/artifacts"
        target.mkdir(parents=True, exist_ok=True)
        for name in ("OpenIDAES-450-demo.tar.gz", "extracted"):
            if not (target / name).exists():
                subprocess.run(["cp", "-al", str(source / name), str(target)], check=False)
        self.tree_status("tree-after-archive")

    def step11(self) -> None:
        out = self.plan.rc / "step11"
        out.mkdir(parents=True, exist_ok=True)
        xcheck = self.venv("venv-xcheck", list(XCHECK_PINS))
        freeze = _output([str(xcheck.parent / "pip"), "freeze"], ROOT, self.env())
        (out / "venv-xcheck.freeze.txt").write_text(freeze, encoding="utf-8")
        self.step(
            "step11-xcheck", [xcheck, "-I", "benchmarks/m01/external_crosscheck.py", "--check"]
        )
        self.copy_log("step11-xcheck", out / "external-crosscheck-check.stdout.txt")
        tree = self.worktree("idaes-wt")
        idaes = tree / ".venv-idaes"
        if not (idaes / "bin" / "python").exists():
            self.step(
                "idaes-env",
                [
                    "bash",
                    "scripts/build-reference-envs.sh",
                    "idaes",
                    self.logs / "idaes-env.build.log",
                ],
                self.system_env(),
                cwd=tree,
            )
        self.step(
            "step11-idaes",
            [
                idaes / "bin" / "python",
                "-I",
                "benchmarks/m01/idaes_conformance.py",
                "--out",
                out / "idaes-conformance.json",
            ],
            self.env(IDAES_DATA=str(idaes / "idaes-data")),
        )
        self.copy_log("step11-idaes", out / "idaes-conformance.stdout.txt")
        freeze = _output([str(idaes / "bin" / "pip"), "freeze"], ROOT, self.env())
        (out / "venv-idaes.freeze.txt").write_text(
            "".join(f"{line}\n" for line in sorted(freeze.splitlines())), encoding="utf-8"
        )

    def step12(self, external: str) -> None:
        out, work = self.plan.rc / "step12", self.plan.work
        out.mkdir(parents=True, exist_ok=True)
        inputs = work / "inputs"
        inputs.mkdir(parents=True, exist_ok=True)
        archived = {}
        for name in ("g10-adapter-halves-v3", "g11-coverage-v3"):
            at = f"{STEP12_INPUTS_AT}:benchmarks/m02/{name}.json"
            data = subprocess.run(["git", "show", at], cwd=ROOT, capture_output=True).stdout
            archived[name] = inputs / f"{name}-{STEP12_INPUTS_AT}.json"
            archived[name].write_bytes(data)
        host = _output(["uname", "-a"]) + _output(["lscpu"])
        (out / "host.txt").write_text(host, encoding="utf-8")
        manifests = sorted((work / "external").glob("pymrm-6089593-*/env-manifest.json"))
        if manifests:
            shutil.copy2(manifests[0], out / "env-manifest.json")
        shutil.copy2(ROOT / "benchmarks/m02/g11-coverage.json", out / "g11-coverage.json")
        (out / "archived-inputs.sha256").write_text(
            "".join(f"{sha256(p)}  {p}\n" for p in sorted(archived.values())), encoding="utf-8"
        )
        d78 = "docs/derivations/scripts/m07_g11_d78_extract.json"
        (out / "d78-extract.sha256").write_text(f"{sha256(ROOT / d78)}  {d78}\n", encoding="utf-8")
        env = self.env(OPENFLOWSHEET_EXTERNAL_ROOT=external)
        variant = ["--variant-file", VARIANT_FILE]
        self.step(
            "step12-g10",
            [
                self.py,
                "benchmarks/m02/g10_adapter_halves.py",
                *variant,
                "--compare",
                "benchmarks/m02/g10-adapter-halves.json",
                "--previous-v3",
                archived["g10-adapter-halves-v3"],
                "--out",
                out / "g10-adapter-halves-v3.json",
            ],
            env,
        )
        keep = work / "g11-keep"  # outside step12/: step 10 audits what 0.3.0's audited (C-10)
        shutil.rmtree(keep, ignore_errors=True)
        self.step(
            "step12-g11",
            [
                self.py,
                "scripts/m07_rc_keep.py",
                "g11",
                keep,
                *variant,
                "--compare",
                "benchmarks/m02/g11-coverage.json",
                "--d78",
                d78,
                "--previous",
                archived["g11-coverage-v3"],
                "--out",
                out / "g11-coverage-v3.json",
            ],
            env,
        )
        self.step(
            "step12-g11-collect",
            [
                self.py,
                "scripts/m07_rc_keep.py",
                "g11-collect",
                keep,
                out / "g11-coverage-v3.runs.json",
                out / "experiments",
            ],
            env,
        )
        for name in ("g12-bundles", "g12-edges-bundles"):
            shutil.rmtree(out / name, ignore_errors=True)
        self.step(
            "step12-g12",
            [
                self.py,
                "scripts/m07_rc_keep.py",
                "g12",
                out / "g12-bundles",
                "--out",
                out / "g12-real-loop-v3.json",
                "--compare",
                "benchmarks/m02/g12-real-loop.json",
            ],
            env,
        )
        self.step(
            "step12-g12-edges",
            [
                self.py,
                "scripts/m07_rc_keep.py",
                "g12",
                out / "g12-edges-bundles",
                "--t-in",
                "653.15",
                "--t-in",
                "693.15",
                "--out",
                out / "g12-real-loop-v3-edges.json",
            ],
            env,
        )
        self.step(
            "step12-m02-tests",
            [
                self.py,
                "-m",
                "pytest",
                "-q",
                "-p",
                "no:cacheprovider",
                "-m",
                "pymrm or not pymrm",
                f"--basetemp={work / 'tmp' / 'step12'}",
                f"--junitxml={out / 'm02-tests.junit.xml'}",
                *_glob("tests/test_m02_*.py"),
            ],
            env,
        )
        self.keep_logs(
            out,
            "step12-g10",
            "step12-g11",
            "step12-g11-collect",
            "step12-g12",
            "step12-g12-edges",
            "step12-m02-tests",
        )

    def step13(self) -> None:
        out, work = self.plan.rc / "step13", self.plan.work
        env = self.env(PYTHONPATH=str(ROOT / "src"))
        self.step(
            "step13-generator",
            [self.py, "docs/derivations/scripts/m04_reference.py", "--check"],
            env,
        )
        self.step("step13-fixtures", [self.py, "scripts/m04_schema_fixtures.py"], env)
        self.step(
            "step13-tests",
            [
                self.py,
                "-m",
                "pytest",
                "-q",
                "-rs",
                "-p",
                "no:cacheprovider",
                f"--basetemp={work / 'tmp' / 'step13'}",
                f"--junitxml={out / 'm04-tests.junit.xml'}",
                *_glob("tests/test_m04_*.py"),
                "tests/test_evidence_manifests.py",
            ],
            env,
        )
        self.keep_logs(out, "step13-generator", "step13-fixtures", "step13-tests")

    def step14(self) -> None:
        """`run_step14.sh`: a clean detached worktree at C, no install into it, `env -i`."""
        out, work = self.plan.rc / "step14", self.plan.work
        out.mkdir(parents=True, exist_ok=True)
        tree = self.worktree("nlp-wt")
        if not self.head_is_c(tree):
            with self.summary.open("a", encoding="utf-8") as stream:
                stream.write(f"step14-nlp-wt exit 2 :: {tree} is not at {self.plan.commit}\n")
            return
        nlp, cache = self.plan.nlp_prefix, self.plan.nlp_cache
        status = _output(["git", "status", "--porcelain", "--ignored"], tree)
        (self.logs / "nlp-wt-at-start.txt").write_text(status, encoding="utf-8")
        modules = _nlp_modules(tree)
        (out / "nlp-modules.txt").write_text("".join(f"{m}\n" for m in modules), encoding="utf-8")
        env = self.nlp_env(tree / "src")
        python = f"{nlp}/bin/python"
        self.step(
            "step14-nlp-check",
            [
                "bash",
                "scripts/m03_nlp_check.sh",
                nlp,
                cache,
                "--",
                "-o",
                "junit_family=xunit1",
                f"--junitxml={out / 'nlp.junit.xml'}",
                f"--basetemp={work / 'tmp' / 'step14-nlp'}",
                *modules,
            ],
            self.clean_env(),
            cwd=tree,
        )
        collect = [
            python,
            "-m",
            "pytest",
            "--collect-only",
            "-q",
            "-p",
            "no:cacheprovider",
            "-m",
            "nlp",
        ]
        self.step("step14-nlp-collect-selected", [*collect, *modules], env, cwd=tree)
        self.step("step14-nlp-collect-all", [*collect, "tests/"], env, cwd=tree)
        self.step(
            "step14-tests",
            [
                python,
                "-m",
                "pytest",
                "-q",
                "-rs",
                "-p",
                "no:cacheprovider",
                "-m",
                "nlp or not nlp",
                f"--junitxml={out / 'm03-m05-tests.junit.xml'}",
                f"--basetemp={work / 'tmp' / 'step14-tests'}",
                *_glob("tests/test_m05_*.py", tree),
                "tests/test_m03_nlp_isolation.py",
                "tests/test_m03_nlp_greybox.py",
            ],
            env,
            cwd=tree,
        )
        self.step(
            "step14-m05-real-replay", [python, "scripts/m05_wo9_real.py", "--replay"], env, cwd=tree
        )
        self.step(
            "step14-m03-reference",
            [self.py, "docs/derivations/scripts/m03_reference.py", "--check"],
            {**self.clean_env(), "PYTHONPATH": str(tree / "src")},
            cwd=tree,
        )
        self.keep_logs(
            out,
            "step14-nlp-check",
            "step14-nlp-collect-selected",
            "step14-nlp-collect-all",
            "step14-tests",
            "step14-m05-real-replay",
            "step14-m03-reference",
        )
        status = _output(["git", "status", "--porcelain", "--ignored"], tree)
        (self.logs / "nlp-wt-at-end.txt").write_text(status, encoding="utf-8")

    def step15(self) -> None:
        out, plan = self.plan.rc / "step15", self.plan
        journey = str(plan.journey)
        self.step(
            "step15-carry",
            [
                self.py,
                "scripts/release_gate.py",
                "--line",
                plan.line,
                "--rc",
                plan.commit,
                "--carry-journey",
                journey[:8],
            ],
            self.env(PYTHONPATH=str(ROOT / "src")),
        )
        base = {k: v for k, v in self.env().items() if k != "OPENFLOWSHEET_EXTERNAL_ROOT"}
        env = {
            **base,
            "OMP_NUM_THREADS": "1",
            "PYTHONNOUSERSITE": "1",
            "PYOMO_CONFIG_DIR": f"{plan.nlp_prefix}/share/pyomo",
            "PYTHONPATH": str(ROOT / "src"),
        }
        directory = f"benchmarks/m07/journey/{journey}"
        for verb in ("check", "replay"):
            self.step(
                f"step15-{verb}",
                [f"{plan.nlp_prefix}/bin/python", "scripts/m07_journey.py", verb, directory],
                env,
            )
        self.keep_logs(out, "step15-carry", "step15-check", "step15-replay")

    def step16(self) -> None:
        out, work = self.plan.rc / "step16", self.plan.work
        path = f"{ROOT / 'src'}{os.pathsep}{ROOT}"
        self.step(
            "step16-tests",
            [
                self.py,
                "-m",
                "pytest",
                "-q",
                "-rs",
                "-p",
                "no:cacheprovider",
                f"--junitxml={out / 'm06-tests.junit.xml'}",
                *_glob("tests/test_m06_*.py"),
                f"--basetemp={work / 'tmp' / 'step16'}",
            ],
            self.env(OPENFLOWSHEET_REQUIRE_BROWSER="1", PYTHONPATH=path),
        )
        self.step(
            "step16-node",
            ["node", "--test", "--test-reporter=spec", *_glob("tests/web/*.test.mjs")],
        )
        self.step(
            "step16-dryrun",
            [self.py, "-m", "benchmarks.m06.w27.dryrun", "--out", dry_run_dir(self.plan.commit)],
            self.env(PYTHONPATH=path),
        )
        self.keep_logs(out, "step16-tests", "step16-node", "step16-dryrun")

    def step17(self) -> None:
        """The line's `rc_items` (§6.7) with the environments built as RP names them."""
        plan, root = self.plan, ROOT
        coolprop = self.venv(
            "cpvenv",
            ["-r", root / "requirements.lock"],
            ["--no-deps", "--require-hashes", "-r", root / "requirements-coolprop.lock"],
            ["--no-deps", "-e", root],
        )
        lca = plan.work / "venv-lca"
        if not (lca / "bin" / "python").exists():
            self.step(
                "venv-lca",
                ["bash", "scripts/build-lca-env.sh", lca, plan.base_python],
                self.system_env(),
            )
        argv = [
            self.py,
            "scripts/release_rc.py",
            "items",
            "--line",
            plan.line,
            "--rc",
            plan.rc,
            "--commit",
            plan.commit,
            "--python",
            f"coolprop={coolprop}",
            "--python",
            f"lca={lca / 'bin' / 'python'}",
        ]
        if plan.nlp_prefix is not None and plan.nlp_cache is not None:
            argv += [
                "--nlp-prefix",
                plan.nlp_prefix,
                "--nlp-cache",
                plan.nlp_cache,
            ]
        if plan.ci_run is not None:
            argv += ["--ci-run", str(plan.ci_run)]
        self.step("step17-items", argv)

    def record(self, step: str) -> None:
        plan = self.plan
        self.step(
            f"record-{step}",
            [
                self.py,
                "scripts/release_rc.py",
                "record",
                step,
                "--rc",
                plan.rc,
                "--commit",
                plan.commit,
                "--line",
                plan.line,
                "--summary",
                self.summary,
                "--logs",
                self.logs,
                "--journey",
                plan.journey or "",
            ],
        )


def _output(argv: list[str], cwd: Path = ROOT, env: Mapping[str, str] | None = None) -> str:
    """A helper command's stdout; empty when it cannot be run (its step's record then fails)."""
    try:
        done = subprocess.run(
            argv,
            cwd=cwd,
            env=None if env is None else dict(env),
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return ""
    return done.stdout


def records_passed(codes: Mapping[str, int]) -> bool:
    """The runner's exit: every record written passed, and step 17's items did. A command's own
    exit is judged by its record (step 14's collection over `tests/` and step 16's dry run are
    expected to exit non-zero)."""
    judged = {k: v for k, v in codes.items() if k.startswith("record-") or k == "step17-items"}
    return bool(judged) and all(code == 0 for code in judged.values())


def _glob(pattern: str, root: Path = ROOT) -> list[str]:
    return sorted(path.relative_to(root).as_posix() for path in root.glob(pattern))


def _nlp_modules(root: Path) -> list[str]:
    """§6.5: the modules `grep -l 'mark.nlp' tests/test_*.py` lists at C."""
    return [
        path
        for path in _glob("tests/test_*.py", root)
        if "mark.nlp" in (root / path).read_text(encoding="utf-8", errors="replace")
    ]


# -- the release_rc dispatch's artifacts and logs (0.3.0's fetch_ci.sh) ----------------------------


def job_log_name(job: str) -> str:
    """`fetch_ci.sh`'s file name for a job's log: `name (leg)` → `name-leg`."""
    return re.sub(r" \((.*)\)$", r"-\1", job)


def fetch_ci(run_id: int, commit: str, ci: Path, gh: Callable[..., str]) -> int:
    """Download the `release_rc` dispatch `run_id` at C's artifacts into `ci`, and each job's
    log that ran into `ci/job-logs/<job>.log`. Refused (exit 2) when the run is not a dispatch
    at C."""
    view = json.loads(gh("run", "view", str(run_id), "--json", "jobs,headSha,event"))
    if view.get("headSha") != commit or view.get("event") != "workflow_dispatch":
        print(f"refused: run {run_id} is not a dispatch at {commit}", file=sys.stderr)
        return 2
    (ci / "job-logs").mkdir(parents=True, exist_ok=True)
    gh("run", "download", str(run_id), "--dir", str(ci))
    for job in view.get("jobs", []):
        if job.get("conclusion") == "skipped":
            continue
        log = gh("run", "view", str(run_id), "--job", str(job["databaseId"]), "--log")
        (ci / "job-logs" / f"{job_log_name(str(job['name']))}.log").write_text(
            log, encoding="utf-8"
        )
    return 0
