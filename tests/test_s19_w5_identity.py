"""S19 W5 WO-0: the identity tool `scripts/w5_identity.py` (ruling `docs/briefs/S19-W5-ruling.md`).

Outside the gate (ruling section 9, row WO-0). Every expectation is the ruling's measurement at
8d31b89e (sections 3.2 and 4), not the tool's own output: W5-T1 (sets and its falsifiers), the
per-file reach of W5-T2 (the probe re-runs themselves are scratch work, quoted in the WO-0
report), W5-T6 (judge on synthetic registries) and W5-T7 (coverage on scratch trees). Scratch
trees are detached worktrees of the base under `tmp_path`, removed afterwards.
"""

from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import w5_identity as w5  # noqa: E402

BASE = "8d31b89e"
TOOL = ROOT / "scripts" / "w5_identity.py"
THERMO = "src/openflowsheet/thermo"

#: Section 4's tiers at 8d31b89e.
TIER_1 = [
    f"src/openflowsheet/assessment/{name}.py"
    for name in (
        *(f"cost/{m}" for m in ("__init__", "capital", "contributor", "derived", "forms")),
        *(f"cost/{m}" for m in ("index", "operating", "quotes", "sets", "uncertainty")),
        *(f"lca/{m}" for m in ("__init__", "brightway", "impact", "inventory", "section")),
        "lca/tables",
    )
]
TIER_3 = [
    f"{THERMO}/{name}.py"
    for name in ("_coolprop_heos_fluids", "coolprop_heos", "iapws95", "pr_c1", "wilson_ig")
] + [f"{THERMO}/wilson_ig_v2.py"]
TIER_4 = [f"{THERMO}/syn001.py"]
UNITS = {"c1": 8, "syn001": 14, "thermal": 5}

#: Section 3.2: edited file -> F0's failed count per failing measure.
REACH = {
    "thermo/pr_lib.py": {"M9": 1},
    "assessment/cost/sets.py": {},
    "thermo/syn001.py": {"M2": 52, "M3": 52, "M6": 77, "M7": 52, "M9": 1},
    "models/syn001/flash.py": {"M9": 1},
    "thermo/pr_c1.py": {"M2": 1, "M3": 1, "M6": 2, "M9": 1},
    "thermo/iapws95.py": {"M2": 3, "M3": 3, "M6": 2, "M9": 1},
    "thermo/wilson_ig.py": {"M2": 5, "M3": 5, "M6": 2, "M9": 1},
    "thermo/coolprop_heos.py": {"M6": 2, "M9": 1},
    "models/c1/flash.py": {"M9": 1},
    "models/thermal/heater.py": {"M9": 1},
    "thermo/wilson_ig_v2.py": {"M2": 5, "M3": 5, "M6": 2, "M9": 1},
    "thermo/_coolprop_heos_fluids.py": {"M6": 2, "M9": 1},
}
#: Section 3.2's named run keys of the tier 3 providers.
RUNS = {
    "thermo/pr_c1.py": {"m02/C1-FLASH-F1-M02-v1"},
    "thermo/iapws95.py": {"s11-th/TH-C1", "s11-th/TH-R1", "s11-th/TH-V1"},
    "thermo/wilson_ig.py": {f"s11-gp/GP-{n}" for n in ("C1", "C2", "C3", "M1", "M2")},
    "thermo/wilson_ig_v2.py": {f"s11-gp/GP-{n}" for n in ("C1", "C2", "C3", "M1", "M2")},
}
SAMPLES = {
    "thermo/pr_c1.py": "pr-c1-v1",
    "thermo/iapws95.py": "iapws95-v1",
    "thermo/wilson_ig.py": "wilson-ig-v2",
    "thermo/wilson_ig_v2.py": "wilson-ig-v2",
    "thermo/coolprop_heos.py": "coolprop-heos-v1",
    "thermo/_coolprop_heos_fluids.py": "coolprop-heos-v1",
}
COMMENT = "# W5 identity experiment: a comment-only edit (never committed).\n"


#: X07a platform limit (docs/X07a_DECISIONS.md): the facts at `BASE` come from importing that
#: tree, which predates the platform layer and imports `fcntl` (run 44618922484). A W5 base at or
#: after X07a's merge lifts it.
BASE_TREE_LIMIT = "the W5 base tree imports fcntl (it predates openflowsheet._platform): POSIX only"


def _skip_base_tree_on_windows() -> None:
    if sys.platform == "win32":
        pytest.skip(BASE_TREE_LIMIT)


def _git(*arguments: str, cwd: Path = ROOT) -> str:
    return subprocess.run(
        ["git", *arguments], cwd=cwd, capture_output=True, text=True, check=True
    ).stdout


def _tool(*arguments: str) -> subprocess.CompletedProcess[str]:
    _skip_base_tree_on_windows()
    return subprocess.run(
        [sys.executable, str(TOOL), *arguments], capture_output=True, text=True, check=False
    )


