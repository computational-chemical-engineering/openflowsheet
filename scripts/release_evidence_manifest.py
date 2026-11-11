"""Generate a release's manifest `evidence/<pkg>/<C>/manifest.json`: RP's standing assertions
RP.S01–RP.S22 (`docs/derivations/release-procedure.md` §11.1) and one check per `rc_items` entry of
the line file (§6.7), measured, not transcribed (ADR 0055 D1.3, WO-R6). The pattern is 0.3.0's
`scripts/s13_evidence_manifest.py`, whose readers this script imports unchanged.

The checks are read from §11.1 itself, so that an assertion cannot be left out: an id without a
rule here, or a rule without an id there, stops the script. Each check is decided from the
evidence that measured it, and its `value` names that evidence; its result is the worst of its
parts (`fail` over `unsupported` over `pass`):

1. **D: tests run here**, each selection in its own pytest process (S13a's rule: exit 0, at least
   one passed, none skipped), and direct measurements of the line file read in this checkout
   (`release/` lies outside the D2.4 trees): RP.S02's version table, RP.S05's clause grammar,
   RP.S22's harvest exclusion.
2. **R: the RC records** under `evidence/<pkg>/<C>/rc/`, re-hashed against `rc/records.json` and
   read for their own verdicts (T08's `_record`: `passed`, every check `pass`, `commit` = C,
   `tree_clean`), at 0.3.0's paths and check ids (§6.1); the RC record by the gate's own
   `rc_record_problems`; the verdict document by its own parser; `release/acceptances.md` by the
   gate's standing rule; `CHANGELOG.md`; the required ADRs by the gate's `adr_problems`.
3. **CI**, read only from the runs given (`--ci-run ID`, or `--ci-json FILE` for a saved
   `gh run view` answer): a run counts only if its head is C. Step 1's jobs are the push run's,
   the others the `release_rc` dispatch's.
4. **RP.S18 (a)** is this manifest: `pass` iff every other check passes and commands were run.

Step 18 (`scripts/release_gate.py --line <l> --rc C`) is not run or judged here (R-914, RP §6.8):
RP.S08's R part, RP.S16 (b) and RP.S18 (b) are judged from its output in the build log.

`--rel-a20 S13-MANIFEST` is REL.A20 (§11.2): the same generator over 0.3.0's committed records
(`--line 0.3 --commit a3e508e3…`), whose twelve same-form assertions must each have the status
S13's manifest gives its counterpart, and whose ten changed-form ones are decided and listed with
the reason for their exclusion; RP.S18's failures must all be changed-form ones (amendment
A-1). Only in that mode may this checkout's trees differ from C's.

Status is `tested` iff every check is `pass`; otherwise `implemented`. `reviewed` is never set.

Usage:
    PYTHONPATH=src:. .venv/bin/python scripts/release_evidence_manifest.py --line 0.4 \\
        --commit C --k3 K3 --ci-run PUSH --ci-run DISPATCH [--manifest-adr N] [--out PATH]
"""

from __future__ import annotations

import argparse
import ast
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
import changelog_section  # noqa: E402
import release_gate as rg  # noqa: E402
import release_rc  # noqa: E402
import release_rc_local  # noqa: E402
import s13_evidence_manifest as s13  # noqa: E402
import t08_evidence_manifest as t08  # noqa: E402
import t08_support_matrix  # noqa: E402
import v0_1_gate  # noqa: E402
import v0_2_gate as engine  # noqa: E402

RP = ROOT / "docs" / "derivations" / "release-procedure.md"
CHANGELOG = ROOT / "CHANGELOG.md"

# ----------------------------------------------------------------------------- the records (§6)

#: §6.1: each local step's record, at 0.3.0's path (WO-R6 keeps them, so that REL.A20 reads them).
STEP_RECORD = {
    1: "step1/rc-step1.json",
    **s13._STEP,
}
#: §6.2: step 1's record holds exactly these checks.
STEP1_CHECKS = ("s1.push_run", "s1.check.x86_64", "s1.check.aarch64", "s1.junit")
#: §6.4 item 4: step 12's experiment record holds exactly `r375.audit`.
STEP12_EXPERIMENTS = s13.A34_RECORD
#: §6.6: step 16's four checks (a)–(d), V03.A32's.
STEP16_CHECKS = s13.A32_CHECKS
#: §6.5: step 14's two checks.
STEP14_CHECKS = ("a60.w24.nlp_tier_and_inventory", "a60.w24.nlp_selection")
_BOTH = ("ubuntu-latest", "ubuntu-24.04-arm")
#: The CI jobs of each step (§6.1, §6.10): step 1 is the push run's `check`; 2's G05 is the push
#: run's `identity`; the others are the `release_rc` dispatch's. Exactly V03.A20's job set.
STEP_JOBS: dict[int, tuple[str, ...]] = {
    1: tuple(f"check ({leg})" for leg in _BOTH),
    2: ("identity", *(f"rc-steps ({leg})" for leg in _BOTH)),
    3: ("dist",),
    4: tuple(f"clean-install ({leg})" for leg in _BOTH),
    5: ("bundle-set", *(f"bundle-replay ({leg})" for leg in _BOTH)),
    6: ("rc-ensemble",),
    **{step: tuple(f"rc-steps ({leg})" for leg in _BOTH) for step in (7, 8, 9, 10)},
}


def item_record(item_id: str) -> str:
    """§6.7: the record the step-17 wrapper writes for item `item_id`."""
    return f"step17/rc-step17-{item_id}.json"


# ----------------------------------------------------------------------------- the catalogue


@dataclass(frozen=True)
class Spec:
    """One check's evidence; its result is the worst of the parts."""

    id: str
    tests: tuple[tuple[str, ...], ...] = ()
    steps: tuple[int, ...] = ()
    jobs: tuple[int, ...] = ()
    records: tuple[str, ...] = ()
    measures: tuple[str, ...] = ()


