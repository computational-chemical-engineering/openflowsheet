"""MSG WO-2: every emitted code has a catalogue entry (design note §3.2; gates MSG-G1, G2, G5).

- **G1**, the closed vocabularies: `ApiErrorCode`, the solve outcomes, the verification,
  regularity and validation statuses, the job statuses and ending reasons, `validation.py`'s
  check ids and the support matrix's limitation ids — each member has an entry;
- **G2**, the static scan (`scripts/msg_catalogue.py scan`): every code literal at an emission
  site has an entry or an allow-list reason;
- `released-codes.txt` ⊆ the catalogue's keys (codes are never removed or renamed);
- **G5**'s half here: `limitations.yaml` is what `sync-limitations` writes from the matrix.

G3, the runtime audit over the whole suite, is `tests/conftest.py`'s plugin; G4 (lint) is
`tests/test_msg_engine.py`'s.
"""

from __future__ import annotations

import sys

import yaml
from conftest import REPO_ROOT, TERMINAL_REPORT

sys.path.insert(0, str(REPO_ROOT / "scripts"))
import msg_catalogue  # noqa: E402

from openflowsheet.messages import audit  # noqa: E402
from openflowsheet.messages.catalogue import CATALOGUE  # noqa: E402
from openflowsheet.messages.lint import review_count  # noqa: E402


def test_g1_every_closed_vocabulary_member_has_an_entry() -> None:
    vocabularies = msg_catalogue.vocabularies()
    assert all(vocabularies.values()), "an empty vocabulary means its source moved"
    assert msg_catalogue.vocabulary_misses(CATALOGUE.keys()) == {}
    for family, members in vocabularies.items():
        if family in ("outcome", "check", "limitation", "job", "api_error"):
            assert {CATALOGUE.entry(code).family for code in members} == {family}  # type: ignore[union-attr]


def test_g2_every_scanned_code_has_an_entry_or_a_reason() -> None:
    assert msg_catalogue.scan_misses(CATALOGUE.keys()) == {}
    allowed = msg_catalogue.scan_allow()
    assert all(reason.strip() for reason in allowed.values())
    assert not set(allowed) & set(CATALOGUE.keys()), "an allowed token that has an entry"
    found = msg_catalogue.scan()
    assert set(allowed) <= set(found), "an allow-list line the scan no longer finds"


def test_g2_the_scanner_finds_each_kind_of_site() -> None:
    source = """
api_error("not_found", "x")
self._refuse("invalid_request", "x")
Failure("unsupported", "kernel_code_here", "x")
RunUnsupportedError("run_code_here")
StoreError("m", code="store_code_here")
MY_CODES = frozenset({"listed_code_here"})
ThingCode = Literal["literal_code_here"]
message = f"head_code_here({unit}): {inner}"
other = "plain_code_here(T)"
"""
    found = {code for code, _ in msg_catalogue.scan_source(source)}
    assert found == {
        "not_found", "invalid_request", "kernel_code_here", "run_code_here", "store_code_here",
        "listed_code_here", "literal_code_here", "head_code_here", "plain_code_here",
    }  # fmt: skip


def test_released_codes_are_never_removed() -> None:
    released = msg_catalogue.released_codes()
    assert released, "released-codes.txt is written by `msg_catalogue.py freeze`"
    assert set(released) <= set(CATALOGUE.keys())


def test_g5_limitations_are_in_sync_with_the_matrix() -> None:
    text = msg_catalogue.LIMITATIONS.read_text(encoding="utf-8")
    current = yaml.safe_load(text)
    assert text == msg_catalogue.limitations_text(msg_catalogue.synced_limitations(current))


def test_the_review_count_is_reported() -> None:
    entries = CATALOGUE.entries()
    complete = sum(1 for entry in entries if entry.complete)
    TERMINAL_REPORT.append(
        f"MSG catalogue: {len(entries)} entries, {complete} complete, {len(entries) - complete} "
        f"stubs, review: true on {review_count()}"
    )
    assert review_count() >= 0


def test_the_audit_is_on_under_the_suite_and_ignores_test_made_codes() -> None:
    assert audit.auditor is not None
    before = dict(audit.auditor.misses)
    audit.observe("no_such_code_for_the_audit(X)", __name__)
    assert audit.auditor.misses == before
    probe = audit.Auditor()
    probe.observe("initializer_failed(T): no_such_code_for_the_audit(S4)", "openflowsheet.x")
    assert probe.misses == {"no_such_code_for_the_audit": "openflowsheet.x"}
