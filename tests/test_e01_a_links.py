"""E01 WO-A3a (design note §9.1, R-863; assertion A43, partition part): the study and
optimization-report links are `$defs` of `assessment.schema.json`, so the two `sha256` names they
declare are E01's addendum's, and v2's partition does not move."""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from jsonschema import ValidationError

from openflowsheet.application.types import _validator

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))
import t08_numerical_policy  # noqa: E402

E01_ADDENDUM = REPO_ROOT / "benchmarks" / "e01" / "numerical_policy_external.yaml"
V2 = REPO_ROOT / "benchmarks" / "t08" / "numerical_policy_v2.yaml"
V2_SHA256 = "6b449911f4e692051b08372fefaf0e205e9b2d746362e4fba2c4a9f6e19d707c"
DIGEST = "0" * 64


def test_the_e01_exact_names_are_the_two_link_digests_and_lie_outside_v2s_domain() -> None:
    table = t08_numerical_policy.external_policy(E01_ADDENDUM)
    assert table["exact_sha256"] == ["assessment_sha256", "regime_sha256"]
    assert table["schemas"] == ["assessment-report.schema.json", "assessment.schema.json"]
    assert not set(table["exact_sha256"]) & t08_numerical_policy.schema_sha256_names()
    declared = t08_numerical_policy.schema_sha256_names(external=True, addendum=table)
    assert {"assessment_sha256", "regime_sha256"} <= declared
    assert "state_sha256" not in table["exact_sha256"]


def test_the_policy_check_passes_with_v2_unchanged() -> None:
    assert hashlib.sha256(V2.read_bytes()).hexdigest() == V2_SHA256
    run = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "t08_numerical_policy.py"), "--check"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert run.returncode == 0, run.stdout + run.stderr
    assert "equals" in run.stdout


def _check(reference: str, document: Any) -> None:
    _validator("assessment.schema.json#/$defs/" + reference).validate(document)


def test_the_assessment_link_validates_and_is_closed() -> None:
    link = {"assessment_id": "a", "assessment_sha256": DIGEST}
    _check("assessment_link", link)
    _check("assessment_link", {**link, "regime_sha256": DIGEST})
    for bad in (
        {**link, "extra": 1},
        {"assessment_id": "a"},
        {**link, "assessment_sha256": "x"},
        {**link, "assessment_id": ""},
    ):
        with pytest.raises(ValidationError):
            _check("assessment_link", bad)


def test_the_formulation_assessment_validates_and_is_closed() -> None:
    record = {
        "assessment_id": "a",
        "assessment_sha256": DIGEST,
        "regime_sha256": DIGEST,
        "regime_entries": {"E1.size": "units:1"},
        "outputs": [{"id": "tac", "scale": 1.0e6}],
        "admissibility": [{"id": "E1.size.max", "nominal": 2.0}],
        "regime_bounds_active": [{"id": "E1.size.max", "slack": 0.0, "multiplier": -1.5}],
    }
    _check("formulation_assessment", record)
    for bad in (
        {**record, "extra": 1},
        {k: v for k, v in record.items() if k != "regime_sha256"},
        {**record, "outputs": [{"id": "tac", "scale": 0.0}]},
        {**record, "admissibility": [{"id": "x", "nominal": 1.0, "more": 1}]},
        {**record, "regime_entries": {"E1.size": ""}},
    ):
        with pytest.raises(ValidationError):
            _check("formulation_assessment", bad)
