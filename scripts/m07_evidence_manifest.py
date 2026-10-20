"""Generate `evidence/M07/<C>/manifest.json` at M07's release candidate `C` (C′ since Amendment 6
§24.6), by measuring, not by transcribing. M07 spec §11 M07.A43: `tested`, listing A00–A62 with
the commands run; the pattern is `scripts/m07a_evidence_manifest.py`, whose T08 readers this
script uses.

The manifest carries one check per assertion of the specification's §11 catalogue (`M07.Axx`),
read from the document itself, so that an assertion cannot be left out: an id without a check here,
or a check without an id there, stops the script. Each check is decided from the evidence that
measured it, and its `value` names that evidence:

1. **Tests, run here** (`pytest --junitxml`) at the checked-out commit, whose distribution trees
   (ADR 0021 D2.4) must equal `C`'s; the script refuses to run otherwise. A failed node fails its
   check, a skipped one leaves it `unsupported`, a selector that ran no node fails it.
2. **The RC records** of steps 13–17 (§8): the committed copies under `evidence/M07/<C>/rc/`, each
   re-hashed against `rc/records.json` and read for its own verdict (T08's `_record`: `passed` and
   every check `pass`, `commit` = `C`, `tree_clean`), and step 1's CI x86-64 `check` log (step 16's
   browser test).
3. **CI**, read only from the runs named on the command line (`--ci-run ID`): a run counts only if
   its head is `C`.
4. **Direct measurements**: W27's order and records at C_W (M07.A50, A51) over the committed
   campaign record tree, by the harness's own `order_check`, `a23` and `spend`; at the candidate,
   the eleven phrases of `## v0.2.0` (A40), the verdict document read by `scripts/v0_2_gate.py`'s
   own parser (A41) and ADR 0042's two tables read by its own `policy` (A42).
5. **M07.A43** is this manifest: `pass` iff every other check passes and commands were run.

A40–A42 are R-class and judged at the candidate (§8 [A6], R-476: after the verdicts and the
ledger), as the alpha's A52 and A64 were (alpha spec §19.4); each such value carries `judged_at`,
the commit the script ran at.

Status is `tested` iff every check M07.A00–A62 is `pass`; otherwise `implemented`. `reviewed` is
never set, and both review fields stay `pending`.

Usage:
    PYTHONPATH=src:. .venv/bin/python scripts/m07_evidence_manifest.py --commit C \\
        --ci-run 39291243747 [--out PATH]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import t08_evidence_manifest as t08  # noqa: E402
import v0_1_gate  # noqa: E402
import v0_2_gate  # noqa: E402

SPEC = ROOT / "docs" / "derivations" / "M07-spec.md"
RC_RECORD = ROOT / "docs" / "v02-rc-record.md"
CHANGELOG = ROOT / "CHANGELOG.md"
CAMPAIGN = ROOT / "benchmarks" / "m06" / "openidaes450" / "runs" / "w27-m07-83f825d"
#: The W27 approval ceiling (M07.A51; registration: USD 15–45, ceiling 45).
SPEND_CEILING_USD = 45.0
(GATE_SET,) = [entry for entry in v0_2_gate.GATE_SETS if entry.name == "v0.2-gate-v1"]

#: Plan §4 (D14 certificates: M07) and the release requirements the alpha's M07a served (D17,
#: D20). Build decision, logged in the build log.
REQUIREMENTS = ("D14", "D17", "D20")
AT_CANDIDATE = ("A40", "A41", "A42")
#: §10: the eleven registered phrases (registration `gate.changelog_what_it_is_not`).
REGISTRATION = ROOT / "benchmarks" / "m07" / "registration.json"


# ----------------------------------------------------------------------------- the catalogue


@dataclass(frozen=True)
class Spec:
    """One assertion's evidence; its result is the worst of the parts."""

    id: str
    tests: tuple[str, ...] = ()
    records: tuple[str, ...] = ()
    jobs: tuple[str, ...] = ()
    measure: str | None = None


