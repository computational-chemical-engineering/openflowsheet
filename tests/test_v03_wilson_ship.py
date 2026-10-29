"""V03.A12–A14: Wilson's ship set is package data, attributed in NOTICE, as the rights check says.

V03 spec §9.1 (R-880; Frank, 2026-10-29, Q-F3 "Ship params + points"). From 0.3.0 the wheel
carries `benchmarks/s10/records.yaml` and `benchmarks/s10/vle/kurihara1993_binaries.csv` by
R-616's pattern: one `PACKAGED` entry and one `_data` link each, bytes unchanged. The binder and
the verifier read the records the package carries, so R-811's refusal of the Wilson basis in a
wheel is gone; `thermo/wilson_ig.py` is not edited (S11.A75), and an installation with neither
copy is still refused (`tests/test_s11_bases.py::test_a09_…`). The built wheel's contents are
T08.A32's (`tests/test_t08_w2_inventory.py`), and a fresh install from it is V03.A19's, at C.

The inputs are real records: the repository's S10 files, `pyproject.toml`, NOTICE,
`docs/s10-rights-check.md` (and its text at `RIGHTS_BEFORE_V03`, the last commit before V03
touched it), the specification's §9.1 and `benchmarks/v03/registration.json`.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import tomllib
from pathlib import Path

import pytest
from conftest import REPO_ROOT

from openflowsheet import resources
from openflowsheet.application.binding import Unbound
from openflowsheet.application.revision_binding import provider_for
from openflowsheet.models.revision_flowsheet import WILSON_BASIS
from openflowsheet.resources import PACKAGED, packaged, packaged_path
from openflowsheet.thermo import FlashRequest, PropertyRequest, StreamState, wilson_ig
from openflowsheet.thermo.wilson_ig import WilsonIdealGasProvider
from openflowsheet.verify import certificate

REGISTRATION = json.loads(
    (REPO_ROOT / "benchmarks" / "v03" / "registration.json").read_text(encoding="utf-8")
)
SHIPS: list[str] = REGISTRATION["ship_set"]["ships"]
REPOSITORY_ONLY: list[str] = REGISTRATION["ship_set"]["repository_only"]
SPEC = (REPO_ROOT / "docs" / "derivations" / "V03-release-spec.md").read_text(encoding="utf-8")
NOTICE = (REPO_ROOT / "NOTICE").read_text(encoding="utf-8")
RIGHTS = "docs/s10-rights-check.md"
#: The last commit to change the rights check before V03's (S10 WO-S10-8 step 1).
RIGHTS_BEFORE_V03 = "a15baa0a"
#: The rights-check rows V03 changed (spec §9.1's ship set and the files it names beside it).
CHANGED_BY_V03 = {
    "`benchmarks/s10/records.yaml`",
    "`benchmarks/s10/fit-report.json`",
    "`benchmarks/s10/vle/kurihara1993_binaries{,.A,.B}.csv`",
    "`benchmarks/s10/vle/kurihara1993_binaries.csv`",
    "`benchmarks/s10/vle/kurihara1993_binaries.{A,B}.csv`",
}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# -- V03.A12: package data, and the basis binds from it --------------------------------------------


def test_a12_the_ship_set_is_the_specification_s() -> None:
    section = SPEC[SPEC.index("### 9.1 Wilson") : SPEC.index("### 9.2 E01")]
    yes = [
        path
        for line in section.splitlines()
        if line.startswith("| `") and "| **Yes**" in line
        for path in re.findall(r"`(benchmarks/[^`]+)`", line.split(" | ")[0])
    ]
    assert yes == SHIPS == [wilson_ig.RECORDS_PATH, "benchmarks/s10/vle/kurihara1993_binaries.csv"]


@pytest.mark.parametrize("relative", SHIPS)
def test_a12_each_shipped_file_is_one_packaged_entry_with_its_link(relative: str) -> None:
    assert relative in PACKAGED
    link = REPO_ROOT / "src" / "openflowsheet" / "_data" / relative
    assert link.is_symlink()
    assert link.resolve() == (REPO_ROOT / relative).resolve()
    data = (REPO_ROOT / relative).read_bytes()
    assert _sha256(packaged(relative).read_bytes()) == _sha256(data)
    assert packaged_path(relative) == link
    declared = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    patterns = declared["tool"]["setuptools"]["package-data"]["openflowsheet"]
    assert f"_data/{relative}" in patterns


def test_a12_nothing_else_of_s10_is_packaged() -> None:
    s10 = [entry for entry in PACKAGED if entry.startswith("benchmarks/s10")]
    assert s10 == SHIPS
    for relative in REPOSITORY_ONLY:
        assert (REPO_ROOT / relative).is_file(), relative
        assert relative not in PACKAGED
        assert not (REPO_ROOT / "src" / "openflowsheet" / "_data" / relative).exists(), relative


def test_a12_the_records_bytes_and_data_sha256_did_not_move() -> None:
    """R-880: bytes unchanged, so `data_sha256` is S10's (the hash in the attribution page)."""
    page = (REPO_ROOT / "docs" / "attributions" / "wilson-ig-v1.md").read_text(encoding="utf-8")
    for relative in SHIPS:
        assert _sha256((REPO_ROOT / relative).read_bytes()) in page, relative
    caps = WilsonIdealGasProvider(packaged_path(wilson_ig.RECORDS_PATH)).describe()
    assert caps.data_sha256 == _sha256((REPO_ROOT / wilson_ig.RECORDS_PATH).read_bytes())


