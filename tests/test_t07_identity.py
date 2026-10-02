"""T07 W8a: the `t07` key of the K05 identity document (`scripts/t07_identity.py`; §15 W8, §16 G1).

Design note `docs/design/T07-jobs-and-bindings.md` §15 W8, ruling rounds 2 (the solution state's
R0) and 3 (the initializer's failure bundle), and `docs/T07_DECISIONS.md` W3-Q3 (R0 as written).
Asserted here, against expectations stated independently of the script: the runs' routes,
outcomes and registered policy hashes, their stage and output sequences, the failure bundle's R0
(ruling round 3 Q1-A4), STA-04's R0 equal to C2's (T06 A59), each contract run's R0 equal to the
same revision solved by direct calls (`t06_identity._revision_case`, G8's "R0 equal to the identity
key's record"); G10's refusal codes; ADR 0002 A1's verdicts from its registered reference; the
key floats-free, with digests of declared inputs and R0 structure only, and the same twice; the
inline and process executors give the same `runs`; and the K05 document minus `t07` is the
pre-W8 document, byte for byte (`9a7b4e6d…`, `docs/t07-measurements.md` §W0.1), moved since by
ADR 0025 D1.2's recording switch only (R-148: `29246e05…`, structural `e62a59a6…`; with v1
recorded again, `tests/t08_v2_substitution.py`, both are the registered values), and then by the
rename to `openflowsheet` only (R-149: `24af004a…`, structural `ed6d11f3…`; with the pre-rename
self-hashes, `tests/t08_rename_substitution.py`, both are R-148's). CI compares the
document key by key across x86-64 and aarch64 (`.github/workflows/ci.yml`, job `identity`).
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
import sys
from functools import cache
from pathlib import Path
from typing import Any

import pytest
from conftest import REPO_ROOT, load_yaml
from t07_corpus import CORPUS
from t08_rename_substitution import record_process_runtime
from t08_v2_substitution import record_v1
from test_t06_w4_registry import REGISTRY

from openflowsheet.application.local import LocalApplication
from openflowsheet.application.revisions import content_hash
from openflowsheet.run.identity import floats_in

sys.path.insert(0, str(REPO_ROOT / "scripts"))
import t07_identity  # noqa: E402

#: The K05 identity document as written before W8 (`docs/t07-measurements.md` §W0.1): the
#: document minus `t07` must still be it.
K05_BASELINE_SHA256 = "9a7b4e6d1e794e903a41ba2bd96ead58a074896380d80e37e0f06545cff3d4bc"
#: The same document since this build records `T08-numerical-policy-v2` (ADR 0025 D1.2; Frank,
#: 2026-10-02, R-148): `K05_BASELINE_SHA256` moved by that substitution only.
K05_MINUS_T07_SHA256_V2 = "29246e053ad126034c1aeef0f396ffe1d9f4dffcf5128f226720280bd1b656e5"
#: K05's `structural_sha256`, registered at T06 (ADR 0017, R-082), and since R-148.
STRUCTURAL_SHA256 = "915c97e82551c75c588ec4a4e41b060241d75e037366c099c285493165a97e27"
STRUCTURAL_SHA256_V2 = "e62a59a6b3634afd8f43eae399129a2d64bafb6e8ba90ad5fe0c9c1a9c5ad238"
#: Both since the rename to `openflowsheet` (Frank, 2026-10-02, R-149): `K05_MINUS_T07_SHA256_V2`
#: and `STRUCTURAL_SHA256_V2` moved by the SYN-001 provider's self-hash only.
K05_MINUS_T07_SHA256_R149 = "24af004ab5718e559bd3d40716d66e21d9b19043a26777a39a0da84c6fbdcb8e"
STRUCTURAL_SHA256_R149 = "ed6d11f3beb78c6f1debc481c6e525ce3ccb120bd30cdfd07e470f728e082e90"
#: The check policy K05's reference run registers (§W0.1, `check_policy_sha256`).
CHECK_POLICY_SHA256 = "21c44e105a1b78428047258af3030b8502957aab5d27f0389c2f143bcb3cf390"
#: Per case: the route `select_route` gives (ruling round 1 R2), the registered policy that
#: `"default"` resolves to on it (R2.3), the outcome and the verdict.
EXPECTED = {
    "SYN-001-nominal": ("revision_eo", "T06-revision-v2", "CONVERGED", "VERIFIED"),
    "SYN-001-UL-C2": ("revision_eo", "T06-revision-v2", "CONVERGED", "VERIFIED"),
    "SYN-001-T06-NET02": ("revision_eo", "T06-revision-v2", "CONVERGED", "VERIFIED"),
    "SYN-001-T06-STA04": ("revision_eo", "T06-revision-v2", "CONVERGED", "VERIFIED"),
    "SYN-001-A02-360": ("legacy_eo", "T04-W12", "CONVERGED", "VERIFIED"),
    "SYN-001-UL-C3X": ("revision_eo", "T06-revision-v2", "INITIALIZATION_FAILED", None),
}
#: §6.4's stages; a run with no certificate skips `verify` (the C3X job in W4a).
STAGES = ("resolve", "bind", "plan", "solve", "verify", "bundle")
CERTIFIED_OUTPUTS = ["solution_certificate", "run_manifest", "replay_bundle"]
FAILED_OUTPUTS = ["failure_bundle", "run_manifest", "replay_bundle"]
#: The members whose values may be SHA-256 digests: of declared inputs (the revision, the
#: policies, the constants, the model structure) and of R0 structure (K05 carries both kinds).
DECLARED_DIGESTS = {
    "structural_sha256",
    "policy_sha256",
    "check_policy_sha256",
    "revision_content_sha256",
    "artifact_r0_sha256",
    "constants_sha256",
    "model_version",
}
HEX64 = re.compile(r"(?<![0-9a-f])[0-9a-f]{64}(?![0-9a-f])")
NONCANONICAL_TEMPLATE = [
    "INVALID",
    [["SCHEMA-01", "FAIL", "document_not_canonical(<p>)"]],
    ["unsupported", "document_not_canonical(<p>)", []],
    ["unsupported", "document_not_canonical(<p>)", []],
    ["rejected", "document_not_canonical", "<edit-p>"],
]


@cache
def _key() -> dict[str, Any]:
    document: dict[str, Any] = json.loads(json.dumps(t07_identity.identity()))
    return document


def _digest_keys(node: Any, key: str = "") -> set[str]:
    if isinstance(node, dict):
        return set().union(*(_digest_keys(value, name) for name, value in node.items()))
    if isinstance(node, list):
        return set().union(*(_digest_keys(value, key) for value in node))
    return {key} if isinstance(node, str) and HEX64.search(node) else set()


# -- runs ---------------------------------------------------------------------------------------


def test_the_runs_are_the_registered_ones() -> None:
    runs = _key()["runs"]
    assert list(runs) == list(EXPECTED)
    policies = REGISTRY["policies"]
    for case, (path, policy, outcome, verdict) in EXPECTED.items():
        result = runs[case]["run_result"]
        assert result == {
            "outcome": outcome,
            "verification_status": verdict,
            "structural_sha256": result["structural_sha256"],
            "policy_sha256": policies[policy]["sha256"],
            "check_policy_sha256": CHECK_POLICY_SHA256,
            "revision_content_sha256": content_hash(CORPUS[case]()),
            "solve_path": path,
            "job_status": "completed",
        }, case
        r0 = runs[case]["r0"]
        assert r0["solve_path"] == path, case
        # Ruling round 2 (G8 (e)): the solution state iff a certificate.
        assert ("solution_state" in r0) == ("certificate" in r0) == (verdict is not None), case
        assert runs[case]["validation"]["status"] == "READY_FOR_SIMULATION", case


def test_the_event_projection_is_section_6() -> None:
    for case, (_, _, _, verdict) in EXPECTED.items():
        events = _key()["runs"][case]["events"]
        assert [event[0] for event in events] == list(range(len(events))), case
        assert [event[2] for event in events] == [False] * (len(events) - 1) + [True], case
        stages = [event[5] for event in events if event[1] == "progress"]
        completed = [event[3] for event in events if event[1] == "progress"]
        expected = [stage for stage in STAGES if verdict is not None or stage != "verify"]
        assert stages == expected and completed == [STAGES.index(s) for s in expected], case
        assert {event[4] for event in events if event[1] == "progress"} == {len(STAGES)}, case
        outputs = [event[6] for event in events if event[1] == "output"]
        assert outputs == (CERTIFIED_OUTPUTS if verdict else FAILED_OUTPUTS), case
        kinds = [event[1] for event in events]
        assert kinds[:2] == ["accepted", "started"] and kinds[-1] == "ended", case


def test_the_initializer_failure_bundle_is_ruling_round_3() -> None:
    """Q1-A4's R0 `failure` entry for UL-C3X (`initializer_failed(U-HX): …`)."""
    assert _key()["runs"]["SYN-001-UL-C3X"]["r0"]["failure"] == {
        "outcome": "INITIALIZATION_FAILED",
        "taxonomy": "initialization and recycle failures",
        "implicated_sources": ["U-HX"],
        "suggested_actions": ["supply_initial_guess"],
        "solver_counters": {"residual_calls": 0, "jacobian_calls": 0, "factorizations": 0},
    }


