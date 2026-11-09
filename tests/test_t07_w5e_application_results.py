"""T07 W5e: the JobControl and Inspection result shapes are frozen in
`schemas/application-results.schema.json` (design note ruling round 4, W5a-Q2, §11.3–§11.4 as
amended; ADR 0019 Amendment 1; gates R4-G3 and R4-G4).

- **The move is inert (R4-G3).** For each of the 20 operations of `b13d556`, `canonical_json`
  of its response schema with every `$ref` inlined equals the snapshot taken at `b13d556`, whose
  `operations.py` is `9b541df`'s. The snapshot is pinned here as SHA-256 digests; `artifact_bytes`
  has no response schema (its response is bytes). Amendments 2 and 3 re-take `list_models` and
  `diff_revisions`, and Amendment 3 adds `list_audit`.
- **The schema.** One `$def` per response shape in `OPERATIONS` with no published schema of its
  own, named in snake_case after its Python result type, a page `<item>_page`; each such operation
  `$ref`s its `$def`.
- **Fixtures (R4-G3).** At least one valid fixture per `$def`, emitted from real responses through
  `dispatch` (`scripts/t07_schema_fixtures.py`, the job-fixture precedent, R-015), and one invalid
  fixture per `$def`: the valid one with a required member removed.
- **Responses (R4-G3).** Every response the W4 and W5 tests produce is held to its operation's
  response schema — now the published `$def` — by `test_t07_w5a_operations` (every operation
  through `dispatch`, and G13) and by `t07_jobs_support.response_schema_violations` at the
  teardown of the W4 test projects.
- **The frozen list (R4-G4).** `docs/interfaces-frozen.md` §2 lists the file, and ADR 0019 carries
  Amendment 1.
"""

from __future__ import annotations

import hashlib
import sys
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import urldefrag, urljoin

import pytest
from conftest import REPO_ROOT, load_json
from jsonschema import Draft202012Validator
from m02_schema_support import without_m02
from m04_schema_support import without_m04
from msg_schema_support import MSG_OPERATIONS, without_msg
from opt_schema_support import without_opt
from st_schema_support import ST_OPERATIONS
from x02_schema_support import without_x02
from x04_schema_support import without_x04

from openflowsheet.application.operations import OPERATIONS, Operation
from openflowsheet.application.types import SCHEMA_BASE, schema_errors
from openflowsheet.canonical import canonical_json