_J = "tests/test_m07_journey.py::test_"
_R = "tests/test_m07_journey_record.py::test_"
_G = "tests/test_m07_v0_2_gate.py::test_"
_STEP = {
    13: (
        "step13/rc-step13.json",
        "step13/m04-tests.junit.xml",
        "step13/step13-generator.log",
        "step13/step13-fixtures.log",
    ),
    14: (
        "step14/rc-step14.json",
        "step14/nlp.junit.xml",
        "step14/step14-nlp-check.log",
        "step14/m03-m05-tests.junit.xml",
        "step14/step14-m05-real-replay.log",
        "step14/step14-m03-reference.log",
    ),
    15: (
        "step15/rc-step15.json",
        "step15/step15-carry.log",
        "step15/step15-check.log",
        "step15/step15-replay.log",
    ),
    16: (
        "step16/rc-step16.json",
        "step16/m06-tests.junit.xml",
        "step16/step16-node.log",
        "step16/step16-dryrun.log",
    ),
    17: (
        "step17/rc-step17.json",
        "step17/step17a-tree.log",
        "step17/step17c-carry.log",
        "step17/step17d-diff.log",
        "step17/step17d-sha256.log",
    ),
}


def _verdicts(step: int) -> tuple[str, ...]:
    """The step's own JSON record, which `t08._record` reads for its verdict (the logs and junit
    files are re-hashed by `tests/test_m07_rc_records.py`, the records test)."""
    return (_STEP[step][0],)


SPECS: tuple[Spec, ...] = (
    Spec("A00", tests=(f"{_J}a00_*",)),
    *(Spec(f"A{n:02d}", tests=(f"{_J}a{n:02d}_*",)) for n in range(1, 9)),
    Spec("A10", tests=(f"{_J}a10_*", f"{_R}a10_*")),
    Spec("A11", tests=(f"{_J}a11_*", f"{_R}a10_a11_*")),
    *(Spec(f"A{n:02d}", tests=(f"{_J}a{n:02d}_*",)) for n in range(12, 16)),
    Spec("A20", tests=(f"{_R}a20_*",)),
    Spec("A21", tests=(f"{_J}a21_*", f"{_R}a21_*")),
    Spec("A22", tests=(f"{_R}a22_*",)),
    Spec("A23", tests=(f"{_J}a23_*", f"{_R}a23_*")),
    Spec("A24", tests=(f"{_J}a24_*", f"{_R}a24_*"), records=_verdicts(15)),
    Spec("A25", tests=(f"{_R}a25_*",)),
    Spec("A26", tests=(f"{_R}a26_*",)),
    *(Spec(f"A{n:02d}", tests=(f"{_G}a{n:02d}_*",)) for n in range(30, 39)),
    Spec("A40", measure="changelog"),
    Spec("A41", tests=("tests/test_m07_ledger.py",), measure="verdict_document"),
    Spec("A42", measure="policy"),
    Spec("A43", measure="self"),
    Spec("A50", measure="order"),
    Spec("A51", measure="records_and_spend"),
    Spec(
        "A60",
        records=(
            *_verdicts(13),
            *_verdicts(14),
            *_verdicts(16),
            "ci/job-logs/check-ubuntu-latest.log",
        ),
        jobs=("check (ubuntu-latest)",),
    ),
    Spec("A61", tests=(f"{_R}wo4_the_real_journey_is_committed",), records=_verdicts(15)),
    Spec("A62", records=_verdicts(17)),
)


def catalogue() -> dict[str, tuple[str, str]]:
    """`M07.<id>` → (subject, judged by), from §11 of the specification (first statement)."""
    found: dict[str, tuple[str, str]] = {}
    for line in SPEC.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^\| M07\.(A\d\d) \|", line)
        if match and match[1] not in found:
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            found[match[1]] = (cells[1], cells[-1])
    return dict(sorted(found.items()))


def _test_modules() -> list[str]:
    """Every module a selector names, once."""
    return sorted({selector.split("::")[0] for spec in SPECS for selector in spec.tests})


# ----------------------------------------------------------------------------- inputs


@dataclass
class Inputs:
    """What the checks judge (the attributes T08's readers use). `main` measures it."""

    commit: str
    tests: t08.TestRun
    ci: list[dict[str, Any]] = field(default_factory=list)
    manifest_exists: bool = False
    evidence: Path = ROOT / "evidence" / "M07"
    #: The commit the script ran at: the candidate, after the verdicts and the ledger.
    judged_at: str | None = None
    commands: int = 0

    @property
    def rc_dir(self) -> Path:
        return self.evidence / self.commit / "rc"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ----------------------------------------------------------------------------- measurements

Part = tuple[str, dict[str, Any]]


