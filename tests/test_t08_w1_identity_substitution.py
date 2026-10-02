"""T08.A13 (W1.8): the identity after D2 and D3 moves only by substitution (release spec §6.2).

The `t07` identity key may move only by substitution: with the fixes' new values replaced by the
old ones — D2's empty strings, D3's wrong counter — the identity document must be the registered
one byte for byte, and the old-to-new difference must touch only the fields the fixes name (ADR
0017 D3's precedent: the old value monkeypatched in at its source).

Measured at `wp/T08` after W1.3/W1.4, with `scripts/t07_evidence_manifest.py`'s `measure_identity`
protocol: the whole K05 document is `3ed2911b…` and the `t07` key `11bcb148…`, both as registered
(T07 `5f3d3ea`), every other key unchanged. So the key does not move at all: its runs' R0
(`r0_projection`) carries neither a bundle's `replay_identity` nor a certificate's ids, and the
failure R0's solver counters of its only failing run (UL-C3X, the initializer's bundle) were
already the step's meter. Here that is checked twice — the key with the fixes, and the key with
them substituted back — and the substitution is shown to be the whole difference where the bytes
do move: the certificates and failure bundles themselves.

**Q-P1-1** (T08 build-first Amendment 1 §Am1.6): the initializer failure bundle names its plan as
the region bundles do. Its old value (no plan: four empty strings) is substituted back here too, and
UL-C3X's bundle is shown to move in `/replay_identity/` only; the key does not move, since the
failure R0 never carries `replay_identity` (`run/identity.py`).

**D1's STR-05 extension** (Frank, 2026-09-29, Q-P1-2) **does move the key**: the key records every
validation check's message of its runs, and STR-05 of SYN-001-nominal and SYN-001-A02-360 now names
the loop's units and the attempt signature by instance (`mixer`, `heater`, `flash`, `splitter`
for the legacy binder's `U-MIX`, `U-HEAT`, `U-FLASH`, `U-SPLIT`). Measured: `t07` `422aa7a5…`,
whole document `7f32b143…`; every other key unchanged. With the old unit naming substituted back
(`_block_metrics` given no instance map, as before the extension) the key is `11bcb148…` again,
and the whole document `3ed2911b…` byte for byte (`measure_identity`, reversed by
`t08_d1_substitution`).

**P-STR04** (T08 review §3.3): STR-03, STR-04 and STR-05 now name binder ids through one helper,
`binding.instance_named`; STR-04's row and parameter ids move with it. No run of the key ends in
an STR-04 `FAIL`, so the key is the STR-05 extension's `422aa7a5…` still. The old naming is
substituted back by making that helper the identity, which undoes D1 and both its extensions.

**ADR 0025 D1.2's recording switch** (Frank, 2026-10-02, R-148) moves the key again: the runs'
manifests and certificates name `T08-numerical-policy-v2`. Measured: `t07` `a96f17ed…`, whole
document `28dd8bf7…`. With v1 recorded again (`tests/t08_v2_substitution.py`) the key is
`422aa7a5…`, and with D1–D3 substituted back as well it is T07's `11bcb148…`.

**The rename to `openflowsheet`** (Frank, 2026-10-02, R-149) moves it once more, through the
SYN-001 provider's self-hash in `model_version`: `t07` `887a2e62…`, whole document `174977cc…`.
With the pre-rename self-hashes (`tests/t08_rename_substitution.py`) it is R-148's `a96f17ed…`,
and every older value above is reached with that substitution undone first.
"""

from __future__ import annotations

import hashlib
import json
import sys
from collections.abc import Iterator
from dataclasses import replace
from typing import Any

import pytest
from conftest import REPO_ROOT
from t07_corpus import CORPUS
from t08_rename_substitution import record_process_runtime
from t08_v2_substitution import record_v1

import openflowsheet.application.binding as binding
import openflowsheet.application.revision_run as revision_run
from openflowsheet.application.policies import DEFAULT_POLICY_ID, T05B_V2, resolve_policy
from openflowsheet.application.revision_run import Route, select_route, solve_route
from openflowsheet.verify.certificate import CheckPolicy

sys.path.insert(0, str(REPO_ROOT / "scripts"))
import t07_identity  # noqa: E402

#: The registered `t07` key: SHA-256 of `json.dumps(key, sort_keys=True)` (§W0.1's per-key
#: convention), from T07's identity document (`evidence/T07/5f3d3ea…`, whole document `3ed2911b…`).
T07_KEY_SHA256 = "11bcb1488029cd9dccbe29a519ff49ee41b3ee7899652c37f9ad414b4927f65d"
#: The `t07` key since D1's STR-05 extension: `T07_KEY_SHA256` moved by that substitution only.
T07_KEY_SHA256_D1 = "422aa7a5d1b50ea1ab5f101fe368fd51c108b463eb9d8a0af905f1e9bd09c122"
#: The `t07` key since this build records `T08-numerical-policy-v2` (ADR 0025 D1.2; R-148):
#: `T07_KEY_SHA256_D1` moved by that substitution only.
T07_KEY_SHA256_V2 = "a96f17eda025168ea184584bd8f0fd2bed6d940ecf8356a6b7ee6f9663348e4b"
#: The `t07` key since the rename to `openflowsheet` (R-149): `T07_KEY_SHA256_V2` moved by the
#: SYN-001 provider's self-hash only.
T07_KEY_SHA256_R149 = "887a2e622676dbfaff0a8ebfc309414f0e74150ace8327887b4a9ec15e498a38"
#: The fields D2 and D3 name, as the pointers `differences` reports.
D2_D3_FIELDS = (
    "/replay_identity/",
    "/observations/counters/",
    "/policy_id",
    "/plan_id",
)
#: The T07 key's runs, plus the D2/D3 states (T08.A11, A12).
STATES: tuple[tuple[str, Any], ...] = (
    *((name, None) for name in t07_identity.CASES),
    ("SYN-001-T06-NET02", T05B_V2),
    ("SYN-001-A02-352-vapor-guess-410", None),
    ("SYN-001-UL-C1", None),
)


