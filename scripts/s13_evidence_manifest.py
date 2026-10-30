"""Generate `evidence/S13/<C>/manifest.json` at V03's release candidate `C` (manifest id S13,
R-878), by measuring, not by transcribing. V03 release spec
(`docs/derivations/V03-release-spec.md`) §7 V03.A27: `tested`, listing V03.A01–A26 and A28–A31
with the commands run, and `S11.G8`, `S12.G8`, `S12.G10`; §6: one check per ADR. The pattern is
`scripts/m07_evidence_manifest.py` (0.2.0's RC manifest), whose T08 readers this script uses, with
S13a's selections for the D-gated assertions.

The manifest carries one check per assertion of §7 (`V03.Axx`), read from the document itself, so
that an assertion cannot be left out: an id without a rule here, or a rule without an id there,
stops the script. Each check is decided from the evidence that measured it, and its `value` names
that evidence; its result is the worst of its parts (`fail` over `unsupported` over `pass`):

1. **Tests, run here** at a commit whose distribution trees (ADR 0021 D2.4) equal `C`'s (the script
   refuses otherwise): each D-gated assertion's nodes in their own pytest process, with S13a's
   selection (`scripts/s13a_evidence_manifest.py` `ITEMS`); a part passes only if its process
   exits 0 with at least one test passed and none skipped. V03.A12 (c) is `scripts/s11_identity.py`
   (S11's G1), run with its own `TMPDIR` and no shared `--basetemp`.
2. **The RC records** of steps 2 and 6–17 under `evidence/S13/<C>/rc/`, each re-hashed against
   `rc/records.json` and read for its own verdict (T08's `_record`: `passed` and every check
   `pass`, `commit` = `C`, `tree_clean`). Step 17c is also read by M07a's measure
   `mr12_extras_v03` (V03 review F-V3), with `evidence/S13`.
3. **CI**, read only from the runs named on the command line (`--ci-run ID`): a run counts only if
   its head is `C`. Steps 1, 3, 4 and 5 are CI jobs (§4: the alpha spec §8.2 steps, M07 §8).
4. **Direct measurements** at the commit the script runs at (`judged_at`): the version files at K3
   and C (A09), `## v0.3.0`'s phrases (A18), the RC record by the gate's own `rc_record_problems`
   (A20), the THM-09/4 rows of `docs/t07-measurements.md` (A24, R-796), the required ADRs by the
   gate's own `adr_problems` (A25), the verdict document by its own parser (A26), and step 18's
   last line from `--step18-log` (A08's R part, A27).
5. **V03.A27** is this manifest: `pass` iff every other check passes, commands were run and step
   18's last line is YES.

`S11.G8` and `S12.G8` (the full gate and CI on both architectures) read `--gate-log` (the full
gate's log at a commit whose distribution trees equal C's) and the CI jobs; `S12.G10` is step
17a's record. The `ADR.<number>` checks transcribe the WO-4 table of `docs/V03_DECISIONS.md` (its
DECISION: WO-6's generator carries it into this manifest), each condition measured where it is
measurable here. `S13.S13a` cites S13a's manifest (WO-1…WO-4, merged before K3).

Status is `tested` iff every check is `pass`; otherwise `implemented`. `reviewed` is never set,
and both review fields stay `pending`.

Usage:
    PYTHONPATH=src:. .venv/bin/python scripts/s13_evidence_manifest.py --commit C \\
        --gate-log LOG --ci-run ID [--ci-run ID] [--step18-log LOG] [--tmp DIR] [--out PATH]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import m07a_evidence_manifest as m07a  # noqa: E402
import s13a_evidence_manifest as s13a  # noqa: E402
import t08_evidence_manifest as t08  # noqa: E402
import v0_1_gate  # noqa: E402
import v0_2_gate  # noqa: E402
import v0_3_gate  # noqa: E402

SPEC = ROOT / "docs" / "derivations" / "V03-release-spec.md"
RC_RECORD = ROOT / "docs" / "v03-rc-record.md"
CHANGELOG = ROOT / "CHANGELOG.md"
DECISIONS = ROOT / "docs" / "V03_DECISIONS.md"
MEASUREMENTS = ROOT / "docs" / "t07-measurements.md"
(GATE_SET,) = v0_3_gate.GATE_SETS
#: The cut commit K3 on `main` (§4, WO-5).
K3 = "295a2e652c6746b0621350112d6e43945d8b114a"
#: S13a's manifest (WO-1…WO-4, spec P3), which this manifest cites.
S13A_COMMIT = "0ce3748a7a473950a295e2668201fb96c44d0ec1"
#: §5.1: the five version-carrying files at K3 and C, each with the exact text it holds.
VERSION_FILES: tuple[tuple[str, str], ...] = (
    ("pyproject.toml", 'version = "0.3.0"\n'),
    ("src/openflowsheet/__init__.py", '__version__ = "0.3.0"\n'),
    (
        "tests/fixtures/schemas/application_results/project_summary/invalid/"
        "missing_capability_id.json",
        '"package_version": "0.3.0",',
    ),
    (
        "tests/fixtures/schemas/application_results/project_summary/valid/"
        "two_revisions_one_job.json",
        '"package_version": "0.3.0",',
    ),
    ("tests/test_m06_w27_coverage.py", 'live["package_version"] == "0.3.0"\n'),
)
ENVELOPE = (
    "benchmarks/t08/support_envelope.yaml",
    ("envelope_id: v0.3-envelope-1\n", "release: 0.3.0\n"),
)
#: R-796: the CI jobs whose THM-09/4 lines are copied into `docs/t07-measurements.md`.
THM09_JOBS = ("check (ubuntu-latest)", "check (ubuntu-24.04-arm)", "default-install")
STEP18_YES = "v0.3.0 tag may be proposed: YES"


# ----------------------------------------------------------------------------- the catalogue


@dataclass(frozen=True)
class Spec:
    """One check's evidence; its result is the worst of the parts."""

    id: str
    tests: bool = False
    records: tuple[str, ...] = ()
    jobs: tuple[str, ...] = ()
    measures: tuple[str, ...] = ()


