"""T08.A30–A32: the [A10] refresh, mode A hygiene, and data provenance (T08 release spec §4.8, §9).

**A30** reads the committed per-architecture summaries `docs/t08-a30/t08-a30-<machine>.json`,
written by `scripts/p03_binary_inventory.py --a30` (x86-64 on `ref-x86-64`; aarch64 by the CI job
`a30-inventory`, dispatch input `a30_inventory`). The full records are evidence artifacts referenced
by `record_sha256`. Each test re-derives its claim from the rows in the summary rather than trusting
the summary's own verdict, and the aarch64 half skips — never passes — until its summary exists.

**A31** and **A32** build the project's sdist and wheel from a copy of the git-tracked tree with the
build backend `pyproject.toml` declares (installed into a scratch directory; the tests skip when it
cannot be obtained) and read what they contain.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tomllib
import zipfile
from pathlib import Path
from typing import Any

import pytest
import yaml
from conftest import REPO_ROOT, load_json, sha256_of
from test_schemas_p01 import validator_for

from openflowsheet.thermo import iapws95
from openflowsheet.thermo._coolprop_heos_fluids import FLUIDS

SUMMARIES = REPO_ROOT / "docs" / "t08-a30"
L01_RECORDS = "benchmarks/l01/components.yaml"
S10_RECORDS = "benchmarks/s10/records.yaml"
MACHINES = ("x86_64", "aarch64")

# ADR 0006 D4 (the eight unresolved objects) and D2 (the METIS 4.x carrier's three SONAME copies),
# x86-64 wheel. D1.5's seven plugins in the METIS closure.
ADR0006_D4 = {
    "libgfortran-8f1e9814.so.5.0.0",
    "libquadmath-828275a7.so.0.0.0",
    "libgomp-870cb1d0.so.1.0.0",
    "libmvec-2-583a17db.28.so",
    "libspral.a",
    "libmatlab_ipc.so",
    "libcplex_adaptor.so",
    "libgurobi_adaptor.so",
}
# ADR 0006 Amendment 2 (R-142): D4 on the aarch64 wheel, its two unresolved toolchain runtimes.
ADR0006_A2 = {"libgfortran-8de1544a.so.5.0.0", "libgomp-7eb2fb8b.so.1.0.0"}
ADR0006_D2 = {"libcoinmetis.so", "libcoinmetis.so.2", "libcoinmetis.so.2.0.0"}
ADR0006_D1_5_PLUGINS = [
    "conic:cbc",
    "conic:clp",
    "linsol:mumps",
    "nlpsol:bonmin",
    "nlpsol:ipopt",
    "nlpsol:sleqp",
    "nlpsol:uno",
]
FAILING = {"restrictive", "gpl-family", "unresolved"}
HEX64 = re.compile(r"^[0-9a-f]{64}$")


def _summary(machine: str) -> dict[str, Any]:
    path = SUMMARIES / f"t08-a30-{machine}.json"
    if not path.is_file():
        pytest.skip(
            f"T08.A30's {machine} half is pending: dispatch the CI input `a30_inventory`, commit "
            f"the uploaded summary as {path.relative_to(REPO_ROOT)}"
        )
    loaded = load_json(path)
    assert isinstance(loaded, dict)
    assert loaded["host"]["machine"] == machine
    return loaded


def _lock_pins() -> dict[str, str]:
    pins = {}
    for line in (REPO_ROOT / "requirements.lock").read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if "==" in line:
            name, version = line.split("==", 1)
            pins[re.sub(r"[-_.]+", "-", name).lower()] = version
    return pins


@pytest.mark.parametrize("machine", MACHINES)
def test_a30_inventory_is_of_the_lock_and_names_its_compiled_distributions(machine: str) -> None:
    """An empty inventory fails: it names ≥ casadi, numpy, scipy and the server extra's wheels."""
    summary = _summary(machine)
    assert summary["lock_sha256"] == sha256_of(REPO_ROOT / "requirements.lock")
    pins = _lock_pins()
    for row in summary["distributions"]:
        assert pins[row["name"]] == row["version"], row["name"]
    compiled = {row["name"] for row in summary["distributions"] if row["compiled"]}
    server = load_json(REPO_ROOT / "docs" / "t07-server-licences.json")
    server_compiled = {row["name"] for row in server["distributions"] if row["compiled"]}
    assert server_compiled  # G19's record: cffi, cryptography, pydantic-core, rpds-py
    assert {"casadi", "numpy", "scipy"} | server_compiled <= compiled
    for row in summary["distributions"]:
        if row["compiled"]:
            assert row["objects"] > 0 and row["object_bytes"] > 0, row["name"]
            assert HEX64.match(row["objects_digest"]) and HEX64.match(row["files_digest"])
    assert sum(row["objects"] for row in summary["distributions"]) == summary["objects"]
    assert HEX64.match(summary["record_sha256"])


@pytest.mark.parametrize("machine", MACHINES)
def test_a30_required_closure_rows_carry_path_hash_needed_and_attribution(machine: str) -> None:
    summary = _summary(machine)
    rows = summary["required_closure"]
    assert rows
    for row in rows:
        assert HEX64.match(row["sha256"]), row["path"]
        assert isinstance(row["needed"], list), row["path"]
        assert row["category"] in FAILING | {"lgpl", "identified"}, row["path"]
        if row["category"] != "unresolved":
            assert row["licence"], row["path"]
    # The project's measured load is inside the static closure: the closure is not too narrow.
    loaded = {path for path in summary["measured_project_load"]["mapped"] if ".so" in path}
    assert summary["measured_project_load"]["solve_exit"] == 0
    assert loaded
    assert loaded <= {row["path"] for row in rows}


@pytest.mark.parametrize("machine", MACHINES)
def test_a30_metis_closure_is_unreachable_from_every_project_path(machine: str) -> None:
    summary = _summary(machine)
    metis = summary["metis"]
    closure = set(metis["closure"])
    required = {row["path"] for row in summary["required_closure"]}
    loaded = set(summary["measured_project_load"]["mapped"])
    assert not closure & required
    assert not closure & loaded
    assert metis["reached_from_project_paths"] == []
    assert {item["path"] for item in metis["carriers"]} <= closure


