"""Generate `evidence/S12/<commit>/manifest.json` (package E01) by running, not by transcribing.

E01 (WO-I1). The manifest is filed as package `S12`, E01's alias: the frozen manifest schema admits
only `^[PKTMSR][0-9]{2}[a-z]?$` (orchestrator ruling on ESC-I2, 2026-10-29; R-565's precedent,
L01 → S04). The check list is the design note `docs/derivations/E01-design.md`: §6.1's E01.A1–A42
with §9.6's A43–A48, §6.2's gates G1–G9 with §9.6's additions and G10. Everything recorded is
produced here, at the checked-out commit (the script refuses to run when `HEAD` is not `--commit`
or when a tracked source, test, script, schema or derivation file differs from it; S01's rule):

1. **The tests**, in three environments (`pytest --junitxml`): run A in the locked environment over
   `tests/test_e01_*.py` and the tests E01 amends or names (§8.3; A43's M04, M02 and ADR 0025
   tests; the T08 inventory, W4 package-data and S05 envelope tests; the identity tests); run L,
   the LCA files in the `lca` extra's environment (`--lca-python`, `scripts/build-lca-env.sh`),
   for A24 and A25, which skip without Brightway; run N, every `nlp`-marked test through
   `scripts/m03_nlp_check.sh` in the audited NLP environment (`--nlp-prefix`, `--nlp-cache`; its
   inventory re-takes included), for A33–A36 and M03's own NLP tests. A node's outcome is the
   worse over the runs that ran it (`failed`/`error` in any fails it; `passed` in any passes it).
   An E01 test cites the assertions its name starts with (`test_a30_a31_…`, `test_a4_…`); tests
   named otherwise cite through `CITATIONS`. `S12.Axx` passes only if at least one node cites it
   and every node citing it passed.
2. **G1**: A1, `git diff` over §4.14's protected paths against the S11 head `wp/E01` merged
   (`S11_HEAD`); A2, `scripts/s11_identity.py` against its `main` baseline
   (`S11-IDENTITY PASS n=‹N› changed=[]`; family C runs every `tests/test_*.py` in both trees).
3. **G9**: A3, `scripts/e01_m03_dump.py` in a detached worktree of `S11_HEAD` and in this tree, in
   the NLP environment, compared byte for byte, with `scripts/m03_schema_fixtures.py --nlp`
   against the committed fixtures and M03's NLP tests; A35 by its tests.
4. **The generators' `--check`s**: `t08_support_matrix.py`, `e01_d04_inventory.py` (A42),
   `e01_lca_data.py`, `t08_numerical_policy.py` (A43, v2's sha256 unchanged),
   `benchmarks/e01/cost_hand/cost_hand.py`, and `m03_schema_fixtures.py` (the default fixtures).
5. **`ruff check`, `ruff format --check`** on the Python files E01 adds or changes, and **`mypy`**.

The gate rows aggregate their assertions and the checks named in `GATES`. G8 — `scripts/gate.sh`
and CI on x86-64 and aarch64 — is not run here (it runs once before merge): `S12.G8`, `S12.gate`
and `S12.ci` are `unsupported`. G10 (A48, release-candidate data) runs at the release-candidate
cut (§9.6): `S12.A48` and `S12.G10` are `unsupported`, recorded `not run (RC item)`, which is not a
pass. `status` is computed, never written: `tested` iff every other assertion and every required
check passes; otherwise `implemented`. Both review fields stay `pending`; `reviewed` is the design
lane's.

Usage:
    TMPDIR=<disk dir> PYTHONPATH=src .venv/bin/python scripts/e01_evidence_manifest.py \\
        --lca-python <venv-lca>/bin/python --nlp-prefix <.venv-nlp> \\
        --nlp-cache <.reference-downloads/m03-ipopt> [--build-python /usr/bin/python3] \\
        [--basetemp DIR] [--commit SHA] [--out PATH]
"""

from __future__ import annotations

import argparse
import filecmp
import json
import os
import re
import subprocess
import sys
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from jsonschema import Draft202012Validator

sys.path.insert(0, str(Path(__file__).resolve().parent))
from s01_evidence_manifest import (  # noqa: E402  (S01's generic helpers, unchanged)
    LOCK,
    ROOT,
    SCHEMA,
    Node,
    Run,
    check,
    command,
    nodes,
    refuse_unless_measuring,
    sha256_file,
    shown,
    text,
)
from s02_evidence_manifest import _verdict  # noqa: E402
from s11_evidence_manifest import merged, skips, wall_times  # noqa: E402

