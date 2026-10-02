"""P03: the binary audit's headline figures are what the committed inventory actually says.

`docs/p03-binary-audit.md`, `docs/adr/0003-compiled-problem-backend.md` and
`docs/adr/0006-distribution-data-rights.md` quote a small set of numbers that their reasoning rests
on: how many bytes the CasADi wheel ships, how many of them are disabled plugin bytes ([A10]), how
much an import actually loads, and which object carries the one restrictive notice. Prose drifts
from its evidence silently. These tests fail the gate when it does.

They are a **consistency and regression guard over the committed record**, not a re-audit: they do
not open a virtual environment and cannot notice that the record itself was generated wrongly. What
re-derives the record is `scripts/p03_binary_inventory.py`, and what checks the record against a
fresh download is `scripts/p03_verify_reproduction.py`; both need the candidate environments, which
the repository environment deliberately does not contain. Requirements D04 and A10 are therefore
`implemented`, not `tested`, on the strength of these tests alone.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
from conftest import load_json

ANGLE_PLACEHOLDER = re.compile(r"<[^<>]*>")

# The figures the audit and both ADRs quote. Changing one here without regenerating the inventory
# fails; regenerating the inventory and getting a different number fails too, which is the point.
SHARED_OBJECT_BYTES = 234_809_336
SHARED_OBJECT_COUNT = 221
DISABLED_PLUGIN_OBJECTS = 10
DISABLED_PLUGIN_BYTES = 1_846_344
DISABLED_TOTAL_BYTES = 1_885_160
IMPORT_CLOSURE_BYTES = 19_384_616
NOTICE_FILES = 81
METIS_CARRIER_BYTES = 306_208
METIS_SHIPPED_BYTES = 918_624
RESTRICTIVE_NOTICE = "metis-external/metis-4.0/LICENSE"

# Every CasADi plugin reachable to `libcoinmetis`. ADR 0006 D1.5 forbids all seven on a default
# path, so the list being complete is load-bearing, not decorative.
METIS_CLOSURE_PLUGINS = {
    "conic:cbc",
    "conic:clp",
    "linsol:mumps",
    "nlpsol:bonmin",
    "nlpsol:ipopt",
    "nlpsol:sleqp",
    "nlpsol:uno",
}

VENDOR_LIBRARY_PREFIXES = (
    "libgurobi",
    "libmosek",
    "libcplex",
    "libknitro",
    "libsnopt",
    "libworhp",
    "libhsl",
    "libcoinhsl",
    "libxprs",
)


@pytest.fixture(scope="session")
def casadi_inventory(repo_root: Path) -> dict[str, Any]:
    loaded = load_json(repo_root / "spikes" / "p03" / "results" / "casadi-inventory.json")
    assert isinstance(loaded, dict)
    return loaded


@pytest.fixture(scope="session")
def pyomo_inventory(repo_root: Path) -> dict[str, Any]:
    loaded = load_json(repo_root / "spikes" / "p03" / "results" / "pyomo-inventory.json")
    assert isinstance(loaded, dict)
    return loaded


@pytest.fixture(scope="session")
def reproduction(repo_root: Path) -> dict[str, Any]:
    loaded = load_json(repo_root / "spikes" / "p03" / "results" / "reproduction.json")
    assert isinstance(loaded, dict)
    return loaded


def test_inventory_totals_agree_with_its_own_file_list(casadi_inventory: dict[str, Any]) -> None:
    """The summary a reader quotes must be the sum of the rows underneath it."""
    files = casadi_inventory["files"]
    assert casadi_inventory["total_bytes"] == sum(int(entry["bytes"]) for entry in files)
    for kind, totals in casadi_inventory["totals"].items():
        rows = [entry for entry in files if entry["kind"] == kind]
        assert totals["files"] == len(rows), kind
        assert totals["bytes"] == sum(int(entry["bytes"]) for entry in rows), kind


def test_shared_object_payload_is_the_audited_figure(casadi_inventory: dict[str, Any]) -> None:
    shared = casadi_inventory["totals"]["elf-shared"]
    assert shared["files"] == SHARED_OBJECT_COUNT
    assert shared["bytes"] == SHARED_OBJECT_BYTES


def test_disabled_distributed_bytes_are_the_a10_figure(casadi_inventory: dict[str, Any]) -> None:
    """[A10]'s minimum evidence: the plugin inventory *including* the bytes that cannot run."""
    disabled = casadi_inventory["disabled_distributed_bytes"]
    assert disabled["plugin_objects"] == DISABLED_PLUGIN_OBJECTS
    assert disabled["plugin_bytes"] == DISABLED_PLUGIN_BYTES
    stubs = sum(int(item["bytes"]) for item in disabled["vendor_adaptor_stubs"])
    assert disabled["plugin_bytes"] + stubs == DISABLED_TOTAL_BYTES
    # Every disabled plugin must be disabled *for a named reason*, never merely broken.
    failed = [item for item in casadi_inventory["plugins"] if item["load"] == "failed"]
    assert len(failed) == DISABLED_PLUGIN_OBJECTS
    for item in failed:
        assert item.get("vendor_library_expected"), item["name"]
        assert item["load_detail"], item["name"]


def test_no_proprietary_vendor_library_is_shipped(casadi_inventory: dict[str, Any]) -> None:
    """The commercial-solver plugins are adaptors. If a vendor library ever appears, stop."""
    shipped = [Path(entry["path"]).name for entry in casadi_inventory["files"]]
    offenders = [
        name
        for name in shipped
        if name.startswith(VENDOR_LIBRARY_PREFIXES) and "_adaptor" not in name
    ]
    assert not offenders, f"a vendor library is bundled: {offenders}"


