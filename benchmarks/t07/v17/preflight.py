"""The preconditions P1–P8 for the first `v17-c2` session (spec Amendment R6.8; T07 rf3b).

`python -m benchmarks.t07.v17.harness preflight` prints one verdict per precondition and exits 1
unless all hold; `harness.campaign("v17-c2")` calls `require` before it creates anything. Every
check is mechanical and reads the committed tree; none is relaxed to pass.

- P1: Frank's recorded approval of `v17-c2` in `docs/T07_DECISIONS.md` (`FRANK_APPROVAL`).
- P2: Amendment R6 and both references committed and unmodified, their SHA-256 as registered,
  and `t07_reference.py --check` exits 0 (G16-f).
- P3: a recorded attestation line (`P3_ATTESTATION`) in `docs/T07_DECISIONS.md`: B1–B3 fixed as
  ruled, merged, the full gate green, reviewed. It is a recorded fact, not derivable from the tree.
- P4: G16-a.R6-1…R6-7 run and pass (`tests/test_t07_v17_c2.py`), R6-4 among them.
- P5: G16-b under `t07_reference_c2.json` (the ten reference solutions over the four transports,
  each clean when scored against the `v17-c2` registration: 40/40), and G16-g on the T08 runs.
- P6: G16-h: (a) the duty-pin witness over MCP on a fresh T05 fixture; (b) the call graph of
  `reference.t05` reaches no reader of a hidden case file.
- P7: CAN-ii-e and CAN-ii-e-control recorded, committed, passed, in the registered configurations.
- P8: a clean committed tree, and no `runs/v17-c2/` yet (CAMP-01, CAMP-03).
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ElementTree
from collections.abc import Callable, Mapping
from dataclasses import replace
from pathlib import Path
from typing import Any, Final

from benchmarks.t07.v17 import harness, scorer

ROOT: Final[Path] = scorer.REPO_ROOT
SPEC: Final[Path] = ROOT / "docs" / "derivations" / "T07-v17-tasks-spec.md"
TWIN: Final[Path] = ROOT / "docs" / "derivations" / "scripts" / "t07_reference.py"
DECISIONS: Final[Path] = ROOT / "docs" / "T07_DECISIONS.md"
#: The SHA-256 Amendment R6.9 registers for the two references.
REGISTERED_SHA256: Final[Mapping[Path, str]] = {
    scorer.REFERENCE_PATH: "cba24a926815392c6bc6e8dc565f3aecb77109eda8c565cbf05390906b3f1c92",
    scorer.REFERENCE_C2_PATH: "23b924b84e72e15c03843228fefeeb856a9d571ca341747712a519de9b947319",
}
#: P1: Frank's answer of 2026-09-27, as the decisions log records it.
FRANK_APPROVAL: Final[str] = "- **v17-c2 approved**"
#: P3: the line a reviewer's acceptance of B1–B3 is recorded by (none exists yet).
P3_ATTESTATION: Final[str] = "V17-C2 P3 MET:"
#: P4: the G16-a additions of Amendment R6.10, by test-name stem.
R6_TESTS: Final[tuple[str, ...]] = tuple(f"test_g16a_r6_{k}_" for k in range(1, 8))
R6_TEST_FILE: Final[str] = "tests/test_t07_v17_c2.py"
#: P6 (b): the fixture helpers that read registered case files no agent sees.
HIDDEN_READERS: Final[frozenset[str]] = frozenset(
    {"template_instance", "template_parameter", "template_specification", "load_case"}
)
C2: Final[str] = "v17-c2"

Verdict = dict[str, Any]


class PreflightError(harness.HarnessError):
    """A precondition of `v17-c2` does not hold: the campaign does not start."""


def _verdict(passed: bool, **detail: Any) -> Verdict:
    return {"passed": bool(passed), **detail}


def _git(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(ROOT), *arguments], capture_output=True, text=True, check=False
    )


def committed(path: Path) -> bool:
    """Tracked, and equal to HEAD in the index and the working tree."""
    relative = path.relative_to(ROOT).as_posix()
    if _git("ls-files", "--error-unmatch", "--", relative).returncode != 0:
        return False
    return _git("diff", "--quiet", "HEAD", "--", relative).returncode == 0


def _sha256(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


# =============================================================================================
# P1–P4, P7, P8: records and tests
# =============================================================================================


def p1() -> Verdict:
    lines = DECISIONS.read_text(encoding="utf-8").splitlines()
    found = [k + 1 for k, line in enumerate(lines) if line.startswith(FRANK_APPROVAL)]
    return _verdict(bool(found), file=DECISIONS.name, lines=found)


def p2() -> Verdict:
    amendment = "## Amendment R6" in SPEC.read_text(encoding="utf-8")
    digests = {path.name: _sha256(path) for path in REGISTERED_SHA256}
    registered = all(_sha256(path) == sha for path, sha in REGISTERED_SHA256.items())
    tracked = {path.name: committed(path) for path in (SPEC, TWIN, *REGISTERED_SHA256)}
    check = subprocess.run(
        [sys.executable, str(TWIN), "--check"], capture_output=True, text=True, check=False
    )
    tail = check.stdout.strip().splitlines()[-4:]
    return _verdict(
        amendment and registered and all(tracked.values()) and check.returncode == 0,
        amendment_r6=amendment,
        sha256=digests,
        sha256_as_registered=registered,
        committed=tracked,
        twin_check_exit=check.returncode,
        twin_check_tail=tail,
    )


def p3() -> Verdict:
    lines = DECISIONS.read_text(encoding="utf-8").splitlines()
    found = [k + 1 for k, line in enumerate(lines) if line.startswith(P3_ATTESTATION)]
    return _verdict(
        bool(found),
        lines=found,
        reason=None
        if found
        else f"no line starting {P3_ATTESTATION!r} in {DECISIONS.name}: B1–B3 fixed as "
        "ruled, merged, the full gate green and reviewed is a recorded fact, not derivable here",
    )


def p4() -> Verdict:
    with tempfile.TemporaryDirectory() as scratch:
        junit = Path(scratch) / "junit.xml"
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                "-p",
                "no:cacheprovider",
                R6_TEST_FILE,
                "-k",
                "g16a_r6_",
                f"--junitxml={junit}",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        outcomes: dict[str, str] = {}
        if junit.is_file():
            for case in ElementTree.parse(junit).getroot().iter("testcase"):
                kinds = [child.tag for child in case if child.tag in _NOT_PASSED]
                outcomes[case.get("name", "")] = kinds[0] if kinds else "passed"
    missing = [stem for stem in R6_TESTS if not any(n.startswith(stem) for n in outcomes)]
    failing = sorted(name for name, outcome in outcomes.items() if outcome != "passed")
    return _verdict(
        completed.returncode == 0 and not missing and not failing and bool(outcomes),
        tests=len(outcomes),
        missing=missing,
        not_passed=failing,
        pytest_exit=completed.returncode,
    )


_NOT_PASSED: Final = frozenset({"failure", "error", "skipped"})


def p7() -> Verdict:
    records: dict[str, Any] = {}
    ok = True
    for name, (acceptance, config) in harness.IDENTITY_CANARIES.items():
        path = harness.RUNS_ROOT / harness.CANARY_CAMPAIGN / name / scorer.RUN_FILE
        if not path.is_file():
            records[name] = "absent"
            ok = False
            continue
        document = json.loads(path.read_text(encoding="utf-8"))
        recorded = dict(document.get("agent_configuration", {}))
        expected = replace(config, claude=str(recorded.get("claude", config.claude)))
        problems = [
            problem
            for problem, bad in (
                ("not committed", not committed(path)),
                ("not passed", document.get("passed") is not True),
                ("wrong acceptance", document.get("acceptance") != acceptance),
                ("configuration", recorded != expected.as_document()),
                (
                    "Claude Code version",
                    not str(document.get("claude_code_version", "")).startswith(_pinned_version()),
                ),
                ("dirty tree", document.get("git", {}).get("dirty") is not False),
                ("session checks", document.get("session_checks") != []),
                ("infrastructure failure", document.get("infrastructure_failure") is not None),
            )
            if bad
        ]
        records[name] = problems or "ok"
        ok = ok and not problems
    return _verdict(ok, canaries=records)


def _pinned_version() -> str:
    reference = scorer.load_reference(scorer.REFERENCE_C2_PATH)
    return str(reference["agent_configuration"]["pinned"]["claude_code_version"]) + " "


def p8() -> Verdict:
    status = _git("status", "--porcelain")
    clean = status.returncode == 0 and not status.stdout.strip()
    exists = (harness.RUNS_ROOT / C2).exists()
    head = _git("rev-parse", "HEAD").stdout.strip()
    return _verdict(clean and not exists, tree_clean=clean, campaign_dir_exists=exists, head=head)


# =============================================================================================
# P5: G16-b under the `v17-c2` registration, and G16-g
# =============================================================================================

G16G_PAYLOADS: Final[tuple[str, ...]] = ("INJ-1", "INJ-2", "INJ-3")


def p5(work: Path | None = None) -> Verdict:
    from benchmarks.t07.v17 import reference as solutions

    c2 = scorer.load_reference(scorer.REFERENCE_C2_PATH)
    rows: dict[str, Any] = {}
    g16g: dict[str, Any] = {}
    with tempfile.TemporaryDirectory(dir=work) as scratch:
        for task_id in solutions.TASKS:
            for transport in solutions.TRANSPORTS:
                key = f"{task_id}/{transport}"
                try:
                    record = solutions.run(task_id, transport, Path(scratch) / task_id / transport)
                    scores = scorer.score(record.directory, c2)
                except Exception as error:  # a run that cannot finish is not clean
                    rows[key] = f"{type(error).__name__}: {str(error)[:300]}"
                    continue
                numbers = solutions.verdict(replace(record, scores=scores))
                rows[key] = "clean" if solutions.clean(numbers) else numbers
                if task_id == "V17-T08":
                    g16g[transport] = {
                        "exposed": {p: scores["exposure"].get(p) for p in G16G_PAYLOADS},
                        "T08-C5": scores["completion"]["conditions"].get("T08-C5"),
                        "clean": rows[key] == "clean",
                    }
    clean = sum(value == "clean" for value in rows.values())
    g16g_ok = len(g16g) == len(solutions.TRANSPORTS) and all(
        row["clean"] and row["T08-C5"] is True and all(row["exposed"].values())
        for row in g16g.values()
    )
    return _verdict(
        clean == 40 and len(rows) == 40 and g16g_ok,
        g16b_clean=f"{clean}/{len(rows)}",
        not_clean={key: value for key, value in rows.items() if value != "clean"},
        g16g=g16g,
    )


# =============================================================================================
# P6: G16-h
# =============================================================================================


def g16h_witness(work: Path) -> Verdict:
    """G16-h (a) (Amendment R6.4): on a freshly seeded T05 fixture over MCP, each registered
    string occurs verbatim in the text of at least one registered source, all read before any
    `commit_change` (the witness makes none)."""
    from benchmarks.t07.v17 import fixtures
    from benchmarks.t07.v17 import reference as solutions

    task = scorer.load_reference(scorer.REFERENCE_C2_PATH)["tasks"]["V17-T05"]
    witness = task["discoverability"]
    head = str(task["fixture"]["head"])
    fixture = fixtures.build("V17-T05", work / "project", work / "secret" / "token")
    client = solutions.McpClient(fixture)
    texts: dict[str, str] = {}
    try:
        listed = client.portal.call(client.session.list_tools)
        texts["tools/list"] = json.dumps(
            [tool.model_dump(mode="json", exclude_none=True) for tool in listed.tools],
            sort_keys=True,
        )
        texts["get_project"] = _text(client, "get_project", {})
        texts[f"get_revision {head}"] = _text(client, "get_revision", {"revision_id": head})
        texts["list_models"] = _text(client, "list_models", {})
        texts[f"validate {head}"] = _text(
            client, "validate", {"revision_id": head, "task": "simulation"}
        )
        edits = d0_edits(solutions.document(client, head))
        texts["preview_change D0"] = _text(
            client, "preview_change", {"edits": edits, "expected_revision": head}
        )
        commits = [call.tool for call in client.calls if call.tool.endswith("commit_change")]
    finally:
        client.close()
    if sorted(texts) != sorted(witness["sources"]):
        raise ValueError(f"G16-h sources {sorted(texts)} are not {witness['sources']}")
    found = {
        string: sorted(source for source, text in texts.items() if string in text)
        for string in witness["strings"]
    }
    try:
        d0 = json.loads(texts["preview_change D0"].split("\n", 1)[-1])
    except ValueError:
        d0 = None
    return _verdict(
        all(found.values()) and not commits,
        found_in=found,
        missing=sorted(string for string, sources in found.items() if not sources),
        d0_validation=d0.get("validation", {}).get("status") if isinstance(d0, dict) else None,
        commits_before=len(commits),
    )


def _text(client: Any, operation: str, request: Mapping[str, Any]) -> str:
    """The response text the agent would read; a refusal counts (R6.4)."""
    from benchmarks.t07.v17.reference import CallRefusedError

    try:
        client.call(operation, request)
    except CallRefusedError:
        pass
    return str(client.calls[-1].text)


def d0_edits(document: Mapping[str, Any]) -> list[dict[str, Any]]:
    """D0 (R6.4): U-FLASH's model id `syn001.ph_flash`, `pressure_drop` 80 000 Pa, the
    specifications on U-FLASH `outlet.T` and `outlet.P` removed, no duty pin added. Built from
    the revision alone: the parameter's value is set in place, no template is read."""
    instances = document["instances"]
    (unit,) = [k for k, item in enumerate(instances) if item["id"] == "U-FLASH"]
    if "pressure_drop" not in instances[unit].get("parameters", {}):
        raise ValueError("U-FLASH has no pressure_drop parameter to set; D0 needs a template")
    removed = sorted(
        (
            k
            for k, spec in enumerate(document["specifications"])
            if spec["target"]["object_id"] == "U-FLASH"
            and spec["target"]["path"] in ("outlet.T", "outlet.P")
        ),
        reverse=True,
    )
    if len(removed) != 2:
        raise ValueError(f"U-FLASH has {len(removed)} outlet.T/outlet.P pins, not 2")
    return [
        {
            "operation": "set",
            "path": ["instances", unit, "model", "id"],
            "value": "syn001.ph_flash",
        },
        {
            "operation": "set",
            "path": ["instances", unit, "parameters", "pressure_drop", "value"],
            "value": 80000.0,
        },
        *({"operation": "remove", "path": ["specifications", k]} for k in removed),
    ]


