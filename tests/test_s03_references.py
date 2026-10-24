"""S03 WO-S03-4: the column reference comparison, gated on the committed records (spec §7, §8, §11).

Authority: `docs/derivations/S03-spec.md` §11's A01, A02, A03 and A08–A14, as amended by §17.9,
§18.7 and §19.1. The gate never runs DWSIM or IDAES (§8): it reads the committed tool records, the
committed qualification records and `s03_reference.json` and recomputes the comparison with
`scripts/s03_reference_comparison.py`. From the committed files the document must equal
`benchmarks/s03/references/comparison.json` byte for byte; from a live solve of our side its
classifications must equal it exactly (A10). The classification is mechanical; the verdict is the
`verdict` agent's (§7.5).

The expectations are independent of both sides: `s03_reference.json`'s 25-digit twin values and
control discriminations, `s03_cases.json`'s registered inputs and tool settings, the environment
fingerprint of `docs/reference-environments.md` §3 and the exempt-module hashes of §17.6. A03, A08's
earlier-cases-file rule and A09 read git history and refuse explicitly without it (R-555's pattern).
"""

from __future__ import annotations

import ast
import copy
import hashlib
import json
import re
import subprocess
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from conftest import REPO_ROOT, sha256_of

sys.path.insert(0, str(REPO_ROOT / "scripts"))
sys.path.insert(0, str(REPO_ROOT / "spikes" / "references"))

import s03_reference_comparison as comparison  # noqa: E402
import s03_references_ours as ours_side  # noqa: E402

REFERENCES = REPO_ROOT / "benchmarks" / "s03" / "references"
RESULTS = REFERENCES / "results"
QUALIFICATION = REFERENCES / "qualification"
GENERATOR = REPO_ROOT / "docs" / "derivations" / "scripts" / "s03_reference.py"
CASES = json.loads(comparison.CASES_PATH.read_text(encoding="utf-8"))
REF = json.loads(comparison.TWIN_PATH.read_text(encoding="utf-8"))
TOOLS = comparison.TOOLS
CASE_IDS = tuple(CASES["cases"])
PAIRS = [(cid, tool) for cid in CASE_IDS for tool in TOOLS]
#: §18.7 A01.
CLAIMS = 4577
CASES_SHA256 = "c901d6c90f4b700b92ff98e2a01ae7e8f1d5557b80dd647e3b14e089d3703f39"
HISTORY = "S03 A03, A08 and A09 need the repository's history (a full clone; R-555's pattern)"


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, check=False
    )


def git_show(commit: str, path: str) -> str | None:
    out = git("show", f"{commit}:{path}")
    return out.stdout if out.returncode == 0 else None


def require_history(*commits: str) -> None:
    for commit in commits:
        assert git("cat-file", "-e", f"{commit}^{{commit}}").returncode == 0, (
            f"{HISTORY}: {commit} is not in this repository"
        )


def contained(earlier: Any, current: Any) -> bool:
    """`earlier` survives in `current` by additions only (§17's preamble: every earlier JSON value
    is present and identical; a mapping may gain keys)."""
    if isinstance(earlier, dict):
        return isinstance(current, dict) and all(
            k in current and contained(v, current[k]) for k, v in earlier.items()
        )
    return bool(earlier == current)


@pytest.fixture(scope="module")
def table() -> dict[str, Any]:
    committed: dict[str, Any] = load(comparison.TABLE)
    return committed


@pytest.fixture(scope="module")
def records() -> dict[tuple[str, str], dict[str, Any] | None]:
    return comparison.load_records(cases=CASES)


