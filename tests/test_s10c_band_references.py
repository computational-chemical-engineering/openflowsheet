"""S10-C G3: the constant-β point against its registered references (S10C.A01–A06, A61).

`docs/derivations/S10C-spec.md` §5.1 and §6 (with Amendment 1 E3); review finding F1. Every
expectation and tolerance is read from `benchmarks/s10c/reference_values.yaml` (`ref`), whose
band points are 50-digit Newton solutions of the square system in `(T, x_F)` (spec §9), never the
successive substitution the implementation uses:

- **A01** every registered point of `ref.band_points`: the position exactly; for `inside`, `T`, the
  returned liquid `x` and `k_values` of every component (an absent one's: infinite-dilution K);
- **A02** the number of temperature solves (`_Point.temperature` calls, counted by a spy that
  forwards every call unchanged; Amendment 1 E3): exactly 1 where `iterations_expected` is 1, at
  most `ref.tolerances.G3.iterations` elsewhere (R-776's watch on a slower contraction);
- **A03** on the `narrowed` copy, `below` / `above` carry no temperature;
- **A04** on the `ideal` copy (Λ ≡ 1), β = 0 and 1 against this file's own bisection of Raoult's
  bubble and dew conditions and against `BP-I01.closed_forms`;
- **A05** `tm` of the provider's liquid trial vanishes at every inside β = 1 point, and equals
  `tm_star` at the two `ref.theorems.T2` states;
- **A06** the returned point's own rows over F;
- **A61** the committed record files are the ones the expectations were derived from.

The `ideal` and `narrowed` copies are built here from the verification records (spec §5.1).
"""

from __future__ import annotations

import hashlib
import math
from pathlib import Path
from typing import Any

import pytest
import yaml
from conftest import REPO_ROOT
from test_s10c_band_point import _bisect, _ln_psat

from openflowsheet.compiled import EvaluationContext
from openflowsheet.models.syn001 import gamma_phi
from openflowsheet.models.syn001.saturation_band import BandTemperature, band_temperature
from openflowsheet.thermo import StreamState
from openflowsheet.thermo.wilson_ig import WilsonIdealGasProvider

CONTEXT = EvaluationContext(model_version="S10C-G3@" + "0" * 64, constants_sha256="0" * 64)
REF: dict[str, Any] = yaml.safe_load(
    (REPO_ROOT / "benchmarks" / "s10c" / "reference_values.yaml").read_text("utf-8")
)
TOL: dict[str, Any] = REF["tolerances"]["G3"]
TOL_T: float = TOL["T"]
TOL_X: float = TOL["x"]
TOL_K_REL: float = TOL["K_rel"]
MAX_ITERATIONS: int = TOL["iterations"]
TOL_TM: float = TOL["tm_at_dew"]
TOL_ROWS: float = TOL["fixed_point_rows"]
#: The narrowed copy's T domain (spec §5.1: `records.narrowed`).
NARROWED_T = [342.0, 365.0]

BAND_POINTS: dict[str, Any] = REF["band_points"]
KEYS = [
    (name, index, point)
    for name, case in BAND_POINTS.items()
    for index, point in enumerate(case["points"])
]
POINTS = [
    pytest.param(name, index, id=f"{name}-beta{point['beta']}") for name, index, point in KEYS
]
INSIDE_DEW = [
    pytest.param(name, index, id=f"{name}-beta{point['beta']}")
    for name, index, point in KEYS
    if point["beta"] == 1.0 and point["position"] == "inside"
]
NARROWED = [
    pytest.param(name, index, id=f"{name}-beta{point['beta']}")
    for name, index, point in KEYS
    if BAND_POINTS[name]["records"] == "narrowed"
]


def _committed(name: str) -> Path:
    return REPO_ROOT / str(REF["records"][name]["path"])


def _document(name: str) -> dict[str, Any]:
    document = yaml.safe_load(_committed(name).read_text("utf-8"))
    assert isinstance(document, dict)
    return document


@pytest.fixture(scope="module")
def providers(tmp_path_factory: pytest.TempPathFactory) -> dict[str, WilsonIdealGasProvider]:
    """The four record sets of spec §5.1; the two copies keep the convention `S10-VER-ref-v1`."""
    directory = tmp_path_factory.mktemp("s10c-g3")
    ideal = _document("verification")
    for entry in ideal["wilson_lambda"]:
        entry["value"] = 1.0
    narrowed = _document("verification")
    narrowed["domain"]["T"] = list(NARROWED_T)
    built = {}
    for name, document in (("ideal", ideal), ("narrowed", narrowed)):
        path = directory / f"{name}-records.yaml"
        path.write_text(yaml.safe_dump(document, sort_keys=False), "utf-8")
        built[name] = WilsonIdealGasProvider(path)
    return {
        "real": WilsonIdealGasProvider(_committed("real")),
        "verification": WilsonIdealGasProvider(_committed("verification")),
        **built,
    }


