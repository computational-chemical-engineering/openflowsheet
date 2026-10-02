"""ADR 0002 Amendment 1: an integer is canonical exactly when its digits are a binary64's canonical
spelling (assertions J10–J17; T07 W5g).

Normative text: `docs/adr/0002-canonicalization-and-schemas.md`, "Amendment 1" (A1.2 the rule,
A1.8 the assertions). **Every expectation is read from the reference**,
`docs/derivations/scripts/adr0002_a1_reference.json`, which its generator decides by exact
integer arithmetic on D3.3's definition and which imports nothing from `openflowsheet` — or is
a byte string, a verdict or a binary64 the ADR registers. None is derived from the code under
test. Every comparison is exact: a verdict, a byte string, or a binary64 bit for bit
(`struct.pack(">d", x)`).

- **J10** the rule on the 22 registered integers (`canonical_json`, `integer_binary64`,
  `units.read_number`, `first_noncanonical`);
- **J11** nothing changes at or below 2⁵³ (the reference's 100 000 draws);
- **J12** closure: `canonical_json(json.loads(canonical_json(d))) == canonical_json(d)` for the
  98 221 integral doubles of the reference's sampling law, J1's and J2's vectors and the witness;
- **J13** `json.loads`, the MCP SDK's parser, YAML and `load_document` give one verdict;
- **J14** the entry points refuse typed, and in-process, HTTP and MCP agree;
- **J15** `get_artifact` serves a canonical file holding such an integer as JSON, on the four
  transports, and V17's T08 certificate as JSON (G16-b itself is `test_t07_v17_reference.py`);
- **J16** nothing registered moves: the standing part (see its docstring for the one-off part);
- **J17** one rule: a text scan for a second copy of it, or a reader-side number hook.

The HTTP and MCP parts need the `server` extra and skip without it.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
import shutil
import struct
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import yaml
from conftest import REPO_ROOT
from t07_corpus import CORPUS
from t07_mcp_support import call, direct_call, in_session, project_with_grant
from test_t07_injection import client_for

from benchmarks.t07.v17 import reference
from openflowsheet.application.authz import grant
from openflowsheet.application.local import LocalApplication
from openflowsheet.application.operations import dispatch
from openflowsheet.application.types import Change, Edit, schema_errors
from openflowsheet.canonical import (
    CanonicalizationError,
    canonical_json,
    document_sha256,
    first_noncanonical,
    integer_binary64,
    load_document,
)
from openflowsheet.units import read_number

REFERENCE_PATH = REPO_ROOT / "docs" / "derivations" / "scripts" / "adr0002_a1_reference.json"
#: A1's registered digest of the reference: a test reads the reference the ADR registers.
REFERENCE_SHA256 = "c76bf9512be632bc33fae9d6d4b2e64c089d2fc29aab4a0ef049ff1dade8da95"
REFERENCE: dict[str, Any] = json.loads(REFERENCE_PATH.read_bytes())
ROWS: list[dict[str, Any]] = REFERENCE["integers"]
ROW = {row["id"]: row for row in ROWS}
REFUSAL = "is not the canonical spelling of a binary64"
BOUNDARY = 2**53
NOMINAL = "SYN-001-nominal"

#: J1's registered binary64 values (ADR 0002 D3.3, the J1 table's IEEE-754 hex column).
J1_HEX = (
    "0000000000000000",
    "8000000000000000",
    "0000000000000001",
    "7fefffffffffffff",
    "ffefffffffffffff",
    "3ff0000000000000",
    "c000000000000000",
    "3fb999999999999a",
    "3fd3333333333334",
    "3fe0000000000000",
    "4076800000000000",
    "40f86a0000000000",
    "4020a1013e8990be",
    "4341c37937e08000",
    "4340000000000000",
    "4415af1d78b58c40",
    "444b1ae4d6e2ef4f",
    "444b1ae4d6e2ef50",
    "4430000000000000",
    "44b52d02c7e14af7",
    "3ee4f8b588e368f1",
    "3eb0c6f7a0b5ed8d",
    "3eb0c6f7a0b5ed8c",
    "3e7ad7f29abcaf48",
    "3e8421f5f40d8376",
    "41b3de4355555554",
)
#: J2's list and its registered bytes.
J2_LIST = [1, 1.0, 2**53, -(2**53), 2.0**60]
J2_BYTES = b"[1,1,9007199254740992,-9007199254740992,1152921504606847000]"
#: J12's witness: V17 T08's certificate member, as W7c measured it.
WITNESS = {
    "regularity": {"inverse_one_norm_estimate": 5.92612204108959e17},
    "verification_status": "VERIFIED",
}

pytestmark = pytest.mark.filterwarnings(
    "ignore:Using `httpx` with `starlette.testclient` is deprecated"
)


def bits(value: float) -> str:
    return struct.pack(">d", value).hex()


def admitted(row: dict[str, Any]) -> bool:
    assert row["verdict"] in ("admitted", "refused"), row
    return bool(row["verdict"] == "admitted")


def _server_extra() -> None:
    for name in ("mcp", "starlette", "httpx"):
        pytest.importorskip(name)


def test_the_reference_is_the_registered_one() -> None:
    """A1: the reference's sha256, and C1's 22 rows, as the ADR registers them."""
    assert hashlib.sha256(REFERENCE_PATH.read_bytes()).hexdigest() == REFERENCE_SHA256
    assert REFERENCE["schema"] == "adr0002-a1-reference-v1"
    assert [row["id"] for row in ROWS] == [f"I{index:02d}" for index in range(1, 23)]


# ============================================================================== J10: the rule


@pytest.mark.parametrize("row", ROWS, ids=[row["id"] for row in ROWS])
def test_j10_the_rule_on_the_registered_integers(row: dict[str, Any]) -> None:
    n = int(row["n"])
    if admitted(row):
        # (a) written as its own digits; read as the registered binary64, bit for bit.
        assert canonical_json(n) == row["n"].encode()
        reading = integer_binary64(n)
        assert isinstance(reading, float) and bits(reading) == row["binary64"]
        number = read_number(n)
        assert isinstance(number, float) and bits(number) == row["binary64"]
        if abs(n) > BOUNDARY:
            # The `int` and its binary64 are one JSON number.
            assert canonical_json(reading) == row["n"].encode()
    else:
        # (b) refused typed, never rounded; read as the infinity of its sign (T06 A100 (a)).
        with pytest.raises(CanonicalizationError, match=REFUSAL) as refused:
            canonical_json(n)
        assert "ADR 0002 D3.3" in str(refused.value)
        if abs(n) >= 10**21:  # A1.2: never formatted (CPython's 4300-digit limit)
            assert row["n"].lstrip("-") not in str(refused.value)
            assert "10^21 or more" in str(refused.value)
        assert integer_binary64(n) is None
        assert read_number(n) == (math.inf if n > 0 else -math.inf)
    # (c) the pointer, and no other exception on any row.
    assert first_noncanonical({"v": [0, n]}) == (None if admitted(row) else "/v/1")


def test_j10_a_boolean_is_not_an_integer() -> None:
    """A1.2: `integer_binary64` refuses a `bool`; the writer still spells it `true`."""
    with pytest.raises(TypeError):
        integer_binary64(True)
    assert canonical_json(True) == b"true"


# ================================================================ J11: unchanged at and below 2⁵³


def test_j11_unchanged_at_and_below_2_to_the_53() -> None:
    sample = REFERENCE["samples"]["j11"]
    assert sample["law"] == "random.Random(seed).randint(-2**53, 2**53), count draws"
    rng = random.Random(sample["seed"])
    draws = [rng.randint(-BOUNDARY, BOUNDARY) for _ in range(sample["count"])]
    fixed = [0, 1, -1, BOUNDARY - 1, -(BOUNDARY - 1), BOUNDARY, -BOUNDARY]
    for n in fixed + draws:
        assert canonical_json(n) == str(n).encode(), n
        reading = integer_binary64(n)
        assert reading == float(n) and bits(reading) == bits(float(n)), n


# ============================================================================== J12: closure


def _j12_draws() -> list[float]:
    sample = REFERENCE["samples"]["j12"]
    assert sample["law"] == (
        "rng = random.Random(seed); per draw: e = rng.randint(53, 69); "
        "m = rng.getrandbits(52) | 2**52; s = rng.choice((1, -1)); "
        "f = s * math.ldexp(m, e - 52); kept iff abs(f) < 1e21 (the integral band)"
    )
    rng = random.Random(sample["seed"])
    kept = []
    for _ in range(sample["count"]):
        e = rng.randint(53, 69)
        m = rng.getrandbits(52) | 2**52
        s = rng.choice((1, -1))
        f = s * math.ldexp(m, e - 52)
        if abs(f) < 1e21:
            kept.append(f)
    return kept


def _leaves(document: Any) -> Iterator[Any]:
    if isinstance(document, dict):
        for key in sorted(document):
            yield from _leaves(document[key])
    elif isinstance(document, list):
        for item in document:
            yield from _leaves(item)
    elif isinstance(document, int | float) and not isinstance(document, bool):
        yield document


def _closes(document: Any) -> None:
    """One J12 document: `b`, `r = json.loads(b)`; `r` canonical, re-spelled `b`, and every
    numeric leaf the original binary64 (-0.0 read as +0.0, ADR 0001 D1.5)."""
    written = canonical_json(document)
    read = json.loads(written)
    assert first_noncanonical(read) is None, written
    assert canonical_json(read) == written
    originals, readings = list(_leaves(document)), list(_leaves(read))
    assert len(originals) == len(readings)
    for original, reading in zip(originals, readings, strict=True):
        assert bits(float(reading)) == bits(float(original) + 0.0), (original, reading)


def test_j12_what_the_writer_writes_the_reader_admits() -> None:
    draws = _j12_draws()
    assert len(draws) == 98_221  # A1.8: 98 221 of 100 000 draws kept
    for f in draws:
        _closes({"v": [f]})
    for hex_ in J1_HEX:
        _closes(struct.unpack(">d", bytes.fromhex(hex_))[0])
    assert canonical_json(J2_LIST) == J2_BYTES
    _closes(J2_LIST)
    _closes(WITNESS)


# ================================================================ J13: every parser agrees


@pytest.mark.parametrize("row", ROWS, ids=[row["id"] for row in ROWS])
def test_j13_every_parser_in_use_gives_the_same_verdict(row: dict[str, Any]) -> None:
    pydantic_core = pytest.importorskip("pydantic_core")
    text, n = row["n"], int(row["n"])
    parsed = {
        "json.loads": json.loads(text),
        "pydantic_core.from_json": pydantic_core.from_json(text),
        "yaml.safe_load": yaml.safe_load(text),
        "load_document": load_document("[" + text + "]")[0],  # type: ignore[index]
    }
    for parser, value in parsed.items():
        assert type(value) is int and value == n, parser
        assert first_noncanonical(value) == (None if admitted(row) else ""), parser


# ====================================================== J14: typed at every entry, and agreed


@pytest.fixture
def app(tmp_path: Path) -> Iterator[LocalApplication]:
    """`test_t07_transactions.py`'s seed: a project at `rev-000001`."""
    application = LocalApplication.create(tmp_path / "p")
    first = application.commit_change(
        Change(edits=(Edit("set", ("settings",), {"mode": "steady"}),)), None, "seed"
    )
    assert first.status == "committed" and first.revision_id == "rev-000001"
    yield application
    application.close()