#: E01's manifest id (ESC-I2 ruling; R-565). E01 is its name in the docs.
PACKAGE = "S12"
ALIAS = "E01"
NOTE = ROOT / "docs" / "derivations" / "E01-design.md"
ADR = ROOT / "docs" / "adr" / "0052-e01-assessment-functionals.md"
DECISIONS = tuple(ROOT / "docs" / f"E01{track}_DECISIONS.md" for track in "AB")
#: The S11 head `wp/E01` merged at 4f000563: E01's tree is this commit plus E01 (§4.14's identity
#: base while S11 is not on `main`).
S11_HEAD = "8d2ee175"
#: §4.14: no file changes under these.
PROTECTED = tuple(
    f"src/openflowsheet/{path}"
    for path in (
        *(
            "compile thermo models verify orchestrator numerics application adapters graph ir "
            "run units canonical.py compiled.py serialize.py"
        ).split(),
        "studies/trust_region",
        "studies/sensitivity.py",
        "studies/sweep.py",
        "studies/estimation.py",
    )
)
ASSERTIONS = tuple(f"A{index:02d}" for index in range(1, 49))
#: Recorded, never run here (§9.6: G10 runs at the release-candidate cut).
RC_ITEMS = ("A48",)
GATES: dict[str, tuple[str, tuple[str, ...], tuple[str, ...]]] = {
    "G1": ("identity: E01.A1, A2", ("A01", "A02"), ()),
    "G2": ("core: E01.A4–A8", tuple(f"A{i:02d}" for i in range(4, 9)), ()),
    "G3": (
        "sizing: E01.A9–A13, A46, A47",
        (*(f"A{i:02d}" for i in range(9, 14)), "A46", "A47"),
        (),
    ),
    "G4": (
        "cost: E01.A14–A23, A44, A45",
        (*(f"A{i:02d}" for i in range(14, 24)), "A44", "A45"),
        ("S12.cost-hand",),
    ),
    "G5": (
        "LCA: E01.A24–A29 (A24, A25 in the lca environment)",
        tuple(f"A{i:02d}" for i in range(24, 30)),
        ("S12.lca-data",),
    ),
    "G6": (
        "studies: E01.A30–A37 (A33–A36 in the nlp environment), §4.13's timings recorded",
        tuple(f"A{i:02d}" for i in range(30, 38)),
        (),
    ),
    "G7": (
        "schemas and rights: E01.A38–A43",
        tuple(f"A{i:02d}" for i in range(38, 44)),
        ("S12.t08", "S12.d04", "S12.policy", "S12.m03-fixtures"),
    ),
    "G9": ("M03 inert: E01.A3, A35", ("A03", "A35"), ("S12.m03-fixtures-nlp", "S12.nlp-check")),
}
TIMED = {"G6": tuple(f"A{i:02d}" for i in range(30, 38))}
#: Nodes that cite assertions other than through their names: E01 tests named otherwise (cited by
#: their docstrings), and the tests of other packages that an E01 assertion names (A43).
CITATIONS: dict[str, tuple[str, ...]] = {
    "tests/test_e01_a_contributor.py::test_th_c2_complete_cost_and_a22": ("A22",),
    "tests/test_e01_a_links.py": ("A43",),
    "tests/test_e01_b_brightway.py::test_the_float64_assembly_is_brightways_own_matrices"
    "_unrounded": ("A24",),
    "tests/test_e01_b_brightway.py::test_foreground_check_reproduces_the_hand_superposition": (
        "A25",
    ),
    "tests/test_e01_b_brightway.py::test_foreground_check_on_p4_against_the_b4_expectation": (
        "A25",
    ),
    "tests/test_e01_b_cost_hand.py::test_the_recorded_states_are_the_solved_states": (
        "A11",
        "A12",
    ),
    "tests/test_e01_b_lca.py::test_p4_matches_the_hand_superposition": ("A25", "A29"),
    **{
        f"tests/test_m04_numerical_policy.py::test_a37_{name}": ("A43",)
        for name in (
            "every_float_of_every_m04_fixture_is_classified",
            "every_rule_of_the_manifest_matches_a_float_of_a19s_manifest",
            "a19s_manifest_is_r0_no_decision_is_near_threshold",
            "a_constructed_near_case_is_flagged",
            "the_sha256_partition_follows_the_schemas",
        )
    },
    **{
        f"tests/test_m02_schemas.py::test_g1_{name}": ("A43",)
        for name in (
            "each_new_schema_is_published_by_its_id",
            "the_addendum_covers_exactly_m02s_schemas_with_its_four_classes",
            "the_sha256_partition_holds_over_m02s_schemas",
            "the_partition_refuses_an_unclassified_and_a_reclassified_name",
            "a32_every_float_of_every_m02_fixture_is_classified",
        )
    },
    **{
        f"tests/test_t08_adr0025.py::test_a1_{name}": ("A43",)
        for name in (
            "the_policy_file_is_what_its_generator_emits",
            "the_generator_refuses_each_condition",
            "an_unclassified_sha256_name_is_refused",
            "a_tampered_policy_file_fails_its_audit",
        )
    },
}
#: Run A's other test files: the tests E01 amends on purpose (§8.3, WO-I1), those A43 names, and
#: the package-data, envelope and identity tests the packaging touches.
OTHER_TESTS = (
    "test_m02_schemas.py",
    "test_m03_schemas.py",
    "test_m03_nlp_status.py",
    "test_m04_numerical_policy.py",
    "test_m05_study_record.py",
    "test_m07_mr12_extras_v02.py",
    "test_package_imports.py",
    "test_s05_envelope.py",
    "test_t08_adr0025.py",
    "test_t08_w2_inventory.py",
    "test_t08_w2_support_envelope.py",
    "test_t08_w4_package_data.py",
    "test_*identity*.py",
)
#: Run L: the files whose Brightway tests skip without the `lca` extra.
LCA_TESTS = (
    "tests/test_e01_b_brightway.py",
    "tests/test_e01_b_lca.py",
    "tests/test_e01_b_tables.py",
)
CITED = re.compile(r"^test_((?:a\d{1,2}_)+)")
G1_LINE = re.compile(r"^S11-IDENTITY PASS n=(\d+) changed=\[\]$")
POLICY_SHA256 = "6b449911f4e692051b08372fefaf0e205e9b2d746362e4fba2c4a9f6e19d707c"
#: Each generator's `--check`: the script, its arguments, the line it must end with, and the
#: environment it runs in ("default" or "nlp").
GENERATOR_LINES: dict[str, tuple[str, tuple[str, ...], re.Pattern[str], str]] = {
    "S12.t08": (
        "scripts/t08_support_matrix.py",
        ("--check",),
        re.compile(r"^0 problem\(s\)$"),
        "default",
    ),
    "S12.d04": ("scripts/e01_d04_inventory.py", ("--check",), re.compile(r"^A42 PASS$"), "default"),
    "S12.lca-data": (
        "scripts/e01_lca_data.py",
        ("--check",),
        re.compile(r"^e01_lca_data: current$"),
        "default",
    ),
    "S12.policy": (
        "scripts/t08_numerical_policy.py",
        ("--check",),
        re.compile(rf"equals the regenerated bytes \(sha256 {POLICY_SHA256}\)$"),
        "default",
    ),
    "S12.cost-hand": (
        "benchmarks/e01/cost_hand/cost_hand.py",
        ("--check",),
        re.compile(r"^cost_hand\.yaml current$"),
        "default",
    ),
    "S12.m03-fixtures": (
        "scripts/m03_schema_fixtures.py",
        (),
        re.compile(r"^all M03 fixtures match what the code emits$"),
        "default",
    ),
    "S12.m03-fixtures-nlp": (
        "scripts/m03_schema_fixtures.py",
        ("--nlp",),
        re.compile(r"^all M03 fixtures match what the code emits$"),
        "nlp",
    ),
}
#: The non-assertion checks `status` also requires.
REQUIRED_CHECKS = (
    "S12.suite",
    "S12.suites",
    "S12.nlp-check",
    *(f"S12.{gate}" for gate in GATES),
    *GENERATOR_LINES,
    "S12.ruff",
    "S12.format",
    "S12.mypy",
)


