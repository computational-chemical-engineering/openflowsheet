"""MR-12 at the M07 release candidate: `mr12_extras_v02` (M07 spec §24.1 action 4, S9.4, R-478).

The alpha's `_m_mr12_extras` fails every extra declared since `v0.1.1` and stays as it is, because
the alpha's records are judged under it. `mr12_extras_v02` accepts an extra only through an
`MR12_AUDITS` entry: the audit and inventory exist at the commit, step 14's record has the entry's
check `pass` at that commit, and the register holds the decision. It also reads S9.2 and S9.3 off
each of step 9's A30 summaries. These tests decide each clause on synthetic inputs, then run the
git-backed measure at `HEAD` over records written to `tmp_path`.

MR-12 v03 (V03 spec §9.3, V03.A11, R-879) is `mr12_extras_v03` over `MR12_AUDITS_V03`: every extra
new since `v0.2.0` (`coolprop`, `lca`) passes through its own entry, whose check step 17c's record
carries at the commit. The `HEAD` test moved to it; the v02 measure stays judged at v0.2.0.
"""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from conftest import RELEASE_0_2_0_COMMIT, REPO_ROOT

sys.path.insert(0, str(REPO_ROOT / "scripts"))
import m07a_evidence_manifest as manifest  # noqa: E402

COMMIT = "c" * 40
AUDIT = manifest.MR12_AUDITS["nlp"]
REGISTER = "# Decision register\n\n## R-449 — other\n\n## R-450 — the nlp extra's licences\n"


def _step14(commit: str = COMMIT, result: str = "pass") -> dict[str, Any]:
    return {
        "format": "t08-rc-v1",
        "step": "w24-nlp-trf",
        "passed": result == "pass",
        "provenance": {"commit": commit, "tree_clean": True},
        "checks": [
            {"id": AUDIT["check"], "result": result},
            {"id": "a60.w24.m03_m05_all_tiers", "result": "pass"},
        ],
    }


def _summary() -> dict[str, Any]:
    return {
        "format": "t08-a30-inventory-v1-summary",
        "verdict": {"pass": True, "undispositioned_in_required_closure": []},
        "measured_project_load": {
            "solve_exit": 0,
            "modules_walked": 182,
            "modules_imported": 179,
            "nlp_extra_modules": dict(manifest.A30_NLP_EXTRA_MODULES),
            "mapped": [],
        },
    }


def _summaries() -> dict[str, dict[str, Any] | None]:
    return {path: _summary() for path in manifest.A30_SUMMARIES}


def _show(register: str = REGISTER, missing: str | None = None) -> Callable[[str], str | None]:
    files = {"docs/decision-register.md": register, AUDIT["audit"]: "x", AUDIT["inventory"]: "{}"}
    return lambda path: None if path == missing else files.get(path)


def test_the_control_passes() -> None:
    result, value = manifest.mr12_extras_v02(COMMIT, ["nlp"], _show(), _step14(), _summaries())
    assert result == "pass", value
    assert value["extras"]["nlp"]["decision_in_register"] is True


def test_an_extra_without_an_mr12_audits_entry_fails() -> None:
    result, value = manifest.mr12_extras_v02(
        COMMIT, ["nlp", "gpu"], _show(), _step14(), _summaries()
    )
    assert result == "fail"
    assert value["extras"]["gpu"] == {"audit": None, "reason": "no MR12_AUDITS entry"}


def test_nlp_fails_when_r450_is_absent() -> None:
    register = REGISTER.replace("## R-450 — ", "R-450 is mentioned, not headed: ")
    result, value = manifest.mr12_extras_v02(
        COMMIT, ["nlp"], _show(register), _step14(), _summaries()
    )
    assert result == "fail"
    assert value["extras"]["nlp"]["decision_in_register"] is False


@pytest.mark.parametrize("check", ["fail", "unsupported", None])
def test_nlp_fails_when_step14s_check_is_not_pass(check: str | None) -> None:
    step14 = _step14(result="pass")
    step14["checks"][0]["result"] = check
    result, _ = manifest.mr12_extras_v02(COMMIT, ["nlp"], _show(), step14, _summaries())
    assert result == "fail"