def _harness() -> Any:
    sys.path.insert(0, str(ROOT / "benchmarks" / "m06" / "w27"))
    import harness  # noqa: PLC0415

    return harness


def _m_order(inputs: Inputs) -> Part:
    """M07.A50: the digest chain and the commit rule over the committed campaign records."""
    verdict = _harness().order_check(CAMPAIGN)
    value = {
        "campaign": t08._shown(CAMPAIGN),
        "commit": verdict.get("commit"),
        "problems": verdict.get("problems"),
    }
    return ("pass" if verdict.get("passed") is True else "fail"), value


def _m_records_and_spend(inputs: Inputs) -> Part:
    """M07.A51: W27-A23 (restated, registration §23.12) on every `run.json`, and the recorded
    spend within the approval's ceiling."""
    harness = _harness()
    runs = sorted(CAMPAIGN.glob("**/" + harness.w27_scorer.RUN_FILE))
    failing = {
        str(path.relative_to(CAMPAIGN)): result["problems"]
        for path in runs
        if not (result := harness.a23(json.loads(path.read_bytes())))["passed"]
    }
    spent = harness.spend(CAMPAIGN)
    value = {
        "run_records": len(runs),
        "a23_failing": failing,
        "spend": spent,
        "ceiling_usd": SPEND_CEILING_USD,
    }
    ok = (
        bool(runs)
        and not failing
        and not spent["uncosted"]
        and spent["total_cost_usd"] <= SPEND_CEILING_USD
    )
    return ("pass" if ok else "fail"), value


def _m_changelog(inputs: Inputs) -> Part:
    """M07.A40: the eleven phrases verbatim in `## v0.2.0`."""
    phrases = json.loads(REGISTRATION.read_text(encoding="utf-8"))["gate"][
        "changelog_what_it_is_not"
    ]
    text = CHANGELOG.read_text(encoding="utf-8")
    start = text.index("\n## v0.2.0 ")
    following = text.find("\n## ", start + 1)
    section = text[start : following if following != -1 else len(text)]
    missing = [phrase for phrase in phrases if phrase not in section]
    value = {"phrases": len(phrases), "missing": missing}
    return ("pass" if len(phrases) == 11 and not missing else "fail"), value


def _m_verdict_document(inputs: Inputs) -> Part:
    """M07.A41: 17 rows, every clause label parsing under v0.2's grammar (the gate's parser
    raises on any departure)."""
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
    }
    ok = len(rows) == 17 and tuple(rows) == GATE_SET.claimed
    return ("pass" if ok else "fail"), value


def _m_policy(inputs: Inputs) -> Part:
    """M07.A42: ADR 0042's D3 and Frank tables pass the alpha's cell rule, read by the gate's own
    `policy` against the verdict document's `Judged` date."""
    adr = ROOT / GATE_SET.policy_adr
    path = ROOT / GATE_SET.verdict_document
    if not path.is_file():
        return "unsupported", {"state": "pending", "reason": "no verdict document to date against"}
    document = v0_2_gate.verdict_document(path.read_text(encoding="utf-8"), GATE_SET, inputs.commit)
    found = v0_2_gate.policy(
        adr.read_text(encoding="utf-8"), GATE_SET, document.judged, document.rejudged
    )
    value = {
        "d3_accepted": sorted(found.accepted),
        "problems": found.problems,
        "frank": found.frank,
    }
    return ("pass" if not found.problems and not found.frank else "fail"), value


MEASURES: dict[str, Callable[[Inputs], Part]] = {
    "order": _m_order,
    "records_and_spend": _m_records_and_spend,
    "changelog": _m_changelog,
    "verdict_document": _m_verdict_document,
    "policy": _m_policy,
}


# ----------------------------------------------------------------------------- the checks