_V03 = "tests/test_v03_v0_3_gate.py"
_REL = "tests/test_rel_release_gate.py"
_STANDING = "tests/test_rel_standing_acceptances.py"
#: One rule per assertion of §11.1. The D selections are the default gate's own tests.
SPECS: tuple[Spec, ...] = (
    Spec(
        "S01",
        tests=((_REL, "-k", "committed_line_files_load or test_l0 or test_l1 or test_a01_"),),
        measures=("line",),
    ),
    Spec("S02", measures=("version_table",)),
    Spec(
        "S03",
        tests=(
            (
                _V03,
                "tests/test_m07a_v0_2_gate.py",
                "tests/test_m07_v0_2_gate.py",
                f"{_REL}::test_a02_the_0_3_gate_set_is_v0_3_gate_s_field_by_field",
            ),
        ),
    ),
    Spec("S04", tests=((_V03, "-k", "a04_"),)),
    Spec("S05", measures=("clause",)),
    Spec("S06", tests=((_V03, "-k", "a06_"), (_REL, "-k", "a03_"), (_STANDING, "-k", "s06_"))),
    Spec("S07", tests=((_STANDING,),)),
    Spec("S08", tests=((_V03, "-k", "a08_"), (_REL, "-k", "a03_ or a05_"))),
    Spec("S09", measures=("versions",)),
    Spec("S10", measures=("changelog",)),
    Spec("S11", steps=(2, *range(6, 15), 16), jobs=tuple(STEP_JOBS), measures=("rc_record",)),
    Spec("S12", steps=(15,)),
    Spec("S13", measures=("items",)),
    Spec("S14", steps=(8,)),
    Spec("S15", steps=(1,), measures=("step1",)),
    Spec("S16", measures=("adrs",)),
    Spec("S17", measures=("verdict_document", "acceptances")),
    Spec("S18", measures=("self",)),
    Spec("S19", steps=(16,), measures=("step16",)),
    Spec("S20", steps=(14,), measures=("nlp_selection",)),
    Spec("S21", records=(STEP12_EXPERIMENTS,), measures=("experiments",)),
    Spec(
        "S22",
        tests=(("tests/test_m07a_harvest.py", "-k", "r911"),),
        measures=("harvest",),
    ),
)
#: §11.2's two lists, as RP states them; `catalogue()` checks them against §11.1's text.
SAME_FORM = ("S02", "S03", "S04", "S06", "S08", "S09", "S11", "S12", "S14", "S16", "S19", "S22")
CHANGED_FORM = ("S01", "S05", "S07", "S10", "S13", "S15", "S17", "S18", "S20", "S21")
#: §11.2: where each changed-form assertion's own acceptance is.
ACCEPTED_ELSEWHERE = {
    "S01": "RP.L01-L10 and REL.A01-A02",
    "S05": "RP.L09",
    "S07": "REL.A06-A10",
    "S15": "REL.A17",
    **{
        i: "its fixtures in WO-R6's tests (a passing record and one control per changed rule)"
        for i in ("S10", "S13", "S17", "S20", "S21")
    },
    "S18": "the generator's fixtures (every other check passes: pass; one fails: fail; zero "
    "commands: fail); its comparable part is A-1's sub-check below",
}
_ITEM = re.compile(r"^- \*\*RP\.(S\d\d)\*\* \(([A-Z, ]+)\)\. ")


@dataclass(frozen=True)
class Assertion:
    """One assertion of §11.1: its gates, its text, whether its form is 0.3.0's, its counterpart."""

    gates: tuple[str, ...]
    text: str
    same_form: bool
    counterpart: str | None


def catalogue(text: str | None = None) -> dict[str, Assertion]:
    """`RP.S01`–`RP.S22` from §11.1, each paragraph read for its gates and its `0.3.0:` note."""
    text = text if text is not None else RP.read_text(encoding="utf-8")
    section = text[text.index("### 11.1 Catalogue") : text.index("### 11.2 ")]
    paragraphs: dict[str, list[str]] = {}
    current = None
    for line in section.splitlines():
        match = _ITEM.match(line)
        if match:
            current = match[1]
            paragraphs[current] = [line]
        elif current and line.startswith("  "):
            paragraphs[current].append(line.strip())
        else:
            current = None
    found: dict[str, Assertion] = {}
    for key, lines in paragraphs.items():
        paragraph = " ".join(lines)
        match = _ITEM.match(paragraph)
        assert match is not None
        note = paragraph[paragraph.rindex("0.3.0: ") + len("0.3.0: ") :]
        counterpart = re.match(r"(V03\.A\d\d)", note)
        found[key] = Assertion(
            gates=tuple(g.strip() for g in match[2].split(",")),
            text=paragraph[match.end() :],
            same_form="Same form." in note,
            counterpart=counterpart[1] if counterpart else None,
        )
    same = tuple(k for k, a in found.items() if a.same_form)
    if same != SAME_FORM or tuple(k for k in found if k not in same) != CHANGED_FORM:
        raise SystemExit(f"§11.1's forms differ from §11.2's lists: same {same}")
    return found


# ----------------------------------------------------------------------------- inputs


@dataclass
class Inputs:
    """What the checks judge (the attributes T08's readers use). `main` measures it."""

    line: rg.Line
    commit: str
    tests: dict[str, Part] = field(default_factory=dict)
    ci: list[dict[str, Any]] = field(default_factory=list)
    evidence: Path | None = None
    k3: str | None = None
    version: str | None = None
    #: ADRs whose acceptance condition includes this manifest (R-913, R-914, RP §6.8).
    manifest_adrs: tuple[str, ...] = ()
    judged_at: str | None = None
    commands: int = 0

    @property
    def rc_dir(self) -> Path:
        package = self.line.document["gate_set"]["evidence_package"]
        return (self.evidence or ROOT / "evidence" / package) / self.commit / "rc"

    @property
    def gate_set(self) -> engine.GateSet:
        return self.line.gate_set

    @property
    def items(self) -> list[Mapping[str, Any]]:
        return list(self.line.document.get("rc_items", []))

    def steps(self, wanted: Sequence[int]) -> list[int]:
        return [step for step in wanted if step in self.gate_set.rc_steps]


