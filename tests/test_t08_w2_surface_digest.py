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

**ADR 0019 Amendment 3 (M06, A3.2; approved by Frank on 2026-10-08).** `diff_revisions`'s
`outputSchema` gains the required member `elements`, so the served tool list moves again, to
`M06_A3_SERVED_SHA256`. With that one member taken out of that one tool's `outputSchema`
(`_without_a3_2`), the served list is R-133's `171dd768…` exactly, and with `v17-c2`'s two texts as
well it is `6d13e13d…`: nothing else moved. (Registered here pending the register entry the
amendment's surface move needs; M06 WO-2.)

**M02 (ADR 0033-0035) widens the served tool list additively** — the `experiment` operation and
its body, five artifact kinds, `revision_coupled`, `COUPLING_NOT_CONVERGED`,
`model_replacement_incompatible`, two widened descriptions — so the served digest moves again.
R-234 (design note M02 §14 B1, following R-192) rules how: this file's 0.1 constants and
`scripts/t08_rc.py`'s A49 constant are not edited; the move is bound to M02's additions by a
decomposition test — with M02's additions removed (`without_m02`, `tests/m02_schema_support.py`)
the served list is the base's registered digest (`M02_BASE_SERVED_SHA256`, M06's `6c4375b4…`
above, R-192), and the served tool descriptions are byte-identical. M02's own served digest is
registered at the merge commit, on the combined tree; the value measured without M06
(`8de83946…`) is evidence, not a pin.

**MSG (ADR 0058; R-934) widens the served tool list additively** — `RunResult.failure` in every
`outputSchema` that reaches a run result (D5), and the `explain` tool (D7) — so the served digest
moves to `MSG_SERVED_SHA256`.
With MSG's additions removed first (`without_msg`, `tests/msg_schema_support.py`) every
decomposition below holds as before, and the list is M04's served digest `455d01eb…` (R-457)
exactly (MSG-G10, `test_msgs_surface_move_decomposes_onto_m04s`).

**X02 (ADR 0070, ADR 0019 Amendment 15; R-950) widens it again, additively** — the optional
`solve_body.warm_start` in the job request every job tool serves — so the served digest moves to
`X02_SERVED_SHA256`. With X02's additions removed first (`without_x02`,
`tests/x02_schema_support.py`) the list is MSG's served digest `eaff4585…` exactly
(`test_x02s_surface_move_decomposes_onto_msgs`), and every decomposition below holds as before.

**OPT (ADR 0071, ADR 0019 Amendment 16; R-960) widens it again, additively** — the `optimize` job
operation (its request and result branches, `job_result.optimization`, six artifact kinds) and
`validate`'s optional `optimization` member — and changes two description texts (`validate.md`,
`submit_job.md`), so the served digest moves to `OPT_SERVED_SHA256`. With OPT's additions removed
and the two texts restored from their pre-OPT copies first (`without_opt`,
`tests/opt_schema_support.py`) the list is X02's served digest `f51b69bf…` exactly
(`test_opts_surface_move_decomposes_onto_x02s`), and every decomposition below holds as before.

**ST (ADR 0068, ADR 0019 Amendment 13; R-1000) widens it again, additively** — one tool,
`get_stream_table`, after `get_artifact` — so the served digest moves to `ST_SERVED_SHA256`. With
ST's tool removed first (`without_st`, `tests/st_schema_support.py`) the list is OPT's served
digest `3fdc797a…` exactly (`test_sts_surface_move_decomposes_onto_opts`), and every decomposition
below holds as before.

**X04 (ADR 0075, ADR 0019 Amendment 17; R-1010) widens it again, additively** —
`project_summary`'s `ambient_pressure`, an explanation number's `display`, `job_result`'s
`display_units`, the optional `display_units` request member of `get_job_result` and
`get_stream_table` — and changes those two tools' description texts, so the served digest moves to
`X04_SERVED_SHA256`. With X04's additions removed and the two texts restored from their pre-X04
copies first (`without_x04`, `tests/x04_schema_support.py`) the list is ST's served digest
`553b7612…` exactly (`test_x04s_surface_move_decomposes_onto_sts`), and every decomposition below
holds as before.

**F1 (ADR 0060 D11, ADR 0019 Amendment 7; R-1030) widens it again, additively** — two tools,
`list_capabilities` and `check_admission`, after `explain` — so the served digest moves to
`F1_SERVED_SHA256`. With F1's tools removed first (`without_f1`, `tests/f1_schema_support.py`) the
list is X04's served digest `6be1c002…` exactly (`test_f1s_surface_move_decomposes_onto_x04s`), and
every decomposition below holds as before.

**F3 (ADR 0061 D13, ADR 0019 Amendment 8; R-1051) widens it again, additively** — five tools, the
protocol `Records` — so the served digest moves to `F3_SERVED_SHA256`. With F3's tools removed
first (`without_f3`, `tests/f3_schema_support.py`) the list is F1's served digest `e2c44b6b…`
exactly (`test_f3s_surface_move_decomposes_onto_f1s`), and every decomposition below holds as
before.

