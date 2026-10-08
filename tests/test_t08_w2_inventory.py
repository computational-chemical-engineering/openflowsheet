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

import hashlib
import json
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

SUMMARIES = REPO_ROOT / "docs" / "t08-a30"
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
    r"|_data/benchmarks/t08/numerical_policy_v2\.yaml|_data/benchmarks/m01/components\.yaml)$"
)
PACKAGING = re.compile(
    r"^(PKG-INFO|setup\.cfg|pyproject\.toml|README\.md|MANIFEST\.in|LICENSE|NOTICE|"
    r"src/openflowsheet\.egg-info/[A-Za-z_.-]+|openflowsheet-[^/]+\.dist-info/.+)$"
)


def test_a32_no_third_party_data_in_the_sdist_or_the_wheel(built: dict[str, Path]) -> None:
    for kind in ("sdist", "wheel"):
        members = list((_sdist_members if kind == "sdist" else _wheel_members)(built[kind]))
        assert any(name.endswith("openflowsheet/__init__.py") for name in members), kind
        other = [
            name
            for name in members
            if not name.endswith(".py")
            and not SHIPPED_DATA.match(name)
            and not PACKAGING.match(name)
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


#: M01 spec §3.5 (R-158): the only real (`synthetic: false`) records the repository may hold, each
#: vetted by M01.A02's retrieval equality in `benchmarks/m01/external-crosscheck.json`.
M01_RECORDS = "benchmarks/m01/components.yaml"
M01_COMPONENTS = ("H2", "N2", "NH3", "Ar", "CH4")
M01_CROSSCHECK = REPO_ROOT / "benchmarks" / "m01" / "external-crosscheck.json"


def test_a32_every_component_record_is_synthetic_or_a_vetted_m01_record_with_rights() -> None:
    """T08.A32 as amended by M01 spec §3.5 (R-158): amended for real records, not relaxed.

    A `synthetic: true` record keeps the v0.1 rule unchanged (it validates and states its rights).
    A `synthetic: false` record must (i) be one of the five records of
    `benchmarks/m01/components.yaml`, (ii) carry `identifiers` with `cas`, `inchi` and `inchikey`,
    (iii) carry non-empty `rights.source` and `rights.redistribution` and a `provenance` on every
    parameter and on the molecular weight, and (iv) be covered by M01.A02's retrieval equality.
    """
    validator = validator_for("component_record")
    records = _component_records()
    assert {(path, record["id"]) for path, record in records} >= {
        ("benchmarks/syn001/components.yaml", component) for component in ("A", "B", "C")
    }
    retrieval = load_json(M01_CROSSCHECK)["retrieval"]
    real = []
    for path, record in records:
        where = (path, record["id"])
        assert [error.message for error in validator.iter_errors(record)] == [], where
        rights = record["rights"]
        assert rights["source"].strip() and rights["redistribution"].strip(), where
        if record["synthetic"] is True:
            continue
        assert record["synthetic"] is False, where
        # The package-data link `src/openflowsheet/_data/benchmarks/m01/components.yaml` is the
        # same single copy (`openflowsheet.resources`), not a second record.
        linked = (REPO_ROOT / path).is_symlink()
        single = (REPO_ROOT / path).resolve().relative_to(REPO_ROOT.resolve()).as_posix()
        assert single == M01_RECORDS and record["id"] in M01_COMPONENTS, where  # (i)
        if not linked:
            real.append(where)
        identifiers = record["identifiers"]
        assert all(identifiers.get(key, "").strip() for key in ("cas", "inchi", "inchikey")), where
        quantities = [record["molecular_weight"], *record["parameters"].values()]
        assert all(str(quantity.get("provenance", "")).strip() for quantity in quantities), where
        vetted = retrieval[record["id"]]  # (iv)
        assert all(vetted["equal"].values()) and vetted["nasa7_low_range_equal"], where
        assert vetted["identifiers_equal"], where
    assert len(real) == len(set(real)), "a real record appears twice"
    assert set(real) == {(M01_RECORDS, component) for component in M01_COMPONENTS}


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
