"""S10-C WO-2: `ph_state` for a composition-dependent K — the band-first route (design note
`docs/derivations/S10C-design.md` §4.5; specification `docs/derivations/S10C-spec.md` §5.2–§5.3,
assertions S10C.A10–A15 (G4) and A20–A22 (G5); ADR 0049 D4–D5).

Expectations and tolerances are read from `benchmarks/s10c/reference_values.yaml` (the 50-digit
generator `docs/derivations/scripts/s10c_reference.py`), never from the code's output. The closure
rows (A13, A21) are recomputed here from the provider's `evaluate_phase`, not taken from the kernel.

The records are S10's committed sets plus two copies built here as the specification prescribes
(§5.1): `ideal` (every Λ_ij = 1.0) and `narrowed` (T ∈ [342, 365] K). Nothing here is evidence
about a real mixture beyond what S10 already registered.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
import yaml
from conftest import REPO_ROOT

from openflowsheet.compiled import EvaluationContext
from openflowsheet.models.syn001 import ENERGY_TOLERANCE, FLOW_TOLERANCE, ph_kernel
from openflowsheet.models.syn001.ph_kernel import EQUILIBRIUM_TOLERANCE, PHState, ph_state
from openflowsheet.thermo import FlashRequest, PropertyRequest, StreamState
from openflowsheet.thermo.wilson_ig import WilsonIdealGasProvider

CONTEXT = EvaluationContext(model_version="S10C-WO2@" + "0" * 64, constants_sha256="0" * 64)
REFERENCE = REPO_ROOT / "benchmarks" / "s10c" / "reference_values.yaml"
VERIFICATION = REPO_ROOT / "benchmarks" / "s10" / "verification-records.yaml"
REAL = REPO_ROOT / "benchmarks" / "s10" / "records.yaml"


def _document(path: Path) -> dict[str, Any]:
    document = yaml.safe_load(path.read_text("utf-8"))
    assert isinstance(document, dict)
    return document


REF = _document(REFERENCE)
PH_TARGETS: dict[str, dict[str, Any]] = REF["ph_targets"]
E2_STATES: dict[str, dict[str, Any]] = REF["e2_states"]
TOL_G4: dict[str, float] = REF["tolerances"]["G4"]
TOL_G5: dict[str, float] = REF["tolerances"]["G5"]
SOLVED = sorted(key for key, target in PH_TARGETS.items() if target["expected"]["status"] == "ok")
REFUSED = sorted(key for key, target in PH_TARGETS.items() if target["expected"]["status"] != "ok")


# -- providers ------------------------------------------------------------------------------------


def _write(document: dict[str, Any], path: Path) -> Path:
    path.write_text(yaml.safe_dump(document, sort_keys=False), "utf-8")
    return path


@pytest.fixture(scope="module")
def providers(tmp_path_factory: pytest.TempPathFactory) -> dict[str, WilsonIdealGasProvider]:
    """The four record sets the YAML's `records` names, the two copies built per spec §5.1."""
    assert REF["records"]["narrowed"].endswith("domain T = [342.0, 365.0] K (built by the test)")
    ideal = _document(VERIFICATION)
    for entry in ideal["wilson_lambda"]:
        entry["value"] = 1.0
    narrowed = _document(VERIFICATION)
    narrowed["domain"]["T"] = [342.0, 365.0]
    directory = tmp_path_factory.mktemp("s10c-ph")
    return {
        "real": WilsonIdealGasProvider(REAL),
        "verification": WilsonIdealGasProvider(VERIFICATION),
        "ideal": WilsonIdealGasProvider(_write(ideal, directory / "ideal-records.yaml")),
        "narrowed": WilsonIdealGasProvider(_write(narrowed, directory / "narrowed-records.yaml")),
    }


class _FlashCount:
    calls = 0


@pytest.fixture
def flash_count(
    monkeypatch: pytest.MonkeyPatch, providers: dict[str, WilsonIdealGasProvider]
) -> Iterator[_FlashCount]:
    """A13/A14's spy: counts `provider.flash` calls on every record set, delegating each."""
    count = _FlashCount()
    for provider in providers.values():
        original = provider.flash

        def counting(
            request: FlashRequest,
            context: EvaluationContext,
            original: Callable[..., Any] = original,
        ) -> Any:
            count.calls += 1
            return original(request, context)

        monkeypatch.setattr(provider, "flash", counting)
    yield count


def _solve(provider: WilsonIdealGasProvider, entry: dict[str, Any]) -> PHState:
    return ph_state(
        provider, tuple(entry["n"]), float(entry["P"]), float(entry["H_target"]), CONTEXT
    )


# -- the closure rows, recomputed here (A13) ------------------------------------------------------