@pytest.fixture(scope="module")
def facts() -> w5.Facts:
    _skip_base_tree_on_windows()
    return w5.facts_at(ROOT, w5.resolve(ROOT, BASE))


@pytest.fixture
def scratch(tmp_path: Path) -> Iterator[Path]:
    """A detached worktree of the base, removed afterwards."""
    _skip_base_tree_on_windows()
    tree = tmp_path / "tree"
    _git("worktree", "add", "--detach", str(tree), BASE)
    try:
        yield tree
    finally:
        _git("worktree", "remove", "--force", str(tree))
        _git("worktree", "prune")


def _append(tree: Path, name: str, text: str) -> None:
    path = tree / w5.normalise(name)
    path.write_text(path.read_text(encoding="utf-8") + text, encoding="utf-8")


def _commit(tree: Path, message: str, *paths: str) -> str:
    _git("add", "--", *paths, cwd=tree)
    _git("-c", "user.name=w5", "-c", "user.email=w5@invalid", "commit", "-qm", message, cwd=tree)
    return _git("rev-parse", "HEAD", cwd=tree).strip()


# -- W5-T1: sets ----------------------------------------------------------------------------------


def test_t1_the_sets_and_tiers_at_the_base_are_section_4s(facts: w5.Facts) -> None:
    assert not {name: p for name, p in w5.assertions(facts).items() if p}
    r_set, frozen = w5.registry_set(facts), facts["frozen"]
    assert (len(r_set), len(frozen)) == (51, 35)
    assert set(frozen) < set(r_set)
    tiers = w5.tiers(facts)
    assert tiers[1] == sorted(TIER_1)
    assert tiers[3] == sorted(TIER_3)
    assert tiers[4] == TIER_4
    assert len(tiers[2]) == 28 and f"{THERMO}/pr_lib.py" in tiers[2]
    for family, n in UNITS.items():
        assert sum(f.startswith(f"src/openflowsheet/models/{family}/") for f in tiers[2]) == n
    assert w5.attribution(facts)[f"{THERMO}/wilson_ig.py"] == ["wilson-ig-v1", "wilson-ig-v2"]


def test_t1_the_check_line_at_the_base() -> None:
    done = _tool("sets", "--check", "--base", BASE)
    assert done.returncode == 0, done.stdout
    assert done.stdout.strip() == (
        "sets --check PASS: |R| 51, |F| 35, F subset of R, tiers 16/28/6/1, "
        "T-2a holds (27 unit hashes)"
    )


@pytest.mark.parametrize(
    ("descriptor", "module", "assertion"),
    [
        ("pr-lib-v1", "openflowsheet/thermo/pr_lib.py", "S1 F subset of R"),
        ("wilson-ig-v2", "openflowsheet/thermo/wilson_ig.py", "S2 implementation sets"),
    ],
)
def test_t1_falsifier_a_legacy_copy_without_one_module_exits_1(
    tmp_path: Path, descriptor: str, module: str, assertion: str
) -> None:
    rows = json.loads(
        (ROOT / "src/openflowsheet/registry/builtin/legacy.json").read_text(encoding="utf-8")
    )
    (row,) = [r for r in rows if r["id"] == descriptor]
    row["implementation"]["modules"].remove(module)
    held = tmp_path / "legacy.json"
    held.write_text(json.dumps(rows), encoding="utf-8")
    done = _tool("sets", "--check", "--base", BASE, "--legacy", str(held))
    assert done.returncode == 1
    assert done.stdout.startswith("sets --check FAIL: ") and assertion in done.stdout


def test_t1_falsifier_t2a(facts: w5.Facts) -> None:
    broken = copy.deepcopy(facts)
    unit = "src/openflowsheet/models/c1/flash.py"
    run = next(iter(broken["registry"]["measures"]["M5"]))
    broken["registry"]["measures"]["M5"][run]["outcome"] = broken["unit_hashes"][unit][:12]
    (problem,) = w5.assertions(broken)["S5 T-2a"]
    assert problem.startswith(f"{unit}: ") and "registered M2 to M8 value" in problem
    with pytest.raises(w5.RuleError, match="S5 T-2a"):
        w5.checked(broken)


def test_t1_falsifier_a_stale_label_fails_s4(facts: w5.Facts) -> None:
    broken = copy.deepcopy(facts)
    value = broken["registry"]["measures"]["M2"]["m02/C1-FLASH-F1-M02-v1"]
    prefix = w5.prefix_of(facts, "pr-c1-v1")
    value["model_version"] = value["model_version"].replace(prefix, "0" * 12)
    (problem,) = w5.assertions(broken)["S4 registered labels carry the code's [:12]"]
    assert "m02/C1-FLASH-F1-M02-v1" in problem