def rows(document: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    return {(r["case"], r["tool"]): r for r in document["rows"]}


def tool_record(tool: str, cid: str) -> dict[str, Any] | None:
    path = RESULTS / f"{tool.lower()}-{cid}.json"
    return load(path) if path.exists() else None


# -- A01 -------------------------------------------------------------------------------------------


def test_a01_the_generator_checks_and_the_twin_hashes_the_cases() -> None:
    """A01: `s03_reference.py --check` re-derives every claim and both files are byte-identical;
    `ref.cases_sha256` is the SHA-256 of `cases` (§18.7: 4577 claims, `c901d6c9…`)."""
    assert REF["claim_count"] == CLAIMS == len(REF["claims"])
    assert REF["cases_sha256"] == CASES_SHA256 == sha256_of(comparison.CASES_PATH)
    done = subprocess.run(
        [sys.executable, "-I", str(GENERATOR), "--check"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=3600,
        check=False,
    )
    output = done.stdout + done.stderr
    assert done.returncode == 0, output[-4000:]
    assert re.search(rf"^{CLAIMS} claims passed$", output, re.MULTILINE), output[-2000:]
    for name in ("s03_cases.json", "s03_reference.json"):
        assert re.search(rf"{re.escape(name)} is byte-identical", output), output[-2000:]


# -- A02 -------------------------------------------------------------------------------------------


@pytest.mark.parametrize(("cid", "tool"), PAIRS)
def test_a02_the_tools_ran_the_registered_inputs(cid: str, tool: str) -> None:
    """A02: every tool record names `s03_cases.json` as its input and carries the case entry
    as registered (§17.8's earlier-cases-file rule makes the standing DWSIM entries equal)."""
    record = tool_record(tool, cid)
    if record is None:
        assert CASES["cases"][cid]["tool_variant"][tool] == "not_applicable"
        return
    assert record["case"] == cid and record["tool"] == tool
    assert record["input_file"] == "docs/derivations/scripts/s03_cases.json"
    assert record["case_definition"] == CASES["cases"][cid]
    if "cases_sha256" in record:
        assert record["cases_sha256"] == CASES_SHA256


def test_a02_the_classifier_reads_the_registered_quantity_lists(table: dict[str, Any]) -> None:
    """A02: the classifier's quantity list per case is `cases.cases.<case>.quantities`, in order,
    for every pair rule 4 compared; the our-side alias map is §18.7's on both sides."""
    assert comparison.OURS_ALIASES == ours_side.OURS_ALIASES == {"PC-L": "RC1", "PC-LI": "RC1"}
    compared = [r for r in table["rows"] if r["rule"] == 4 or "before_control_rule" in r]
    assert compared
    for r in compared:
        if "quantities" in r:
            names = [q["quantity"] for q in r["quantities"]]
            assert names == [q for q, _ in CASES["cases"][r["case"]]["quantities"]], r["case"]
            kinds = [q["kind"] for q in r["quantities"]]
            assert kinds == [k for _, k in CASES["cases"][r["case"]]["quantities"]], r["case"]


# -- A03 -------------------------------------------------------------------------------------------

#: §8's forbidden strings, case-sensitive.
FORBIDDEN = (
    "s03_reference",
    "s02_reference",
    "s06_reference",
    "openflowsheet",
    "ours-",
    "comparison",
    "twin",
)
#: §17.6: the exempt modules, pinned; they may contain `twin` and `comparison` only.
EXEMPT = {
    "spikes/references/t06_fixtures.py": (
        "c6320cc81ea4bf08c36f7d7b5aca19180c2109fd66e4e23c84476d35286ba61f"
    ),
    "spikes/references/t06_qualify_dwsim.py": (
        "e3c1218e435df89462a6aa6ee894f2eccd5576d7012182d31a7f23c92e4e46d0"
    ),
    "spikes/references/t06_qualify_idaes.py": (
        "aead49938b96e43514ff4e4bcacece87c65d413efa8733e20793c8fd1c7e6eea"
    ),
}
EXEMPT_MAY_CONTAIN = ("twin", "comparison")
TOOL_SCRIPTS = (
    "spikes/references/s03_qualify_idaes.py",
    "spikes/references/s03_qualify_dwsim.py",
    "spikes/references/s03_qualify.sh",
)
#: The data files a scanned module may name: the one project input (§2.3 step 2), the two
#: qualification outputs, and DWSIM's own runtime configuration (a file of the tool environment).
DATA_NAMES_ALLOWED = {
    "s03_cases.json",
    "idaes.json",
    "dwsim.json",
    "DWSIM.UI.Desktop.runtimeconfig.json",
    "dwsim-{}.json",
    "idaes-{}.json",
}
DATA_SUFFIX = re.compile(r"\.(json|ya?ml|csv|toml|txt|npz|npy|pkl)$")


def scan_points() -> dict[str, str | None]:
    """HEAD's working tree, and every qualification commit (§17.6 item 4, §18.7)."""
    points: dict[str, str | None] = {"HEAD": None}
    for commits in comparison.QUALIFICATION_COMMITS.values():
        for commit in commits:
            points[commit[:8]] = commit
    return points


def read_at(commit: str | None, path: str) -> str | None:
    if commit is None:
        file = REPO_ROOT / path
        return file.read_text(encoding="utf-8") if file.exists() else None
    return git_show(commit, path)


def imported_modules(source: str) -> set[str]:
    """Every module named by an import statement, function-level ones included."""
    names: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            names |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module.split(".")[0])
    return names


def scanned_set(commit: str | None) -> dict[str, str]:
    """The tool scripts present at `commit` and every in-repository module they import,
    transitively (a module resolves to `spikes/references/<name>.py`, the scripts' directory)."""
    found: dict[str, str] = {}
    todo = [p for p in TOOL_SCRIPTS if read_at(commit, p) is not None]
    while todo:
        path = todo.pop()
        if path in found:
            continue
        source = read_at(commit, path)
        assert source is not None, path
        found[path] = source
        if not path.endswith(".py"):
            continue
        for name in sorted(imported_modules(source)):
            candidate = f"spikes/references/{name}.py"
            if candidate not in found and read_at(commit, candidate) is not None:
                todo.append(candidate)
            for root in ("src", "scripts", "tests", "benchmarks", "docs"):
                assert read_at(commit, f"{root}/{name}.py") is None or name in {"conftest"}, (
                    f"{path} imports {name}, which resolves outside spikes/references"
                )
    return found


def data_names(source: str) -> set[str]:
    """String literals naming a data file, docstrings excluded; an f-string is read with `{}` for
    each placeholder (the per-case output names `dwsim-{}.json`, `idaes-{}.json`)."""
    tree = ast.parse(source)
    skip = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Module | ast.FunctionDef | ast.ClassDef | ast.AsyncFunctionDef):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                skip.add(id(body[0].value))
    texts = []
    for node in ast.walk(tree):
        if isinstance(node, ast.JoinedStr):
            parts = []
            for part in node.values:
                skip.add(id(part))
                is_text = isinstance(part, ast.Constant) and isinstance(part.value, str)
                parts.append(part.value if is_text else "{}")
            texts.append("".join(parts))
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in skip:
            texts.append(node.value)
    return {Path(t.strip()).name for t in texts if DATA_SUFFIX.search(t.strip())}


