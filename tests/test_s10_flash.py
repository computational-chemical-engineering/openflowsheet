"""S10.A12-A22 and A23 (the flash half): the TP flash `S10-tp-flash-v1`, `stability()` and the
`FlashResult.message` grammar of `wilson-ig-v1` (S10 spec §4, §5.4-§5.5, §7.1, §7.3; ADR 0047;
WO-S10-2).

Every expectation comes from `benchmarks/s10/reference_values.yaml`, which
`docs/derivations/scripts/s10_reference.py` writes at 50 digits from
`benchmarks/s10/verification-records.yaml` (Newton-polished fixed points, never the
implementation). The records are three SYNTHETIC components (spec §6): nothing here is evidence
about a real mixture. Tolerances are spec §7.3's: trial distances absolute TOL_TM; two-phase
outputs per state and output from the YAML's `tolerances.flash.per_state`; `k_values` relative;
single-phase outlets bitwise; the component balance 1e-13 n_tot.
"""

from __future__ import annotations

import dataclasses
import math
import re
from pathlib import Path
from typing import Any

import pytest
import yaml
from conftest import REPO_ROOT

from openflowsheet.thermo import FlashRequest, FlashResult, StreamState, wilson_ig
from openflowsheet.thermo.wilson_ig import WilsonIdealGasProvider

RECORDS = REPO_ROOT / "benchmarks" / "s10" / "verification-records.yaml"
REFERENCE: dict[str, Any] = yaml.safe_load(
    (REPO_ROOT / "benchmarks" / "s10" / "reference_values.yaml").read_text("utf-8")
)
F_STATES: dict[str, Any] = REFERENCE["closed_form"]["flash"]
QUERIES: dict[str, Any] = REFERENCE["closed_form"]["stability_queries"]
PER_STATE: dict[str, Any] = REFERENCE["tolerances"]["flash"]["per_state"]
COMPONENTS = ("VA", "VB", "VC")
#: Spec §7.3, the YAML's `tolerances.tm.TOL_TM`.
TOL_TM: float = REFERENCE["tolerances"]["tm"]["TOL_TM"]
#: Spec §7.3: the component balance of a two-phase result, relative to n_tot.
TOL_BALANCE = 1.0e-13
#: S10.A17: the fugacity residual is at most 10 DELTA_K.
RESIDUAL_MAX = 1.0e-12
SCOPE = "S10-tpd-v1"
CONTEXT: Any = None

SINGLE = tuple(f for f, e in F_STATES.items() if e["phase_signature"] in ("LIQUID", "VAPOR"))
TWO_PHASE = tuple(f for f, e in F_STATES.items() if e["phase_signature"] == "TWO_PHASE")
NON_DORMANT = tuple(f for f in F_STATES if f != "F9")

_NUMBER = r"(-?[0-9][0-9.e+-]*|-?inf|nan)"
#: Spec §5.4's grammar of `ok` messages (R = Python repr(float)).
GRAMMAR = {
    "LIQUID": re.compile(
        rf"stability: STABLE_WITHIN_TESTED_SCOPE; scope: {SCOPE}; "
        rf"tm_vapour_trial: {_NUMBER}; tm_liquid_trial: not_evaluated"
    ),
    "VAPOR": re.compile(
        rf"stability: STABLE_WITHIN_TESTED_SCOPE; scope: {SCOPE}; "
        rf"tm_vapour_trial: {_NUMBER}; tm_liquid_trial: {_NUMBER}"
    ),
    "TWO_PHASE": re.compile(
        rf"stability: STABLE_WITHIN_TESTED_SCOPE; scope: {SCOPE}; "
        rf"tm_vapour_trial: {_NUMBER}; tm_liquid_trial: {_NUMBER}; fugacity_residual: {_NUMBER}"
    ),
}


@pytest.fixture(scope="module")
def provider() -> WilsonIdealGasProvider:
    return WilsonIdealGasProvider(RECORDS)


def _state(fid: str) -> StreamState:
    entry = F_STATES[fid]["state"]
    return StreamState(n=tuple(entry["n"]), temperature=entry["T"], pressure=entry["P"])