@pytest.fixture
def substituted(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """The fixes' new values replaced by the old: no plan on the region view (D2's empty
    strings), certificates as the verifier left them (D2), a region bundle's counters read off
    its `RegionResult` (D3's wrong counter), no plan on the initializer bundle (Q-P1-1's
    empty strings), and the binder's unit ids in STR-03/04/05's messages (before D1)."""
    region_bundle = revision_run.region_bundle

    def old_region_bundle(result: Any, trace: Any, **keywords: Any) -> Any:
        bundle = region_bundle(result, trace, **{**keywords, "plan": None})
        counters = {
            name: getattr(result.counters, name) for name in bundle.observations["counters"]
        }
        return replace(bundle, observations={**bundle.observations, "counters": counters})

    initializer_bundle = revision_run.initializer_bundle

    def old_initializer_bundle(step: Any, trace: Any, **keywords: Any) -> Any:
        return initializer_bundle(step, trace, **{**keywords, "plan": None})

    monkeypatch.setattr(revision_run, "region_bundle", old_region_bundle)
    monkeypatch.setattr(revision_run, "initializer_bundle", old_initializer_bundle)
    monkeypatch.setattr(binding, "instance_named", lambda identifier, instance_of: identifier)
    monkeypatch.setattr(revision_run, "_run_identity", lambda certificate, plan: certificate)
    yield


def differences(old: Any, new: Any, pointer: str = "") -> list[str]:
    """Every pointer where `new` differs from `old`, exactly (no float allowance)."""
    if isinstance(old, dict) and isinstance(new, dict):
        return [
            found
            for key in sorted(set(old) | set(new))
            for found in (
                differences(old[key], new[key], f"{pointer}/{key}")
                if key in old and key in new
                else [f"{pointer}/{key}"]
            )
        ]
    if isinstance(old, list) and isinstance(new, list) and len(old) == len(new):
        return [
            found
            for index, (a, b) in enumerate(zip(old, new, strict=True))
            for found in differences(a, b, f"{pointer}/{index}")
        ]
    same = type(old) is type(new) and (old == new or (old != old and new != new))
    return [] if same else [pointer]


def _key_sha256() -> str:
    key = json.loads(json.dumps(t07_identity.identity()))
    return hashlib.sha256(json.dumps(key, sort_keys=True).encode()).hexdigest()


def test_a13_the_t07_key_is_the_registered_one_moved_by_d1_v2_recording_and_rename_only() -> None:
    assert _key_sha256() == T07_KEY_SHA256_R149


def test_r149_with_the_pre_rename_self_hashes_the_key_is_r148s(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    record_process_runtime(monkeypatch)
    assert _key_sha256() == T07_KEY_SHA256_V2


def test_r148_with_v1_recorded_the_key_is_d1s(monkeypatch: pytest.MonkeyPatch) -> None:
    record_process_runtime(monkeypatch)
    record_v1(monkeypatch)
    assert _key_sha256() == T07_KEY_SHA256_D1


def test_a13_with_the_old_values_substituted_the_key_is_the_registered_one(
    substituted: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    record_process_runtime(monkeypatch)
    record_v1(monkeypatch)
    assert _key_sha256() == T07_KEY_SHA256


def _label(name: str, policy: Any) -> str:
    return name if policy is None else f"{name} under {policy.policy_id}"


def _records() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for name, policy in STATES:
        document = CORPUS[name]()
        route = select_route(document)
        assert isinstance(route, Route), name
        used = policy or resolve_policy(DEFAULT_POLICY_ID, route.solve_path)
        result = solve_route(route, document, policy=used, check_policy=CheckPolicy())
        if result.certificate is not None:
            out[_label(name, policy)] = result.certificate.as_document()
        else:
            assert result.failure is not None, name
            out[_label(name, policy)] = result.failure.as_document()
    return out


@pytest.fixture(scope="module")
def new_records() -> dict[str, dict[str, Any]]:
    return _records()


def test_a13_the_old_to_new_difference_is_only_the_named_fields(
    new_records: dict[str, dict[str, Any]], substituted: None
) -> None:
    old_records = _records()
    moved: dict[str, list[str]] = {}
    for name, new in new_records.items():
        found = differences(old_records[name], new)
        stray = [entry for entry in found if not entry.startswith(D2_D3_FIELDS)]
        assert stray == [], (name, stray)
        moved[name] = found
    # And the fixes did move what they name: every certificate's two ids, NET-02's replay
    # identity and counters, A02-352's counters.
    assert all(moved[name] for name in ("SYN-001-UL-C1", "SYN-001-A02-360", "SYN-001-nominal"))
    assert any(e.startswith("/replay_identity/") for e in moved["SYN-001-T06-NET02 under T05b-v2"])
    assert any(
        e.startswith("/observations/counters/") for e in moved["SYN-001-A02-352-vapor-guess-410"]
    )
    # Q-P1-1: the initializer bundle moved in its four replay-identity members and nowhere else.
    assert moved["SYN-001-UL-C3X"] == [
        f"/replay_identity/{name}"
        for name in ("constants_sha256", "model_version", "plan_id", "policy_id")
    ]