def test_sta04_is_c2() -> None:
    """T06 A59: STA-04's declaration, trace and certificate are C2's under the same policy."""
    runs = _key()["runs"]
    assert runs["SYN-001-T06-STA04"]["r0"] == runs["SYN-001-UL-C2"]["r0"]
    assert (
        runs["SYN-001-T06-STA04"]["run_result"]["structural_sha256"]
        == runs["SYN-001-UL-C2"]["run_result"]["structural_sha256"]
    )


@pytest.mark.parametrize(
    "case", ["SYN-001-nominal", "SYN-001-UL-C2", "SYN-001-T06-NET02", "SYN-001-T06-STA04"]
)
def test_a_contract_run_is_the_direct_run(case: str) -> None:
    """G8: the contract's R0 is the direct `plan_revision` → `execute_plan` → `verify_revision`
    record (`t06_identity._revision_case`, the `t06` key's builder) under the same policy. The
    plan is compared in its written form (W3-Q3): the direct record keeps `3.0` as `"3.0"`."""
    from t06_identity import _revision_case

    direct = json.loads(json.dumps(_revision_case(CORPUS[case](), "T06-revision-v2")))
    r0 = _key()["runs"][case]["r0"]
    for member in ("events", "solver_counters", "structural", "certificate"):
        assert r0[member] == direct[member], (case, member)
    assert direct["outcome"] == "CONVERGED"