**F2 (ADR 0062 D1) widens it again, additively** — ADR 0062 D1's 14 quantity kinds at the end of
`quantity.schema.json`'s kind enum, and one sentence of its description, served in `list_models`'
`outputSchema`, and F2-WO8 widens `check_admission.md`'s draft form to `<schema_version 1 or 2
document>` (the F2 review's ruling 3) — so the served digest moves to `F2_SERVED_SHA256`. With F2's
additions removed and that text restored first (`without_f2`, `tests/f2_schema_support.py`) the
list is F3's served digest `f7ec3c94…`
exactly (`test_f2s_surface_move_decomposes_onto_f3s`), and every decomposition below holds as
before.

**X06 (ADR 0078 D6, ADR 0019 Amendment 18; R-1073) widens it again, additively** — from X06-WO2
the three tools of the protocol `Branches`, the ChangeSet's optional `branch` member wherever the
ChangeSet is served, and the `branch` sentence in `commit_change.md` and `preview_change.md`; from
X06-WO3 the two tools of `SolvePolicies` and from X06-WO4 the four of `Administration` — so
the served digest moves to `X06_SERVED_SHA256`. With X06's additions removed and the two texts
restored from their pre-X06 copies first (`without_x06`, `tests/x06_schema_support.py`) the list
is F2's served digest `8eee5313…` exactly (`test_x06s_surface_move_decomposes_onto_f2s`), and
every decomposition below holds as before. F2 merges first, so X06 decomposes onto F2's (ADR 0078
D6, R-1072/R-1073; X06-FR0).
**F8 (ADR 0067 D5, ADR 0019 Amendment 12; R-1076) widens it again, additively** — the replay
report's reserved mode `forced_replay` and its two optional members `registry_comparison` and
`data_availability`, served in `get_job_result`'s `outputSchema` (D3's artifact kinds do not reach
the served list: MCP serves J5's consumer reading, the enum opened) — so the served digest moves
to `F8_SERVED_SHA256`. With F8's additions removed first (`without_f8`,
`tests/f8_schema_support.py`) the list is X06's served digest `ba4b5ce5…` exactly
(`test_f8s_surface_move_decomposes_onto_x06s`), and every decomposition below holds as before.
F2 and X06 merge first, so F8 decomposes onto X06's (R-1072/R-1073; F8-FR1).
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterator
from types import ModuleType
from typing import Any

import pytest
from conftest import REPO_ROOT, load_yaml
from f1_schema_support import F1_OPERATIONS, without_f1
from f2_schema_support import F2_DESCRIPTIONS, F2_KIND_NOTE, F2_KINDS, pre_f2_text, without_f2
from f3_schema_support import F3_OPERATIONS, without_f3
from f8_schema_support import F8_REPLAY_MODE, F8_REPORT_MEMBERS, without_f8
from m02_schema_support import without_m02
from m04_schema_support import without_m04
from msg_schema_support import MSG_OPERATIONS, without_msg
from opt_schema_support import OPT_DESCRIPTIONS, pre_opt_text, without_opt
from st_schema_support import ST_OPERATIONS, without_st
from x02_schema_support import without_x02
from x04_schema_support import X04_DESCRIPTIONS, pre_x04_text, without_x04
from x06_schema_support import X06_DESCRIPTIONS, X06_OPERATIONS, pre_x06_text, without_x06

from openflowsheet.application.operations import OPERATIONS
from openflowsheet.canonical import canonical_json

DESCRIPTIONS = REPO_ROOT / "src" / "openflowsheet" / "application" / "bindings" / "descriptions"
V17_C2_TEXTS = REPO_ROOT / "tests" / "fixtures" / "t08" / "v17_c2_descriptions"
MCP_OPERATIONS = sorted(name for name, op in OPERATIONS.items() if "mcp" in op.transports)
#: The MCP operations before MSG (ADR 0058 D7 added `explain`, whose text `v17-c2` never served).
PRE_MSG_MCP_OPERATIONS = sorted(
    set(MCP_OPERATIONS)
    - MSG_OPERATIONS
    - ST_OPERATIONS
    - F1_OPERATIONS
    - F3_OPERATIONS
    - X06_OPERATIONS
)

#: R-133: the served descriptions' digest after N1 and N2 (`harness.tool_descriptions_sha256`).
T08_DESCRIPTIONS_SHA256 = "171dd768efcfb24f65d79d83a4f157dcfd1436935bf5106a247b84f3040e4d14"
#: ADR 0019 Amendment 3 (A3.2): the served tool list with `diff_revisions`'s `elements`.
M06_A3_SERVED_SHA256 = "6c4375b478d71c12b1211c17fafe7e58e9dfc0a05e11def2106799a6917631c9"
#: R-234: the base's registered served digest that M02's surface move decomposes onto: R-192's
#: (M06's Amendment 3), on `main` at M02's merge of it. (Evidence, not a pin: served with M02 and
#: without M06, the digest was `8de83946…`.)
M02_BASE_SERVED_SHA256 = M06_A3_SERVED_SHA256
#: R-457: M04's served digest, registered at the alpha's merge (`scripts/m07a_rc.py`'s `D_3`).
M04_SERVED_SHA256 = "455d01eb2f420032b27358798e6b331a0120aa1857f02ce3cb7851647849e125"
#: MSG-G10 (ADR 0058): the served digest with `RunResult.failure` (D5) and the `explain` tool (D7),
#: re-measured at MSG WO-11 after `explain.md`'s two review edits (Q6). (Evidence, not a pin: at
#: WO-7, before the edits, `1ca06b37…`; with `failure` alone, at WO-6, `b083ffe1…`.)
MSG_SERVED_SHA256 = "eaff45852d7596816d90d744078f537e46c723e577295d347d9d73aea0942eac"
#: X02 (ADR 0070, R-950): the served digest with `solve_body.warm_start` over MSG's list, measured
#: when `main` (MSG) was merged into `wp/X02`. (Evidence, not a pin: at X02 WO-2, over M04's list
#: before MSG, `0af895a0…`.)
X02_SERVED_SHA256 = "f51b69bf66569e35aebead73b66e98d58f24c84016db639536c0ee35181f4c7b"
#: OPT (ADR 0071, R-960): the served digest with OPT's additions and two texts over X02's list,
#: measured when `main` (X02) was merged into `wp/OPT` (`scripts/m07a_rc.py`'s `D_6`). (Evidence,
#: not a pin: at OPT WO-6, over M04's list before MSG and X02, `3fb06cad…`.)
OPT_SERVED_SHA256 = "3fdc797ad64485abf63fb491ebd56aa43dc510e62e9e218b0dd7a8fcc2e38a85"
#: ST G12 (ADR 0068, R-1000; design note §7): the served digest with the `get_stream_table` tool
#: over OPT's list, measured when `main` (OPT) was merged into `wp/ST` (`scripts/m07a_rc.py`'s
#: `D_7`). Without that tool it is `OPT_SERVED_SHA256` (c_7). (Evidence, not a pin: as c_5 over
#: MSG's list before X02 and OPT, `ebb4ca84…`; at WO-3, before the review's edits, `6705fb05…`.)
ST_SERVED_SHA256 = "553b76122fefd4f09d6e91d16e7096d05b9f7793bb88e1876252dc2213e24894"
#: X04 (ADR 0075, R-1010): the served digest with X04's display-units members and its two
#: description texts over ST's list, measured when `main` (ST) was merged into `wp/X04`
#: (`scripts/m07a_rc.py`'s `D_8`). Without them it is `ST_SERVED_SHA256` (c_8).
X04_SERVED_SHA256 = "6be1c002592524126617af8dd65d331513f4a96355f5381dba020ad561a2ba57"
#: F1 (ADR 0060 D11, R-1030): the served digest with F1's two tools over X04's list, measured at
#: F1-WO4a on `wp/F1`, re-taken at F1-WO4b, whose draft form changed `check_admission.md`, and at
#: the F1 review's fix round, which applied the design lane's edits to both texts
#: (`scripts/m07a_rc.py`'s `D_9`). Without them it is `X04_SERVED_SHA256` (c_9).
F1_SERVED_SHA256 = "e2c44b6b9c2a7f5689ed4f2fd96b6e9804d1a63e60a5c620d29b5b5d594bcebb"
#: F3 (ADR 0061 D13, R-1051): the served digest with F3's five `Records` tools over F1's list,
#: measured at F3-WO5b on `wp/F3` and re-taken at the F3 review 2 fix round (C6: the report
#: items' `at`; C11: the design lane's edits to four texts; `scripts/m07a_rc.py`'s `D_10`).
#: Without them it is `F1_SERVED_SHA256` (c_10).
F3_SERVED_SHA256 = "f7ec3c94233d30506ec2082a13c4e54d57bd540e43e97fdf877b1e3c75fed467"
#: F2 (ADR 0062 D1): the served digest with D1's 14 quantity kinds in `list_models`' output schema
#: over F3's list, measured at F2-WO2b on `wp/F2` (WO1 moved it; WO2 left it where WO1 did), and
#: re-taken at F2-WO8 for `check_admission.md`'s new text (`9a4b4eb3…` before). Without them it
#: is `F3_SERVED_SHA256`.
F2_SERVED_SHA256 = "8eee5313e1dff685ed3f5c7a60c6aa8fb7fea31d8fcd5c8ac608eac9450f304a"
#: X06 (ADR 0078 D6, R-1073): the served digest with X06-WO2's branches, X06-WO3's solve
#: policies and X06-WO4's administration over F2's list, measured at the X06 fix round on
#: `wp/X06` with the review's three text edits (`scripts/m07a_rc.py`'s `D_12`; `4a80f77f…` at
#: X06-WO3, `d0f0c8b7…` at X06-WO4), and re-taken at X06-FR0 over F2-WO8's list (`7792576e…`
#: before). Without them, with the two texts restored, it is `F2_SERVED_SHA256` (c_12 onto c_11).
X06_SERVED_SHA256 = "ba4b5ce59af4ac4c1e5d29f157ccd5d6308cc0a6282f0dc3434fc3b5cf88db62"
#: F8 (ADR 0067 D5, R-1076): the served digest with the replay report's reserved mode and its two
#: members in `get_job_result`'s output schema over X06's list, measured at F8-WO1b on `wp/F8`,
#: re-taken at F8-FR0 over F2-WO8's list (`c11d3877…` before) and at F8-FR1 over X06's list
#: (`3571c5c3…` before; `scripts/m07a_rc.py`'s `D_13`). Without them it is `X06_SERVED_SHA256`
#: (c_13 onto c_12).
F8_SERVED_SHA256 = "de241b22b43681d81d4afc02a2250ddef684b83fb258e9ae491bc8fee2c7fd94"
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


def _tools(mcp: ModuleType) -> list[dict[str, Any]]:
    """The served tool list as `harness.tool_descriptions_sha256` digests it."""
    return [tool.model_dump(mode="json", exclude_none=True) for tool in mcp.tools()]


def _before_f8(mcp: ModuleType) -> list[dict[str, Any]]:
    """The served tool list without F8's replay-report additions (`without_f8`), X06's list."""
    stripped = without_f8(_tools(mcp))
    assert isinstance(stripped, list)
    return stripped


def _before_x06(mcp: ModuleType) -> list[dict[str, Any]]:
    """The served tool list without F8's and X06's additions (`without_x06`), F2's list."""
    stripped = without_x06(_before_f8(mcp))
    assert isinstance(stripped, list)
    return stripped


def _before_f2(mcp: ModuleType) -> list[dict[str, Any]]:
    """The served tool list without F8's and X06's additions and F2's 14 kinds (`without_f2`),
    F3's list."""
    stripped = without_f2(_before_x06(mcp))
    assert isinstance(stripped, list)
    return stripped


def _before_f3(mcp: ModuleType) -> list[dict[str, Any]]:
    """The served tool list without X06's additions, F2's kinds and F3's five tools (`without_f3`),
    F1's list."""
    stripped = without_f3(_before_f2(mcp))
    assert isinstance(stripped, list)
    return stripped


def _before_f1(mcp: ModuleType) -> list[dict[str, Any]]:
    """The served tool list without F3's five tools and F1's two (`without_f1`), X04's list:
    every earlier decomposition starts from it."""
    stripped = without_f1(_before_f3(mcp))
    assert isinstance(stripped, list)
    return stripped


def _digest(tools: list[dict[str, Any]]) -> str:
    return hashlib.sha256(canonical_json(tools)).hexdigest()


def _served_without_m02(mcp: ModuleType) -> str:
    """The served tool list's digest with M04's and then M02's additive members removed (R-234;
    M04's decomposes onto M02's the same way, `test_m04s_surface_move_decomposes_onto_m02s`)."""
    return _digest(
        without_m02(
            without_m04(
                without_msg(without_x02(without_opt(without_st(without_x04(_before_f1(mcp))))))
            )
        )
    )


def _without_a3_2(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """`tools` with ADR 0019 Amendment 3's `elements` taken out of `diff_revisions`'s
    `outputSchema` alone (in place; returned for chaining)."""
    (diff,) = [tool for tool in tools if tool["name"] == "diff_revisions"]
    schema = diff["outputSchema"]
    assert schema["required"] == ["added", "changed", "elements", "removed"]
    del schema["properties"]["elements"]
    schema["required"].remove("elements")
    return tools


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
    # R-234: M02 moved the served list; without M02's additions it is M06's (R-192), and without
    # Amendment 3's member as well it is R-133's.
    assert harness.tool_descriptions_sha256() != M06_A3_SERVED_SHA256
    assert _served_without_m02(mcp) == M06_A3_SERVED_SHA256
    assert (
        _digest(
            _without_a3_2(
                without_m02(
                    without_m04(
                        without_msg(
                            without_x02(without_opt(without_st(without_x04(_before_f1(mcp)))))
                        )
                    )
                )
            )
        )
        == T08_DESCRIPTIONS_SHA256
    )
    assert T08_DESCRIPTIONS_SHA256 != _v17_c2_digest()


def test_m02s_surface_move_decomposes_onto_the_base(mcp: ModuleType) -> None:
    """R-234: the served list minus M02's additions is the base's registered list, and M02 changed
    no tool's name or description text (T08.A18 is not reopened)."""
    from benchmarks.t07.v17 import harness

    served = without_m04(
        without_msg(without_x02(without_opt(without_st(without_x04(_before_f1(mcp))))))
    )
    stripped = without_m02(served)
    assert harness.tool_descriptions_sha256() != M02_BASE_SERVED_SHA256
    assert hashlib.sha256(canonical_json(stripped)).hexdigest() == M02_BASE_SERVED_SHA256
    assert [(t["name"], t["description"]) for t in served] == [
        (t["name"], t["description"]) for t in stripped
    ]
    # The texts are the files, byte for byte (OPT's and X04's two in their earlier form); the files
    # are pinned against the base below.
    by_tool = {op.mcp_tool: name for name, op in OPERATIONS.items() if op.mcp_tool is not None}
    for tool in served:
        name = by_tool[tool["name"]]
        assert tool["description"] == _pre_opt_file(name)


def _pre_opt_file(name: str) -> str:
    """Operation `name`'s description file, OPT's two in their pre-OPT form, X04's two in their
    pre-X04 form, F2's one in its pre-F2 form and X06's two in their pre-X06 form."""
    if name in X06_DESCRIPTIONS:
        return pre_x06_text(name)
    if name in F2_DESCRIPTIONS:
        return pre_f2_text(name)
    if name in X04_DESCRIPTIONS:
        return pre_x04_text(name)
    if name in OPT_DESCRIPTIONS:
        return pre_opt_text(name)
    return (DESCRIPTIONS / f"{name}.md").read_text("utf-8")


def test_the_served_files_differ_from_v17_c2_in_exactly_the_two_reviewed_files() -> None:
    """Before OPT's two texts, X04's two and F2's one (restored from their pre-OPT, pre-X04 and
    pre-F2 copies), the files differ from `v17-c2`'s in exactly R-133's two; OPT and X04 changed
    exactly their two, F2 its one."""
    assert sorted(V17_C2_FILE_SHA256) == PRE_MSG_MCP_OPERATIONS
    served = {name: _sha256(_pre_opt_file(name)) for name in PRE_MSG_MCP_OPERATIONS}
    files = {name: (DESCRIPTIONS / f"{name}.md").read_text("utf-8") for name in MCP_OPERATIONS}
    assert sorted(n for n in MCP_OPERATIONS if files[n] != _pre_opt_file(n)) == sorted(
        {*OPT_DESCRIPTIONS, *X04_DESCRIPTIONS, *F2_DESCRIPTIONS, *X06_DESCRIPTIONS}
    )
    changed = sorted(
        name for name in PRE_MSG_MCP_OPERATIONS if served[name] != V17_C2_FILE_SHA256[name]
    )
    assert tuple(changed) == CHANGED
    for name in CHANGED:
        kept = (V17_C2_TEXTS / f"{name}.md").read_text("utf-8")
        assert _sha256(kept) == V17_C2_FILE_SHA256[name]


def test_restoring_the_two_files_reproduces_v17_c2s_digest(mcp: ModuleType) -> None:
    """With every link stripped (OPT's restoring its two texts to their pre-OPT form), `v17-c2`'s
    two texts in place of R-133's give `v17-c2`'s digest. (The texts are replaced after the
    strips: OPT's strip sets `validate`'s text to its pre-OPT form, which is R-133's.)"""
    texts = {
        OPERATIONS[name].mcp_tool: (V17_C2_TEXTS / f"{name}.md").read_text("utf-8")
        for name in CHANGED
    }
    stripped = _without_a3_2(
        without_m02(
            without_m04(
                without_msg(without_x02(without_opt(without_st(without_x04(_before_f1(mcp))))))
            )
        )
    )
    for tool in stripped:
        tool["description"] = texts.get(tool["name"], tool["description"])
    assert _digest(stripped) == _v17_c2_digest()


def test_m04s_surface_move_decomposes_onto_m02s(mcp: ModuleType) -> None:
    """M04 (ADR 0037 D6), following R-234: the served list minus M04's additions is M02's served
    list (which in turn decomposes onto the base above), M04 moved it, and M04 changed no tool's
    name or description text."""
    served = without_msg(without_x02(without_opt(without_st(without_x04(_before_f1(mcp))))))
    stripped = without_m04(served)
    assert _digest(stripped) != _digest(served)
    assert _digest(without_m02(stripped)) == M02_BASE_SERVED_SHA256
    assert [(t["name"], t["description"]) for t in served] == [
        (t["name"], t["description"]) for t in stripped
    ]


def test_msgs_surface_move_decomposes_onto_m04s(mcp: ModuleType) -> None:
    """MSG-G10 (ADR 0058, R-934): the served list is `MSG_SERVED_SHA256`; minus MSG's additions it
    is M04's registered list (R-457). MSG added one tool, `explain` (D7), and changed no other
    tool's name or description text."""
    served = without_x02(
        without_opt(without_st(without_x04(_before_f1(mcp))))
    )  # X02's and OPT's additions postdate MSG
    stripped = without_msg(served)
    assert _digest(served) == MSG_SERVED_SHA256
    assert _digest(stripped) == M04_SERVED_SHA256
    added = [t for t in served if t["name"] in {OPERATIONS[n].mcp_tool for n in MSG_OPERATIONS}]
    assert [t["name"] for t in added] == ["explain"]
    kept = [t for t in served if t not in added]
    assert [(t["name"], t["description"]) for t in kept] == [
        (t["name"], t["description"]) for t in stripped
    ]
    # Only `get_job_result`'s reaches a run result once inlined (an unused `$def` is not served).
    moved = [t["name"] for t, u in zip(kept, stripped, strict=True) if t != u]
    assert moved == [OPERATIONS["get_job_result"].mcp_tool]


def test_x02s_surface_move_decomposes_onto_msgs(mcp: ModuleType) -> None:
    """X02 (ADR 0070, R-950): the served list is `X02_SERVED_SHA256`; minus X02's additions it is
    MSG's served list (R-934, which decomposes onto M04's above). X02 added no tool and changed no
    tool's name or description text; the tools that moved are the six that serve the job request
    (`solve_body`)."""
    served = without_opt(without_st(without_x04(_before_f1(mcp))))  # OPT's additions postdate X02
    stripped = without_x02(served)
    assert _digest(served) == X02_SERVED_SHA256
    assert _digest(stripped) == MSG_SERVED_SHA256
    assert [(t["name"], t["description"]) for t in served] == [
        (t["name"], t["description"]) for t in stripped
    ]
    moved = {t["name"] for t, u in zip(served, stripped, strict=True) if t != u}
    assert moved == {
        OPERATIONS[name].mcp_tool
        for name in ("submit_job", "get_job", "list_jobs", "wait_job", "cancel_job")
    } | {OPERATIONS["get_job_result"].mcp_tool}


def test_opts_surface_move_decomposes_onto_x02s(mcp: ModuleType) -> None:
    """OPT (ADR 0071, R-960): the served list is `OPT_SERVED_SHA256`; minus OPT's additions, with
    its two texts restored, it is X02's served list (R-950, which decomposes onto MSG's and M04's
    above). OPT added no tool and changed no tool's name; the tools that moved are the six that
    serve the job request or result and `validate`, and the texts that changed are exactly
    `validate`'s and `submit_job`'s."""
    served = without_st(without_x04(_before_f1(mcp)))  # ST's tool postdates OPT
    stripped = without_opt(served)
    assert _digest(served) == OPT_SERVED_SHA256
    assert _digest(stripped) == X02_SERVED_SHA256
    assert [t["name"] for t in served] == [t["name"] for t in stripped]
    retexted = {
        t["name"]
        for t, u in zip(served, stripped, strict=True)
        if t["description"] != u["description"]
    }
    assert retexted == {OPERATIONS[name].mcp_tool for name in OPT_DESCRIPTIONS}
    moved = {t["name"] for t, u in zip(served, stripped, strict=True) if t != u}
    assert moved == {
        OPERATIONS[name].mcp_tool
        for name in ("submit_job", "get_job", "list_jobs", "wait_job", "cancel_job", "validate")
    } | {OPERATIONS["get_job_result"].mcp_tool}


def test_sts_surface_move_decomposes_onto_opts(mcp: ModuleType) -> None:
    """ST G12 (ADR 0068, R-1000): the served list is `ST_SERVED_SHA256`; minus ST's tool it is
    OPT's (`OPT_SERVED_SHA256`, which decomposes onto X02's, MSG's and M04's above). ST added one
    tool, `get_stream_table`, after `get_artifact`, and moved no other tool at all — name,
    description, input or output schema."""
    served = without_x04(_before_f1(mcp))  # X04's additions postdate ST
    stripped = without_st(served)
    assert _digest(served) == ST_SERVED_SHA256
    assert _digest(stripped) == OPT_SERVED_SHA256
    names = [t["name"] for t in served]
    added = [t for t in served if t["name"] in {OPERATIONS[n].mcp_tool for n in ST_OPERATIONS}]
    assert [t["name"] for t in added] == ["get_stream_table"]
    assert names.index("get_stream_table") == names.index("get_artifact") + 1
    assert [t for t in served if t not in added] == stripped
    (tool,) = added
    assert tool["description"] == pre_x04_text("get_stream_table")


def test_x04s_surface_move_decomposes_onto_sts(mcp: ModuleType) -> None:
    """X04 (ADR 0075, R-1010): the served list is `X04_SERVED_SHA256`; minus X04's additions, with
    its two texts restored, it is ST's (`ST_SERVED_SHA256`, which decomposes onto OPT's and the
    earlier lists above). X04 added no tool and changed no tool's name; the tools that moved are
    `get_project` (`ambient_pressure`), `get_job_result` (the request member, `display_units`,
    `display`), `get_stream_table` (the request member) and `explain` (`display`), and the texts
    that changed are exactly `get_job_result`'s and `get_stream_table`'s, each the file."""
    served = _before_f1(mcp)  # F1's tools postdate X04
    stripped = without_x04(served)
    assert _digest(served) == X04_SERVED_SHA256
    assert _digest(stripped) == ST_SERVED_SHA256
    assert [t["name"] for t in served] == [t["name"] for t in stripped]
    retexted = {
        t["name"]
        for t, u in zip(served, stripped, strict=True)
        if t["description"] != u["description"]
    }
    assert retexted == {OPERATIONS[name].mcp_tool for name in X04_DESCRIPTIONS}
    for tool in served:
        if tool["name"] in retexted:
            (name,) = [n for n in X04_DESCRIPTIONS if OPERATIONS[n].mcp_tool == tool["name"]]
            assert tool["description"] == (DESCRIPTIONS / f"{name}.md").read_text("utf-8")
    moved = {t["name"] for t, u in zip(served, stripped, strict=True) if t != u}
    assert moved == {
        OPERATIONS[name].mcp_tool
        for name in ("get_project", "get_job_result", "get_stream_table", "explain")
    }


def test_f1s_surface_move_decomposes_onto_x04s(mcp: ModuleType) -> None:
    """F1 (ADR 0060 D11, R-1030): the served list is `F1_SERVED_SHA256`; minus F1's two tools it is
    X04's (`X04_SERVED_SHA256`, which decomposes onto ST's and the earlier lists above). F1 added
    `list_capabilities` and `check_admission`, each served from its file (`check_admission`'s in
    its pre-F2 form: F2-WO8 changed it), and moved no other tool at all: name, description, input
    or output schema."""
    served = _before_f3(mcp)  # F3's tools postdate F1
    stripped = without_f1(served)
    assert _digest(served) == F1_SERVED_SHA256
    assert _digest(stripped) == X04_SERVED_SHA256
    added = [t for t in served if t["name"] in {OPERATIONS[n].mcp_tool for n in F1_OPERATIONS}]
    assert sorted(t["name"] for t in added) == ["check_admission", "list_capabilities"]
    assert [t for t in served if t not in added] == stripped
    for tool in added:
        name = tool["name"]
        expected = pre_f2_text(name) if name in F2_DESCRIPTIONS else None
        assert tool["description"] == (expected or (DESCRIPTIONS / f"{name}.md").read_text("utf-8"))


def test_f3s_surface_move_decomposes_onto_f1s(mcp: ModuleType) -> None:
    """F3 (ADR 0061 D13, R-1051): the served list is `F3_SERVED_SHA256`; minus F3's five tools it
    is F1's (`F1_SERVED_SHA256`, which decomposes onto X04's and the earlier lists above). F3
    added the five `Records` tools, each served from its file, and moved no other tool at all:
    name, description, input or output schema."""
    served = _before_f2(mcp)  # F2's and X06's additions postdate F3
    stripped = without_f3(served)
    assert _digest(served) == F3_SERVED_SHA256
    assert _digest(stripped) == F1_SERVED_SHA256
    added = [t for t in served if t["name"] in {OPERATIONS[n].mcp_tool for n in F3_OPERATIONS}]
    assert sorted(t["name"] for t in added) == sorted(F3_OPERATIONS)
    assert [t for t in served if t not in added] == stripped
    for tool in added:
        assert tool["description"] == (DESCRIPTIONS / f"{tool['name']}.md").read_text("utf-8")


def test_f2s_surface_move_decomposes_onto_f3s(mcp: ModuleType) -> None:
    """F2 (ADR 0062 D1): the served list is `F2_SERVED_SHA256`; minus F2's 14 kinds it is F3's
    (`F3_SERVED_SHA256`, which decomposes onto F1's and the earlier lists above). F2 added no tool
    and changed no tool's name; it changed one description text, `check_admission`'s (F2-WO8,
    restored from its pre-F2 copy by the strip), and moved `list_models` in exactly its two kind
    enums (pins' and choice options' `specifications`), each by exactly the 14 kinds and the
    description's one sentence."""
    served = _before_x06(mcp)  # X06's and F8's additions postdate F2
    stripped = without_f2(served)
    assert _digest(served) == F2_SERVED_SHA256
    assert _digest(stripped) == F3_SERVED_SHA256
    assert [t["name"] for t in served] == [t["name"] for t in stripped]
    moved = [(t, u) for t, u in zip(served, stripped, strict=True) if t != u]
    admission = OPERATIONS["check_admission"].mcp_tool
    assert sorted(t["name"] for t, _ in moved) == sorted(
        [OPERATIONS["list_models"].mcp_tool, admission]
    )
    ((text, text_before),) = [(t, u) for t, u in moved if t["name"] == admission]
    assert {**text, "description": text_before["description"]} == text_before
    assert text_before["description"] == pre_f2_text("check_admission")
    assert text["description"] == text_before["description"].replace(
        "<schema_version 1 document>", "<schema_version 1 or 2 document>"
    )
    ((tool, before),) = [(t, u) for t, u in moved if t["name"] != admission]
    assert tool["inputSchema"] == before["inputSchema"]
    pins = ("pins", "items", "properties", "specifications")
    options = ("choices", "items", "properties", "options", "items", "properties", "specifications")
    for path in (pins, options):
        kind, kind_before = (_at(t["outputSchema"], path) for t in (tool, before))
        assert kind["enum"] == [*kind_before["enum"], *F2_KINDS]
        assert kind["description"] == kind_before["description"] + F2_KIND_NOTE
        # Nothing else in the kind's schema moved.
        assert {k: v for k, v in kind.items() if k not in ("enum", "description")} == {
            k: v for k, v in kind_before.items() if k not in ("enum", "description")
        }
    # With the two kinds put back, the tool is F3's exactly: nothing else in it moved.
    for path in (pins, options):
        _at(tool["outputSchema"], path).update(_at(before["outputSchema"], path))
    assert tool == before


def test_f8s_surface_move_decomposes_onto_x06s(mcp: ModuleType) -> None:
    """F8 (ADR 0067 D5, R-1076): the served list is `F8_SERVED_SHA256`; minus F8's additions it is
    X06's (`X06_SERVED_SHA256`, which decomposes onto F2's and the earlier lists above; F8-FR1:
    F2 and X06 merge first, R-1072/R-1073). F8 added no
    tool and changed no tool's name or description text; the one tool that moved is
    `get_job_result`, in exactly its replay report: `mode` by the one reserved value and the
    properties by the two optional members, nothing else."""
    served = _tools(mcp)
    stripped = without_f8(served)
    assert _digest(served) == F8_SERVED_SHA256
    assert _digest(stripped) == X06_SERVED_SHA256
    assert [(t["name"], t["description"]) for t in served] == [
        (t["name"], t["description"]) for t in stripped
    ]
    moved = [(t, u) for t, u in zip(served, stripped, strict=True) if t != u]
    assert [t["name"] for t, _ in moved] == [OPERATIONS["get_job_result"].mcp_tool]
    ((tool, before),) = moved
    assert tool["inputSchema"] == before["inputSchema"]
    (report,) = tool["outputSchema"]["properties"]["replay_report"]["anyOf"][:1]
    (report_before,) = before["outputSchema"]["properties"]["replay_report"]["anyOf"][:1]
    assert report["properties"]["mode"]["enum"] == [
        *report_before["properties"]["mode"]["enum"],
        F8_REPLAY_MODE,
    ]
    assert sorted(set(report["properties"]) - set(report_before["properties"])) == sorted(
        F8_REPORT_MEMBERS
    )
    assert report["required"] == report_before["required"]  # both members optional
    # With the report put back, the tool is X06's exactly: nothing else in it moved.
    tool["outputSchema"]["properties"]["replay_report"]["anyOf"][0] = report_before
    assert tool == before


def _at(schema: dict[str, Any], path: tuple[str, ...]) -> dict[str, Any]:
    """The `kind` property schema of the `specifications` items at `path` under `models`' items."""
    node: Any = schema["properties"]["models"]["items"]["properties"]
    for key in path:
        node = node[key]
    kind = node["items"]["properties"]["kind"]
    assert isinstance(kind, dict)
    return kind


def test_x06s_surface_move_decomposes_onto_f2s(mcp: ModuleType) -> None:
    """X06 (ADR 0078 D6, R-1073; E-X06-22): the served list is `X06_SERVED_SHA256`; minus X06's
    additions, with its two texts restored, it is F2's (`F2_SERVED_SHA256`, which decomposes onto
    F3's and the earlier lists above). X06-WO2 added the three `Branches` tools after F3's and
    X06-WO3 the two `SolvePolicies` tools after them and X06-WO4 the four `Administration` tools
    after those, each served from its file; the tools that
    moved are the two that serve the ChangeSet as a request (`commit_change`, `preview_change`:
    the `branch` member and the text) and `get_job_result` (the optimization report's candidate
    ChangeSet), and nothing else moved. F8's additions postdate X06 (F8-FR1)."""
    served = _before_f8(mcp)
    stripped = without_x06(served)
    assert _digest(served) == X06_SERVED_SHA256
    assert _digest(stripped) == F2_SERVED_SHA256
    names = [t["name"] for t in served]
    added = [t for t in served if t["name"] in {OPERATIONS[n].mcp_tool for n in X06_OPERATIONS}]
    x06_tools = [
        "list_branches",
        "create_branch",
        "delete_branch",
        "register_solve_policy",
        "get_solve_policy",
        "get_policy",
        "grant_capability",
        "revoke_capability",
        "set_ambient_pressure",
    ]
    assert [t["name"] for t in added] == x06_tools
    assert names[-9:] == x06_tools
    for tool in added:
        assert tool["description"] == (DESCRIPTIONS / f"{tool['name']}.md").read_text("utf-8")
    kept = [t for t in served if t not in added]
    assert [t["name"] for t in kept] == [t["name"] for t in stripped]
    retexted = {
        t["name"]
        for t, u in zip(kept, stripped, strict=True)
        if t["description"] != u["description"]
    }
    assert retexted == {OPERATIONS[name].mcp_tool for name in X06_DESCRIPTIONS}
    moved = {t["name"] for t, u in zip(kept, stripped, strict=True) if t != u}
    assert moved == {
        OPERATIONS[name].mcp_tool for name in ("commit_change", "preview_change", "get_job_result")
    }