SCHEMA = "application-results.schema.json"
SCHEMA_DIR = REPO_ROOT / "schemas"
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "schemas" / "application_results"
#: The operation each `$def` answers (§4.3), by the rule: the snake_case of its result type.
DEF_OF_OPERATION: dict[str, str] = {
    "submit_job": "submit_result",
    "list_jobs": "job_page",
    "list_job_events": "job_event_page",
    "wait_job": "job_wait",
    "get_project": "project_summary",
    "list_models": "model_registry_view",
    "list_revisions": "revision_page",
    "get_revision": "projection",
    "inspect_structure": "projection",
    "get_artifact": "projection",
    "diff_revisions": "semantic_diff",
    # ADR 0019 Amendment 3 (A3.3)
    "list_audit": "audit_page",
    # ADR 0058 D7 (MSG WO-7)
    "explain": "message_entry",
    # ADR 0068 (ST): the stream table is a projection, as every other view
    "get_stream_table": "projection",
}
#: `revision_summary` and `audit_record` are pages' items, each its own `$def`.
#: `explanation` is MSG's (ADR 0058 D3): no operation's response is it, `RunResult.failure` and
#: a transported `ApiError`'s `detail` carry it.
DEFS = frozenset({*DEF_OF_OPERATION.values(), "revision_summary", "audit_record", "explanation"})
#: R4-G3: SHA-256 of `canonical_json` of each operation's fully resolved response schema, taken at
#: `b13d556` with `resolved_response` below (`None`: no response schema).
SNAPSHOT_AT_B13D556: dict[str, str | None] = {
    "validate": "dbbdaa6c1e6859398c5d685df7c881b8739fa786b4db981d00c071ed4aff7582",
    "commit_change": "d416001ea57015e2f08b602623c845d4fb3606575fd03eb363d888b813b58941",
    "solve": "9a9b75207b7d94467ade4dff227760dbe059451f94fc5d573fae35ff687498c7",
    "reproduce": "8e62572a35ecd04613e194db6cbf82cd53da11cd150d7360a1056b0fbb31cd66",
    "submit_job": "0cd08fb1d03d1ff16f89db5d9a6c6602bcac8772740d30ed2ff49595cf2e3995",
    "get_job": "599ebcdb703795bae609c5a804dfbd54b7f9b489ee9cf328cf879948dddcb736",
    "list_jobs": "cf3c8df4f34064a7ee04a5ef098fe5304b25b0ccede5aa69d180de9571dce660",
    "list_job_events": "8784978e7d6a6cde8a94b70c14252f0f4a9dfa3b6d2ddd2f771fde74dfe4a835",
    "wait_job": "347d746a0ef4806b14a83d7c7d3cb4bc909a488c30d65fc0f4cea4afaf537986",
    "cancel_job": "599ebcdb703795bae609c5a804dfbd54b7f9b489ee9cf328cf879948dddcb736",
    "get_job_result": "7a8610722f2d4644e792e571879f9c01d43693ea3f767d3be724839bd53a4598",
    "get_project": "0eb1108f60e26c855b4e72747118184be043d60fdcf4237355f6f5a4e415253b",
    "list_models": "6b4d0be4dbe3e7f309f53c192fbbc7ec1fb3cbe005a6a88b45274bdf1616203f",
    "list_revisions": "33627ba534225466aed55586e31158b1c703f72a533cf6337255f59a0baa19fc",
    "get_revision": "951b77ea0f69a0eb8f5cb7d44a9c1c570dd6d05d57b7c72de05a7a7e61208465",
    "diff_revisions": "9544ff03264e46a0684f8a89e45197b37319db193c21ec97d7f0ecde908e1dea",
    "inspect_structure": "951b77ea0f69a0eb8f5cb7d44a9c1c570dd6d05d57b7c72de05a7a7e61208465",
    "preview_change": "d416001ea57015e2f08b602623c845d4fb3606575fd03eb363d888b813b58941",
    "get_artifact": "951b77ea0f69a0eb8f5cb7d44a9c1c570dd6d05d57b7c72de05a7a7e61208465",
    "artifact_bytes": None,
}


# -------------------------------------------------------------------------- $ref resolution


def _published() -> dict[str, Any]:
    documents = (load_json(path) for path in sorted(SCHEMA_DIR.glob("*.schema.json")))
    return {document["$id"]: document for document in documents}


def _target(document: Any, fragment: str) -> Any:
    """RFC 6901 over a JSON Schema document (a `$ref` fragment is a pointer here)."""
    node = document
    for token in fragment.split("/")[1:] if fragment else ():
        node = node[token.replace("~1", "/").replace("~0", "~")]
    return node


def _resolved(
    schema: Any,
    base: str,
    published: dict[str, Any],
    seen: tuple[str, ...],
    in_defs: bool = False,
) -> Any:
    """`schema` inlined. A cyclic `$ref` raises, except one met inside a `$defs` member, which
    becomes a `$comment` naming it (OPT D-60): `optimization-request.schema.json`'s
    `$defs/optimize_body` refers to its own document's root, so inlining that root reaches the
    body again through its `$defs`. Only inputs that raised before take that branch, so no earlier
    snapshot moves."""
    if isinstance(schema, list):
        return [_resolved(item, base, published, seen, in_defs) for item in schema]
    if not isinstance(schema, dict):
        return schema
    members = {
        key: _resolved(value, base, published, seen, in_defs or key == "$defs")
        for key, value in schema.items()
        if key != "$ref"
    }
    if "$ref" not in schema:
        return members
    absolute = urljoin(base, schema["$ref"])
    if absolute in seen:
        if in_defs:
            return {**members, "$comment": f"recursive reference to {absolute}, not inlined"}
        raise ValueError(f"a cyclic $ref: {absolute}")
    uri, fragment = urldefrag(absolute)
    target = _resolved(
        _target(published[uri], fragment), uri, published, (*seen, absolute), in_defs
    )
    if not members:
        return target
    assert "allOf" not in members, "a $ref beside an allOf"
    return {**members, "allOf": [target]}