def _stored(application: LocalApplication, revision_id: str) -> tuple[bytes, str]:
    """The stored revision's canonical bytes, and its recorded `content_sha256`."""
    store = application.store
    with store.reading() as connection:
        revision = store.get_revision(connection, revision_id)
        (recorded,) = connection.execute(
            "SELECT content_sha256 FROM revisions WHERE revision_id = ?", (revision_id,)
        ).fetchone()
    assert revision is not None
    return canonical_json(revision.document), str(recorded)


@pytest.mark.parametrize(
    ("value", "spelling"),
    [
        (5.92612204108959e17, ROW["I08"]["n"]),
        (2.0**54, ROW["I05"]["n"]),
        (int(ROW["I08"]["n"]), ROW["I08"]["n"]),
        (int(ROW["I04"]["n"]), ROW["I04"]["n"]),
    ],
    ids=["float-witness", "float-2^54", "int-witness", "int-2^53+2"],
)
def test_j14a_such_a_value_commits(app: LocalApplication, value: Any, spelling: str) -> None:
    """At `afcc327` the two floats raised an untyped `CanonicalizationError` (A1.1)."""
    result = app.commit_change(
        Change(edits=(Edit("set", ("settings", "x"), value),)), "rev-000001", "k"
    )
    assert result.status == "committed", result
    assert result.revision_id is not None
    written, stored_sha256 = _stored(app, result.revision_id)
    assert b'"x":' + spelling.encode() in written
    assert stored_sha256 == hashlib.sha256(written).hexdigest()


