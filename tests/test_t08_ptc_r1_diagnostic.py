"""T08: PTC-R1's saddle diagnostic (`benchmarks/t08/ptc_r1/diagnose.py`).

Brief `docs/briefs/T08-ptc-r1-diagnostic.md`. A diagnostic after `C_res`: it changes no verdict
(R-118). These tests check that its capture is pass-through — a handful of re-runs reproduce their
committed records byte-for-byte, with the shims removed afterwards — and that it never overwrites a
diagnostic.
"""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path
from typing import Any

import pytest

import openflowsheet.numerics.ptc as ptc_module
from benchmarks.t06.ensemble import host
from benchmarks.t08.ptc_r1 import compare, diagnose
from openflowsheet.orchestrator import region as region_module


@cache
def _committed() -> dict[str, Any] | None:
    """This machine class's committed results, or `None` where there are none (bit-equality is
    only claimed against the platform that produced them). A machine class names an architecture,
    not a CPU: GitHub's `ci-x86-64` runners vary their CPU model, and CI run 36851384496 (an
    `ubuntu-latest` runner) reproduced 1 of 5 records. So the committed host's CPU model must match
    too (ADR 0007 F1: bitwise agreement is reported, never promised across hardware)."""
    path = compare.CASE_DIR / f"results-{host()['machine_class']}.json"
    if not path.exists():
        return None
    loaded: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    if loaded["host"].get("cpu_model") != host().get("cpu_model"):
        return None
    return loaded


def _pick(group: str, index: int) -> dict[str, Any]:
    results = _committed()
    if results is None:
        pytest.skip(f"no committed PTC-R1 results for {host()['machine_class']} on this CPU model")
    chosen: list[dict[str, Any]] = diagnose.selection(results)[group]
    return chosen[index * (len(chosen) - 1) // 2]


@pytest.mark.parametrize(
    ("group", "index"), [("MID", 0), ("MID", 1), ("MID", 2), ("control", 0), ("control", 2)]
)
def test_the_rerun_reproduces_the_committed_record(group: str, index: int) -> None:
    committed = _pick(group, index)
    rows = {(int(row[0]), int(row[1])): row for row in compare.start_rows()}
    original = (region_module.solve_ptc, ptc_module.solve_linear)
    run = diagnose.diagnose_run(rows[(committed["i"], committed["j"])], committed)
    assert (region_module.solve_ptc, ptc_module.solve_linear) == original
    assert run["class"] == committed["class"]
    assert run["class"] in (("MID",) if group == "MID" else ("LOW", "HIGH"))
    (attempt,) = run["attempts"]
    accepted = [trial for trial in attempt["trials"] if trial["accepted"]]
    assert len(accepted) == committed["accepted_steps"]
    assert accepted[0]["tau_s"] == 1.0  # T04 §7.7: the SER opens at θ
    assert all(trial["det_sign"] in (-1, 0, 1) for trial in attempt["trials"])


def test_a_rerun_that_differs_is_refused() -> None:
    committed = dict(_pick("MID", 0))
    committed["state"] = [[name, value * (1.0 + 2.0**-52)] for name, value in committed["state"]]
    rows = {(int(row[0]), int(row[1])): row for row in compare.start_rows()}
    with pytest.raises(AssertionError, match="does not reproduce"):
        diagnose.diagnose_run(rows[(committed["i"], committed["j"])], committed)


def test_it_refuses_to_overwrite_a_diagnostic(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def refuse(*_: Any) -> Any:
        raise AssertionError("the diagnostic ran past its refusal")

    monkeypatch.setattr(diagnose, "host", lambda: {"machine_class": "synthetic"})
    monkeypatch.setattr(diagnose, "diagnose_run", refuse)
    monkeypatch.setattr(diagnose, "provenance", refuse)
    existing = tmp_path / "diagnostic-synthetic.json"
    existing.write_text("{}\n", encoding="utf-8")
    assert diagnose.main(["--run", "--out-dir", str(tmp_path)]) == 1
    assert existing.read_text(encoding="utf-8") == "{}\n"
    assert sorted(path.name for path in tmp_path.iterdir()) == ["diagnostic-synthetic.json"]


def test_the_thresholds_are_the_references() -> None:
    thresholds = diagnose.saddle_thresholds()
    assert thresholds["singular_s"] == pytest.approx(4.15865463594877608, rel=1e-15)
    assert thresholds["contracting_s"] == pytest.approx(2 * thresholds["singular_s"], rel=1e-15)
