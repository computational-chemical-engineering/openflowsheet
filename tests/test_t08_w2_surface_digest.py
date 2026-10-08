"""T08.A49 / T08.B50: the served tool descriptions' digest after the description review (R-133).

T08.A49 and T08.B50 pin the digest of the MCP tool list as `v17-c2` served it,
`v17_c2_tool_descriptions_sha256` in `benchmarks/t08/reference_values.yaml` (`6d13e13d…`). The
design-lane description review (`docs/reviews/T08-description-review.md`, N1 and N2) changed two
texts, `validate.md` and `commit_change.md`, so the served digest moved. Frank decided on
2026-10-01 to carry V17 across that change with the change recorded (R-133). The old digest stays
registered as `v17-c2`'s; this module registers the new one beside it and shows that the change is
exactly those two files:

- the served digest is `T08_DESCRIPTIONS_SHA256`;
- against `v17-c2`'s per-file hashes (the review's table), the served files differ in exactly
  `validate.md` and `commit_change.md`;
- serving `v17-c2`'s two texts (byte copies in `tests/fixtures/t08/v17_c2_descriptions/`) in their
  place reproduces `6d13e13d…`, so nothing else on the served tool list (names, input schemas,
  the other 15 texts) moved.

**M02 (ADR 0033-0035) widens the served tool list additively** — the `experiment` operation and
its body, five artifact kinds, `revision_coupled`, `COUPLING_NOT_CONVERGED`,
`model_replacement_incompatible`, two widened descriptions — so the served digest moves again.
Proposed by the build lane, pending the design lane (R-133's "a further change of the surface is a
new decision"): the new digest is registered beside R-133's (`M02_DESCRIPTIONS_SHA256`), and both
claims above are held on the served list **with M02's additions removed** (`without_m02`,
`tests/m02_schema_support.py`), which reproduces `171dd768…` and, with `v17-c2`'s two texts,
`6d13e13d…` exactly.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterator
from types import ModuleType

import pytest
from conftest import REPO_ROOT, load_yaml
from m02_schema_support import without_m02

from openflowsheet.application.operations import OPERATIONS, Operation
from openflowsheet.canonical import canonical_json

DESCRIPTIONS = REPO_ROOT / "src" / "openflowsheet" / "application" / "bindings" / "descriptions"
V17_C2_TEXTS = REPO_ROOT / "tests" / "fixtures" / "t08" / "v17_c2_descriptions"
MCP_OPERATIONS = sorted(name for name, op in OPERATIONS.items() if "mcp" in op.transports)

#: R-133: the served descriptions' digest after N1 and N2 (`harness.tool_descriptions_sha256`).
T08_DESCRIPTIONS_SHA256 = "171dd768efcfb24f65d79d83a4f157dcfd1436935bf5106a247b84f3040e4d14"
#: M02's served digest (the surface above plus M02's additive members); see the module docstring.
M02_DESCRIPTIONS_SHA256 = "8de83946703c054c75e9ebbee0e5db7dd0dc97d2d6fc503a42cc041d6746123b"
#: The files N1 and N2 changed; the only difference from `v17-c2`'s served texts.
CHANGED = ("commit_change", "validate")
#: Each description's SHA-256 as `v17-c2` served it: the table of
#: `docs/reviews/T08-description-review.md`, which hashed the files at `d43bf2c`, where the served
#: digest was still `6d13e13d…`.
V17_C2_FILE_SHA256 = {
    "cancel_job": "e87d799cbe4c32f845772273180fc44d0571fc09a4071a41bd5ef299fab1e557",
    "commit_change": "53266974fe402613f3b147da7bc4673c5d57f55d2f3bf9f7c5dc48f5c9b0b384",
    "diff_revisions": "4a351ae2d7f67e5ff026cc5551109eeb19d7556eedbd2dd50298032858430fea",
    "get_artifact": "22cb20636e1f01efa15af3458e83978ad762e5d5279229db8d8723e6e7122883",
    "get_job": "349d0218d98e272591986daddfd1a87474d37c6a7d473f355e90ddfbf14a56b7",
    "get_job_result": "7eeab9bbee35cd31f55269dd2cd5de2ba4147d531a58ea4b5103e8c903f3520d",
    "get_project": "9ac0612f06676a8ebea3ff185df1fb942a3350efb79f63be53c1c05244aec6fb",
    "get_revision": "02442571d8c73ce99121f9248e712214fde89cca7d493c88876f6eb018cae932",
    "inspect_structure": "4e7c30320406679057dba4933e89a3e77f769538106b396961c1b677c45c9e8d",
    "list_job_events": "66b1ec26d3b22a53e17e43732d56496fd3e28db339298b0e3557987ef836c7d3",
    "list_jobs": "ffe3183f0de54bcf71b90151d8170915af647182bea734a682719fd8e04a6e03",
    "list_models": "941766bdd62094110bf39cacc25c6515efac4041e782f2cae8c5abcacd291db7",
    "list_revisions": "12c3e8f9c506c79fb7ef52e23630ac3cea548c04ed5b80b2e5f0a629a5beaec4",
    "preview_change": "a90d23555bc367af9f91e62704f7f4bc3e5a41d386f99d36a65a89cb7e70b701",
    "submit_job": "61b8509cafb9b4ab101e54622b68b36cf8e938b54df65db105b29b5c36c1771d",
    "validate": "302dc544f519046e25efe6d5a5e83840b6017bfbd36d94a3e3e54435eaae7c12",
    "wait_job": "4a5b99596c771bf6b3254fa9c294e8ad32077de45c3a2e64b93eda0dca37a01c",
}


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _served_without_m02(mcp: ModuleType) -> str:
    """The served tool list's digest (`harness.tool_descriptions_sha256`'s) with M02's additive
    members removed."""
    tools = [tool.model_dump(mode="json", exclude_none=True) for tool in mcp.tools()]
    return hashlib.sha256(canonical_json(without_m02(tools))).hexdigest()


def _v17_c2_digest() -> str:
    """`v17-c2`'s served digest as registered (not changed by R-133)."""
    reference = load_yaml(REPO_ROOT / "benchmarks" / "t08" / "reference_values.yaml")
    registered = reference["registered"]["v17_c2_tool_descriptions_sha256"]["sha256"]
    assert isinstance(registered, str)
    return registered