_CHECK = ("check (ubuntu-latest)", "check (ubuntu-24.04-arm)")
_COOLPROP = ("rc-coolprop (ubuntu-latest)", "rc-coolprop (ubuntu-24.04-arm)")
#: §4 steps 1, 3, 4, 5 (the alpha spec §8.2 steps, read as in M07 §8) and the CI copies of 2, 6–10.
_CI_STEPS = (
    *_CHECK,
    "identity",
    "dist",
    "clean-install (ubuntu-latest)",
    "clean-install (ubuntu-24.04-arm)",
    "bundle-set",
    "bundle-replay (ubuntu-latest)",
    "bundle-replay (ubuntu-24.04-arm)",
    "rc-ensemble",
    "rc-steps (ubuntu-latest)",
    "rc-steps (ubuntu-24.04-arm)",
)
_STEP = {
    2: "identity/rc-identity.json",
    6: "ensemble/rc-ensemble-ref-x86-64.json",
    7: "corpus-ref-x86-64.json",
    8: "surface/rc-alpha-surface.json",
    9: "a30/t08-a30-x86_64.json",
    10: "certificates-ref-x86-64.json",
    11: "step11/rc-step11.json",
    12: "step12/rc-step12.json",
    13: "step13/rc-step13.json",
    14: "step14/rc-step14.json",
    15: "step15/rc-step15.json",
    16: "step16/rc-step16.json",
}
_STEP17 = {item: f"step17/rc-step17{item}.json" for item in "abcde"}

SPECS: tuple[Spec, ...] = (
    *(Spec(f"A{n:02d}", tests=True) for n in range(1, 8)),
    Spec("A08", tests=True, measures=("step18",)),
    Spec("A09", measures=("versions",)),
    *(Spec(f"A{n:02d}", tests=True) for n in range(10, 17)),
    Spec("A17", records=(_STEP17["e"],)),
    Spec("A18", measures=("changelog",)),
    Spec("A19", records=(_STEP17["e"],)),
    Spec(
        "A20",
        records=tuple(_STEP[step] for step in (2, *range(6, 15), 16)),
        jobs=_CI_STEPS,
        measures=("rc_record",),
    ),
    Spec("A21", records=(_STEP[15],)),
    Spec("A22", records=tuple(_STEP17.values()), measures=("mr12_extras_v03",)),
    Spec("A23", records=(_STEP[8],)),
    Spec("A24", jobs=(*_CHECK, *_COOLPROP), measures=("ci_runs", "thm09")),
    Spec("A25", measures=("adrs",)),
    Spec("A26", measures=("verdict_document",)),
    Spec("A27", measures=("self", "step18")),
    *(Spec(f"A{n:02d}", tests=True) for n in range(28, 32)),
)
#: The gates V03.A27 names beside the assertions (build decision, docs/V03_RC_DECISIONS.md).
GATES: tuple[tuple[str, str, Spec], ...] = (
    (
        "S11.G8",
        "S11 §6.2 G8 at C: the full gate, CI on x86-64 and aarch64, and the CoolProp step with "
        "0 skipped (V03 spec §6, ADRs 0050/0051: G8 again at C, steps 1 and 17b, V03.A24)",
        Spec("S11.G8", records=(_STEP17["b"],), jobs=(*_CHECK, *_COOLPROP), measures=("gate",)),
    ),
    (
        "S12.G8",
        "E01 §6.2 G8 at C: the full gate and CI on x86-64 and aarch64 (V03 spec §6, ADR 0052)",
        Spec("S12.G8", jobs=_CHECK, measures=("gate",)),
    ),
    (
        "S12.G10",
        "E01 §9.6 G10 at C: release-candidate data, a48_release_check() pass (RC step 17a)",
        Spec("S12.G10", records=(_STEP17["a"],)),
    ),
)


