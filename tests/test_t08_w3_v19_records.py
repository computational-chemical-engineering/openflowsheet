"""T08 W3 (V19 facts for C1, the ammonia loop): the committed records have the form §9 asks for.

Release spec `docs/derivations/T08-release-spec.md` §7.1, §9 T08.A61-A63; brief
`docs/briefs/T08-phase3-v19.md`. The records under `benchmarks/t08/v19/` were measured in
environments separate from this project's (the group's PyMRM reactor; IDAES 2.13), by the scripts
next to them. These tests check that each record carries what the assertion requires -- versions,
commit, tolerance, outcome, timing -- and that its internal arithmetic is consistent. They do not
re-run either external model and judge nothing (the verdicts are the design lane's).
"""

from __future__ import annotations

import hashlib
import json
import statistics
from pathlib import Path
from typing import Any

import pytest
from conftest import REPO_ROOT

V19 = REPO_ROOT / "benchmarks" / "t08" / "v19"


def _load(name: str) -> dict[str, Any]:
    record: dict[str, Any] = json.loads((V19 / name).read_text(encoding="utf-8"))
    return record


def _is_sha(text: object, length: int = 40) -> bool:
    return isinstance(text, str) and len(text) == length and int(text, 16) >= 0


# --- T08.A61: the group's reactor (c1-reactor.json) -------------------------------------------

RELEASE_COMMIT = "6089593464fc9bc2c0a0cb58e30ad5433ece6332"
RELEASE_ROOT = "d2b00336d621722fc25e7052883b79184b6736b5"


def test_a61_record_pins_the_released_repository_and_environment() -> None:
    record = _load("c1-reactor.json")
    assert record["record"] == "t08-v19-c1-reactor"
    assert record["version"] == 2
    assert record["judged"] is False
    repo = record["group_repository"]
    assert repo["commit"] == RELEASE_COMMIT
    assert repo["root_commits"] == [RELEASE_ROOT]
    assert repo["branch"] == "main" and "origin/main" in repo["on_remote_branches"]
    assert repo["tag"] == "v1.1.0" and _is_sha(repo["tag_commit"])
    assert repo["describe"] == "v1.1.0-1-g6089593"
    assert repo["worktree_clean_before"] is True and repo["worktree_clean_after"] is True
    assert repo["licence_file"] == ["LICENSE"]
    assert repo["licence_file_first_line"] == "MIT License"
    assert repo["pyproject_license"] == "MIT"
    env = record["environment"]
    assert "never the project .venv" in env["kind"]
    assert {"pymrm", "numpy", "scipy", "pandas", "pytest"} <= set(env["packages"])
    assert all(isinstance(v, str) and v for v in env["packages"].values())
    assert env["installed_reactor"]["version"] == repo["pyproject_version"]
    # The superseded line's measurements are dropped; only the pointer stays.
    assert record["superseded"]["commit"] != RELEASE_COMMIT
    assert "7c042a0" in record["superseded"]["disposition"]
    for key in ("regression", "diagnostic"):
        assert key not in record


def test_a61_group_suite_outcome_is_recorded_with_its_counts() -> None:
    record = _load("c1-reactor.json")
    suite = record["group_test_suite"]
    assert suite["collected"] == sum(suite["collected_per_module"].values())
    assert len(suite["collected_per_module"]) == 6
    counts = suite["counts"]
    assert sum(counts.values()) == suite["collected"]
    assert (suite["exit_code"] == 0) is (counts.get("failed", 0) + counts.get("errors", 0) == 0)
    assert len(suite["skipped"]) == counts.get("skipped", 0)
    assert all(reason.split(": ", 1)[1] for reason in suite["skipped"])
    reading = record["a61_reading"]
    assert "pytest suite" in reading["reading"] and reading["observations"]


def _check_solve(summary: dict[str, Any]) -> None:
    result = summary["result"]
    assert result["outcome"] in {"solved", "failed", "error"}
    if result["outcome"] == "error":
        assert result["exception"]
        return
    assert result["dt_init_1d"] > 0
    assert isinstance(result["solve_converged"], bool)
    assert result["runtime_s"] > 0
    if result["outcome"] == "failed":
        assert result["solver_accepted"] is False and result["message"]
        return
    assert summary["runtime_s_median"] == statistics.median(summary["runtime_s"])
    assert len(summary["runtime_s"]) == summary["repeats"]
    assert result["species"] == ["H2", "N2", "NH3"]
    assert len(result["retentate_out_mol_s"]) == 3
    assert isinstance(result["element_balance_ok"], bool)
    assert result["convergence_certificate"]["class"] in {"converged", "floored"}