# -- running -------------------------------------------------------------------------------------


class Environments:
    """The interpreters and directories outside the repository, each shown by a symbol."""

    def __init__(self, arguments: argparse.Namespace) -> None:
        self.lca: Path | None = arguments.lca_python
        self.nlp_prefix: Path | None = arguments.nlp_prefix
        self.nlp_cache: Path | None = arguments.nlp_cache
        self.build: Path | None = arguments.build_python
        self.basetemp: Path | None = arguments.basetemp
        self.symbols = {
            str(path): symbol
            for path, symbol in (
                (self.lca, "$LCA_PYTHON"),
                (self.nlp_prefix, "$NLP_PREFIX"),
                (self.nlp_cache, "$NLP_CACHE"),
                (self.build, "$BUILD_PYTHON"),
                (self.basetemp, "$BASETEMP"),
            )
            if path is not None
        }

    def nlp(self) -> bool:
        return self.nlp_prefix is not None and self.nlp_cache is not None

    def nlp_python(self) -> str:
        assert self.nlp_prefix is not None
        return str(self.nlp_prefix / "bin" / "python")

    def nlp_environment(self, tree: Path) -> dict[str, str]:
        """The audited NLP environment as `scripts/m03_nlp_check.sh` sets it, for `tree`."""
        assert self.nlp_prefix is not None and self.nlp_cache is not None
        return {
            "PYTHONNOUSERSITE": "1",
            "PYOMO_CONFIG_DIR": str(self.nlp_prefix / "share" / "pyomo"),
            "OMP_NUM_THREADS": "1",
            "PYTHONPATH": os.pathsep.join(
                [str(tree / "src"), str(self.nlp_cache / "nlp-test-tools")]
            ),
        }

    def display(self, part: str) -> str:
        """An argument as the manifest shows it: an outside path by its symbol, this
        interpreter's tools as `.venv/bin/<name>`, other paths relative to the root."""
        option, equals, value = part.partition("=")
        if equals and option.startswith("--"):
            return f"{option}={self.display(value)}"
        for path, symbol in self.symbols.items():
            if part == path or part.startswith(path + os.sep):
                return symbol + part[len(path) :]
        tools = Path(sys.executable).parent
        if os.path.isabs(part) and Path(part).parent == tools:
            return f".venv/bin/{Path(part).name}"
        if os.path.isabs(part):
            return shown(part)
        return part


def run(
    environments: Environments,
    argv: Sequence[str],
    *,
    environment: Mapping[str, str] | None = None,
    prefix: str = "PYTHONPATH=src:. ",
    cwd: Path = ROOT,
) -> Run:
    """`argv` at `cwd` with `src` and the root importable, or with `environment` instead."""
    variables = dict(os.environ)
    if environment is None:
        variables["PYTHONPATH"] = os.pathsep.join([str(cwd / "src"), str(cwd)])
    else:
        variables.update(environment)
    completed = subprocess.run(
        list(argv), cwd=cwd, env=variables, capture_output=True, text=True, check=False
    )
    cmd = prefix + " ".join(environments.display(part) for part in argv)
    return Run(cmd, completed.returncode, completed.stdout + completed.stderr)


def _last_line(entry: Run) -> str:
    return entry.stdout.strip().splitlines()[-1] if entry.stdout.strip() else ""