def catalogue() -> dict[str, tuple[str, str]]:
    """`V03.<id>` → (subject, gate), from §7 of the specification."""
    text = SPEC.read_text(encoding="utf-8")
    section = text[text.index("## 7. Assertions") : text.index("## 8. ")]
    found: dict[str, tuple[str, str]] = {}
    for line in section.splitlines():
        match = re.match(r"^\| V03\.(A\d\d) \|", line)
        if match and match[1] not in found:
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            found[match[1]] = (cells[1], cells[-1])
    return dict(sorted(found.items()))


# ----------------------------------------------------------------------------- inputs


@dataclass
class Inputs:
    """What the checks judge (the attributes T08's readers use). `main` measures it."""

    commit: str
    tests: dict[str, Part] = field(default_factory=dict)
    ci: list[dict[str, Any]] = field(default_factory=list)
    evidence: Path = ROOT / "evidence" / "S13"
    #: The commit the script ran at: the candidate, after the verdicts and the ledger.
    judged_at: str | None = None
    gate_log: Path | None = None
    step18_log: Path | None = None
    commands: int = 0

    @property
    def rc_dir(self) -> Path:
        return self.evidence / self.commit / "rc"


Part = tuple[str, dict[str, Any]]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _show(commit: str, path: str) -> str | None:
    if not t08._git_ok("cat-file", "-e", f"{commit}:{path}"):
        return None
    return t08._git("show", f"{commit}:{path}")


def _working_files(prefix: str) -> dict[str, str]:
    return {
        str(path.relative_to(ROOT)): path.read_text(encoding="utf-8")
        for path in sorted((ROOT / prefix).glob("*.md"))
    }


# ----------------------------------------------------------------------------- tests run here


def _pytest_part(
    check_id: str, selection: Sequence[str], artifacts: Path, tmp: Path
) -> tuple[Part, dict[str, Any], list[Path]]:
    """One assertion's nodes in their own pytest process (S13a's rule)."""
    junit = artifacts / f"{check_id}.junit.xml"
    log = artifacts / f"{check_id}.log"
    command = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        f"--basetemp={tmp / check_id}",
        f"--junitxml={junit}",
        *selection,
    ]
    environment = {**os.environ, "PYTHONPATH": f"{ROOT / 'src'}{os.pathsep}{ROOT}"}
    environment.pop("PYTEST_ADDOPTS", None)
    completed = subprocess.run(command, cwd=ROOT, env=environment, capture_output=True, check=False)
    log.write_bytes(completed.stdout + completed.stderr)
    last, counts = s13a.summary(completed.stdout.decode(errors="replace"))
    passed = (
        completed.returncode == 0
        and counts.get("passed", 0) > 0
        and not counts.get("skipped")
        and not counts.get("failed")
        and not counts.get("error", counts.get("errors"))
    )
    shown = shlex.join(command).replace(str(ROOT) + "/", "").replace(str(tmp), "TMP")
    record = {
        "cmd": shown.replace(sys.executable, "python"),
        "cwd": ".",
        "exit_code": completed.returncode,
        "stdout_sha256": hashlib.sha256(completed.stdout).hexdigest(),
    }
    part = ("pass" if passed else "fail"), {"selection": list(selection), "summary": last}
    return part, record, [log, junit]


def _identity_part(artifacts: Path, tmp: Path) -> tuple[Part, dict[str, Any], list[Path]]:
    """V03.A12 (c): `scripts/s11_identity.py` (S11's G1). Its shards run in parallel, so it gets a
    private `TMPDIR` and no `PYTEST_ADDOPTS` (no shared `--basetemp`)."""
    private = tmp / "s11-identity"
    private.mkdir(parents=True, exist_ok=True)
    environment = {**os.environ, "PYTHONPATH": f"{ROOT / 'src'}{os.pathsep}{ROOT}"}
    environment.pop("PYTEST_ADDOPTS", None)
    environment["TMPDIR"] = str(private)
    command = [sys.executable, "scripts/s11_identity.py"]
    completed = subprocess.run(command, cwd=ROOT, env=environment, capture_output=True, check=False)
    log = artifacts / "V03.A12c.log"
    log.write_bytes(completed.stdout + completed.stderr)
    last = (completed.stdout.decode(errors="replace").strip().splitlines() or [""])[-1]
    record = {
        "cmd": "TMPDIR=TMP python scripts/s11_identity.py",
        "cwd": ".",
        "exit_code": completed.returncode,
        "stdout_sha256": hashlib.sha256(completed.stdout).hexdigest(),
    }
    ok = completed.returncode == 0 and last.startswith("S11-IDENTITY PASS")
    return (("pass" if ok else "fail"), {"a12c": last[:300]}), record, [log]