def resolved_response(operation: Operation) -> Any:
    """The operation's response schema with every `$ref` inlined, recursively: a `$ref` alone is
    replaced by its target, one with siblings becomes `allOf: [target]` beside them."""
    if operation.response_schema is None:
        return None
    return _resolved(dict(operation.response_schema), "", _published(), ())


def _digest(document: Any) -> str | None:
    return None if document is None else hashlib.sha256(canonical_json(document)).hexdigest()


# ----------------------------------------------------------------------------------- R4-G3


#: ADR 0019 Amendment 2 (approved by Frank on 2026-09-27; T07 ruling round 6, B2 item 4, gate
#: G-R6-6): `model_registry_view`'s pins and choice options gain the required member
#: `specifications`. `list_models`'s snapshot is re-taken; every other operation's stands.
SNAPSHOT_AMENDMENT_2: dict[str, str | None] = {
    "list_models": "12d8824519a37a41eafa12a88308bbafa563ccd706d226c60f3f39310b6cad85",
}
#: ADR 0019 Amendment 3, A3.2 (approved by Frank on 2026-10-08; M06 design note §4.2, gate G5):
#: `semantic_diff` gains the required member `elements`. `diff_revisions`'s snapshot is re-taken;
#: with the member removed it is the `b13d556` snapshot again.
SNAPSHOT_AMENDMENT_3: dict[str, str | None] = {
    "diff_revisions": "07f04027b7ce896a9c42e0dcd6b45ab60f518edfbd992e60aa50d707e79b473e",
    # A3.3: the new operation `list_audit`, by addition (it had no snapshot to move from).
    "list_audit": "658c9b64bf105525b15916eafa494c88bf54920d697853a3debaaddada2b9a7c",
}


#: M02 (ADR 0033-0035, design note §3.6): the operations whose resolved response embeds a schema
#: M02 widened additively (`job`, `run-result`, `solve-event`, `api-error`, `transaction-result`).
#: Re-taken; with M02's additions removed every one is its earlier snapshot again (G1 (c),
#: `tests/test_m02_schemas.py`). The `job.schema.json`-embedding ones re-taken again at WO-6,
#: where `job_result`'s `experiment` member admits null for a job ended before any attempt.
SNAPSHOT_M02: dict[str, str | None] = {
    "commit_change": "c44597cdfdff995b96c491f8b4de0e71d17c79d442519e4b8e5cbeee81a28207",
    "preview_change": "c44597cdfdff995b96c491f8b4de0e71d17c79d442519e4b8e5cbeee81a28207",
    "solve": "892799e0e9385badcd353ae38e1ec483b6510abb04983647a922d87f6a929505",
    "submit_job": "e9abdbeb0d5cdfcabb497a0961bf1472852954c148f520f51ec93d9630a704da",
    "get_job": "1d3c46e2e941994d4f946f1b8de9cd31a256b0d9306c18d298a2af70f25325c4",
    "cancel_job": "1d3c46e2e941994d4f946f1b8de9cd31a256b0d9306c18d298a2af70f25325c4",
    "list_jobs": "0ae6014c2dba7c1801b3ae33b8ce87125ecaa0005e1671214537c1dbe60d1a81",
    "list_job_events": "9e7f7152392798eec6d79c2be32ca7c90287dcce754cfb4c9d2cb5c3dab561fa",
    "wait_job": "1b119ce8f27d361d598aef22268d9c5046daa73814670687909c6f4719142ccb",
    "get_job_result": "e76fcd6c22749c16c55c2246e2542ede607bca861661c7be2ebc7d10425a07f4",
}