def _flash(provider: WilsonIdealGasProvider, fid: str) -> FlashResult:
    return provider.flash(FlashRequest(state=_state(fid)), CONTEXT)


@pytest.fixture(scope="module")
def results(provider: WilsonIdealGasProvider) -> dict[str, FlashResult]:
    return {fid: _flash(provider, fid) for fid in F_STATES}


def _bits(state: StreamState) -> tuple[str, ...]:
    return (*(v.hex() for v in state.n), state.temperature.hex(), state.pressure.hex())


def _assert_dormant(outlet: StreamState | None, state: StreamState) -> None:
    assert outlet is not None
    assert all(v == 0.0 and math.copysign(1.0, v) == 1.0 for v in outlet.n)
    assert len(outlet.n) == len(state.n)
    assert outlet.temperature.hex() == state.temperature.hex()
    assert outlet.pressure.hex() == state.pressure.hex()


def _ratio(got: float, want: float, tolerance: float) -> float:
    return abs(got - want) / tolerance


def _two_phase_ratios(fid: str, result: FlashResult) -> dict[str, float]:
    """|impl - expected| / tolerance for every two-phase output of spec §7.3 at `fid` (outputs
    whose tolerance is absent are the exact zeros of an absent component, checked apart)."""
    entry, tolerance = F_STATES[fid], PER_STATE[fid]["per_output"]
    assert result.vapor is not None and result.liquid is not None
    assert result.vapor_fraction is not None
    ratios = {"beta": _ratio(result.vapor_fraction, entry["vapor_fraction"], tolerance["beta"])}
    vapor_total, liquid_total = sum(result.vapor.n), sum(result.liquid.n)
    for i, c in enumerate(COMPONENTS):
        outputs = {
            "nV": (result.vapor.n[i], entry["vapor_n"][c]),
            "nL": (result.liquid.n[i], entry["liquid_n"][c]),
            "y": (result.vapor.n[i] / vapor_total, entry["y"][c]),
            "x": (result.liquid.n[i] / liquid_total, entry["x"][c]),
        }
        for key, (got, want) in outputs.items():
            if f"{key}_{c}" in tolerance:
                ratios[f"{key}_{c}"] = _ratio(got, want, tolerance[f"{key}_{c}"])
        k_tolerance = tolerance.get(f"k_relative_{c}", tolerance["k_relative"])
        ratios[f"K_{c}"] = abs(result.k_values[c] / entry["k_values"][c] - 1.0) / k_tolerance
    return ratios


def _message_tm(message: str, key: str) -> float | None:
    match = re.search(rf"{key}: ([^;]+)", message)
    assert match is not None, message
    return None if match.group(1) == "not_evaluated" else float(match.group(1))


# -- A12: phase signature and vapour fraction -----------------------------------------------------


@pytest.mark.parametrize("fid", sorted(F_STATES))
def test_a12_phase_signature_and_vapour_fraction(results: dict[str, FlashResult], fid: str) -> None:
    result, entry = results[fid], F_STATES[fid]
    assert result.status == "ok", result.message
    assert result.phase_signature == entry["phase_signature"]
    assert result.provider_id == "wilson-ig-v1"
    assert result.reference_convention == "S10-VER-ref-v1"
    if entry["phase_signature"] == "ZERO_FLOW":
        assert result.vapor_fraction is None
    elif entry["phase_signature"] == "TWO_PHASE":
        beta = result.vapor_fraction
        assert beta is not None and 0.0 < beta < 1.0
        assert _ratio(beta, entry["vapor_fraction"], PER_STATE[fid]["per_output"]["beta"]) <= 1.0
    else:
        assert result.vapor_fraction is not None
        assert result.vapor_fraction.hex() == float(entry["vapor_fraction"]).hex()


# -- A13: single-phase outlets are bitwise --------------------------------------------------------


