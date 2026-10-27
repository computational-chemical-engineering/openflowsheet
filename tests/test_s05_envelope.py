"""S05.A22, A25-A32: the envelope, the robustness grid and the evidence (WO-S05-2).

Spec `docs/derivations/S05-IAPWS95-spec.md` §6.1. A22 is a stability grid with no expectation
file; A25-A28 are facts of the repository (library-only registration, the packaging hold, the
generator's committed facts, the generators' independence); A29 runs `scripts/s05_mutations.py`'s
battery; A30 checks this file's probe table against §4.5's code lists. Neither generator is
imported here.
"""

from __future__ import annotations

import ast
import fnmatch
import hashlib
import importlib.util
import json
import os
import re
import sys
import tomllib
import zipfile
from collections.abc import Callable, Iterator
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from openflowsheet.application import revision_binding
from openflowsheet.compiled import EvaluationContext
from openflowsheet.resources import PACKAGED, packaged
from openflowsheet.thermo import (
    FlashRequest,
    FlashResult,
    Phase,
    PropertyRequest,
    PropertyResult,
    StreamState,
)
from openflowsheet.thermo import iapws95 as w

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "docs" / "derivations" / "scripts"
SPEC = ROOT / "docs" / "derivations" / "S05-IAPWS95-spec.md"
REF: dict[str, Any] = json.loads((SCRIPTS / "s05_reference.json").read_text("utf-8"))
REGISTERED_SHA256 = "b9e93877e37874f1b3a483e298a45692e264d70686d4c158372084b96abbe6ed"
CONTEXT = EvaluationContext(model_version="s05-envelope", constants_sha256="0" * 64)
PROVIDER = w.Iapws95Provider()
SIX = w.PHASE_PROPERTIES
PHASES: tuple[Phase, Phase] = ("LIQUID", "VAPOR")


def _script(name: str) -> ModuleType:
    path = ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def ev(
    t: float,
    p: float,
    phase: Phase,
    properties: tuple[str, ...] = SIX,
    derivatives: tuple[str, ...] = ("T", "P", "n_H2O"),
    n: tuple[float, ...] = (1.0,),
) -> PropertyResult:
    state = StreamState(n=n, temperature=t, pressure=p)
    return PROVIDER.evaluate_phase(PropertyRequest(state, phase, properties, derivatives), CONTEXT)


def flash(
    t: float, p: float, spec: str = "TP", n: tuple[float, ...] = (1.0,), der: tuple[str, ...] = ()
) -> FlashResult:
    state = StreamState(n=n, temperature=t, pressure=p)
    return PROVIDER.flash(FlashRequest(state, spec, der), CONTEXT)


def code_of(result: PropertyResult | FlashResult) -> str:
    return result.message.split(":", 1)[0]


# -- A22: the robustness grid ----------------------------------------------------------------------

GRID_T = (273.16, *(float(t) for t in range(300, 1251, 50)), 1273.15)
GRID_P = (1.0e2, 1.0e3, 1.0e4, 1.0e5, 1.0e6, 1.0e7, 1.0e8, 3.0e7)
#: Spec §14 (R-595): the root residual in density units at every answer; measured worst 3.4e-14
#: on the dense grid below (273.16 K liquid, its rounding floor; docs/C10_DECISIONS.md, WO-S05-3).
ROOT_TOL = 1e-12


def root_residual(t: float, p: float, v: float) -> float:
    """|p(M/v, T) − P| / (ρ (∂p/∂ρ)_T), with p and ∂p/∂ρ from `phi_jet` (A03's surface)."""
    rho = w.M / v
    delta = rho / w.RHO_C
    _, res = w.phi_jet(w.T_C / t, delta)
    rt = w.R_S * t
    pressure = rho * rt * (1.0 + delta * res.d)
    slope = rt * (1.0 + 2.0 * delta * res.d + delta * delta * res.dd)
    return abs(pressure - p) / (rho * slope)