@pytest.fixture
def no_checkout(monkeypatch: pytest.MonkeyPatch) -> None:
    """`thermo/wilson_ig.py`'s own lookup as it is in a wheel: no source checkout."""
    monkeypatch.setattr(wilson_ig, "_checkout_records", lambda: None)
    with pytest.raises(wilson_ig.RecordError, match="^records_missing: "):
        wilson_ig.load_records()


@pytest.mark.usefixtures("no_checkout")
def test_a12_r_811_s_wheel_refusal_is_gone() -> None:
    provider = provider_for(WILSON_BASIS)
    assert not isinstance(provider, Unbound)
    assert provider.describe().provider_id == "wilson-ig-v2"
    assert (
        provider.describe().data_sha256
        == wilson_ig.load_records(REPO_ROOT / wilson_ig.RECORDS_PATH).sha256
    )
    assert certificate._wilson_provider().describe() == provider.describe()


def _answers(provider: WilsonIdealGasProvider) -> tuple[object, ...]:
    state = StreamState(n=(0.3, 0.3, 0.4), temperature=350.0, pressure=101325.0)
    inputs = ("T", "P", "n_CH3OH", "n_C2H5OH", "n_H2O")
    phases = tuple(
        provider.evaluate_phase(
            PropertyRequest(
                state=state,
                phase=phase,
                properties=provider.describe().properties,
                derivatives=inputs,
            ),
            None,
        )
        for phase in ("LIQUID", "VAPOR")
    )
    flash = provider.flash(FlashRequest(state=state), None)  # type: ignore[arg-type]
    return (*phases, flash)


@pytest.mark.usefixtures("no_checkout")
def test_a12_wilson_ig_v1_binds_from_package_data() -> None:
    """The library-only v1 provider, given the package's copy, answers as the checkout's does,
    value for value (same code, same bytes: bitwise)."""
    from_package = WilsonIdealGasProvider(packaged_path(wilson_ig.RECORDS_PATH))
    from_checkout = WilsonIdealGasProvider(REPO_ROOT / wilson_ig.RECORDS_PATH)
    assert from_package.describe() == from_checkout.describe()
    package, checkout = _answers(from_package), _answers(from_checkout)
    assert package[-1].status == "ok"  # type: ignore[attr-defined]
    assert package == checkout