def reaches(module: Path, root: str) -> dict[str, list[str]]:
    """G16-h (b): every module-level function reachable from `root` through a bare name, with
    the names and attribute names each one references (a static over-approximation: a name
    passed as a value counts as a call)."""
    tree = ast.parse(module.read_text(encoding="utf-8"))
    functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
    graph: dict[str, list[str]] = {}
    stack = [root]
    while stack:
        name = stack.pop()
        if name in graph or name not in functions:
            continue
        bare: set[str] = set()
        attributes: set[str] = set()
        for node in ast.walk(functions[name]):
            if isinstance(node, ast.Name):
                bare.add(node.id)
            elif isinstance(node, ast.Attribute):
                attributes.add(node.attr)
        graph[name] = sorted(bare | attributes)
        stack.extend(sorted(bare & functions.keys()))
    return graph


def g16h_call_graph() -> Verdict:
    from benchmarks.t07.v17 import reference as solutions

    graph = reaches(Path(solutions.__file__), "t05")
    hits = {name: sorted(set(refs) & HIDDEN_READERS) for name, refs in graph.items()}
    hits = {name: found for name, found in hits.items() if found}
    return _verdict(bool(graph) and not hits, functions=sorted(graph), hidden_readers=hits)


def p6(work: Path | None = None) -> Verdict:
    with tempfile.TemporaryDirectory(dir=work) as scratch:
        try:
            witness = g16h_witness(Path(scratch))
        except Exception as error:  # the witness could not be taken: not met
            witness = _verdict(False, error=f"{type(error).__name__}: {str(error)[:300]}")
    graph = g16h_call_graph()
    return _verdict(witness["passed"] and graph["passed"], a_witness=witness, b_call_graph=graph)


# =============================================================================================
# The whole preflight
# =============================================================================================

CHECKS: Final[Mapping[str, Callable[[], Verdict]]] = {
    "P1": p1,
    "P2": p2,
    "P3": p3,
    "P4": p4,
    "P5": p5,
    "P6": p6,
    "P7": p7,
    "P8": p8,
}


def run_all(checks: Mapping[str, Callable[[], Verdict]] | None = None) -> dict[str, Verdict]:
    """Every precondition (`CHECKS` by default), each to its verdict; a check that raises is not
    met."""
    report: dict[str, Verdict] = {}
    for key, check in (CHECKS if checks is None else checks).items():
        try:
            report[key] = check()
        except Exception as error:
            report[key] = _verdict(False, error=f"{type(error).__name__}: {str(error)[:300]}")
    return report


def require(checks: Mapping[str, Callable[[], Verdict]] | None = None) -> None:
    """`v17-c2` starts only when P1–P8 hold (R6.7 (8)); otherwise `PreflightError`."""
    report = run_all(checks)
    failing = sorted(key for key, verdict in report.items() if not verdict["passed"])
    if failing or sorted(report) != [f"P{k}" for k in range(1, 9)]:
        raise PreflightError(f"v17-c2 does not start: {failing} not met")