def test_a30_x86_64_reproduces_the_p03_audit() -> None:
    """The x86-64 CasADi objects are P03's audited bytes, and ADR 0006's lists re-derive."""
    summary = _summary("x86_64")
    casadi = next(row for row in summary["distributions"] if row["name"] == "casadi")
    audited = load_json(REPO_ROOT / "spikes" / "p03" / "results" / "casadi-inventory.json")
    rows = sorted(
        f"casadi/{entry['path']}\t{entry['sha256']}\n"
        for entry in audited["files"]
        if entry["kind"] in {"elf-shared", "elf-executable", "static-archive"}
    )
    assert casadi["objects"] == len(rows) == 232
    assert casadi["object_bytes"] == 240_481_560
    assert casadi["objects_digest"] == hashlib.sha256("".join(rows).encode()).hexdigest()
    metis = summary["metis"]
    assert {Path(item["path"]).name for item in metis["carriers"]} == ADR0006_D2
    assert {item["conclusion"] for item in metis["carriers"]} == {"METIS 4.x"}
    assert metis["closure_plugins"] == ADR0006_D1_5_PLUGINS
    unresolved = {
        Path(item["path"]).name
        for item in summary["findings"]
        if item["distribution"] == "casadi" and item["category"] == "unresolved"
    }
    assert unresolved == ADR0006_D4


@pytest.mark.parametrize("machine", MACHINES)
def test_a30_every_failing_object_is_dispositioned_or_listed(machine: str) -> None:
    """Restrictive, non-LGPL GPL-family and unresolved objects are each a finding, and a finding's
    disposition is one ADR 0006 actually makes (by name, in the CasADi wheel)."""
    summary = _summary(machine)
    findings = {item["path"]: item for item in summary["findings"]}
    counted = sum(
        count
        for categories in summary["categories_by_distribution"].values()
        for category, count in categories.items()
        if category in FAILING
    )
    assert counted == len(findings)
    for item in findings.values():
        assert item["category"] in FAILING
        name = Path(item["path"]).name
        expected = None
        if item["distribution"] == "casadi" and name in ADR0006_D4:
            expected = "ADR 0006 D4"
        elif item["distribution"] == "casadi" and name in ADR0006_A2:
            expected = "ADR 0006 Amendment 2"
        elif item["distribution"] == "casadi" and name in ADR0006_D2:
            expected = "ADR 0006 D2"
        elif (
            item["distribution"] in {"numpy", "scipy"}
            and item["licence"] == "GPL-3.0-with-GCC-exception"
        ):
            expected = "ADR 0006 Amendment 1"  # Frank, 2026-10-01 (R-135)
        assert item["dispositioned_by"] == expected, item["path"]
    for row in summary["required_closure"]:
        if row["category"] in FAILING:
            assert findings[row["path"]]["in_required_closure"], row["path"]


@pytest.mark.parametrize("machine", MACHINES)
def test_a30_zero_undispositioned_objects_in_a_required_closure(machine: str) -> None:
    """Spec §4.8's verdict rule. A failure is a licence reading for Frank, not a code defect."""
    summary = _summary(machine)
    undispositioned = sorted(
        f"{item['path']} ({item['category']}: {item['licence']})"
        for item in summary["findings"]
        if item["dispositioned_by"] is None
        and (item["in_required_closure"] or item["loaded_by_project"])
    )
    assert summary["verdict"]["pass"] == (not undispositioned)
    assert undispositioned == []


# ------------------------------------------------------------------------------------------------
# A31 / A32: the sdist and the wheel, built from the tracked tree.