def test_a12_packaged_path_is_none_off_the_file_system(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(KeyError):
        packaged_path("benchmarks/s10/vle/kurihara1993_ternary.csv")
    monkeypatch.setattr(resources, "packaged", lambda relative: object())
    assert resources.packaged_path(wilson_ig.RECORDS_PATH) is None


# -- V03.A13: NOTICE -------------------------------------------------------------------------------

WILSON_STRINGS = (
    "Kurihara",
    "J. Chem. Eng. Data 38 (1993) 446",
    "NASA TM-4513",
    "CoolProp 8.0.0",
    "deReuck-BOOK-1993",
    "Schroeder-JPCRD-2014",
    "Wagner-JPCRD-2002",
    "CIAAW",
)
IPCC_STRINGS = ("IPCC AR6 WG1", "Table 7.15")
#: E01's GWP-100 file (ADR 0052): the IPCC values ship, and NOTICE cites them, with E01's merge.
IPCC_FILE = "assessment/lca/gwp100-ipcc-ar6-v1.json"


@pytest.mark.parametrize("string", WILSON_STRINGS)
def test_a13_notice_holds_each_wilson_string_once(string: str) -> None:
    collapsed = " ".join(NOTICE.split())
    assert NOTICE.count(string) == collapsed.count(string) == 1


def test_a13_the_wilson_block_names_both_package_paths() -> None:
    block = NOTICE[NOTICE.index("Third-party data: the Wilson records") :]
    for relative in SHIPS:
        assert f"openflowsheet/_data/{relative}" in block
        assert f"(repository path {relative})" in " ".join(block.split())
    assert all(string in block for string in WILSON_STRINGS)


@pytest.mark.parametrize("string", IPCC_STRINGS)
def test_a13_notice_cites_ipcc_once_exactly_when_its_values_ship(string: str) -> None:
    """§9.2: the IPCC block arrives with E01's data (E01's NOTICE carries it); before E01's merge
    neither ships, after it each string is there once."""
    expected = 1 if IPCC_FILE in PACKAGED else 0
    assert " ".join(NOTICE.split()).count(string) == expected


# -- V03.A14: the rights check's ship column -------------------------------------------------------


def _file_map(text: str) -> dict[str, list[str]]:
    section = text[text.index("## 3. Per-file map") :]
    section = section[: section.index("**Summary.**")]
    rows = [line for line in section.splitlines() if line.startswith("| `")]
    split = ([cell.strip() for cell in row.strip().strip("|").split(" | ")] for row in rows)
    return {cells[0]: cells for cells in split}


def _rows(text: str) -> dict[str, str]:
    return {
        line.split(" | ")[0].strip("| "): line
        for line in text.splitlines()
        if line.startswith("| S10-RC-")
    }


def test_a14_the_ship_column_is_the_specification_s() -> None:
    files = _file_map((REPO_ROOT / RIGHTS).read_text(encoding="utf-8"))
    shipped = sorted(
        re.sub(r"`", "", name) for name, cells in files.items() if cells[2].startswith("**Yes")
    )
    assert shipped == sorted(SHIPS)
    for name, cells in files.items():
        if not cells[2].startswith("**Yes"):
            assert cells[2].startswith(("No", "Repository only", "Not a packaged path")), name
    assert "Frank, 2026-10-29" in files["`benchmarks/s10/records.yaml`"][2]


def test_a14_every_other_row_is_unchanged() -> None:
    now = (REPO_ROOT / RIGHTS).read_text(encoding="utf-8")
    before = subprocess.run(
        ["git", "show", f"{RIGHTS_BEFORE_V03}:{RIGHTS}"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    now_map, before_map = _file_map(now), _file_map(before)
    assert set(now_map) ^ set(before_map) <= CHANGED_BY_V03
    for name in set(now_map) - CHANGED_BY_V03:
        assert now_map[name] == before_map[name], name
    now_rows, before_rows = _rows(now), _rows(before)
    assert set(now_rows) == set(before_rows) == {f"S10-RC-0{n}" for n in range(1, 10)}
    for row in set(now_rows) - {"S10-RC-05", "S10-RC-08"}:
        assert now_rows[row] == before_rows[row], row


@pytest.mark.parametrize("row", ["S10-RC-05", "S10-RC-08"])
def test_a14_rc_05_and_rc_08_cite_frank(row: str) -> None:
    line = _rows((REPO_ROOT / RIGHTS).read_text(encoding="utf-8"))[row]
    assert "ship decided by Frank, 2026-10-29 (Q-F3, R-880)" in line
    assert "**unresolved**" in line


def test_a14_the_repository_only_files_are_not_marked_yes() -> None:
    files = _file_map((REPO_ROOT / RIGHTS).read_text(encoding="utf-8"))
    for relative in REPOSITORY_ONLY:
        matches = [name for name in files if _expands_to(name, relative)]
        assert matches, relative
        assert all(not files[name][2].startswith("**Yes") for name in matches), relative


def _expands_to(cell: str, relative: str) -> bool:
    """Whether the backticked brace pattern `cell` (`a{,.A,.B}.csv`) names `relative`."""
    pattern = cell.strip("`")
    braces = re.search(r"\{([^}]*)\}", pattern)
    if braces is None:
        return pattern == relative
    head, tail = pattern[: braces.start()], pattern[braces.end() :]
    return any(f"{head}{choice}{tail}" == relative for choice in braces.group(1).split(","))


def test_the_expansion_helper() -> None:
    assert _expands_to("`a/b{,.A,.B}.csv`", "a/b.csv")
    assert _expands_to("`a/b.{A,B}.csv`", "a/b.B.csv")
    assert not _expands_to("`a/b.{A,B}.csv`", "a/b.csv")
    assert Path(SHIPS[0]).name == "records.yaml"
