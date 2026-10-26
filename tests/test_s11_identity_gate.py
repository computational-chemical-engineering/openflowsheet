"""S11 WO-0 — gate G1's rule (S11 design note §6.2 G1, §2.2), as `scripts/s11_identity.py`
applies it.

The gate itself runs S08's 52 configurations, the T05/T05b `ph_state` calls and every
`bind_revision_flowsheet` call of the whole suite on the base and on the branch; these tests pin
that its verdict passes on equal records (and on differences confined to §8.3's amended tests or
to keys new on the branch) and fails on every other outcome, so that the gate cannot report
success by construction, and that the recorder's digest reads what §6.2 says it reads.
"""

from __future__ import annotations

import ast
import copy
import subprocess
import sys
from dataclasses import replace
from typing import Any

import pytest
from conftest import REPO_ROOT
from t07_corpus import CORPUS

sys.path.insert(0, str(REPO_ROOT / "scripts"))
import s11_identity  # noqa: E402
import s11_identity_recorder as recorder  # noqa: E402

from openflowsheet.application.binding import Unbound  # noqa: E402
from openflowsheet.application.revision_binding import (  # noqa: E402
    RevisionBinding,
    bind_revision_flowsheet,
)

_AMENDED = "tests/test_t05_w1b_revision.py::test_builders_hold_the_thirteen_models_of_the_table"


def _trees() -> tuple[dict[str, Any], dict[str, Any]]:
    """A base and a branch with equal records in all three families."""
    columns = {f"X.{index}": f"d-{index}" for index in range(52)}
    base = {
        "ab": {
            "columns": columns,
            "stage_a": {"X.1": "s-1"},
            "ph_state": {"tests/test_t05_a.py::t#0": "p0", "tests/test_t05_a.py::t#1": "p1"},
            "pytest_exit": 0,
        },
        "c": {
            "records": {
                "tests/test_a.py::t#0": "c0",
                "tests/test_a.py::t[x]#0": "c1",
                f"{_AMENDED}#0": "c2",
            },
            "exit": [0, 0],
        },
    }
    return base, copy.deepcopy(base)


def test_g1_equal_records_pass_and_count_every_judged_key() -> None:
    base, branch = _trees()
    passed, line = s11_identity.verdict(base, branch)
    # 52 configurations, one stage_a, two ph_state, two judged bindings (the amended one is not).
    assert (passed, line) == (True, "S11-IDENTITY PASS n=57 changed=[]")


def _set(path: tuple[Any, ...], value: Any) -> Any:
    def mutate(tree: dict[str, Any]) -> None:
        *head, last = path
        for part in head:
            tree = tree[part]
        tree[last] = value

    return mutate


def _drop(path: tuple[Any, ...]) -> Any:
    def mutate(tree: dict[str, Any]) -> None:
        *head, last = path
        for part in head:
            tree = tree[part]
        del tree[last]

    return mutate


@pytest.mark.parametrize(
    ("mutate", "named"),
    [
        (_set(("c", "records", "tests/test_a.py::t#0"), "moved"), "C:tests/test_a.py::t#0"),
        (_set(("c", "records", "tests/test_a.py::t[x]#0"), "moved"), "C:tests/test_a.py::t[x]#0"),
        (_drop(("c", "records", "tests/test_a.py::t#0")), "C base-only keys (1)"),
        (_set(("c", "exit"), [0, 1]), "C branch shards [1] exited non-zero"),
        (_set(("c", "records"), {f"{_AMENDED}#0": "c2"}), "C recorded no shared binding"),
        (_set(("ab", "columns", "X.3"), "moved"), "A:X.3"),
        (_drop(("ab", "columns", "X.3")), "A keys differ (1)"),
        (_set(("ab", "stage_a", "X.1"), "moved"), "A.stage_a:X.1"),
        (_drop(("ab", "stage_a", "X.1")), "A.stage_a keys differ (1)"),
        (_set(("ab", "ph_state", "tests/test_t05_a.py::t#1"), "moved"), "B:tests/test_t05_a.py"),
        (_set(("ab", "ph_state", "tests/test_t05_a.py::t#2"), "new"), "B keys differ (1)"),
        (_set(("ab", "pytest_exit"), 1), "the branch T05/T05b pytest run exited 1"),
    ],
)
def test_g1_the_verdict_fails_on_any_other_outcome(mutate: Any, named: str) -> None:
    base, branch = _trees()
    mutate(branch)
    passed, line = s11_identity.verdict(base, branch)
    assert not passed
    assert line.startswith("S11-IDENTITY FAIL ")
    assert named in line


def test_g1_a_failed_base_shard_fails() -> None:
    base, branch = _trees()
    base["c"]["exit"] = [2, 0]
    passed, line = s11_identity.verdict(base, branch)
    assert not passed and "C base shards [0] exited non-zero" in line


def test_g1_fifty_one_configurations_fail_even_when_both_trees_agree() -> None:
    base, branch = _trees()
    for tree in (base, branch):
        del tree["ab"]["columns"]["X.0"]
    passed, line = s11_identity.verdict(base, branch)
    assert not passed and "A has 51 configurations, not 52" in line


def test_g1_no_ph_state_call_fails() -> None:
    base, branch = _trees()
    for tree in (base, branch):
        tree["ab"]["ph_state"] = {}
    passed, line = s11_identity.verdict(base, branch)
    assert not passed and "B recorded no ph_state call" in line