def grid_problems(t: float) -> list[str]:
    """Why the grid row at `t` breaks A22: a `not_converged`, a refusal other than
    `phase_not_stable`, an answer with (∂v/∂P)_T ≥ 0 or cp ≤ 0 or a root residual above
    `ROOT_TOL`, or a state that answers no phase."""
    problems: list[str] = []
    for p in GRID_P:
        answered = []
        for phase in PHASES:
            result = ev(t, p, phase)
            where = f"{t} K, {p} Pa, {phase}"
            if result.status != "ok":
                if (result.status, code_of(result)) != ("unsupported", "phase_not_stable"):
                    problems.append(f"{where}: {result.status} {result.message}")
                continue
            answered.append(phase)
            if not result.derivatives["v"]["P"] < 0.0:
                problems.append(f"{where}: dv/dP = {result.derivatives['v']['P']!r}")
            if not result.values["cp"] > 0.0:
                problems.append(f"{where}: cp = {result.values['cp']!r}")
            if not (residual := root_residual(t, p, result.values["v"])) <= ROOT_TOL:
                problems.append(f"{where}: root residual {residual!r}")
        if not answered:
            problems.append(f"{t} K, {p} Pa: no phase answered")
    return problems


def test_a22_the_grid_is_the_specs() -> None:
    assert len(GRID_T) == 22 and GRID_T[0] == w.T_MIN and GRID_T[-1] == w.T_MAX
    assert GRID_T[1:-1] == tuple(300.0 + 50.0 * k for k in range(20))
    assert len(set(GRID_P)) == 8 and min(GRID_P) == w.P_MIN and max(GRID_P) == w.P_MAX


@pytest.mark.parametrize("t", GRID_T)
def test_a22_robustness_grid(t: float) -> None:
    assert grid_problems(t) == []


#: Spec §14 (R-595): the review's dense grid, 180 T × 61 P (`docs/reviews/S05-review.md` F1), on
#: which the unfixed solver answered 99 states `ok` off their root: 120 T on [T_t, 646.9 K], 60 T
#: on [648.5 K, T_max], and ten P per decade over [P_min, P_max], spaced as `numpy.linspace`
#: and `numpy.logspace` space them (start + k·step, the end point exact).


def _linspace(start: float, stop: float, n: int) -> tuple[float, ...]:
    step = (stop - start) / (n - 1)
    return (*(start + k * step for k in range(n - 1)), stop)


DENSE_T = (*_linspace(w.T_MIN, 646.9, 120), *_linspace(648.5, w.T_MAX, 60))
DENSE_P = tuple(10.0**x for x in _linspace(2.0, 8.0, 61))


def dense_problems(t: float) -> list[str]:
    """Every answer of the dense row at `t` whose root residual exceeds `ROOT_TOL`."""
    problems = []
    for p in DENSE_P:
        for phase in PHASES:
            result = ev(t, p, phase, ("v",), ())
            if result.status == "ok":
                if not (residual := root_residual(t, p, result.values["v"])) <= ROOT_TOL:
                    problems.append(f"{t} K, {p} Pa, {phase}: root residual {residual!r}")
    return problems


def test_a22_the_dense_grid_is_the_reviews() -> None:
    assert len(DENSE_T) == 180 and len(set(DENSE_T)) == 180 and len(DENSE_P) == 61
    assert DENSE_T[0] == w.T_MIN and DENSE_T[-1] == w.T_MAX
    assert DENSE_P[0] == w.P_MIN and DENSE_P[-1] == w.P_MAX
    assert {599.7899159663866, 631.1966386554623, 659.0872881355932} <= set(DENSE_T)
    assert 63095734.44801943 in DENSE_P


@pytest.mark.parametrize("t", DENSE_T)
def test_a22_dense_grid_root_residual(t: float) -> None:
    assert dense_problems(t) == []