Part = tuple[str, dict[str, Any]]


def ci_selection_problems(
    runs: Sequence[Mapping[str, Any]], commit: str, listed: Sequence[Mapping[str, Any]] | None
) -> list[str]:
    """Amendment A-4 (RP §6.2, §6.10): the manifest reads exactly C's push run and C's
    `release_rc` dispatch, and refuses any other run. Each given run is at C; at most one is a
    `push` and at most one a `workflow_dispatch`. Where step 1's record lists every `ci.yml` run
    at C (`listed`), the push run is §6.2's (the greatest push run id) and the dispatch the
    greatest dispatch run id. `gh run view` without `--attempt` reads a run's latest attempt; an
    attempt the given run states must be the one listed."""
    problems = [
        f"run {run.get('databaseId')}: its head {run.get('headSha')} is not C"
        for run in runs
        if run.get("headSha") != commit
    ]
    by_event: dict[str, list[Mapping[str, Any]]] = {}
    for run in runs:
        by_event.setdefault(str(run.get("event")), []).append(run)
    for event, found in sorted(by_event.items()):
        ids = [run.get("databaseId") for run in found]
        if event not in ("push", "workflow_dispatch"):
            problems.append(f"runs {ids}: event {event!r} is neither push nor workflow_dispatch")
        elif len(found) > 1:
            problems.append(f"runs {ids}: {len(found)} {event} runs given, not one (A-4)")
    if listed is not None:
        selections = (("push", release_rc.push_run), ("workflow_dispatch", release_rc.rc_dispatch))
        for event, select in selections:
            expected = select(listed, commit)
            for run in by_event.get(event, [])[:1]:
                if expected is None or run.get("databaseId") != expected.get("databaseId"):
                    problems.append(
                        f"run {run.get('databaseId')} is not the {event} run step 1 lists for C "
                        f"({None if expected is None else expected.get('databaseId')}; A-4)"
                    )
                elif run.get("attempt") not in (None, expected.get("attempt")):
                    problems.append(
                        f"run {run.get('databaseId')}: attempt {run.get('attempt')}, not the "
                        f"latest listed, {expected.get('attempt')} (A-4)"
                    )
    return problems


def listed_runs(rc_dir: Path, commit: str) -> list[dict[str, Any]] | None:
    """Step 1's `runs_at_c` (A-4), each at C; `None` without a step 1 record (0.3.0's). A step 1
    record that lists no runs is refused: it was not written by A-4's step 1."""
    record = rc_dir / STEP_RECORD[1]
    if not record.is_file():
        return None
    found = json.loads(record.read_text(encoding="utf-8")).get("runs_at_c")
    if not isinstance(found, list):
        raise SystemExit(f"{record}: no `runs_at_c` (RP §6.2, A-4)")
    return [{**run, "headSha": commit} for run in found]


def _read_here(path: str) -> bytes | None:
    file = ROOT / path
    return file.read_bytes() if file.is_file() else None


def load_line(name: str) -> rg.Line:
    """The line file as this checkout holds it (RP.L01–L04, L06, L07, L09, L10 by the loader)."""
    return rg.load_line(name, _read_here)


def version_at(commit: str) -> str | None:
    text = s13._show(commit, "src/openflowsheet/__init__.py")
    found = s13.A12C_VERSION.search(text or "")
    return found[1] if found else None


# ----------------------------------------------------------------------------- measurements (D)


def _m_line(inputs: Inputs) -> Part:
    """RP.S01: the line file loads (the loader's checks) and RP.L05/RP.L08 hold at C."""
    paths = t08._git("ls-tree", "-r", "--name-only", inputs.commit).splitlines()
    found = rg.tree_problems(inputs.line, paths)
    value = {
        "line": rg.line_path(inputs.line.name),
        "chain": [str(document["line"]) for document in inputs.line.chain],
        "tree_problems": found,
    }
    return ("pass" if not found else "fail"), value


def version_table(name: str) -> tuple[list[str], list[str]]:
    """RP.S02's table T-V(M.m): the covered versions, and the not covered."""
    major, minor = (int(part) for part in name.split("."))
    base = f"{major}.{minor}.0"
    covered = [base, f"{base}b1", f"{base}rc1", f"{base}rc12"]
    not_covered = [
        f"{base}a1",
        f"{base}b0",
        f"{base}rc0",
        f"{base}rc01",
        f"{base}.dev0",
        f"{base}.post1",
        f"{major}.{minor}.1",
        f"{major}.{minor}",
        f"{major}.{minor}0.0",
        f"{major + 1}.{minor}.0",
        f"{base} ",
    ]
    if minor >= 1:
        not_covered += [f"{major}.{minor - 1}.0", f"{major}.{minor - 1}.0rc1"]
    return covered, not_covered


def _m_version_table(inputs: Inputs) -> Part:
    """RP.S02: `gate_set_of` over T-V(M.m) gives the line's gate set exactly for the covered."""
    release = inputs.line.release()
    covered, not_covered = version_table(inputs.line.name)
    name = inputs.gate_set.name
    wrong = [v for v in covered if getattr(engine.gate_set_of(v, release), "name", None) != name]
    wrong += [v for v in not_covered if engine.gate_set_of(v, release) is not None]
    value = {"covered": len(covered), "not_covered": len(not_covered), "misclassified": wrong}
    return ("pass" if not wrong else "fail"), value