#: M04 (ADR 0037 D6, ADR 0019 Amendment 5): the operations whose resolved response embeds
#: `job.schema.json`, which gains the `surrogate_study` operation, its body branch, two artifact
#: kinds and `job_result`'s `surrogate_study` member. Re-taken; with M04's additions removed
#: (`tests/m04_schema_support.py`) every one is its `SNAPSHOT_M02` value again
#: (`tests/test_m04_study_job.py`). Re-taken at M04 Amendment 2 (build log E26): the body's
#: `plan_id` pattern admits `b2-it<i>`; `solve`, `list_job_events` and `get_job_result` do not
#: embed the body and stand.
SNAPSHOT_M04: dict[str, str | None] = {
    "solve": "5b57cd405a07bb31faa5dbd975099aaef6acff63369a80679b2fc38d18be245a",
    "submit_job": "122685ba5d8a10abda155f2c780ca4cbd153f30a020ccff24bec8ef3a7df49f2",
    "get_job": "495b5e39670d2e50f1afcc65f74d62d72df39cf3684caa01ba398cc074a50688",
    "cancel_job": "495b5e39670d2e50f1afcc65f74d62d72df39cf3684caa01ba398cc074a50688",
    "list_jobs": "073d671f237aa768695a443de80abd50dfafb6ec180896a0db0ee2ddb92f1aea",
    "list_job_events": "fea66b274012462bf3b573a88ade48356e41c93cbbea288f480db93e5bdbbcbf",
    "wait_job": "5fc1ef1fa2774bece09c8d401cbb986b008a33b46a628964edb83c405f2dd030",
    "get_job_result": "a4ae235fb61b8566dbc660f1f864a7c7f8ab122e4000fee0825b5f414bfa988a",
}