def run_tests(
    artifacts: Path, tmp: Path
) -> tuple[dict[str, Part], list[dict[str, Any]], list[Path]]:
    """Every D-gated assertion's nodes, by S13a's selections, and A12 (c)."""
    gate_of = catalogue()
    parts: dict[str, Part] = {}
    commands: list[dict[str, Any]] = []
    files: list[Path] = []
    for assertion, _order, selection in s13a.ITEMS:
        gates = [part.strip() for part in gate_of[assertion][1].split(",")]
        if "D" not in gates:
            continue
        part, command, written = _pytest_part(f"V03.{assertion}", selection, artifacts, tmp)
        parts[assertion] = part
        commands.append(command)
        files.extend(written)
    (result, said), command, written = _identity_part(artifacts, tmp)
    a12_result, a12_value = parts["A12"]
    parts["A12"] = (t08._result([a12_result, result]), {**a12_value, **said})
    commands.append(command)
    files.extend(written)
    return parts, commands, files


# ----------------------------------------------------------------------------- measurements


def _m_versions(inputs: Inputs) -> Part:
    """V03.A09: at K3 and C, the five version files read `0.3.0` and the envelope is pinned."""
    value: dict[str, Any] = {}
    ok = True
    for name, commit in (("K3", K3), ("C", inputs.commit)):
        missing = []
        for path, wanted in VERSION_FILES:
            text = _show(commit, path)
            if text is None or wanted not in text or "0.3.0.dev0" in text:
                missing.append(path)
        envelope = _show(commit, ENVELOPE[0]) or ""
        lines = envelope.splitlines(keepends=True)
        if not all(line in lines for line in ENVELOPE[1]):
            missing.append(ENVELOPE[0])
        value[name] = {"commit": commit, "not_as_stated": missing}
        ok = ok and not missing
    return ("pass" if ok else "fail"), value


def _m_changelog(inputs: Inputs) -> Part:
    """V03.A18: §8's 17 phrases verbatim in `CHANGELOG.md` `## v0.3.0` (registration's list)."""
    phrases = json.loads(
        (ROOT / "benchmarks" / "v03" / "registration.json").read_text(encoding="utf-8")
    )["changelog_what_it_is_not"]
    import changelog_section  # noqa: PLC0415

    section = changelog_section.section(CHANGELOG.read_text(encoding="utf-8"), "v0.3.0")
    missing = [phrase for phrase in phrases if phrase not in section]
    value = {"phrases": len(phrases), "missing": missing, "judged_at": inputs.judged_at}
    return ("pass" if len(phrases) == 17 and not missing else "fail"), value


def _m_rc_record(inputs: Inputs) -> Part:
    """V03.A20: the RC record has a passed row for each of steps 1–17, read by the gate's own
    `rc_record_problems`."""
    text = RC_RECORD.read_text(encoding="utf-8") if RC_RECORD.is_file() else None
    found = v0_2_gate.rc_record_problems(text, inputs.commit, GATE_SET)
    value = {"record": t08._shown(RC_RECORD), "problems": found}
    if text is not None:
        value["sha256"] = _sha256(RC_RECORD)
    return ("pass" if not found else "fail"), value


def _m_mr12_extras_v03(inputs: Inputs) -> Part:
    """V03.A22 (17c): M07a's `mr12_extras_v03` at C over step 17c's committed record (F-V3)."""
    reader = m07a.Inputs(inputs.commit, t08.TestRun({}, 0), evidence=inputs.evidence)
    return m07a.MEASURES["mr12_extras_v03"](reader)


def _m_ci_runs(inputs: Inputs) -> Part:
    """V03.A24: every CI run named at C concluded `success`."""
    runs = t08._runs_at_c(inputs)  # type: ignore[arg-type]
    if not runs:
        return "unsupported", {"state": "pending", "reason": "no CI run at C was given"}
    value = {
        "ci_runs": {str(run.get("databaseId")): run.get("conclusion") for run in runs},
        "events": sorted({str(run.get("event")) for run in runs}),
    }
    ok = all(run.get("conclusion") == "success" for run in runs)
    return ("pass" if ok else "fail"), value


