"""V02 alpha Amendment 2, R-345: `independence_qualification` carries [A09] text only
(spec `docs/derivations/V02-alpha-release-spec.md` §18.1, assertions Am2.1–Am2.4).

The certificate writes one `independence_qualifications` entry, naming the binding provider, for
every check whose `independence_qualification` is not `None` (`verify/certificate.py`). Before
R-345 two producers put non-[A09] text in that field — the EXT-COUPLING checks (`external model,
R<n>`) and the derivative witness when it skipped columns (`not differenced: …`) — so every
coupled-route certificate carried four entries outside T06 A33 (A4)'s set (RC record at `C_α⁰`,
failure F1). Their facts stay where they were already recorded once: the `external_model` and
`derivative_witness_partial` limitations.

- S1, SYN-001 nominal (K05's session): no partial witness, no external unit; the fix moves
  nothing there, and a fix that dropped the prefixed entries would fail Am2.2 here.
- S2, `pr-c1-v1` revision V1 (M02 WO-8): the witness skips the exactly-zero stream component
  flows; no external unit. It isolates the witness defect.
- S3, `C1-LOOP-M02-v1` on `revision_coupled` with the in-process stand-in `standin-x025-v1`,
  `CONVERGED` with a certificate. It carries the EXT defect.

Each state asserts its precondition, so a fixture that stops meeting it fails rather than passing
vacuously. Am2.4's negative controls restore the old notes by monkeypatching the producers and
require Am2.1 and Am2.2 to fail, naming exactly the restored check ids.
"""

from __future__ import annotations

import dataclasses
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest
from conftest import REPO_ROOT
from m02_wo8_support import solve as solve_revision
from test_m02_wo8_region import FLOWSHEETS
from test_m02_wo10_coupled import loop, runner_in
from test_m02_wo10_coupled import solve as solve_coupled

from openflowsheet.application import coupled_run
from openflowsheet.application.coupled_run import LiveExperiments
from openflowsheet.models import flow_id
from openflowsheet.models.revision_flowsheet import parse_revision
from openflowsheet.run.bundle import read_artifact
from openflowsheet.run.session import run_session
from openflowsheet.thermo import PropertyProvider
from openflowsheet.thermo.pr_c1 import PrC1Provider
from openflowsheet.thermo.syn001 import Syn001Provider
from openflowsheet.verify import checks as verify_checks
from openflowsheet.verify.certificate import verify_revision
from openflowsheet.verify.checks import qualification, witness_skipped_columns

#: T06 A33 (A4)'s prefixes (spec §8.4 (A4), R-080), restated here so the rule is not the
#: certificate's own.
A33_PREFIXES = ("energy_balance.", "phase_admissibility.", "independent_split.")
WITNESS_IDS = ("derivative_witness.on_pattern", "derivative_witness.off_pattern")
EXT_IDS = ("EXT-COUPLING:reactor:xi", "EXT-COUPLING:reactor:T")


# == the two rules ================================================================================


def am2_1(certificate: Mapping[str, Any], provider: PropertyProvider) -> list[str]:
    """Am2.1: the ids of checks whose qualification is set but does not start with
    `checks.qualification(provider)`, sorted. Empty is a pass."""
    prefix = qualification(provider)
    return sorted(
        check["id"]
        for check in certificate["checks"]
        if check["independence_qualification"] is not None
        and not check["independence_qualification"].startswith(prefix)
    )


def am2_2(certificate: Mapping[str, Any], provider: PropertyProvider) -> list[str]:
    """Am2.2: the ids where `independence_qualifications` and A33 (A4)'s set differ (either way),
    and the ids of entries whose four provider members are not `describe()`'s, sorted. Empty is a
    pass."""
    described = provider.describe()
    members = (
        described.provider_id,
        described.implementation_sha256,
        described.data_sha256,
        described.reference_convention,
    )
    entries = certificate["independence_qualifications"]
    qualified = {entry["check_id"] for entry in entries}
    expected = {
        check["id"]
        for check in certificate["checks"]
        if check["id"].startswith(A33_PREFIXES) and check["result"] in ("pass", "fail")
    }
    wrong = {
        entry["check_id"]
        for entry in entries
        if (
            entry["provider_id"],
            entry["implementation_sha256"],
            entry["data_sha256"],
            entry["reference_convention"],
        )
        != members
    }
    assert len(qualified) == len(entries), "one entry per check id"
    return sorted((qualified ^ expected) | wrong)


def limitations(certificate: Mapping[str, Any], kind: str) -> list[dict[str, Any]]:
    return [item for item in certificate["limitations"] if item["kind"] == kind]