def _git(*arguments: str) -> str:
    return subprocess.run(
        ["git", *arguments], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()


# -- the documents -------------------------------------------------------------------------------


def assertion_texts() -> dict[str, str]:
    """Each id's bullet (`- **Axx…**` and its continuation lines), first occurrence."""
    found: dict[str, str] = {}
    lines = NOTE.read_text(encoding="utf-8").splitlines()
    for index, line in enumerate(lines):
        match = re.match(r"^- \*\*A(\d{1,2})\b(.*)$", line)
        if not match:
            continue
        identifier = f"A{int(match.group(1)):02d}"
        if identifier in found:
            continue
        body = [line[2:].strip()]
        for following in lines[index + 1 :]:
            if not following.startswith("  ") or not following.strip():
                break
            body.append(following.strip())
        found[identifier] = f"{ALIAS}." + " ".join(body).replace("**", "")
    missing = [identifier for identifier in ASSERTIONS if identifier not in found]
    if missing:
        raise SystemExit(f"assertions not found in the design note: {missing}")
    return found


# -- the tests -----------------------------------------------------------------------------------


def cited(node: str) -> tuple[str, ...]:
    function = node.split("[", 1)[0]
    module, _, name = function.partition("::")
    explicit = CITATIONS.get(function, ()) + CITATIONS.get(module, ())
    match = CITED.match(name) if module.startswith("tests/test_e01_") else None
    named = tuple(
        f"A{int(number):02d}"
        for number in re.findall(r"a(\d{1,2})_", match.group(1) if match else "")
    )
    return named + explicit


def properties(junit: Path, prefix: str) -> dict[str, dict[str, str]]:
    """Each node's recorded properties (`record_property`) whose names start with `prefix`."""
    found: dict[str, dict[str, str]] = {}
    for case in ElementTree.parse(junit).getroot().iter("testcase"):
        node = f"{case.get('classname', '').replace('.', '/')}.py::{case.get('name', '')}"
        for item in case.iter("property"):
            if item.get("name", "").startswith(prefix):
                found.setdefault(node, {})[item.get("name", "")] = item.get("value", "")
    return found


def _judged(citing: Sequence[Node]) -> tuple[str, dict[str, Any]]:
    """S02's verdict, with the node ids made manifest-safe (a parametrize id may hold `<…>`)."""
    result, value = _verdict(citing)
    return result, {**value, "selectors": [text(node) for node in value["selectors"]]}


def suite_check(identifier: str, description: str, chosen: Sequence[Node]) -> dict[str, Any]:
    """Every chosen node passed (and there is at least one)."""
    result, value = _verdict(chosen)
    del value["selectors"]
    return check(identifier, description, result, value, "every node passed")


def suites_check(chosen: Sequence[Node]) -> dict[str, Any]:
    """No node failed or errored, and no skipped node is cited by an assertion."""
    _, value = _verdict(chosen)
    del value["selectors"]
    failed = [item for item in value["not_passed"] if item["outcome"] in ("failed", "error")]
    cited_skips = [item.node for item in chosen if item.outcome == "skipped" and cited(item.node)]
    value = {**value, "not_passed": failed, "skipped": skips(chosen), "cited_skips": cited_skips}
    passed = bool(chosen) and not failed and not cited_skips
    return check(
        "S12.suites",
        "the other test files run here (§8.3's amended tests, A43's M04/M02/ADR 0025 tests, the "
        "T08 inventory, W4 package-data and S05 envelope tests, the identity tests, and the "
        "`nlp`-marked tests of M03 and M05): no node failed or errored in any run, and no skipped "
        "node is cited by an assertion; the skipped nodes are listed with their reasons",
        "pass" if passed else "fail",
        value,
        "no failure; skips listed, none cited",
    )


# -- G1 and G9 -----------------------------------------------------------------------------------


def a1_check() -> tuple[str, dict[str, Any]]:
    """§4.14's protected paths: no change against the S11 head; the literal `main...HEAD` form
    is recorded (it shows S11's own changes until S11 merges)."""
    against_s11 = _git("diff", "--name-only", f"{S11_HEAD}..HEAD", "--", *PROTECTED).splitlines()
    literal = _git("diff", "--name-only", "main...HEAD", "--", *PROTECTED).splitlines()
    s11_own = _git("diff", "--name-only", f"main...{S11_HEAD}", "--", *PROTECTED).splitlines()
    value = {
        "judged_by": f"git diff --name-only {S11_HEAD}..HEAD over §4.14's protected paths",
        "protected": list(PROTECTED),
        "changed_against_s11_head": against_s11,
        "literal_main_three_dot_files": len(literal),
        "s11_own_main_three_dot_files": len(s11_own),
        "literal_equals_s11_own": literal == s11_own,
    }
    return ("pass" if not against_s11 and literal == s11_own else "fail"), value


def m03_dump(environments: Environments, artifacts: Path) -> tuple[dict[str, Any], list[Run]]:
    """A3: the M03 NLP fixture documents (wall times blanked), A35's component list and the
    objective, dumped in a detached worktree of `S11_HEAD` and in this tree, byte for byte."""
    python = environments.nlp_python()
    dumper = str(ROOT / "scripts" / "e01_m03_dump.py")
    outputs = {"base": artifacts / "m03-dump-base.json", "head": artifacts / "m03-dump-head.json"}
    prefix = "OMP_NUM_THREADS=1 PYTHONNOUSERSITE=1 PYOMO_CONFIG_DIR=$NLP_PREFIX/share/pyomo "
    shown_tree = f"‹worktree of {S11_HEAD}›"
    runs: list[Run] = []
    with tempfile.TemporaryDirectory() as directory:
        tree = Path(directory) / "base"
        subprocess.run(
            ["git", "worktree", "add", "--detach", str(tree), S11_HEAD],
            cwd=ROOT,
            capture_output=True,
            check=True,
        )
        try:
            for name, where in (("base", tree), ("head", ROOT)):
                entry = run(
                    environments,
                    [python, dumper, str(where), str(outputs[name])],
                    environment=environments.nlp_environment(where),
                    prefix=prefix
                    + f"PYTHONPATH={shown_tree + '/' if name == 'base' else ''}"
                    + "src:$NLP_CACHE/nlp-test-tools ",
                )
                if name == "base":
                    entry = Run(
                        entry.cmd.replace(str(tree), shown_tree), entry.exit_code, entry.stdout
                    )
                runs.append(entry)
        finally:
            subprocess.run(
                ["git", "worktree", "remove", "--force", str(tree)],
                cwd=ROOT,
                capture_output=True,
                check=False,
            )
    present = all(path.is_file() for path in outputs.values())
    identical = present and filecmp.cmp(outputs["base"], outputs["head"], shallow=False)
    value = {
        "base": S11_HEAD,
        "exit_codes": [entry.exit_code for entry in runs],
        "lines": [_last_line(entry) for entry in runs],
        "sha256": {name: sha256_file(path) for name, path in outputs.items() if path.is_file()},
        "identical": identical,
    }
    return value, runs


# -- the manifest --------------------------------------------------------------------------------


def status(entries: Sequence[Mapping[str, Any]]) -> str:
    """`tested` iff every assertion but the RC items and every required check passes."""
    required = {
        f"S12.{identifier}" for identifier in ASSERTIONS if identifier not in RC_ITEMS
    } | set(REQUIRED_CHECKS)
    results = {entry["id"]: entry["result"] for entry in entries}
    missing = required - set(results)
    if missing:
        raise SystemExit(f"checks missing: {sorted(missing)}")
    return "tested" if all(results[name] == "pass" for name in required) else "implemented"


def found_limitations(entries: Sequence[Mapping[str, Any]], a33: Mapping[str, Any]) -> list[str]:
    starts = "; ".join(f"{name}: {value}" for name, value in sorted(a33.items()))
    items = [
        f"Package id: this manifest is filed as {PACKAGE}, the alias of E01 (orchestrator ruling "
        "on ESC-I2, 2026-10-29; R-565's precedent, L01 → S04): the frozen "
        "schemas/evidence-manifest.schema.json admits only ^[PKTMSR][0-9]{2}[a-z]?$. Check ids "
        f"are {PACKAGE}.*; each assertion's description names it E01.A#.",
        "requirements is empty: the design note assigns E01 no D/A requirement id, and "
        "docs/requirements.yaml has no E01 entry.",
        "A33 is judged as the orchestrator's ruling on ESC-I1 (2026-10-29) restates it (design "
        "note §6.1, A33's dated erratum): tac(candidate) ≤ tac(start) over the starts feasible "
        "for the formulation's constraints within their stated tolerance (box exactly, slack ≥ "
        "−τ_feas = 1e-8), M03's infeasible starts reported with their violations, not compared. "
        f"Recorded at this commit (nlp environment): {starts}. The literal clause over every "
        "start does not hold at M03's starts 0 and 1, which violate recovery_A ≥ 0.",
        "A1 is judged against the S11 head wp/E01 merged (8d2ee175): S11 is not on main yet, so "
        "the literal `git diff --stat main...wp/E01` over the protected paths shows S11's own "
        "changes (recorded in S12.A01: equal to S11's main...8d2ee175 set). The literal form "
        "applies once S11 merges.",
        "G8 (scripts/gate.sh, CI on x86-64 and aarch64) was not run by this generator: it runs "
        "once before merge into main. S12.G8, S12.gate and S12.ci are unsupported.",
        "G10, release-candidate data (§9.6 A48: every primary range in shipped sets is "
        "verified: true) is not run (RC item): S12.A48 and S12.G10 are unsupported, which is not "
        "a pass. The shipped SSLW primary ranges carry verified: false until a person with Seider "
        "3rd ed. ch. 22 checks them (§9.7 QA1); the release candidate is blocked until then.",
        "Review: the design lane's single reviewer pass over tracks A and B and WO-I1 against the "
        "design note (ADR 0052's acceptance) has not happened; the review fields stay pending, "
        "and the human numerical and process-model review is pending. This manifest claims "
        "neither.",
        "Open for the design lane (docs/E01B_DECISIONS.md, WO-I1): the DECISION lines on the "
        "repository path assessment/, the MR-12 pattern for the lca extra and the P1–P4 "
        "configurations; and the observation that AssessmentProgram.build(contributors=None) "
        "takes only the contributors registered by importing assessment.cost.contributor, "
        "cost.derived and lca.section, which nothing in src imports, so a default build yields "
        "an empty program without a refusal (the tests pass explicit contributors).",
        "Environments: run A is the locked environment; run L (A24, A25) is the lca extra's "
        "environment built by scripts/build-lca-env.sh in a scratch directory, outside "
        "requirements.lock; run N (A33–A36, M03 and M05 nlp tests, A3's dumps and "
        "m03_schema_fixtures.py --nlp) is the audited NLP environment of docs/m03-ipopt-audit.md "
        "from a sibling worktree, with scripts/m03_nlp_check.sh's two inventory re-takes.",
        "G1's family C (scripts/s11_identity.py) runs every tests/test_*.py in the base and this "
        "tree and requires every shard to exit 0, so the whole default suite passed in this tree; "
        "it is not the full gate (no ruff/mypy over the repository, no packaging or wheel "
        "checks beyond the tests named).",
        "The agreement with the hand and independent expectations (benchmarks/e01/cost_hand "
        "mpmath, the IDAES evaluation, benchmarks/e01/lca_hand, Brightway's foreground_check) is "
        "numerical verification against the pinned sources, not empirical validation of cost or "
        "impact; test-background-v1 is synthetic, and the KKT_POINT_VERIFIED candidate of A33 is "
        "a verified local point, not optimality evidence. Self-generated fixtures (the "
        "assessment-report fixtures) are regression fixtures.",
        "The wall times in S12.G6 are the JUnit times of the cited nodes in this run (each "
        "includes binding, solving and verification where the test does).",
        "The T08 support envelope's harvest of this manifest, if t08_support_matrix.py --check "
        "asks for one, follows its generation in a later commit.",
    ]
    for entry in entries:
        if entry["id"] == "S12.suites" and entry["value"].get("skipped"):
            listed = "; ".join(f"{n} × {key}" for key, n in entry["value"]["skipped"].items())
            items.append(
                text(f"Skipped (not counted as passed; none cited by an E01 assertion): {listed}.")
            )
    for entry in entries:
        if entry["result"] == "pass" or entry["id"] in (
            "S12.G8",
            "S12.gate",
            "S12.ci",
            "S12.G10",
            *(f"S12.{item}" for item in RC_ITEMS),
        ):
            continue
        value = entry.get("value")
        detail = (
            "; ".join(f"{item['node']} {item['outcome']}" for item in value["not_passed"])
            if isinstance(value, dict) and value.get("not_passed")
            else "see its value"
        )
        items.append(text(f"{entry['id']} is {entry['result']}: {detail}"))
    return items


def build(commit: str, environments: Environments) -> dict[str, Any]:
    refuse_unless_measuring(commit)
    texts = assertion_texts()
    artifacts = ROOT / "evidence" / PACKAGE / commit / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    junits = {
        "A": artifacts / "e01-tests-a.junit.xml",
        "L": artifacts / "e01-tests-l.junit.xml",
        "N": artifacts / "e01-tests-n.junit.xml",
    }
    python = sys.executable
    tools = Path(python).parent
    lca_run = environments.lca is not None
    tests_a = sorted(
        {
            shown(path)
            for pattern in ("test_e01_*.py", *OTHER_TESTS)
            for path in (ROOT / "tests").glob(pattern)
        }
        - ({"tests/test_e01_b_brightway.py"} if lca_run else set())
    )
    tests_n = sorted(
        shown(path)
        for path in (ROOT / "tests").glob("test_*.py")
        if "mark.nlp" in path.read_text(encoding="utf-8")
    )
    changed = [
        path
        for path in _git(
            "diff", "--name-only", "--diff-filter=AM", f"{S11_HEAD}..HEAD"
        ).splitlines()
        if path.endswith(".py")
    ]

    def pytest(junit: Path, name: str) -> list[str]:
        argv = ["-q", "-p", "no:cacheprovider", f"--junitxml={junit}"]
        if environments.basetemp is not None:
            argv.append(f"--basetemp={environments.basetemp / name}")
        return argv

    default_a: dict[str, str] | None = None
    prefix_a = "PYTHONPATH=src:. "
    if environments.build is not None:
        default_a = {
            "PYTHONPATH": os.pathsep.join([str(ROOT / "src"), str(ROOT)]),
            "OFS_S05_BUILD_PYTHON": str(environments.build),
        }
        prefix_a = "OFS_S05_BUILD_PYTHON=$BUILD_PYTHON PYTHONPATH=src:. "
    runs: dict[str, Run] = {
        "tests-A": run(
            environments,
            [python, "-m", "pytest", *pytest(junits["A"], "a"), *tests_a],
            environment=default_a,
            prefix=prefix_a,
        )
    }
    if lca_run:
        runs["tests-L"] = run(
            environments,
            [str(environments.lca), "-m", "pytest", *pytest(junits["L"], "l"), *LCA_TESTS],
        )
    dump_value: dict[str, Any] | None = None
    dump_runs: list[Run] = []
    if environments.nlp():
        runs["S12.nlp-check"] = run(
            environments,
            [
                "bash",
                str(ROOT / "scripts" / "m03_nlp_check.sh"),
                str(environments.nlp_prefix),
                str(environments.nlp_cache),
                "--",
                *pytest(junits["N"], "n"),
                *tests_n,
            ],
            prefix="",
        )
        dump_value, dump_runs = m03_dump(environments, artifacts)
    for name, (script, arguments, _, where) in GENERATOR_LINES.items():
        if where == "nlp":
            if not environments.nlp():
                continue
            runs[name] = run(
                environments,
                [environments.nlp_python(), str(ROOT / script), *arguments],
                environment=environments.nlp_environment(ROOT),
                prefix="OMP_NUM_THREADS=1 PYTHONNOUSERSITE=1 PYOMO_CONFIG_DIR=$NLP_PREFIX/share/"
                "pyomo PYTHONPATH=src:$NLP_CACHE/nlp-test-tools ",
            )
        else:
            runs[name] = run(environments, [python, str(ROOT / script), *arguments])
    runs["S12.ruff"] = run(environments, [str(tools / "ruff"), "check", *changed])
    runs["S12.format"] = run(environments, [str(tools / "ruff"), "format", "--check", *changed])
    runs["S12.mypy"] = run(environments, [str(tools / "mypy")])
    runs["S12.G1"] = run(
        environments,
        [
            python,
            str(ROOT / "scripts" / "s11_identity.py"),
            "--keep",
            str(artifacts / "s11-identity"),
        ],
    )

    if not junits["A"].is_file():
        raise SystemExit(f"pytest wrote no report (exit {runs['tests-A'].exit_code})")
    present = [path for path in junits.values() if path.is_file()]
    found: list[Node] = []
    for path in present:
        found = merged(found, nodes(path))
    times = wall_times(*present)
    a33 = {
        name: value
        for node, values in (
            properties(junits["N"], "a33_") if junits["N"].is_file() else {}
        ).items()
        if node.endswith("test_a33_a34_p2_tac_objective_from_every_start")
        for name, value in values.items()
    }

    g1_line = _last_line(runs["S12.G1"])
    a2_result = "pass" if runs["S12.G1"].exit_code == 0 and G1_LINE.match(g1_line) else "fail"
    a1_result, a1_value = a1_check()
    special: dict[str, tuple[str, dict[str, Any]]] = {
        "A01": (a1_result, a1_value),
        "A02": (
            a2_result,
            {
                "judged_by": "scripts/s11_identity.py against its main baseline 8c34ecb0",
                "cmd": runs["S12.G1"].cmd,
                "exit_code": runs["S12.G1"].exit_code,
                "line": g1_line,
                "expected": "S11-IDENTITY PASS n=‹N› changed=[]",
            },
        ),
    }
    m03_tests = [item for item in found if item.node.startswith("tests/test_m03_nlp_greybox.py")]
    if dump_value is None:
        special["A03"] = ("unsupported", {"judged_by": "not run: no NLP environment given"})
    else:
        fixtures = runs.get("S12.m03-fixtures-nlp")
        fixtures_ok = fixtures is not None and fixtures.exit_code == 0
        tests_result, tests_value = _verdict(m03_tests)
        passed = dump_value["identical"] and fixtures_ok and tests_result == "pass"
        special["A03"] = (
            "pass" if passed else "fail",
            {
                "judged_by": "the byte comparison of scripts/e01_m03_dump.py (base vs this tree), "
                "m03_schema_fixtures.py --nlp and M03's NLP tests",
                "dump": dump_value,
                "fixtures_nlp_line": _last_line(fixtures) if fixtures else None,
                "m03_nlp_tests": {k: v for k, v in tests_value.items() if k != "selectors"},
            },
        )
    entries: list[dict[str, Any]] = []
    for identifier in ASSERTIONS:
        value: Any
        if identifier in special:
            result, value = special[identifier]
        elif identifier in RC_ITEMS:
            result, value = (
                "unsupported",
                "not run (RC item): G10 runs at the release-candidate cut",
            )
        else:
            result, value = _judged([item for item in found if identifier in cited(item.node)])
            if identifier == "A33":
                value = {**value, "recorded_starts": a33}
            for name, generator in (("A42", "S12.d04"), ("A43", "S12.policy")):
                if identifier == name:
                    script, _, pattern, _ = GENERATOR_LINES[generator]
                    line = _last_line(runs[generator])
                    ok = runs[generator].exit_code == 0 and bool(pattern.search(line))
                    value = {**value, "generator": {"script": script, "line": line, "ok": ok}}
                    result = result if ok else "fail"
        entries.append(check(f"S12.{identifier}", texts[identifier], result, value))

    entries += [
        suite_check(
            "S12.suite",
            "every node of tests/test_e01_*.py passed (the worse over runs A, L and N), including "
            "those that cite no assertion",
            [item for item in found if item.node.startswith("tests/test_e01_")],
        ),
        suites_check([item for item in found if not item.node.startswith("tests/test_e01_")]),
    ]
    if "S12.nlp-check" in runs:
        nlp_entry = runs["S12.nlp-check"]
        entries.append(
            check(
                "S12.nlp-check",
                "scripts/m03_nlp_check.sh over every nlp-marked test file, with its two inventory "
                "re-takes (NLP-1 and the Ipopt executable workloads)",
                "pass" if nlp_entry.exit_code == 0 else "fail",
                {
                    "cmd": nlp_entry.cmd,
                    "exit_code": nlp_entry.exit_code,
                    "line": _last_line(nlp_entry),
                },
                "=== m03_nlp_check.sh: PASSED ===",
            )
        )
    else:
        entries.append(
            check("S12.nlp-check", "scripts/m03_nlp_check.sh", "unsupported", "no NLP environment")
        )
    for name, (script, arguments, pattern, where) in GENERATOR_LINES.items():
        described = " ".join((script, *arguments)) + (
            " (nlp environment)" if where == "nlp" else ""
        )
        if name not in runs:
            entries.append(check(name, described, "unsupported", "no NLP environment given"))
            continue
        line = _last_line(runs[name])
        entries.append(
            check(
                name,
                described,
                "pass" if runs[name].exit_code == 0 and pattern.search(line) else "fail",
                {"cmd": runs[name].cmd, "exit_code": runs[name].exit_code, "line": line},
                pattern.pattern,
            )
        )
    results = {entry["id"]: entry["result"] for entry in entries}

    for gate, (description, members, extra) in GATES.items():
        parts = {f"S12.{member}": results[f"S12.{member}"] for member in members}
        parts.update({name: results[name] for name in extra})
        value = {"judged_by": "its assertions and checks", "parts": parts}
        if gate in TIMED:
            value["wall_time_s"] = {
                item.node: round(times.get(item.node, 0.0), 3)
                for item in found
                if any(a in cited(item.node) for a in TIMED[gate])
            }
        passed = all(result == "pass" for result in parts.values())
        entries.append(
            check(f"S12.{gate}", f"§6.2 {gate}, {description}", "pass" if passed else "fail", value)
        )
    for name, description in (
        ("S12.ruff", "ruff check is clean on the Python files E01 adds or changes"),
        ("S12.format", "ruff format --check is clean on the Python files E01 adds or changes"),
        ("S12.mypy", "mypy (the project's configuration) is clean"),
    ):
        entries.append(
            check(
                name,
                description,
                "pass" if runs[name].exit_code == 0 else "fail",
                {"cmd": runs[name].cmd, "exit_code": runs[name].exit_code},
                "exit code 0",
            )
        )
    for name, description, reason in (
        (
            "S12.G8",
            "§6.2 G8, release-level: full scripts/gate.sh PASS once before merge; CI green on "
            "x86-64 and aarch64",
            "not run by this generator; it runs once before merge (CLAUDE.md)",
        ),
        ("S12.gate", "scripts/gate.sh passes before merge", "not run by this generator"),
        ("S12.ci", "CI is green on x86-64 and aarch64 before merge", "not run by this generator"),
        (
            "S12.G10",
            "§9.6 G10, release-candidate data: E01.A48",
            "not run (RC item): it runs at the release-candidate cut; not a pass",
        ),
    ):
        entries.append(check(name, description, "unsupported", reason))

    commands = [command(entry) for entry in (*runs.values(), *dump_runs)]
    documents = [
        (NOTE, "the E01 design note (§6 assertions and gates, §9 amendment, A33's erratum)"),
        (ADR, "the decision E01 implements"),
        *((path, "E01's build decisions with the measured facts") for path in DECISIONS),
    ]
    manifest: dict[str, Any] = {
        "work_package": PACKAGE,
        "commit": commit,
        "requirements": [],
        "status": status(entries),
        "inputs": {
            "case_id": "E01 (manifest id S12) acceptance: docs/derivations/E01-design.md §6.1 "
            "(E01.A1–A42) and §9.6 (A43–A48), gates G1–G10, ESC-I1's and ESC-I2's rulings "
            "(docs/E01B_DECISIONS.md, 2026-10-29)",
            "case_hash": sha256_file(NOTE),
            "environment_lock_hash": sha256_file(LOCK),
        },
        "commands": commands,
        "checks": entries,
        "artifacts": [
            *(
                {
                    "path": shown(path),
                    "sha256": sha256_file(path),
                    "description": f"JUnit report of test run {run_id} (ignored; kept by hash)",
                }
                for run_id, path in junits.items()
                if path.is_file()
            ),
            *(
                {
                    "path": shown(artifacts / f"m03-dump-{name}.json"),
                    "sha256": sha256_file(artifacts / f"m03-dump-{name}.json"),
                    "description": f"A3's dump, {name} tree (ignored; kept by hash)",
                }
                for name in ("base", "head")
                if (artifacts / f"m03-dump-{name}.json").is_file()
            ),
            *(
                {"path": shown(path), "sha256": sha256_file(path), "description": description}
                for path, description in documents
            ),
        ],
        "limitations": found_limitations(entries, a33),
        "review": {"numerical": "pending", "process_model": "pending"},
    }
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    errors = [error.message for error in Draft202012Validator(schema).iter_errors(manifest)]
    if errors:
        raise SystemExit(f"the manifest does not validate: {errors}")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--commit", help="the measured commit (default: HEAD)")
    parser.add_argument("--lca-python", type=Path, help="the lca extra's interpreter (run L)")
    parser.add_argument("--nlp-prefix", type=Path, help="the audited NLP environment (run N)")
    parser.add_argument("--nlp-cache", type=Path, help="its download cache (nlp-test-tools)")
    parser.add_argument(
        "--build-python", type=Path, help="OFS_S05_BUILD_PYTHON for the S05 envelope tests"
    )
    parser.add_argument("--basetemp", type=Path, help="pytest's --basetemp root, one dir per run")
    parser.add_argument(
        "--out", type=Path, help=f"default: evidence/{PACKAGE}/<commit>/manifest.json"
    )
    arguments = parser.parse_args()
    commit = arguments.commit or _git("rev-parse", "HEAD")
    manifest = build(commit, Environments(arguments))
    out = arguments.out or ROOT / "evidence" / PACKAGE / commit / "manifest.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    passed = sum(1 for entry in manifest["checks"] if entry["result"] == "pass")
    failing = [entry["id"] for entry in manifest["checks"] if entry["result"] == "fail"]
    print(
        f"{shown(out)}: status {manifest['status']}, {passed}/{len(manifest['checks'])} checks "
        f"pass; fail: {failing}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