@pytest.mark.parametrize("point", list(scan_points()))
def test_a03_the_tool_scripts_are_blind(point: str) -> None:
    """A03 (§8 as amended by §17.6 and §18.7): at HEAD and at every qualification commit, the S03
    tool scripts and every in-repository module they import contain none of the seven strings
    (the three pinned exempt modules may contain `twin` and `comparison`, and nothing else of the
    list); an exempt module's hash is the pinned one; the only project data file they name is
    `s03_cases.json`; the script that produced a commit's records is present at it."""
    commit = scan_points()[point]
    if commit is not None:
        require_history(commit)
    found = scanned_set(commit)
    producers = {
        tool: f"spikes/references/s03_qualify_{tool.lower()}.py"
        for tool, commits in comparison.QUALIFICATION_COMMITS.items()
        if commit is None or commit in commits
    }
    for tool, script in producers.items():
        assert script in found, f"{point}: {tool}'s tool script is missing"
    assert {"spikes/references/s03_qualify.sh"} <= set(found)
    for path, source in found.items():
        exempt = path in EXEMPT
        if exempt:
            digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
            assert digest == EXEMPT[path], "exempt module changed: re-register in S03 §17.6"
        for word in FORBIDDEN:
            if exempt and word in EXEMPT_MAY_CONTAIN:
                continue
            assert word not in source, f"{point}: {path} contains {word!r}"
        if path.endswith(".py"):
            extra = data_names(source) - DATA_NAMES_ALLOWED
            assert not extra, f"{point}: {path} names data files {sorted(extra)}"
    s03 = [p for p in found if Path(p).name.startswith("s03_qualify_")]
    for path in s03:
        assert "s03_cases.json" in found[path], path


# -- A08 -------------------------------------------------------------------------------------------

#: §8's fields of a tool record that ran (a selected attempt), and of every record.
FIELDS_EVERY = {"case", "tool", "environment_fingerprint", "settings", "attempts", "available"}
FIELDS_RAN = {
    "level",
    "stage_map",
    "feed_stages",
    "condenser_realization",
    "reboiler_realization",
    "specifications",
    "converged",
    "termination",
    "raw_output",
    "registered_quantities",
    "rule_values",
    "accuracy_rerun",
    "settings_used",
}


def test_a08_every_registered_pair_has_its_record() -> None:
    """A08 (i)-(ii): one record per registered (case, tool), a `not_applicable` pair needing none
    (a record that exists says `not_applicable`); no record outside the registered set; our
    records are `OURS_CASES` exactly."""
    expected = set()
    for cid, tool in PAIRS:
        path = RESULTS / f"{tool.lower()}-{cid}.json"
        if CASES["cases"][cid]["tool_variant"][tool] == "not_applicable":
            if path.exists():
                assert "not_applicable" in load(path), path.name
                expected.add(path.name)
            continue
        assert path.exists(), path.name
        assert "not_applicable" not in load(path), path.name
        expected.add(path.name)
    present = {p.name for p in RESULTS.glob("*.json") if not p.name.startswith("ours-")}
    assert present == expected
    ours = {p.name for p in RESULTS.glob("ours-*.json")}
    assert ours == {f"ours-{c}.json" for c in ours_side.OURS_CASES}
    assert set(ours_side.OURS_CASES) | set(comparison.OURS_ALIASES) == set(CASE_IDS)


@pytest.mark.parametrize(("cid", "tool"), PAIRS)
def test_a08_every_record_carries_section_8s_fields_and_the_settings(cid: str, tool: str) -> None:
    """A08: §8's fields; the registered settings as `s03_cases.json` has them (IDAES also
    `IDAES_amendment_2`, §18.7 (iii)); the script's registered quantities are the ones the
    classifier recomputes from the raw fields (no harness defect, B4-2)."""
    record = tool_record(tool, cid)
    if record is None or "not_applicable" in record:
        return
    assert FIELDS_EVERY <= set(record), sorted(FIELDS_EVERY - set(record))
    assert contained(record["settings"]["registered"], CASES["tool_settings"][tool])
    if tool == "IDAES":
        assert record["settings"]["amendment_2"] == CASES["tool_settings"]["IDAES_amendment_2"]
    if not record["available"]:
        assert record["not_available_reason"]
        return
    assert FIELDS_RAN <= set(record), sorted(FIELDS_RAN - set(record))
    case = CASES["cases"][cid]
    recomputed = comparison.tool_quantities(comparison.view(record, case), case)
    assert recomputed == record["registered_quantities"]
    assert list(recomputed) == [q for q, _ in case["quantities"]]
    assert set(record["accuracy_rerun"]["quantities"]) == set(recomputed)


def record_commit(path: Path) -> str:
    out = git("log", "-1", "--format=%H", "--", str(path.relative_to(REPO_ROOT)))
    assert out.returncode == 0 and out.stdout.strip(), f"{HISTORY}: no commit for {path.name}"
    return out.stdout.strip()


@pytest.mark.parametrize(("cid", "tool"), PAIRS)
def test_a08_records_from_an_earlier_cases_file_stand(cid: str, tool: str) -> None:
    """A08 (§17.8): the record's qualification commit is a registered one; there, the case's entry
    equals today's, every `tool_settings` key is present and equal today, and a recorded cases
    SHA-256 is that file's."""
    path = RESULTS / f"{tool.lower()}-{cid}.json"
    if not path.exists():
        return
    require_history(*[c for cs in comparison.QUALIFICATION_COMMITS.values() for c in cs])
    commit = record_commit(path)
    assert commit in comparison.QUALIFICATION_COMMITS[tool], (path.name, commit)
    earlier_text = git_show(commit, "docs/derivations/scripts/s03_cases.json")
    assert earlier_text is not None, HISTORY
    earlier = json.loads(earlier_text)
    assert earlier["cases"][cid] == CASES["cases"][cid]
    for key, value in earlier["tool_settings"].items():
        assert contained(value, CASES["tool_settings"][key]), key
    record = load(path)
    if "cases_sha256" in record:
        assert record["cases_sha256"] == hashlib.sha256(earlier_text.encode()).hexdigest()