def by_id(certificate: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {check["id"]: check for check in certificate["checks"]}


# == the three states =============================================================================


def s1_certificate(directory: Path) -> dict[str, Any]:
    """K05's session on SYN-001 nominal (`scripts/k03_schema_fixtures.py`)."""
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    from k03_schema_fixtures import POLICY
    from k03_schema_fixtures import flowsheet as build

    manifest = run_session(build(), directory, policy=POLICY, run_id="run-am2-s1")
    assert manifest.verification_status == "VERIFIED"
    certificate: dict[str, Any] = read_artifact(directory, "solution-certificate.json")
    # Precondition: neither defect can show here.
    assert limitations(certificate, "derivative_witness_partial") == []
    assert limitations(certificate, "external_model") == []
    assert certificate["independence_qualifications"], "S1 qualifies its energy checks"
    return certificate


def s2_certificate() -> tuple[dict[str, Any], list[str]]:
    """V1 on `pr-c1-v1`, and the columns the witness must skip: the stream component flows that
    are exactly 0.0 at the certified state (design note §14.3 C2)."""
    document = FLOWSHEETS["V1"]()
    solved = solve_revision(document)
    assert solved.run.state is not None
    state = solved.run.state
    view = parse_revision(document)
    zero = frozenset(
        name
        for stream in view.streams
        for c in view.components
        if state[name := flow_id(stream, c)] == 0.0
    )
    certificate = verify_revision(
        solved.binding, document, solved.run, solve_plan=solved.plan.steps[-1].solve_plan
    ).as_document()
    assert certificate["verification_status"] == "VERIFIED"
    # Precondition: the witness skips at least one column; no external unit.
    (partial,) = limitations(certificate, "derivative_witness_partial")
    assert partial["columns"]
    assert limitations(certificate, "external_model") == []
    return certificate, witness_skipped_columns(solved.binding.spec.variable_ids, zero)


def s3_certificate(directory: Path) -> dict[str, Any]:
    """The coupled loop with the in-process stand-in (M02 WO-10's G8 (a) solve)."""
    manifest, artifacts = solve_coupled(
        loop(), directory / "bundle", LiveExperiments(runner_in(directory / "records"))
    )
    assert (manifest.outcome, manifest.verification_status) == ("CONVERGED", "VERIFIED")
    certificate: dict[str, Any] = artifacts["solution-certificate.json"]
    # Precondition: one `external_model` limitation per external unit, and its two checks.
    units = {check["subject"] for check in certificate["checks"] if check["id"] in EXT_IDS}
    assert units == {"reactor"}
    assert [item["unit"] for item in limitations(certificate, "external_model")] == ["reactor"]
    assert set(EXT_IDS) <= set(by_id(certificate))
    return certificate


@pytest.fixture(scope="module")
def s1(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    return s1_certificate(tmp_path_factory.mktemp("s1"))


@pytest.fixture(scope="module")
def s2() -> tuple[dict[str, Any], list[str]]:
    return s2_certificate()


@pytest.fixture(scope="module")
def s3(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    return s3_certificate(tmp_path_factory.mktemp("s3"))


# == Am2.1–Am2.3 ==================================================================================


def test_am2_1_and_2_s1_syn001_nominal(s1: dict[str, Any]) -> None:
    provider = Syn001Provider()
    assert am2_1(s1, provider) == []
    assert am2_2(s1, provider) == []


def test_am2_1_to_3_s2_a_partial_witness(s2: tuple[dict[str, Any], list[str]]) -> None:
    certificate, skipped = s2
    provider = PrC1Provider()
    assert am2_1(certificate, provider) == []
    assert am2_2(certificate, provider) == []
    checks = by_id(certificate)
    assert [checks[name]["independence_qualification"] for name in WITNESS_IDS] == [None, None]
    (partial,) = limitations(certificate, "derivative_witness_partial")
    assert skipped and partial["columns"] == skipped


def test_am2_1_to_3_s3_a_coupled_run(s3: dict[str, Any]) -> None:
    provider = PrC1Provider()
    assert am2_1(s3, provider) == []
    assert am2_2(s3, provider) == []
    checks = by_id(s3)
    assert [checks[name]["independence_qualification"] for name in EXT_IDS] == [None, None]
    if limitations(s3, "derivative_witness_partial"):
        assert [checks[name]["independence_qualification"] for name in WITNESS_IDS] == [
            None,
            None,
        ]


# == Am2.4: the negative controls =================================================================


def test_am2_4a_the_old_ext_note_restored_fails_am2_1_and_2_at_s3(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = coupled_run._check  # noqa: SLF001 - the producer the control restores

    def old_note(*args: Any, **kwargs: Any) -> Any:
        result = original(*args, **kwargs)
        return dataclasses.replace(result, independence_qualification="external model, R1")

    monkeypatch.setattr(coupled_run, "_check", old_note)
    certificate = s3_certificate(tmp_path / "s3")
    provider = PrC1Provider()
    assert am2_1(certificate, provider) == sorted(EXT_IDS)
    assert am2_2(certificate, provider) == sorted(EXT_IDS)
    s1 = s1_certificate(tmp_path / "s1")
    assert am2_1(s1, Syn001Provider()) == am2_2(s1, Syn001Provider()) == []


def test_am2_4b_the_old_witness_note_restored_fails_am2_1_and_2_at_s2(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = verify_checks.derivative_witness

    def old_note(*args: Any, unstenciled: frozenset[str] = frozenset(), **kwargs: Any) -> Any:
        results = original(*args, unstenciled=unstenciled, **kwargs)
        if not unstenciled:
            return results
        note = (
            f"not differenced: {len(unstenciled)} exactly-zero pr-c1-v1 stream-flow columns "
            "(design note §14.3 C2)"
        )
        return [dataclasses.replace(r, independence_qualification=note) for r in results]

    monkeypatch.setattr(verify_checks, "derivative_witness", old_note)
    certificate, _ = s2_certificate()
    provider = PrC1Provider()
    assert am2_1(certificate, provider) == sorted(WITNESS_IDS)
    assert am2_2(certificate, provider) == sorted(WITNESS_IDS)
    s1 = s1_certificate(tmp_path / "s1")
    assert am2_1(s1, Syn001Provider()) == am2_2(s1, Syn001Provider()) == []