def test_t1_the_tier_rules_read_m7s_corpus_and_m2(facts: w5.Facts) -> None:
    """Section 4's rules, falsified: without its M7 hits syn001 falls to tier 3; with neither
    a registered label nor an M6 sample, iapws95 falls to tier 2."""
    moved = copy.deepcopy(facts)
    moved["bundle_hits"][w5.prefix_of(facts, "syn001")] = []
    assert w5.provider_tiers(moved)["syn001"] == 3
    prefix = w5.prefix_of(facts, "iapws95-v1")
    for value in moved["registry"]["measures"]["M2"].values():
        value["model_version"] = value["model_version"].replace(prefix, "f" * 12)
    moved["m6_providers"].remove("iapws95-v1")
    assert w5.provider_tiers(moved)["iapws95-v1"] == 2


# -- W5-T2: the per-file reach of section 3.2 ------------------------------------------------------


@pytest.mark.parametrize("name", sorted(REACH))
def test_t2_predict_gives_section_3_2s_counts_and_keys(facts: w5.Facts, name: str) -> None:
    moved, registry = w5.predict(facts, [w5.normalise(name)])
    assert {m: len(keys) for m, keys in moved.items() if keys} == REACH[name]
    assert registry
    assert moved["M9"] == ({w5.normalise(name)} if REACH[name] else set())
    if name in RUNS:
        assert moved["M2"] == moved["M3"] == RUNS[name]
    if name in SAMPLES:
        assert moved["M6"] == {
            f"sample/provider/{SAMPLES[name]}/{kind}" for kind in ("evaluate_phase", "flash")
        }


def test_t2_predict_of_nothing_is_empty(facts: w5.Facts) -> None:
    moved, registry = w5.predict(facts, ["src/openflowsheet/thermo/__init__.py"])
    assert not any(moved.values()) and not registry
    assert w5.f0_line(facts, moved) == (
        "F0 PASS: M1 50/50, M2 61/61, M3 61/61, M4 61/61, M5 61/61, M6 85/85, M7 52/52, "
        "M8 105/105, M9 35/35"
    )


def test_t2_syn001s_reach(facts: w5.Facts) -> None:
    moved, _ = w5.predict(facts, [f"{THERMO}/syn001.py"])
    runs = {r for r in facts["registry"]["measures"]["M2"] if r.split("/")[0] in ("k05", "g8")}
    assert moved["M2"] == moved["M3"] == moved["M7"] == runs and len(runs) == 52
    samples = {k for k in moved["M6"] if k.startswith("sample/")}
    assert (len(samples), len(moved["M6"] - samples)) == (62, 15)


def test_t2_against_log_compares_both_ways(facts: w5.Facts, tmp_path: Path) -> None:
    moved, _ = w5.predict(facts, [f"{THERMO}/pr_c1.py"])
    key = "m02/C1-FLASH-F1-M02-v1"
    lines = [w5.f0_line(facts, moved), "platform ref-x86-64"]
    lines += [f"{m}: {k}: registered 'a', now 'b'" for m, ks in moved.items() for k in ks]
    log = tmp_path / "f0.log"
    log.write_text("\n".join(lines) + "\n", encoding="utf-8")
    assert w5.log_moved(log) == (lines[0], moved)
    assert not w5.differences(moved, w5.log_moved(log)[1], "moved")
    log.write_text("\n".join(line for line in lines if key not in line) + "\n", encoding="utf-8")
    assert w5.differences(moved, w5.log_moved(log)[1], "moved") == [
        f"M2: {key}: predicted, not moved",
        f"M3: {key}: predicted, not moved",
    ]


# -- W5-T6: judge on synthetic registries ----------------------------------------------------------


def _registry_after(facts: w5.Facts, changes: dict[str, list[str]]) -> dict[str, Any]:
    after: dict[str, Any] = copy.deepcopy(facts["registry"])
    for measure, keys in changes.items():
        for key in keys:
            after["measures"][measure][key] = "re-registered"
    return after


def test_t6_judge_on_synthetic_registries(facts: w5.Facts) -> None:
    pr_lib = f"{THERMO}/pr_lib.py"
    predicted, _ = w5.predict(facts, [pr_lib])
    before = facts["registry"]
    assert w5.judge(before, _registry_after(facts, {"M9": [pr_lib]}), predicted) == []
    other = f"{THERMO}/pr_c1.py"
    assert w5.judge(before, _registry_after(facts, {"M9": [pr_lib, other]}), predicted) == [
        f"M9: {other}: moved, not predicted"
    ]
    assert w5.judge(before, before, predicted) == [f"M9: {pr_lib}: predicted, not moved"]
    renamed = _registry_after(facts, {"M9": [pr_lib]})
    renamed["reference_platform"] = "elsewhere"
    assert w5.judge(before, renamed, predicted) == ["reference_platform: changed"]