#: MSG-G10 (ADR 0058 D5, R-934): `RunResult` gains the required, nullable member `failure`, so
#: every response that reaches a run result moves. Taken at MSG WO-6; with MSG's additions removed
#: (`tests/msg_schema_support.py`) each is its value before MSG again
#: (`test_msg_g10_without_failure_every_response_is_its_pre_msg_snapshot`).
SNAPSHOT_MSG: dict[str, str | None] = {
    "solve": "9c4b2e9ac57f55e1b27f8fe51c8701e06c8a001c372efb2369d66e8f6b29611d",
    "submit_job": "8b41af7869075bc82b0aaae51c436524098a95adf5337cf554aa83571042218e",
    "get_job": "fa671751435bb82de48af731c8207a30fa09fe4d411d57acacbbfd69c2bf381c",
    "list_jobs": "b4e10d15c0e000e135467398e17f0162beb67a8d78cf86909df384291a38eca6",
    "wait_job": "a67fe653b2fb80f6ef2a3ca7cd73f2cbab6091656fae3b38683ff153297a23cc",
    "cancel_job": "fa671751435bb82de48af731c8207a30fa09fe4d411d57acacbbfd69c2bf381c",
    "get_job_result": "aec2e54622d8776e59d4e34134e9b5911ddeb7ccce3f29ee496ad0d3e083e526",
}
#: MSG-G10 (ADR 0058 D7): the `explain` row is new (`message_entry`). Taken at MSG WO-7; it has no
#: pre-MSG value, and `without_msg` leaves no other operation's snapshot moved by it.
SNAPSHOT_MSG_EXPLAIN: dict[str, str | None] = {
    "explain": "a4fcafe739c5fa4e6a82cc75170d6b67b915126b5329129f15a84da8a3f26127",
}
#: X02 (ADR 0070, ADR 0019 Amendment 15): the operations whose resolved response embeds
#: `job.schema.json`'s `solve_body`, which gains the optional `warm_start`. Taken at X02 WO-2 over
#: M04's responses, re-taken when `main` (MSG) was merged into `wp/X02`; with X02's additions
#: removed (`tests/x02_schema_support.py`) each is its `SNAPSHOT_MSG` (or `SNAPSHOT_M04`) value
#: again (`test_x02_without_warm_start_every_response_is_its_pre_x02_snapshot`).
SNAPSHOT_X02: dict[str, str | None] = {
    "submit_job": "c7c943e33959eb52a9444cac3590d9220c2b949e577b84390d0e4b452a1e216d",
    "get_job": "58acf056845fbc271e282b7b653c27e98341a719ef8c2b9e02ed64c60c4b2fbf",
    "cancel_job": "58acf056845fbc271e282b7b653c27e98341a719ef8c2b9e02ed64c60c4b2fbf",
    "list_jobs": "531d74323c395c369c1e312733360fa4c856045f66b4f591ff84b9d28eed350b",
    "wait_job": "aee140a905404cbc4541de59eff9fb9d3c2bb6c9e1ca5f410d60fdb28996cc5d",
    "get_job_result": "9347208b0c04ff78b686323c6f23107fd57612cf80dbe4f1bd59eeaf957e82cf",
}
#: OPT (ADR 0071, ADR 0019 Amendment 16): the operations whose resolved response embeds an enum or
#: branch OPT widened (the job operation, the request and result branches, the artifact kinds).
#: Taken at OPT WO-6, re-taken when `main` (MSG, X02) was merged into `wp/OPT`; with OPT's additions
#: removed (`tests/opt_schema_support.py`) each is its `SNAPSHOT_X02` (or earlier) value again
#: (`test_opt_without_its_additions_every_response_is_its_pre_opt_snapshot`).
SNAPSHOT_OPT: dict[str, str | None] = {
    "solve": "7e6839850000e0be81db15fcaa59b88bd367d73f5649b6e3844fc16b13ec4ada",
    "submit_job": "b1b7ebfde3cb0fdffab462dca8765513c5c14336dc20ef62bef3fa5d3092c696",
    "get_job": "d6514613a8d894e37295b4a38e7120351256fc3a9938806a7d95677f1347e36a",
    "list_jobs": "386b39be780ea2d036e0b1c060804c79e29c7bfb06ae23b22c16c9347b34dea7",
    "list_job_events": "751ec851357114a79d56275011fdbe8840e03b36e21d4a2a377fd36e2c364887",
    "wait_job": "38629f7b22454f174e3e0a13bedc9285292b63757dca93e10c41f26b638c5660",
    "cancel_job": "d6514613a8d894e37295b4a38e7120351256fc3a9938806a7d95677f1347e36a",
    "get_job_result": "9a3e82fb0d6f8f89cbd5729489ae82e6c2340e299b7d5a2e9c7ee29024063c8e",
}
#: ST G12 (ADR 0068): the `get_stream_table` row is new; its response is the `projection` `$def`,
#: so its snapshot is `get_artifact`'s, and no other snapshot moves (`st_schema_support`).
SNAPSHOT_ST: dict[str, str | None] = {
    "get_stream_table": "951b77ea0f69a0eb8f5cb7d44a9c1c570dd6d05d57b7c72de05a7a7e61208465",
}
#: X04 (ADR 0075, ADR 0019 Amendment 17; R-1010): the operations whose resolved response embeds
#: `project_summary` (`ambient_pressure`, D6.3), an explanation's numbers (`display`, D7.1–D7.2) or
#: `job_result` (`display_units`, D7.4–D7.5). Taken in X04's final work order over ST's responses;
#: with X04's additions removed (`tests/x04_schema_support.py`) each is its `SNAPSHOT_ST` (or
#: earlier) value again (`test_x04_without_its_additions_every_response_is_its_pre_x04_snapshot`).
SNAPSHOT_X04: dict[str, str | None] = {
    "get_project": "0124a532c7cf9c5d84850b609253b594346258a6ed83224c47e208e069664ff2",
    "solve": "e7f66229ba0e6c43c21226fb4db3cd8e273da6838ea95a5423603d89e50bab04",
    "submit_job": "9a6b2d2623b0c5c98cf3c6726465897834f20bd9a283bdb4797a996c87ca69d6",
    "get_job": "8d01b63a3caa3f024a5014619cd48f15552fa3a1306df93634eef687c9a4cfe5",
    "list_jobs": "c7bb7114734034dd108ecc61d10ac72c0b22d494ea4f1b87eae0f9d17efb31a0",
    "wait_job": "fd16741d814bbae321fb820832fcde74bc229a8a8908078ce3e8255071b9d681",
    "cancel_job": "8d01b63a3caa3f024a5014619cd48f15552fa3a1306df93634eef687c9a4cfe5",
    "get_job_result": "866c3ca98e8c4cdf25f6b73cc5049f9d3e28c5bd5ef8cef045fd03e69bb52364",
    "explain": "eb32f91fcb5209fcf0893734c083a4c6a357e4524557f78c537d5461a9f894c2",
}


def _without_specifications(schema: Any) -> Any:
    """`schema` with Amendment 2's member taken out of every pin and option: its property and its
    entry in `required`."""
    if isinstance(schema, list):
        return [_without_specifications(item) for item in schema]
    if not isinstance(schema, dict):
        return schema
    out = {key: _without_specifications(value) for key, value in schema.items()}
    properties = out.get("properties")
    if isinstance(properties, dict) and {"name", "port", "quantity"} <= set(properties):
        properties.pop("specifications", None)
        out["required"] = [member for member in out["required"] if member != "specifications"]
    return out


