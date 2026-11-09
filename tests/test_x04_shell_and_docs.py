"""X04 WO-5 (`docs/derivations/X04-test-specification.md` §5 W): the limitations (A37), the web
shell's freedom from conversion arithmetic (A39) and the display-units guide (A40). The web shell's
units control and its two screens (A38) are tested in `tests/web/x04-units.test.mjs` (Node) and
`tests/test_m06_browser_smoke.py::test_x04_a38_with_eng_a_stream_s_t_is_the_server_s_display_value`
(browser)."""

from __future__ import annotations

import json
import re
from fractions import Fraction
from typing import Any

import pytest
import yaml
from conftest import REPO_ROOT

from openflowsheet.application import cli
from openflowsheet.messages.render import entry_document

ENVELOPE = REPO_ROOT / "benchmarks" / "t08" / "support_envelope.yaml"
LIMITATIONS = REPO_ROOT / "src" / "openflowsheet" / "messages" / "catalogue" / "limitations.yaml"
WEB_JS = REPO_ROOT / "apps" / "web" / "js"
GUIDE = REPO_ROOT / "docs-site" / "guide" / "display-units.md"
REFERENCE: dict[str, Any] = json.loads(
    (REPO_ROOT / "docs" / "derivations" / "scripts" / "x04_reference.json").read_text("utf-8")
)

# -- A37. Limitations ------------------------------------------------------------------------------

#: A37: each limitation's evidence names these tests (spec §5 A37), besides its ADR section.
EVIDENCE = {
    "L-X04-1": {
        "tests/test_x04_display_core.py::test_a6_preference_grammar[PU20]",
        "tests/test_t05_w11_cases.py::test_a_value_outside_its_si_unit_is_refused[barg-pin]",
    },
    "L-X04-2": {
        "tests/test_x04_stream_table.py::test_a21_without_a_preference_the_document_is_sts",
        "tests/test_x04_stream_table.py::test_a23_the_jobs_exercise_arrays_absences_and_every_object",
    },
    "L-X04-3": {
        "tests/test_x04_messages.py::test_a18_no_kind_no_conversion",
        "tests/test_x04_stream_table.py::test_a23_the_jobs_exercise_arrays_absences_and_every_object",
    },
}


def test_a37_the_limitations_are_envelope_rows_with_their_evidence_and_are_synced() -> None:
    envelope = yaml.safe_load(ENVELOPE.read_text(encoding="utf-8"))
    rows = {row["id"]: row for row in envelope["limitations"] if row["id"].startswith("L-X04-")}
    assert sorted(rows) == sorted(EVIDENCE)
    for code, tests in EVIDENCE.items():
        assert tests <= set(rows[code]["evidence"]), code
        assert any(item.startswith("doc:docs/adr/0075-") for item in rows[code]["evidence"])
    synced = yaml.safe_load(LIMITATIONS.read_text(encoding="utf-8"))
    entries = {entry["code"]: entry for entry in synced["entries"]}
    for code, row in rows.items():
        assert entries[code]["family"] == "limitation"
        assert entries[code]["summary"] == " ".join(row["text"].split())


def test_a37_explain_l_x04_1_works(capsys: pytest.CaptureFixture[str]) -> None:
    document = entry_document("L-X04-1")
    assert document is not None and document["code"] == "L-X04-1"
    assert "Gauge pressures are not accepted as inputs" in document["summary"]
    assert cli.main(["explain", "L-X04-1"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("L-X04-1: ")
    assert "Gauge pressures are not accepted as inputs" in out


# -- A39. The web shell never converts ------------------------------------------------------------

#: A39's conversion constants: none may appear in the shell's code (outside comments).
CONSTANTS = tuple(
    Fraction(text)
    for text in ("273.15", "459.67", "5463", "45967", "3600", "101325", "0.45359237", "9.80665")
)
_STRING_OR_COMMENT = re.compile(
    r"(\"(?:\\.|[^\"\\\n])*\"|'(?:\\.|[^'\\\n])*'|`(?:\\.|[^`\\])*`)|(//[^\n]*|/\*.*?\*/)", re.S
)
_NUMBER = re.compile(r"(?<![\w.$])(\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)(?![\w.])")


def _code(text: str) -> str:
    """`text` without its comments; strings are kept (a constant in a string is code too)."""
    return _STRING_OR_COMMENT.sub(lambda m: m.group(1) or " ", text)


def test_a39_the_comment_stripper_keeps_strings_and_drops_comments() -> None:
    sample = 'const a = "http://x"; // 273.15\n/* 3600 */ const b = `${c}`; // tail'
    assert _code(sample) == 'const a = "http://x";  \n  const b = `${c}`;  '


def test_a39_no_conversion_constant_in_the_shell() -> None:
    files = sorted(WEB_JS.rglob("*.js"))
    assert len(files) > 20
    found: list[tuple[str, str]] = []
    for path in files:
        for number in _NUMBER.findall(_code(path.read_text(encoding="utf-8"))):
            if Fraction(number) in CONSTANTS:
                found.append((path.relative_to(WEB_JS).as_posix(), number))
    assert found == []


def test_a39_the_displayed_values_are_the_server_s_display_items() -> None:
    """The two places the shell shows a converted number read it from a `display` item."""
    stream_table = (WEB_JS / "model" / "stream-table.js").read_text(encoding="utf-8")
    assert "object.display?.[member]" in stream_table
    streams = (WEB_JS / "screens" / "streams.js").read_text(encoding="utf-8")
    assert "fmt(cell.display.value, getNumberMode())" in streams
    text = (WEB_JS / "text.js").read_text(encoding="utf-8")
    assert "fmt(item.display.value)" in text


# -- A40. Documentation ----------------------------------------------------------------------------


@pytest.fixture(scope="module")
def guide() -> str:
    return GUIDE.read_text(encoding="utf-8")


def test_a40_every_reference_row_is_named_on_the_page(guide: str) -> None:
    rows = REFERENCE["rows"]
    assert len(rows) == 30
    for row in rows:
        assert f"| `{row['kind']}` | `{row['unit']}` |" in guide, row


def test_a40_the_page_states_inputs_presets_the_ambient_command_and_what_stays_si(
    guide: str,
) -> None:
    assert "## Input units" in guide and "ADR 0016" in guide
    for name, units in REFERENCE["presets"].items():
        assert f"| `{name}` |" in guide
        for kind, unit in units.items():
            assert f"`{kind}={unit}`" in guide, (name, kind)
    assert "openflowsheet project ambient --project DIR --pressure" in guide
    assert "--clear" in guide
    assert "## What stays SI" in guide
    for code in ("L-X04-1", "L-X04-2", "L-X04-3"):
        assert code in guide


def test_a40_the_page_is_in_the_site_navigation() -> None:
    nav = (REPO_ROOT / "mkdocs.yml").read_text(encoding="utf-8")
    assert "guide/display-units.md" in nav
