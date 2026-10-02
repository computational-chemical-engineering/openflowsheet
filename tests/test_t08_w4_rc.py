"""T08 W4.4: `scripts/t08_rc.py`, the release-candidate job's steps (release spec §8.2).

The steps themselves run at `C` (CI dispatch and the session's local runs). Here: every
registered value the script restates equals its source; the certificate audit (T08.A34) passes
the registered certificate and refuses each kind of tampering; the identity digests follow
§W0.1's convention; the test-outcome judgement fails a missing, failed or skipped node; and the
enumerations A45, A47 and A48 rely on are what their sources say.
"""

from __future__ import annotations

import copy
import hashlib
import json
import sys
from typing import Any

import pytest
from conftest import REPO_ROOT, load_yaml

sys.path.insert(0, str(REPO_ROOT / "scripts"))
import t08_rc  # noqa: E402


def test_the_registered_values_are_their_sources() -> None:
    import test_t07_identity
    import test_t08_w1_identity_substitution
    import test_t08_w2_surface_digest

    lock = (REPO_ROOT / "requirements.lock").read_bytes()
    assert t08_rc.LOCK_SHA256 == hashlib.sha256(lock).hexdigest()
    assert t08_rc.K05_MINUS_T07_SHA256 == test_t07_identity.K05_MINUS_T07_SHA256_R149
    assert t08_rc.T07_KEY_SHA256 == test_t08_w1_identity_substitution.T07_KEY_SHA256_R149
    assert t08_rc.R133_DESCRIPTIONS_SHA256 == test_t08_w2_surface_digest.T08_DESCRIPTIONS_SHA256
    reference = load_yaml(REPO_ROOT / "benchmarks" / "t08" / "reference_values.yaml")
    registered = reference["registered"]["v17_c2_tool_descriptions_sha256"]["sha256"]
    assert t08_rc.V17_C2_DESCRIPTIONS_SHA256 == registered
    for path in (
        t08_rc.NOMINAL_CERTIFICATE,
        t08_rc.P03_CASADI_INVENTORY,
        t08_rc.T06_MANIFEST,
        *t08_rc.A30_SUMMARIES.values(),
    ):
        assert (REPO_ROOT / path).is_file(), path


def _nominal() -> dict[str, Any]:
    document: dict[str, Any] = json.loads(
        (REPO_ROOT / t08_rc.NOMINAL_CERTIFICATE).read_text(encoding="utf-8")
    )
    return document


def test_the_audit_passes_the_registered_certificate() -> None:
    validator = t08_rc._schema_validator()
    document = _nominal()
    assert document["independence_qualifications"], "the fixture qualifies energy checks"
    assert t08_rc.audit_certificate(document, validator) == []


def test_the_audit_refuses_a_missing_or_extra_qualification() -> None:
    validator = t08_rc._schema_validator()
    missing = _nominal()
    missing["independence_qualifications"] = missing["independence_qualifications"][1:]
    assert "a09.qualified_check_ids" in t08_rc.audit_certificate(missing, validator)
    extra = _nominal()
    entry = copy.deepcopy(extra["independence_qualifications"][0])
    entry["check_id"] = "residual.U-FEED:FEED-T"
    extra["independence_qualifications"].append(entry)
    assert "a09.qualified_check_ids" in t08_rc.audit_certificate(extra, validator)


def test_the_audit_refuses_another_provider_and_a_missing_regularity() -> None:
    validator = t08_rc._schema_validator()
    other = _nominal()
    other["independence_qualifications"][0]["data_sha256"] = "0" * 64
    assert any(p.startswith("a09.provider(") for p in t08_rc.audit_certificate(other, validator))
    absent = _nominal()
    del absent["regularity"]
    assert any(p.startswith("schema:") for p in t08_rc.audit_certificate(absent, validator))


def test_identity_digests_follow_the_w0_1_convention() -> None:
    document = {"structural_sha256": "s", "t02": {"a": 1}, "t07": {"b": [1, 2]}}
    data = (json.dumps(document, indent=1, sort_keys=True) + "\n").encode()
    digests = t08_rc.identity_digests(data)
    assert digests["whole"] == hashlib.sha256(data).hexdigest()
    rest = {"structural_sha256": "s", "t02": {"a": 1}}
    assert (
        digests["minus_t07"]
        == hashlib.sha256((json.dumps(rest, indent=1, sort_keys=True) + "\n").encode()).hexdigest()
    )
    assert digests["t07_key"] == hashlib.sha256(b'{"b": [1, 2]}').hexdigest()


