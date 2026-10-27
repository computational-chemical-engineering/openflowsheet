"""S07.A29-A31 (spec §9, §12.3 WO-S07-3): no redistribution, library-only registration, and the
cross-architecture digest.

A29 reads files (`PACKAGED`, the pyproject, ref's key set) and, where `OFS_S07_BUILD_PYTHON` names a
Python with T08.A43's setuptools (the manifest generator sets it), a built sdist and wheel.
A30 reads
the registry and the harvest. A31 recomputes the provider's answers (CoolProp: `require_coolprop()`)
and compares them with `benchmarks/s07/platform_digest.json`, which `scripts/s07_platform_digest.py`
wrote on x86-64 (a regression fixture, not validation); on `ubuntu-24.04-arm` the same tests judge
each row by its class under spec §20 (R-627), A31a-A31e.
"""

from __future__ import annotations

import ast
import copy
import importlib.util
import json
import os
import platform
import sys
import tomllib
import zipfile
from pathlib import Path, PurePosixPath
from types import ModuleType
from typing import Any

import pytest
from conftest import REPO_ROOT
from s07_coolprop_support import require_coolprop

from openflowsheet.application import revision_binding
from openflowsheet.resources import PACKAGED

SCRIPTS = REPO_ROOT / "docs" / "derivations" / "scripts"
REFERENCE = SCRIPTS / "s07_reference.json"
GENERATOR = SCRIPTS / "s07_reference.py"
PROVIDER_ID = "coolprop-heos-v1"
#: A Python with `setuptools` (T08.A43's pin) to build the sdist and the wheel.
BUILD_PYTHON = os.environ.get("OFS_S07_BUILD_PYTHON")