def test_r4_g3_every_resolved_response_schema_equals_the_snapshot() -> None:
    measured = {name: _digest(resolved_response(op)) for name, op in OPERATIONS.items()}
    assert len(measured) == 23
    assert measured == {
        **SNAPSHOT_AT_B13D556,
        **SNAPSHOT_AMENDMENT_2,
        **SNAPSHOT_AMENDMENT_3,
        **SNAPSHOT_M02,
        **SNAPSHOT_M04,
        **SNAPSHOT_MSG,
        **SNAPSHOT_MSG_EXPLAIN,
        **SNAPSHOT_X02,
        **SNAPSHOT_OPT,
        **SNAPSHOT_ST,
        **SNAPSHOT_X04,
    }
    assert SNAPSHOT_ST["get_stream_table"] == SNAPSHOT_AT_B13D556["get_artifact"]
    for operation in OPERATIONS.values():
        assert "$ref" not in canonical_json(resolved_response(operation)).decode("utf-8")


def test_x04_without_its_additions_every_response_is_its_pre_x04_snapshot() -> None:
    """R4-G3 for X04 (ADR 0075, R-1010): with X04's additions removed every resolved response is
    its snapshot before X04, and exactly the operations of `SNAPSHOT_X04` moved."""
    before = {
        **SNAPSHOT_AT_B13D556,
        **SNAPSHOT_AMENDMENT_2,
        **SNAPSHOT_AMENDMENT_3,
        **SNAPSHOT_M02,
        **SNAPSHOT_M04,
        **SNAPSHOT_MSG,
        **SNAPSHOT_MSG_EXPLAIN,
        **SNAPSHOT_X02,
        **SNAPSHOT_OPT,
        **SNAPSHOT_ST,
    }
    assert set(before) == set(OPERATIONS)
    moved = []
    for name, operation in OPERATIONS.items():
        resolved = resolved_response(operation)
        assert _digest(without_x04(resolved)) == before[name], name
        if _digest(resolved) != before[name]:
            moved.append(name)
    assert sorted(moved) == sorted(SNAPSHOT_X04)


def test_opt_without_its_additions_every_response_is_its_pre_opt_snapshot() -> None:
    """OPT (ADR 0071): with OPT's additions removed, every operation's resolved response is its
    snapshot before OPT, and exactly the operations of `SNAPSHOT_OPT` moved."""
    before = {
        **SNAPSHOT_AT_B13D556,
        **SNAPSHOT_AMENDMENT_2,
        **SNAPSHOT_AMENDMENT_3,
        **SNAPSHOT_M02,
        **SNAPSHOT_M04,
        **SNAPSHOT_MSG,
        **SNAPSHOT_MSG_EXPLAIN,
        **SNAPSHOT_X02,
    }
    moved = []
    for name, operation in OPERATIONS.items():
        if name in ST_OPERATIONS:  # ST's row (ADR 0068) postdates OPT; its own `SNAPSHOT_ST`
            continue
        # X04's additions (ADR 0075) postdate OPT: they are taken out first.
        resolved = without_x04(resolved_response(operation))
        assert _digest(without_opt(resolved)) == before[name], name
        if _digest(resolved) != before[name]:
            moved.append(name)
    assert sorted(moved) == sorted(SNAPSHOT_OPT)


def test_msg_g10_without_failure_every_response_is_its_pre_msg_snapshot() -> None:
    """MSG-G10: with `RunResult.failure` and MSG's `$defs` removed, every operation's resolved
    response is its snapshot before MSG, and exactly the operations of `SNAPSHOT_MSG` moved; the
    `explain` row (ADR 0058 D7) is the only operation MSG added."""
    before = {
        **SNAPSHOT_AT_B13D556,
        **SNAPSHOT_AMENDMENT_2,
        **SNAPSHOT_AMENDMENT_3,
        **SNAPSHOT_M02,
        **SNAPSHOT_M04,
    }
    # ST's row (ADR 0068) is later than MSG and has its own snapshot (`SNAPSHOT_ST`).
    assert set(OPERATIONS) - set(before) - ST_OPERATIONS == MSG_OPERATIONS
    assert MSG_OPERATIONS == set(SNAPSHOT_MSG_EXPLAIN)
    moved = []
    for name, operation in OPERATIONS.items():
        if name in MSG_OPERATIONS | ST_OPERATIONS:
            continue
        # X02's (ADR 0070) and OPT's (ADR 0071) additions postdate MSG: they are taken out
        # first, the later first.
        resolved = without_x02(without_opt(without_x04(resolved_response(operation))))
        assert _digest(without_msg(resolved)) == before[name], name
        if _digest(resolved) != before[name]:
            moved.append(name)
    assert sorted(moved) == sorted(SNAPSHOT_MSG)