def _m_clause(inputs: Inputs) -> Part:
    """RP.S05: under the line's `clause`, `g (a)` parses for every claimed g, and for no
    not-claimed g, and `<first claimed> (A)` does not; under the inherited line's, `g (a)` does
    not parse for a g claimed only by this line."""
    gate_set = inputs.gate_set
    wrong = [g for g in gate_set.claimed if not gate_set.clause.fullmatch(f"{g} (a)")]
    wrong += [g for g in gate_set.not_claimed if gate_set.clause.fullmatch(f"{g} (a)")]
    capital = f"{gate_set.claimed[0]} (A)"
    if gate_set.clause.fullmatch(capital):
        wrong.append(capital)
    new: list[str] = []
    if len(inputs.line.chain) > 1:
        parent = rg.gate_set_of_entry(inputs.line.chain[1]["gate_set"])
        new = [g for g in gate_set.claimed if g not in parent.claimed]
        wrong += [f"{g} (inherited)" for g in new if parent.clause.fullmatch(f"{g} (a)")]
    value = {
        "claimed": len(gate_set.claimed),
        "not_claimed": len(gate_set.not_claimed),
        "new_claims": new,
        "wrong": wrong,
    }
    return ("pass" if not wrong else "fail"), value


_HEX40 = re.compile(r"^evidence/[^/]+/[0-9a-f]{40}/manifest\.json$")


def _harvest_excluded_at(commit: str) -> tuple[str, ...]:
    """`HARVEST_EXCLUDED` as `scripts/t08_support_matrix.py` declares it at `commit`."""
    source = t08._git("show", f"{commit}:scripts/t08_support_matrix.py")
    declared = re.search(r"^HARVEST_EXCLUDED: tuple\[str, \.\.\.\] = (.*)$", source, re.M)
    if declared is None:
        raise SystemExit(f"RP.S22: no HARVEST_EXCLUDED in t08_support_matrix.py at {commit}")
    value = ast.literal_eval(declared.group(1))
    if not isinstance(value, tuple) or not all(isinstance(item, str) for item in value):
        raise SystemExit(f"RP.S22: HARVEST_EXCLUDED at {commit} is not a tuple of str")
    return value


def _m_harvest(inputs: Inputs) -> Part:
    """RP.S22 (§5.2): `HARVEST_EXCLUDED` holds `evidence/<pkg>/`; C's tree holds nothing under
    it; every excluded manifest is `evidence/<pkg>/<40 hex>/manifest.json`; a package whose id
    merely starts with `<pkg>` is still harvested. The tuple is the one declared where the release
    manifest is written: at the commit that adds `evidence/<pkg>/<C>/manifest.json` once it is
    committed (so a later release's exclusion does not judge an earlier one, REL.A20), and in the
    working tree before that (orchestrator, 2026-11-10, 0.4.0 cut)."""
    prefix = f"evidence/{inputs.gate_set.evidence_package}/"
    commit = t08._git("rev-parse", f"{inputs.commit}^{{commit}}").strip()
    added = t08._git(
        "log", "--diff-filter=A", "--format=%H", "--", f"{prefix}{commit}/manifest.json"
    ).split()
    excluded = _harvest_excluded_at(added[-1]) if added else t08_support_matrix.HARVEST_EXCLUDED
    at_c = t08._git("ls-tree", "-r", "--name-only", inputs.commit, "--", prefix).splitlines()
    manifests = sorted(
        str(path.relative_to(ROOT))
        for member in excluded
        for path in (ROOT / member).glob("**/manifest.json")
    )
    sibling = f"evidence/{inputs.gate_set.evidence_package}x/{'0' * 40}/manifest.json"
    value = {
        "harvest_excluded": list(excluded),
        "at_c": at_c[:5],
        "manifests": manifests,
        "sibling_excluded": sibling.startswith(excluded),
    }
    ok = (
        prefix in excluded
        and not at_c
        and all(_HEX40.match(path) for path in manifests)
        and not sibling.startswith(excluded)
    )
    return ("pass" if ok else "fail"), value


# ----------------------------------------------------------------------------- measurements (R, CI)


def _m_versions(inputs: Inputs) -> Part:
    """RP.S09 (§7.1): at K3 and C the version-carrying files read the version, and the envelope
    reads `envelope_id: <envelope_id>` and `release: <version>`."""
    version = inputs.version
    if inputs.k3 is None or version is None:
        return "unsupported", {"reason": "K3 or the version is not given"}
    if not inputs.gate_set.covers.fullmatch(version):
        return "fail", {"version": version, "reason": "the line does not cover the version"}
    texts = [(path, wanted.replace("0.3.0", version)) for path, wanted in s13.VERSION_FILES]
    envelope_path, _ = s13.ENVELOPE
    envelope = (f"envelope_id: {inputs.gate_set.envelope_id}\n", f"release: {version}\n")
    value: dict[str, Any] = {"version": version}
    ok = True
    for name, commit in (("K3", inputs.k3), ("C", inputs.commit)):
        missing = [
            path
            for path, wanted in texts
            if wanted not in (text := s13._show(commit, path) or "") or f"{version}.dev0" in text
        ]
        lines = (s13._show(commit, envelope_path) or "").splitlines(keepends=True)
        if not all(line in lines for line in envelope):
            missing.append(envelope_path)
        value[name] = {"commit": commit, "not_as_stated": missing}
        ok = ok and not missing
    return ("pass" if ok else "fail"), value


def _verdict(inputs: Inputs) -> engine.VerdictDocument | None:
    path = ROOT / inputs.gate_set.verdict_document
    if not path.is_file():
        return None
    return engine.verdict_document(path.read_text(encoding="utf-8"), inputs.gate_set, inputs.commit)