@pytest.mark.parametrize("fid", SINGLE)
def test_a13_single_phase_outlets_are_bitwise(results: dict[str, FlashResult], fid: str) -> None:
    result, state = results[fid], _state(fid)
    liquid = F_STATES[fid]["phase_signature"] == "LIQUID"
    named, other = (result.liquid, result.vapor) if liquid else (result.vapor, result.liquid)
    assert named is not None and _bits(named) == _bits(state)
    _assert_dormant(other, state)
    assert result.k_values == {}
    # Spec §5.4: 0 iterations for a result decided by the closed-form vapour trial; the liquid
    # trial's count for a vapour.
    assert (result.iterations == 0) if liquid else (result.iterations >= 1)


# -- A14, A15, A16: two-phase outputs --------------------------------------------------------------


@pytest.mark.parametrize("fid", TWO_PHASE)
def test_a14_a15_two_phase_outputs(results: dict[str, FlashResult], fid: str) -> None:
    ratios = _two_phase_ratios(fid, results[fid])
    worst = max(ratios, key=ratios.__getitem__)
    assert ratios[worst] <= 1.0, (worst, ratios[worst])


@pytest.mark.parametrize("fid", TWO_PHASE)
def test_a15_absent_components_are_exact_zeros_with_k_at_infinite_dilution(
    results: dict[str, FlashResult], fid: str
) -> None:
    result, state = results[fid], _state(fid)
    assert result.vapor is not None and result.liquid is not None
    assert tuple(result.k_values) == COMPONENTS
    for i, c in enumerate(COMPONENTS):
        if state.n[i] == 0.0:
            assert result.vapor.n[i] == 0.0 and result.liquid.n[i] == 0.0
            assert math.copysign(1.0, result.vapor.n[i]) == 1.0
            assert math.copysign(1.0, result.liquid.n[i]) == 1.0
            assert math.isfinite(result.k_values[c]) and result.k_values[c] > 0.0
    absent = [c for i, c in enumerate(COMPONENTS) if state.n[i] == 0.0]
    assert absent == (["VA"] if fid in ("F4", "F5") else [])


def test_a14_a15_worst_agreement(results: dict[str, FlashResult]) -> None:
    """The worst ratio to its tolerance over every two-phase output (recorded in the run log)."""
    worst = max(
        (
            (ratio, f"{fid}.{key}")
            for fid in TWO_PHASE
            for key, ratio in _two_phase_ratios(fid, results[fid]).items()
        ),
    )
    assert worst[0] <= 1.0, worst


@pytest.mark.parametrize("fid", TWO_PHASE)
def test_a16_component_balance(results: dict[str, FlashResult], fid: str) -> None:
    result, state = results[fid], _state(fid)
    assert result.vapor is not None and result.liquid is not None
    total = state.total_flow
    for nv, nl, n in zip(result.vapor.n, result.liquid.n, state.n, strict=True):
        assert abs(nv + nl - n) <= TOL_BALANCE * total
    assert result.vapor.temperature == result.liquid.temperature == state.temperature
    assert result.vapor.pressure == result.liquid.pressure == state.pressure


# -- A17: the message grammar ----------------------------------------------------------------------


@pytest.mark.parametrize("fid", NON_DORMANT)
def test_a17_the_message_grammar(results: dict[str, FlashResult], fid: str) -> None:
    result, entry = results[fid], F_STATES[fid]
    assert GRAMMAR[entry["phase_signature"]].fullmatch(result.message), result.message
    assert entry["stability"]["label"] == "STABLE_WITHIN_TESTED_SCOPE"
    for key in ("tm_vapour_trial", "tm_liquid_trial"):
        got, want = _message_tm(result.message, key), entry["stability"][key]
        if want is None:
            assert got is None
        else:
            assert got is not None and abs(got - want) <= TOL_TM, (key, got, want)
    if entry["phase_signature"] == "TWO_PHASE":
        residual = float(result.message.rsplit("fugacity_residual: ", 1)[1])
        assert 0.0 <= residual <= RESIDUAL_MAX


def test_a17_the_liquid_trial_is_not_evaluated_exactly_for_f1_f6a_f7_f12(
    results: dict[str, FlashResult],
) -> None:
    skipped = {
        fid for fid in NON_DORMANT if "tm_liquid_trial: not_evaluated" in results[fid].message
    }
    assert skipped == {"F1", "F6a", "F7", "F12"}