def _script(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / "scripts" / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# -- A29: no redistribution ------------------------------------------------------------------------


def _covers(entry: str, path: str) -> bool:
    entry_parts, path_parts = PurePosixPath(entry).parts, PurePosixPath(path).parts
    return path_parts[: len(entry_parts)] == entry_parts or entry_parts[: len(path_parts)] == (
        path_parts
    )


def test_a29_a_no_packaged_path_covers_the_reference_or_the_generators() -> None:
    forbidden = (
        "docs/derivations/scripts/s07_reference.json",
        "docs/derivations/scripts",
        "docs/derivations/scripts/s07_reference.py",
        "docs",
    )
    covering = [(entry, path) for entry in PACKAGED for path in forbidden if _covers(entry, path)]
    assert covering == []
    # control: `_covers` does cover a path below a packaged entry and a packaged file itself
    assert _covers("schemas", "schemas/component-record.schema.json")
    assert _covers("benchmarks/s05/iapws95_coefficients.json", "benchmarks/s05")
    assert not any(entry.startswith("benchmarks/s07") for entry in PACKAGED)


def _project() -> dict[str, Any]:
    with (REPO_ROOT / "pyproject.toml").open("rb") as handle:
        return tomllib.load(handle)["project"]


def test_a29_b_the_default_requirements_name_coolprop_only_under_the_extra() -> None:
    project = _project()
    assert [d for d in project.get("dependencies", []) if "coolprop" in d.lower()] == []
    assert project["optional-dependencies"]["coolprop"] == ["CoolProp==8.0.0"]
    others = {
        name: [d for d in requirements if "coolprop" in d.lower()]
        for name, requirements in project["optional-dependencies"].items()
        if name != "coolprop"
    }
    assert all(not found for found in others.values()), others


def test_a29_c_the_reference_key_set_is_c3s_whitelist() -> None:
    """C3's whitelist is read from the generator's own literals (`TOP_KEYS`, `FLUID_KEYS_B`,
    `FLUID_KEYS_A`), without importing it (it needs mpmath)."""
    tree = ast.parse(GENERATOR.read_text("utf-8"))
    values: dict[str, set[str]] = {}
    for statement in tree.body:
        if isinstance(statement, ast.Assign) and len(statement.targets) == 1:
            target = statement.targets[0]
            if isinstance(target, ast.Name) and target.id in {
                "TOP_KEYS",
                "FLUID_KEYS_B",
                "FLUID_KEYS_A",
            }:
                expression = ast.Expression(statement.value)
                code = compile(expression, "<whitelist>", "eval")
                values[target.id] = eval(code, {"__builtins__": {}}, dict(values))  # noqa: S307
    assert set(values) == {"TOP_KEYS", "FLUID_KEYS_B", "FLUID_KEYS_A"}
    reference = json.loads(REFERENCE.read_text("utf-8"))
    assert set(reference) == values["TOP_KEYS"]
    tiers = {row["tier"] for row in reference["fluids"].values()}
    assert tiers == {"A", "B"}
    for cid, fluid in reference["fluids"].items():
        want = values["FLUID_KEYS_A"] if fluid["tier"] == "A" else values["FLUID_KEYS_B"]
        assert set(fluid) == want, cid
    # control: a coefficient-like extra key is a difference
    mutated = copy.deepcopy(reference)
    mutated["fluids"]["H2O"]["coefficients"] = [1.0]
    assert set(mutated["fluids"]["H2O"]) != values["FLUID_KEYS_A"]


@pytest.mark.skipif(not BUILD_PYTHON, reason="OFS_S07_BUILD_PYTHON (a Python with setuptools)")
def test_a29_a_built_sdist_and_wheel_hold_no_coolprop_file_and_no_fluid_json(
    tmp_path: Path,
) -> None:
    dist = _script("t08_dist")
    built = dist.build_once(Path(str(BUILD_PYTHON)), "HEAD", tmp_path, "1700000000")
    sdist = dist.sdist_members(built["sdist"])
    wheel = dist.wheel_members(built["wheel"])
    banned_files = {"s07_reference.json", "platform_digest.json", "published_checks.yaml"}
    suffixes = (".so", ".dylib", ".dll", ".pyd")
    for kind, members in (("sdist", sdist), ("wheel", wheel)):
        names = list(members)
        assert [n for n in names if PurePosixPath(n).name in banned_files] == [], kind
        assert [n for n in names if n.endswith(suffixes)] == [], kind
        assert [n for n in names if "CoolProp/" in n or "/fluids/" in n] == [], kind
        assert [n for n in names if n.startswith(("docs/", "benchmarks/s07/"))] == [], kind
    # controls: the provider module and its fluid table (the project's own code) are shipped
    assert "src/openflowsheet/thermo/coolprop_heos.py" in sdist
    assert "openflowsheet/thermo/coolprop_heos.py" in wheel
    assert "openflowsheet/thermo/_coolprop_heos_fluids.py" in wheel
    # (b) the wheel's Requires-Dist names CoolProp only under the coolprop extra
    with zipfile.ZipFile(built["wheel"]) as archive:
        (metadata,) = [n for n in archive.namelist() if n.endswith(".dist-info/METADATA")]
        fields = dist.metadata_fields(archive.read(metadata).decode("utf-8"))
    mentions = [v for v in fields.get("Requires-Dist", []) if "coolprop" in v.lower()]
    assert len(mentions) == 1
    assert 'extra == "coolprop"' in mentions[0]


# -- A30: library-only, superseded by S11 (R-810) ------------------------------------------------


def test_a30_library_only_registration() -> None:
    """S11 (ADR 0050, R-810) reverses A30 on purpose: `coolprop-heos-v1` is selectable, on the
    T08 providers axis, and no longer registered library-only."""
    from test_t08_w2_support_envelope import LIBRARY_ONLY_PROVIDERS

    selectable = {basis.provider_id for basis in revision_binding.SELECTABLE_BASES}
    assert PROVIDER_ID in selectable
    assert PROVIDER_ID not in LIBRARY_ONLY_PROVIDERS
    matrix = _script("t08_support_matrix")
    assert PROVIDER_ID in matrix.code_facts()["scanned_providers"]
    assert PROVIDER_ID in matrix.code_facts()["providers"]
    # control: the S05 provider is selectable the same way, and S04's stays library-only
    assert "iapws95-v1" in selectable and "iapws95-v1" not in LIBRARY_ONLY_PROVIDERS
    assert LIBRARY_ONLY_PROVIDERS == {"pr-lib-v1": "S04"}


def test_a30_the_u02_note_names_the_provider() -> None:
    """The manifest generator's U02 limitation names `coolprop-heos-v1` and library-only; once an
    S07 manifest is harvested, every S07 U02 item's note does and there is at least one (T08 C3
    judges the same on the whole registry)."""
    generator = _script("s07_evidence_manifest")
    assert f"`{PROVIDER_ID}`" in generator.LIBRARY_ONLY
    assert "library-only" in generator.LIBRARY_ONLY
    matrix = _script("t08_support_matrix")
    harvested = {path for path, _ in matrix.harvest_items() if path.startswith("evidence/S07/")}
    items = [
        entry
        for entry in matrix.load()["harvest"]
        if entry["manifest"] in harvested and "U02" in (entry.get("to") or [])
    ]
    if harvested:
        assert items
    for entry in items:
        assert f"`{PROVIDER_ID}`" in entry["note"] and "library-only" in entry["note"], entry


# -- A31: the cross-architecture digest ------------------------------------------------------------


@pytest.fixture(scope="module")
def digest_script() -> ModuleType:
    require_coolprop()
    return _script("s07_platform_digest")


def test_a31_the_digest_file_is_the_scripts_output(digest_script: ModuleType) -> None:
    """`--check` on x86-64 (the fixture's own machine): the committed file is byte-identical to the
    script's output. Everywhere: 123 fluids, each with the script's answer count."""
    if platform.machine() in ("x86_64", "AMD64"):
        text = digest_script.render(digest_script.build())
        assert digest_script.DIGEST.read_text("utf-8") == text
    stored: dict[str, Any] = json.loads(digest_script.DIGEST.read_text("utf-8"))
    assert stored["schema"] == "s07-platform-digest-v1"
    assert len(stored["fluids"]) == 123
    counts = {cid: len(rows) for cid, rows in stored["fluids"].items()}
    reference = json.loads(REFERENCE.read_text("utf-8"))
    for cid in stored["fluids"]:
        rows = digest_script.answers(cid, reference)
        assert len(rows) == counts[cid], cid
        assert all(isinstance(value, float) for _, value, _ in rows), cid
    # tier B stops where §16.10 stops: no derivatives at the TP states
    assert not any(".dT." in key for key, _, _ in digest_script.answers("1-Butene", reference))
    assert any(".dT." in key for key, _, _ in digest_script.answers("H2O", reference))


#: §20.3's class-N set, written out from the spec (A31c(1)): T_sigma_max for every fluid, the
#: nine's `sat_hi`, `NC_V` and `NC_L`, and three clamped supercritical states of six fluids.
TIER_A = ("Ar", "C2H6", "C3H8", "CH4", "CO2", "H2", "H2O", "N2", "O2")
CLAMPED = ("MD4M", "PropyleneGlycol", "R236FA", "R245ca", "n-Nonane", "n-Perfluorohexane")


@pytest.fixture(scope="module")
def measured(digest_script: ModuleType) -> dict[str, Any]:
    """The running machine's rows, classes and sensitivities, computed once for every A31 test."""
    return digest_script.measure()  # type: ignore[no-any-return]


@pytest.fixture(scope="module")
def a31(digest_script: ModuleType, measured: dict[str, Any]) -> dict[str, Any]:
    return digest_script.compare(measured=measured)  # type: ignore[no-any-return]


def test_a31a_the_digests_own_machine_is_bitwise(a31: dict[str, Any]) -> None:
    """A31a (spec §20.6, §20.8): on x86-64 every row of every fluid equals the digest bitwise."""
    if platform.machine() != "x86_64":
        pytest.skip(f"A31a holds on x86_64 only; this machine is {platform.machine()} (A31b)")
    assert a31["outcome"] == "a" and a31["bitwise"], a31["verdict"]
    assert a31["failures"] == [] and a31["verdict"] == "S07 A31 (x86_64): bit-identical"


def test_a31b_cross_architecture(
    digest_script: ModuleType, a31: dict[str, Any], capsys: pytest.CaptureFixture[str]
) -> None:
    """A31b (spec §20.8): outcome (a), or every row within its class (S exact, T by §20.4, N by
    §20.5). The verdict line is printed (CI's own comes from `--report`), and when the outcome is
    not (a) the report is written as §20.9 says."""
    with capsys.disabled():
        print("\n" + a31["verdict"])
    if a31["outcome"] != "a":
        digest_script.write_report(a31)
    assert a31["failures"] == []


def test_a31c_the_rules_inputs(digest_script: ModuleType, measured: dict[str, Any]) -> None:
    """A31c (spec §20.8): the class-N set is §20.3's 168 pairs and holds no `phi`, `band`, `tsat`
    or `a12` row; 2H <= eps_sigma, r <= 20, (rho_L - rho_V)/rho_c >= 0.04 and Psat >= P_lo hold
    (each checked by the script, which names the item it fails)."""
    reference = json.loads(REFERENCE.read_text("utf-8"))
    expected = {(cid, "a10.T_sigma_max") for cid in reference["fluids"]}
    expected |= {(cid, f"{s}") for cid in TIER_A for s in ("sat.sat_hi", "tp.NC_V", "tp.NC_L")}
    expected |= {(cid, f"tp.{s}") for cid in CLAMPED for s in ("S_dense", "V_sup", "V_corner")}
    assert len(expected) == 168
    assert {tuple(pair) for pair in measured["class_n_pairs"]} == expected
    tiers = {cid: ("A" if cid in TIER_A else "B") for cid in reference["fluids"]}
    assert digest_script.expected_class_n(tiers) == expected
    for entry in measured["fluids"].values():
        near = [key for key, kind in entry["classes"].items() if kind == "N"]
        assert not [key for key in near if key.split(".")[0] not in ("tp", "sat", "a10")]
    assert [line for line in measured["failures"] if line.startswith("A31c")] == []
    assert 2.0 * digest_script.H <= min(
        float(fluid["constants"]["eps_sigma"]) for fluid in reference["fluids"].values()
    )
    r_max = max(r for entry in measured["fluids"].values() for r in entry["inputs"]["r"].values())
    drho = min(entry["inputs"]["drho"] for entry in measured["fluids"].values())
    assert r_max <= digest_script.R_MAX and drho >= digest_script.DRHO_MIN


def test_a31c_a_near_critical_row_without_a_sensitivity_has_no_class(
    digest_script: ModuleType,
) -> None:
    """§20.3: a `tsat`, `band` or `a12` row with |theta| < 1e-2 is not covered by §20."""
    fluid = {"constants": {"T_c": 100.0}, "band": {"T": 99.5}}
    with pytest.raises(ValueError, match="§20 defines no class-N sensitivity for band.p.VAPOR.h"):
        digest_script.row_class("band.p.VAPOR.h", 1.0, fluid)
    assert digest_script.row_class("phi.x.3", 1.0, fluid) == "T"
    assert digest_script.row_class("band.p.VAPOR.status", "refused:x", fluid) == "S"


def test_a31d_every_sensitivity_is_evaluable(measured: dict[str, Any]) -> None:
    """A31d (spec §20.8): every §20.5 evaluation answers `ok` and gives a finite sigma, so every
    class-N row other than Psat has one."""
    assert [line for line in measured["failures"] if "sensitivity" in line] == []
    for cid, entry in measured["fluids"].items():
        for key, kind in entry["classes"].items():
            psat = key.split(".")[0] in ("sat", "a10") and key.endswith(".Psat")
            if kind == "N" and not psat:
                sigma = entry["sigma"][key]
                assert sigma >= 0.0 and sigma < float("inf"), (cid, key)


def _mutated(
    digest_script: ModuleType, measured: dict[str, Any], cid: str, key: str, change: Any
) -> dict[str, Any]:
    stored: dict[str, Any] = json.loads(digest_script.DIGEST.read_text("utf-8"))
    index = [row[0] for row in measured["fluids"][cid]["rows"]].index(key)
    stored["fluids"][cid][index] = change(stored["fluids"][cid][index])
    return stored


def test_a31e_comparator_controls(digest_script: ModuleType, measured: dict[str, Any]) -> None:
    """A31e (spec §20.8): on a copy of the digest, perturbations at 2x a row's allowance are
    flagged and at 0.5x are not, for a class-T row, a class-N Psat row and a class-N cp row whose
    allowance is carried by its sigma; no other row is flagged."""
    h2o = measured["fluids"]["H2O"]

    def flagged(key: str, change: Any) -> list[tuple[str, str]]:
        digest = _mutated(digest_script, measured, "H2O", key, change)
        return digest_script.compare(digest, measured)["flagged"]  # type: ignore[no-any-return]

    def scaled(factor: float) -> Any:
        return lambda hexed: (float.fromhex(hexed) * factor).hex()

    for key in ("tp.V_sup.v", "a10.T_sigma_max.Psat"):
        assert flagged(key, scaled(1.0 + 2e-10)) == [("H2O", key)], key
        assert flagged(key, scaled(1.0 + 5e-11)) == [], key
    key = "a10.T_sigma_max.LIQUID.cp"
    assert h2o["classes"][key] == "N" and h2o["classes"]["tp.V_sup.v"] == "T"
    _, x, scale = next(row for row in h2o["rows"] if row[0] == key)
    allowance = digest_script.allowance(key, x, scale, "N", h2o["sigma"][key])
    assert allowance >= 1e-8 * max(abs(x), scale)
    assert flagged(key, lambda hexed: (float.fromhex(hexed) + 2.0 * allowance).hex()) == [
        ("H2O", key)
    ]
    assert flagged(key, lambda hexed: (float.fromhex(hexed) + 0.5 * allowance).hex()) == []


def test_a31_the_comparison_judges_kind_and_count(
    digest_script: ModuleType, measured: dict[str, Any]
) -> None:
    """§20.3: a refusal string where a number stood fails (class S), and so does a different row
    count; on x86-64 any difference fails (§20.6), on another machine a last-bit one does not."""
    refused = _mutated(digest_script, measured, "H2O", "tp.V_sup.h", lambda _: "refused:x")
    result = digest_script.compare(refused, measured, machine="aarch64")
    assert result["flagged"] == [("H2O", "tp.V_sup.h")] and result["classes"]["S"]["failing"] == 1
    assert "FAILS spec §20: 1 rows over their allowance" in result["verdict"]
    short = json.loads(digest_script.DIGEST.read_text("utf-8"))
    short["fluids"]["H2O"].pop()
    assert digest_script.compare(short, measured, machine="aarch64")["failures"]
    nudged = _mutated(
        digest_script,
        measured,
        "H2O",
        "tp.V_sup.h",
        lambda hexed: (float.fromhex(hexed) * (1.0 + 1e-14)).hex(),
    )
    elsewhere = digest_script.compare(nudged, measured, machine="aarch64")
    assert elsewhere["outcome"] == "b" and elsewhere["failures"] == []
    assert elsewhere["verdict"].startswith("S07 A31 (aarch64): not bit-identical; within spec §20")
    home = digest_script.compare(nudged, measured, machine="x86_64")
    assert home["flagged"] == [] and home["verdict"].endswith("(spec §20.6)")


def test_a31_the_report(
    digest_script: ModuleType, measured: dict[str, Any], tmp_path: Path
) -> None:
    """§20.9: the report holds every differing row with its class, both values as hex, |d|, the
    allowance, u and the ratio; the worst ratio per `<class>:<quantity>` group, which keeps the a10
    temperature and reads `lnphi`; and per class the rows compared, differing and failing. Judged
    against the unperturbed comparison, so the test holds whatever the machine's own differences
    (on aarch64 the perturbed row may already differ, by at most 2.3e-8 of cp: §20.1)."""
    key = "a10.T_sigma_max.LIQUID.cp"
    base = digest_script.compare(None, measured, machine="aarch64")
    digest = _mutated(
        digest_script,
        measured,
        "H2O",
        key,
        lambda hexed: (float.fromhex(hexed) * (1.0 + 1e-7)).hex(),
    )
    result = digest_script.compare(digest, measured, machine="aarch64")
    path = digest_script.write_report(result, tmp_path / "a31.json")
    report = json.loads(path.read_text("utf-8"))
    assert report["verdict"] == result["verdict"] and report["passed"] and report["outcome"] == "b"
    before = {(row["fluid"], row["key"]) for row in base["rows"]}
    after = {(row["fluid"], row["key"]) for row in report["rows"]}
    assert after == before | {("H2O", key)}
    row = next(row for row in report["rows"] if (row["fluid"], row["key"]) == ("H2O", key))
    assert row["class"] == "N" and not row["fails"]
    assert float.fromhex(row["x"]) != float.fromhex(row["y"])
    assert 0.0 < row["u"] < 1.0 and row["u"] == row["delta"] / row["allowance"]
    assert 7e-8 < row["ratio"] < 1.3e-7
    assert f"N:{key}" in report["groups"] and report["groups"][f"N:{key}"][0] >= row["ratio"]
    assert all(group.split(":")[0] in ("T", "N") for group in report["groups"])
    differing = report["classes"]["N"]["differing"]
    assert differing == base["classes"]["N"]["differing"] + (("H2O", key) not in before)
    assert report["classes"]["N"]["failing"] == 0 and report["class_n_pairs"] == 168
    assert report["classes"]["T"]["compared"] > 0
    assert digest_script.quantity("tp.NC_V.dT.lnphi_H2O") == "tp.dT.lnphi"
    assert digest_script.quantity("a12.273.16.u") == "a12.u"
    lines = digest_script.report_lines(result)
    assert lines[0] == result["verdict"] and lines[1].startswith("  class T: ")
    assert len(lines) == 1 + 3 + min(20, len(report["rows"]))
    assert sum("S07 A31 (" in line for line in lines) == 1