def decide(spec: Spec, subject: str, judged_by: str, inputs: Inputs) -> dict[str, Any]:
    parts: list[str] = []
    value: dict[str, Any] = {"judged_by": judged_by}
    sources: list[tuple[str, Callable[[], Part]]] = []
    if spec.tests:
        sources.append(("tests", lambda: t08._tests(spec.tests, inputs)))  # type: ignore[arg-type]
    if spec.records:
        sources.append(("records", lambda: t08._records(spec.records, inputs)))  # type: ignore[arg-type]
    if spec.jobs:
        sources.append(("ci", lambda: t08._jobs(spec.jobs, inputs)))  # type: ignore[arg-type]
    if spec.measure is not None and spec.measure != "self":
        measure = spec.measure
        sources.append(("measured", lambda: MEASURES[measure](inputs)))
    for name, read in sources:
        try:
            result, said = read()
        except Exception as error:  # noqa: BLE001 - evidence that could not be read did not pass
            result, said = "fail", {"error": f"{type(error).__name__}: {error}"}
        parts.append(result)
        value[name] = said
    if spec.id in AT_CANDIDATE and value.get("measured", {}).get("state") != "pending":
        value["judged_at"] = inputs.judged_at
    description = re.sub(r"<([^<>]*)>", r"{\1}", subject)
    return {
        "id": f"M07.{spec.id}",
        "description": description,
        "result": t08._result(parts),
        "value": value,
    }


def _self(entry: dict[str, Any], others: Sequence[Mapping[str, Any]], inputs: Inputs) -> None:
    """M07.A43: this manifest is `tested` iff every other check passes, with commands run."""
    failing = [other["id"] for other in others if other["result"] != "pass"]
    entry["value"]["measured"] = {"other_checks": len(others), "not_pass": failing}
    entry["value"]["measured"]["commands"] = inputs.commands
    entry["result"] = "pass" if not failing and inputs.commands > 0 else "fail"


def checks(inputs: Inputs) -> list[dict[str, Any]]:
    listed = catalogue()
    specs = {spec.id: spec for spec in SPECS}
    if set(listed) != set(specs) or len(specs) != len(SPECS):
        raise SystemExit(
            "the catalogue and the checks differ: catalogue only "
            f"{sorted(set(listed) - set(specs))}, checks only {sorted(set(specs) - set(listed))}"
        )
    entries = [decide(specs[i], subject, judged, inputs) for i, (subject, judged) in listed.items()]
    (own,) = [entry for entry in entries if entry["id"] == "M07.A43"]
    _self(own, [entry for entry in entries if entry is not own], inputs)
    return entries


def status(entries: Sequence[Mapping[str, Any]]) -> str:
    """`tested` iff every check M07.A00–A62 passes; never `reviewed`."""
    return "tested" if entries and all(e["result"] == "pass" for e in entries) else "implemented"


def limitations(entries: Sequence[Mapping[str, Any]]) -> list[str]:
    found = [
        "Evidence class: numerical and software verification at M07's release candidate C "
        "(tests run here at a commit whose distribution trees equal C's; the RC records of steps "
        "13-17 on ref-x86-64; CI), and W27's campaign records at C_W carried to C by step 17. "
        "Self-generated records are regression evidence, not empirical validation.",
        "The design lane's verdicts on V11-V20 and W21-W27 are not judged here; M07.A40-A42 are "
        "judged at the candidate, after the verdicts and the ledger (§8 [A6], R-476).",
        "Step 18 (`scripts/v0_2_gate.py --rc C`) is not run by this script; M07.A36 is judged "
        "here by its tests, and step 18's line is recorded in the build log.",
    ]
    for entry in entries:
        if entry["result"] != "pass":
            state = (entry["value"].get("measured") or {}).get("state")
            found.append(
                f"{entry['id']} is {entry['result']}"
                + (f" ({state})" if state else "")
                + ": see its value."
            )
    return found


def _artifact_rows(inputs: Inputs, artifacts: Path | None) -> list[dict[str, str]]:
    rows = [
        (RC_RECORD, "the RC record at C (§8)"),
        (inputs.rc_dir / "records.json", "the RC records: sha256, size and how each is kept"),
        (ROOT / "release" / "rc-trees" / f"{inputs.commit}.json", "the tree record of C"),
    ]
    found = [
        {"path": t08._shown(path), "sha256": _sha256(path), "description": description}
        for path, description in rows
    ]
    junit = artifacts / "t08-tests.junit.xml" if artifacts is not None else None
    if junit is not None and junit.is_file():
        found.append(
            {
                "path": t08._shown(junit),
                "sha256": _sha256(junit),
                "description": "the tests run here, per node (not committed)",
            }
        )
    return found