def test_t6_judge_between_revisions(scratch: Path) -> None:
    """The command line over three synthetic commits on the base: a comment edit of `pr_lib.py`
    with its M9 value and `builtin-sha256.txt` re-registered (PASS), with one more value changed
    (FAIL naming it), and with nothing re-registered (FAIL, predicted, not moved)."""
    pr_lib = f"{THERMO}/pr_lib.py"
    corpus = scratch / w5.CORPUS_FILE
    registered = json.loads(corpus.read_text(encoding="utf-8"))

    def commit(values: dict[str, str]) -> str:
        _git("checkout", "-q", "--detach", BASE, cwd=scratch)
        _append(scratch, pr_lib, COMMENT)
        document = copy.deepcopy(registered)
        document["measures"]["M9"].update(values)
        corpus.write_text(json.dumps(document, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        if values:
            (scratch / w5.REGISTRY_CONSTANT).write_text("2" * 64 + "\n", encoding="utf-8")
        paths = (pr_lib, w5.CORPUS_FILE, w5.REGISTRY_CONSTANT)
        return _commit(scratch, "synthetic re-registration", *paths)

    other = "src/openflowsheet/models/c1/feed.py"
    cases = [
        ({pr_lib: "0" * 64}, 0, "judge PASS: "),
        ({pr_lib: "0" * 64, other: "1" * 64}, 1, f"M9: {other}: moved, not predicted"),
        ({}, 1, f"M9: {pr_lib}: predicted, not moved"),
    ]
    for values, code, expected in cases:
        after = commit(values)
        done = _tool("--tree", str(scratch), "judge", "--before", BASE, "--after", after)
        assert done.returncode == code, done.stdout
        assert expected in done.stdout


# -- W5-T7: coverage on scratch trees --------------------------------------------------------------


def test_t7_coverage_is_0_at_the_base(scratch: Path) -> None:
    done = _tool("--tree", str(scratch), "coverage", "--base", BASE)
    assert done.returncode == 0, done.stdout
    assert done.stdout.startswith("coverage: 0 new edge(s) outside a hash scope, 0 retarget(s)")


def test_t7_a_new_import_of_an_unhashed_function_is_1(scratch: Path) -> None:
    _append(scratch, "thermo/pr_lib.py", "from openflowsheet.canonical import file_sha256\n")
    done = _tool("--tree", str(scratch), "coverage", "--base", BASE)
    assert done.returncode == 1
    lines = done.stdout.splitlines()
    assert lines[0] == (
        f"EDGE {THERMO}/pr_lib.py -> src/openflowsheet/canonical.py (file_sha256): "
        "outside its scope"
    )
    assert lines[-1].startswith("coverage: 1 new edge(s) outside a hash scope, 0 retarget(s)")


def test_t7_a_retarget_through_a_re_export_is_0_and_listed(scratch: Path) -> None:
    index = scratch / "src/openflowsheet/assessment/cost/index.py"
    old = "from openflowsheet.assessment.program import Limitation, Refusal\n"
    new = (
        "from openflowsheet.assessment.linearization import Refusal\n"
        "from openflowsheet.assessment.program import Limitation\n"
    )
    text = index.read_text(encoding="utf-8")
    assert text.count(old) == 1
    index.write_text(text.replace(old, new), encoding="utf-8")
    done = _tool("--tree", str(scratch), "coverage", "--base", BASE)
    assert done.returncode == 0, done.stdout
    assert done.stdout.splitlines() == [
        "RETARGET src/openflowsheet/assessment/cost/index.py: Refusal from "
        "openflowsheet.assessment.program -> openflowsheet.assessment.linearization",
        "coverage: 0 new edge(s) outside a hash scope, 1 retarget(s), 1 edited hashed file(s); "
        "M9 key set equal to base (35)",
    ]


def test_t7_a_name_that_was_not_re_exported_is_a_hole(scratch: Path) -> None:
    """R4's object-identity test, falsified: a name `index.py` never took from a module at the
    base is a new edge, not a retarget."""
    _append(
        scratch,
        "assessment/cost/index.py",
        "from openflowsheet.assessment.linearization import Refusal, feasibility_tolerance\n",
    )
    done = _tool("--tree", str(scratch), "coverage", "--base", BASE)
    assert done.returncode == 1
    assert done.stdout.splitlines()[-1].startswith("coverage: 1 new edge(s)")


INDEX = "src/openflowsheet/assessment/cost/index.py"
PROGRAM = "src/openflowsheet/assessment/program.py"
MOVED = '\n\ndef w5_moved() -> None:\n    """Moved out of a hashed file."""\n'


def _summary(edges: int, retargets: int = 0, edited: int = 1) -> str:
    return (
        f"coverage: {edges} new edge(s) outside a hash scope, {retargets} retarget(s), "
        f"{edited} edited hashed file(s); M9 key set equal to base (35)"
    )


def test_t7_a_function_moved_into_an_imported_module_is_a_hole(scratch: Path) -> None:
    """Review R-W5-WO0, fix 1: `index.py` imports from `program.py` at the base; a function
    `program.py` gains and `index.py` now imports is a new (module, name) pair outside its hash
    scope, not importable from that module at the base: a hole."""
    _append(scratch, PROGRAM, MOVED)
    _append(scratch, INDEX, "from openflowsheet.assessment.program import w5_moved\n")
    done = _tool("--tree", str(scratch), "coverage", "--base", BASE)
    assert done.returncode == 1, done.stdout
    assert done.stdout.splitlines() == [
        f"EDGE {INDEX} -> {PROGRAM} (w5_moved): outside its scope",
        _summary(1),
    ]


def test_t7_a_name_importable_at_the_base_from_an_imported_module_is_admitted(
    scratch: Path,
) -> None:
    _append(scratch, INDEX, "from openflowsheet.assessment.program import CONTRIBUTOR_ORDER\n")
    done = _tool("--tree", str(scratch), "coverage", "--base", BASE)
    assert done.returncode == 0, done.stdout
    assert done.stdout.splitlines() == [
        f"NAME {INDEX}: CONTRIBUTOR_ORDER from openflowsheet.assessment.program, "
        "importable from it at base",
        _summary(0),
    ]


def test_t7_coverage_judges_the_head_commit(scratch: Path) -> None:
    """Review R-W5-WO0, fix 2: `--head REV` judges that commit, not the working tree, so the gate
    and W5-S3 read the same E. The hole is committed and the working tree put back at the base:
    the working tree reports 0, the commit 1."""
    _append(scratch, PROGRAM, MOVED)
    _append(scratch, INDEX, "from openflowsheet.assessment.program import w5_moved\n")
    _commit(scratch, "a hole", PROGRAM, INDEX)
    _git("checkout", "-q", BASE, "--", PROGRAM, INDEX, cwd=scratch)
    working = _tool("--tree", str(scratch), "coverage", "--base", BASE)
    assert working.returncode == 0, working.stdout
    assert working.stdout.splitlines() == [_summary(0, edited=0)]
    done = _tool("--tree", str(scratch), "coverage", "--base", BASE, "--head", "HEAD")
    assert done.returncode == 1, done.stdout
    assert done.stdout.splitlines() == [
        f"EDGE {INDEX} -> {PROGRAM} (w5_moved): outside its scope",
        _summary(1),
    ]


def test_t1_s2_and_s4_run_only_at_a_base(scratch: Path) -> None:
    """Review R-W5-WO0, fix 2: at a step after a tier 1 split (a new module in `cost/`) S2 fails,
    and after a tier 3 edit (`pr_c1.py`) S4 fails, until K. `--step` skips both and says so."""
    split = scratch / "src/openflowsheet/assessment/cost/w5_split.py"
    split.write_text('"""A tier 1 split\'s new module."""\n', encoding="utf-8")
    _append(scratch, "thermo/pr_c1.py", COMMENT)
    done = _tool("--tree", str(scratch), "sets", "--check")
    assert done.returncode == 1, done.stdout
    assert "S2 implementation sets equal the generator's: core:functional_contributor:cost" in (
        done.stdout
    )
    assert "S4 registered labels carry the code's [:12]: M2 m02/C1-FLASH-F1-M02-v1" in done.stdout
    step = _tool("--tree", str(scratch), "sets", "--check", "--step")
    assert step.returncode == 0, step.stdout
    assert step.stdout.strip() == (
        "sets --check PASS at a step (S2, S4 not checked): |R| 51, |F| 35, F subset of R, "
        "tiers 16/28/6/1, T-2a holds (27 unit hashes)"
    )


# -- R1's refusals (review R-W5-WO0, fix 3) --------------------------------------------------------

SYN001 = f"{THERMO}/syn001.py"
PR_C1 = f"{THERMO}/pr_c1.py"


def test_r1_predict_refuses_tier_4_and_m7() -> None:
    done = _tool("predict", "--base", BASE, "--files", "thermo/syn001.py")
    assert done.returncode == 1, done.stdout
    assert done.stdout.splitlines() == [
        f"REFUSED {SYN001}: tier 4 (excluded), refused by R1",
        "REFUSED M7: 52 key(s) predicted to move, refused by R1",
        "predict FAIL: E refused (2 problem(s))",
    ]


def test_r1_predict_refuses_a_file_above_max_tier() -> None:
    done = _tool("predict", "--base", BASE, "--files", "thermo/pr_c1.py", "--max-tier", "2")
    assert done.returncode == 1, done.stdout
    assert done.stdout.splitlines() == [
        f"REFUSED {PR_C1}: tier 3 (run identity), above --max-tier 2",
        "predict FAIL: E refused (1 problem(s))",
    ]
    assert _tool("predict", "--base", BASE, "--files", "thermo/pr_c1.py").returncode == 0


def test_r1_a_nonempty_m7_prediction_is_refused_alone(facts: w5.Facts) -> None:
    moved: w5.Moved = {measure: set() for measure in w5.MEASURES}
    moved["M7"] = {"bundle"}
    assert w5.refusals(facts, [], moved, 3) == ["M7: 1 key(s) predicted to move, refused by R1"]


def _re_registered(scratch: Path, facts: w5.Facts, edited: str) -> str:
    """A synthetic K on the base: a comment edit of `edited` and every predicted value of
    `corpus.json` re-registered."""
    _git("checkout", "-q", "--detach", BASE, cwd=scratch)
    _append(scratch, edited, COMMENT)
    predicted, _ = w5.predict(facts, [edited])
    corpus = scratch / w5.CORPUS_FILE
    document = json.loads(corpus.read_text(encoding="utf-8"))
    for measure, keys in predicted.items():
        for key in keys:
            document["measures"][measure][key] = "re-registered"
    corpus.write_text(json.dumps(document, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return _commit(scratch, "synthetic re-registration", edited, w5.CORPUS_FILE)


def test_r1_judge_refuses_a_k_re_registering_m7(facts: w5.Facts, scratch: Path) -> None:
    """The reviewer's falsifier: a K re-registering all 52 M7 keys (with every other predicted
    key of `syn001.py`) passed W5-K2; R1 refuses it. And a tier 3 K above `--max-tier 2`."""
    after = _re_registered(scratch, facts, SYN001)
    done = _tool("--tree", str(scratch), "judge", "--before", BASE, "--after", after)
    assert done.returncode == 1, done.stdout
    assert done.stdout.splitlines()[-1] == "judge FAIL: E refused (2 problem(s))"
    assert "REFUSED M7: 52 key(s) predicted to move, refused by R1" in done.stdout
    after = _re_registered(scratch, facts, PR_C1)
    arguments = ("--tree", str(scratch), "judge", "--before", BASE, "--after", after)
    done = _tool(*arguments, "--max-tier", "2")
    assert done.returncode == 1, done.stdout
    assert done.stdout.splitlines() == [
        f"REFUSED {PR_C1}: tier 3 (run identity), above --max-tier 2",
        "judge FAIL: E refused (1 problem(s))",
    ]


# -- W5-S4 and the K-side table diff (review R-W5-WO0, fix 4) --------------------------------------

PR_LIB = f"{THERMO}/pr_lib.py"
#: `PrLibProvider.describe()`'s reference convention, and the changed string.
DESCRIBE = (
    "data_sha256=load_records().sha256,\n            reference_convention=REFERENCE_CONVENTION,"
)
CHANGED = 'data_sha256=load_records().sha256,\n            reference_convention="w5",'
REGISTRY = (*w5.TABLE_FILES.values(), w5.DIGEST_FILE, w5.REGISTRY_CONSTANT)


def _write_registry(tree: Path) -> None:
    """The tree's own generator, `--write`."""
    subprocess.run(
        [sys.executable, "scripts/registry_builtin.py", "--write"],
        cwd=tree,
        env={**os.environ, "PYTHONPATH": str(tree / "src")},
        capture_output=True,
        check=True,
    )


def _replace(tree: Path, name: str, old: str, new: str) -> None:
    path = tree / name
    text = path.read_text(encoding="utf-8")
    assert text.count(old) == 1
    path.write_text(text.replace(old, new), encoding="utf-8")


def _k(scratch: Path, edited: Sequence[str], m9: Sequence[str] = ()) -> str:
    """K: the edits made, the registry regenerated, the M9 values of `m9` re-registered."""
    _write_registry(scratch)
    corpus = scratch / w5.CORPUS_FILE
    document = json.loads(corpus.read_text(encoding="utf-8"))
    document["measures"]["M9"].update(dict.fromkeys(m9, "3" * 64))
    corpus.write_text(json.dumps(document, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return _commit(scratch, "synthetic K", *edited, *REGISTRY, w5.CORPUS_FILE)


def _judge(scratch: Path, after: str) -> subprocess.CompletedProcess[str]:
    return _tool("--tree", str(scratch), "judge", "--before", BASE, "--after", after)


def test_s4_a_describe_change_regenerated_fails_judge(scratch: Path) -> None:
    """The reviewer's falsifier: a `describe()` string changed in a batch N file, the generator's
    `--write` run, M9 re-registered: K moves a payload pointer no rule predicts. Tier 1
    contributors have no `describe()` the generator reads (their payload is `{}`), so the file is
    `pr_lib.py`, the batch N file whose `describe()` is a table row."""
    _replace(scratch, PR_LIB, DESCRIBE, CHANGED)
    done = _judge(scratch, _k(scratch, [PR_LIB], [PR_LIB]))
    assert done.returncode == 1, done.stdout
    assert done.stdout.splitlines()[:-1] == [
        "legacy.json:/4/payload/reference_convention: moved, not predicted",
        "tables.sha256: moved, not predicted",
    ]


def test_s4_the_describe_change_at_a_step_fails_against_tables(scratch: Path) -> None:
    """The same change at a step (committed, not regenerated): HEAD's generator differs from the
    committed registry on the payload pointer. A comment edit passes."""
    _append(scratch, PR_LIB, COMMENT)
    _commit(scratch, "a comment", PR_LIB)
    arguments = ("--tree", str(scratch), "predict", "--base", BASE, "--against-tables")
    done = _tool(*arguments)
    assert done.returncode == 0, done.stdout
    assert done.stdout.splitlines()[-1] == "predict --against-tables PASS: M9 1"
    _replace(scratch, PR_LIB, DESCRIBE, CHANGED)
    _commit(scratch, "a describe change", PR_LIB)
    done = _tool(*arguments)
    assert done.returncode == 1, done.stdout
    assert "legacy.json:/4/payload/reference_convention: moved, not predicted" in done.stdout
    assert "tables.sha256: moved, not predicted" in done.stdout


def test_s4_wo_n4s_factory_switch_is_predicted(scratch: Path) -> None:
    """WO-N4: the units' factory constant switched in the generator. Regenerated: PASS on 30
    factory pointers; not regenerated: each predicted, not moved."""
    _replace(
        scratch,
        w5.GENERATOR,
        '{"module": BINDER, "attribute": "MODEL_BUILDERS"',
        '{"module": "openflowsheet.application.model_builders", "attribute": "MODEL_BUILDERS"',
    )
    _commit(scratch, "the switch, not regenerated", w5.GENERATOR)
    stale = _judge(scratch, "HEAD")
    assert stale.returncode == 1, stale.stdout
    assert (
        sum(
            line.endswith("/factory/module: predicted, not moved")
            for line in stale.stdout.splitlines()
        )
        == 30
    )
    done = _judge(scratch, _k(scratch, []))
    assert done.returncode == 0, done.stdout
    assert done.stdout.splitlines()[-1].endswith("|E| 0; predicted none; tables 30 pointer(s)")


def test_s4_a_tier_1_split_moves_the_contributors_modules(scratch: Path) -> None:
    """A new module in `cost/` (a tier 1 split): `core.json`'s cost and derived `modules` gain it;
    a wrong expected value fails."""
    split = "src/openflowsheet/assessment/cost/w5_split.py"
    (scratch / split).write_text('"""A tier 1 split\'s new module."""\n', encoding="utf-8")
    done = _judge(scratch, _k(scratch, [split]))
    assert done.returncode == 0, done.stdout
    assert done.stdout.splitlines()[-1].endswith("tables 2 pointer(s)")
    tables = w5.held_tables(scratch, BASE)
    expected, still_open = w5.predict_tables(tables, [split], set(), {split})
    assert sorted(expected) == [f"core.json:/{i}/implementation/modules" for i in (0, 1)]
    assert (
        "openflowsheet/assessment/cost/w5_split.py"
        in expected["core.json:/0/implementation/modules"]
    )
    assert not still_open
    after = w5.held_tables(scratch, "HEAD")
    wrong = {**expected, "core.json:/0/implementation/modules": []}
    assert w5.table_problems(wrong, {}, True, tables, after) == [
        f"core.json:/0/implementation/modules: predicted [], found "
        f"{json.dumps(after['core'][0]['implementation']['modules'])}"
    ]


def test_s4_a_removed_unit_module_is_unpredicted(scratch: Path) -> None:
    """A file of R removed outside the ruling's rules: its row's `modules` is open, and predict
    fails naming it."""
    sink = "src/openflowsheet/models/c1/sink.py"
    _git("rm", "-q", sink, cwd=scratch)
    _git("-c", "user.name=w5", "-c", "user.email=w5@invalid", "commit", "-qm", "rm", cwd=scratch)
    done = _tool("--tree", str(scratch), "predict", "--base", BASE)
    assert done.returncode == 1, done.stdout
    lines = done.stdout.splitlines()
    (opened,) = [line for line in lines if line.startswith("TABLE ")]
    assert opened.startswith("TABLE legacy.json:/") and opened.endswith(
        "/implementation/modules: open"
    )
    pointer = opened.removeprefix("TABLE ").removesuffix(": open")
    assert f"{pointer}: unpredicted (openflowsheet/models/c1/sink.py removed; " in done.stdout
    assert lines[-1].startswith("predict FAIL: 1 unpredicted table pointer(s); ")


# -- review R-W5-WO0, fix 5 ------------------------------------------------------------------------


def test_t2_against_log_through_the_command(facts: w5.Facts, tmp_path: Path) -> None:
    """`predict --against-log` as the gate runs it: PASS on the predicted keys and line; a key
    the log moved that was not predicted; a summary line that differs."""
    moved, _ = w5.predict(facts, [PR_C1])
    lines = [w5.f0_line(facts, moved), "platform ref-x86-64"]
    lines += [f"{m}: {k}: registered 'a', now 'b'" for m, ks in moved.items() for k in sorted(ks)]
    log = tmp_path / "f0.log"
    arguments = ("predict", "--base", BASE, "--files", "thermo/pr_c1.py", "--against-log", str(log))
    log.write_text("\n".join(lines) + "\n", encoding="utf-8")
    done = _tool(*arguments)
    assert done.returncode == 0, done.stdout
    assert done.stdout.splitlines()[-1] == (
        f"predict --against-log PASS: M2 1, M3 1, M6 2, M9 1; log {lines[0]}"
    )
    extra = f"M9: {PR_LIB}: registered 'a', now 'b'"
    log.write_text("\n".join([*lines, extra]) + "\n", encoding="utf-8")
    done = _tool(*arguments)
    assert done.returncode == 1, done.stdout
    assert done.stdout.splitlines()[-2:] == [
        f"M9: {PR_LIB}: moved, not predicted",
        f"predict --against-log FAIL (1 difference(s)): M2 1, M3 1, M6 2, M9 1; log {lines[0]}",
    ]
    wrong = lines[0].replace("M9 FAIL 1/35", "M9 35/35")
    log.write_text("\n".join([wrong, *lines[1:]]) + "\n", encoding="utf-8")
    done = _tool(*arguments)
    assert done.returncode == 1, done.stdout
    assert done.stdout.splitlines()[-2] == (
        f"summary line: log {wrong!r}, predicted {'predicted ' + lines[0]!r}"
    )


def test_t1_falsifiers_s3(facts: w5.Facts) -> None:
    """S3, falsified: a hash site without a provider id; a provider with two values."""
    broken = copy.deepcopy(facts)
    site = next(path for path in sorted(broken["sites"]) if path.endswith("/pr_lib.py"))
    broken["sites"][site]["provider_id"] = None
    problems = w5.assertions(broken)["S3 attribution"]
    assert f"{site}: hash site without PROVIDER_ID" in problems
    broken = copy.deepcopy(facts)
    broken["prefixes"]["pr-c1-v1"].append("0" * 12)
    problems = w5.assertions(broken)["S3 attribution"]
    assert any(p.startswith("pr-c1-v1: 2 implementation_sha256 values") for p in problems)
    with pytest.raises(w5.RuleError, match="S3 attribution"):
        w5.checked(broken)


def test_t1_falsifiers_s6(facts: w5.Facts, monkeypatch: pytest.MonkeyPatch) -> None:
    """S6, falsified on the check itself (the tier rules partition R by construction): a file
    dropped, a file of F placed in tier 1, an unattributed file placed in tier 3."""
    right = w5.tiers(facts)
    unit = "src/openflowsheet/models/c1/flash.py"
    cases = [
        ({**right, 1: right[1][1:]}, "tiers hold 50 files, R 51"),
        ({**right, 1: [*right[1], unit], 2: [f for f in right[2] if f != unit]}, "not F"),
        ({**right, 2: [f for f in right[2] if f != unit], 3: [*right[3], unit]}, "no provider"),
    ]
    for tiered, expected in cases:
        monkeypatch.setattr(w5, "tiers", lambda _facts, tiered=tiered: tiered)
        problems = w5.assertions(facts)["S6 the tiers partition R"]
        assert any(expected in p for p in problems), problems


def test_t7_a_cost_file_importing_from_lca_is_a_hole(scratch: Path) -> None:
    """Reading (b) of R4's hash scope: the intersection of the identity sets holding the file,
    so the cost contributors' hash does not cover `lca/`."""
    sets = "src/openflowsheet/assessment/cost/sets.py"
    _append(scratch, sets, "from openflowsheet.assessment.lca.impact import categories_of\n")
    done = _tool("--tree", str(scratch), "coverage", "--base", BASE)
    assert done.returncode == 1, done.stdout
    assert done.stdout.splitlines() == [
        f"EDGE {sets} -> src/openflowsheet/assessment/lca/impact.py (categories_of): "
        "outside its scope",
        _summary(1),
    ]


def test_t7_a_unit_module_importing_a_sibling_unit_is_a_hole(scratch: Path) -> None:
    """Reading (b): a unit module's own `artifact_hash` holds only the file."""
    heater = "src/openflowsheet/models/c1/heater.py"
    _append(scratch, heater, "from openflowsheet.models.c1.feed import PORTS as FEED_PORTS\n")
    done = _tool("--tree", str(scratch), "coverage", "--base", BASE)
    assert done.returncode == 1, done.stdout
    assert done.stdout.splitlines() == [
        f"EDGE {heater} -> src/openflowsheet/models/c1/feed.py (PORTS): outside its scope",
        _summary(1),
    ]


def test_t7_a_changed_m9_key_set_exits_1(scratch: Path) -> None:
    """W5-S7: a new unit module (it hashes its own `__file__`) adds an M9 key; no hashed file is
    edited, and coverage still exits 1."""
    unit = "src/openflowsheet/models/c1/w5_unit.py"
    (scratch / unit).write_text(
        '"""A new unit module."""\n\nfrom pathlib import Path\n\n'
        "from openflowsheet.canonical import file_sha256\n\n\n"
        "def _artifact_hash() -> str:\n    return file_sha256(Path(__file__))\n",
        encoding="utf-8",
    )
    done = _tool("--tree", str(scratch), "coverage", "--base", BASE)
    assert done.returncode == 1, done.stdout
    assert done.stdout.splitlines() == [
        "coverage: 0 new edge(s) outside a hash scope, 0 retarget(s), 0 edited hashed file(s); "
        f"M9 key set DIFFERS: added ['{unit}'], removed [] (36)"
    ]