def _m_thm09(inputs: Inputs) -> Part:
    """V03.A24 (R-796): the THM-09/4 lines of the CI jobs at C copied into
    `docs/t07-measurements.md` (rows whose Commit cell names C)."""
    short = inputs.commit[:8]
    rows = [
        [cell.strip() for cell in line.strip().strip("|").split("|")]
        for line in MEASUREMENTS.read_text(encoding="utf-8").splitlines()
        if line.startswith("| ") and f"`{short}" in line
    ]
    found = {
        job: [row[0] for row in rows if len(row) > 2 and row[1] == f"`{job}`"] for job in THM09_JOBS
    }
    value = {"file": t08._shown(MEASUREMENTS), "rows_at_c": found}
    if not all(found.values()):
        value["state"] = "pending"
        return "unsupported", value
    return "pass", value


def _m_adrs(inputs: Inputs) -> Part:
    """V03.A25: gate item 12 at the candidate (the gate's own `adr_problems` over `docs/adr/`):
    the 25 required ADRs Accepted; 0043 Proposed and not required."""
    files = _working_files("docs/adr")
    found = v0_2_gate.adr_problems(files, GATE_SET)
    (adr_0043,) = [path for path in files if path.startswith("docs/adr/0043-")]
    line = v0_2_gate.status_line(files[adr_0043]) or ""
    proposed = "Proposed" in line and "0043" not in GATE_SET.required_adrs
    value = {
        "required": len(GATE_SET.required_adrs),
        "problems": found,
        "adr_0043_status": line,
        "judged_at": inputs.judged_at,
    }
    if found and not (ROOT / GATE_SET.verdict_document).is_file():
        # Before WO-7 the routes "after V03.A24" and "at WO-8" (§6) cannot have run yet.
        value["state"] = "pending"
        return "unsupported", value
    return ("pass" if not found and proposed else "fail"), value


def _m_verdict_document(inputs: Inputs) -> Part:
    """V03.A26: 17 rows in claimed order, every clause parsing under v0.3's grammar (the gate's
    parser raises on any departure)."""
    path = ROOT / GATE_SET.verdict_document
    if not path.is_file():
        return "unsupported", {
            "state": "pending",
            "reason": f"{GATE_SET.verdict_document} does not exist (WO-7, after steps 1–17)",
        }
    document = v0_2_gate.verdict_document(path.read_text(encoding="utf-8"), GATE_SET, inputs.commit)
    rows = {gate: row.verdict for gate, row in document.rows.items()}
    value = {
        "rows": len(rows),
        "verdicts": dict(sorted(Counter(rows.values()).items())),
        "judged": document.judged.isoformat() if document.judged else None,
        "judged_at": inputs.judged_at,
    }
    ok = len(rows) == 17 and tuple(rows) == GATE_SET.claimed
    return ("pass" if ok else "fail"), value


def _m_step18(inputs: Inputs) -> Part:
    """V03.A08 (R part) and A27: step 18's output (`v0_3_gate.py --rc C`), its last line YES."""
    if inputs.step18_log is None:
        return "unsupported", {
            "state": "pending",
            "reason": "step 18 runs after the ledger (WO-8); no --step18-log was given",
        }
    text = inputs.step18_log.read_text(encoding="utf-8")
    last = (text.strip().splitlines() or [""])[-1]
    value = {"log_sha256": _sha256(inputs.step18_log), "last_line": last}
    return ("pass" if last == STEP18_YES else "fail"), value


def _m_gate(inputs: Inputs) -> Part:
    """The full gate (`scripts/gate.sh`), read from its log; the log's commit must have C's
    distribution trees."""
    if inputs.gate_log is None:
        return "unsupported", {"state": "pending", "reason": "no --gate-log was given"}
    text = inputs.gate_log.read_text(encoding="utf-8", errors="replace")
    last, counts = s13a.summary(text)
    ok = "=== check.sh: PASSED ===" in text and counts.get("passed", 0) > 0
    ok = ok and not counts.get("failed")
    value = {
        "log": inputs.gate_log.name,
        "log_sha256": _sha256(inputs.gate_log),
        "summary": last,
        "check_sh_passed": "=== check.sh: PASSED ===" in text,
    }
    return ("pass" if ok else "fail"), value


MEASURES: dict[str, Callable[[Inputs], Part]] = {
    "versions": _m_versions,
    "changelog": _m_changelog,
    "rc_record": _m_rc_record,
    "mr12_extras_v03": _m_mr12_extras_v03,
    "ci_runs": _m_ci_runs,
    "thm09": _m_thm09,
    "adrs": _m_adrs,
    "verdict_document": _m_verdict_document,
    "step18": _m_step18,
    "gate": _m_gate,
}


# ----------------------------------------------------------------------------- the checks