def _standing_rows(inputs: Inputs) -> tuple[rg.Acceptances | None, rg.Scopes]:
    where = inputs.gate_set.policy_adr
    text = _read_here(where)
    table = rg.standing_acceptances(None if text is None else text.decode("utf-8"), where)
    head = inputs.judged_at or t08._git("rev-parse", "HEAD").strip()
    return table, rg.Scopes(rg.GitTrees(), inputs.line, inputs.commit, head)


def _failing_clauses(document: engine.VerdictDocument) -> list[str]:
    return [clause for row in document.rows.values() for clause in row.clauses]


def _m_changelog(inputs: Inputs) -> Part:
    """RP.S10 (§10): `## v<version>` holds each registered phrase verbatim, exactly once, and one
    line per accepted failure clause in force at C, `- <clause> FAIL, accepted by Frank <date>
    (release/acceptances.md)`, from the standing rows (each exactly once)."""
    if inputs.version is None:
        return "unsupported", {"reason": "the version is not given"}
    phrases = list(inputs.line.document["changelog_what_it_is_not"])
    section = changelog_section.section(CHANGELOG.read_text(encoding="utf-8"), f"v{inputs.version}")
    wrong = [phrase for phrase in phrases if section.count(phrase) != 1]
    value: dict[str, Any] = {"phrases": len(phrases), "not_once": wrong}
    document = _verdict(inputs)
    table, scopes = _standing_rows(inputs)
    if document is None:
        value["failure_lines"] = f"{inputs.gate_set.verdict_document} does not exist"
        return "fail", value
    if table is None:
        value["failure_lines"] = f"{inputs.gate_set.policy_adr} has no standing acceptances table"
        return "fail", value
    rows = {row.item: row for row in table.failures}
    expected = []
    for clause in _failing_clauses(document):
        row = rows.get(clause)
        if row is not None and rg.row_state(row, scopes).stands:
            expected.append(
                f"- {clause} FAIL, accepted by Frank {rg._date_word(row)} (release/acceptances.md)"
            )
    lines = section.splitlines()
    absent = [line for line in expected if lines.count(line) != 1]
    value.update({"failure_lines": expected, "not_once_lines": absent})
    return ("pass" if not wrong and not absent else "fail"), value


def _m_rc_record(inputs: Inputs) -> Part:
    """RP.S11: the RC record has a passed row for each step of `rc_steps` (the gate's own
    `rc_record_problems`)."""
    path = ROOT / inputs.gate_set.rc_record
    text = path.read_text(encoding="utf-8") if path.is_file() else None
    found = engine.rc_record_problems(text, inputs.commit, inputs.gate_set)
    value: dict[str, Any] = {"record": inputs.gate_set.rc_record, "problems": found}
    if text is not None:
        value["sha256"] = t08._sha256(path)
    return ("pass" if not found else "fail"), value


def _checks_of(inputs: Inputs, path: str) -> dict[str, Mapping[str, Any]]:
    record = json.loads((inputs.rc_dir / path).read_text(encoding="utf-8"))
    return {check["id"]: check for check in record["checks"]}


def item_part(item: Mapping[str, Any], inputs: Inputs) -> Part:
    """§6.7: the item's record passes at C and holds exactly one check, whose id is the item's."""
    path = item_record(str(item["id"]))
    result, value = t08._records((path,), inputs)  # type: ignore[arg-type]
    if (inputs.rc_dir / path).is_file():
        found = _checks_of(inputs, path)
        value["checks"] = {key: check.get("result") for key, check in found.items()}
        if sorted(found) != [item["id"]]:
            result = "fail"
    return result, {**value, "where": item["where"]}


def _m_items(inputs: Inputs) -> Part:
    """RP.S13: every `rc_items` entry passes at C; `unsupported` is not a pass."""
    if not inputs.items:
        return "unsupported", {"reason": "the line has no rc_items"}
    results = {str(item["id"]): item_part(item, inputs)[0] for item in inputs.items}
    return t08._result(list(results.values())), {"items": results}


def _m_step1(inputs: Inputs) -> Part:
    """RP.S15 (§6.2): step 1's record holds exactly `s1.push_run`, `s1.check.<arch>`, `s1.junit`."""
    found = _checks_of(inputs, STEP_RECORD[1])
    value = {"checks": sorted(found), "push_run": found.get("s1.push_run", {}).get("run_id")}
    return ("pass" if sorted(found) == sorted(STEP1_CHECKS) else "fail"), value


def _m_adrs(inputs: Inputs) -> Part:
    """RP.S16 (a): the gate's `adr_problems` here returns no problem but "ADR <n> is not
    Accepted" for a manifest-conditioned ADR whose status line starts `Status: Proposed`."""
    files = s13._working_files("docs/adr")
    found = engine.adr_problems(files, inputs.gate_set)
    admitted = [
        problem
        for problem in found
        if (match := re.match(r"^ADR (\d{4}) is not Accepted: ", problem))
        and match[1] in inputs.manifest_adrs
        and s13._bare_status(files, match[1]).startswith("Status: Proposed")
    ]
    value = {
        "required": len(inputs.gate_set.required_adrs),
        "problems": found,
        "admitted": admitted,
        "manifest_adrs": list(inputs.manifest_adrs),
    }
    return ("pass" if len(admitted) == len(found) else "fail"), value


def _m_verdict_document(inputs: Inputs) -> Part:
    """RP.S17 (§4.7): the header names C once with one `Judged` line, one row per claimed gate in
    order, every clause parsing (the gate's own parser raises on any departure)."""
    document = _verdict(inputs)
    if document is None:
        return "fail", {"reason": f"{inputs.gate_set.verdict_document} does not exist"}
    rows = {gate: row.verdict for gate, row in document.rows.items()}
    value = {
        "rows": len(rows),
        "verdicts": dict(sorted(Counter(rows.values()).items())),
        "judged": document.judged.isoformat() if document.judged else None,
    }
    return ("pass" if tuple(rows) == inputs.gate_set.claimed else "fail"), value


