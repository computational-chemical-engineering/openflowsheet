"""T06 W9: the `t06` key of the K05 identity document (`scripts/t06_identity.py`; spec §10, A45).

Spec `docs/derivations/T06-corpus-spec.md` §10 (Amendments 1–3) and ADR 0014 D8 (amended): the R0
records of §4.3's new flowsheets, REF-01…REF-07 and ADV-06 L/M/H under their registered policies,
NET-02's `T05b-v2` control, STR-02's and STR-06's validation, STA-03's conversion and tear records
(A69's two spellings too, each tear record equal to SYN-001-nominal's), STA-04's declared order
and record (equal to C2's), §8.7's three typed initializer failures, and the ensemble's
definition. Asserted here: the key's shape and registered outcomes, the ensemble definition
against the registry, the published starts and the twin's KATs, floats-free, digests only of
declared inputs, and the same twice on one machine. CI compares the document key by key across
x86-64 and aarch64 (A45; `.github/workflows/ci.yml`, job `identity`); the document minus `t06` is
the pre-W9 document (`docs/t06-measurements.md`, "W9").
"""

from __future__ import annotations

import re
import sys
from functools import cache
from typing import Any

from conftest import REPO_ROOT, load_yaml
from test_t06_w4_registry import BY_ID, REGISTRY
from test_t06_w6_generator import PUBLISHED
from test_t06_w11_initializer import FEEDS

from openflowsheet.run.identity import floats_in

TWIN = load_yaml(REPO_ROOT / "benchmarks" / "t06" / "reference_values.yaml")
NEW_CASES = [
    "THM-01",
    "THM-02",
    "THM-10",
    "STA-02",
    "NET-02",
    "NET-03",
    "NET-06",
    "NET-09",
    "NET-10",
    "NET-11",
]
REFERENCES = ["REF-01", "REF-02", "REF-03", "REF-04", "REF-05", "REF-06", "REF-07"]
FULL_RECORD = {
    "plan",
    "outcome",
    "events",
    "solver_counters",
    "structural",
    "root_fingerprint",
    "message",
    "certificate",
}
#: The digests an R0 document may carry: identities of declared inputs (the constants, the model
#: version's structure hash, the variable ids, a registered policy's values), never of a
#: computed state.
DECLARED_DIGESTS = {"constants_sha256", "model_version", "variable_ids_sha256", "policy_sha256"}
HEX64 = re.compile(r"[0-9a-f]{64}")
#: No R0 message carries a digit sequence computed from a state (T05b B20 (c)).
FLOAT = re.compile(r"\d\.\d|\d[eE][-+]?\d")


def _digest_keys(node: Any, key: str = "") -> set[str]:
    if isinstance(node, dict):
        return set().union(*(_digest_keys(value, name) for name, value in node.items()))
    if isinstance(node, list):
        return set().union(*(_digest_keys(value, key) for value in node))
    return {key} if isinstance(node, str) and HEX64.search(node) else set()


def _identity() -> dict[str, Any]:
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    from t06_identity import identity

    return identity()


@cache
def _document() -> dict[str, Any]:
    return _identity()