@pytest.mark.parametrize(
    ("outcomes", "field"),
    [
        ({}, "missing"),
        ({"tests/t.py::f[1]": "failed"}, "failed"),
        ({"tests/t.py::f": "skipped"}, "skipped"),
        ({"tests/t.py::f": "xpassed"}, "failed"),
    ],
)
def test_judge_reports_what_did_not_pass(outcomes: dict[str, str], field: str) -> None:
    assert t08_rc.judge(["tests/t.py::f"], outcomes)[field]


def test_judge_passes_every_parametrization_of_a_named_function() -> None:
    value = t08_rc.judge(
        ["tests/t.py::f"], {"tests/t.py::f[a]": "passed", "tests/t.py::g": "failed"}
    )
    assert value == {
        "nodes": 1,
        "outcomes": {"passed": 1},
        "missing": [],
        "failed": [],
        "skipped": [],
    }


def test_a47_a48_name_registered_tests() -> None:
    named = t08_rc.registered_functions((*t08_rc.A47_ASSERTIONS, *t08_rc.A48_ASSERTIONS))
    assert all(functions for functions in named.values()), named
    for functions in named.values():
        for function in functions:
            assert (REPO_ROOT / function.split("::", 1)[0]).is_file(), function


def test_a45_enumerations() -> None:
    assert t08_rc.k05_registered_cases()[0] == "SYN-001-nominal"
    assert len(t08_rc.k05_registered_cases()) == 5
    # `test_g8_every_eligible_revision_ends_typed_with_one_bundle_document` counts 47.
    assert len(t08_rc.g8_revisions()) == 47


def test_a45_has_no_open_set() -> None:
    # Amendment R3 1: T06 A34 left A45 for T08.A46; the two sets are counted per set.
    assert t08_rc.A45_SETS == ("k05", "g8")
    assert not hasattr(t08_rc, "T06_A34_OPEN")


def test_a46_replay_set_is_first_starts_and_retained_failures() -> None:
    classes = {("A", 0): "SUCCESS", ("A", 1): "SUCCESS", ("A", 2): "F-STALL", ("B", 0): "F-GEN"}
    record = {"records": [{"case": c, "start": s} for c, s in classes]}
    found = t08_rc.a34_replay_set(record, lambda r: classes[(r["case"], r["start"])])
    assert found == [["A", 0], ["A", 2], ["B", 0]]


def test_a46_replay_output_is_parsed_line_by_line() -> None:
    stdout = (
        "NET-01  00 MATCH\n"
        "NET-02  03 DIFFER\n"
        "    outcome: CONVERGED != FAILED\n"
        "('NET-03', 7): not generated (F-GEN); nothing to replay\n"
        "STR-01  00 MATCH\n"
    )
    parsed = t08_rc.parse_replay(stdout)
    assert parsed["MATCH"] == [["NET-01", 0], ["STR-01", 0]]
    assert parsed["DIFFER"] == [["NET-02", 3]]
    assert len(parsed["not_generated"]) == 1


def test_bundle_directories_are_portable_artifact_paths() -> None:
    """RC run 36904782855's `bundle-set` upload failed on the revision id `T05b:DZ-3`
    (`actions/upload-artifact` refuses `":<>|*?` and CR/LF). A bundle directory percent-encodes
    them (and `%` itself, so distinct names stay distinct); the index keeps the revision's name."""
    unsafe = '":<>|*?\r\n'
    assert t08_rc._portable("T05b:DZ-3") == "T05b%3ADZ-3"
    assert t08_rc._portable("SYN-001-nominal") == "SYN-001-nominal"
    names = ["a:b", "a%3Ab", "a%b", "a%25b", "x|y*z?"]
    encoded = [t08_rc._portable(name) for name in names]
    assert len(set(encoded)) == len(names)
    assert not any(c in unsafe for name in encoded for c in name)