def _m_acceptances(inputs: Inputs) -> Part:
    """RP.S17 (§8.3): `acceptances` is a standing table, and each row the gate needs stands at
    C (cell rule, fingerprint): every `frank_items` row, and the row of each failing clause."""
    table, scopes = _standing_rows(inputs)
    where = inputs.gate_set.policy_adr
    if table is None:
        return "fail", {"reason": f"{where} has no standing acceptances table"}
    document = _verdict(inputs)
    needed = {row.item: row for row in table.decisions if row.item in inputs.gate_set.frank_items}
    failures = {row.item: row for row in table.failures}
    clauses = _failing_clauses(document) if document is not None else []
    needed.update({c: failures[c] for c in clauses if c in failures})
    missing = [i for i in (*inputs.gate_set.frank_items, *clauses) if i not in needed]
    states = {item: rg.row_state(row, scopes).word() for item, row in needed.items()}
    ok = not missing and all(word == "stands" for word in states.values())
    return ("pass" if ok else "fail"), {"acceptances": where, "rows": states, "missing": missing}


def _m_step16(inputs: Inputs) -> Part:
    """RP.S19 (§6.6): step 16's record holds exactly the four checks (a)–(d)."""
    found = _checks_of(inputs, STEP_RECORD[16])
    return ("pass" if sorted(found) == sorted(STEP16_CHECKS) else "fail"), {"checks": sorted(found)}


def _m_nlp_selection(inputs: Inputs) -> Part:
    """RP.S20 (§6.5): both checks pass; equal sets of node ids, n ≥ 1 recorded, the run over the
    modules exits 0, the modules listed."""
    found = _checks_of(inputs, STEP_RECORD[14])
    selection = found.get(STEP14_CHECKS[1], {})
    keys = ("modules", "selected_count", "all_count", "equal", "selected_exit_code")
    value = {key: selection.get(key) for key in keys}
    count = selection.get("selected_count")
    ok = (
        all(found.get(check, {}).get("result") == "pass" for check in STEP14_CHECKS)
        and bool(selection.get("modules"))
        and isinstance(count, int)
        and count >= 1
        and count == selection.get("all_count")
        and selection.get("equal") is True
        and selection.get("selected_exit_code") == 0
    )
    return ("pass" if ok else "fail"), value


def _m_experiments(inputs: Inputs) -> Part:
    """RP.S21 (§6.4): step 12's experiment record holds exactly `r375.audit`, which exited 0 with
    the registered line (j recorded, not judged)."""
    found = _checks_of(inputs, STEP12_EXPERIMENTS)
    audit = found.get("r375.audit", {})
    line = str(audit.get("last_line", ""))
    ok = (
        sorted(found) == ["r375.audit"]
        and audit.get("exit_code") == 0
        and release_rc_local.AUDIT_LINE.fullmatch(line) is not None
    )
    return ("pass" if ok else "fail"), {"checks": sorted(found), "audit_line": line}


MEASURES: dict[str, Callable[[Inputs], Part]] = {
    "line": _m_line,
    "version_table": _m_version_table,
    "clause": _m_clause,
    "harvest": _m_harvest,
    "versions": _m_versions,
    "changelog": _m_changelog,
    "rc_record": _m_rc_record,
    "items": _m_items,
    "step1": _m_step1,
    "adrs": _m_adrs,
    "verdict_document": _m_verdict_document,
    "acceptances": _m_acceptances,
    "step16": _m_step16,
    "nlp_selection": _m_nlp_selection,
    "experiments": _m_experiments,
}


# ----------------------------------------------------------------------------- the checks


def decide(spec: Spec, description: str, inputs: Inputs) -> dict[str, Any]:
    parts: list[str] = []
    value: dict[str, Any] = {}
    records = (*(STEP_RECORD[s] for s in inputs.steps(spec.steps)), *spec.records)
    jobs = tuple(job for step in inputs.steps(spec.jobs) for job in STEP_JOBS[step])
    sources: list[tuple[str, Callable[[], Part]]] = []
    if spec.tests:
        sources.append(
            ("tests", lambda: inputs.tests.get(spec.id) or ("fail", {"error": "not run"}))
        )
    if records:
        sources.append(("records", lambda: t08._records(records, inputs)))  # type: ignore[arg-type]
    if jobs:
        sources.append(("ci", lambda: t08._jobs(tuple(dict.fromkeys(jobs)), inputs)))  # type: ignore[arg-type]
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
        "id": f"RP.{spec.id}",
        "description": s13._braced(description),
        "result": t08._result(parts),
        "value": value,
    }


def _self(entry: dict[str, Any], others: Sequence[Mapping[str, Any]], inputs: Inputs) -> None:
    """RP.S18 (a): `tested` iff every other check passes, with commands run (R-913 (g1))."""
    failing = [other["id"] for other in others if other["result"] != "pass"]
    entry["value"]["self"] = {
        "other_checks": len(others),
        "not_pass": failing,
        "commands": inputs.commands,
    }
    entry["result"] = "pass" if not failing and inputs.commands > 0 else "fail"


def checks(inputs: Inputs) -> list[dict[str, Any]]:
    listed = catalogue()
    specs = {spec.id: spec for spec in SPECS}
    if list(listed) != list(specs):
        raise SystemExit(
            f"§11.1 and the checks differ: §11.1 only {sorted(set(listed) - set(specs))}, "
            f"checks only {sorted(set(specs) - set(listed))}"
        )
    for key, assertion in listed.items():
        tested = bool(specs[key].tests) or key in ("S02", "S05", "S22")
        if ("D" in assertion.gates) != tested:
            raise SystemExit(f"RP.{key}: its gates {assertion.gates} and its rule differ")
    entries = [
        decide(specs[key], f"RP.{key} ({', '.join(a.gates)}): {a.text}", inputs)
        for key, a in listed.items()
    ]
    for item in inputs.items:
        try:
            result, value = item_part(item, inputs)
        except Exception as error:  # noqa: BLE001
            result, value = "fail", {"error": f"{type(error).__name__}: {error}"}
        entries.append(
            {
                "id": f"ITEM.{item['id']}",
                "description": s13._braced(f"rc_items {item['id']} (§6.7): {item['assertion']}"),
                "result": result,
                "value": value,
            }
        )
    (own,) = [entry for entry in entries if entry["id"] == "RP.S18"]
    _self(own, [entry for entry in entries if entry is not own], inputs)
    return entries