def test_a61_one_non_isothermal_1d_solve_is_timed() -> None:
    solve = _load("c1-reactor.json")["one_1d_solve"]
    assert solve["model"].startswith("reactor.MembraneReactor1D")
    assert solve["case"]["Case_ID"]
    summary = solve["non_isothermal"]
    _check_solve(summary)
    result = summary["result"]
    assert result["is_isothermal"] is False and result["overrides"] == {}
    assert result["outcome"] == "solved", "no 1D solve was timed"
    assert summary["repeats"] >= 3


def test_q6_no_membrane_configuration_is_recorded() -> None:
    no_membrane = _load("c1-reactor.json")["no_membrane"]
    summaries = [no_membrane["non_isothermal"], *no_membrane["isothermal_by_start"]]
    for summary in summaries:
        _check_solve(summary)
        result = summary["result"]
        assert {"P0_H2": 0.0, "P0_N2": 0.0, "P0_NH3": 0.0}.items() <= result["overrides"].items()
        assert "Perm_NH3" not in result["overrides"]
        if result["outcome"] == "solved":
            # No species crosses the membrane in this configuration.
            assert result["membrane_transfer_mol_s"] == [0.0, 0.0, 0.0]
            eq = result["equilibrium_y_NH3_at_T_in_p_out"]
            assert (eq is not None) is result["is_isothermal"]
            if eq is not None:
                assert 0.0 < result["y_NH3_retentate_out"] < eq < 1.0
    starts = [s["result"]["dt_init_1d"] for s in no_membrane["isothermal_by_start"]]
    assert len(set(starts)) == len(starts)


def test_a61_frank_statements_and_quoted_lines() -> None:
    record = _load("c1-reactor.json")
    for statement in record["frank_statements"]:
        assert statement["statement"]
    quoted = {
        (q["path"], n): text for q in record["quoted_lines"] for n, text in q["lines"].items()
    }
    assert quoted[("src/reactor/paper/validation.py", "103")] == "cfg.Perm_NH3 = 0.0"
    assert quoted[("src/reactor/config.py", "51")].startswith("#Perm_NH3")
    assert "self.lambda_mem(" in quoted[("src/reactor/membrane_reactor_1d.py", "688")]


def test_a60_provenance_record_points_at_sources() -> None:
    record = _load("c1-provenance.json")
    assert record["record"] == "t08-v19-c1-provenance"
    assert record["version"] == 2
    assert record["group_repository_commit"] == RELEASE_COMMIT
    assert (
        record["group_repository_commit"] == _load("c1-reactor.json")["group_repository"]["commit"]
    )
    assert record["group_repository"]["root_commit"] == RELEASE_ROOT
    statuses = {
        "found",
        "partly_found",
        "not_determinable",
        "discrepancy",
        "deviation_documented",
    }
    items = [f["item"] for f in record["findings"]]
    assert len(items) == len(set(items))
    for finding in record["findings"]:
        assert finding["status"] in statuses, finding["item"]
        assert finding["answer"]
        assert finding["pointers"], finding["item"]
    assert any(f["item"].startswith("published rate law") for f in record["findings"])
    assert any(f["item"].startswith("where the Rossetti") for f in record["findings"])
    licence = next(f for f in record["findings"] if f["item"].startswith("licence"))
    assert licence["status"] == "found" and "MIT" in licence["answer"]
    for statement in record["frank_statements"]:
        assert statement["statement"] and statement["pointers"]


def test_scripts_are_not_imported_by_the_package() -> None:
    src = Path(REPO_ROOT / "src")
    for path in src.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "benchmarks.t08.v19" not in text and "t08/v19" not in text, path


# --- T08.A62, A63, Q7: IDAES 2.13 (c1-idaes.json) ------------------------------------------------

STATES = ("reactor_inlet", "separator")


def test_a62_a63_record_pins_the_independent_tool() -> None:
    record = _load("c1-idaes.json")
    assert record["record"] == "t08-v19-c1-idaes"
    assert record["judged"] is False and record["comparison_claimed"] is False
    env = record["environment"]
    assert "never the project .venv" in env["kind"]
    assert env["packages"]["idaes-pse"] == "2.13.0"
    assert env["ipopt_version"]
    lock = REPO_ROOT / "spikes" / "references" / "idaes-requirements.lock"
    assert env["lock_sha256"] == hashlib.sha256(lock.read_bytes()).hexdigest()
    assert all(_is_sha(h, 64) for h in env["idaes_extension_sha256"].values())
    route = record["property_route"]
    assert "Peng-Robinson" in route["method"]
    assert route["components"] == ["H2", "N2", "NH3", "Ar", "CH4"]
    assert set(route["components"]) <= set(route["sources"])


