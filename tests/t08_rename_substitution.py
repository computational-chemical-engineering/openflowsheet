"""The rename `process_runtime` → `openflowsheet`, reversed: how the values registered before it
stay checkable (R-149).

Two modules hash their own source bytes, and both import the package by name: the SYN-001
provider's `implementation_sha256` (`thermo/syn001.py`, blueprint §6.4: it is in the exact cache
key and in `model_version`) and the T06 ensemble generator's `generator_sha256`
(`benchmarks/t06/generator.py`, T06 spec §6.5). The rename changed three import lines in the one
and the imports of the other, and nothing else in either file: each file with `openflowsheet`
replaced by `process_runtime` is its pre-rename bytes, so each hash moved by that substitution
only. Through `model_version` the provider's hash moves `plan_id`, `structural_sha256`,
`artifact_r0_sha256` and every hash that covers them — the K05 identity (whole `28dd8bf7…` →
`174977cc…`, minus-`t07` `29246e05…` → `24af004a…`, `t07` `a96f17ed…` → `887a2e62…`, structural
`e62a59a6…` → `ed6d11f3…`; T02's floats `9a8a5baf…` do not move), the schema fixtures, the CLI's
pins and the W5c binding signatures. Frank approved re-registering them as a substitution-only
move (2026-10-02, R-149). As for R-148 (`t08_v2_substitution`), the substitution is undone where
the values are made: `record_process_runtime` monkeypatches both self-hashes back to their
pre-rename values, and with it every moved value is the registered one byte for byte.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path
from typing import Any

import pytest

import openflowsheet.thermo.syn001 as syn001
from benchmarks.t06 import generator

#: (new, old): the SYN-001 provider's `implementation_sha256`.
PROVIDER_SHA256 = (
    "4e4c37cc8054c7da12965cba80494be5666053e3bf817446053ebdeb8d6a04e7",
    "67e472816d4d67676f4cac64861e815602de01b3e7621e225f93cbdfda32982a",
)
#: (new, old): the T06 generator's `generator_sha256`. The published start sets
#: (`starts-nominal-v1.json`, `starts-nominal-holdout1.json`) record the old one: §6.5 never
#: regenerates them, so they keep naming the bytes that generated them.
GENERATOR_SHA256 = (
    "509b01fb1544ec24a79b43c11353cfa9b5563ee885ed3eddfdc04d8daf1c14b4",
    "7f426aa9f8a114553d362ed03f4a040e67827a8be17c1751b7e2374043117893",
)


def renamed_back_sha256(path: Path) -> str:
    """SHA-256 of `path`'s bytes with the package's name as it was before the rename."""
    return hashlib.sha256(
        path.read_bytes().replace(b"openflowsheet", b"process_runtime")
    ).hexdigest()


def record_process_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make this build hash its two self-hashing modules as they were before the rename."""
    assert syn001._implementation_sha256() == PROVIDER_SHA256[0]
    assert generator.generator_sha256() == GENERATOR_SHA256[0]
    monkeypatch.setattr(syn001, "_implementation_sha256", lambda: PROVIDER_SHA256[1])
    monkeypatch.setattr(generator, "generator_sha256", lambda: GENERATOR_SHA256[1])
    # `test_t04_ptc_region.case` keeps compiled cases, whose evaluation context holds the
    # `model_version` made from the provider's hash; K05's T04 key reads them (`OFF-B/ptc`).
    ptc_region = sys.modules.get("test_t04_ptc_region")
    if ptc_region is not None:
        monkeypatch.setattr(ptc_region, "_CASES", {})


def renamed_back_text(text: str, substitutions: tuple[tuple[str, str], ...]) -> str:
    """`text` with the provider's hash, full and as `model_version`'s 12-character prefix, and
    then each (new, old) of `substitutions` put back."""
    new, old = PROVIDER_SHA256
    text = text.replace(new, old).replace(new[:12], old[:12])
    for moved, registered in substitutions:
        text = text.replace(moved, registered)
    return text