def test_a22_a_wrong_root_is_caught(monkeypatch: pytest.MonkeyPatch) -> None:
    """No vacuous pass: a density off by 1e-9 relative fails the root residual."""
    real = PROVIDER.evaluate_phase

    def shifted(request: PropertyRequest, context: EvaluationContext) -> PropertyResult:
        result = real(request, context)
        if result.status == "ok":
            result.values["v"] *= 1.0 + 1e-9
        return result

    monkeypatch.setattr(PROVIDER, "evaluate_phase", shifted)
    assert any("root residual" in problem for problem in grid_problems(500.0))
    assert any("root residual" in problem for problem in dense_problems(500.0))


def test_a22_a_broken_stability_sign_is_caught(monkeypatch: pytest.MonkeyPatch) -> None:
    """No vacuous pass: a provider whose cp is negated fails the row."""
    real = PROVIDER.evaluate_phase

    def negated(request: PropertyRequest, context: EvaluationContext) -> PropertyResult:
        result = real(request, context)
        if result.status == "ok":
            result.values["cp"] = -result.values["cp"]
        return result

    monkeypatch.setattr(PROVIDER, "evaluate_phase", negated)
    assert any("cp = " in problem for problem in grid_problems(500.0))


# -- A25: library-only (R-568, R-569; spec §8 F-2), superseded by S11 (R-810) ----------------------


def test_a25_library_only_registration() -> None:
    """S11 (ADR 0050, R-810) reverses A25 on purpose: `iapws95-v1` is selectable, on the T08
    providers axis, and no longer registered library-only."""
    from test_t08_w2_support_envelope import LIBRARY_ONLY_PROVIDERS

    selectable = {basis.provider_id for basis in revision_binding.SELECTABLE_BASES}
    assert w.PROVIDER_ID == "iapws95-v1"
    assert w.PROVIDER_ID in selectable
    assert w.PROVIDER_ID not in LIBRARY_ONLY_PROVIDERS
    matrix = _script("t08_support_matrix")
    assert w.PROVIDER_ID in matrix.code_facts()["scanned_providers"]
    assert w.PROVIDER_ID in matrix.code_facts()["providers"]


def test_a25_the_u02_note_names_the_provider() -> None:
    """The manifest's U02 limitation (whose harvest note the envelope carries) names
    `iapws95-v1` and library-only; once an S05 manifest is harvested, every S05 U02 item's note
    does and there is at least one (T08 C3 judges the same on the whole registry)."""
    generator = _script("s05_evidence_manifest")
    assert "`iapws95-v1`" in generator.LIBRARY_ONLY and "library-only" in generator.LIBRARY_ONLY
    matrix = _script("t08_support_matrix")
    harvested = {path for path, _ in matrix.harvest_items() if path.startswith("evidence/S05/")}
    items = [
        entry
        for entry in matrix.load()["harvest"]
        if entry["manifest"].startswith("evidence/S05/") and "U02" in (entry.get("to") or [])
    ]
    assert bool(items) == bool(harvested)
    for entry in items:
        assert "`iapws95-v1`" in entry["note"] and "library-only" in entry["note"], entry


# -- A26: packaged (R-594, superseded by R-616; spec §16.2) ---------------------------------------

COEFFICIENT_FILE = "benchmarks/s05/iapws95_coefficients.json"
PACKAGE_COPY = ROOT / "src" / "openflowsheet" / "_data" / COEFFICIENT_FILE
DATA_PATTERNS: list[str] = tomllib.loads((ROOT / "pyproject.toml").read_text("utf-8"))["tool"][
    "setuptools"
]["package-data"]["openflowsheet"]