def test_x02_without_warm_start_every_response_is_its_pre_x02_snapshot() -> None:
    """X02 (ADR 0070): with X02's three optional members removed, every operation's resolved
    response is its snapshot before X02 (after MSG), and exactly the operations of `SNAPSHOT_X02`
    moved."""
    before = {
        **SNAPSHOT_AT_B13D556,
        **SNAPSHOT_AMENDMENT_2,
        **SNAPSHOT_AMENDMENT_3,
        **SNAPSHOT_M02,
        **SNAPSHOT_M04,
        **SNAPSHOT_MSG,
        **SNAPSHOT_MSG_EXPLAIN,
    }
    moved = []
    for name, operation in OPERATIONS.items():
        if name in ST_OPERATIONS:  # ST's row (ADR 0068) postdates X02; its own `SNAPSHOT_ST`
            continue
        # OPT's (ADR 0071) and X04's (ADR 0075) additions postdate X02: they are taken out first.
        resolved = without_opt(without_x04(resolved_response(operation)))
        assert _digest(without_x02(resolved)) == before[name], name
        if _digest(resolved) != before[name]:
            moved.append(name)
    assert sorted(moved) == sorted(SNAPSHOT_X02)


def test_g_r6_6_list_models_moved_only_by_the_approved_additive_member() -> None:
    """R4-G3 differs only in `model_registry_view`, and only by `specifications`: with that member
    removed from its pins and options, `list_models`'s resolved schema is the `b13d556`
    snapshot again, and no other `$def` of the file moved."""
    resolved = resolved_response(OPERATIONS["list_models"])
    assert _digest(resolved) != SNAPSHOT_AT_B13D556["list_models"]
    assert _digest(_without_specifications(resolved)) == SNAPSHOT_AT_B13D556["list_models"]
    # M02's additive members are taken out first (G1 (c)); they are M02's, not Amendment 2's.
    moved = [
        name
        for name in SNAPSHOT_AT_B13D556
        if _digest(
            without_m02(
                without_m04(
                    without_msg(
                        without_x02(without_opt(without_x04(resolved_response(OPERATIONS[name]))))
                    )
                )
            )
        )
        != SNAPSHOT_AT_B13D556[name]
    ]
    # `list_audit` is ADR 0019 Amendment 3's row, `explain` ADR 0058 D7's, `get_stream_table`
    # ADR 0068's.
    assert sorted(set(OPERATIONS) - set(SNAPSHOT_AT_B13D556)) == [
        "explain",
        "get_stream_table",
        "list_audit",
    ]
    # ADR 0019 Amendment 3 (A3.2) moves `diff_revisions` too; its own test below.
    assert moved == ["list_models", "diff_revisions"]


def test_g5_diff_revisions_moved_only_by_the_approved_additive_member() -> None:
    """ADR 0019 Amendment 3, A3.2: with `elements` removed from `semantic_diff`'s properties and
    `required`, `diff_revisions`'s resolved schema is the `b13d556` snapshot again."""
    resolved = resolved_response(OPERATIONS["diff_revisions"])
    assert _digest(resolved) == SNAPSHOT_AMENDMENT_3["diff_revisions"]
    assert resolved["required"] == ["added", "changed", "elements", "removed"]
    without = {
        **resolved,
        "required": [member for member in resolved["required"] if member != "elements"],
        "properties": {
            key: value for key, value in resolved["properties"].items() if key != "elements"
        },
    }
    assert _digest(without) == SNAPSHOT_AT_B13D556["diff_revisions"]