@pytest.mark.parametrize(
    "value",
    [2**55, 2**64 - 1, 2**53 + 1, 10**5000],
    ids=["2^55", "2^64-1", "2^53+1", "10^5000"],
)
def test_j14b_any_other_integer_is_rejected_typed(app: LocalApplication, value: int) -> None:
    """At `afcc327`, `10**5000` raised `ValueError` from formatting the refusal message."""
    result = app.commit_change(
        Change(edits=(Edit("set", ("settings", "x"), value),)), "rev-000001", "k"
    )
    assert result.status == "rejected"
    assert result.error is not None and result.error.code == "document_not_canonical"
    assert result.error.detail == {"pointer": "/edits/0/value"}


def _commit_text(value: bytes, key: str, expected: str | None) -> bytes:
    """A `commit_change` body whose edit value is the JSON text `value`."""
    expected_text = b"null" if expected is None else json.dumps(expected).encode()
    return (
        b'{"edits":[{"operation":"set","path":["x"],"value":' + value + b"}],"
        b'"expected_revision":' + expected_text + b',"idempotency_key":"' + key.encode() + b'"}'
    )


#: J14 (c): the canonical spelling I07 is admitted, its binary64's exact value I06 is refused.
J14C_BODIES = (
    _commit_text(ROW["I07"]["n"].encode(), "j14-admitted", None),
    _commit_text(ROW["I06"]["n"].encode(), "j14-refused", "rev-000001"),
)