# -- Q29 and ADR 0002 A1 -----------------------------------------------------------------------


def test_q29_codes_cover_g10_and_every_refusal_is_typed() -> None:
    q29 = _key()["q29"]
    assert list(q29) == [Path(name).stem for name in t07_identity.Q29_REVISIONS]
    for name in t07_identity.Q29_REVISIONS:
        document = load_yaml(REPO_ROOT / name)
        leaves = [t07_identity._pointer(path) for path in t07_identity._numeric_leaves(document)]
        assert len(leaves) > 40, name
        per_vector = q29[Path(name).stem]
        assert list(per_vector) == list(t07_identity.VECTORS)
        for label, (_, canonical) in t07_identity.VECTORS.items():
            groups = per_vector[label]
            assert sorted(p for _, pointers in groups for p in pointers) == sorted(leaves), (
                name,
                label,
            )
            if not canonical:
                assert groups == [[NONCANONICAL_TEMPLATE, leaves]], (name, label)
                continue
            for entry, _ in groups:
                assert entry[4] is None, (name, label)
                # Ruling round 5 S3: a canonical vector the frozen revision schema refuses ends
                # at SCHEMA-01, alone, as `schema_invalid(...)`, never `document_not_canonical`.
                if entry[0] == "INVALID" and entry[1][0][0] == "SCHEMA-01":
                    ((check_id, result, message),) = entry[1]
                    assert (check_id, result) == ("SCHEMA-01", "FAIL"), (name, label)
                    assert message.startswith("schema_invalid("), (name, label)


def test_adr0002_a1_codes_are_the_registered_verdicts() -> None:
    reference = json.loads(t07_identity.A1_REFERENCE.read_text("utf-8"))["integers"]
    expected = [
        [row["id"], row["n"], "committed", None, None]
        if row["verdict"] == "admitted"
        else [row["id"], row["n"], "rejected", "document_not_canonical", "/edits/0/value"]
        for row in reference
    ]
    assert _key()["adr0002_a1"] == expected


# -- the key's properties ---------------------------------------------------------------------


def test_the_key_is_floats_free_and_deterministic() -> None:
    key = _key()
    assert floats_in(key) == []  # a float survives the JSON round trip as a float
    assert _digest_keys({"runs": key["runs"], "q29": key["q29"]}) <= DECLARED_DIGESTS
    assert json.loads(json.dumps(t07_identity.identity())) == key, "the same twice"


def test_the_process_executor_gives_the_inline_runs(tmp_path: Path) -> None:
    LocalApplication.create(tmp_path / "project", project_id="t07-identity").close()
    with LocalApplication.open(tmp_path / "project", executor="process") as application:
        process = json.loads(json.dumps(t07_identity.runs(application)))
    assert process == _key()["runs"]


def _minus_t07(monkeypatch: pytest.MonkeyPatch) -> tuple[str, str]:
    """The K05 document minus `t07`: its SHA-256 as written, and its `structural_sha256`. The
    `t07` builder is stubbed (it is dropped anyway) so this costs the rest of the document only."""
    import k05_structural_identity

    monkeypatch.setattr(k05_structural_identity, "t07_identity", dict)
    document = copy.deepcopy(k05_structural_identity.identity())
    assert document.pop("t07") == {}
    written = (json.dumps(document, indent=1, sort_keys=True) + "\n").encode()
    return hashlib.sha256(written).hexdigest(), document["structural_sha256"]


def test_the_document_minus_t07_is_the_pre_w8_document(monkeypatch: pytest.MonkeyPatch) -> None:
    """The key is added under a new name; no other key and no byte of the rest moves — but for
    ADR 0025 D1.2's recording switch and the rename, which the next tests undo (R-148, R-149)."""
    assert _minus_t07(monkeypatch) == (K05_MINUS_T07_SHA256_R149, STRUCTURAL_SHA256_R149)


def test_r149_with_the_pre_rename_self_hashes_the_document_minus_t07_is_r148s(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """R-149's substitution proof: the provider's pre-rename hash gives R-148's bytes."""
    record_process_runtime(monkeypatch)
    assert _minus_t07(monkeypatch) == (K05_MINUS_T07_SHA256_V2, STRUCTURAL_SHA256_V2)


def test_with_v1_recorded_the_document_minus_t07_is_the_registered_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """R-148's substitution proof, after R-149's: recording v1 again, with the pre-rename
    self-hashes, gives the registered bytes."""
    record_process_runtime(monkeypatch)
    record_v1(monkeypatch)
    assert _minus_t07(monkeypatch) == (K05_BASELINE_SHA256, STRUCTURAL_SHA256)
