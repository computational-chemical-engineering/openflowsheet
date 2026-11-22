"""X07a ruling P5 (WO3 A9): the platform-limit rows of the replay and floating-point class agree
with the code that carries them.

Every `X07a-L<n>` row in the platform-limit table of `docs/X07a_DECISIONS.md` is carried by a
`bitwise_baseline(row=...)` marker, an `assert_inspected_off_registered(..., row=...)` or
`frozen_windows_consequence(row=...)` call, a `conftest.PLATFORM_DIFFERENCES` entry or a
`conftest.FROZEN_WINDOWS_CONSEQUENCES` entry, and every id those carry is a row: a limit without a
row is undocumented, and a row without a use is a limit nothing applies.
"""

from __future__ import annotations

import re

from conftest import (
    FROZEN_WINDOWS_CONSEQUENCES,
    FROZEN_WINDOWS_LIMITS,
    PLATFORM_DIFFERENCES,
    REPO_ROOT,
)

from openflowsheet.run.replay import REGISTERED_PLATFORMS

DECISIONS = REPO_ROOT / "docs" / "X07a_DECISIONS.md"
ROW = re.compile(r"X07a-L\d+")
#: A row's first cell is its id.
TABLE_ROW = re.compile(r"^\| (X07a-L\d+) \|", re.MULTILINE)
#: The keyword both the marker and the P1c helper take the id by.
USE = re.compile(r'row="(X07a-L\d+)"')


def _table_ids() -> set[str]:
    return set(TABLE_ROW.findall(DECISIONS.read_text(encoding="utf-8")))


def _code_ids() -> set[str]:
    used = {
        row
        for path in (REPO_ROOT / "tests").rglob("*.py")
        if path.name != "test_x07a_platform_rows.py"
        for row in USE.findall(path.read_text(encoding="utf-8"))
    }
    differences = {row for nodes in PLATFORM_DIFFERENCES.values() for row, _ in nodes.values()}
    return used | differences | set(FROZEN_WINDOWS_CONSEQUENCES)


def test_every_row_is_carried_by_code_and_every_use_is_a_row() -> None:
    table, code = _table_ids(), _code_ids()
    assert table, "the platform-limit table has no X07a-L row"
    assert table == code, {"rows without a use": table - code, "uses without a row": code - table}


def test_the_platform_differences_name_no_registered_platform() -> None:
    """P3c: on a registered platform a beyond-policy float is a failure, never a row."""
    assert not set(PLATFORM_DIFFERENCES) & REGISTERED_PLATFORMS
    for nodes in PLATFORM_DIFFERENCES.values():
        for node, (row, paths) in nodes.items():
            assert ROW.fullmatch(row) and paths, node


def test_a_frozen_limits_consequence_holds_only_while_its_limit_stands() -> None:
    """Review R-5 (Q-13 option A): a row that follows from a `FROZEN_WINDOWS_LIMITS` skip names a
    node that is still a key: lifting the limit fails here until the consequence row, its use and
    its table row are retired with it."""
    for row, (node, line) in FROZEN_WINDOWS_CONSEQUENCES.items():
        assert ROW.fullmatch(row) and line, row
        assert node in FROZEN_WINDOWS_LIMITS, (row, node)


#: WO3 A11: the reproducibility statement for the two unregistered CI platforms.
STATEMENT = (
    "macOS arm64 and Windows x86-64: bundles made on the same platform identity replay exactly; "
    "bundles from another platform are inspected, not reproduced (ADR 0007 D3.3, Amendment 3)"
)


def test_the_install_notes_and_the_envelope_state_what_replay_does_off_registered() -> None:
    for path in (
        REPO_ROOT / "benchmarks" / "t08" / "support_envelope.yaml",
        REPO_ROOT / "docs-site" / "getting-started" / "install.md",
    ):
        text = " ".join(path.read_text(encoding="utf-8").replace("- ", " ").split())
        assert STATEMENT in text, path