@pytest.fixture
def mcp() -> Iterator[ModuleType]:
    """The MCP binding, with `tools()`'s cache emptied before and after (it caches the served
    descriptions)."""
    pytest.importorskip("mcp")
    from openflowsheet.application.bindings import mcp as binding

    binding.tools.cache_clear()
    yield binding
    binding.tools.cache_clear()


def test_the_served_digest_is_registered(mcp: ModuleType) -> None:
    from benchmarks.t07.v17 import harness

    assert _v17_c2_digest() == "6d13e13d660521c1a39dc245d5237c974a4273b0c3eeadb02d44538ba2669a4d"
    assert harness.tool_descriptions_sha256() == M02_DESCRIPTIONS_SHA256
    assert _served_without_m02(mcp) == T08_DESCRIPTIONS_SHA256 != _v17_c2_digest()


def test_the_served_files_differ_from_v17_c2_in_exactly_the_two_reviewed_files() -> None:
    assert sorted(V17_C2_FILE_SHA256) == MCP_OPERATIONS
    served = {
        name: _sha256((DESCRIPTIONS / f"{name}.md").read_text("utf-8")) for name in MCP_OPERATIONS
    }
    changed = sorted(name for name in MCP_OPERATIONS if served[name] != V17_C2_FILE_SHA256[name])
    assert tuple(changed) == CHANGED
    for name in CHANGED:
        kept = (V17_C2_TEXTS / f"{name}.md").read_text("utf-8")
        assert _sha256(kept) == V17_C2_FILE_SHA256[name]


def test_restoring_the_two_files_reproduces_v17_c2s_digest(
    mcp: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    served = mcp.description

    def v17_c2_description(operation: Operation) -> str:
        if operation.name in CHANGED:
            return (V17_C2_TEXTS / f"{operation.name}.md").read_text("utf-8")
        text = served(operation)
        assert isinstance(text, str)
        return text

    monkeypatch.setattr(mcp, "description", v17_c2_description)
    mcp.tools.cache_clear()
    assert _served_without_m02(mcp) == _v17_c2_digest()