# ----------------------------------------------------------------------------- the manifest


def status(entries: Sequence[Mapping[str, Any]]) -> str:
    """`tested` iff every check passes; never `reviewed`."""
    return "tested" if entries and all(e["result"] == "pass" for e in entries) else "implemented"


def limitations(entries: Sequence[Mapping[str, Any]], inputs: Inputs) -> list[str]:
    gate_set = inputs.gate_set
    found = [
        "Evidence class: numerical and software verification at the release candidate C (tests "
        "run here; the RC records at C on ref-x86-64; CI on x86-64 and aarch64). Self-generated "
        "records are regression evidence, not empirical validation.",
        f"Not harvested into {gate_set.envelope_id}. This manifest is written after C, and "
        "classifying its items would change benchmarks/t08/support_envelope.yaml, a D2.4 path. "
        f"scripts/t08_support_matrix.py excludes evidence/{gate_set.evidence_package}/, as R-485 "
        "and R-911 excluded M07's and S13's manifests from their releases' harvests; the next "
        "envelope's package harvests it.",
        "Step 18 (scripts/release_gate.py --line <l> --rc C) is not run or judged here (R-914, RP "
        "§6.8): RP.S08's R part, RP.S16 (b) and RP.S18 (b) are judged from its output in the "
        "build log.".replace("<l>", inputs.line.name),
    ]
    for entry in entries:
        if entry["result"] != "pass":
            found.append(f"{entry['id']} is {entry['result']}: see its value.")
    return found


def _rc_commands(inputs: Inputs) -> list[dict[str, Any]]:
    """The commands the RC records state they ran at C."""
    paths = [*STEP_RECORD.values(), STEP12_EXPERIMENTS]
    paths += [item_record(str(item["id"])) for item in inputs.items]
    found = []
    for path in paths:
        file = inputs.rc_dir / path
        if not file.is_file():
            continue
        record = json.loads(file.read_text(encoding="utf-8"))
        machine = (record.get("provenance") or {}).get("machine_class")
        for check in record.get("checks", []):
            command = check.get("command") or (
                " ".join(check["argv"]) if isinstance(check.get("argv"), list) else None
            )
            if command:
                found.append(
                    {
                        "cmd": f"{s13._braced(command)} (RC {path} at C, {machine}; "
                        f"{check['id']}: {check['result']})",
                        "cwd": ".",
                        "exit_code": int(check.get("exit_code", 0) or 0),
                    }
                )
    return found


def build(inputs: Inputs, commands: Sequence[Mapping[str, Any]] = ()) -> dict[str, Any]:
    inputs.commands = len(commands)
    entries = checks(inputs)
    index = inputs.rc_dir / "records.json"
    line_file = ROOT / rg.line_path(inputs.line.name)
    return {
        "work_package": inputs.gate_set.evidence_package,
        "commit": inputs.commit,
        "requirements": [],
        "status": status(entries),
        "inputs": {
            "case_id": f"line {inputs.line.name} at C: RP.S01-RP.S22 of "
            f"docs/derivations/release-procedure.md §11.1 ({t08._sha256(RP)}) and one check per "
            f"rc_items entry of {rg.line_path(inputs.line.name)} ({t08._sha256(line_file)})",
            "case_hash": t08._sha256(index) if index.is_file() else t08._sha256(line_file),
            "environment_lock_hash": t08._sha256(ROOT / "requirements.lock"),
        },
        "commands": [dict(command) for command in commands],
        "checks": entries,
        "artifacts": [
            {"path": t08._shown(path), "sha256": t08._sha256(path), "description": description}
            for path, description in (
                (ROOT / inputs.gate_set.rc_record, "the RC record"),
                (index, "the RC records: sha256, size and how each is kept"),
                (line_file, "the line file"),
            )
            if path.is_file()
        ],
        "limitations": limitations(entries, inputs),
        "review": {"numerical": "pending", "process_model": "pending"},
    }


# ----------------------------------------------------------------------------- REL.A20 (§11.2)


def rel_a20(manifest: Mapping[str, Any], s13_manifest: Mapping[str, Any]) -> tuple[bool, list[str]]:
    """§11.2: each same-form assertion has its counterpart's status in S13's manifest (RP.S22's
    counterpart is a test, not a check of that manifest: its status is RP's stated `pass`); each
    changed-form one is listed with its status and the reason for its exclusion. Amendment A-1:
    RP.S18's `not_pass` lies within the changed-form assertions, and commands were run."""
    listed = catalogue()
    theirs = {entry["id"]: entry["result"] for entry in s13_manifest["checks"]}
    ours = {entry["id"]: entry["result"] for entry in manifest["checks"]}
    equal = True
    lines = []
    for key in SAME_FORM:
        counterpart = listed[key].counterpart
        expected = theirs.get(counterpart, "absent") if counterpart else "pass"
        same = ours[f"RP.{key}"] == expected
        equal = equal and same
        lines.append(
            f"RP.{key} same form: {ours[f'RP.{key}']}; S13 {counterpart or 'test'} {expected}: "
            + ("equal" if same else "DIFFERS")
        )
    for key in CHANGED_FORM:
        lines.append(
            f"RP.{key} changed form: {ours[f'RP.{key}']}; excluded from the equality (§11.2), "
            f"accepted by {ACCEPTED_ELSEWHERE[key]}"
        )
    (own,) = [entry for entry in manifest["checks"] if entry["id"] == "RP.S18"]
    said = own["value"]["self"]
    outside = [i for i in said["not_pass"] if i.removeprefix("RP.") not in CHANGED_FORM]
    holds = not outside and said["commands"] > 0
    equal = equal and holds
    lines.append(
        f"RP.S18 (A-1): not_pass {len(said['not_pass'])}, outside the changed form "
        f"{outside or 'none'}; commands {said['commands']}: " + ("holds" if holds else "FAILS")
    )
    return equal, lines