def test_a17_the_resolution_band_decides_f7_f8_f10_f11(results: dict[str, FlashResult]) -> None:
    """F7 and F11 lie in [-EPS_TPD, 0) and stay single-phase; F8 and F10 lie just outside and
    split (spec §4.3). The distances the flash states put them there."""
    tm_v = {f: _message_tm(results[f].message, "tm_vapour_trial") for f in ("F7", "F8")}
    tm_l = {f: _message_tm(results[f].message, "tm_liquid_trial") for f in ("F10", "F11")}
    assert tm_v["F7"] is not None and -1.0e-10 <= tm_v["F7"] < 0.0
    assert tm_v["F8"] is not None and tm_v["F8"] < -1.0e-10
    assert tm_l["F11"] is not None and -1.0e-10 <= tm_l["F11"] < 0.0
    assert tm_l["F10"] is not None and tm_l["F10"] < -1.0e-10
    assert (results["F7"].phase_signature, results["F8"].phase_signature) == ("LIQUID", "TWO_PHASE")
    assert (results["F11"].phase_signature, results["F10"].phase_signature) == (
        "VAPOR",
        "TWO_PHASE",
    )


# -- A18: the dormant feed -------------------------------------------------------------------------


def test_a18_the_dormant_feed(results: dict[str, FlashResult]) -> None:
    result, state = results["F9"], _state("F9")
    assert result.status == "ok" and result.phase_signature == "ZERO_FLOW"
    assert result.vapor_fraction is None
    _assert_dormant(result.vapor, state)
    _assert_dormant(result.liquid, state)
    assert result.k_values == {} and result.iterations == 0
    assert result.message == (
        "stability: UNKNOWN; scope: S10-tpd-v1; reason: dormant_state: composition undefined "
        "(ADR 0001 D3.1, D3.4)"
    )


# -- A19: refusals through flash -------------------------------------------------------------------


def _request(
    n: tuple[float, ...] = (0.6, 1.0, 0.4),
    t: float = 350.0,
    p: float = 1.2e5,
    specification: str = "TP",
    derivatives: tuple[str, ...] = (),
) -> FlashRequest:
    return FlashRequest(
        state=StreamState(n=n, temperature=t, pressure=p),
        specification=specification,
        derivatives=derivatives,
    )


R_STATES: dict[str, tuple[FlashRequest, str, str]] = {
    "R1": (_request(t=299.0), "out_of_domain", "out_of_domain"),
    "R2": (_request(p=4.0e5), "out_of_domain", "out_of_domain"),
    "R3": (_request(n=(-1e-12, 1.0, 1.0)), "out_of_domain", "out_of_domain"),
    "R4": (_request(t=math.nan), "out_of_domain", "out_of_domain"),
    "R5": (_request(n=(1.0, 1.0)), "error", "state_length"),
    "R6": (_request(specification="PH"), "unsupported", "unsupported_specification"),
    "R7": (_request(derivatives=("T",)), "unsupported", "flash_derivatives_unsupported"),
}


@pytest.mark.parametrize("rid", sorted(R_STATES))
def test_a19_refusals(provider: WilsonIdealGasProvider, rid: str) -> None:
    request, status, code = R_STATES[rid]
    result = provider.flash(request, CONTEXT)
    assert result.status == status, result.message
    assert result.message.startswith(f"{code}: "), result.message
    assert result.vapor is None and result.liquid is None
    assert result.vapor_fraction is None and result.phase_signature is None
    assert result.k_values == {} and result.iterations == 0


def test_the_message_rule(
    provider: WilsonIdealGasProvider, results: dict[str, FlashResult]
) -> None:
    """Spec §5.4: every ok or not_converged result begins with `stability: `, every refusal with
    its code; never neither."""
    every = [*results.values(), *(provider.flash(r, CONTEXT) for r, _, _ in R_STATES.values())]
    for result in every:
        if result.status in ("ok", "not_converged"):
            assert result.message.startswith("stability: "), result.message
        else:
            assert re.match(r"[a-z_]+: ", result.message), result.message
            assert not result.message.startswith("stability: ")