def test_import_closure_is_the_audited_figure(casadi_inventory: dict[str, Any]) -> None:
    reach = casadi_inventory["reachability"]
    assert reach["resolved"] is True
    assert reach["closure_bytes"] == IMPORT_CLOSURE_BYTES
    assert reach["in_package_closure"] == ["libcasadi.so.3.7"]


def test_exactly_one_restrictive_notice_and_it_is_metis_4(casadi_inventory: dict[str, Any]) -> None:
    notices = casadi_inventory["notices"]
    assert len(notices) == NOTICE_FILES
    restrictive = [item for item in notices if item["restrictive_clauses"]]
    assert [item["path"] for item in restrictive] == [RESTRICTIVE_NOTICE]
    assert "non-commercial / no-redistribution" in restrictive[0]["restrictive_clauses"]


def test_metis_attribution_is_carried_by_exactly_three_copies(
    casadi_inventory: dict[str, Any],
) -> None:
    probe = next(
        item for item in casadi_inventory["attribution_probes"] if item["component"] == "metis"
    )
    carriers = probe["carriers"]
    assert len(carriers) == 3
    assert {item["conclusion"] for item in carriers} == {"METIS 4.x"}
    assert {int(item["bytes"]) for item in carriers} == {METIS_CARRIER_BYTES}
    assert sum(int(item["bytes"]) for item in carriers) == METIS_SHIPPED_BYTES
    # One content, three names: the wheel ships no symlinks.
    assert len({item["sha256"] for item in carriers}) == 1
    assert casadi_inventory["symlinks"] == {}


def test_metis_is_not_reachable_from_the_extension_module(
    casadi_inventory: dict[str, Any],
) -> None:
    """The selected route must not load the restrictive object. ADR 0006 D1.5."""
    closure = set(casadi_inventory["reachability"]["in_package_closure"])
    assert not any(name.startswith("libcoinmetis") for name in closure)


def test_the_metis_closure_names_all_seven_plugins(casadi_inventory: dict[str, Any]) -> None:
    """Derived from the recorded DT_NEEDED lists, not from the prose. ADR 0006 D1.5, audit §2.6.

    The enumeration matters because D1.5 is a use restriction a future session will grep by plugin
    name; an incomplete list reads as permission for the six it leaves out.
    """
    needed = {
        entry["path"]: entry["needed"] for entry in casadi_inventory["files"] if "needed" in entry
    }
    assert needed, "the inventory records no per-object DT_NEEDED"
    closure: set[str] = set()
    frontier = ["libcoinmetis.so.2"]
    seen = set(frontier)
    while frontier:
        target = frontier.pop()
        for path, dependencies in needed.items():
            if target in dependencies and path not in closure:
                closure.add(path)
                basename = path.split("/")[-1]
                if basename not in seen:
                    seen.add(basename)
                    frontier.append(basename)
    plugins = {
        re.sub(r"^libcasadi_([a-z0-9]+)_([a-z0-9_]+)\.so.*$", r"\1:\2", path)
        for path in closure
        if path.startswith("libcasadi_")
    }
    assert plugins == METIS_CLOSURE_PLUGINS


def test_pyomo_ships_no_disabled_bytes(pyomo_inventory: dict[str, Any]) -> None:
    """The rejected candidate's [A10] count is zero, and the audit's comparison says so."""
    assert len(pyomo_inventory["shipped_binaries"]) == 1
    assert pyomo_inventory["dist_info"]["notice_files"], "Pyomo carries its notice in dist-info"


def test_clean_environment_reproduction_had_no_shipped_difference(
    reproduction: dict[str, Any],
) -> None:
    """Plan §8.1 day 9. Only install-generated bytecode may differ, and it is counted."""
    casadi = reproduction["casadi"]
    assert casadi["differing"] == []
    assert casadi["missing_from_clean_install"] == []
    assert casadi["unexpected_in_clean_install"] == []
    assert casadi["reproduced"] is True
    assert all(name.endswith(".pyc") for name in casadi["generated_differing"])
    assert reproduction["pyomo_wheel"]["reproduced"] is True


@pytest.mark.parametrize(
    "name", ["0003-compiled-problem-backend.md", "0006-distribution-data-rights.md"]
)
def test_the_p03_adrs_exist_and_carry_no_placeholder(repo_root: Path, name: str) -> None:
    """Angle-bracket template text is never valid evidence (CLAUDE.md, scientific conduct)."""
    text = (repo_root / "docs" / "adr" / name).read_text(encoding="utf-8")
    assert text.startswith("# ADR 00")
    offenders = [
        match
        for match in ANGLE_PLACEHOLDER.findall(text)
        # Real content that is legitimately angle-bracketed: shell/env placeholders quoted from
        # tool output, and generic path forms the plan itself writes that way.
        if not re.fullmatch(
            r"<(CPLEX_VERSION|GUROBI_VERSION|commit|package|ID|type|name|n)>", match
        )  # noqa: E501
        and not match.startswith("<http")
    ]
    assert not offenders, f"{name} carries placeholder text: {offenders}"


def test_no_backend_wheel_bytes_are_tracked_in_the_repository(repo_root: Path) -> None:
    """ADR 0006 D5.5 hygiene: the project distributes source, never the wheel's bytes."""
    import subprocess

    listing = subprocess.run(
        ["git", "ls-files"], cwd=repo_root, capture_output=True, text=True, check=True
    ).stdout.splitlines()
    offenders = [path for path in listing if re.search(r"\.(so|so\.\d|a|dylib|dll)$", path)]
    assert not offenders, f"compiled backend bytes are tracked: {offenders}"