def dwsim_order(record: dict[str, Any]) -> list[tuple[str, float, str]]:
    """§17.2's order of positions for one DWSIM record: L1 (tolerances tightest first, each
    method in order), then L2(a) for each method under which L1 was structurally inexpressible."""
    settings = CASES["tool_settings"]["DWSIM"]
    tolerances = [float(t) for t in settings["column_tolerance_ladder"]]
    methods = settings["column_method_order_amendment_1"]["methods"]
    order = [("L1", t, m) for t in tolerances for m in methods]
    attempts = {(a["level"], a["tolerance"], a["method"]): a for a in record["attempts"]}
    for m in methods:
        l1 = [attempts.get(("L1", t, m)) for t in tolerances]
        if any(a is not None and a.get("structurally_expressible") is False for a in l1):
            order += [("L2", t, m) for t in tolerances]
    return order


@pytest.mark.parametrize("cid", CASE_IDS)
def test_a08_dwsim_ladder_conformance(cid: str) -> None:
    """A08 (§17.8): the selected (level, tolerance, method) is the first attempt in §17.2's order
    that passed structural inspection and rules 2–2d; a not-available record shows every position
    as a failed attempt or a structural reason. Russell and Burningham–Otto attempts are ignored."""
    record = tool_record("DWSIM", cid)
    if record is None or "not_applicable" in record:
        return
    attempts = {(a["level"], a["tolerance"], a["method"]): a for a in record["attempts"]}
    order = dwsim_order(record)
    first = None
    for position in order:
        attempt = attempts.get(position)
        assert attempt is not None, f"{cid}: position {position} has no attempt"
        if attempt.get("structurally_expressible") is False:
            assert attempt["failed_rule"] == "structural" and attempt["reason"], position
            assert not attempt["passes"]
            continue
        if attempt["passes"]:
            first = position
            break
        assert attempt["failed_rule"] and attempt["reason"], position
    if record["available"]:
        used = record["settings_used"]
        assert first == (record["level"], used["column_tolerance"], used["method"]), first
    else:
        assert first is None


@pytest.mark.parametrize("cid", CASE_IDS)
def test_a08_idaes_ladder_conformance(cid: str) -> None:
    """A08 (iii) (§18.7): at every attempted level all three positions are recorded (a run or the
    reason none was made); the selected (level, position) is the first that passes in §18.1's
    order and no later level was attempted; a not-available record shows every position at every
    expressible level."""
    record = tool_record("IDAES", cid)
    if record is None or "not_applicable" in record:
        return
    positions = [p["id"] for p in CASES["tool_settings"]["IDAES_amendment_2"]["path_positions"]]
    assert positions == ["P0", "P1", "P2"]
    selected = None
    for level in ("L1", "L2", "L3"):
        entry = record["levels"].get(level)
        if entry is None:
            assert selected is not None, f"{cid}: {level} neither attempted nor after a pass"
            continue
        if not entry["realization"]["expressible"]:
            assert "positions" not in entry, level
            continue
        if selected is not None:
            assert "positions" not in entry, f"{cid}: {level} attempted after a passing level"
            continue
        assert list(entry["positions"]) == positions, (cid, level)
        for name in positions:
            summary = entry["positions"][name]["summary"]
            assert summary["position"] == name and summary["level"] == level
            assert summary["reason"], (cid, level, name)
        passing = [p for p in positions if entry["positions"][p]["summary"]["passes"]]
        if entry["passes"]:
            selected = (level, passing[0])
            assert entry["selected_position"] == passing[0]
    if record["available"]:
        assert selected == (record["level"], record["position"])
    else:
        assert selected is None


def test_a08_the_idaes_qualification_records_p0s_reproduction_and_the_pilots() -> None:
    """A08 (iv): `qualification/idaes.json` supersedes `6d9486a0`, records the P0 reproduction
    (§18.8 step 5) and `pilot_runs` (§18.2)."""
    qualification = load(QUALIFICATION / "idaes.json")
    assert qualification["supersedes"] == "6d9486a0"
    p0 = qualification["p0_reproduction"]
    assert p0["all_reproduced"] is True
    assert p0["attempts_compared"] == p0["attempts_reproduced"] == 20
    assert isinstance(qualification["pilot_runs"], list) and qualification["pilot_runs"]


# -- A09 -------------------------------------------------------------------------------------------


def test_a09_the_qualification_commits_precede_the_comparison() -> None:
    """A09: every qualification commit (DWSIM `95870140` and the top-up, IDAES WO-S03-2b's) is an
    ancestor of the commit that holds `comparison.json` (HEAD while it is uncommitted)."""
    commits = [c for cs in comparison.QUALIFICATION_COMMITS.values() for c in cs]
    require_history(*commits)
    status = git("status", "--porcelain", "--", str(comparison.TABLE.relative_to(REPO_ROOT)))
    holder = "HEAD" if status.stdout.strip() else record_commit(comparison.TABLE)
    for commit in commits:
        assert git("merge-base", "--is-ancestor", commit, holder).returncode == 0, commit
        assert commit != git("rev-parse", holder).stdout.strip()


# -- A10 -------------------------------------------------------------------------------------------