def decide(spec: Spec, check_id: str, description: str, inputs: Inputs) -> dict[str, Any]:
    parts: list[str] = []
    value: dict[str, Any] = {}
    sources: list[tuple[str, Callable[[], Part]]] = []
    if spec.tests:
        sources.append(
            ("tests", lambda: inputs.tests.get(spec.id) or ("fail", {"error": "not run"}))
        )
    if spec.records:
        sources.append(("records", lambda: t08._records(spec.records, inputs)))  # type: ignore[arg-type]
    if spec.jobs:
        sources.append(("ci", lambda: t08._jobs(spec.jobs, inputs)))  # type: ignore[arg-type]
    for measure in spec.measures:
        if measure != "self":
            sources.append((measure, lambda measure=measure: MEASURES[measure](inputs)))  # type: ignore[misc]
    for name, read in sources:
        try:
            result, said = read()
        except Exception as error:  # noqa: BLE001 - evidence that could not be read did not pass
            result, said = "fail", {"error": f"{type(error).__name__}: {error}"}
        parts.append(result)
        value[name] = said
    return {
        "id": check_id,
        "description": _braced(description),
        "result": t08._result(parts),
        "value": value,
    }


def _wo4_rows() -> dict[str, tuple[str, str, str]]:
    """ADR number → (condition, checked against, result) from WO-4's table (spec §6)."""
    text = DECISIONS.read_text(encoding="utf-8")
    section = text[text.index("## WO-4: ADR checks and flips") :]
    section = section[: section.find("\n## ", 1) if "\n## " in section[1:] else len(section)]
    rows: dict[str, tuple[str, str, str]] = {}
    for line in section.splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if line.startswith("| 00") and len(cells) == 4:
            for number in re.findall(r"\d{4}", cells[0]):
                rows[number] = (cells[1], cells[2], cells[3])
    return rows


def adr_checks(inputs: Inputs, a24: str) -> list[dict[str, Any]]:
    """Spec §6: one check per ADR, transcribed from WO-4's table, each condition measured where
    it is measurable here (the status line at the candidate; V03.A24's check)."""
    files = _working_files("docs/adr")
    entries = []
    for number, (condition, checked, said) in _wo4_rows().items():
        paths = [path for path in files if path.startswith(f"docs/adr/{number}-")]
        line = (v0_2_gate.status_line(files[paths[0]]) or "") if len(paths) == 1 else ""
        accepted = line.replace("*", "").strip().startswith("Status: Accepted")
        value: dict[str, Any] = {
            "wo4_checked_against": checked,
            "wo4_result": said,
            "status_line": line,
        }
        if said.startswith("met"):
            result = "pass" if accepted else "fail"
        elif number in ("0050", "0051", "0052"):
            # Accepted after V03.A24 holds at C: the condition is A24's check.
            value["v03_a24"] = a24
            result = {"pass": "pass", "fail": "fail"}.get(a24, "unsupported")
        elif number == "0043":
            result = (
                "pass" if "Proposed" in line and number not in GATE_SET.required_adrs else "fail"
            )
        else:  # 0053, 0054: Accepted at WO-8, with S13's manifest tested
            result = "pass" if accepted else "unsupported"
            if not accepted:
                value["state"] = "pending"
        entries.append(
            {
                "id": f"ADR.{number}",
                "description": _braced(f"ADR {number} (V03 spec §6): {condition}"),
                "result": result,
                "value": value,
            }
        )
    return entries


def s13a_check() -> dict[str, Any]:
    path = ROOT / "evidence" / "S13a" / S13A_COMMIT / "manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    ancestor = t08._git_ok("merge-base", "--is-ancestor", S13A_COMMIT, "HEAD")
    ok = manifest.get("status") == "tested" and ancestor
    return {
        "id": "S13.S13a",
        "description": "S13a's manifest (WO-1…WO-4, V03.A01–A08, A10–A16, A18, A28–A31 before "
        "K3) is tested and its commit an ancestor of this one",
        "result": "pass" if ok else "fail",
        "value": {
            "manifest": t08._shown(path),
            "sha256": _sha256(path),
            "status": manifest.get("status"),
            "ancestor": ancestor,
        },
    }


def _self(entry: dict[str, Any], others: Sequence[Mapping[str, Any]], inputs: Inputs) -> None:
    """V03.A27: this manifest is `tested` iff every other check passes, with commands run, and
    step 18's last line is YES."""
    failing = [other["id"] for other in others if other["result"] != "pass"]
    entry["value"]["self"] = {
        "other_checks": len(others),
        "not_pass": failing,
        "commands": inputs.commands,
    }
    step18 = entry["value"].get("step18", {})
    if step18.get("state") == "pending":  # before WO-8: judged once step 18 has run
        entry["result"] = "unsupported"
        return
    ok = not failing and inputs.commands > 0 and step18.get("last_line") == STEP18_YES
    entry["result"] = "pass" if ok else "fail"