def _independent_rows(
    provider: WilsonIdealGasProvider, n: tuple[float, ...], answer: PHState, target: float
) -> tuple[float, float, float]:
    """`(material, equilibrium, energy)` of the PH closure at an `ok` answer, from the provider:
    K from LIQUID `lnphi_<c>` at the answer's liquid composition (0.0 rows at a dormant liquid),
    the energy from `n_tot h` of each flowing stream against `H*`."""
    assert answer.split is not None and answer.temperature is not None
    vapor, liquid = answer.split.vapor, answer.split.liquid
    assert vapor is not None and liquid is not None
    components = provider.describe().components
    temperature, pressure = answer.temperature, liquid.pressure
    material = max(abs(v + w - z) for v, w, z in zip(vapor.n, liquid.n, n, strict=True))
    equilibrium = 0.0
    if any(value != 0.0 for value in liquid.n):
        result = provider.evaluate_phase(
            PropertyRequest(
                state=StreamState(n=liquid.n, temperature=temperature, pressure=pressure),
                phase="LIQUID",
                properties=tuple(f"lnphi_{c}" for c in components),
            ),
            CONTEXT,
        )
        assert result.status == "ok", result.message
        big_v, big_l = sum(vapor.n), sum(liquid.n)
        equilibrium = max(
            abs(v * big_l - math.exp(result.values[f"lnphi_{c}"]) * w * big_v)
            for v, w, c in zip(vapor.n, liquid.n, components, strict=True)
        )
    total = 0.0
    for phase, stream in (("VAPOR", vapor), ("LIQUID", liquid)):
        if all(value == 0.0 for value in stream.n):
            continue
        result = provider.evaluate_phase(
            PropertyRequest(
                state=StreamState(n=stream.n, temperature=temperature, pressure=pressure),
                phase=phase,  # type: ignore[arg-type]
                properties=("h",),
            ),
            CONTEXT,
        )
        assert result.status == "ok", result.message
        total += sum(stream.n) * result.values["h"]
    return material, equilibrium, abs(total - target)


def _assert_rows_close(
    provider: WilsonIdealGasProvider, n: tuple[float, ...], answer: PHState, target: float
) -> None:
    material, equilibrium, energy = _independent_rows(provider, n, answer, target)
    assert material <= FLOW_TOLERANCE, material
    assert equilibrium <= EQUILIBRIUM_TOLERANCE, equilibrium
    assert energy <= ENERGY_TOLERANCE, energy


def _composition(flows: tuple[float, ...]) -> tuple[float, ...]:
    total = sum(flows)
    return tuple(value / total for value in flows)


# -- G4: the PH targets (A10–A14) -----------------------------------------------------------------


@pytest.mark.parametrize("key", SOLVED)
def test_g4_ph_target_is_the_registered_answer(
    key: str, providers: dict[str, WilsonIdealGasProvider], flash_count: _FlashCount
) -> None:
    """A10, A13, A14: `ok`, the registered route and signature, T*, β* and the outlet flows within
    G4's tolerances; the closure rows recomputed here; the provider's TP flash called exactly the
    registered number of times (0, or 1 at a narrowed domain end inside the band)."""
    entry = PH_TARGETS[key]
    expected = entry["expected"]
    provider = providers[entry["records"]]
    n = tuple(float(value) for value in entry["n"])
    answer = _solve(provider, entry)
    assert answer.status == "ok", answer.message
    assert answer.route == expected["route"]
    assert answer.split is not None and answer.temperature is not None
    assert answer.split.phase_signature == expected["phase_signature"]
    assert abs(answer.temperature - expected["T"]) <= TOL_G4["T"]
    beta = answer.split.vapor_fraction
    assert beta is not None
    if expected["phase_signature"] == "TWO_PHASE":
        assert abs(beta - expected["vapor_fraction"]) <= TOL_G4["vapor_fraction"]
    else:
        assert beta == expected["vapor_fraction"]
    vapor, liquid = answer.split.vapor, answer.split.liquid
    assert vapor is not None and liquid is not None
    flow_tolerance = TOL_G4["flow_rel_n_tot"] * sum(n)
    for got, want in zip(liquid.n, expected["liquid_n"], strict=True):
        assert abs(got - want) <= flow_tolerance
    for got, want in zip(vapor.n, expected["vapor_n"], strict=True):
        assert abs(got - want) <= flow_tolerance
    _assert_rows_close(provider, n, answer, float(entry["H_target"]))
    assert flash_count.calls == expected["provider_tp_flash_calls"]