def test_nlp_fails_when_step14s_check_is_missing() -> None:
    step14 = _step14()
    del step14["checks"][0]
    result, value = manifest.mr12_extras_v02(COMMIT, ["nlp"], _show(), step14, _summaries())
    assert result == "fail"
    assert value["extras"]["nlp"]["check_result"] is None


def test_nlp_fails_when_step14_names_another_commit() -> None:
    step14 = _step14(commit="d" * 40)
    result, _ = manifest.mr12_extras_v02(COMMIT, ["nlp"], _show(), step14, _summaries())
    assert result == "fail"


@pytest.mark.parametrize("key", ["audit", "inventory"])
def test_nlp_fails_when_a_file_is_absent_at_the_commit(key: str) -> None:
    show = _show(missing=AUDIT[key])
    result, value = manifest.mr12_extras_v02(COMMIT, ["nlp"], show, _step14(), _summaries())
    assert result == "fail"
    assert value["extras"]["nlp"]["files_at_commit"][key] is False


@pytest.mark.parametrize(
    ("member", "wrong"),
    [
        ("modules_walked", 181),
        ("modules_imported", 180),
        ("solve_exit", 1),
        ("nlp_extra_modules", {"openflowsheet.studies.nlp.greybox": "pyomo"}),
    ],
)
def test_an_a30_summary_off_s9_2_or_s9_3_fails(member: str, wrong: Any) -> None:
    summaries = _summaries()
    path = manifest.A30_SUMMARIES[2]
    broken = copy.deepcopy(summaries[path])
    assert broken is not None
    broken["measured_project_load"][member] = wrong
    summaries[path] = broken
    result, value = manifest.mr12_extras_v02(COMMIT, ["nlp"], _show(), _step14(), summaries)
    assert result == "fail"
    assert value["a30_summaries"][path][member] == wrong


def test_a_missing_a30_summary_fails() -> None:
    summaries = _summaries()
    summaries[manifest.A30_SUMMARIES[1]] = None
    result, _ = manifest.mr12_extras_v02(COMMIT, ["nlp"], _show(), _step14(), summaries)
    assert result == "fail"


def _git_backed(commit: str, tmp_path: Path) -> tuple[Any, tuple[str, dict[str, Any]], Path]:
    rc = tmp_path / commit / "rc"
    for path, document in [(manifest.STEP14_RECORD, _step14(commit)), *_summaries().items()]:
        (rc / path).parent.mkdir(parents=True, exist_ok=True)
        (rc / path).write_text(json.dumps(document), encoding="utf-8")
    inputs = manifest.Inputs(commit=commit, tests=None, evidence=tmp_path)  # type: ignore[arg-type]
    return inputs, manifest.MEASURES["mr12_extras_v02"](inputs), rc


def test_the_git_backed_measure_at_the_v0_2_0_commit(tmp_path: Path) -> None:
    """S9.4 is about the v0.2 release candidate: it reads at v0.2.0 (S07 Ruling M, A44)."""
    inputs, (result, value), rc = _git_backed(RELEASE_0_2_0_COMMIT, tmp_path)
    assert result == "pass", value
    assert value["new_since_v0_1_1"] == ["nlp"]
    (rc / manifest.STEP14_RECORD).write_text(
        json.dumps(_step14(RELEASE_0_2_0_COMMIT, "fail")), encoding="utf-8"
    )
    assert manifest.MEASURES["mr12_extras_v02"](inputs)[0] == "fail"


def test_the_git_backed_measure_at_head(tmp_path: Path) -> None:
    """The tripwire (S07 Ruling M, A44) moved to the v03 measure (V03 spec §9.3, V03.A11):
    `coolprop` and `lca`, the extras added since v0.2.0, each pass through their
    `MR12_AUDITS_V03` entry at `HEAD`, over a step 17c record written to `tmp_path`; an extra
    without an entry still fails."""
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()
    rc = tmp_path / head / "rc"
    (rc / manifest.STEP17C_RECORD).parent.mkdir(parents=True, exist_ok=True)
    (rc / manifest.STEP17C_RECORD).write_text(json.dumps(_step17c(head)), encoding="utf-8")
    inputs = manifest.Inputs(commit=head, tests=None, evidence=tmp_path)  # type: ignore[arg-type]
    result, value = manifest.MEASURES["mr12_extras_v03"](inputs)
    assert result == "pass", value
    assert value["new_since_v0_2_0"] == ["coolprop", "lca"]
    assert set(value["extras"]) == {"coolprop", "lca"}
    for extra in ("coolprop", "lca"):
        assert value["extras"][extra]["files_at_commit"] == {"audit": True, "inventory": True}
        assert value["extras"][extra]["decision_in_register"] is True