def test_a26_the_coefficient_file_is_a_packaged_single_file() -> None:
    from openflowsheet.resources import DIRECTORIES

    # (a) one file entry; nothing below benchmarks/s05 is an entry or a directory entry
    assert COEFFICIENT_FILE in PACKAGED
    assert not [e for e in PACKAGED if e != COEFFICIENT_FILE and e.startswith("benchmarks/s05")]
    assert not [e for e in DIRECTORIES if e.startswith("benchmarks/s05")]
    # (b) the package copy is a link to the one repository copy, and hashes to H_C
    assert PACKAGE_COPY.is_symlink()
    assert os.readlink(PACKAGE_COPY) == f"../../../../../{COEFFICIENT_FILE}"
    repository = (ROOT / COEFFICIENT_FILE).read_bytes()
    assert packaged(COEFFICIENT_FILE).read_bytes() == repository
    assert hashlib.sha256(repository).hexdigest() == REGISTERED_SHA256
    # (c) exactly one package-data pattern matches
    pattern = f"_data/{COEFFICIENT_FILE}"
    assert len([p for p in DATA_PATTERNS if fnmatch.fnmatch(pattern, p)]) == 1
    # control: (a)-(c) hold for a packaged benchmark file
    control = "benchmarks/m01/components.yaml"
    assert control in PACKAGED
    assert (ROOT / "src" / "openflowsheet" / "_data" / control).is_symlink()
    assert len([p for p in DATA_PATTERNS if fnmatch.fnmatch(f"_data/{control}", p)]) == 1


#: A Python with `setuptools` (T08.A43's pin) to build the wheel; the manifest generator sets it.
BUILD_PYTHON = os.environ.get("OFS_S05_BUILD_PYTHON")
STRINGS = (
    "\u00a9 2018 International Association for the Properties of Water and Steam",
    "Publication in whole or in part is allowed in all countries provided that attribution is "
    "given to the International Association for the Properties of Water and Steam",
    "Please cite as: International Association for the Properties of Water and Steam, IAPWS "
    "R6-95(2018), Revised Release on the IAPWS Formulation 1995 for the Thermodynamic "
    "Properties of Ordinary Water Substance for General and Scientific Use (2018)",
)


def _collapsed(text: str) -> str:
    return " ".join(text.split())


@pytest.mark.skipif(not BUILD_PYTHON, reason="OFS_S05_BUILD_PYTHON (a Python with setuptools)")
def test_a26_a31_a_built_wheel_holds_the_coefficient_file_and_the_notice(tmp_path: Path) -> None:
    dist = _script("t08_dist")
    export, out = tmp_path / "export", tmp_path / "out"
    dist.export_commit("HEAD", export)
    out.mkdir()
    wheel = dist.run_hook(Path(str(BUILD_PYTHON)), "build_wheel", export, out, "1700000000")
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        member = "openflowsheet/_data/" + COEFFICIENT_FILE
        # A26 (d): exactly one such member, at the package path, with H_C's bytes
        assert [n for n in names if n.endswith("iapws95_coefficients.json")] == [member]
        assert hashlib.sha256(archive.read(member)).hexdigest() == REGISTERED_SHA256
        below = "openflowsheet/_data/benchmarks/s05/"
        assert [n for n in names if n.startswith(below)] == [member]
        # controls: the provider module and a packaged benchmark file are in the same wheel
        assert "openflowsheet/thermo/iapws95.py" in names
        assert "openflowsheet/_data/benchmarks/m01/components.yaml" in names
        # A31 (d): the wheel's NOTICE, located as T08.A31 locates it, equals the repository's
        notices = [n for n in names if dist.classify_wheel(n, n.split("/", 1)[0]) == "licence"]
        notice = [n for n in notices if n.endswith("/licenses/NOTICE")]
        assert len(notice) == 1
        assert archive.read(notice[0]) == (ROOT / "NOTICE").read_bytes()


# -- A31: the attribution (R-616; spec §16.3) ------------------------------------------------------


def test_a31_the_attribution_is_in_notice_the_record_and_the_provider_documentation() -> None:
    notice = _collapsed((ROOT / "NOTICE").read_text("utf-8"))
    recorded = _collapsed((ROOT / "docs" / "C10_DECISIONS.md").read_text("utf-8"))
    document = _collapsed((ROOT / "docs" / "attributions" / "iapws95-v1.md").read_text("utf-8"))
    for string in STRINGS:
        assert string in notice, string
        assert string in recorded, string
        assert string in document, string
    for string in (w.PROVIDER_ID, COEFFICIENT_FILE, REGISTERED_SHA256):
        assert string in document, string