@pytest.mark.parametrize(
    "key", [k for k in SOLVED if PH_TARGETS[k]["expected"]["phase_signature"] != "TWO_PHASE"]
)
def test_g4_single_phase_answer_is_exact(
    key: str, providers: dict[str, WilsonIdealGasProvider]
) -> None:
    """A11: the named phase carries the feed bitwise, the other is dormant (every flow `+0.0`) at
    `(T*, P)`, `k_values == {}` and `iterations == 0`."""
    entry = PH_TARGETS[key]
    expected = entry["expected"]
    n = tuple(float(value) for value in entry["n"])
    answer = _solve(providers[entry["records"]], entry)
    assert answer.status == "ok" and answer.split is not None
    split = answer.split
    assert split.vapor is not None and split.liquid is not None
    named, other = (
        (split.vapor, split.liquid)
        if expected["phase_signature"] == "VAPOR"
        else (split.liquid, split.vapor)
    )
    assert named.n == n
    assert all(value == 0.0 and math.copysign(1.0, value) == 1.0 for value in other.n)
    for stream in (named, other):
        assert stream.temperature == answer.temperature
        assert stream.pressure == float(entry["P"])
    assert split.k_values == {}
    assert split.iterations == 0


@pytest.mark.parametrize("key", REFUSED)
def test_g4_target_outside_the_domain_is_refused_typed(
    key: str, providers: dict[str, WilsonIdealGasProvider], flash_count: _FlashCount
) -> None:
    """A12, A14: `out_of_domain` with today's code, no temperature and no split; the registered
    number of TP-flash calls."""
    entry = PH_TARGETS[key]
    expected = entry["expected"]
    answer = _solve(providers[entry["records"]], entry)
    assert answer.status == expected["status"] == "out_of_domain"
    assert answer.code == expected["code"]
    assert answer.message.splitlines()[0] == expected["code"]
    assert answer.temperature is None and answer.split is None
    assert flash_count.calls == expected["provider_tp_flash_calls"]


def test_g4_band_route_compositions_match_the_reference(
    providers: dict[str, WilsonIdealGasProvider],
) -> None:
    """A10's flows, restated as compositions where the YAML registers `x`, `y`: the band route's
    liquid and vapour compositions within G4's flow tolerance (relative to a unit total)."""
    checked = 0
    for key in SOLVED:
        entry = PH_TARGETS[key]
        expected = entry["expected"]
        if "x" not in expected:
            continue
        answer = _solve(providers[entry["records"]], entry)
        assert answer.split is not None
        assert answer.split.liquid is not None and answer.split.vapor is not None
        x = _composition(answer.split.liquid.n)
        y = _composition(answer.split.vapor.n)
        for got, want in zip((*x, *y), (*expected["x"], *expected["y"]), strict=True):
            assert abs(got - want) <= TOL_G4["flow_rel_n_tot"], key
        checked += 1
    assert checked >= 6


# -- G5: the 13 E-2 states (A20–A22) --------------------------------------------------------------


def _e2_failures(provider: WilsonIdealGasProvider, entry: dict[str, Any]) -> list[str]:
    """What G5 (A20, A21's rows) finds wrong with `ph_state` at one E-2 state; empty = pass."""
    expected = entry["expected"]
    n = tuple(float(value) for value in entry["n"])
    answer = _solve(provider, entry)
    if answer.status != "ok":
        return [f"status {answer.status}: {answer.message.splitlines()[0]}"]
    assert answer.split is not None and answer.temperature is not None
    failures = []
    if answer.route != expected["route"]:
        failures.append(f"route {answer.route}")
    if answer.split.phase_signature != expected["phase_signature"]:
        failures.append(f"signature {answer.split.phase_signature}")
    if not abs(answer.temperature - expected["T"]) <= TOL_G5["T"]:
        failures.append(f"T off by {answer.temperature - expected['T']!r}")
    beta = answer.split.vapor_fraction
    if beta is None or not abs(beta - expected["vapor_fraction"]) <= TOL_G5["vapor_fraction"]:
        failures.append(f"beta {beta!r}")
    assert answer.split.liquid is not None and answer.split.vapor is not None
    if sum(answer.split.liquid.n) > 0.0 and sum(answer.split.vapor.n) > 0.0:
        x = _composition(answer.split.liquid.n)
        y = _composition(answer.split.vapor.n)
        worst = max(
            abs(got - want)
            for got, want in zip((*x, *y), (*expected["x"], *expected["y"]), strict=True)
        )
        if not worst <= TOL_G5["x_y"]:
            failures.append(f"x, y off by {worst!r}")
    else:
        failures.append("a phase is empty")
    material, equilibrium, energy = _independent_rows(provider, n, answer, float(entry["H_target"]))
    if not (
        material <= FLOW_TOLERANCE
        and equilibrium <= EQUILIBRIUM_TOLERANCE
        and energy <= ENERGY_TOLERANCE
    ):
        failures.append(f"rows {material!r}, {equilibrium!r}, {energy!r}")
    return failures