def test_g_r6_6_every_pin_lists_its_pin_encodings() -> None:
    """The response validates against the amended schema, and each pin's and each option's
    `specifications` is its `pin_encodings`."""
    from openflowsheet.application.local import LocalApplication
    from openflowsheet.application.revision_binding import MODEL_SIGNATURES, pin_encodings

    with tempfile.TemporaryDirectory() as scratch:
        with LocalApplication.create(Path(scratch) / "p", project_id="g-r6-6") as application:
            view = application.list_models().as_document()
    assert schema_errors(f"{SCHEMA}#/$defs/model_registry_view", view) == []
    checked = {"syn001.": 0, "c1.": 0}
    for model in view["models"]:
        if model["model_id"].startswith("thermal."):
            # S11 I1b (the C6-2 precedent): the `thermal.*` entries are checked by
            # `test_s11_thermal_binding`, so this test's base keys stand.
            continue
        signature = MODEL_SIGNATURES[model["model_id"]]
        options = [o for c in signature.choices for o in c.options]
        listed = [*model["pins"], *(o for c in model["choices"] for o in c["options"])]
        for entry, pin in zip(listed, (*signature.pins, *options), strict=True):
            assert entry["name"] == pin.name
            expected = [e.as_document() for e in pin_encodings(signature, pin)]
            assert entry["specifications"] == expected
            checked[model["model_id"].split(".", 1)[0] + "."] += 1
    # SYN-001's 16 as before; M02's join (R-280) adds the C1 feed's 3, heater's 1, flash's 4.
    assert checked == {"syn001.": 16, "c1.": 8}


def test_the_schema_is_draft_2020_12_with_an_id_and_a_description() -> None:
    document = load_json(SCHEMA_DIR / SCHEMA)
    Draft202012Validator.check_schema(document)
    assert document["$id"] == SCHEMA_BASE + SCHEMA
    assert len(document["description"]) > 80


def test_one_def_per_unpublished_shape_and_each_operation_refs_it() -> None:
    assert set(load_json(SCHEMA_DIR / SCHEMA)["$defs"]) == DEFS
    for name, operation in OPERATIONS.items():
        expected = DEF_OF_OPERATION.get(name)
        if expected is not None:
            assert operation.response_schema == {
                "$ref": f"{SCHEMA_BASE}{SCHEMA}#/$defs/{expected}"
            }, name
        elif operation.response_schema is not None:
            # Every other response is a published schema of its own, referenced whole.
            (reference,) = operation.response_schema.values()
            assert list(operation.response_schema) == ["$ref"], name
            assert SCHEMA not in reference, name


def _valid(name: str) -> list[Path]:
    return sorted((FIXTURES / name / "valid").glob("*.json"))


def _invalid(name: str) -> list[Path]:
    return sorted((FIXTURES / name / "invalid").glob("*.json"))


@pytest.mark.parametrize("name", sorted(DEFS))
def test_r4_g3_every_def_has_a_valid_and_an_invalid_fixture(name: str) -> None:
    reference = f"{SCHEMA}#/$defs/{name}"
    assert _valid(name) and _invalid(name), name
    for path in _valid(name):
        assert schema_errors(reference, load_json(path)) == [], path
    for path in _invalid(name):
        fixture = load_json(path)
        assert set(fixture) == {"expect_error", "document"}, path
        errors = schema_errors(reference, fixture["document"])
        assert any(fixture["expect_error"] in error for error in errors), (path, errors)


def test_the_fixtures_are_what_real_responses_emit_today() -> None:
    """R-015: regenerated from real responses, the fixtures are equal with the members that differ
    between generations masked (timestamps, output digests and sizes, the git commit)."""
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    from t07_schema_fixtures import application_results_documents, stable

    emitted = application_results_documents()
    committed = sorted(str(path.relative_to(FIXTURES.parent)) for path in FIXTURES.rglob("*.json"))
    assert sorted(emitted) == committed
    for name, document in emitted.items():
        assert stable(document) == stable(load_json(FIXTURES.parent / name)), name


# ----------------------------------------------------------------------------------- R4-G4


def test_r4_g4_the_frozen_list_and_the_adr_carry_the_schema() -> None:
    frozen = (REPO_ROOT / "docs" / "interfaces-frozen.md").read_text("utf-8")
    section = frozen.split("## 2.", 1)[1].split("## 3.", 1)[0]
    assert f"schemas/{SCHEMA}" in section
    adr = (REPO_ROOT / "docs" / "adr" / "0019-application-contract-v1.md").read_text("utf-8")
    assert "## Amendment 1" in adr and SCHEMA in adr
