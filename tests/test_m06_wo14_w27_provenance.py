"""M06 WO-14 (gate G13): the committed W27 provenance and access report are internally consistent.

No network and no archive: the expectations are the audit's measured numbers
(`study/openidaes450:docs/openidaes450-audit.md`) and design note `docs/design/M06-web-shell.md` §9.
The live re-derivation against the downloaded archive is `scripts/m06_w27_acquire.py --check`.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

import pytest

DIR = Path(__file__).resolve().parent.parent / "benchmarks" / "m06" / "openidaes450"
PINNED_SIZE = 220_802_919
AUDIT_SIZE = 220_433_394


@pytest.fixture(scope="module")
def provenance() -> dict[str, Any]:
    data: dict[str, Any] = json.loads((DIR / "provenance.json").read_text(encoding="utf-8"))
    return data


@pytest.fixture(scope="module")
def report() -> dict[str, Any]:
    data: dict[str, Any] = json.loads((DIR / "access_report.json").read_text(encoding="utf-8"))
    return data


def test_provenance_fields(provenance: dict[str, Any]) -> None:
    assert provenance["paper"]["id"] == "arXiv:2608.01369"
    assert provenance["repository_url"].endswith("CRAFTS-Multi-agent-for-Equation-oriented-PSE")
    assert provenance["commit"]["short"] == "13ca57e"
    assert re.fullmatch(r"[0-9a-f]{40}", provenance["commit"]["sha"])
    assert provenance["commit"]["sha"].startswith("13ca57e")
    assert provenance["release"]["tag"] == "openidaes450-demo-2026-09-26"
    assert provenance["archive"]["url"].endswith(
        "/releases/download/openidaes450-demo-2026-09-26/OpenIDAES-450-demo.tar.gz"
    )
    assert re.fullmatch(r"[0-9a-f]{64}", provenance["licence"]["sha256"])
    assert provenance["licence"]["spdx"] == "MIT"
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", provenance["acquisition_time_utc"])
    assert provenance["attribution"]
    permission = provenance["permission"]
    assert permission["date"] == "2026-09-26"
    assert "Ziyun Zhang" in permission["holder"]
    assert "publishing the resulting comparisons" in permission["quoted_sentence"]


def test_archive_size_and_hash(provenance: dict[str, Any]) -> None:
    archive = provenance["archive"]
    assert archive["size_bytes"] == PINNED_SIZE
    assert re.fullmatch(r"[0-9a-f]{64}", archive["sha256"])
    assert archive["sha256"].startswith("6d42c02f")


def test_size_disclosure(provenance: dict[str, Any]) -> None:
    d = provenance["size_disclosure"]
    assert d["audit_recorded_size_bytes"] == AUDIT_SIZE
    assert d["pinned_size_bytes"] == provenance["archive"]["size_bytes"] == PINNED_SIZE
    assert d["audit_recorded_hash"] is None
    assert d["release_manifest_bytes_at_audited_commit"] == AUDIT_SIZE
    assert d["release_manifest_at_repository_head"]["bytes"] == PINNED_SIZE
    assert d["asset_created_at"] > d["release_published_at"]
    assert d["asset_updated_at"] >= d["asset_created_at"]


def test_rows(report: dict[str, Any]) -> None:
    rows = report["rows"]
    ids = [r["case_id"] for r in rows]
    assert len(rows) == 450
    assert len(set(ids)) == 450
    assert ids == sorted(ids)
    for r in rows:
        assert r["residual_check"] in {"pass", "fail", "absent"}
        assert not set(r["files_present"]) & set(r["files_missing"])
        assert isinstance(r["parse_errors"], list)
    assert report["summary"]["total"] == 450


def test_residual_check_split(report: dict[str, Any]) -> None:
    assert Counter(r["residual_check"] for r in report["rows"]) == {
        "pass": 425,
        "fail": 24,
        "absent": 1,
    }
    assert report["summary"]["residual_check"] == {"absent": 1, "fail": 24, "pass": 425}
    absent = [r for r in report["rows"] if r["residual_check"] == "absent"]
    assert all("model_checks.json" in r["files_missing"] for r in absent)


def test_audit_scope_counts(report: dict[str, Any]) -> None:
    rows = report["rows"]
    assert Counter(r["family"] for r in rows) == {
        "idaes": 188,
        "watertap": 158,
        "prommis": 25,
        "gtep": 21,
        "reflo": 19,
        "mvo": 18,
        "dispatches": 11,
        "reaktoro": 6,
        "pareto": 4,
    }
    assert Counter(r["model_type"] for r in rows) == {
        "native_IDAES": 237,
        "original_reduced_model": 163,
        "new_reduced_demo": 11,
        "native_grid_optimization": 21,
        "native_design_optimization": 17,
        "EXPOsan_dynamic_BDF": 1,
    }


def test_full82(report: dict[str, Any]) -> None:
    in82 = [r for r in report["rows"] if r["in_full82"]]
    assert len(in82) == 82
    assert Counter(r["family"] for r in in82) == {
        "watertap": 41,
        "idaes": 20,
        "prommis": 20,
        "dispatches": 1,
    }
    assert Counter(r["residual_check"] for r in in82)["fail"] == 7
    assert report["summary"]["full82_total"] == 82
    assert report["source"]["split_file"]["case_count"] == 82
    assert re.fullmatch(r"[0-9a-f]{64}", report["source"]["split_file"]["sha256"])
    assert (
        "not independently verified" in report["source"]["split_file"]["paper_evaluation_binding"]
    )


def test_inaccessible_assets(report: dict[str, Any]) -> None:
    assets = report["inaccessible_assets"]
    ids = [a["id"] for a in assets]
    assert len(set(ids)) == len(ids)
    for required in (
        "visual_descriptor_adapter",
        "topology_agent_adapter",
        "specification_agent_adapter",
        "role_prompts_and_workflow",
        "scoring_harness",
        "score_run_binding_82",
    ):
        assert required in ids
    for a in assets:
        assert a["status"] in {"present", "absent"}
        assert a["sought_where"], a["id"]
        for place in a["sought_where"]:
            assert place["location"]
            assert place["result"]
        locations = " ".join(p["location"] for p in a["sought_where"])
        assert "release assets" in locations
        assert "repository tree" in locations
        assert "paper" in locations


def test_acquire_script_pins_match_provenance(provenance: dict[str, Any]) -> None:
    text = (DIR.parent.parent.parent / "scripts" / "m06_w27_acquire.py").read_text(encoding="utf-8")
    assert provenance["archive"]["sha256"] in text
    assert "220_802_919" in text