def checks(inputs: Inputs) -> list[dict[str, Any]]:
    listed = catalogue()
    specs = {spec.id: spec for spec in SPECS}
    if set(listed) != set(specs) or len(specs) != len(SPECS):
        raise SystemExit(
            "the catalogue and the checks differ: catalogue only "
            f"{sorted(set(listed) - set(specs))}, checks only {sorted(set(specs) - set(listed))}"
        )
    d_gated = {i for i, (_, gate) in listed.items() if "D" in [g.strip() for g in gate.split(",")]}
    selected = {assertion for assertion, _, selection in s13a.ITEMS if selection}
    if not d_gated == {spec.id for spec in SPECS if spec.tests} <= selected:
        raise SystemExit("the D-gated assertions, the tested checks and S13a's selections differ")
    entries = [
        decide(specs[i], f"V03.{i}", f"V03.{i} (§7 gate {gate}): {subject}", inputs)
        for i, (subject, gate) in listed.items()
    ]
    entries += [decide(spec, check_id, text, inputs) for check_id, text, spec in GATES]
    (a24,) = [entry["result"] for entry in entries if entry["id"] == "V03.A24"]
    entries += adr_checks(inputs, a24)
    entries.append(s13a_check())
    (own,) = [entry for entry in entries if entry["id"] == "V03.A27"]
    _self(own, [entry for entry in entries if entry is not own], inputs)
    return entries


def status(entries: Sequence[Mapping[str, Any]]) -> str:
    """`tested` iff every check passes; never `reviewed`."""
    return "tested" if entries and all(e["result"] == "pass" for e in entries) else "implemented"


def limitations(entries: Sequence[Mapping[str, Any]]) -> list[str]:
    found = [
        "Evidence class: numerical and software verification at V03's release candidate C (tests "
        "run here at a commit whose distribution trees equal C's; the RC records of steps 2 and "
        "6-17 on ref-x86-64; CI on x86-64 and aarch64). Self-generated records are regression "
        "evidence, not empirical validation.",
        "requirements is empty: V03's claims (X31 and the carried rows) are judged by the verdict "
        "document at C (spec §3, A26), and the frozen schema admits only D/A requirement ids.",
        "The D-gated assertions (A01-A08, A10-A16, A28-A31) are judged by their test nodes run "
        "here with S13a's selections; S13a's own manifest, at a commit before K3, is cited "
        "(S13.S13a), not re-used as evidence for C.",
        "V03.A24's ratio classes (S07 A31, S11 thermal check) are read through the CI jobs that "
        "assert them; the ratios themselves are recorded in docs/v03-rc-record.md, not here.",
        "S11.G8 and S12.G8 read the full gate from --gate-log, run at a commit whose distribution "
        "trees equal C's; the log's commit is named in the build log.",
        "The design lane's verdicts are not judged here; A25, A26, A27 and ADRs 0053/0054 are "
        "judged at the candidate after the verdicts and the ledger (WO-7, WO-8).",
    ]
    for entry in entries:
        if entry["result"] != "pass":
            states = [
                str(part["state"])
                for part in entry["value"].values()
                if isinstance(part, dict) and part.get("state")
            ]
            found.append(
                f"{entry['id']} is {entry['result']}"
                + (f" ({', '.join(states)})" if states else "")
                + ": see its value."
            )
    return found


def _braced(text: str) -> str:
    """A `<K>`-style operand as `{K}`, as `decide` writes a description."""
    return re.sub(r"<([^<>]*)>", r"{\1}", text)


def _rc_commands(inputs: Inputs) -> list[dict[str, Any]]:
    """The commands RC steps 2 and 6–17 ran at C, as their records state them."""
    found = []
    for label, path in [
        *((str(s), p) for s, p in _STEP.items()),
        *(("17" + i, p) for i, p in _STEP17.items()),
    ]:
        file = inputs.rc_dir / path
        if not file.is_file():
            continue
        record = json.loads(file.read_text(encoding="utf-8"))
        machine = (record.get("provenance") or {}).get("machine_class")
        for check in record.get("checks", []):
            if check.get("command"):
                found.append(
                    {
                        "cmd": f"{_braced(check['command'])} (RC step {label} at C, {machine}; "
                        f"{check['id']}: {check['result']})",
                        "cwd": ".",
                        "exit_code": int(check.get("exit_code", 0)),
                    }
                )
    return found


