"""ADR 0025 D1.2's recording switch, reversed: how the identity values registered under v1 stay
checkable (R-148).

From `wp/T08` at the merge of `wp/T08-a25-recording` this build records
`T08-numerical-policy-v2` (`run.compare.CURRENT_POLICY_ID`) in every run manifest and certificate
it writes. `RunManifest.structural_sha256` covers `numerical_policy_id`, so the K05 identity keys
move — whole `7f32b143…` → `28dd8bf7…`, minus-`t07` `9a7b4e6d…` → `29246e05…`, `t07` `422aa7a5…` →
`a96f17ed…`, structural `915c97e8…` → `e62a59a6…` — and so does the structural hash the CLI's
`solve` and `inspect` print for SYN-001-nominal (`af86adb8…` → `f9536122…`); T02's floats
`9a8a5baf…` do not. Frank approved re-registering them as a substitution-only move (2026-10-02,
R-148). The substitution is undone at its two sources (ADR 0017 D3's precedent: the old value
monkeypatched in where it is made): the id a run manifest records (`run.session`'s
`_numerical_policy_id`, which `application.revision_run` reads too) and the certificate's default
(`SolutionCertificate.numerical_policy_id`). The switch's third source change goes with them:
`replay._as_recorded`, which reads a rerun's certificate as naming the policy this build records,
is the identity again, as it was before the switch (`5b86e71`). That is the whole of `056f850`'s
source diff reversed; with it, every moved value is the registered one byte for byte.
"""

from __future__ import annotations

import pytest

import openflowsheet.run.replay as replay
import openflowsheet.run.session as session
from openflowsheet.run.compare import CURRENT_POLICY_ID, V1_POLICY_ID
from openflowsheet.verify.certificate import SolutionCertificate

#: (new, old): the structural hash of the CLI's SYN-001-nominal run, as `solve` and `inspect`
#: print it (`tests/fixtures/t07/cli-existing-commands.json`).
CLI_STRUCTURAL_SUBSTITUTION = (
    "f95361227b7d1d5647c486e0ba143fc69dc1203a7bbbb82eb0fad4f1dff775e3",
    "af86adb802f001acb1cb4bb36ed211307b941952f9470595af6407d5b1eb3272",
)


#: (new, old): the texts the switch moved in the K05 schema fixtures (`056f850`): the recorded id,
#: and the three hashes of the run-manifest fixture that cover it — the certificate artifact's,
#: `manifest_sha256` and `structural_sha256`.
FIXTURE_SUBSTITUTIONS = (
    (f'"{CURRENT_POLICY_ID}"', f'"{V1_POLICY_ID}"'),
    (
        "b103575cb2b60ffb2a4291af601f6d5682df8e0054cbf499b9817fa64a08e54d",
        "bb831ac7dcbcdb64fc752dfc68c156c82313db0a4306e2748383afe3f22d77e0",
    ),
    (
        "b4f7241d0bd306f053a313d2664ae5b9a3e82e25866e288e6f87ff4ceaff72e6",
        "c124b5d188d20afb7da5247570b58100b96b8c858a6bbda87c1c7b0102caf4f7",
    ),
    (
        "e62a59a6b3634afd8f43eae399129a2d64bafb6e8ba90ad5fe0c9c1a9c5ad238",
        "915c97e82551c75c588ec4a4e41b060241d75e037366c099c285493165a97e27",
    ),
)
#: SHA-256 of each fixture the switch moved, as committed before it (`5b86e71`), relative to
#: `tests/fixtures/schemas`.
FIXTURES_V1_SHA256 = {
    "run_manifest/valid/syn001_nominal.json": (
        "88a84f7d1384936594964d21243c481456ff86a609c070d1082b0963f0497c4d"
    ),
    "solution_certificate/valid/syn001_nominal_verified.json": (
        "d864a7bcacbd383693d7411d678160830e202ee656a2008146ee015f3fbe2167"
    ),
    "solution_certificate/valid/syn001_trivial_root_failed.json": (
        "10ee57b31935a5c5ba19ccd28c90b5ed92481a74642298cdb902aeb88dee39ac"
    ),
    "solution_certificate/valid/t04_hom01_bound_verified.json": (
        "dd82a236c0a6cd594a154318bff36889c2200bfca06f03ca14df35f3f058b189"
    ),
}


def record_v1(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make this build record `V1_POLICY_ID` again, at both sources of the recorded id."""
    defaults = SolutionCertificate.__init__.__defaults__
    assert defaults is not None and defaults[0] == CURRENT_POLICY_ID, defaults
    monkeypatch.setattr(session, "_numerical_policy_id", lambda: V1_POLICY_ID)
    monkeypatch.setattr(SolutionCertificate.__init__, "__defaults__", (V1_POLICY_ID, *defaults[1:]))
    monkeypatch.setattr(SolutionCertificate, "numerical_policy_id", V1_POLICY_ID)
    monkeypatch.setattr(
        replay, "_as_recorded", lambda name, fresh, archived, policy_id: (fresh, [])
    )


def v2_reversed_cli_text(text: str) -> str:
    """`text` with the CLI's structural hash as it was recorded under v1."""
    new, old = CLI_STRUCTURAL_SUBSTITUTION
    return text.replace(new, old)


def v2_reversed_fixture_text(text: str) -> str:
    """A K05 schema fixture's text as committed before the switch."""
    for new, old in FIXTURE_SUBSTITUTIONS:
        text = text.replace(new, old)
    return text