def _timeless(document: Any) -> Any:
    """A validation report's `provenance.timestamp` is the one clock reading here."""
    if isinstance(document, dict):
        return {k: _timeless(v) for k, v in document.items() if k != "timestamp"}
    if isinstance(document, list | tuple):
        return [_timeless(item) for item in document]
    return document


def test_j14c_the_transports_agree_on_the_text(tmp_path: Path) -> None:
    """The JSON text `36028797018963970` is committed and `36028797018963968` refused
    `document_not_canonical` at `/edits/0/value`, identically in-process, over HTTP and over
    MCP (stdio, so the SDK's own parser reads the text)."""
    _server_extra()
    from starlette.testclient import TestClient

    from openflowsheet.application.bindings.http import create_app

    outcomes: dict[str, list[tuple[bool, Any]]] = {}

    capability, _ = project_with_grant(tmp_path / "direct", ("draft", "read"))
    with LocalApplication.open(tmp_path / "direct", capability=capability) as view:
        outcomes["python"] = [
            direct_call(view, "commit_change", json.loads(body)) for body in J14C_BODIES
        ]

    _, token_file = project_with_grant(tmp_path / "http", ("draft", "read"))
    token = token_file.read_text(encoding="utf-8").strip()
    with LocalApplication.open(tmp_path / "http") as owner:
        client = TestClient(create_app(owner), raise_server_exceptions=False)
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        responses = [
            client.post("/v1/changes", content=body, headers=headers) for body in J14C_BODIES
        ]
        client.close()
    outcomes["http"] = [(r.status_code != 200, r.json()) for r in responses]
    assert [r.status_code for r in responses] == [200, 422]

    _, token_file = project_with_grant(tmp_path / "mcp", ("draft", "read"))

    async def body(session: Any) -> list[tuple[bool, Any]]:
        return [await call(session, "commit_change", json.loads(text)) for text in J14C_BODIES]

    outcomes["mcp"] = in_session(tmp_path / "mcp", token_file, tmp_path / "mcp.log", body)

    (committed, committed_doc), (refused, refused_doc) = outcomes["python"]
    assert not committed and committed_doc["status"] == "committed", committed_doc
    assert refused and refused_doc["code"] == "document_not_canonical", refused_doc
    assert refused_doc["detail"] == {"pointer": "/edits/0/value"}
    for transport in ("http", "mcp"):
        assert _timeless(outcomes[transport]) == _timeless(outcomes["python"]), transport
    with LocalApplication.open(tmp_path / "mcp") as owner:
        written, _ = _stored(owner, committed_doc["revision_id"])
    assert b'"x":' + ROW["I07"]["n"].encode() in written