def test_e2_states_are_the_registered_thirteen() -> None:
    """The YAML's E-2 states are `tests/test_s10_flash.py::NEAR_AZEOTROPE` (spec §5.3)."""
    from test_s10_flash import NEAR_AZEOTROPE

    assert len(E2_STATES) == len(NEAR_AZEOTROPE) == 13
    for entry, (flows, temperature) in zip(E2_STATES.values(), NEAR_AZEOTROPE, strict=True):
        assert tuple(entry["n"]) == (0.0, *flows)
        assert entry["T_state"] == temperature


@pytest.mark.parametrize("key", sorted(E2_STATES))
def test_g5_e2_state_is_solved_on_the_band_route(
    key: str, providers: dict[str, WilsonIdealGasProvider], flash_count: _FlashCount
) -> None:
    """A20, A21: `ok`, route `band`, TWO_PHASE, T* within 1e-10 K, β* within 1e-9, x and y within
    1e-9 of the 50-digit answer; the closure rows recomputed here; no TP-flash call."""
    entry = E2_STATES[key]
    assert _e2_failures(providers["verification"], entry) == []
    assert flash_count.calls == entry["expected"]["provider_tp_flash_calls"] == 0


# -- M3: the TP-flash bracket route in place of §4.5 (A22) ----------------------------------------


def test_m3_the_tp_flash_bracket_route_fails_g5(
    monkeypatch: pytest.MonkeyPatch, providers: dict[str, WilsonIdealGasProvider]
) -> None:
    """A22: with `ph_state`'s composition-dependent branch replaced by today's temperature route
    (the provider's TP flash bracketed in T, accepted on the same liquid-K rows, no band-route
    fallback), G5 fails at least one of the 13 E-2 states: not `ok`, or not accepted."""

    def mutant(
        provider: Any, n: Any, pressure: float, target: float, context: Any, budget: int
    ) -> PHState:
        with monkeypatch.context() as patch:
            # Today's body: the dispatch disabled, the band fallback removed, and the rows kept
            # composition-aware so that only the route differs from §4.5.
            patch.setattr(ph_kernel, "form_of", lambda capabilities: None)
            patch.setattr(ph_kernel, "_closure_rows", ph_kernel._liquid_k_rows)
            patch.setattr(ph_kernel, "_band_route", lambda *args: None)
            return ph_kernel.ph_state(
                provider, n, pressure, target, context, max_evaluations=budget
            )

    monkeypatch.setattr(ph_kernel, "_band_first", mutant)
    verification = providers["verification"]
    failed = {key: _e2_failures(verification, entry) for key, entry in E2_STATES.items()}
    detected = sorted(key for key, failures in failed.items() if failures)
    assert detected, "M3 not detected by G5: every E-2 state passed through the TP-flash bracket"


# -- one component with T_sat outside the domain (design §4.5, "no sign change") -------------------


@pytest.mark.parametrize(
    ("n", "phase"),
    [((1.0, 0.0, 0.0), "VAPOR"), ((0.0, 0.0, 1.0), "LIQUID")],
    ids=["VA-boils-below-T_min", "VC-boils-above-T_max"],
)
def test_one_component_single_phase_on_the_whole_domain(
    n: tuple[float, ...],
    phase: str,
    providers: dict[str, WilsonIdealGasProvider],
    flash_count: _FlashCount,
) -> None:
    """On the narrowed domain [342, 365] K pure VA boils below `T_min` (338.05 K at 1 atm) and
    pure VC above `T_max` (373.18 K): `ln K` has no sign change, so the stream is vapour or liquid
    on the whole domain. `H*` is built from the provider's `h` at 350 K; the answer is 350 K within
    G4's tolerance on the bracket route. A target 1 MW past `T_max`'s enthalpy is refused."""
    provider = providers["narrowed"]
    pressure = 101325.0
    result = provider.evaluate_phase(
        PropertyRequest(
            state=StreamState(n=n, temperature=350.0, pressure=pressure),
            phase=phase,  # type: ignore[arg-type]
            properties=("h",),
        ),
        CONTEXT,
    )
    assert result.status == "ok", result.message
    target = sum(n) * result.values["h"]
    answer = ph_state(provider, n, pressure, target, CONTEXT)
    assert answer.status == "ok", answer.message
    assert answer.route == "bracket"
    assert answer.split is not None and answer.temperature is not None
    assert answer.split.phase_signature == phase
    assert abs(answer.temperature - 350.0) <= TOL_G4["T"]
    _assert_rows_close(provider, n, answer, target)
    assert flash_count.calls == 0
    beyond = ph_state(provider, n, pressure, target + 1.0e6, CONTEXT)
    assert (beyond.status, beyond.code) == ("out_of_domain", "ph_outside_domain(above)")