# -- MR-12 v03 (V03 spec §9.3, V03.A11): synthetic clauses -----------------------------------------

V03_AUDITS = manifest.MR12_AUDITS_V03
V03_REGISTER = "# Decision register\n\n## R-624 — coolprop\n\n## R-870 — lca\n"


def _step17c(commit: str = COMMIT, results: dict[str, str] | None = None) -> dict[str, Any]:
    results = results or {}
    return {
        "format": "t08-rc-v1",
        "step": "17c",
        "provenance": {"commit": commit, "tree_clean": True},
        "checks": [
            {"id": audit["check"], "result": results.get(extra, "pass")}
            for extra, audit in V03_AUDITS.items()
        ],
    }


def _show_v03(
    register: str = V03_REGISTER, missing: str | None = None
) -> Callable[[str], str | None]:
    files = {"docs/decision-register.md": register}
    for audit in V03_AUDITS.values():
        files[audit["audit"]] = "x"
        files[audit["inventory"]] = "{}"
    return lambda path: None if path == missing else files.get(path)


NEW_V03 = ["coolprop", "lca"]


def test_v03_the_control_passes() -> None:
    result, value = manifest.mr12_extras_v03(COMMIT, NEW_V03, _show_v03(), _step17c())
    assert result == "pass", value
    assert value["new_since_v0_2_0"] == NEW_V03


def test_v03_an_extra_without_an_entry_fails() -> None:
    result, value = manifest.mr12_extras_v03(COMMIT, [*NEW_V03, "gpu"], _show_v03(), _step17c())
    assert result == "fail"
    assert value["extras"]["gpu"] == {"audit": None, "reason": "no MR12_AUDITS_V03 entry"}


@pytest.mark.parametrize("extra", NEW_V03)
@pytest.mark.parametrize("key", ["audit", "inventory"])
def test_v03_a_missing_file_fails(extra: str, key: str) -> None:
    show = _show_v03(missing=V03_AUDITS[extra][key])
    assert manifest.mr12_extras_v03(COMMIT, NEW_V03, show, _step17c())[0] == "fail"


@pytest.mark.parametrize("extra", NEW_V03)
def test_v03_a_failed_or_absent_check_fails(extra: str) -> None:
    failed = _step17c(results={extra: "fail"})
    assert manifest.mr12_extras_v03(COMMIT, NEW_V03, _show_v03(), failed)[0] == "fail"
    absent = _step17c()
    absent["checks"] = [c for c in absent["checks"] if c["id"] != V03_AUDITS[extra]["check"]]
    assert manifest.mr12_extras_v03(COMMIT, NEW_V03, _show_v03(), absent)[0] == "fail"


def test_v03_a_record_of_another_commit_fails() -> None:
    other = _step17c("d" * 40)
    assert manifest.mr12_extras_v03(COMMIT, NEW_V03, _show_v03(), other)[0] == "fail"


@pytest.mark.parametrize("decision", ["R-624", "R-870"])
def test_v03_a_decision_not_in_the_register_fails(decision: str) -> None:
    register = V03_REGISTER.replace(f"## {decision} — ", f"## {decision}x — ")
    show = _show_v03(register=register)
    assert manifest.mr12_extras_v03(COMMIT, NEW_V03, show, _step17c())[0] == "fail"


def test_v03_the_v02_table_is_unchanged() -> None:
    """R-879: the v02 measure's table is not edited, so v0.2's judgement does not move."""
    assert manifest.MR12_AUDITS == {
        "nlp": {
            "audit": "docs/m03-ipopt-audit.md",
            "inventory": "benchmarks/m03/ipopt-inventory-x86_64.json",
            "check": "a60.w24.nlp_tier_and_inventory",
            "decision": "R-450",
        }
    }