# -- A32: the package copy serves the provider -----------------------------------------------------


def _raises_key_error(relative: str) -> Any:
    raise KeyError(relative)


def test_a32_the_package_copy_serves_the_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    repository = (ROOT / COEFFICIENT_FILE).read_bytes()
    w.load_coefficients.cache_clear()
    try:
        monkeypatch.setattr(w, "_checkout_coefficients", lambda: None)
        assert w.load_coefficients() == w.parse_coefficients(repository)
        w.load_coefficients.cache_clear()
        # control: with the package copy unavailable too, nothing is left to read
        monkeypatch.setattr(w, "packaged", _raises_key_error)
        with pytest.raises(FileNotFoundError):
            w.load_coefficients()
    finally:
        monkeypatch.undo()
        w.load_coefficients.cache_clear()


# -- A27, A28: the generator's facts and the generators' independence -----------------------------


def test_a27_generator_facts() -> None:
    assert REF["coefficients_sha256"] == REGISTERED_SHA256 == w.COEFFICIENTS_SHA256
    assert REF["claim_count"] >= 300
    assert REF["claim_count"] == len(REF["claims"])


def _top_level_imports(path: Path) -> set[str]:
    found: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text("utf-8"))):
        if isinstance(node, ast.Import):
            found |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            found.add(node.module.split(".")[0])
    return found


def test_a28_the_reference_generator_imports_only_the_standard_library_and_mpmath() -> None:
    imports = _top_level_imports(SCRIPTS / "s05_reference.py")
    assert "mpmath" in imports
    assert not imports - set(sys.stdlib_module_names) - {"__future__", "mpmath"}
    # control: the cross-check generator is caught by the same reading
    assert {"CoolProp", "iapws"} <= _top_level_imports(SCRIPTS / "s05_crosscheck.py")


def test_a28_no_test_imports_the_cross_check_or_its_libraries() -> None:
    crosscheck = "s05_" + "crosscheck"
    offenders = []
    for path in sorted((ROOT / "tests").glob("*.py")):
        imports = _top_level_imports(path)
        if imports & {"CoolProp", "iapws", crosscheck}:
            offenders.append(f"{path.name}: {sorted(imports & {'CoolProp', 'iapws', crosscheck})}")
        if path.name != Path(__file__).name and crosscheck in path.read_text("utf-8"):
            offenders.append(f"{path.name} names {crosscheck}")
    assert offenders == []


# -- A29: the mutation battery ---------------------------------------------------------------------

MUTATIONS = _script("s05_mutations")


def test_a29_every_edit_applies_once_and_the_mutations_are_the_specs() -> None:
    assert [m.id for m in MUTATIONS.MUTATIONS] == [f"m{k}" for k in range(1, 9)]
    assert [m.assertion for m in MUTATIONS.MUTATIONS] == [
        "A03",
        "A03",
        "A05",
        "A13",
        "A15",
        "A07",
        "A06",
        "A03",
    ]
    for mutation in MUTATIONS.MUTATIONS:
        assert MUTATIONS.mutated_source(mutation) != MUTATIONS.mutated_source(None)


def test_a29_a_stale_edit_is_refused() -> None:
    stale = MUTATIONS.Mutation("mx", "stale", "A03", (), (("no such text", ""),))
    with pytest.raises(ValueError, match="occurs 0 times"):
        MUTATIONS.mutated_source(stale)


def test_a29_the_control_run_passes(tmp_path: Path) -> None:
    every = tuple(dict.fromkeys(node for m in MUTATIONS.MUTATIONS for node in m.nodes))
    ran = MUTATIONS._run(MUTATIONS.CONTROL, every, tmp_path / "control.log")
    assert ran["exit_code"] == 0 and ran["outcomes"].get("passed", 0) > 0, ran["outcomes"]