def test_a10_the_comparison_recomputes_identically_from_the_committed_files() -> None:
    """A10 (i) (§19.1): `comparison.json` and `SHA256SUMS` are what the classifier computes from the
    committed records, byte for byte."""
    assert comparison.TABLE.read_text(encoding="utf-8") == comparison.dumps(comparison.compute())
    assert comparison.SUMS.read_text(encoding="utf-8") == comparison.sums_text()


@pytest.fixture(scope="module")
def live_ours() -> dict[str, dict[str, Any] | None]:
    solved = {cid: ours_side.solve(cid) for cid in ours_side.OURS_CASES}
    return {cid: solved[comparison.OURS_ALIASES.get(cid, cid)] for cid in CASE_IDS}


def classifications(document: dict[str, Any]) -> dict[str, Any]:
    """§19.1 A10 (ii): the part of the document that a live solve must reproduce exactly.

    Every pair's classification, category, rule and label; every per-quantity `within_tolerance`
    and `quantities_outside`; the `controls` block and `comparison_stopped`; and under `x31` every
    pair class, case row, case outcome and clause outcome. Floats that depend on our values (ratios,
    responses, worst ratios, the rule 4 `reason` that prints one) are conditioned beyond 1e12 with
    respect to our values and are left out: A07 pins our values to 1e-12 relative, and A10 (i) pins
    the document as a function of them.
    """

    def pair(row: dict[str, Any]) -> dict[str, Any]:
        quantities = row.get("quantities")
        return {
            "classification": row["classification"],
            "category": row["category"],
            "rule": row["rule"],
            "label": row["label"],
            "quantities_outside": row.get("quantities_outside"),
            "within_tolerance": None
            if quantities is None
            else {q["quantity"]: q["within_tolerance"] for q in quantities},
        }

    def x31_case(case: dict[str, Any]) -> dict[str, Any]:
        return {
            "row": case["row"],
            "outcome": case["outcome"],
            "pairs": {tool: p["class"] for tool, p in case["pairs"].items()},
        }

    x31 = document["x31"]
    return {
        "rows": {(row["case"], row["tool"]): pair(row) for row in document["rows"]},
        "controls": document["controls"],
        "comparison_stopped": document["comparison_stopped"],
        "x31": {
            "cases": {cid: x31_case(case) for cid, case in x31["cases"].items()},
            "inverse_kinds": {kind: x31_case(case) for kind, case in x31["inverse_kinds"].items()},
            "clause": x31["clause"],
        },
    }


def test_a10_the_comparison_recomputes_from_a_live_solve_of_our_side(
    table: dict[str, Any], live_ours: dict[str, Any]
) -> None:
    """A10 (ii) (§19.1): recomputed from the committed tool records, the twin and a live solve of
    our side, every classification equals `comparison.json`'s exactly."""
    live = json.loads(comparison.dumps(comparison.compute(ours=live_ours)))
    expected = classifications(table)
    assert len(expected["rows"]) == len(table["rows"]) == len(live["rows"])
    assert classifications(live) == expected


# -- A11 -------------------------------------------------------------------------------------------


def test_a11_no_control_agrees_and_each_tool_has_a_working_control(table: dict[str, Any]) -> None:
    """A11 (i), (iii): no control classifies `AGREE`; (PC-L, IDAES) and (PC-LI, DWSIM) are
    `not_applicable`; the committed classification has a `DISAGREE` control for each tool, so
    its pairs count (§17.3(b), §18.3)."""
    by = rows(table)
    for tool in TOOLS:
        for control in comparison.control_cases(CASES, tool):
            assert by[control, tool]["classification"] != "AGREE"
        assert table["controls"]["per_tool"][tool]["pairs_count"] is True
    assert by["PC-L", "IDAES"]["label"] == "not_applicable"
    assert by["PC-LI", "DWSIM"]["label"] == "not_applicable"
    assert by["PC-L", "DWSIM"]["classification"] == "DISAGREE"
    assert by["PC-LI", "IDAES"]["classification"] == "DISAGREE"
    assert table["comparison_stopped"] is False
    assert not any(r.get("rule") == "17.3(b)" for r in table["rows"])


