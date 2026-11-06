"""REL.A01–A05 and RP.S01: `scripts/release_gate.py`'s line-file loader and gate resolution.

The standing release procedure (RP, `docs/derivations/release-procedure.md`) §3; ADR 0055 D1.2,
D1.3 and §10. The line files are the committed `release/lines/{0.3,0.4}.json`, read from the
working tree; each RP.L control is a copy of the committed 0.4 file with one change, which the
loader must refuse with exit 2 and RP's reason (§3.4). REL.A03 runs `release_gate.py --line 0.3`
and `v0_3_gate.py` at the same checkout, and V03.A06–A08's constructed fixtures
(`tests/test_v03_v0_3_gate.py`) through both. REL.A05 runs `release.yml`'s gate step in the shell
harness of `tests/test_release_workflows.py`.
"""

from __future__ import annotations

import copy
import dataclasses
import json
import os
import re
import subprocess
import sys
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

import pytest
import test_release_workflows as workflows
import test_v03_v0_3_gate as v03
from conftest import REPO_ROOT

sys.path.insert(0, str(REPO_ROOT / "scripts"))
import release_gate  # noqa: E402
import v0_3_gate  # noqa: E402

C_0_3 = "a3e508e35fc5451fe56fa7b70941621992d35b50"
LINE_0_4 = json.loads((REPO_ROOT / "release" / "lines" / "0.4.json").read_text("utf-8"))


def reader(**overrides: Mapping[str, Any] | str | None) -> Callable[[str], bytes | None]:
    """The working tree's files, with `path=document` overrides (a mapping is written as JSON)."""

    def read(path: str) -> bytes | None:
        if path in overrides:
            value = overrides[path]
            if value is None:
                return None
            return (value if isinstance(value, str) else json.dumps(value)).encode("utf-8")
        file = REPO_ROOT / path
        return file.read_bytes() if file.is_file() else None

    return read


def line_0_4(edit: Callable[[dict[str, Any]], None]) -> Callable[[str], bytes | None]:
    """The committed 0.4 line file with one edit, as the candidate's tree."""
    document = copy.deepcopy(LINE_0_4)
    edit(document)
    return reader(**{"release/lines/0.4.json": document})


def refusal(read: Callable[[str], bytes | None], line: str = "0.4") -> list[str]:
    with pytest.raises(release_gate.LineError) as raised:
        release_gate.load_line(line, read)
    return str(raised.value).splitlines()


# -- REL.A01, RP.L01–RP.L10 -----------------------------------------------------------------------


def test_the_committed_line_files_load() -> None:
    line = release_gate.load_line("0.4", reader())
    assert [document["line"] for document in line.chain] == ["0.4", "0.3"]
    assert line.document["role"] == "gate"
    assert release_gate.load_line("0.3", reader()).document["role"] == "inheritance"


def test_a01_a_field_changed_and_not_in_changed_is_refused() -> None:
    def edit(document: dict[str, Any]) -> None:
        document["gate_set"]["packages"].append("S13")

    assert refusal(line_0_4(edit)) == [
        "line 0.4: field gate_set.packages differs from 0.3 and is not in changed"
    ]

    def listed(document: dict[str, Any]) -> None:
        edit(document)
        document["changed"].append("gate_set.packages")

    line = release_gate.load_line("0.4", line_0_4(listed))
    assert "S13" in line.gate_set.packages