# ----------------------------------------------------------------------------- main


def run_tests(
    artifacts: Path, tmp: Path
) -> tuple[dict[str, Part], list[dict[str, Any]], list[Path]]:
    """Every D assertion's selections, each in its own pytest process (S13a's rule)."""
    parts: dict[str, Part] = {}
    commands: list[dict[str, Any]] = []
    files: list[Path] = []
    for spec in SPECS:
        results, said = [], []
        for n, selection in enumerate(spec.tests):
            label = f"RP.{spec.id}" + (f".{n}" if len(spec.tests) > 1 else "")
            (result, value), command, written = s13._pytest_part(label, selection, artifacts, tmp)
            results.append(result)
            said.append(value)
            commands.append(command)
            files.extend(written)
        if spec.tests:
            parts[spec.id] = t08._result(results), {"selections": said}
    return parts, commands, files


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    parser.add_argument("--line", required=True, help="the line, <major>.<minor>")
    parser.add_argument("--commit", required=True, help="the release candidate C")
    parser.add_argument("--k3", default=None, help="the cut commit K3")
    parser.add_argument("--ci-run", action="append", default=[], help="a CI run id (repeatable)")
    parser.add_argument("--ci-json", action="append", type=Path, default=[], help="a saved run")
    parser.add_argument("--manifest-adr", action="append", default=[], help="R-914 (repeatable)")
    parser.add_argument("--evidence", type=Path, default=None, help="evidence/<pkg> (default)")
    parser.add_argument("--tmp", type=Path, default=None, help="private pytest temp root")
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--rel-a20", type=Path, default=None, help="S13's manifest: REL.A20")
    arguments = parser.parse_args(argv)

    line = load_line(arguments.line)
    package = line.document["gate_set"]["evidence_package"]
    commit = t08._git("rev-parse", f"{arguments.commit}^{{commit}}").strip()
    if arguments.rel_a20 is None:
        differing = v0_1_gate.tree_differences(commit, "HEAD")
        if differing:
            raise SystemExit(f"HEAD's distribution trees differ from C's (D2.4): {differing}")
        dirty = [
            ln for ln in t08._git("status", "--porcelain").splitlines() if "evidence/" not in ln
        ]
        if dirty:
            raise SystemExit(f"the tree is not clean: {dirty[:5]}")
    elif arguments.out is None:
        raise SystemExit("--rel-a20 needs --out: it never writes a release's manifest")
    destination = arguments.out or (ROOT / "evidence" / package / commit / "manifest.json")
    artifacts = destination.parent / "artifacts"
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
    for saved in arguments.ci_json:
        ci.append(json.loads(saved.read_text(encoding="utf-8")))
        commands.append(
            {
                "cmd": f"gh run view {ci[-1]['databaseId']} --json "
                "databaseId,headSha,conclusion,event,jobs,workflowName,url (saved)",
                "cwd": ".",
                "exit_code": 0,
                "stdout_sha256": t08._sha256(saved),
            }
        )
    rc_dir = Inputs(line, commit, evidence=arguments.evidence).rc_dir
    refused = ci_selection_problems(ci, commit, listed_runs(rc_dir, commit))
    if refused:
        raise SystemExit("CI runs refused (RP §6.2, §6.10, A-4):\n" + "\n".join(refused))
    tests, test_commands, _files = run_tests(artifacts, tmp)
    commands.extend(test_commands)
    inputs = Inputs(
        line,
        commit,
        tests,
        ci,
        evidence=arguments.evidence,
        k3=arguments.k3,
        version=version_at(commit),
        manifest_adrs=tuple(arguments.manifest_adr),
        judged_at=head,
    )
    commands.extend(_rc_commands(inputs))
    commands.append(
        {
            "cmd": "PYTHONPATH=src:. .venv/bin/python scripts/release_evidence_manifest.py "
            + " ".join(argv if argv is not None else sys.argv[1:]).replace(str(ROOT) + "/", "")
            + f" (run at {head})",
            "cwd": ".",
            "exit_code": 0,
        }
    )
    manifest = build(inputs, commands)
    found = t08.problems(manifest)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(manifest, indent=1, ensure_ascii=False, allow_nan=False) + "\n", "utf-8"
    )
    counts = Counter(entry["result"] for entry in manifest["checks"])
    print(
        f"{package} {manifest['status']} {commit[:8]}: {len(manifest['checks'])} checks, "
        f"{counts['pass']} pass, {counts['fail']} fail, {counts['unsupported']} unsupported; "
        "not pass: "
        + (" ".join(e["id"] for e in manifest["checks"] if e["result"] != "pass") or "none")
    )
    for problem in found:
        print(f"invalid: {problem}")
    if arguments.rel_a20 is not None:
        theirs = json.loads(arguments.rel_a20.read_text(encoding="utf-8"))
        equal, lines = rel_a20(manifest, theirs)
        print("\n".join(lines))
        print(f"REL.A20: {'PASS' if equal else 'FAIL'}")
        return 1 if found or not equal else 0
    return 1 if found or manifest["status"] != "tested" else 0


if __name__ == "__main__":
    raise SystemExit(main())
