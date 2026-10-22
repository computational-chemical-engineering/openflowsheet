"""C12: the attribution file and the rights check of the nine `pr-lib-v1` records.

`docs/attributions/pr-lib-v1.md` must name every source a record states in `rights.source` and
every DOI and retrieval tool in a record's `provenance`, and each of its sections must carry the
verdict of the rights-check rows it cites (`docs/l01-rights-check.md`). The rights check's
per-record map must list the ATcT row exactly for the records whose formation enthalpy is not zero
by definition. These are coverage and consistency checks; whether the rights statements are
correct, and whether the records ship, is not decided here (L01-Q4, T08.A32).
"""

from __future__ import annotations

import re
from typing import Any

import yaml
from conftest import REPO_ROOT

RECORDS = REPO_ROOT / "benchmarks" / "l01" / "components.yaml"
ATTRIBUTION = REPO_ROOT / "docs" / "attributions" / "pr-lib-v1.md"
RIGHTS_CHECK = REPO_ROOT / "docs" / "l01-rights-check.md"
IDS = ("H2", "N2", "Ar", "CH4", "H2O", "CO2", "O2", "C2H6", "C3H8")
VERDICTS = ("permitted with conditions", "unresolved")
#: A `rights.source` segment that names no external source.
BY_DEFINITION = "zero by definition"

RECORD_LIST: list[dict[str, Any]] = yaml.safe_load(RECORDS.read_text(encoding="utf-8"))[
    "components"
]
TEXT = ATTRIBUTION.read_text(encoding="utf-8")
CHECK = RIGHTS_CHECK.read_text(encoding="utf-8")


def _rights_check_verdicts() -> dict[str, str]:
    """Row id -> verdict, from the rights-check table.

    Row layout: `| RC-xx | source | takes | terms | verdict | doubts |`.
    """
    verdicts: dict[str, str] = {}
    for line in CHECK.splitlines():
        match = re.match(r"\| (RC-\d\d) \|", line)
        if match is None:
            continue
        cell = line.split(" | ")[4]
        found = [verdict for verdict in VERDICTS if cell.startswith(f"**{verdict}**")]
        assert len(found) == 1, (match.group(1), cell)
        assert match.group(1) not in verdicts, match.group(1)
        verdicts[match.group(1)] = found[0]
    return verdicts


def test_the_nine_records_are_the_ones_checked() -> None:
    assert tuple(record["id"] for record in RECORD_LIST) == IDS


def test_every_rights_source_segment_is_in_the_attribution_file() -> None:
    named = set()
    for record in RECORD_LIST:
        for segment in record["rights"]["source"].split("; "):
            label, separator, source = segment.partition(": ")
            assert separator and label.strip() and source.strip(), (record["id"], segment)
            if source != BY_DEFINITION:
                named.add(source)
                assert source in TEXT, (record["id"], source)
    # Nine reference EOS, NASA TM-4513, ATcT 1.112 and chemicals.
    assert len(named) == 12, sorted(named)


def test_every_provenance_doi_and_retrieval_tool_is_in_the_attribution_file() -> None:
    dois: set[str] = set()
    tools: set[str] = set()
    for record in RECORD_LIST:
        quantities = [record["molecular_weight"], *record["parameters"].values()]
        for quantity in quantities:
            provenance = quantity["provenance"]
            dois.update(re.findall(r"doi:(10\.\d{4,}/[^\s;,]+)", provenance))
            tools.update(re.findall(r"\b((?:chemicals|Cantera) \d+\.\d+\.\d+)", provenance))
            for source in ("NASA TM-4513", "ATcT", "CIAAW"):
                if source in provenance:
                    tools.add(source)
    assert len(dois) == len(IDS), sorted(dois)  # one reference EOS per record
    assert tools == {"chemicals 1.5.2", "Cantera 3.2.0", "NASA TM-4513", "ATcT", "CIAAW"}
    assert sorted(item for item in dois | tools if item not in TEXT) == []


def test_every_attribution_section_carries_its_rights_check_verdict() -> None:
    verdicts = _rights_check_verdicts()
    assert sorted(verdicts) == [f"RC-{number:02d}" for number in range(1, 13)]
    cited: set[str] = set()
    for line in TEXT.splitlines():
        if not line.startswith("## "):
            continue
        rows = re.findall(r"RC-\d\d", line)
        if not rows:
            continue
        stated = line.rsplit(" — ", 1)[-1]
        assert stated in VERDICTS, line
        assert all(verdicts[row] == stated for row in rows), (line, {r: verdicts[r] for r in rows})
        cited.update(rows)
    # Each record source (RC-01..RC-08) has a section; RC-09..RC-12 are named in the
    # cross-check section's text.
    assert cited >= {f"RC-{number:02d}" for number in range(1, 9)}
    assert all(row in TEXT for row in verdicts)


def test_the_per_record_map_lists_atct_exactly_where_the_record_uses_it() -> None:
    rows_by_id: dict[str, str] = {}
    for line in CHECK.splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) == 4 and cells[0] in IDS:
            assert cells[0] not in rows_by_id, cells[0]
            rows_by_id[cells[0]] = cells[3]
    assert set(rows_by_id) == set(IDS)
    for record in RECORD_LIST:
        provenance = record["parameters"]["standard_formation_enthalpy"]["provenance"]
        uses_atct = provenance.startswith("Active Thermochemical Tables (ATcT) version 1.112")
        assert uses_atct != provenance.startswith("Element in its reference state"), record["id"]
        assert ("05" in rows_by_id[record["id"]].split(", ")) == uses_atct, record["id"]