def test_a62_pr_flash_records_phase_split_and_k_values() -> None:
    flashes = _load("c1-idaes.json")["pr_flash"]
    assert "light_gases_vapour_only" in flashes
    for route, by_state in flashes.items():
        assert by_state["phase_representation"], route
        for state in STATES:
            result = by_state[state]
            assert "spec" in result
            if "error" in result:
                continue
            assert isinstance(result["trivial_solution"], bool)
            if result["termination_condition"] != "optimal":
                continue  # a failed solve is recorded as it ended; its point need not close
            fractions = result["phase_fraction"]
            assert abs(fractions["Vap"] + fractions["Liq"] - 1.0) < 1e-9
            assert set(result["K_value"]) == set(result["y_vapour"]) == set(result["x_liquid"])
            for comp, k in result["K_value"].items():
                if k is not None:
                    assert k == pytest.approx(result["y_vapour"][comp] / result["x_liquid"][comp])
    primary = flashes["light_gases_vapour_only"]
    # The two states the assertion names, as the primary route returned them.
    assert primary["reactor_inlet"]["single_phase"] is True
    assert primary["separator"]["single_phase"] is False
    assert primary["separator"]["K_value"]["NH3"] is not None
    for state in STATES:
        assert primary[state]["termination_condition"] == "optimal"
        assert "psat_independence" in primary[state]


def test_a63_loop_skeleton_and_representability_table() -> None:
    record = _load("c1-idaes.json")
    loop = record["loop_skeleton"]
    assert loop["degrees_of_freedom"]["after_unfixing_tear_guess"] == 0
    assert loop["termination_condition"] in {"optimal", "infeasible", "maxIterations", "other"}
    assert {"fresh_feed", "reactor_inlet", "reactor_outlet", "liquid_product", "purge"} <= set(
        loop["streams"]
    )
    table = record["representability"]
    for row in table:
        assert set(row) == {
            "unit",
            "idaes_model_and_method",
            "reaction_form",
            "representable",
            "reason",
        }
        assert row["representable"] in {"Y", "N", "not_built"}
        assert row["reason"]
    units = {row["unit"] for row in table}
    assert {"reactor (stoichiometric)", "cooler", "purge", "recycle closure"} <= units
    assert any(row["unit"].startswith("reactor (kinetic") for row in table)
    kinetic = record["kinetic_reactor_q7"]
    assert "error" in kinetic or kinetic["termination_condition"]


# --- T08.A60, A64: the dossier draft (docs/v02-real-chemistry-dossier.md) -----------------------

DOSSIER = REPO_ROOT / "docs" / "v02-real-chemistry-dossier.md"


def _table_after(text: str, heading: str) -> list[list[str]]:
    """Rows (cells stripped) of the first Markdown table after ``heading``, header excluded."""
    lines = text[text.index(heading) :].splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith("|"))
    rows = []
    for line in lines[start + 2 :]:
        if not line.startswith("|"):
            break
        rows.append([cell.strip() for cell in line.strip().strip("|").split("|")])
    return rows


def test_a60_dossier_has_the_twelve_items_with_status_and_evidence() -> None:
    text = DOSSIER.read_text(encoding="utf-8")
    rows = _table_after(text, "## Item statuses")
    assert [int(r[0]) for r in rows] == list(range(1, 13))
    for number, _item, status, evidence in rows:
        word = status.split()[0].strip("`")
        assert word in {"met", "needs_fact", "needs_frank"}, number
        assert evidence, number
    for number in range(1, 13):
        assert f"\n## {number}. " in text, number


def test_a64_rights_table_has_no_unknown() -> None:
    text = DOSSIER.read_text(encoding="utf-8")
    rows = _table_after(text, "## 8. Rights table")
    assert len(rows) >= 8
    for row in rows:
        assert len(row) == 7, row[0]
        item, source, licence, scope, mode, _attribution, status = row
        assert all((item, source, licence, scope, mode, status)), item
        # Verdicts, V19 (v): a row states its source, licence, scope and mode, never a dash.
        assert "—" not in (source, licence, scope, mode), item
        assert "unknown" not in " ".join(row).lower(), item
        assert any(s in status for s in ("met", "needs_frank", "needs_fact")), item