def _rc_commands(inputs: Inputs) -> list[dict[str, Any]]:
    """The commands RC steps 13–17 ran at C, as their records state them."""
    found = []
    for step in sorted(_STEP):
        record = json.loads((inputs.rc_dir / _STEP[step][0]).read_text(encoding="utf-8"))
        machine = record["provenance"].get("machine_class")
        for check in record["checks"]:
            if check.get("command"):
                found.append(
                    {
                        "cmd": f"{check['command']} (RC step {step} at C, {machine}; "
                        f"{check['id']}: {check['result']})",
                        "cwd": ".",
                        "exit_code": int(check.get("exit_code", 0)),
                    }
                )
    return found


def build(
    inputs: Inputs, commands: Sequence[Mapping[str, Any]] = (), artifacts: Path | None = None
) -> dict[str, Any]:
    inputs.commands = len(commands)
    entries = checks(inputs)
    return {
        "work_package": "M07",
        "commit": inputs.commit,
        "requirements": list(REQUIREMENTS),
        "status": status(entries),
        "inputs": {
            "case_id": "M07's acceptance at C: one check per assertion of "
            f"docs/derivations/M07-spec.md §11 ({_sha256(SPEC)})",
            "case_hash": _sha256(inputs.rc_dir / "records.json"),
            "environment_lock_hash": _sha256(ROOT / "requirements.lock"),
        },
        "commands": [dict(command) for command in commands],
        "checks": entries,
        "artifacts": _artifact_rows(inputs, artifacts),
        "limitations": limitations(entries),
        "review": {"numerical": "pending", "process_model": "pending"},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    parser.add_argument("--commit", required=True, help="the release candidate C")
    parser.add_argument("--ci-run", action="append", default=[], help="a CI run id (repeatable)")
    parser.add_argument("--out", type=Path, default=None)
    arguments = parser.parse_args()

    commit = t08._git("rev-parse", f"{arguments.commit}^{{commit}}").strip()
    differing = v0_1_gate.tree_differences(commit, "HEAD")
    if differing:
        raise SystemExit(f"HEAD's distribution trees differ from C's (D2.4): {differing}")
    dirty = [ln for ln in t08._git("status", "--porcelain").splitlines() if "evidence/" not in ln]
    if dirty:
        raise SystemExit(f"the tree is not clean: {dirty[:5]}")
    destination = arguments.out or (ROOT / "evidence" / "M07" / commit / "manifest.json")
    artifacts = ROOT / "evidence" / "M07" / commit / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)

    head = t08._git("rev-parse", "HEAD").strip()
    inputs_dir = ROOT / "evidence" / "M07"
    commands: list[dict[str, Any]] = []
    ci: list[dict[str, Any]] = []
    for run_id in arguments.ci_run:
        run, command = t08.fetch_ci(run_id, artifacts)
        ci.append(run)
        commands.append(command)
    t08._test_modules = _test_modules  # T08's runner, over this catalogue's modules
    tests, test_command = t08.run_tests(artifacts)
    commands.append(test_command)
    inputs = Inputs(
        commit,
        tests,
        ci,
        manifest_exists=destination.is_file(),
        evidence=inputs_dir,
        judged_at=head,
    )
    commands.extend(_rc_commands(inputs))
    commands.append(
        {
            "cmd": "PYTHONPATH=src:. .venv/bin/python scripts/m07_evidence_manifest.py "
            f"--commit {commit}"
            + "".join(f" --ci-run {run_id}" for run_id in arguments.ci_run)
            + f" (run at {head})",
            "cwd": ".",
            "exit_code": 0,
        }
    )

    manifest = build(inputs, commands, artifacts)
    found = t08.problems(manifest)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(manifest, indent=1, ensure_ascii=False, allow_nan=False) + "\n", "utf-8"
    )
    counts = Counter(entry["result"] for entry in manifest["checks"])
    print(f"wrote {t08._shown(destination)}")
    print(f"tests run here: pytest exit {tests.exit_code}, {len(tests.nodes)} nodes")
    print(
        f"checks: {len(manifest['checks'])}: {counts['pass']} pass, {counts['fail']} fail, "
        f"{counts['unsupported']} unsupported; status {manifest['status']}"
    )
    for entry in manifest["checks"]:
        if entry["result"] != "pass":
            print(f"  {entry['id']}: {entry['result']}")
    for problem in found:
        print(f"invalid: {problem}")
    return 1 if found or manifest["status"] != "tested" else 0


if __name__ == "__main__":
    raise SystemExit(main())