_SOLVED: dict[tuple[str, int], tuple[BandTemperature, int]] = {}


def _solved(
    providers: dict[str, WilsonIdealGasProvider], name: str, index: int
) -> tuple[BandTemperature, int]:
    """The point through `band_temperature`'s dispatch, and its number of temperature solves.

    The spy wraps `gamma_phi._Point.temperature` and forwards each call with its arguments
    untouched, so the answer is the production one (S10C.A02 as amended by E3).
    """
    key = (name, index)
    if key not in _SOLVED:
        case = BAND_POINTS[name]
        point = case["points"][index]
        original = gamma_phi._Point.temperature
        solves = 0

        def counted(self: Any, *args: Any, **kwargs: Any) -> Any:
            nonlocal solves
            solves += 1
            return original(self, *args, **kwargs)

        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(gamma_phi._Point, "temperature", counted)
            answer = band_temperature(
                providers[case["records"]],
                tuple(case["n"]),
                case["P"],
                point["beta"],
                CONTEXT,
            )
        _SOLVED[key] = (answer, solves)
    return _SOLVED[key]


@pytest.mark.parametrize(("name", "index"), POINTS)
def test_a01_the_registered_band_points(
    providers: dict[str, WilsonIdealGasProvider], name: str, index: int
) -> None:
    """S10C.A01: position exact; T 1e-9 K, x 1e-10, K 1e-9 relative (every component)."""
    expected = BAND_POINTS[name]["points"][index]
    answer, _ = _solved(providers, name, index)
    assert answer.position == expected["position"]
    if expected["position"] != "inside":
        return
    assert answer.temperature is not None
    assert abs(answer.temperature - expected["T"]) <= TOL_T, (answer.temperature, expected["T"])
    assert len(answer.liquid) == len(expected["x"])
    for i, (got, want) in enumerate(zip(answer.liquid, expected["x"], strict=True)):
        assert abs(got - want) <= TOL_X, (i, got, want)
    assert len(answer.k_values) == len(expected["K"])
    for i, (got, want) in enumerate(zip(answer.k_values, expected["K"], strict=True)):
        assert abs(got - want) <= TOL_K_REL * abs(want), (i, got, want)


@pytest.mark.parametrize(("name", "index"), POINTS)
def test_a02_the_number_of_temperature_solves(
    providers: dict[str, WilsonIdealGasProvider], name: str, index: int
) -> None:
    """S10C.A02 (E3): 1 where `iterations_expected` is 1; at most G3's `iterations` elsewhere."""
    expected = BAND_POINTS[name]["points"][index]["iterations_expected"]
    _, solves = _solved(providers, name, index)
    if expected == 1:
        assert solves == 1
    else:
        assert expected == f"<= {MAX_ITERATIONS}"
        assert 1 <= solves <= MAX_ITERATIONS, solves


@pytest.mark.parametrize(("name", "index"), NARROWED)
def test_a03_positions_off_the_narrowed_domain_carry_no_temperature(
    providers: dict[str, WilsonIdealGasProvider], name: str, index: int
) -> None:
    """S10C.A03: on the narrowed copy the string equals `ref`; `below` / `above` have no T."""
    expected = BAND_POINTS[name]["points"][index]["position"]
    answer, _ = _solved(providers, name, index)
    assert answer.position == expected
    if expected != "inside":
        assert answer.temperature is None
        assert answer.k_values == ()
        assert answer.liquid == ()