def _records(document: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Every full revision-path R0 record in the key, by a readable name."""
    return {
        **{f"cases.{k}": v for k, v in document["cases"].items()},
        **{f"controls.{k}": v for k, v in document["controls"].items()},
        **{f"references.{k}": v for k, v in document["references"].items()},
        **{f"adv06.{k}": v for k, v in document["adv06"].items()},
        "sta04.record": document["sta04"]["record"],
    }


def test_the_key_carries_the_registered_records() -> None:
    document = _document()
    assert list(document) == [
        "cases",
        "controls",
        "references",
        "adv06",
        "validation",
        "sta03",
        "sta04",
        "initializer_failures",
        "ensemble",
    ]
    assert list(document["cases"]) == NEW_CASES
    assert list(document["references"]) == REFERENCES
    for name, entry in _records(document).items():
        expected = FULL_RECORD if entry["outcome"] == "CONVERGED" else FULL_RECORD - {"certificate"}
        assert set(entry) == expected, name
    for group in ("cases", "references"):
        for name, entry in document[group].items():
            assert entry["outcome"] == "CONVERGED", name
            assert entry["certificate"]["verification_status"] == "VERIFIED", name
            assert entry["plan"]["policy_id"] == "T06-revision-v2", name
            assert entry["root_fingerprint"] is not None and entry["message"] == "", name
    for case in NEW_CASES:
        assert BY_ID[case]["policy"] == "T06-revision-v2"
    assert REGISTRY["reference_fixtures"]["policy"] == "T06-revision-v2"


def test_net02_has_its_registered_entry_and_its_control() -> None:
    document = _document()
    assert document["cases"]["NET-02"]["certificate"]["verification_status"] == "VERIFIED"
    (control,) = BY_ID["NET-02"]["controls"]
    entry = document["controls"]["NET-02|T05b-v2"]
    assert "T05b-v2" in control["policies"]
    assert entry["outcome"] == control["code"] == "BOUND_BLOCKED"
    assert entry["plan"]["policy_id"] == "T05b-v2"
    assert entry["root_fingerprint"] is None and "certificate" not in entry


def test_adv06_levels_are_their_registered_outcomes() -> None:
    adv06 = _document()["adv06"]
    assert list(adv06) == ["L", "M", "H"]
    assert adv06["L"]["certificate"]["verification_status"] == "VERIFIED"
    assert adv06["M"]["outcome"] == "CONVERGED"
    assert adv06["M"]["certificate"]["verification_status"] == "UNVERIFIED"
    assert adv06["H"]["outcome"] != "CONVERGED"
    assert all(level["plan"]["policy_id"] == "T06-revision-v2" for level in adv06.values())


def test_validation_sta03_sta04_and_the_initializer_failures() -> None:
    document = _document()
    validation = document["validation"]
    assert validation["STR-02"]["status"] == "DRAFT"
    assert validation["STR-06"]["status"] == "INVALID"
    assert ["COMP-03", "FAIL"] in validation["STR-06"]["checks"]
    for check in BY_ID["STR-02"]["expected"]["not_run"]:
        assert [check, "NOT_RUN"] in validation["STR-02"]["checks"]

    sta03 = document["sta03"]
    assert list(sta03) == [
        "SYN-001-T06-STA03-kgs",
        "SYN-001-T06-STA03-degC",
        "SYN-001-nominal:SPEC-feed-n-A=3.6kmol/h",
        "SYN-001-nominal:SPEC-feed-T=80.33degF",
    ]
    tears = [entry["tear"] for entry in sta03.values()]
    assert all(tear == tears[0] for tear in tears)
    assert tears[0]["outcome"] == "CONVERGED"
    assert tears[0]["certificate"]["verification_status"] == "VERIFIED"
    for name, entry in sta03.items():
        assert entry["status"] == "READY_FOR_SIMULATION", name
        (conversion,) = entry["conversions"]
        assert entry["dim01"] == {"result": "PASS", "implicated": [conversion["input_id"]]}
        assert conversion["source"] == "specification"
    assert sta03["SYN-001-T06-STA03-kgs"]["conversions"][0]["si_value"] == "1.0"
    assert sta03["SYN-001-T06-STA03-degC"]["conversions"][0]["si_value"] == "300.0"

    assert document["sta04"]["declared_components"] == ["C", "A", "B"]
    assert document["sta04"]["record"]["certificate"]["verification_status"] == "VERIFIED"

    failures = document["initializer_failures"]
    assert list(failures) == ["450.0", "279.0", "400.0"]
    for temperature, (message, exact) in FEEDS.items():
        entry = failures[repr(temperature)]
        assert entry["outcome"] == "INITIALIZATION_FAILED"
        # R-029: the key records the typed prefix `initializer_failed(<id>): <status>: <unit>`
        # only (the 400 K text quotes a computed number); A62's exact messages are asserted by
        # `tests/test_t06_w11_initializer.py`.
        del exact
        assert entry["message"] == ": ".join(message.split(": ")[:3])
        assert not FLOAT.search(entry["message"]), entry["message"]


def test_the_ensemble_definition_is_the_registered_one() -> None:
    ensemble = _document()["ensemble"]
    registered = REGISTRY["ensemble"]
    assert [case["case"] for case in ensemble["cases"]] == registered["cases"]
    published = {entry["case"]: entry for entry in PUBLISHED["cases"]}
    for case in ensemble["cases"]:
        entry = published[case["case"]]
        assert case["fixture"] == entry["fixture"] and case["path"] == entry["path"]
        assert case["coordinates"] == [c["id"] for c in entry["coordinates"]], case["case"]
    policies = REGISTRY["policies"]
    assert {path: p["policy_id"] for path, p in ensemble["policies"].items()} == (
        registered["policies"]
    )
    for entry in ensemble["policies"].values():
        assert entry["policy_sha256"] == policies[entry["policy_id"]]["sha256"]
    assert (ensemble["profile"], ensemble["key_prefix"], ensemble["rng"]) == (
        "nominal",
        "T06-ens-v1",
        registered["law"]["rng"],
    )
    kats = TWIN["closed_form"]["draw_known_answers"]
    assert ensemble["kats_k53"] == [[kat["key"], kat["k53"]] for kat in kats]


def test_the_key_is_floats_free_and_deterministic() -> None:
    document = _document()
    assert floats_in(document) == []
    assert _digest_keys(document) <= DECLARED_DIGESTS
    for name, entry in _records(document).items():
        fingerprint = entry["root_fingerprint"]
        if fingerprint is not None:
            assert "opening_state_sha256" not in fingerprint, name
            assert "full_state_sha256" not in fingerprint, name
        assert not FLOAT.search(entry["message"]), (name, entry["message"])
    # §8.7's messages carry the registered feed temperatures and domain bounds (A62), checked
    # against their registered strings above, not computed state.
    assert _identity() == document, "the same twice on one machine"
