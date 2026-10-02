"""T08.B50's content clause, exactly (build-first spec Amendment 4, R-144; verdicts finding G2).

"The content differences from `c7bbc98` served by `list_models` and `get_project`, excluding
`server.package_version`, are exactly `syn001.kinetic_cstr` in `list_models` and `T08-ptc-v1`,
`T08-warm-v1` in `get_project.solve_policies`."

`c7bbc98`'s content is `tests/fixtures/t08/b50-c7bbc98-surface.json`, served by that commit's own
code on a fresh project (`scripts/t08_b50_surface_fixture.py`). It is checked here against what
`v17-c2` recorded verbatim at `c7bbc98`: every `list_models` result in its transcripts, and the
server-determined members of every `get_project` result (the rest describe the campaign's seeded
project, not the build). Today's content is served by this build on a fresh project created the
same way; with the version member and the three named entries taken out, the two are equal, and
each named entry is there exactly once. (The generator, run without `--write`, re-serves `c7bbc98`
from a temporary worktree and compares; that is not run here, since it writes to `.git`.)
"""

from __future__ import annotations

import copy
import json
import sys
from typing import Any

import pytest
from conftest import REPO_ROOT

from openflowsheet.application.local import LocalApplication
from openflowsheet.application.operations import dispatch

sys.path.insert(0, str(REPO_ROOT / "scripts"))
import t08_b50_surface_fixture as generator  # noqa: E402

FIXTURE = json.loads(generator.FIXTURE.read_text(encoding="utf-8"))
V17_C2 = REPO_ROOT / "benchmarks" / "t07" / "v17" / "runs" / "v17-c2"
#: B50's named differences.
NEW_MODELS = ("syn001.kinetic_cstr",)
NEW_POLICIES = ("T08-ptc-v1", "T08-warm-v1")
#: `get_project`'s members that the server determines, whatever the project's state.
SERVER_MEMBERS = ("default_policy_id", "server", "solve_policies")


def _v17_c2_results(operation: str) -> list[Any]:
    """Every result `v17-c2`'s sessions received from `operation`, parsed."""
    found: list[Any] = []
    for path in sorted(V17_C2.glob("*/transcript.jsonl")):
        calls: set[str] = set()
        for line in path.read_text(encoding="utf-8").splitlines():
            message = json.loads(line).get("message")
            content = message.get("content") if isinstance(message, dict) else None
            for item in content if isinstance(content, list) else []:
                if item.get("type") == "tool_use" and item["name"].endswith(f"__{operation}"):
                    calls.add(item["id"])
                if item.get("type") == "tool_result" and item.get("tool_use_id") in calls:
                    found.append(json.loads(item["content"]))
    return found


def test_the_fixture_is_c7bbc98s_served_content() -> None:
    assert FIXTURE["commit"] == generator.COMMIT
    for path in sorted(V17_C2.glob("*/run.json")):
        assert json.loads(path.read_text("utf-8"))["git"] == {
            "commit": generator.COMMIT,
            "dirty": False,
        }, path
    models = _v17_c2_results("list_models")
    projects = _v17_c2_results("get_project")
    # The calls the 30 sessions made (counted in the committed transcripts).
    assert (len(models), len(projects)) == (15, 24)
    assert all(result == FIXTURE["list_models"] for result in models)
    for result in projects:
        assert {m: result[m] for m in SERVER_MEMBERS} == {
            m: FIXTURE["get_project"][m] for m in SERVER_MEMBERS
        }


@pytest.fixture(scope="module")
def served(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    project = tmp_path_factory.mktemp("b50") / "p"
    LocalApplication.create(project, project_id=generator.PROJECT_ID).close()
    with LocalApplication.open(project) as application:
        return {name: dispatch(application, name, {}) for name in ("get_project", "list_models")}


def _taken_out(entries: list[dict[str, Any]], key: str, names: tuple[str, ...]) -> list[Any]:
    """`entries` without those whose `key` is one of `names`, each of which occurs once."""
    assert sorted(entry[key] for entry in entries if entry[key] in names) == sorted(names)
    return [entry for entry in entries if entry[key] not in names]


def test_b50_list_models_differs_by_the_kinetic_cstr_only(served: dict[str, Any]) -> None:
    today = copy.deepcopy(served["list_models"])
    today["models"] = _taken_out(today["models"], "model_id", NEW_MODELS)
    assert today == FIXTURE["list_models"]


def test_b50_get_project_differs_by_the_two_policies_and_the_version_only(
    served: dict[str, Any],
) -> None:
    today, then = copy.deepcopy(served["get_project"]), copy.deepcopy(FIXTURE["get_project"])
    for document in (today, then):
        del document["server"]["package_version"]
    today["solve_policies"] = _taken_out(today["solve_policies"], "policy_id", NEW_POLICIES)
    assert today == then