def test_g1_amended_tests_and_branch_only_keys_are_not_judged() -> None:
    base, branch = _trees()
    branch["c"]["records"][f"{_AMENDED}#0"] = "moved"  # an amended test's outcome moves
    branch["c"]["records"]["tests/test_s11_new.py::t#0"] = "new"  # a new test
    passed, line = s11_identity.verdict(base, branch)
    assert (passed, line) == (True, "S11-IDENTITY PASS n=57 changed=[]")
    del branch["c"]["records"][f"{_AMENDED}#0"]  # an amended test renamed: base-only
    assert s11_identity.verdict(base, branch) == (True, "S11-IDENTITY PASS n=57 changed=[]")


def test_g1_amended_matches_the_named_test_and_its_parametrisations_only() -> None:
    amended = s11_identity.amended
    assert amended(f"{_AMENDED}#3")
    assert amended(f"{_AMENDED}[case-1]#0")
    assert not amended(f"{_AMENDED}_too#0")
    assert amended("tests/test_t08_w2_unsupported.py::test_anything#0")  # a whole file
    assert amended("tests/test_t08_w2_unsupported.py::TestX::test_y[a]#1")
    assert not amended("tests/test_t08_w2_unsupported_more.py::test_anything#0")
    assert not amended("<outside shard 3>#0")


def test_g1_every_amended_prefix_names_a_test_of_the_base() -> None:
    """§8.3's entries, resolved at the base `8c34ecb0`: each file exists there and each named
    function is a module-level test of it."""
    for prefix in s11_identity.AMENDED_TESTS:
        path, _, name = prefix.partition("::")
        shown = subprocess.run(
            ["git", "show", f"{s11_identity.MERGE_BASE}:{path}"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        if shown.returncode != 0 and "unknown revision" in shown.stderr + shown.stdout:
            pytest.skip(f"the base {s11_identity.MERGE_BASE} is not in this clone")
        assert shown.returncode == 0, f"{path} is not in the base: {shown.stderr}"
        if name:
            tests = {
                node.name
                for node in ast.parse(shown.stdout).body
                if isinstance(node, ast.FunctionDef)
            }
            assert name in tests, prefix


def test_g1_shards_deal_the_base_files_and_put_new_files_in_one_extra_shard(tmp_path: Any) -> None:
    base, branch = tmp_path / "base", tmp_path / "branch"
    for tree, names in ((base, "abcde"), (branch, "abcdfg")):
        (tree / "tests").mkdir(parents=True)
        for name in names:
            (tree / "tests" / f"test_{name}.py").write_text("")
    assert s11_identity.shards(base, branch, 2) == [
        ["tests/test_a.py", "tests/test_c.py"],
        ["tests/test_b.py", "tests/test_d.py"],
        ["tests/test_f.py", "tests/test_g.py"],
    ]


# -- the recorder's digest -----------------------------------------------------------------------


def test_g1_the_hint_is_part_of_the_outcome_though_not_of_unbound_equality() -> None:
    """The WO-0 control's premise: a refusal whose hint differs by one character is equal as an
    `Unbound` (the hint is `compare=False`) but has another digest."""
    one = Unbound("unsupported", "model_unsupported(x)", hint="x binds on the syn001 basis only")
    other = replace(one, hint="x binds on the syn001 basis only.")
    assert one == other
    assert recorder.outcome(one) != recorder.outcome(other)
    assert recorder.outcome(one) != recorder.outcome(replace(one, implicated=("u",)))


def test_g1_a_binding_is_compared_by_its_spec_ids_kinds_and_parameter_bits() -> None:
    binding = bind_revision_flowsheet(CORPUS["SYN-001-nominal"]())
    assert isinstance(binding, RevisionBinding)
    fields = recorder.outcome(binding, binding.revision_sha256)
    assert fields[:2] == ("bound", True)
    assert recorder.outcome(binding, "0" * 64)[1] is False
    assert fields[3] == binding.spec.variable_ids and fields[4] == binding.spec.equation_ids
    name = binding.spec.parameter_ids[0]
    value = float(binding.spec.parameters[name])
    nudged = dict(binding.spec.parameters)
    nudged[name] = value + abs(value) * sys.float_info.epsilon + sys.float_info.min
    moved = replace(binding, spec=replace(binding.spec, parameters=nudged))
    assert recorder.outcome(moved, binding.revision_sha256) != fields
    kinds = dict(binding.spec.row_kinds)
    row = next(iter(kinds))
    kinds[row] = "dimensionless" if kinds[row] != "dimensionless" else "pressure"
    kinded = replace(binding, spec=replace(binding.spec, row_kinds=kinds))
    assert recorder.outcome(kinded, binding.revision_sha256) != fields


def test_g1_the_document_digest_falls_back_for_a_document_with_no_canonical_form() -> None:
    document = CORPUS["SYN-001-nominal"]()
    canonical = recorder.document_digest(document)
    document["broken"] = float("nan")
    assert recorder.document_digest(document) not in (canonical, recorder.document_digest({}))


def test_g1_the_document_digest_marks_the_revision_identifiers_only() -> None:
    """`VOLATILE`: a clock-named revision (`test_t07_r6_replays`) digests as any other name; every
    other field still moves the digest."""
    document = CORPUS["SYN-001-nominal"]()
    digest = recorder.document_digest(document)
    for name in recorder.VOLATILE:
        renamed = {**document, name: "clock-123"}
        assert recorder.document_digest(renamed) == digest
    assert recorder.document_digest({**document, "extra": 1}) != digest
    assert recorder.document_digest({**document, "streams": []}) != digest