def _mutation_cases() -> Iterator[Any]:
    for mutation in MUTATIONS.MUTATIONS:
        yield pytest.param(mutation.id, id=mutation.id)


@pytest.mark.parametrize("mutation_id", _mutation_cases())
def test_a29_the_named_assertion_catches_the_mutation(mutation_id: str, tmp_path: Path) -> None:
    mutation = MUTATIONS.BY_ID[mutation_id]
    ran = MUTATIONS._run(mutation.id, mutation.nodes, tmp_path / f"{mutation.id}.log")
    assert ran["exit_code"] == 1 and ran["outcomes"].get("failed", 0) >= 1, ran["outcomes"]
    assert mutation.expect in ran["output"]


# -- A30: refusal coverage -------------------------------------------------------------------------


def spec_codes() -> tuple[dict[str, str], set[str]]:
    """§4.5's codes: `evaluate_phase`'s table (code -> status) and `flash`'s numbered list."""
    text = SPEC.read_text("utf-8")
    body = text[text.index("### 4.5 ") : text.index("## 5. ")]
    table, rest = body.split("`flash` checks", 1)
    phase: dict[str, str] = {}
    for line in table.splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) == 4 and cells[0].isdigit():
            for code in re.findall(r"`(\w+)`", cells[1]):
                phase[code] = cells[2]
    flash_codes = set(re.findall(r"^\d+\. `(\w+)`", rest.split("Otherwise", 1)[0], re.M))
    return phase, flash_codes


L_AMBIENT = (300.0, 1.0e5)
BAND_T = float(REF["band"]["T"])
BAND_IN_LO = float(REF["band"]["probes"]["in_lo"]["P"])
BAND_OUT_LO = float(REF["band"]["probes"]["out_lo"]["P"])


def _starved(call: Callable[[], PropertyResult]) -> Callable[[], PropertyResult]:
    """`call` with no Newton iteration allowed and a cold saturation cache (restored after)."""

    def run() -> PropertyResult:
        w._tsat_bounds()  # cached constants of the file, computed before the starvation
        w._saturation.cache_clear()
        saved = w.MAX_ITERATIONS
        try:
            w.MAX_ITERATIONS = 0  # type: ignore[misc]
            return call()
        finally:
            w.MAX_ITERATIONS = saved  # type: ignore[misc]
            w._saturation.cache_clear()

    return run