def _artifact_rows(inputs: Inputs, files: Sequence[Path]) -> list[dict[str, str]]:
    rows = [
        (RC_RECORD, "the RC record at C (§4)"),
        (inputs.rc_dir / "records.json", "the RC records: sha256, size and how each is kept"),
        (ROOT / "release" / "rc-trees" / f"{inputs.commit}.json", "the tree record of C (R-151)"),
    ]
    found = [
        {"path": t08._shown(path), "sha256": _sha256(path), "description": description}
        for path, description in rows
        if path.is_file()
    ]
    found += [
        {
            "path": t08._shown(path),
            "sha256": _sha256(path),
            "description": "tests run here (not committed)",
        }
        for path in files
        if path.is_file()
    ]
    return found


def build(
    inputs: Inputs, commands: Sequence[Mapping[str, Any]] = (), files: Sequence[Path] = ()
) -> dict[str, Any]:
    inputs.commands = len(commands)
    entries = checks(inputs)
    index = inputs.rc_dir / "records.json"
    return {
        "work_package": "S13",
        "commit": inputs.commit,
        "requirements": [],
        "status": status(entries),
        "inputs": {
            "case_id": "V03's acceptance at C: one check per assertion of "
            f"docs/derivations/V03-release-spec.md §7 ({_sha256(SPEC)}), S11.G8, S12.G8, S12.G10 "
            "and one per ADR of §6",
            "case_hash": _sha256(index) if index.is_file() else _sha256(SPEC),
            "environment_lock_hash": _sha256(ROOT / "requirements.lock"),
        },
        "commands": [dict(command) for command in commands],
        "checks": entries,
        "artifacts": _artifact_rows(inputs, files),
        "limitations": limitations(entries),
        "review": {"numerical": "pending", "process_model": "pending"},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    parser.add_argument("--commit", required=True, help="the release candidate C")
    parser.add_argument("--gate-log", type=Path, default=None, help="scripts/gate.sh's log")
    parser.add_argument("--ci-run", action="append", default=[], help="a CI run id (repeatable)")
    parser.add_argument("--step18-log", type=Path, default=None, help="step 18's output")
    parser.add_argument("--tmp", type=Path, default=None, help="private pytest temp root")
    parser.add_argument("--out", type=Path, default=None)
    arguments = parser.parse_args()

    commit = t08._git("rev-parse", f"{arguments.commit}^{{commit}}").strip()
    differing = v0_1_gate.tree_differences(commit, "HEAD")
    if differing:
        raise SystemExit(f"HEAD's distribution trees differ from C's (D2.4): {differing}")
    dirty = [ln for ln in t08._git("status", "--porcelain").splitlines() if "evidence/" not in ln]
    if dirty:
        raise SystemExit(f"the tree is not clean: {dirty[:5]}")
    destination = arguments.out or (ROOT / "evidence" / "S13" / commit / "manifest.json")
    artifacts = ROOT / "evidence" / "S13" / commit / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    tmp = arguments.tmp or (artifacts / "tmp")
    tmp.mkdir(parents=True, exist_ok=True)

    head = t08._git("rev-parse", "HEAD").strip()
    commands: list[dict[str, Any]] = []
    ci: list[dict[str, Any]] = []
    for run_id in arguments.ci_run:
        run, command = t08.fetch_ci(run_id, artifacts)
        ci.append(run)
        commands.append(command)
    tests, test_commands, files = run_tests(artifacts, tmp)
    commands.extend(test_commands)
    inputs = Inputs(
        commit,
        tests,
        ci,
        judged_at=head,
        gate_log=arguments.gate_log,
        step18_log=arguments.step18_log,
    )
    commands.extend(_rc_commands(inputs))
    commands.append(
        {
            "cmd": "PYTHONPATH=src:. .venv/bin/python scripts/s13_evidence_manifest.py "
            f"--commit {commit}"
            + (f" --gate-log {arguments.gate_log.name}" if arguments.gate_log else "")
            + "".join(f" --ci-run {run_id}" for run_id in arguments.ci_run)
            + (f" --step18-log {arguments.step18_log.name}" if arguments.step18_log else "")
            + f" (run at {head})",
            "cwd": ".",
            "exit_code": 0,
        }
    )

    manifest = build(inputs, commands, files)
    found = t08.problems(manifest)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(manifest, indent=1, ensure_ascii=False, allow_nan=False) + "\n", "utf-8"
    )
    counts = Counter(entry["result"] for entry in manifest["checks"])
    print(
        f"S13 {manifest['status']} {commit[:8]}: {len(manifest['checks'])} checks, "
        f"{counts['pass']} pass, {counts['fail']} fail, {counts['unsupported']} unsupported; "
        "not pass: "
        + (" ".join(e["id"] for e in manifest["checks"] if e["result"] != "pass") or "none")
    )
    for problem in found:
        print(f"invalid: {problem}")
    return 1 if found or manifest["status"] != "tested" else 0


if __name__ == "__main__":
    raise SystemExit(main())