def test_j14d_an_integer_text_past_the_parsers_limit_is_invalid_request(tmp_path: Path) -> None:
    """A 4301-digit integer: CPython's parser raises a plain `ValueError`, which is refused
    422 `invalid_request`, never `internal_error` (A1.7 item 5)."""
    _server_extra()
    from starlette.testclient import TestClient

    from openflowsheet.application.bindings.http import create_app

    _, token_file = project_with_grant(tmp_path / "http", ("draft", "read"))
    token = token_file.read_text(encoding="utf-8").strip()
    with LocalApplication.open(tmp_path / "http") as owner:
        client = TestClient(create_app(owner), raise_server_exceptions=False)
        response = client.post(
            "/v1/changes",
            content=_commit_text(b"1" * 4301, "j14-long", None),
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        )
        client.close()
        with owner.store.reading() as connection:
            head = owner.store.head(connection)
    assert response.status_code == 422, response.text
    assert response.json()["code"] == "invalid_request"
    assert response.json()["detail"]["pointer"] == ""
    assert schema_errors("api-error.schema.json", response.json()) == []
    assert head is None


# ========================================================= J15: get_artifact serves it as JSON


def _witness_project(root: Path) -> tuple[Path, str, dict[str, tuple[Any, str]]]:
    """A project holding an imported bundle whose certificate member's bytes are
    `canonical_json(WITNESS)`, and a reading grant; `(project, the member's id, grants)`."""
    project = root / "project"
    with LocalApplication.create(project, project_id="a1-j15") as owner:
        edits = [
            {"operation": "set", "path": [key], "value": value}
            for key, value in CORPUS[NOMINAL]().items()
        ]
        revision = dispatch(
            owner,
            "commit_change",
            {"edits": edits, "expected_revision": None, "idempotency_key": "a"},
        )["revision_id"]
        request = {"operation": "solve", "idempotency_key": "s", "body": {"revision_id": revision}}
        job = dispatch(owner, "submit_job", request)["job"]["job_id"]
        while not dispatch(owner, "wait_job", {"job_id": job, "timeout_s": 30})["ended"]:
            pass
        outside = root / "bundle"
        shutil.copytree(project / "jobs" / job / "bundle", outside)
        (outside / "artifacts" / "solution-certificate.json").write_bytes(canonical_json(WITNESS))
        dispatch(owner, "reproduce", {"bundle_path": str(outside), "policy": {"rerun": False}})
    reader = grant(project, principal_id="agent-reader", rights=("read",), capability_id="cap-r")
    return project, "import-000001:bundle/solution-certificate.json", {"reader": reader}


@pytest.mark.parametrize("transport", ["python", "cli", "http", "mcp"])
def test_j15_a_canonical_file_is_served_as_json(tmp_path: Path, transport: str) -> None:
    """At `afcc327` the file was served as text lines: `592612204108959000` was refused."""
    if transport in ("http", "mcp"):
        _server_extra()
    project, member, grants = _witness_project(tmp_path)
    with client_for(transport, project, grants["reader"], tmp_path) as client:
        error, served = client.call("get_artifact", {"artifact_id": member})
    assert not error, served
    value = served["value"]
    assert isinstance(value, dict), value
    assert canonical_json(value) == canonical_json(WITNESS)
    estimate = value["regularity"]["inverse_one_norm_estimate"]
    assert bits(float(estimate)) == ROW["I08"]["binary64"]