#: (entry point, code, status, probe, answered control); spec §5.5's probes where it has one.
PROBES: list[tuple[str, str, str, Callable[[], Any], Callable[[], Any]]] = [
    (
        "evaluate_phase",
        "undeclared_derivative_input",
        "unsupported",
        lambda: ev(*L_AMBIENT, "LIQUID", derivatives=("n_N2",)),
        lambda: ev(*L_AMBIENT, "LIQUID"),
    ),
    (
        "evaluate_phase",
        "unknown_property",
        "unsupported",
        lambda: ev(*L_AMBIENT, "LIQUID", ("g",)),
        lambda: ev(*L_AMBIENT, "LIQUID", ("h",)),
    ),
    (
        "evaluate_phase",
        "state_length",
        "error",
        lambda: ev(*L_AMBIENT, "LIQUID", n=(1.0, 0.0)),
        lambda: ev(*L_AMBIENT, "LIQUID", n=(1.0,)),
    ),
    (
        "evaluate_phase",
        "out_of_domain",
        "out_of_domain",
        lambda: ev(273.15, 1.0e5, "LIQUID", ("h",)),
        lambda: ev(273.16, 1.0e8, "LIQUID", ("h",)),
    ),
    (
        "evaluate_phase",
        "dormant_state",
        "unsupported",
        lambda: ev(*L_AMBIENT, "LIQUID", n=(0.0,)),
        lambda: ev(*L_AMBIENT, "LIQUID", n=(1.0,)),
    ),
    (
        "evaluate_phase",
        "no_saturation",
        "unsupported",
        lambda: ev(647.0001, 1.0e5, "VAPOR", ("Psat",)),
        lambda: ev(647.0, 1.0e5, "VAPOR", ("Psat",)),
    ),
    (
        "evaluate_phase",
        "near_critical",
        "unsupported",
        lambda: ev(647.5, 2.21e7, "VAPOR", ("h",)),
        lambda: ev(648.0, 2.21e7, "VAPOR", ("h",)),
    ),
    (
        "evaluate_phase",
        "phase_not_stable",
        "unsupported",
        lambda: ev(700.0, 3.0e7, "LIQUID", ("h",)),
        lambda: ev(700.0, 3.0e7, "VAPOR", ("h",)),
    ),
    (
        "evaluate_phase",
        "density_not_converged",
        "not_converged",
        _starved(lambda: ev(700.0, 1.0e7, "VAPOR", ("h",))),
        lambda: ev(700.0, 1.0e7, "VAPOR", ("h",)),
    ),
    (
        "evaluate_phase",
        "saturation_not_converged",
        "not_converged",
        _starved(lambda: ev(451.25, 1.0e4, "VAPOR", ("Psat",))),
        lambda: ev(451.25, 1.0e4, "VAPOR", ("Psat",)),
    ),
    (
        "flash",
        "unsupported_specification",
        "unsupported",
        lambda: flash(*L_AMBIENT, spec="PH"),
        lambda: flash(*L_AMBIENT),
    ),
    (
        "flash",
        "flash_derivatives_unsupported",
        "unsupported",
        lambda: flash(*L_AMBIENT, der=("T",)),
        lambda: flash(*L_AMBIENT),
    ),
    (
        "flash",
        "state_length",
        "error",
        lambda: flash(*L_AMBIENT, n=(1.0, 0.0)),
        lambda: flash(*L_AMBIENT),
    ),
    (
        "flash",
        "out_of_domain",
        "out_of_domain",
        lambda: flash(1273.16, 1.0e5),
        lambda: flash(1273.15, 1.0e8),
    ),
    (
        "flash",
        "near_critical",
        "unsupported",
        lambda: flash(647.5, 2.21e7),
        lambda: flash(648.0, 2.21e7),
    ),
    (
        "flash",
        "tp_flash_degenerate",
        "unsupported",
        lambda: flash(BAND_T, BAND_IN_LO),
        lambda: flash(BAND_T, BAND_OUT_LO),
    ),
]


def test_a30_the_probe_table_covers_every_code_of_section_4_5() -> None:
    phase, flash_codes = spec_codes()
    assert len(phase) == 10 and len(flash_codes) == 6  # rows 1-9 (9 has two codes); items 1-7
    assert {code for entry, code, *_ in PROBES if entry == "evaluate_phase"} == set(phase)
    assert {code for entry, code, *_ in PROBES if entry == "flash"} == flash_codes
    for entry, code, status, *_ in PROBES:
        if entry == "evaluate_phase":
            assert phase[code] == status, code


@pytest.mark.parametrize(
    ("entry", "code", "status", "probe", "control"),
    PROBES,
    ids=[f"{entry}-{code}" for entry, code, *_ in PROBES],
)
def test_a30_each_probe_is_refused_and_its_control_answered(
    entry: str, code: str, status: str, probe: Callable[[], Any], control: Callable[[], Any]
) -> None:
    del entry
    refused = probe()
    assert (refused.status, code_of(refused)) == (status, code), refused.message
    assert refused.message.startswith(code + ":")
    answered = control()
    assert answered.status == "ok", answered.message


def test_the_manifest_generator_reads_the_thirty_three_assertions() -> None:
    generator = _script("s05_evidence_manifest")
    rows = generator.assertion_table(SPEC.read_text("utf-8"))
    assert tuple(rows) == generator.ASSERTIONS and len(rows) == 33
    assert generator.cited("tests/test_s05_envelope.py::test_a22_robustness_grid[300.0]") == (
        "A22",
    )