def not_available_copy(record: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(record)
    out["available"] = False
    out["not_available_reason"] = "A11 mutation: a NOT_COMPARABLE copy"
    return out


@pytest.mark.parametrize("tool", TOOLS)
def test_a11_without_a_disagreeing_control_every_pair_of_the_tool_is_lost(
    tool: str, records: dict[tuple[str, str], Any], table: dict[str, Any]
) -> None:
    """A11 (ii) by mutation: with every control of the tool replaced by a `NOT_COMPARABLE` copy,
    each of its pairs that reached rule 2 becomes `NOT_COMPARABLE(control_not_comparable: …)`;
    the other tool's pairs and the tool's rule 0 pairs do not change."""
    mutated = dict(records)
    for control in comparison.control_cases(CASES, tool):
        if mutated[tool, control] is not None and mutated[tool, control].get("available"):
            mutated[tool, control] = not_available_copy(mutated[tool, control])
    document = comparison.compute(records=mutated)
    before, after = rows(table), rows(document)
    controls = set(comparison.control_cases(CASES, tool))
    changed = 0
    for key, row in after.items():
        old = before[key]
        if key[1] != tool or key[0] in controls:
            if key[0] not in controls:
                assert row["label"] == old["label"], key
            continue
        if old["rule"] in (2, "2b", "2c", "2d", 4):
            assert row["category"] == "control_not_comparable", key
            assert row["label"].startswith("NOT_COMPARABLE(control_not_comparable: "), key
            changed += 1
        else:
            assert row["label"] == old["label"], key
    assert changed > 0
    assert document["controls"]["per_tool"][tool]["pairs_count"] is False


def test_a11_one_disagreeing_control_is_enough_for_idaes() -> None:
    """A11 (ii): replacing one IDAES control by a `NOT_COMPARABLE` copy while the other is
    `DISAGREE` changes no IDAES pair, either way round. PC-P is not `DISAGREE` in the committed
    classification, so the rows are synthetic (§18.7 A11 (ii))."""
    ours = comparison.load_ours(cases=CASES)
    base = [
        comparison.classify(cid, tool, tool_record(tool, cid), ours[cid], CASES, REF)
        for cid, tool in PAIRS
    ]
    for working, lost in (("PC-LI", "PC-P"), ("PC-P", "PC-LI")):
        synthetic = copy.deepcopy(base)
        for r in synthetic:
            if r["tool"] != "IDAES":
                continue
            if r["case"] == working:
                r.update(classification="DISAGREE", category=None, rule=4, label="DISAGREE")
            elif r["case"] == lost:
                r.update(
                    classification="NOT_COMPARABLE",
                    category="capability",
                    rule=0,
                    label="NOT_COMPARABLE(capability: synthetic)",
                )
        reference = copy.deepcopy(synthetic)
        summary = comparison.apply_controls(synthetic, CASES)
        assert summary["per_tool"]["IDAES"]["pairs_count"] is True
        assert synthetic == reference


def test_a11_dwsim_pc_p_is_as_recorded_and_moves_no_other_pair(
    records: dict[tuple[str, str], Any], table: dict[str, Any]
) -> None:
    """A11 (iv): (PC-P, DWSIM) is rule 0 as recorded; giving it another `NOT_COMPARABLE` reason
    (access) changes no other DWSIM pair."""
    by = rows(table)
    assert by["PC-P", "DWSIM"]["rule"] == 0
    assert by["PC-P", "DWSIM"]["category"] == "capability"
    mutated = dict(records)
    pcp = copy.deepcopy(records["DWSIM", "PC-P"])
    pcp["available"] = True
    pcp["level"] = "L1"
    pcp["settings_used"] = {"column_tolerance": 1e-8, "method": "Wang-Henke"}
    pcp["environment_fingerprint"]["measured"] = {"changed": "A11 (iv) mutation"}
    mutated["DWSIM", "PC-P"] = pcp
    after = rows(comparison.compute(records=mutated))
    assert after["PC-P", "DWSIM"]["category"] == "access"
    for key, row in after.items():
        if key != ("PC-P", "DWSIM"):
            assert row["label"] == by[key]["label"], key


# -- A12 -------------------------------------------------------------------------------------------


def available_rc1(tool: str) -> dict[str, Any]:
    record = tool_record(tool, "RC1")
    assert record is not None and record["available"], f"{tool} RC1 is not available"
    return record


def alter_l1(record: dict[str, Any], factor: float) -> None:
    raw = record["raw_output"]
    if record["tool"] == "DWSIM":
        raw["profile"]["L_mol_per_s"][0] *= factor
    else:
        raw["stages"]["1"]["L_mol_per_s"] *= factor


def alter_pressure(record: dict[str, Any], j: int, delta: float) -> None:
    raw = record["raw_output"]
    if record["tool"] == "DWSIM":
        raw["profile"]["P_Pa"][j - 1] += delta
    else:
        raw["stages"][str(j)]["P_Pa"] += delta


def classify_rc1(record: dict[str, Any]) -> dict[str, Any]:
    ours = load(RESULTS / "ours-RC1.json")
    return comparison.classify("RC1", record["tool"], record, ours, CASES, REF)


@pytest.mark.parametrize("tool", TOOLS)
def test_a12_rules_2c_and_2d_fire_on_the_rc1_record(tool: str) -> None:
    """A12: on the tool's committed RC1 record, copies altered in exactly one raw field:
    `L[1]` × (1 + 2e-4) → 2c (RR's definition); × (1 + 2e-8) → 2d (the residual); a stage
    pressure + 0.01 Pa → 2c; an accuracy-rerun quantity moved by 0.2 tolerance → 2d. The
    unaltered record classifies by rule 4."""
    record = available_rc1(tool)
    assert classify_rc1(record)["rule"] == 4

    broken = copy.deepcopy(record)
    alter_l1(broken, 1 + 2e-4)
    row = classify_rc1(broken)
    assert (row["rule"], row["category"]) == ("2c", "semantics"), row["label"]
    assert row["reason"].startswith("specification_condenser_reflux_ratio("), row["reason"]

    inaccurate = copy.deepcopy(record)
    alter_l1(inaccurate, 1 + 2e-8)
    row = classify_rc1(inaccurate)
    assert (row["rule"], row["category"]) == ("2d", "reference_accuracy"), row["label"]
    assert row["reason"].startswith("specification_residual_condenser_reflux_ratio("), row

    pressure = copy.deepcopy(record)
    alter_pressure(pressure, 4, 0.01)
    row = classify_rc1(pressure)
    assert (row["rule"], row["category"]) == ("2c", "semantics"), row["label"]
    assert row["reason"].startswith("pressure("), row["reason"]

    moved = copy.deepcopy(record)
    twin = REF["twin"]["RC1"]["quantities"]["T[4]"]
    tol = float(comparison.tolerance("T", Decimal(twin["value"])))
    moved["accuracy_rerun"]["quantities"]["T[4]"] = record["registered_quantities"]["T[4]"] + (
        0.2 * tol
    )
    row = classify_rc1(moved)
    assert (row["rule"], row["category"]) == ("2d", "reference_accuracy"), row["label"]
    assert row["reason"].startswith("rerun_movement("), row["reason"]


def test_a12_idaes_path_dependence_fires_at_two_tenths_not_at_five_hundredths() -> None:
    """A12 (§18.7): on each IDAES record with a selected attempt, a copy with one extra "Optimal"
    position equal to the selected attempt's quantities except one moved by 0.2 tolerance →
    rule 2d `path_dependence`; moved by 0.05 tolerance → not fired."""
    checked = 0
    for cid in CASE_IDS:
        record = tool_record("IDAES", cid)
        if record is None or not record.get("available"):
            continue
        case = CASES["cases"][cid]
        twin = comparison.twin_quantities(REF, cid)
        quantity, kind = case["quantities"][0]
        tol = float(comparison.tolerance(kind, Decimal(twin[quantity]["value"])))
        ours = load(RESULTS / f"ours-{comparison.OURS_ALIASES.get(cid, cid)}.json")
        assert comparison.classify(cid, "IDAES", record, ours, CASES, REF)["rule"] == 4
        for fraction, fires in ((0.2, True), (0.05, False)):
            extra = copy.deepcopy(record)
            raw = copy.deepcopy(record["raw_output"])
            j = int(quantity[2:-1])
            raw["stages"][str(j)]["T_K"] += fraction * tol
            level = extra["levels"][extra["level"]]
            level["positions"]["PX"] = {
                "summary": {"position": "PX", "termination": comparison.IPOPT_OPTIMAL},
                "full": {
                    "record": {
                        "ipopt": {"exit": comparison.IPOPT_OPTIMAL},
                        "termination": comparison.IPOPT_OPTIMAL,
                        "solves": [{"termination": comparison.IPOPT_OPTIMAL}],
                    },
                    "raw": raw,
                },
            }
            row = comparison.classify(cid, "IDAES", extra, ours, CASES, REF)
            if fires:
                assert row["rule"] == "2d", (cid, row["label"])
                assert row["reason"].startswith("path_dependence("), row["reason"]
            else:
                assert row["rule"] == 4, (cid, row["label"])
        checked += 1
    assert checked > 0


def synthetic_view(case: dict[str, Any], got: Decimal) -> dict[str, Any]:
    """A raw-field view whose specified end (the case's only specification) computes to `got`."""
    n = int(case["stage_count"])
    spec = next(iter(case["specifications"].values()))
    end = next(iter(case["specifications"]))
    kind = spec["kind"]
    comps = ("A", "B", "C")
    top = {
        "flow": Decimal("0.4"),
        "comp": {"A": Decimal("0.3"), "B": Decimal("0.09"), "C": Decimal("0.01")},
    }
    bottom = {
        "flow": Decimal("0.6"),
        "comp": {"A": Decimal("0.0"), "B": Decimal("0.31"), "C": Decimal("0.29")},
    }
    v: dict[str, Any] = {
        "n": n,
        "T": [340.0] * n,
        "L": [1.0] * n,
        "V": [1.0] * n,
        "top": top,
        "bottom": bottom,
        "inlet_comps": [{"A": Decimal("0.3"), "B": Decimal("0.4"), "C": Decimal("0.3")}],
        "duties": {"Q_condenser": Decimal(-1), "Q_reboiler": Decimal(1)},
    }
    product = top if end == "condenser" else bottom
    if kind == "reflux_ratio":
        v["L"][0] = float(got * (top["flow"] if case["condenser"] == "total" else Decimal(1)))
    elif kind == "boilup_ratio":
        v["V"][n - 1] = float(got)
    elif kind == "distillate_rate":
        top["flow"] = got
    elif kind == "bottoms_rate":
        bottom["flow"] = got
    elif kind == "duty":
        v["duties"]["Q_reboiler" if end == "reboiler" else "Q_condenser"] = got
    elif kind == "purity":
        product["comp"][spec["component"]] = got * product["flow"]
    elif kind == "recovery":
        product["comp"][spec["component"]] = got * v["inlet_comps"][0][spec["component"]]
    elif kind == "temperature":
        v["T"][int(spec["stage"]) - 1] = float(got)
    assert set(top["comp"]) == set(comps)
    return v


#: §17.9 A12's kinds: (case template, end, specification).
SPEC_KINDS = {
    "RR partial": ("RC1", "condenser", {"kind": "reflux_ratio", "value": "2"}),
    "RR total": ("RC2", "condenser", {"kind": "reflux_ratio", "value": "1.5"}),
    "BR": ("RC1", "reboiler", {"kind": "boilup_ratio", "value": "1.5"}),
    "D partial": ("RC4", "condenser", {"kind": "distillate_rate", "value": "0.5"}),
    "D total": ("RC2", "condenser", {"kind": "distillate_rate", "value": "0.45"}),
    "B": ("RC2", "reboiler", {"kind": "bottoms_rate", "value": "0.55"}),
    "duty": ("RC3", "reboiler", {"kind": "duty", "value": "30000"}),
    "purity": ("RC5", "condenser", {"kind": "purity", "value": "0.85", "component": "A"}),
    "recovery": ("RC6", "reboiler", {"kind": "recovery", "value": "0.99", "component": "C"}),
    "temperature": ("RC7", "reboiler", {"kind": "temperature", "value": "368", "stage": 6}),
}


@pytest.mark.parametrize("name", list(SPEC_KINDS))
def test_a12_each_specification_kind_meets_its_thresholds(name: str) -> None:
    """A12 (§17.9): one synthetic record per specification kind, its residual at 2× rule 2c's
    threshold (1e-4 relative) → 2c; at 2× the kind's rule 2d threshold (§17.4) → 2d; at 0.5×
    → neither."""
    template, end, spec = SPEC_KINDS[name]
    case = copy.deepcopy(CASES["cases"][template])
    case["specifications"] = {end: spec}
    registered = Decimal(spec["value"])
    threshold, basis = comparison.RULE2D_SPEC[spec["kind"]]

    def at(residual: Decimal, relative: bool) -> dict[str, Any]:
        got = registered * (1 + residual) if relative else registered + residual
        return comparison.specification_values(synthetic_view(case, got), case)[end]

    two_c = at(2 * comparison.RULE2C_SPEC_RELATIVE, True)
    assert not two_c["rule2c_passes"]
    two_d = at(2 * threshold, basis == "relative")
    assert two_d["rule2c_passes"] and not two_d["rule2d_passes"], two_d
    neither = at(threshold / 2, basis == "relative")
    assert neither["rule2c_passes"] and neither["rule2d_passes"], neither


# -- A13 -------------------------------------------------------------------------------------------


def test_a13_the_document_is_complete(table: dict[str, Any]) -> None:
    """A13: every registered pair is present once; every `NOT_COMPARABLE` and `DISAGREE` carries
    its reason; the X31 count and §17.5's table for RC1–RC4 and per inverse kind; §7.4's response
    table; each control's tool-model distance; each IDAES pair's (level, position) and each IDAES
    record's largest path-dependence ratio."""
    by = rows(table)
    assert sorted(by) == sorted(PAIRS) and len(table["rows"]) == len(PAIRS)
    for r in table["rows"]:
        assert r["label"] and r["reason"], (r["case"], r["tool"])
        if r["classification"] == "DISAGREE":
            assert r["quantities"] and r["quantities_outside"] > 0
        if r["classification"] == "NOT_COMPARABLE":
            assert r["category"] in {
                "capability",
                "access",
                "reference_accuracy",
                "semantics",
                "ours_not_verified",
                "control_not_comparable",
            }
    x31 = table["x31"]
    assert list(x31["cases"]) == list(comparison.X31_CASES)
    assert x31["cases_with_two_references"] == sum(
        1 for c in comparison.X31_CASES if x31["cases"][c]["row"] == 5
    )
    assert x31["clause"] in {"met with two references", "met where available", "not met", "blocked"}
    for entry in [*x31["cases"].values(), *x31["inverse_kinds"].values()]:
        assert 1 <= entry["row"] <= 7 and entry["outcome"]
        assert set(entry["pairs"]) == set(TOOLS)
        for pair in entry["pairs"].values():
            assert pair["class"] in {"comparable", "absent", "unusable", "access", "ours"}
    assert {v["case"] for v in x31["inverse_kinds"].values()} == {"RC5", "RC6", "RC7"}
    assert set(table["perturbation_response"]) == set(REF["perturbations"])
    for pert, entry in table["perturbation_response"].items():
        names = [q["quantity"] for q in entry["quantities"]]
        assert names == [q for q, _ in CASES["cases"][pert]["quantities"]]
    distances = table["control_tool_model_distance"]
    for cid in REF["controls"]:
        for tool in TOOLS:
            if CASES["cases"][cid]["tool_variant"][tool] != "not_applicable":
                assert f"{cid}/{tool}" in distances
    for cid in CASE_IDS:
        r = by[cid, "IDAES"]
        record = tool_record("IDAES", cid)
        if record is not None and record.get("available"):
            assert (r["level"], r["position"]) == (record["level"], record["position"])
            assert cid in table["idaes_path_dependence"]
            assert table["idaes_path_dependence"][cid]["max_ratio"] <= 0.1


def test_a13_each_working_control_is_carried_by_its_effect(table: dict[str, Any]) -> None:
    """§7.3: a `DISAGREE` control's tool sits within one tolerance of the tool-model twin, so the
    `DISAGREE` came from the effect the control exists to show."""
    for key, entry in table["control_tool_model_distance"].items():
        cid, tool = key.split("/")
        if rows(table)[cid, tool]["classification"] == "DISAGREE":
            assert entry["max_ratio"] is not None and entry["max_ratio"] <= 1.0, key


# -- A14 -------------------------------------------------------------------------------------------


@pytest.mark.parametrize("cid", [c for c in CASE_IDS if c in REF["twin"]] + ["PC-P", "PC-L"])
def test_a14_the_tolerance_is_section_6s_formula_unrounded(cid: str) -> None:
    """A14: rule 4 decides on `a_k + 1e-6 |v|` from `ref`'s 25-digit values with no per-case or
    per-tool factor: a synthetic pair at 0.999 tolerance agrees and at 1.001 disagrees, for every
    quantity of every case; the formula equals `ref`'s rounded tolerance string to 1e-24."""
    case = CASES["cases"][cid]
    twin = comparison.twin_quantities(REF, cid)
    kinds = dict(case["quantities"])
    for q, kind in case["quantities"]:
        value = Decimal(twin[q]["value"])
        tol = comparison.tolerance(kind, value)
        assert abs(tol - Decimal(twin[q]["tolerance"])) <= Decimal("1e-24") * tol, q
        ours = float(value)
        for factor, word in ((Decimal("0.999"), "AGREE"), (Decimal("1.001"), "DISAGREE")):
            tool = float(Decimal(repr(ours)) + factor * tol)
            got, _ = comparison.rule4({q: tool}, {q: ours}, twin, kinds)
            assert got == word, (cid, q, factor)