def test_a01_the_command_exits_2(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def edit(document: dict[str, Any]) -> None:
        document["gate_set"]["packages"].append("S13")

    monkeypatch.setattr(release_gate, "_read_at", lambda candidate: line_0_4(edit))
    assert release_gate.main(["--line", "0.4", "--rc", "HEAD"]) == 2
    assert capsys.readouterr().err == (
        "error: line 0.4: field gate_set.packages differs from 0.3 and is not in changed\n"
    )


def test_l01_policy_adr_in_place_of_acceptances() -> None:
    def edit(document: dict[str, Any]) -> None:
        document["gate_set"]["policy_adr"] = document["gate_set"].pop("acceptances")

    (problem,) = refusal(line_0_4(edit))
    assert problem.startswith("line 0.4: RP.L01: not release-line-v1: gate_set: ")


def test_l02_inherits_naming_its_own_line() -> None:
    def edit(document: dict[str, Any]) -> None:
        document["inherits"] = "0.4"

    assert refusal(line_0_4(edit)) == ["line 0.4: RP.L02: the inherits chain 0.4 -> 0.4 is a cycle"]


def test_l02_line_is_the_stem() -> None:
    def edit(document: dict[str, Any]) -> None:
        document["line"] = "0.5"

    assert refusal(line_0_4(edit)) == ["line 0.4: RP.L02: `line` is '0.5', not the file's stem"]


def test_l04_a_name_in_changed_whose_field_is_equal() -> None:
    def edit(document: dict[str, Any]) -> None:
        document["changed"].append("gate_set.packages")

    assert refusal(line_0_4(edit)) == [
        "line 0.4: field gate_set.packages is in changed but equals 0.3's"
    ]


def test_l05_a_tests_glob_that_matches_nothing_at_c() -> None:
    tracked = subprocess.run(
        ["git", "ls-files"], cwd=REPO_ROOT, capture_output=True, text=True, check=True
    ).stdout.splitlines()
    tracked.append("scripts/wheel_data_check.py")  # RP §3.4: WO-R6's; RP.L08 is held below
    assert release_gate.tree_problems(release_gate.load_line("0.4", reader()), tracked) == []

    def edit(document: dict[str, Any]) -> None:
        document["gates"]["X31"]["tests"].append("tests/test_zz_*.py")

    line = release_gate.load_line("0.4", line_0_4(edit))
    assert release_gate.tree_problems(line, tracked) == [
        "line 0.4: RP.L05: X31 tests tests/test_zz_*.py: matches no tracked file at C"
    ]
    missing = [path for path in tracked if path != "docs/reviews/S09-verdicts.md"]
    assert release_gate.tree_problems(release_gate.load_line("0.4", reader()), missing) == [
        "line 0.4: RP.L05: X31 documents docs/reviews/S09-verdicts.md: does not exist at C"
    ]


def test_l05_a_directory_document_exists_by_its_files() -> None:
    line = release_gate.load_line("0.4", reader())
    assert "benchmarks/t08/ptc_r1" in LINE_0_4["gates"]["V14"]["documents"]
    paths = ["benchmarks/t08/ptc_r1/x.json"]
    assert not any("ptc_r1:" in problem for problem in release_gate.tree_problems(line, paths))
    assert any(
        "V14 documents benchmarks/t08/ptc_r1: does not exist" in problem
        for problem in release_gate.tree_problems(line, ["benchmarks/t08/ptc_r1x"])
    )


def test_l06_the_x31_entry_removed() -> None:
    def edit(document: dict[str, Any]) -> None:
        del document["gates"]["X31"]

    assert refusal(line_0_4(edit)) == [
        "line 0.4: RP.L06: the keys of gates are not the claimed gates: missing ['X31'], extra []"
    ]


def test_l07_a_step_17_pair_naming_no_item() -> None:
    def edit(document: dict[str, Any]) -> None:
        document["gates"]["X31"]["rc"].append([17, "NO-SUCH-ITEM"])

    assert refusal(line_0_4(edit)) == [
        "line 0.4: RP.L07: X31 rc [17, 'NO-SUCH-ITEM']: not an rc_items id"
    ]

    def elsewhere(document: dict[str, Any]) -> None:
        document["gates"]["X31"]["rc"].append([12, "PTC-R1"])

    assert refusal(line_0_4(elsewhere)) == [
        "line 0.4: RP.L07: X31 rc [12, 'PTC-R1']: an rc_items id at step 12"
    ]


def test_l08_a_duplicated_id() -> None:
    def edit(document: dict[str, Any]) -> None:
        document["rc_items"].append(copy.deepcopy(document["rc_items"][0]))

    assert refusal(line_0_4(edit)) == ["line 0.4: RP.L08: rc_items ids ['E01-A48'] are not unique"]


def test_l08_the_committed_0_4_line_passes_at_this_checkout() -> None:
    """RP §3.4: RP.L08 failed on `WHEEL-DATA` alone until WO-R6 provided
    `scripts/wheel_data_check.py`; with it, RP.L05 and RP.L08 pass on the committed 0.4 line."""
    tracked = subprocess.run(
        ["git", "ls-files"], cwd=REPO_ROOT, capture_output=True, text=True, check=True
    ).stdout.splitlines()
    line = release_gate.load_line("0.4", reader())
    assert release_gate.tree_problems(line, tracked) == []
    without = [path for path in tracked if path != "scripts/wheel_data_check.py"]
    assert release_gate.tree_problems(line, without) == [
        "line 0.4: RP.L08: WHEEL-DATA script scripts/wheel_data_check.py: not at C"
    ]


def test_l09_w27_added_to_the_clause_alternation() -> None:
    def edit(document: dict[str, Any]) -> None:
        document["gate_set"]["clause"] = r"\b(?:V(?:1[1-9]|20)|W2[1-7]|X31) \([a-z0-9]+\)"
        document["changed"].append("gate_set.clause")

    assert refusal(line_0_4(edit)) == [
        "line 0.4: RP.L09: the clause grammar parses 'W27 (a)', not claimed"
    ]


def test_l10_rejudge_waits_gains_an_unclaimed_gate() -> None:
    def edit(document: dict[str, Any]) -> None:
        document["gate_set"]["rejudge_waits"].append(["W27", "M02 N1"])
        document["changed"].append("gate_set.rejudge_waits")

    assert refusal(line_0_4(edit)) == [
        "line 0.4: RP.L10: rejudge_waits [W27, M02 N1]: W27 is not claimed"
    ]


def test_l10_a_frank_item_without_exactly_one_row() -> None:
    table = (REPO_ROOT / "release" / "acceptances.md").read_text("utf-8")
    without = "\n".join(line for line in table.splitlines() if not line.startswith("| M02 N1 |"))
    assert refusal(reader(**{"release/acceptances.md": without})) == [
        "line 0.4: RP.L10: 0 rows 'M02 N1' in release/acceptances.md, not 1"
    ]


# -- REL.A02: the 0.3 transcription -----------------------------------------------------------


def test_a02_the_0_3_gate_set_is_v0_3_gate_s_field_by_field() -> None:
    (registered,) = v0_3_gate.GATE_SETS
    entry = json.loads((REPO_ROOT / "release" / "lines" / "0.3.json").read_text("utf-8"))
    transcribed = release_gate.gate_set_of_entry(entry["gate_set"])
    assert entry["gate_set"]["acceptances"] == "docs/adr/0053-v0.3.0-release-policy.md"
    for field in dataclasses.fields(registered):
        ours, theirs = getattr(transcribed, field.name), getattr(registered, field.name)
        if field.name in ("covers", "clause"):
            ours, theirs = ours.pattern, theirs.pattern
        assert ours == theirs, field.name
    assert list(entry["gate_set"]) == list(release_gate.GATE_SET_FIELDS)


# -- REL.A03: the 0.3 line in dated mode is v0_3_gate.py byte for byte -----------------------


def _stdout(*arguments: str) -> tuple[int, str]:
    run = subprocess.run(
        [sys.executable, *arguments],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")},
    )
    return run.returncode, run.stdout


@pytest.mark.parametrize("flags", [[], ["--json"]])
def test_a03_the_command_at_the_same_checkout(flags: list[str]) -> None:
    generic = _stdout("scripts/release_gate.py", "--line", "0.3", "--rc", C_0_3[:8], *flags)
    legacy = _stdout("scripts/v0_3_gate.py", "--rc", C_0_3[:8], *flags)
    assert generic == legacy
    assert generic[1]


def _fixtures() -> list[tuple[str, dict[str, Any]]]:
    """V03.A06–A08's states, each as `v03.report`'s keyword arguments."""
    states: list[tuple[str, dict[str, Any]]] = [("yes", {})]
    for item, (state, *_) in sorted(v03.NO.items()):
        arguments: dict[str, Any] = {"candidate_files": v03.files(**state.get("files", {}))}
        for key in ("version", "rc_version", "differences"):
            if key in state:
                arguments[key] = state[key]
        states.append((f"item {item}", arguments))
    fail = {
        "ledger": v03.ledger({gate: "PASS" for gate in v03.CLAIMED} | {"X31": "FAIL"}),
        "verdicts": v03.document(v03.ALL_PASS | {"X31": ("FAIL", "X31 (c)", "—")}),
    }
    before = "accepted, 2026-11-19"
    for name, cell, clause in (
        ("a07 no row", v03.ACCEPTED, "X31 (a)"),
        ("a07 on judged", v03.ACCEPTED, "X31 (c)"),
        ("a07 the day before", before, "X31 (c)"),
    ):
        adr = v03.adr_0053(d3=cell, clause=clause)
        states.append((name, {"candidate_files": v03.files(**fail, adr_0053=adr)}))
    no = v03.files(adr_0050=None, envelope=v03.envelope(release="0.3.0rc1"))
    states.append(("a08 no", {"candidate_files": no}))
    return states


FIXTURES = _fixtures()


@pytest.mark.parametrize(("name", "state"), FIXTURES, ids=[name for name, _ in FIXTURES])
def test_a03_v03_fixtures_through_both(name: str, state: dict[str, Any]) -> None:
    legacy = v03.report(**state)
    line = release_gate.load_line("0.3", reader())
    candidate_files = state.get("candidate_files") or v03.files()
    version = state.get("version", v03.VERSION)
    generic = release_gate.build(
        files=candidate_files,
        rc=v03.RC,
        rc_version=state.get("rc_version") or version,
        rc_in_repository=True,
        candidate=v03.CANDIDATE,
        version=version,
        differences=state.get("differences") or [],
        is_ancestor=lambda commit: commit in v03.ANCESTORS,
        line=line,
    )
    assert generic == legacy
    assert release_gate.text(generic, line) == v0_3_gate.text(legacy)
    if legacy["gate_set"] is not None:
        assert release_gate.markdown(generic, line) == v0_3_gate.markdown(legacy)


def test_a03_the_fixtures_cover_yes_and_every_item() -> None:
    outcomes = {name: v03.report(**state)["tag_may_be_proposed"] for name, state in FIXTURES}
    assert outcomes["yes"] and outcomes["a07 on judged"]
    assert not any(outcomes[f"item {item}"] for item in range(1, 13))


def test_a03_a_w27_row_is_malformed_in_both() -> None:
    rows = v03.ALL_PASS | {"W27": ("PASS", "—", "—")}
    candidate_files = v03.files(verdicts=v03.document(rows))
    with pytest.raises(ValueError, match=r"does not claim: \['W27'\]"):
        release_gate.build(
            files=candidate_files,
            rc=v03.RC,
            rc_version=v03.VERSION,
            rc_in_repository=True,
            candidate=v03.CANDIDATE,
            version=v03.VERSION,
            differences=[],
            is_ancestor=lambda commit: True,
            line=release_gate.load_line("0.3", reader()),
        )


# -- REL.A05: release.yml resolves the gate ---------------------------------------------------


@pytest.fixture
def scratch(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "scripts").mkdir(parents=True)
    (repo / "release" / "lines").mkdir(parents=True)
    (repo / "pyproject.toml").write_text('[project]\nname = "p"\nversion = "0.4.0"\n', "utf-8")
    workflows._git(tmp_path, "init", "-q", str(repo))
    (tmp_path / "runner" / "record").mkdir(parents=True)
    return repo


def _gate(repo: Path, script: str) -> None:
    """A gate script that prints the command it was run as, then the YES line of `$VERSION`."""
    (repo / script).write_text(
        "import os, sys\n"
        "print('command:', ' '.join(sys.argv))\n"
        "print(f\"v{os.environ['VERSION']} tag may be proposed: YES\")\n",
        "utf-8",
    )


def _line_file(repo: Path, line: str, role: str) -> None:
    (repo / "release" / "lines" / f"{line}.json").write_text(json.dumps({"role": role}), "utf-8")


def _gate_command(repo: Path, version: str) -> subprocess.CompletedProcess[str]:
    return workflows._run(repo, "The release gate", version)


def test_a05_a_line_file_with_role_gate_runs_the_generic_gate(scratch: Path) -> None:
    _gate(scratch, "scripts/release_gate.py")
    _gate(scratch, "scripts/v0_4_gate.py")
    _line_file(scratch, "0.4", "gate")
    run = _gate_command(scratch, "0.4.0rc1")
    assert run.returncode == 0, run.stderr
    assert run.stdout.splitlines()[0] == (
        f"command: scripts/release_gate.py --line 0.4 --rc {workflows.C}"
    )


def test_a05_the_legacy_0_3_0_runs_the_legacy_script(scratch: Path) -> None:
    _gate(scratch, "scripts/release_gate.py")
    _gate(scratch, "scripts/v0_3_gate.py")
    _line_file(scratch, "0.3", "inheritance")
    for version in ("0.3.0", "0.3.0.post1"):
        run = _gate_command(scratch, version)
        assert run.returncode == 0, run.stderr
        assert run.stdout.splitlines()[0] == f"command: scripts/v0_3_gate.py --rc {workflows.C}"


def test_a05_neither_is_refused(scratch: Path) -> None:
    _gate(scratch, "scripts/release_gate.py")
    _line_file(scratch, "0.4", "gate")
    run = _gate_command(scratch, "0.5.0")
    assert run.returncode == 1
    assert run.stderr.strip() == "refused: no release gate for the 0.5 line"
    assert run.stdout == ""


def test_a05_the_generic_gate_s_refusals_name_it(scratch: Path) -> None:
    (scratch / "scripts" / "release_gate.py").write_text("import sys\nsys.exit(1)\n", "utf-8")
    _line_file(scratch, "0.4", "gate")
    run = _gate_command(scratch, "0.4.0")
    assert run.returncode == 1
    assert "refused: scripts/release_gate.py --line 0.4 exited 1" in run.stderr


def test_a05_a_malformed_line_file_fails_closed(scratch: Path) -> None:
    _gate(scratch, "scripts/v0_4_gate.py")
    (scratch / "release" / "lines" / "0.4.json").write_text("{", "utf-8")
    run = _gate_command(scratch, "0.4.0")
    assert run.returncode != 0
    assert "command:" not in run.stdout


def test_a05_the_step_s_text() -> None:
    run = workflows.step("gate", "The release gate")["run"]
    assert 'line="release/lines/$major.$minor.json"' in run
    assert 'if [ "$role" = gate ]; then' in run
    assert 'gate=(scripts/release_gate.py --line "$major.$minor")' in run
    assert 'gate=("scripts/v${major}_${minor}_gate.py")' in run
    assert 'refuse "no release gate for the $major.$minor line"' in run
    assert 'python "${gate[@]}" --rc "$RC"' in run


# -- amendment A-3 (RP §5.1, review S-2): the line file is byte-equal at C and the candidate -----


@pytest.mark.parametrize("path", ["release/lines/0.4.json", "release/lines/0.3.json"])
def test_a3_a_line_file_changed_after_c_exits_2(
    path: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The judged line file, or one it inherits, differs at the candidate from C's (here in its
    bytes only, one appended newline): exit 2. Control: the committed bytes pass the check."""
    changed = (REPO_ROOT / path).read_text(encoding="utf-8") + "\n"
    monkeypatch.setattr(release_gate, "_read_at", lambda candidate: reader(**{path: changed}))
    assert release_gate.main(["--line", "0.4", "--rc", "HEAD", "--lapses"]) == 2
    assert capsys.readouterr().err == (
        f"error: line 0.4: {path} differs between C and the candidate (RP §5.1, A-3): a change "
        "after C needs a new C\n"
    )
    monkeypatch.setattr(release_gate, "_read_at", lambda candidate: reader())
    assert release_gate.main(["--line", "0.4", "--rc", "HEAD", "--lapses"]) == 0
    assert capsys.readouterr().out.startswith("acceptance lapses at C = ")


# -- REL.A18: RP's coverage table (§14) -----------------------------------------------------------

RP_TEXT = (REPO_ROOT / "docs" / "derivations" / "release-procedure.md").read_text(encoding="utf-8")
A18_ROWS = (
    "R-460",
    "R-875",
    "R-902",
    "R-903",
    "R-906",
    "R-907",
    "R-909",
    "R-911",
    "R-913",
    "R-914",
)


def a18_problems(text: str) -> list[str]:
    """REL.A18: §14's first ten rows are the ten register entries, in order, and every `§n` or
    `§n.m` of a section cell names a heading of RP that exists."""
    headings = set(re.findall(r"^#{2,3} (\d+(?:\.\d+)?)\. ", text, flags=re.MULTILINE))
    headings |= set(re.findall(r"^#{2,3} (\d+\.\d+) ", text, flags=re.MULTILINE))
    section = text[text.index("## 14. Coverage table") : text.index("## 15. ")]
    rows = [
        [cell.strip() for cell in line.strip().strip("|").split("|")]
        for line in section.splitlines()
        if line.startswith("| R-")
    ]
    problems = []
    if tuple(row[0] for row in rows[:10]) != A18_ROWS:
        problems.append(f"the first ten rows are {[row[0] for row in rows[:10]]}")
    for row in rows:
        references = re.findall(r"§(\d+(?:\.\d+)?)", row[2])
        if not references:
            problems.append(f"{row[0]}: no section")
        problems += [
            f"{row[0]}: §{ref} is not a heading" for ref in references if ref not in headings
        ]
    return problems


def test_rel_a18_the_coverage_table() -> None:
    """Base: no problem. Controls: a referenced heading removed, a row removed."""
    assert a18_problems(RP_TEXT) == []
    assert a18_problems(RP_TEXT.replace("### 6.4 Step 12", "### 6.4x Step 12")) == [
        "R-909: §6.4 is not a heading",
        "R-480: §6.4 is not a heading",
    ]
    without = "\n".join(line for line in RP_TEXT.splitlines() if not line.startswith("| R-907 "))
    assert a18_problems(without)[0].startswith("the first ten rows are ")