def _tracked() -> list[str]:
    completed = subprocess.run(
        ["git", "ls-files", "-z"], cwd=REPO_ROOT, capture_output=True, check=True
    )
    return [path for path in completed.stdout.decode().split("\0") if path]


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    """The sdist and the wheel of the working tree's tracked files, by the declared backend."""
    scratch = tmp_path_factory.mktemp("a31")
    with (REPO_ROOT / "pyproject.toml").open("rb") as handle:
        requires = tomllib.load(handle)["build-system"]["requires"]
    backend = scratch / "backend"
    installed = subprocess.run(
        [sys.executable, "-m", "pip", "install", "--quiet", "--target", str(backend), *requires],
        capture_output=True,
        text=True,
        check=False,
    )
    if installed.returncode != 0:
        pytest.skip(
            f"the build backend {requires} could not be installed: {installed.stderr[-300:]}"
        )
    tree = scratch / "tree"
    for path in _tracked():
        source = REPO_ROOT / path
        if not source.is_file():
            continue  # deleted in the working tree
        target = tree / path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    out = scratch / "dist"
    environment = {**os.environ, "PYTHONPATH": str(backend)}
    built: dict[str, Path] = {}
    for kind in ("sdist", "wheel"):
        # One process per hook, as a build frontend calls them.
        script = (
            "import sys; from setuptools import build_meta; "
            f"print('BUILT', build_meta.build_{kind}(sys.argv[1]))"
        )
        completed = subprocess.run(
            [sys.executable, "-c", script, str(out)],
            cwd=tree,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        assert completed.returncode == 0, completed.stderr[-2000:]
        built[kind] = out / completed.stdout.strip().splitlines()[-1].split()[1]
    return built


def _sdist_members(path: Path) -> dict[str, bytes]:
    """Members by path below the sdist's top directory, with their content."""
    with tarfile.open(path) as archive:
        members = {}
        for member in archive.getmembers():
            handle = archive.extractfile(member) if member.isfile() else None
            if handle is not None:
                members[member.name.split("/", 1)[1]] = handle.read()
    return members


def _wheel_members(path: Path) -> dict[str, bytes]:
    with zipfile.ZipFile(path) as archive:
        return {name: archive.read(name) for name in archive.namelist() if not name.endswith("/")}


def _casadi_tree_hashes() -> set[str]:
    """The SHA-256 of every non-empty file of the audited CasADi tree (P03's record).

    Its notice files are left out: they are standard licence texts (the Apache-2.0 text is
    byte-identical to the project's own `LICENSE`), not CasADi's bytes.
    """
    audited = load_json(REPO_ROOT / "spikes" / "p03" / "results" / "casadi-inventory.json")
    return {
        entry["sha256"]
        for entry in audited["files"]
        if entry["bytes"] > 0 and not entry["path"].startswith(("include/licenses/", "LICENSE/"))
    }


BINARY = re.compile(r"\.(so(\.\d+)*|a|whl|dylib|dll|pyd)$", re.IGNORECASE)


def _casadi_files(files: dict[str, bytes], casadi_tree: set[str]) -> list[str]:
    """Paths that are CasADi's: a compiled object or a wheel by name, or a CasADi file by content.

    By content, not by a `casadi/` directory name: `stubs/casadi/__init__.pyi` is the project's own
    typing stub (it replaces the wheel's malformed one); P02's `spikes/p02/casadi/` is a harness.
    """
    return sorted(
        path
        for path, content in files.items()
        if BINARY.search(path) or (content and hashlib.sha256(content).hexdigest() in casadi_tree)
    )


def test_a31_no_file_of_a_casadi_tree_is_tracked() -> None:
    """ADR 0006 D5.5: mode B cannot begin by accident."""
    files = {
        path: (REPO_ROOT / path).read_bytes() for path in _tracked() if (REPO_ROOT / path).is_file()
    }
    assert _casadi_files(files, _casadi_tree_hashes()) == []


def test_a31_the_wheel_and_sdist_carry_no_casadi_bytes_and_carry_licence_and_notice(
    built: dict[str, Path],
) -> None:
    casadi_tree = _casadi_tree_hashes()
    sdist = _sdist_members(built["sdist"])
    wheel = _wheel_members(built["wheel"])
    assert _casadi_files(sdist, casadi_tree) == []
    assert _casadi_files(wheel, casadi_tree) == []
    assert not any(name.split("/", 1)[0] == "casadi" for name in wheel)
    licences = {
        name.rsplit("/", 1)[-1]: content
        for name, content in wheel.items()
        if re.match(r"[^/]+\.dist-info/licenses/[^/]+$", name)
    }
    for name in ("LICENSE", "NOTICE"):
        expected = (REPO_ROOT / name).read_bytes()
        assert sdist.get(name) == expected, name
        assert licences.get(name) == expected, name


def test_a31_readme_states_casadi_is_lgpl() -> None:
    """ADR 0006 D3.2(1), D5.1: the mode-A notice statement."""
    readme = " ".join((REPO_ROOT / "README.md").read_text(encoding="utf-8").split())
    assert "This software uses **CasADi 3.8.0**" in readme
    assert "GNU Lesser General Public License, version 3 or later (LGPL-3.0-or-later)" in readme


# The project's own package data (`pyproject.toml` [tool.setuptools.package-data]); anything else
# that is not Python source or packaging metadata would be data the release ships. Since T08 W4.2
# that includes the runtime data under `_data/`: the published schemas and three of the project's
# registered documents (K04's numerical policy, SYN-001's synthetic variants, and T08's numerical
# policy of ADR 0025), byte copies of the repository files (`openflowsheet.resources`; T08.A43
# compares the bytes). Since M01 (spec §3.5, §15 Q-N4's default) it also includes the five C1
# component records, published constants with their citations and rights, which the provider
# `pr-c1-v1` reads at run time; the reference tools' data stays out.
SHIPPED_DATA = re.compile(
    r"^(src/)?openflowsheet/(py\.typed|application/bindings/descriptions/([a-z_]+\.md|REVIEW\.json)"
    r"|_data/schemas/[a-z0-9-]+\.schema\.json|_data/benchmarks/(k04|syn001)/reference_values\.yaml"
    r"|_data/benchmarks/t08/numerical_policy_v2\.yaml|_data/benchmarks/m01/components\.yaml"
    # M02 (register R-317 (b)): the external addendum whose `compare` rules a coupled replay reads.
    r"|_data/benchmarks/m02/numerical_policy_external\.yaml"
    # E01 (ADR 0052): the synthetic LCA background table, authored in this repository.
    r"|_data/assessment/lca/test-background-v1\.json"
    # M02 design note §3.1: the registered variants and their registry (the project's own data).
    r"|adapters/variants/[a-z0-9.-]+\.json"
    # M02 design note §2.4: the reactor environment's lock — the project's own pin file (names,
    # versions and hashes of distributions it installs elsewhere; none of their content).
    r"|adapters/pymrm/reactor-env\.lock)$"
)
PACKAGING = re.compile(
    r"^(PKG-INFO|setup\.cfg|pyproject\.toml|README\.md|MANIFEST\.in|LICENSE|NOTICE|"
    r"src/openflowsheet\.egg-info/[A-Za-z_.-]+|openflowsheet-[^/]+\.dist-info/.+)$"
)


# S05 spec §16.12 (R-617): third-party data shipped under recorded terms, admitted only with its
# hash and with its attribution in the same artifact's NOTICE (Frank, C10 "Ship decision", R-616).
ATTRIBUTED_DATA = {
    "openflowsheet/_data/benchmarks/s05/iapws95_coefficients.json": (
        "b9e93877e37874f1b3a483e298a45692e264d70686d4c158372084b96abbe6ed"
    ),
    # E01 (ADR 0052): the six third-party assessment data files, under the same rule, each with
    # its own attribution (`E01_ATTRIBUTION`) in NOTICE.
    "openflowsheet/_data/assessment/cost/chains.json": (
        "d4707a829a9ed6136c7cd06b5e398dd1831ad6b1504af1dfbfe296e56e99fd52"
    ),
    "openflowsheet/_data/assessment/cost/sslw-idaes-v1.json": (
        "23d103d897d01c436f191285e38f305ff4374e42aa75c7f2c5a080984dbef6fb"
    ),
    "openflowsheet/_data/assessment/index/bls-ppi-wpu11-annual-v1.json": (
        "1c36f463a0a61123f7b71d82c848954aae61305a0a550a735cefb3c77c4ba578"
    ),
    "openflowsheet/_data/assessment/index/eurostat-ppi-c28-ea-annual-v1.json": (
        "a16dad15929cf747c57621b104ee15ce4a885215ae00442396bc81fd977a5529"
    ),
    "openflowsheet/_data/assessment/index/frb-g5a-annual-v1.json": (
        "0be392930ed58c6c035e274cdcfbdfe058eced3dd8a79c573bf0c71ab5cc78a6"
    ),
    "openflowsheet/_data/assessment/lca/gwp100-ipcc-ar6-v1.json": (
        "9b307aad8fa5faae7dba951b4097b4eebe030436019cd16a113fc71e11b808de"
    ),
}
IAPWS_ATTRIBUTION = (
    "\u00a9 2018 International Association for the Properties of Water and Steam",
    "Publication in whole or in part is allowed in all countries provided that attribution is "
    "given to the International Association for the Properties of Water and Steam",
    "Please cite as: International Association for the Properties of Water and Steam, IAPWS "
    "R6-95(2018), Revised Release on the IAPWS Formulation 1995 for the Thermodynamic "
    "Properties of Ordinary Water Substance for General and Scientific Use (2018)",
)


#: E01's attribution strings per file: the IDAES BSD licence's conditions and disclaimer (its
#: second condition asks a binary redistribution to reproduce them), and each source's citation.
E01_ATTRIBUTION = {
    "openflowsheet/_data/assessment/cost/chains.json": (
        "Charalambous et al., Nature 632 (2024), doi:10.1038/s41586-024-07683-8",
        "Creative Commons Attribution licence (CC BY)",
    ),
    "openflowsheet/_data/assessment/cost/sslw-idaes-v1.json": (
        "of the IDAES PSE Framework 2.13.0, which is distributed under this licence:",
        "Institute for the Design of Advanced Energy Systems Process Systems Engineering "
        "Framework (IDAES PSE Framework) Copyright (c) 2018-2026, by the software owners:",
        "2. Redistributions in binary form must reproduce the above copyright notice, this list "
        "of conditions and the following disclaimer in the documentation and/or other materials "
        "provided with the distribution.",
        "SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.",
    ),
    "openflowsheet/_data/assessment/index/bls-ppi-wpu11-annual-v1.json": (
        "Source: U.S. Bureau of Labor Statistics via FRED, Federal Reserve Bank of St. Louis.",
    ),
    "openflowsheet/_data/assessment/index/eurostat-ppi-c28-ea-annual-v1.json": (
        "Source: Eurostat.",
        "Creative Commons Attribution 4.0 International",
    ),
    "openflowsheet/_data/assessment/index/frb-g5a-annual-v1.json": (
        "Source: Board of Governors of the Federal Reserve System, via FRED",
    ),
    "openflowsheet/_data/assessment/lca/gwp100-ipcc-ar6-v1.json": (
        "IPCC AR6 WG1 Chapter 7, Table 7.15 (\u00a9 2021 IPCC)",
        "doi:10.1017/9781009157896.009",
    ),
}
#: The NOTICE before E01's section (bytes): it attributes the IAPWS file and none of E01's.
PRE_E01_NOTICE_BYTES = 2237


def _attributed(name: str, content: bytes, notice: bytes) -> bool:
    path = name.removeprefix("src/")
    if path not in ATTRIBUTED_DATA:
        return False
    text = " ".join(notice.decode("utf-8").split())
    strings = E01_ATTRIBUTION.get(path, IAPWS_ATTRIBUTION)
    return (
        hashlib.sha256(content).hexdigest() == ATTRIBUTED_DATA[path]
        and path in text
        and all(" ".join(string.split()) in text for string in strings)
    )


def test_a32_no_third_party_data_in_the_sdist_or_the_wheel(built: dict[str, Path]) -> None:
    """Amended for one attributed file by S05 spec §16.12 (R-617), and for E01's six (ADR 0052)
    under the same rule."""
    for kind in ("sdist", "wheel"):
        contents = (_sdist_members if kind == "sdist" else _wheel_members)(built[kind])
        members = list(contents)
        assert any(name.endswith("openflowsheet/__init__.py") for name in members), kind
        notice_name = r"NOTICE" if kind == "sdist" else r"[^/]+\.dist-info/licenses/NOTICE"
        notices = [name for name in members if re.fullmatch(notice_name, name)]
        assert len(notices) == 1, kind
        notice = contents[notices[0]]
        admitted = [name for name in members if _attributed(name, contents[name], notice)]
        prefix = "src/" if kind == "sdist" else ""
        assert sorted(admitted) == sorted(prefix + path for path in ATTRIBUTED_DATA), kind
        if kind == "wheel":
            iapws = "openflowsheet/_data/benchmarks/s05/iapws95_coefficients.json"
            name, content = iapws, contents[iapws]
            assert not _attributed(name, content, notice[:1292])
            assert not _attributed(name, content + b"\n", notice)
            assert not _attributed("openflowsheet/_data/benchmarks/s05/x.json", content, notice)
            for path in E01_ATTRIBUTION:
                assert _attributed(path, contents[path], notice), path
                assert not _attributed(path, contents[path], notice[:PRE_E01_NOTICE_BYTES]), path
                assert not _attributed(path, contents[path] + b"\n", notice), path
        other = [
            name
            for name in members
            if not name.endswith(".py")
            and not SHIPPED_DATA.match(name)
            and not PACKAGING.match(name)
            and name not in admitted
        ]
        assert other == [], kind
        # Since T08 W4.2 `MANIFEST.in` prunes `tests/` from the sdist (setuptools adds
        # `tests/test*.py` by default), so every Python file of either artifact is the package's.
        source = r"^(src/)?openflowsheet/" if kind == "wheel" else r"^src/openflowsheet/"
        python = [name for name in members if name.endswith(".py")]
        assert [name for name in python if not re.match(source, name)] == [], kind


def _component_records() -> list[tuple[str, dict[str, Any]]]:
    """Every component-record-shaped mapping in a tracked YAML or JSON file.

    The schema's negative fixtures (`tests/fixtures/schemas/component_record/invalid/`) are
    excluded: they are invalid by construction and ship nowhere.
    """
    found = []
    for path in _tracked():
        if not path.endswith((".yaml", ".yml", ".json")) or "/invalid/" in path:
            continue
        text = (REPO_ROOT / path).read_text(encoding="utf-8", errors="replace")
        if "elemental_verification" not in text:
            continue
        document = yaml.safe_load(text) if path.endswith((".yaml", ".yml")) else json.loads(text)
        stack = [document]
        while stack:
            item = stack.pop()
            if isinstance(item, dict):
                if "elemental_verification" in item and isinstance(item.get("id"), str):
                    found.append((path, item))
                stack.extend(item.values())
            elif isinstance(item, list):
                stack.extend(item)
    return found


def _m01_vetted(vetting: dict[str, Any], component: str, path: str) -> bool:
    """M01.A02's retrieval equality (M01 spec §3.5, R-158), unchanged."""
    del path
    entry = vetting["retrieval"][component]
    return bool(
        all(entry["equal"].values())
        and entry["nasa7_low_range_equal"]
        and entry["identifiers_equal"]
    )


def _l01_vetted(vetting: dict[str, Any], component: str, path: str) -> bool:
    """L01.A12's retrieval equality, of these bytes (L01 spec §12.4 (iv), R-529)."""
    equal = vetting["retrieval"][component]["equal"]
    return (
        len(equal) == 13
        and all(flag is True for flag in equal.values())
        and vetting["retrieval_all_equal"] is True
        and component not in vetting["retrieval_failures"]
        and vetting["records_sha256"] == sha256_of(REPO_ROOT / path)
    )


#: The twelve equalities of S10's vetting (S10 spec §18 A5-1, R-722), per record.
S10_VETTING_EQUALITIES = frozenset(
    {
        "name",
        "elemental_composition",
        "source_species",
        "no_identifiers",
        "parameter_keys_units",
        "molar_mass_ciaaw2021",
        "nasa7_low_range_decimal",
        "nasa7_range_200_1000",
        "nasa7_note_quoted",
        "formation_enthalpy_h298",
        "vapour_pressure_within_claim",
        "vapour_pressure_source_quoted",
    }
)


def _s10_vetted(vetting: dict[str, Any], component: str, path: str) -> bool:
    """S10's vetting of these bytes and of these inputs (S10 spec §18 A5-1 (iv), R-722)."""
    equal = vetting["retrieval"][component]["equal"]
    inputs = vetting["inputs_sha256"]
    return (
        set(equal) == S10_VETTING_EQUALITIES
        and all(flag is True for flag in equal.values())
        and vetting["retrieval_all_equal"] is True
        and vetting["retrieval_failures"] == []
        and vetting["nasa7_retrieval"]["equal"][component] is True
        and vetting["records_sha256"] == sha256_of(REPO_ROOT / path)
        and set(inputs)
        == {"benchmarks/s10/nasa7-low.json", "benchmarks/s10/saturation-points.json"}
        and all(digest == sha256_of(REPO_ROOT / name) for name, digest in inputs.items())
    )


#: T08.A32's vetted record files (M01 spec §3.5, R-158; L01 spec §12.4, R-529; S10 spec §18 A5-1,
#: R-722): the only files whose real (`synthetic: false`) records the repository may hold, each
#: with its registered ids, the JSON that vets them and the retrieval predicate (iv). Adding a file
#: takes a design-lane amendment that names its vetting.
VETTED_RECORD_FILES: dict[str, tuple[tuple[str, ...], Path, Any]] = {
    "benchmarks/m01/components.yaml": (
        ("H2", "N2", "NH3", "Ar", "CH4"),
        REPO_ROOT / "benchmarks" / "m01" / "external-crosscheck.json",
        _m01_vetted,
    ),
    "benchmarks/l01/components.yaml": (
        ("H2", "N2", "Ar", "CH4", "H2O", "CO2", "O2", "C2H6", "C3H8"),
        REPO_ROOT / "benchmarks" / "l01" / "components-crosscheck.json",
        _l01_vetted,
    ),
    "benchmarks/s10/records.yaml": (
        ("CH3OH", "C2H5OH", "H2O"),
        REPO_ROOT / "benchmarks" / "s10" / "records-vetting.json",
        _s10_vetted,
    ),
}

#: Vetted files whose records carry no `identifiers` (no CAS RN, InChI or InChIKey: R-706, S10
#: spec §9.1). For these, (ii) is replaced by (ii'): no `identifiers` key, and the record's name and
#: elemental composition equal the registered pair (S10 spec §18 A5-1, R-722).
IDENTITY_WITHOUT_IDENTIFIERS: dict[str, dict[str, tuple[str, dict[str, int]]]] = {
    "benchmarks/s10/records.yaml": {
        "CH3OH": ("methanol", {"C": 1, "H": 4, "O": 1}),
        "C2H5OH": ("ethanol", {"C": 2, "H": 6, "O": 1}),
        "H2O": ("water", {"H": 2, "O": 1}),
    },
}

#: Parameters that are a reference convention's formation datum rather than a property of the
#: substance (ADR 0001 D5; R-704): (v) compares them within a convention, (v') never across
#: conventions, whose streams never mix (ADR 0001 D5.2). S10 spec §18 A5-1, R-722.
CONVENTION_DATUM_PARAMETERS = frozenset({"standard_formation_enthalpy"})
#: The fields of a shared parameter that (v') compares across conventions.
CROSS_CONVENTION_FIELDS = ("value", "unit", "dimension", "kind")

#: T08.A32 (vi) (S11 rulings item 1, R-830): the provider-identity record files, each with its
#: provider and registered ids. They are not vetted files: their records hold no property datum
#: (`parameters: {}`), only identity and a molar mass equal to the provider's own constant, so a
#: `synthetic: false` record in one is judged by (i-p), (ii-p), (iii), (iv-p) and (v-p) in place of
#: (ii), (iv), (v) and (v'). Adding a file takes a design-lane amendment that names its provider.
PROVIDER_IDENTITY_RECORD_FILES: dict[str, tuple[str, tuple[str, ...]]] = {
    "benchmarks/s05/components.yaml": ("iapws95-v1", ("H2O",)),
    "benchmarks/s07/components.yaml": ("coolprop-heos-v1", tuple(row["id"] for row in FLUIDS)),
}
#: (i-p): each provider's reference convention.
PROVIDER_CONVENTIONS = {"iapws95-v1": "IAPWS95-ref-v1", "coolprop-heos-v1": "COOLPROP-DEF-ref-v1"}
#: (v-p): the ids a provider-identity record shares with another real record that carries a CAS RN,
#: whose CAS RNs are compared (measured at R-830: 9 ids, all equal).
CAS_COMPARED_IDS = frozenset({"Ar", "C2H6", "C3H8", "CH4", "CO2", "H2", "H2O", "N2", "O2"})


def _provider_identity(provider: str) -> dict[str, tuple[str, float, str]]:
    """(ii-p), (iv-p): the provider's own (CAS RN, molar mass, name) per id: IAPWS-95's constant,
    or each row of S07's `FLUIDS` (vetted by S05 and S07 A01/C19, never by these files)."""
    if provider == "iapws95-v1":
        return {"H2O": ("7732-18-5", iapws95.M, "water")}
    return {row["id"]: (row["cas"], row["M"], row["name"]) for row in FLUIDS}


def _provider_identity_problems(single: str, record: dict[str, Any], convention: str) -> list[str]:
    """(i-p)'s convention, (ii-p) and (iv-p) for one `synthetic: false` record of a
    provider-identity file (T08.A32 (vi), R-830); (i-p)'s registered id is checked with (i)."""
    provider, _ = PROVIDER_IDENTITY_RECORD_FILES[single]
    where = f"{single}:{record['id']}"
    problems = []
    if convention != PROVIDER_CONVENTIONS[provider]:
        problems.append(f"(i-p) {where}: reference_convention {convention}")
    expected = _provider_identity(provider).get(record["id"])
    if expected is None:
        return problems
    cas, molar_mass, name = expected
    found = str((record.get("identifiers") or {}).get("cas", "")).strip()
    if not found or found != cas:
        problems.append(f"(ii-p) {where}: CAS RN {found!r} is not the provider's {cas!r}")
    if record["parameters"] != {}:
        problems.append(f"(iv-p) {where}: parameters {sorted(record['parameters'])}")
    if record["molecular_weight"]["value"] != molar_mass:
        problems.append(f"(iv-p) {where}: molar mass is not the provider's")
    if record["name"] != name:
        problems.append(f"(iv-p) {where}: name {record['name']!r} is not {name!r}")
    if provider == "iapws95-v1" and (
        (record.get("identifiers") or {}).get("formula") != "H2O"
        or record["elemental_composition"] != {"H": 2, "O": 1}
    ):
        problems.append(f"(iv-p) {where}: formula or elemental composition")
    return problems


def _one_datum_problems(copies: dict[str, tuple[str, dict[str, Any]]]) -> list[str]:
    """(v) and (v') for one id; `copies` maps each vetted file to (its convention, the record).

    (v): within one reference convention, the same whole mapping in every file. (v'): across
    conventions, the same name and elemental composition, at least one shared parameter outside
    `CONVENTION_DATUM_PARAMETERS`, and every such shared parameter equal in
    `CROSS_CONVENTION_FIELDS`.
    """
    problems = []
    groups: dict[str, list[tuple[str, dict[str, Any]]]] = {}
    for path, (convention, record) in sorted(copies.items()):
        groups.setdefault(convention, []).append((path, record))
    for convention, group in groups.items():
        first_path, first = group[0]
        for path, record in group[1:]:
            if record != first:
                problems.append(f"(v) {path} != {first_path} under {convention}")
    heads = [(convention, *group[0]) for convention, group in groups.items()]
    for index, (c0, p0, r0) in enumerate(heads):
        for c1, p1, r1 in heads[index + 1 :]:
            where = f"(v') {p0} ({c0}) and {p1} ({c1})"
            if (r0["name"], r0["elemental_composition"]) != (
                r1["name"],
                r1["elemental_composition"],
            ):
                problems.append(f"{where}: identity differs")
            shared = (set(r0["parameters"]) & set(r1["parameters"])) - CONVENTION_DATUM_PARAMETERS
            if not shared:
                problems.append(f"{where}: no shared parameter outside the conventions' data")
            for key in sorted(shared):
                q0, q1 = r0["parameters"][key], r1["parameters"][key]
                if any(q0[field] != q1[field] for field in CROSS_CONVENTION_FIELDS):
                    problems.append(f"{where}: {key} differs")
    return problems


def _vetted_conventions() -> dict[str, str]:
    """The reference convention of each vetted and each provider-identity file."""
    return {
        path: yaml.safe_load((REPO_ROOT / path).read_text(encoding="utf-8"))["reference_convention"]
        for path in (*VETTED_RECORD_FILES, *PROVIDER_IDENTITY_RECORD_FILES)
    }


def _a32_problems(
    records: list[tuple[str, dict[str, Any]]], conventions: dict[str, str]
) -> tuple[list[str], frozenset[str]]:
    """T08.A32's rules on `records` (as `_component_records` gives them), each problem tagged by
    its clause, and the ids (v-p) compared. The rules are the test's docstring's."""
    validator = validator_for("component_record")
    vettings = {
        path: load_json(json_path) for path, (_, json_path, _) in VETTED_RECORD_FILES.items()
    }
    problems: list[str] = []
    real = []
    by_id: dict[str, dict[str, tuple[str, dict[str, Any]]]] = {}
    cas_by_id: dict[str, dict[str, str]] = {}
    provider_held: set[str] = set()
    for path, record in records:
        where = f"{path}:{record['id']}"
        if [error.message for error in validator.iter_errors(record)]:
            problems.append(f"(schema) {where}")
            continue
        rights = record["rights"]
        if not (rights["source"].strip() and rights["redistribution"].strip()):
            problems.append(f"(iii) {where}: rights")
        if record["synthetic"] is True:
            continue
        if record["synthetic"] is not False:
            problems.append(f"(synthetic) {where}")
            continue
        # A package-data link (`src/openflowsheet/_data/benchmarks/m01/components.yaml`) is the
        # same single copy (`openflowsheet.resources`), not a second record.
        linked = (REPO_ROOT / path).is_symlink()
        single = (REPO_ROOT / path).resolve().relative_to(REPO_ROOT.resolve()).as_posix()
        provider_file = single in PROVIDER_IDENTITY_RECORD_FILES
        if provider_file:
            clause, ids = "(i-p)", PROVIDER_IDENTITY_RECORD_FILES[single][1]
        elif single in VETTED_RECORD_FILES:
            clause, ids = "(i)", VETTED_RECORD_FILES[single][0]
        else:
            problems.append(f"(i) {where}: not a vetted or provider-identity file")
            continue
        if record["id"] not in ids:
            problems.append(f"{clause} {where}: not a registered id")
            continue
        if not linked:
            real.append((single, record["id"]))
            cas = str((record.get("identifiers") or {}).get("cas", "")).strip()
            if cas:
                cas_by_id.setdefault(record["id"], {})[single] = cas
        quantities = [record["molecular_weight"], *record["parameters"].values()]
        if not all(str(quantity.get("provenance", "")).strip() for quantity in quantities):
            problems.append(f"(iii) {where}: provenance")
        if provider_file:  # (vi): (i-p), (ii-p), (iv-p); (v-p) below, never (v) or (v')
            problems += _provider_identity_problems(single, record, conventions[single])
            if not linked:
                provider_held.add(record["id"])
            continue
        if not linked:
            by_id.setdefault(record["id"], {})[single] = (conventions[single], record)
        identity = IDENTITY_WITHOUT_IDENTIFIERS.get(single)
        if identity is None:  # (ii)
            identifiers = record.get("identifiers") or {}
            keys = ("cas", "inchi", "inchikey")
            if not all(str(identifiers.get(key, "")).strip() for key in keys):
                problems.append(f"(ii) {where}")
        else:  # (ii')
            pair = (record["name"], record["elemental_composition"])
            if "identifiers" in record or pair != identity[record["id"]]:
                problems.append(f"(ii') {where}")
        _, _, vetted = VETTED_RECORD_FILES[single]
        if not vetted(vettings[single], record["id"], single):
            problems.append(f"(iv) {where}")
    for copies in by_id.values():  # (v), (v'): one datum per substance and convention
        problems += _one_datum_problems(copies)
    compared = frozenset(c for c in provider_held if len(cas_by_id.get(c, {})) > 1)
    for component in sorted(compared):  # (v-p): one CAS RN per id across the real records
        if len(set(cas_by_id[component].values())) != 1:
            problems.append(f"(v-p) {component}: CAS RNs differ {cas_by_id[component]}")
    if len(real) != len(set(real)):
        problems.append("(i) a real record appears twice")
    registered = {
        (path, component) for path, (ids, _, _) in VETTED_RECORD_FILES.items() for component in ids
    }
    registered |= {
        (path, component)
        for path, (_, ids) in PROVIDER_IDENTITY_RECORD_FILES.items()
        for component in ids
    }
    if set(real) != registered:
        problems.append(f"(i) the real (file, id) set differs: {sorted(set(real) ^ registered)}")
    return problems, compared


def test_a32_every_component_record_is_synthetic_or_a_vetted_real_record_with_rights() -> None:
    """T08.A32 as amended by M01 spec §3.5 (R-158), L01 spec §12.4 (R-529) and S10 spec §18 A5-1
    (R-722): amended for real records, not relaxed.

    A `synthetic: true` record keeps the v0.1 rule unchanged (it validates and states its rights).
    A `synthetic: false` record must (i) resolve, as a symlink resolves to its single copy, to a
    file of `VETTED_RECORD_FILES` and carry one of its ids, (ii) carry `identifiers` with `cas`,
    `inchi` and `inchikey`, or, in a file of `IDENTITY_WITHOUT_IDENTIFIERS`, (ii') carry no
    `identifiers` and the registered name and composition, (iii) carry non-empty `rights.source`
    and `rights.redistribution` and a `provenance` on every parameter and on the molecular weight,
    (iv) be covered by its file's retrieval equality, and (v) where its id is in more than one
    vetted file, be the same whole mapping in each file of the same reference convention, and
    (v') agree with the files of other conventions as `_one_datum_problems` states.

    (vi) (S11 rulings item 1, R-830): in a file of `PROVIDER_IDENTITY_RECORD_FILES` a
    `synthetic: false` record is judged by (i-p) one of its file's ids under the provider's
    convention, (ii-p) the provider's CAS RN, (iii), (iv-p) no datum (`parameters == {}`, the
    provider's molar mass float-equal, its name, and for IAPWS-95 the formula and composition), and
    (v-p) in place of (v) and (v'): for each id it shares with another real record carrying a CAS
    RN, the CAS RNs are equal, over exactly `CAS_COMPARED_IDS`.

    The real (file, id) pairs are the two registries', each once. Whether the rights statements are
    correct, and whether the records ship, is not decided here (L01-Q4, M01 Q-N4, S10 Q-F3).
    """
    records = _component_records()
    assert {(path, record["id"]) for path, record in records} >= {
        ("benchmarks/syn001/components.yaml", component) for component in ("A", "B", "C")
    }
    assert len(PROVIDER_IDENTITY_RECORD_FILES["benchmarks/s07/components.yaml"][1]) == 123
    problems, compared = _a32_problems(records, _vetted_conventions())
    assert problems == []
    assert compared == CAS_COMPARED_IDS


def test_a32_one_datum_rule_within_and_across_conventions() -> None:
    """(v) and (v') at registered states (S10 spec §18 A5-1, assertion T08.A32-v): H2O is held by
    L01 (`PR-C1-ref-v1`) and S10 (`WILSON-IG-ref-v1`), CH4 by M01 and L01 (both `PR-C1-ref-v1`)."""

    def record(path: str, component: str) -> dict[str, Any]:
        doc = yaml.safe_load((REPO_ROOT / path).read_text(encoding="utf-8"))
        return next(r for r in doc["components"] if r["id"] == component)

    l01, s10 = record("benchmarks/l01/components.yaml", "H2O"), record(S10_RECORDS, "H2O")
    m01_ch4, l01_ch4 = (record(p, "CH4") for p in ("benchmarks/m01/components.yaml", L01_RECORDS))
    across = {L01_RECORDS: ("PR-C1-ref-v1", l01), S10_RECORDS: ("WILSON-IG-ref-v1", s10)}
    assert _one_datum_problems(across) == []
    # What (v') leaves out differs at this state, so the exclusion is not vacuous: the datum
    # (ATcT against the NASA polynomial's own H(298.15 K)) and the molar mass (two tables).
    datum = "standard_formation_enthalpy"
    assert l01["parameters"][datum]["value"] != s10["parameters"][datum]["value"]
    assert l01["molecular_weight"]["value"] != s10["molecular_weight"]["value"]
    within = {"benchmarks/m01/components.yaml": ("PR-C1-ref-v1", m01_ch4)}
    within[L01_RECORDS] = ("PR-C1-ref-v1", l01_ch4)
    assert _one_datum_problems(within) == []
    # (v) is unchanged within a convention: the two H2O records under one label fail.
    same = {L01_RECORDS: ("PR-C1-ref-v1", l01), S10_RECORDS: ("PR-C1-ref-v1", s10)}
    assert _one_datum_problems(same) == [f"(v) {S10_RECORDS} != {L01_RECORDS} under PR-C1-ref-v1"]
    nudged = copy.deepcopy(s10)
    nudged["parameters"]["ideal_gas_cp_b0"]["value"] = math.nextafter(4.19864056, math.inf)
    renamed = copy.deepcopy(s10)
    renamed["name"] = "steam"
    datum_only = copy.deepcopy(s10)
    datum_only["parameters"] = {datum: s10["parameters"][datum]}
    where = f"(v') {L01_RECORDS} (PR-C1-ref-v1) and {S10_RECORDS} (WILSON-IG-ref-v1)"
    for mutated, expected in (
        (nudged, f"{where}: ideal_gas_cp_b0 differs"),
        (renamed, f"{where}: identity differs"),
        (datum_only, f"{where}: no shared parameter outside the conventions' data"),
    ):
        problems = _one_datum_problems({**across, S10_RECORDS: ("WILSON-IG-ref-v1", mutated)})
        assert problems == [expected]


def test_a32_provider_identity_predicate_refuses_each_defect() -> None:
    """T08.A32 (vi) (S11 rulings item 1, R-830): the committed records pass, and each single defect
    fails the clause that exists to catch it."""
    records = _component_records()
    conventions = _vetted_conventions()
    assert _a32_problems(records, conventions) == ([], CAS_COMPARED_IDS)
    s05, s07 = "benchmarks/s05/components.yaml", "benchmarks/s07/components.yaml"
    n2_cas = next(row["cas"] for row in FLUIDS if row["id"] == "N2")

    def at(mutated: list[tuple[str, dict[str, Any]]], path: str, cid: str) -> dict[str, Any]:
        return next(r for p, r in mutated if p == path and r["id"] == cid)

    def parameter(m: list[tuple[str, dict[str, Any]]]) -> None:
        h2o = at(m, s05, "H2O")
        h2o["parameters"]["molar_mass_copy"] = copy.deepcopy(h2o["molecular_weight"])

    def molar_mass(m: list[tuple[str, dict[str, Any]]]) -> None:
        weight = at(m, s07, "CO2")["molecular_weight"]
        weight["value"] = math.nextafter(weight["value"], math.inf)

    def cas(m: list[tuple[str, dict[str, Any]]]) -> None:
        at(m, s07, "CO2")["identifiers"]["cas"] = n2_cas

    def name(m: list[tuple[str, dict[str, Any]]]) -> None:
        at(m, s07, "Ar")["name"] = "Argon2"

    def unknown_id(m: list[tuple[str, dict[str, Any]]]) -> None:
        at(m, s07, "CO2")["id"] = "CO2-not-a-fluid"

    def unregistered_file(m: list[tuple[str, dict[str, Any]]]) -> None:
        m.append(("benchmarks/s05/components-copy.yaml", copy.deepcopy(at(m, s05, "H2O"))))

    for defect, expected, conventions_change in (
        (parameter, {"(iv-p)"}, {}),
        (molar_mass, {"(iv-p)"}, {}),
        (cas, {"(ii-p)", "(v-p)"}, {}),
        (name, {"(iv-p)"}, {}),
        (unknown_id, {"(i-p)"}, {}),
        (unregistered_file, {"(i)"}, {}),
        (None, {"(i-p)"}, {s05: "PR-C1-ref-v1"}),
    ):
        mutated = copy.deepcopy(records)
        if defect is not None:
            defect(mutated)
        problems, _ = _a32_problems(mutated, {**conventions, **conventions_change})
        clauses = {problem.split(" ", 1)[0] for problem in problems}
        label = defect.__name__ if defect is not None else "convention"
        assert expected <= clauses, (label, problems)


def test_a32_s10_vetting_predicate_refuses_each_defect() -> None:
    """`_s10_vetted` (S10 spec §18 A5-1 (iv)) holds on the committed vetting and fails on each
    single defect: a false or missing equality, a recorded failure, the NASA re-read false, a
    stale records hash, a stale or extra input hash."""
    vetting = load_json(REPO_ROOT / "benchmarks" / "s10" / "records-vetting.json")
    assert isinstance(vetting, dict)
    assert all(_s10_vetted(vetting, cid, S10_RECORDS) for cid in ("CH3OH", "C2H5OH", "H2O"))

    def false_flag(v: dict[str, Any]) -> None:
        v["retrieval"]["H2O"]["equal"]["formation_enthalpy_h298"] = False

    def missing_flag(v: dict[str, Any]) -> None:
        del v["retrieval"]["H2O"]["equal"]["no_identifiers"]

    def failure(v: dict[str, Any]) -> None:
        v["retrieval_failures"] = ["CH3OH.name"]

    def nasa(v: dict[str, Any]) -> None:
        v["nasa7_retrieval"]["equal"]["H2O"] = False

    def records_hash(v: dict[str, Any]) -> None:
        v["records_sha256"] = "0" * 64

    def input_hash(v: dict[str, Any]) -> None:
        v["inputs_sha256"]["benchmarks/s10/saturation-points.json"] = "0" * 64

    def extra_input(v: dict[str, Any]) -> None:
        v["inputs_sha256"]["benchmarks/s10/fit-report.json"] = sha256_of(
            REPO_ROOT / "benchmarks" / "s10" / "fit-report.json"
        )

    for defect in (false_flag, missing_flag, failure, nasa, records_hash, input_hash, extra_input):
        mutated = copy.deepcopy(vetting)
        defect(mutated)
        assert not _s10_vetted(mutated, "H2O", S10_RECORDS), defect.__name__


def test_a32_the_envelope_states_reference_data_and_openidaes_are_not_distributed() -> None:
    envelope = yaml.safe_load(
        (REPO_ROOT / "benchmarks" / "t08" / "support_envelope.yaml").read_text(encoding="utf-8")
    )
    rows = [*envelope["unsupported"], *envelope["limitations"]]
    texts = [
        " ".join(str(row.get(key, "")) for key in ("capability", "outcome", "text")) for row in rows
    ]
    stating = [
        text
        for text in texts
        if "not distributed" in text and "OpenIDAES-450" in text and "reference" in text.lower()
    ]
    assert stating, (
        "no envelope row states the reference-tool data and OpenIDAES-450 are not distributed"
    )