#: (new, old): the hashes of the K05 run-manifest fixture that cover `model_version`: the R0
#: artifact digest, the four artifacts that name it, `structural_sha256` and `manifest_sha256`.
FIXTURE_SUBSTITUTIONS = (
    (
        "68e18bd114f96383fca469f143b3c51469c3c0ef72d70159d1d1ad314f49d01b",
        "77508d4ac3373f523f87c89ba83841173f94ba12c608deb3c8ab83053576471d",
    ),
    (
        "3cb9083f678702548514941a961c38f4240ccb087026f81d8f36cc673d2b8229",
        "b103575cb2b60ffb2a4291af601f6d5682df8e0054cbf499b9817fa64a08e54d",
    ),
    (
        "2ce6ddaee2cc171edd05e32d9fabc73813e0a96a2e80642670e23d44025085c8",
        "349dc7d7503b52847e955ae923097f85f1665356adba04bab757260bced4e405",
    ),
    (
        "9e9097a33c882792d0b8f3475f125dceb8a4a682c636e4fc9c9c061813e37cf7",
        "bdfb019429479302b8445fa43ef73924e6722bd1c52097bbae65e64f0e81f83d",
    ),
    (
        "9d515044db4dedf09caa99a2aeba4d86bcce8e8e55bc8262766ce69a40a93143",
        "cd0f2dcec153e82563ac61f174e4ea752b0f8796d2d123ac322e890b7e5c8976",
    ),
    (
        "ed6d11f3beb78c6f1debc481c6e525ce3ccb120bd30cdfd07e470f728e082e90",
        "e62a59a6b3634afd8f43eae399129a2d64bafb6e8ba90ad5fe0c9c1a9c5ad238",
    ),
    (
        "30a80bfaea3cde844a9ab65190c24c36d22c79b9ca67db3d24a0aa7da44c0eab",
        "b4f7241d0bd306f053a313d2664ae5b9a3e82e25866e288e6f87ff4ceaff72e6",
    ),
)
#: SHA-256 of each schema fixture the rename moved, as committed before it (`50602a0`), relative
#: to `tests/fixtures/schemas`. The new fixtures are these with the substitutions applied (and
#: the run manifest's `manifest_sha256` recomputed over its substituted document), not
#: regenerations: their volatile fields (`started_at`, `elapsed_seconds`, `lock_sha256`) are
#: the committed ones still.
FIXTURES_PRE_RENAME_SHA256 = {
    "attempt_context/valid/syn001_restart.json": (
        "02b536a264065ee0009ece1bf39ce621a88f70d2cda772c2ff3e6cccf10981f6"
    ),
    "attempt_context/valid/t04_hom05_homotopy.json": (
        "fcaccd3e04d97f599e5d95329f690b9674c97f4707a08439affb69906e630ea3"
    ),
    "attempt_context/valid/t04_ptc_restart.json": (
        "9aac20c69185e070503f5c68d2c4abc87b1ec90e6a1e93001458ea84dc5b63d9"
    ),
    "regularity_evidence/valid/syn001_nominal.json": (
        "69a54b100931cbdf7df81e874ad9c9ff9fee99f1b241ed2004c0f510da8e94f7"
    ),
    "run_manifest/valid/syn001_nominal.json": (
        "459a9185f92ee7e676b05e29a4faef7262afb8832b50c7634c77d7f97e0cd595"
    ),
    "solution_certificate/valid/syn001_nominal_verified.json": (
        "2eb62559604a557c20d094fe9c0104b1d50236773527ef12a477d6cec5cdac13"
    ),
    "solution_certificate/valid/syn001_trivial_root_failed.json": (
        "8237c10a4c4b5486d3d4dc408573c1d397f3bc35eac45526b6e29c4fcc25a1be"
    ),
    "solution_certificate/valid/t04_hom01_bound_verified.json": (
        "bace14bb92bacb0f6aab4a4c10a840412fc13d069431c8b58845dd02726df41b"
    ),
    "solve_event/valid/syn001_nominal_trace.json": (
        "90ee476e9c394462e989ab71386befd90ab7efbe184560e1a31c434f2877a451"
    ),
    "solve_event/valid/syn001_off_b_restart_trace.json": (
        "af05a40bf4dac48cdfa9a06d9d7e7930438f93cd6db29e82c51a2ca197ac0c62"
    ),
    "solve_plan/valid/syn001_nominal.json": (
        "c8744b60d47779d404e3b648a0318e23cabc545298276e49e7b2bd19a93d2bc1"
    ),
}


def renamed_back_fixture_text(text: str) -> str:
    """A schema fixture's text as committed before the rename."""
    return renamed_back_text(text, FIXTURE_SUBSTITUTIONS)


#: (new, old): the structural hash of the CLI's SYN-001-nominal run, as `solve` and `inspect`
#: print it (`tests/fixtures/t07/cli-existing-commands.json`).
CLI_STRUCTURAL_SUBSTITUTION = (
    "16ae2bd4ab03810597147f4daa3894fb123ead2bb0e36548ef75fd28b3ce773b",
    "f95361227b7d1d5647c486e0ba143fc69dc1203a7bbbb82eb0fad4f1dff775e3",
)
#: SHA-256 of `tests/fixtures/t07/cli-existing-commands.json` as committed before the rename.
PINS_PRE_RENAME_SHA256 = "79b052bccc694579a13cec66efa38d09c50b42bc30cccda98c29a653f99a24e6"


def renamed_back_cli_text(text: str) -> str:
    """The CLI's printed text as it was before the rename."""
    return renamed_back_text(text, (CLI_STRUCTURAL_SUBSTITUTION,))


#: SHA-256 of `json.dumps(EXPECTED, sort_keys=True)` for `tests/test_t07_w5c_signatures.py`'s
#: table as committed before the rename: 69 revisions, of which the rename moved the 55 `binds`
#: digests and nothing else.
W5C_PRE_RENAME_SHA256 = "eaf1fbfab6f2be50090e8576d3ee1500e7181c9c293a6be7f23c5d922dece6cf"

#: SHA-256 of `json.dumps([[name, policy, *digests], …])` over `LEGACY_PLAN` in its order
#: (`tests/test_t07_w3a_revision_runs.py`), as committed before the rename: the rename moved 38 of
#: its 40 entries, plan and report digests both, through the provider's self-hash only.
W3A_PRE_RENAME_SHA256 = "00330b0ba182f465dc18ea2973df56842eccc051d745e875457d0226568fce8f"


def renamed_back_starts(document: dict[str, Any]) -> dict[str, Any]:
    """A regenerated T06 start set with its two self-hashes as before the rename: the provider
    block's `implementation_sha256` and `generator_sha256`, each checked to be the new value."""
    assert document["generator_sha256"] == GENERATOR_SHA256[0]
    assert document["provider"]["implementation_sha256"] == PROVIDER_SHA256[0]
    provider = {**document["provider"], "implementation_sha256": PROVIDER_SHA256[1]}
    return {**document, "generator_sha256": GENERATOR_SHA256[1], "provider": provider}