def test_j15_v17_t08_certificate_is_served_as_json(tmp_path: Path) -> None:
    """V17 T08's reference run (python) scores clean, and its certificate — which holds an
    integer beyond 2⁵³ that spells a binary64 (W7c) — is served as JSON, not as lines. G16-b's
    40 runs are `test_t07_v17_reference.py`."""
    record = reference.run("V17-T08", "python", tmp_path)
    assert reference.clean(reference.verdict(record)), reference.verdict(record)
    (solve,) = record.session.solves
    with LocalApplication.open(tmp_path / "project") as owner:
        job = dispatch(owner, "get_job", {"job_id": solve.job_id})
        (bundle,) = reference.outputs(job, "replay_bundle")
        served = dispatch(
            owner, "get_artifact", {"artifact_id": f"{bundle}/solution-certificate.json"}
        )["value"]
    assert isinstance(served, dict), served[:3]
    estimate = served["regularity"]["inverse_one_norm_estimate"]
    assert type(estimate) is int and abs(estimate) > BOUNDARY, estimate
    assert integer_binary64(estimate) is not None and first_noncanonical(served) is None


# ================================================================ J16: nothing registered moves


def _fixture_documents() -> Iterator[tuple[Path, Any]]:
    for path in sorted((REPO_ROOT / "tests" / "fixtures").rglob("*")):
        if path.suffix not in (".json", ".yaml"):
            continue
        try:
            document = load_document(path.read_text(encoding="utf-8"), source=str(path))
        except (CanonicalizationError, yaml.YAMLError):
            continue  # a fixture that registers a refusal (J6's duplicate key, …)
        yield path, document


def test_j16_the_fixtures_hold_no_number_the_amendment_changes() -> None:
    """The standing part of J16. The amendment changes one branch: integers with |n| > 2⁵³,
    which were all refused (J11 pins that the float and |n| ≤ 2⁵³ branches are untouched). A
    canonical fixture with no such integer therefore has the same canonical bytes and digest
    before and after, and closes (J12). The rest of J16 — R4-G1's identity protocol, the V17
    exporter's byte identity without `_number`, and the scan of every git-tracked document — is
    run once at the amendment's commit and recorded, not kept as a standing test (A1.8)."""
    checked = 0
    for path, document in _fixture_documents():
        if first_noncanonical(document) is not None:
            continue  # a fixture that registers a non-canonical value
        integers = [
            leaf for leaf in _leaves(document) if isinstance(leaf, int) and abs(leaf) > BOUNDARY
        ]
        assert integers == [], path
        written = canonical_json(document)
        assert canonical_json(json.loads(written)) == written, path
        assert document_sha256(json.loads(written)) == hashlib.sha256(written).hexdigest()
        checked += 1
    assert checked >= 80, checked


# ================================================================================ J17: one rule


SCANNED = (REPO_ROOT / "src" / "openflowsheet", REPO_ROOT / "benchmarks" / "t07")
EXEMPT = REPO_ROOT / "src" / "openflowsheet" / "canonical.py"
MARKERS = ("_MAX_EXACT_INTEGER", "2**53", "2 ** 53", "1 << 53", "parse_int=")


def _second_copies(roots: tuple[Path, ...], exempt: Path) -> list[tuple[str, str]]:
    found = []
    for root in roots:
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path == exempt or "__pycache__" in path.parts:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            found += [(str(path), marker) for marker in MARKERS if marker in text]
    return found


def test_j17_the_rule_has_one_implementation() -> None:
    """No file under `src/openflowsheet/` but `canonical.py`, and none under
    `benchmarks/t07/`, holds the bound or a reader-side number hook (docstrings write 2⁵³)."""
    assert all(root.is_dir() for root in SCANNED)
    assert _second_copies(SCANNED, EXEMPT) == []


def test_j17_the_scan_would_catch_a_second_copy(tmp_path: Path) -> None:
    for marker in MARKERS:
        planted = tmp_path / marker.replace("*", "s").replace("<", "l").replace(" ", "_")
        planted.mkdir()
        (planted / "reader.py").write_text(f"x = {marker!r}\n", encoding="utf-8")
        assert _second_copies((planted,), EXEMPT) == [(str(planted / "reader.py"), marker)]
