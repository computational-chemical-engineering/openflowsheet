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

The alpha's counterpart (V02 alpha release spec §5.2 MR-7; M07a.A51): the differences from
`c7bbc98`, excluding `server.package_version`, are exactly B50's three named entries plus the v0.2
additions that register entries name (`V02_ADDITIONS`, each with the entry that names it, checked
against the register's text). An addition no entry names fails, and so does a named one that is
not served; each failure names the entry.
"""

from __future__ import annotations

import copy
import dataclasses
import json
import re
import sys
from typing import Any

import pytest
from conftest import REPO_ROOT
from m04_schema_support import M04_MODELS

from openflowsheet.application import local
from openflowsheet.application.local import LocalApplication
from openflowsheet.application.operations import dispatch

sys.path.insert(0, str(REPO_ROOT / "scripts"))
import t08_b50_surface_fixture as generator  # noqa: E402

FIXTURE = json.loads(generator.FIXTURE.read_text(encoding="utf-8"))
V17_C2 = REPO_ROOT / "benchmarks" / "t07" / "v17" / "runs" / "v17-c2"
#: B50's named differences.
NEW_MODELS = ("syn001.kinetic_cstr",)
#: MR-7's register-sourced v0.2 additions: per `c7bbc98` content member, each id with the register
#: entry that names it (R-230: M02's six PR units; R-231: the two bindable C1 reactor ids). v0.2
#: adds no solve policy. The join that serves them is R-280's.
V02_ADDITIONS: dict[str, dict[str, str]] = {
    "models": {
        "c1.adiabatic_mixer": "R-230",
        "c1.feed_source": "R-230",
        "c1.product_sink": "R-230",
        "c1.stream_splitter": "R-230",
        "c1.tp_flash": "R-230",
        "c1.tp_heater": "R-230",
        "c1.reactor": "R-231",
        "c1.reactor_standin": "R-231",
        # M04's surrogate (W27 Amendment 3; R-295), added at the alpha's merge into main.
        "c1.reactor_surrogate": "R-301",
        # S11's column (ADR 0050, R-810; design note §8.3, I1): registered on purpose.
        "syn001.column": "R-805",
        # S11's `thermal.*` family (ADR 0051 D6, R-816; units design §8.3, I1b): registered on
        # purpose; R-816's "Amended 2026-10-27" line spells the ids.
        **{
            f"thermal.{name}": "R-816"
            for name in ("compressor", "flash", "heater", "mixer", "pump", "turbine", "valve")
        },
    },
    "solve_policies": {},
}
#: M02's join (R-280 (b); R-234's method): the eight C1 models `list_models` serves since M02,
#: stripped before B50's clause is judged, so the clause stands as T08 registered it.
#: S11's addition (R-805), stripped like M02's and M04's.
S11_MODELS = (
    "syn001.column",
    *(m for m in sorted(V02_ADDITIONS["models"]) if m.startswith("thermal.")),
)
M02_MODELS = tuple(sorted(set(V02_ADDITIONS["models"]) - set(M04_MODELS) - set(S11_MODELS)))
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
    """With M04's surrogate (R-295, R-301), M02's eight C1 models and S11's column (R-805, R-810)
    stripped (each exactly once; R-280 (b), the decomposition onto the pre-M02 surface),
    `list_models` differs from `c7bbc98`'s by the kinetic CSTR only."""
    today = copy.deepcopy(served["list_models"])
    today["models"] = _taken_out(today["models"], "model_id", M04_MODELS)
    today["models"] = _taken_out(today["models"], "model_id", M02_MODELS)
    today["models"] = _taken_out(today["models"], "model_id", S11_MODELS)
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


# --- The alpha's counterpart (MR-7; M07a.A51) ------------------------------------------------

REGISTER = REPO_ROOT / "docs" / "decision-register.md"
#: (operation, content member, entry key, B50's named additions to that member).
SURFACE = (
    ("list_models", "models", "model_id", NEW_MODELS),
    ("get_project", "solve_policies", "policy_id", NEW_POLICIES),
)


def _register_entry(entry_id: str) -> str:
    """The register's text for `entry_id`, from its heading to the next heading."""
    match = re.search(
        rf"^## {re.escape(entry_id)} — .*?(?=^## |\Z)",
        REGISTER.read_text(encoding="utf-8"),
        flags=re.MULTILINE | re.DOTALL,
    )
    assert match is not None, entry_id
    return match.group(0)


def mr7_problems(served: dict[str, Any]) -> list[str]:
    """MR-7's clause on `served` (`get_project` and `list_models` on a fresh project): one line per
    failure, naming the entry; empty iff the clause holds."""
    today, then = copy.deepcopy(served), copy.deepcopy(FIXTURE)
    for documents in (today, then):
        del documents["get_project"]["server"]["package_version"]
    problems: list[str] = []
    for operation, member, key, named in SURFACE:
        additions = {**dict.fromkeys(named, "T08.B50"), **V02_ADDITIONS[member]}
        ids = [entry[key] for entry in today[operation][member]]
        before = {entry[key] for entry in then[operation][member]}
        for entry_id, source in additions.items():
            count = ids.count(entry_id)
            if count != 1:
                problems.append(f"{member}: `{entry_id}` ({source}) served {count} times, not once")
        for entry_id in sorted(set(ids) - before - set(additions)):
            problems.append(f"{member}: `{entry_id}` is served, not c7bbc98's, named by no entry")
        for entry_id in sorted(before - set(ids)):
            problems.append(f"{member}: c7bbc98's `{entry_id}` is not served")
        # What remains is compared entry by entry: the entries both serve, and the other members.
        today[operation][member] = [
            entry for entry in today[operation][member] if entry[key] in before
        ]
        then[operation][member] = [
            entry for entry in then[operation][member] if entry[key] in set(ids)
        ]
    for operation, _, _, _ in SURFACE:
        if today[operation] != then[operation]:
            problems.append(f"{operation}: content other than additions and removals differs")
    return problems


def _serve(directory: Any) -> dict[str, Any]:
    project = directory / "p"
    LocalApplication.create(project, project_id=generator.PROJECT_ID).close()
    with LocalApplication.open(project) as application:
        return {name: dispatch(application, name, {}) for name in ("get_project", "list_models")}


def test_m07a_a51_each_v0_2_addition_is_named_by_its_register_entry() -> None:
    """MR-7's list is register-sourced: each entry's text names its id, and no id is B50's."""
    for member, additions in V02_ADDITIONS.items():
        for entry_id, source in additions.items():
            assert f"`{entry_id}`" in _register_entry(source), (member, entry_id, source)
    assert not set(V02_ADDITIONS["models"]) & set(NEW_MODELS)
    assert not set(V02_ADDITIONS["solve_policies"]) & set(NEW_POLICIES)


def test_m07a_a51_a_the_content_is_b50s_entries_plus_the_registered_additions(
    served: dict[str, Any],
) -> None:
    assert mr7_problems(served) == []


def test_m07a_a51_b_an_unregistered_model_fails_naming_it(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    probe = "c1.unregistered_probe"
    signature = dataclasses.replace(local.MODEL_SIGNATURES["c1.tp_heater"], model_id=probe)
    builders = {**local.MODEL_BUILDERS, probe: local.MODEL_BUILDERS["c1.tp_heater"]}
    monkeypatch.setattr(local, "MODEL_BUILDERS", builders)
    monkeypatch.setattr(local, "MODEL_SIGNATURES", {**local.MODEL_SIGNATURES, probe: signature})
    assert mr7_problems(_serve(tmp_path)) == [
        f"models: `{probe}` is served, not c7bbc98's, named by no entry"
    ]


def test_m07a_a51_c_a_registered_addition_removed_fails_naming_it(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    builders = {k: v for k, v in local.MODEL_BUILDERS.items() if k != "c1.tp_heater"}
    monkeypatch.setattr(local, "MODEL_BUILDERS", builders)
    assert mr7_problems(_serve(tmp_path)) == [
        "models: `c1.tp_heater` (R-230) served 0 times, not once"
    ]