# -- A20: unsupported is a result ------------------------------------------------------------------


def test_a20_the_liquid_trial_cap_is_not_converged(
    provider: WilsonIdealGasProvider, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(wilson_ig, "SS_MAX", 1)
    result = _flash(provider, "F2")
    assert result.status == "not_converged"
    assert result.vapor is None and result.liquid is None
    assert result.vapor_fraction is None and result.phase_signature is None
    assert result.k_values == {} and result.iterations == 1
    assert result.message.startswith(
        "stability: UNKNOWN; scope: S10-tpd-v1; reason: stability_not_converged: "
    ), result.message
    # The same cap through stability(): UNKNOWN with no distance (spec §5.5).
    report = provider.stability(_state("F2"), "VAPOR", CONTEXT)
    assert report.label == "UNKNOWN"
    assert report.reason.startswith("stability_not_converged: ")
    assert report.tm == {"VAPOR": None, "LIQUID": None} and report.trial_composition is None
    assert report.iterations == 1 and report.residual is not None and report.residual > 1e-13


def test_a20_the_two_phase_cap_is_not_converged(
    provider: WilsonIdealGasProvider, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(wilson_ig, "SS_MAX_TWO_PHASE", 1)
    result = _flash(provider, "F3")
    assert result.status == "not_converged"
    assert result.vapor is None and result.liquid is None
    assert result.vapor_fraction is None and result.phase_signature is None
    assert result.k_values == {}
    assert result.message.startswith(
        "stability: UNKNOWN; scope: S10-tpd-v1; reason: two_phase_not_converged: "
    ), result.message


def test_a20_no_rachford_rice_bracket_is_not_converged(provider: WilsonIdealGasProvider) -> None:
    """Step 4a's refusal: K_i > 1 for every flowing component has no bracket, and the split says
    so instead of returning a β."""
    search = wilson_ig._Search(provider.records, _state("F3"))
    split = search.two_phase((0.1, 0.2, 0.3))
    assert split.failure is not None and split.failure.startswith("no Rachford-Rice bracket")
    assert split.iterations == 1 and split.k == () and math.isnan(split.beta)


@pytest.mark.parametrize(
    ("z", "k"),
    [
        ((0.3, 0.7), (2.5, 0.4)),
        ((0.5, 0.5), (1.0 + 1e-6, 1.0 - 1e-6)),
        ((0.999999, 1e-6), (1.2, 1e-3)),
        ((0.05, 0.95), (30.0, 0.9)),
    ],
)
def test_rachford_rice_closes_on_the_binary_root(
    z: tuple[float, float], k: tuple[float, float]
) -> None:
    """Step 4a against the analytic binary root β = -(z1 d1 + z2 d2)/(d1 d2), d = K - 1: f changes
    sign within 4 ulp of the returned β, and β agrees with the root to its conditioning."""
    beta = wilson_ig._rachford_rice(z, k)
    d1, d2 = k[0] - 1.0, k[1] - 1.0
    root = -(z[0] * d1 + z[1] * d2) / (d1 * d2)

    def f(b: float) -> float:
        return sum(zi * (ki - 1.0) / (1.0 + b * (ki - 1.0)) for zi, ki in zip(z, k, strict=True))

    step = 4.0 * math.ulp(beta)
    assert f(beta) == 0.0 or f(beta - step) >= 0.0 >= f(beta + step)  # f is decreasing
    assert abs(beta - root) <= 1e-9 * max(1.0, abs(root))


# -- A21, A22: stability() -------------------------------------------------------------------------


@pytest.mark.parametrize("fid", sorted(QUERIES))
@pytest.mark.parametrize("phase", ["LIQUID", "VAPOR"])
def test_a21_stability_queries(provider: WilsonIdealGasProvider, fid: str, phase: str) -> None:
    want = QUERIES[fid][phase]
    report = provider.stability(_state(fid), phase, CONTEXT)  # type: ignore[arg-type]
    trial = "VAPOR" if phase == "LIQUID" else "LIQUID"
    assert report.label == want["label"]
    assert report.scope == SCOPE and report.epsilon == 1e-10 and report.phase == phase
    assert report.reason == ""
    got = report.tm[trial]
    assert got is not None and abs(got - want["tm"]) <= TOL_TM, (got, want["tm"])
    assert report.tm[phase] is None
    assert report.trial_composition is not None
    assert abs(sum(report.trial_composition) - 1.0) <= 1e-15
    assert all(w > 0.0 for w in report.trial_composition)  # every component flows at these states
    if phase == "LIQUID":
        assert report.iterations == 0 and report.residual is None
    else:
        assert 1 <= report.iterations <= 100
        assert report.residual is not None and report.residual <= 1e-13


def test_a21_both_labels_occur(provider: WilsonIdealGasProvider) -> None:
    labels = {
        provider.stability(_state(fid), phase, CONTEXT).label  # type: ignore[arg-type]
        for fid in QUERIES
        for phase in ("LIQUID", "VAPOR")
    }
    assert labels == {"STABLE_WITHIN_TESTED_SCOPE", "UNSTABLE"}


def test_a21_the_flash_and_stability_state_the_same_distances(
    provider: WilsonIdealGasProvider, results: dict[str, FlashResult]
) -> None:
    """One search: the flash's tm values are stability()'s, bitwise, at every queried state."""
    for fid in QUERIES:
        state = _state(fid)
        tm_v = provider.stability(state, "LIQUID", CONTEXT).tm["VAPOR"]
        assert _message_tm(results[fid].message, "tm_vapour_trial") == tm_v
        stated = _message_tm(results[fid].message, "tm_liquid_trial")
        if stated is not None:
            assert provider.stability(state, "VAPOR", CONTEXT).tm["LIQUID"] == stated


@pytest.mark.parametrize(
    ("state", "reason"),
    [
        (StreamState(n=(0.0, 0.0, 0.0), temperature=350.0, pressure=1.0e5), "dormant_state"),
        (StreamState(n=(0.6, 1.0, 0.4), temperature=299.0, pressure=1.2e5), "out_of_domain"),
        (StreamState(n=(1.0, 1.0), temperature=350.0, pressure=1.2e5), "state_length"),
    ],
)
@pytest.mark.parametrize("phase", ["LIQUID", "VAPOR"])
def test_a22_stability_reports_unknown(
    provider: WilsonIdealGasProvider, state: StreamState, reason: str, phase: str
) -> None:
    report = provider.stability(state, phase, CONTEXT)  # type: ignore[arg-type]
    assert report.label == "UNKNOWN"
    assert report.reason.startswith(f"{reason}: "), report.reason
    assert report.tm == {"VAPOR": None, "LIQUID": None}
    assert report.trial_composition is None and report.iterations == 0 and report.residual is None
    assert report.scope == SCOPE and report.epsilon == 1e-10


def test_a22_an_unknown_phase_is_reported_not_raised(provider: WilsonIdealGasProvider) -> None:
    report = provider.stability(_state("F3"), "SOLID", CONTEXT)  # type: ignore[arg-type]
    assert report.label == "UNKNOWN" and report.reason.startswith("unsupported_phase: ")


# -- Amendment 1 E-1: the flowing set is defined on z ----------------------------------------------


def _hex(value: Any) -> Any:
    """Every float of a result as its hex string, so == compares bits (0.0 and -0.0 differ)."""
    if isinstance(value, float):
        return value.hex()
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {f.name: _hex(getattr(value, f.name)) for f in dataclasses.fields(value)}
    if isinstance(value, dict):
        return {key: _hex(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_hex(item) for item in value]
    return value


@pytest.mark.parametrize(
    ("fid", "n_zero"),
    [("F3", (0.0, 1.0, 1.0)), ("F3", (0.0, 0.0, 2.0)), ("F5", None)],
)
def test_e1_a_flow_whose_z_underflows_is_absent(
    provider: WilsonIdealGasProvider, fid: str, n_zero: tuple[float, ...] | None
) -> None:
    """n_VA = 5e-324 gives z_VA = 0.0 (n_tot is unchanged by it), so the flash and stability()
    return what they return with n_VA = 0.0, bitwise, instead of raising on ln 0; a single-phase
    result still returns the feed itself. F3's two are the review's reproducers (liquid), F5 a
    split."""
    base = _state(fid)
    zero = base if n_zero is None else dataclasses.replace(base, n=n_zero)
    assert zero.n[0] == 0.0
    state = dataclasses.replace(zero, n=(5e-324, *zero.n[1:]))
    assert state.total_flow == zero.total_flow
    for phase in ("LIQUID", "VAPOR"):
        report = provider.stability(state, phase, CONTEXT)
        assert report.label != "UNKNOWN", report.reason
        assert _hex(report) == _hex(provider.stability(zero, phase, CONTEXT))
    result = provider.flash(FlashRequest(state=state), CONTEXT)
    want = provider.flash(FlashRequest(state=zero), CONTEXT)
    assert result.status == "ok"
    if result.phase_signature == "TWO_PHASE":
        assert result.vapor is not None and result.liquid is not None
        assert result.vapor.n[0] == 0.0 and result.liquid.n[0] == 0.0
        assert _hex(result) == _hex(want)
    else:
        feed = result.liquid if result.phase_signature == "LIQUID" else result.vapor
        assert feed is not None and _bits(feed) == _bits(state)
        assert _hex(dataclasses.replace(result, liquid=want.liquid, vapor=want.vapor)) == _hex(want)


# -- A23: permutation (the flash half) -------------------------------------------------------------

PERMUTED = ("VC", "VA", "VB")


def test_a23_permuted_records_give_the_permuted_flash(tmp_path: Path) -> None:
    document = yaml.safe_load(RECORDS.read_text("utf-8"))
    by_id = {c["id"]: c for c in document["components"]}
    document["components"] = [by_id[c] for c in PERMUTED]
    path = tmp_path / "permuted.yaml"
    path.write_text(yaml.safe_dump(document, sort_keys=False), "utf-8")
    permuted = WilsonIdealGasProvider(path)
    assert permuted.describe().components == PERMUTED
    entry, tolerance = F_STATES["F3"], PER_STATE["F3"]["per_output"]
    n = dict(zip(COMPONENTS, entry["state"]["n"], strict=True))
    state = StreamState(
        n=tuple(n[c] for c in PERMUTED),
        temperature=entry["state"]["T"],
        pressure=entry["state"]["P"],
    )
    result = permuted.flash(FlashRequest(state=state), CONTEXT)
    assert result.status == "ok" and result.phase_signature == "TWO_PHASE"
    assert result.vapor is not None and result.liquid is not None
    assert result.vapor_fraction is not None
    assert _ratio(result.vapor_fraction, entry["vapor_fraction"], tolerance["beta"]) <= 1.0
    for i, c in enumerate(PERMUTED):
        assert _ratio(result.vapor.n[i], entry["vapor_n"][c], tolerance[f"nV_{c}"]) <= 1.0
        assert _ratio(result.liquid.n[i], entry["liquid_n"][c], tolerance[f"nL_{c}"]) <= 1.0
    assert tuple(result.k_values) == PERMUTED
    for c in PERMUTED:
        assert abs(result.k_values[c] / entry["k_values"][c] - 1.0) <= tolerance["k_relative"]
    for key in ("tm_vapour_trial", "tm_liquid_trial"):
        got = _message_tm(result.message, key)
        assert got is not None and abs(got - entry["stability"][key]) <= TOL_TM
    # The stability report's trial composition is permuted too.
    report = permuted.stability(state, "VAPOR", CONTEXT)
    reference = WilsonIdealGasProvider(RECORDS).stability(_state("F3"), "VAPOR", CONTEXT)
    assert report.trial_composition is not None and reference.trial_composition is not None
    for i, c in enumerate(PERMUTED):
        w = reference.trial_composition[COMPONENTS.index(c)]
        assert abs(report.trial_composition[i] - w) <= 1e-12
