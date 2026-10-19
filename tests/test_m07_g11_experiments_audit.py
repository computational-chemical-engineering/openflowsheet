"""`scripts/m07_g11_experiments_audit.py` (R-375, W21 (e)): blueprint §9.1's six items in a G11
experiment's records, against `schemas/experiment.schema.json`.

The positive case is an accepted point of the kept run 1 at `C′`, as committed; each negative case
breaks one item in a copy of it and the audit must name that item, and only that item besides the
schema where the break is also a schema violation. The audit over every committed record is
`tests/test_m07_rc_records.py`'s.
"""

from __future__ import annotations

import copy
import gzip
import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from conftest import REPO_ROOT

from openflowsheet.adapters import variants

sys.path.insert(0, str(REPO_ROOT / "scripts"))
import m07_g11_experiments_audit as audit  # noqa: E402

RC = "ce993651ce37c1343e771b276160bd6623e43500"
EXPERIMENTS = REPO_ROOT / "evidence" / "M07" / RC / "rc" / "step12" / "experiments"
VARIANT_FILE = REPO_ROOT / "benchmarks" / "m02" / "variant-v3-provisional.json"


def _record(name: str) -> dict[str, Any]:
    path = EXPERIMENTS / name
    raw = path.read_bytes() if path.is_file() else gzip.decompress(Path(f"{path}.gz").read_bytes())
    document = json.loads(raw)
    assert isinstance(document, dict)
    return document


def _variant() -> variants.Variant:
    return variants.variant_from_document(json.loads(VARIANT_FILE.read_text("utf-8")))


def _accepted() -> tuple[dict[str, Any], dict[str, Any]]:
    """The first point of run 1 whose result is `ok` with all four elements present, and its
    runs-file entry."""
    record = _record("g11-experiments-run1.json")
    runs = json.loads((EXPERIMENTS / "g11-coverage-v3.runs.json").read_text("utf-8"))
    by_label = {p["label"]: p for p in runs[0]}
    for point in record["points"]:
        for experiment in point["experiments"] or []:
            diagnostics = experiment["attempts"][-1]["execution"]["diagnostics"] or {}
            if (experiment["result"] or {}).get("envelope", {}).get("status") == "ok" and len(
                diagnostics.get("element_defect_rel") or {}
            ) == 4:
                return experiment, by_label[point["label"]]
    raise AssertionError("no accepted point in run 1")


def _last_attempt(experiment: dict[str, Any]) -> dict[str, Any]:
    attempt = experiment["attempts"][-1]
    assert isinstance(attempt, dict)
    return attempt


def _found(experiment: dict[str, Any], point: dict[str, Any]) -> dict[str, list[str]]:
    return audit.audit_experiment(experiment, _variant(), audit.validators(), point)


def test_an_accepted_point_as_committed_has_every_item() -> None:
    """Its only findings are the two `job_id`s G11 names `m02-g11v3-<label>` (context, J78)."""
    experiment, point = _accepted()
    found = _found(experiment, point)
    context = found.pop("context")
    assert found == dict.fromkeys(audit.ITEMS, [])
    assert [m.split(":", 1)[0] for m in context] == ["result produced_by/job_id", "attempt job_id"]


def _set_provider_id(e: dict[str, Any]) -> None:
    e["request"]["boundary"]["provider_id"] = ""


def _set_reactor_commit(e: dict[str, Any]) -> None:
    e["result"]["provenance"]["reactor"]["commit"] = "0" * 40


def _set_num_z(e: dict[str, Any]) -> None:
    e["result"]["accuracy"]["discretization_estimate"]["num_z"] = 400


def _fail_certificate(e: dict[str, Any]) -> None:
    _last_attempt(e)["execution"]["diagnostics"]["certificate"]["kpi_drift_ok"] = False


def _drop_a_defect(e: dict[str, Any]) -> None:
    e["result"]["envelope"]["defect"] = e["result"]["envelope"]["defect"][:-1]


def _zero_wall_time(e: dict[str, Any]) -> None:
    _last_attempt(e)["execution"]["timing"]["wall_s"] = 0.0


def _bad_outcome_class(e: dict[str, Any]) -> None:
    e["result"]["outcome_class"] = "transient"


@pytest.mark.parametrize(
    ("item", "breaks"),
    [
        ("boundary", _set_provider_id),
        ("version", _set_reactor_commit),
        ("discretization", _set_num_z),
        ("convergence", _fail_certificate),
        ("fluxes", _drop_a_defect),
        ("cost", _zero_wall_time),
        ("schema", _bad_outcome_class),
    ],
)
def test_a_broken_item_is_named(item: str, breaks: Callable[[dict[str, Any]], None]) -> None:
    experiment, point = _accepted()
    broken = copy.deepcopy(experiment)
    breaks(broken)
    found = _found(broken, point)
    assert found[item], item
    assert {name for name, problems in found.items() if problems} <= {item, "schema", "context"}


def test_an_element_defect_keyed_by_an_absent_element_breaks_the_fluxes() -> None:
    """§14.6 E2: the keys are exactly the elements present in the composition sent."""
    experiment, point = _accepted()
    broken = copy.deepcopy(experiment)
    execution = _last_attempt(broken)["execution"]
    composition = execution["tube_inlet"]["composition"]
    execution["tube_inlet"]["composition"] = [*composition[:3], 0.0, 0.0]  # no Ar, no CH4
    found = _found(broken, point)
    assert found["fluxes"] == ["attempt 1: diagnostics.element_defect_rel"]


def test_a_request_that_is_not_the_points_inlet_breaks_the_boundary_mapping() -> None:
    experiment, point = _accepted()
    moved = {**point, "T_in_K": point["T_in_K"] + 1.0}
    found = _found(experiment, moved)
    assert found["boundary"] == ["request inlet or n_tubes is not the point's"]


def test_the_command_line_fails_a_broken_record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    record = _record("g11-experiments-run1.json")
    for point in record["points"]:
        for experiment in point["experiments"] or []:
            _zero_wall_time(experiment)
    path = tmp_path / "broken.json.gz"
    path.write_bytes(gzip.compress(json.dumps(record).encode("utf-8")))
    arguments = [str(path), "--variant-file", str(VARIANT_FILE)]
    monkeypatch.setattr(sys, "argv", ["m07_g11_experiments_audit.py", *arguments])
    assert audit.main() == 1
    assert capsys.readouterr().out.splitlines()[0].endswith(": FAIL")