@pytest.mark.parametrize("beta", [0.0, 1.0])
def test_a04_the_ideal_limit_against_bisection_and_the_closed_forms(
    providers: dict[str, WilsonIdealGasProvider], beta: float
) -> None:
    """S10C.A04: Λ ≡ 1, `Σ z_i P_i^sat = P` (β = 0) and `Σ z_i/P_i^sat = 1/P` (β = 1)."""
    case = BAND_POINTS["BP-I01"]
    assert case["records"] == "ideal"
    pressure = case["P"]
    total = math.fsum(case["n"])
    z = [value / total for value in case["n"]]
    document = _document("verification")
    ln_psat = _ln_psat(document)
    t_min, t_max = (float(end) for end in document["domain"]["T"])

    def k(temperature: float) -> list[float]:
        return [math.exp(f(temperature)) / pressure for f in ln_psat]

    def bubble(temperature: float) -> float:  # Σ z_i P_i^sat = P
        return math.fsum(zi * ki for zi, ki in zip(z, k(temperature), strict=True)) - 1.0

    def dew(temperature: float) -> float:  # Σ z_i/P_i^sat = 1/P
        return 1.0 - math.fsum(zi / ki for zi, ki in zip(z, k(temperature), strict=True))

    if beta == 0.0:
        bisected = _bisect(bubble, t_min, t_max)
        closed_form = case["closed_forms"]["T_bubble"]
    else:
        bisected = _bisect(dew, t_min, t_max)
        closed_form = case["closed_forms"]["T_dew"]
    index = next(i for i, point in enumerate(case["points"]) if point["beta"] == beta)
    answer, _ = _solved(providers, "BP-I01", index)
    assert answer.position == "inside"
    assert answer.temperature is not None
    assert abs(answer.temperature - bisected) <= TOL_T, (answer.temperature, bisected)
    assert abs(answer.temperature - closed_form) <= TOL_T, (answer.temperature, closed_form)


@pytest.mark.parametrize(("name", "index"), INSIDE_DEW)
def test_a05_the_liquid_trial_vanishes_at_every_inside_dew_point(
    providers: dict[str, WilsonIdealGasProvider], name: str, index: int
) -> None:
    """S10C.A05: `tm["LIQUID"]` of the vapour at `(n, T_d, P)` is zero to 1e-12."""
    case = BAND_POINTS[name]
    answer, _ = _solved(providers, name, index)
    assert answer.temperature is not None
    state = StreamState(n=tuple(case["n"]), temperature=answer.temperature, pressure=case["P"])
    report = providers[case["records"]].stability(state, "VAPOR", CONTEXT)
    tm = report.tm["LIQUID"]
    assert tm is not None, report.reason
    assert abs(tm) <= TOL_TM, tm


@pytest.mark.parametrize("label", sorted(REF["theorems"]["T2"]))
def test_a05_the_liquid_trial_at_the_t2_states_is_tm_star(
    providers: dict[str, WilsonIdealGasProvider], label: str
) -> None:
    """S10C.A05: 0.5 K off `T_d`, `tm` equals the registered non-vanishing `tm_star`."""
    case = REF["theorems"]["T2"][label]
    state = StreamState(n=tuple(case["n"]), temperature=case["T"], pressure=case["P"])
    report = providers[case["records"]].stability(state, "VAPOR", CONTEXT)
    tm = report.tm["LIQUID"]
    assert tm is not None, report.reason
    assert abs(tm - case["tm_star"]) <= TOL_TM, (tm, case["tm_star"])


@pytest.mark.parametrize(("name", "index"), POINTS)
def test_a06_the_returned_points_own_rows(
    providers: dict[str, WilsonIdealGasProvider], name: str, index: int
) -> None:
    """S10C.A06: `x_i (1 + β(K_i − 1)) − z_i` and `Σ z_i (K_i − 1)/(1 + β(K_i − 1))` over F."""
    case = BAND_POINTS[name]
    beta = case["points"][index]["beta"]
    answer, _ = _solved(providers, name, index)
    if answer.position != "inside":
        return
    total = math.fsum(case["n"])
    z = [value / total for value in case["n"]]
    flowing = [i for i, value in enumerate(z) if value > 0.0]
    k, x = answer.k_values, answer.liquid
    material = max(abs(x[i] * (1.0 + beta * (k[i] - 1.0)) - z[i]) for i in flowing)
    assert material <= TOL_ROWS, material
    rachford_rice = math.fsum(z[i] * (k[i] - 1.0) / (1.0 + beta * (k[i] - 1.0)) for i in flowing)
    assert abs(rachford_rice) <= TOL_ROWS, rachford_rice


@pytest.mark.parametrize("name", ["real", "verification"])
def test_a61_the_record_files_are_the_registered_ones(name: str) -> None:
    """S10C.A61: a moved record invalidates every expectation."""
    digest = hashlib.sha256(_committed(name).read_bytes()).hexdigest()
    assert digest == REF["records"][name]["sha256"]
