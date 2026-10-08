"""M06 WO-15: the W27 registration re-derives its committed files (registration §14.1).

`benchmarks/m06/openidaes450/registration.json` and `dry_illustration.json` must be byte-identical
to what `docs/derivations/scripts/m06_w27_registration.py` writes from the committed
`case_facts.json` and the snapshot stored in the dry illustration, and every generator self-claim
(GC-*) must hold: a table edit that leaves a dead entry, an unadjudicated unit key or an unaliased
v0.2 spelling fails here.

`case_facts.json` itself is re-derived from the pinned archive by `m06_w27_registration.py facts
--check`, which needs the git-ignored archive (`scripts/m06_w27_acquire.py`); it is run for the
evidence manifest, not on every gate. That command exits 2, saying so, when the archive is absent.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "docs" / "derivations" / "scripts" / "m06_w27_registration.py"


@pytest.fixture(scope="module")
def generator() -> ModuleType:
    spec = importlib.util.spec_from_file_location("m06_w27_registration", GENERATOR)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def facts(generator: ModuleType) -> dict[str, object]:
    document: dict[str, object] = json.loads(generator.FACTS_JSON.read_bytes())
    return document


def test_every_registration_claim_holds(generator: ModuleType, facts: dict[str, object]) -> None:
    failing = [claim for claim, holds, _ in generator.registration_claims(facts) if not holds]
    assert failing == []


def test_registration_json_is_what_the_generator_writes(
    generator: ModuleType, facts: dict[str, object]
) -> None:
    fresh = generator.dump(generator.build_registration(facts))
    assert generator.REGISTRATION_JSON.read_bytes() == fresh


def test_dry_illustration_is_reproduced_and_its_claims_hold(
    generator: ModuleType, facts: dict[str, object]
) -> None:
    stored = json.loads(generator.DRY_JSON.read_bytes())
    dry = generator.build_dry(facts, stored["snapshots"]["today"]["snapshot"])
    assert [c["claim"] for c in dry["generator_claims"] if not c["holds"]] == []
    assert generator.DRY_JSON.read_bytes() == generator.dump(dry)


def test_the_dry_illustration_says_it_is_not_the_campaign_sample(generator: ModuleType) -> None:
    stored = json.loads(generator.DRY_JSON.read_bytes())
    assert stored["warning"].startswith("NOT THE CAMPAIGN SAMPLE.")


def test_the_registered_card_hashes_cover_all_450_cases(generator: ModuleType) -> None:
    registration = json.loads(generator.REGISTRATION_JSON.read_bytes())
    access = json.loads(generator.ACCESS_JSON.read_bytes())
    cards = registration["prompt"]["card"]["sha256_by_case"]
    assert sorted(cards) == sorted(row["case_id"] for row in access["rows"])
    assert len(cards) == 450
