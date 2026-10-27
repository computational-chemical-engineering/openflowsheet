"""S11 WO-D4: `wilson-ig-v2`, v1's answers bit for bit and the molar entropy `s` (S11.A75–A78).

`docs/derivations/S11-units-design.md` §4.6 (ADR 0051). The expectations of A76 are
`benchmarks/s11/wilson_entropy_reference.yaml`, produced at 50 digits from the potential by
`docs/derivations/scripts/s11_wilson_entropy_reference.py`, which imports nothing from
`openflowsheet`.
"""

from __future__ import annotations

import dataclasses
import hashlib
import itertools
import math
from collections.abc import Iterator, Mapping, Sequence
from typing import Any

import pytest
import yaml
from conftest import REPO_ROOT
from test_s11_thermal_kernel import FD_TOL, _fd_worst

from openflowsheet.compiled import EvaluationContext
from openflowsheet.models.syn001.equilibrium_form import (
    FORM_GAMMA_PHI_IG,
    admission,
    composition_dependent,
    form_of,
)
from openflowsheet.models.thermal.blocks import IsentropicEnthalpyBlock, isentropic_block_id
from openflowsheet.thermo import FlashRequest, Phase, PropertyRequest, StreamState, wilson_ig
from openflowsheet.thermo.wilson_ig import R, WilsonIdealGasProvider
from openflowsheet.thermo.wilson_ig_v2 import (
    LIMITATION_ADDED,
    PROVENANCE_ADDED,
    PROVIDER_ID,
    UNCERTAINTY_ADDED,
    WilsonIdealGasProviderV2,
)

CONTEXT = EvaluationContext(model_version="S11-WO-D4@" + "0" * 64, constants_sha256="0" * 64)
RECORDS = {
    "verification": REPO_ROOT / "benchmarks" / "s10" / "verification-records.yaml",
    "real": REPO_ROOT / "benchmarks" / "s10" / "records.yaml",
}
#: S10's registered states, per record file.
S10_REFERENCES = {
    "verification": REPO_ROOT / "benchmarks" / "s10" / "reference_values.yaml",
    "real": REPO_ROOT / "benchmarks" / "s10" / "reference_values_real.yaml",
}
ENTROPY: dict[str, Any] = yaml.safe_load(
    (REPO_ROOT / "benchmarks" / "s11" / "wilson_entropy_reference.yaml").read_text(encoding="utf-8")
)
#: SHA-256 of `thermo/wilson_ig.py` at the S11 base `8c34ecb0`: v1 is not edited by a byte (§4.12).
WILSON_V1_SHA256 = "4bcd8f4dc8115b6b35a246bc0bb3324dbac68291440750b9d51a369b042d64b9"
PHASES: tuple[Phase, ...] = ("LIQUID", "VAPOR")


@pytest.fixture(scope="module", params=sorted(RECORDS))
def pair(request: pytest.FixtureRequest) -> tuple[str, WilsonIdealGasProvider, Any]:
    name = request.param
    return name, WilsonIdealGasProvider(RECORDS[name]), WilsonIdealGasProviderV2(RECORDS[name])


def _hexed(value: Any) -> Any:
    """`value` with every float replaced by its `float.hex` (so −0.0 ≠ 0.0 and NaN is a value)."""
    if isinstance(value, float):
        return value.hex()
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {f.name: _hexed(getattr(value, f.name)) for f in dataclasses.fields(value)}
    if isinstance(value, Mapping):
        return {key: _hexed(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_hexed(item) for item in value]
    return value


# -- the states of A75 ---------------------------------------------------------------------------


def _harvest(node: Any) -> Iterator[StreamState]:
    """Every `{n, T, P}` mapping of a registered S10 reference file, in document order."""
    if isinstance(node, Mapping):
        if {"n", "T", "P"} <= set(node) and isinstance(node["n"], list):
            yield StreamState(
                n=tuple(float(v) for v in node["n"]),
                temperature=float(node["T"]),
                pressure=float(node["P"]),
            )
        for item in node.values():
            yield from _harvest(item)
    elif isinstance(node, list):
        for item in node:
            yield from _harvest(item)


def _grid(provider: WilsonIdealGasProvider) -> list[StreamState]:
    """The domain's corners and interior, at interior, binary, pure and dormant compositions."""
    (t_lo, t_hi), (p_lo, p_hi) = (
        provider.records.temperature_domain,
        provider.records.pressure_domain,
    )
    temperatures = (t_lo, 0.5 * (t_lo + t_hi), 0.75 * t_lo + 0.25 * t_hi, t_hi)
    pressures = (p_lo, 101_325.0, p_hi)
    compositions = (
        (1.0, 0.6, 0.4),
        (0.2, 0.2, 0.6),
        (0.7, 0.0, 0.3),
        (0.0, 0.0, 2.0),
        (1e-12, 1.0, 1.0),
        (0.0, 0.0, 0.0),
    )
    return [
        StreamState(n=n, temperature=t, pressure=p)
        for t, p, n in itertools.product(temperatures, pressures, compositions)
    ]


def _states(name: str, provider: WilsonIdealGasProvider) -> list[StreamState]:
    document = yaml.safe_load(S10_REFERENCES[name].read_text(encoding="utf-8"))
    count = len(provider.records.components)
    harvested = [state for state in _harvest(document) if len(state.n) == count]
    assert len(harvested) >= 10, (name, len(harvested))
    return harvested + _grid(provider)


# -- S11.A75 -------------------------------------------------------------------------------------


def test_a75_v1_is_not_edited() -> None:
    source = (REPO_ROOT / "src" / "openflowsheet" / "thermo" / "wilson_ig.py").read_bytes()
    assert hashlib.sha256(source).hexdigest() == WILSON_V1_SHA256
    assert wilson_ig.PROVIDER_ID == "wilson-ig-v1"


def test_a75_describe_is_v1s_with_s(pair: tuple[str, Any, Any]) -> None:
    _, v1, v2 = pair
    old, new = v1.describe(), v2.describe()
    own = (REPO_ROOT / "src" / "openflowsheet" / "thermo" / "wilson_ig_v2.py").read_bytes()
    assert new.provider_id == PROVIDER_ID == "wilson-ig-v2"
    assert (
        new.implementation_sha256
        == hashlib.sha256(own + b"\n" + old.implementation_sha256.encode()).hexdigest()
    )
    assert new.data_sha256 == old.data_sha256
    assert new.properties == (*old.properties, "s")
    assert new.uncertainty == f"{old.uncertainty} {UNCERTAINTY_ADDED}"
    assert new.data_provenance == f"{old.data_provenance} {PROVENANCE_ADDED}"
    assert new.numerical_limitations == (*old.numerical_limitations, LIMITATION_ADDED)
    changed = {
        "provider_id",
        "implementation_sha256",
        "properties",
        "uncertainty",
        "data_provenance",
        "numerical_limitations",
    }
    for field in dataclasses.fields(old):
        if field.name not in changed:
            assert _hexed(getattr(new, field.name)) == _hexed(getattr(old, field.name)), field.name
    assert "v" not in new.properties and "Z" not in new.properties


def test_a75_every_v1_answer_bit_for_bit(pair: tuple[str, Any, Any]) -> None:
    name, v1, v2 = pair
    ids = v1.records.components
    names = ("h", *(f"lnphi_{c}" for c in ids))
    inputs = ("T", "P", *(f"n_{c}" for c in ids))
    states = _states(name, v1)
    compared = 0
    for state, phase in itertools.product(states, PHASES):
        for derivatives in ((), inputs):
            request = PropertyRequest(
                state=state, phase=phase, properties=names, derivatives=derivatives
            )
            want = v1.evaluate_phase(request, CONTEXT)
            got = v2.evaluate_phase(request, CONTEXT)
            assert _hexed(got) == _hexed(want), (state, phase, derivatives)
            # With `s` asked as well, the other properties are still v1's, bit for bit.
            if want.status == "ok" and not (derivatives and 0.0 in state.n):
                with_s = v2.evaluate_phase(
                    dataclasses.replace(request, properties=(*names, "s")), CONTEXT
                )
                assert with_s.status == "ok", with_s.message
                assert _hexed({k: with_s.values[k] for k in names}) == _hexed(want.values)
                assert _hexed({k: with_s.derivatives.get(k) for k in names if derivatives}) == (
                    _hexed({k: want.derivatives.get(k) for k in names if derivatives})
                )
                assert with_s.provider_id == want.provider_id
                assert with_s.reference_convention == want.reference_convention
            compared += 1
        assert _hexed(v2.stability(state, phase, CONTEXT)) == _hexed(
            v1.stability(state, phase, CONTEXT)
        )
    for state in states:
        flash = FlashRequest(state=state, specification="TP")
        assert _hexed(v2.flash(flash, CONTEXT)) == _hexed(v1.flash(flash, CONTEXT)), state
    assert compared >= 4 * len(states)


# -- S11.A76 -------------------------------------------------------------------------------------


def _reference(name: str) -> list[dict[str, Any]]:
    states: list[dict[str, Any]] = ENTROPY["record_files"][name]["states"]
    return states


def test_a76_the_reference_covers_the_assertion() -> None:
    files = ENTROPY["record_files"]
    states = [entry for name in files for entry in files[name]["states"]]
    assert len(states) >= 30
    assert {entry["phase"] for entry in states} == set(PHASES)
    for name, path in RECORDS.items():
        assert files[name]["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
        assert any(0.0 in entry["state"]["n"] for entry in files[name]["states"])


def _ask(v2: WilsonIdealGasProviderV2, entry: Mapping[str, Any], derivatives: Sequence[str]) -> Any:
    state = entry["state"]
    return v2.evaluate_phase(
        PropertyRequest(
            state=StreamState(n=tuple(state["n"]), temperature=state["T"], pressure=state["P"]),
            phase=entry["phase"],
            properties=("s",),
            derivatives=tuple(derivatives),
        ),
        CONTEXT,
    )


def test_a76_s_equals_the_50_digit_reference(pair: tuple[str, Any, Any]) -> None:
    name, _, v2 = pair
    tolerance = ENTROPY["tolerances"]["s_relative"]
    assert tolerance == 1e-13
    worst = 0.0
    for entry in _reference(name):
        result = _ask(v2, entry, ())
        assert result.status == "ok", (entry["id"], result.message)
        want = entry["s"]
        error = abs(result.values["s"] - want) / abs(want)
        worst = max(worst, error)
        assert error <= tolerance, (entry["id"], result.values["s"], want)
    assert worst > 0.0 or len(_reference(name)) == 0


def test_a76_the_derivatives_equal_the_reference(pair: tuple[str, Any, Any]) -> None:
    """S10's evaluate_phase rule, |got − want| ≤ 1e-12 max(|want|, s_q), with s_q = R/T, R/P,
    R/n_tot in s's units (S11D decisions)."""
    name, _, v2 = pair
    tolerance = ENTROPY["tolerances"]["derivative_relative"]
    ids = v2.records.components
    for entry in _reference(name):
        state = entry["state"]
        flowing = all(value > 0.0 for value in state["n"])
        wrt = ("T", "P", *((f"n_{c}" for c in ids) if flowing else ()))
        result = _ask(v2, entry, wrt)
        assert result.status == "ok", (entry["id"], result.message)
        got = result.derivatives["s"]
        expected = {"T": entry["ds_dT"], "P": entry["ds_dP"]}
        floors = {"T": R / state["T"], "P": R / state["P"]}
        if flowing:
            for c in ids:
                expected[f"n_{c}"] = entry["ds_dn"][c]
                floors[f"n_{c}"] = R / sum(state["n"])
        for key, want in expected.items():
            assert abs(got[key] - want) <= tolerance * max(abs(want), floors[key]), (
                entry["id"],
                key,
                got[key],
                want,
            )


# -- S11.A77 -------------------------------------------------------------------------------------


def test_a77_i_ds_dt_is_dh_dt_over_t(pair: tuple[str, Any, Any]) -> None:
    name, v1, v2 = pair
    for entry in _reference(name):
        state = entry["state"]
        stream = StreamState(n=tuple(state["n"]), temperature=state["T"], pressure=state["P"])
        h = v1.evaluate_phase(
            PropertyRequest(
                state=stream, phase=entry["phase"], properties=("h",), derivatives=("T",)
            ),
            CONTEXT,
        )
        ds_dt = _ask(v2, entry, ("T",)).derivatives["s"]["T"]
        want = h.derivatives["h"]["T"] / state["T"]
        assert abs(ds_dt - want) <= 1e-10 * abs(want), entry["id"]


def test_a77_ii_the_pressure_derivatives(pair: tuple[str, Any, Any]) -> None:
    name, _, v2 = pair
    for entry in _reference(name):
        by_p = _ask(v2, entry, ("P",)).derivatives["s"]["P"]
        if entry["phase"] == "LIQUID":
            assert by_p == 0.0 and math.copysign(1.0, by_p) == 1.0, entry["id"]
        else:
            want = -R / entry["state"]["P"]
            assert abs(by_p - want) <= 1e-15 * abs(want), entry["id"]


def test_a77_iii_equal_gibbs_energies_at_saturation(pair: tuple[str, Any, Any]) -> None:
    """Pure i at P = P_i^sat(T), T ∈ {310, 350, 390} K: s^V − s^L = (h^V − h^L)/T.

    Only the (i, T) whose P_i^sat lies in the records' pressure domain can be asked; the others
    are refused `out_of_domain` by v1 (S11D decisions). The reference lists both kinds.
    """
    name, _, v2 = pair
    ids = v2.records.components
    rows = ENTROPY["record_files"][name]["saturation"]
    assert {(row["component"], row["T"]) for row in rows} == {
        (c, float(t)) for c in ids for t in (310, 350, 390)
    }
    asked = 0
    for row in rows:
        n = tuple(1.0 if c == row["component"] else 0.0 for c in ids)
        stream = StreamState(n=n, temperature=row["T"], pressure=row["P_sat"])
        answers = {
            phase: v2.evaluate_phase(
                PropertyRequest(state=stream, phase=phase, properties=("h", "s")), CONTEXT
            )
            for phase in PHASES
        }
        if not row["in_domain"]:
            assert all(answer.status == "out_of_domain" for answer in answers.values())
            continue
        vapour, liquid = answers["VAPOR"].values, answers["LIQUID"].values
        want = (vapour["h"] - liquid["h"]) / row["T"]
        assert abs((vapour["s"] - liquid["s"]) - want) <= 1e-12 * abs(want), row
        asked += 1
    assert asked >= 3, asked


#: Vapour compressions inside both records' domains: (n…, T_I, P_I, P_O).
ISENTROPIC_STATES = [
    (*n, t, p_in, p_out)
    for n in ((0.4, 0.3, 0.3), (1.0, 0.5, 0.2), (0.2, 0.2, 0.6))
    for t in (365.0, 380.0)
    for p_in, p_out in ((60_000.0, 75_000.0), (80_000.0, 100_000.0))
]


def test_a77_iv_the_isentropic_block_jacobian(pair: tuple[str, Any, Any]) -> None:
    """A46's central-difference test on the additive-vapour block over v2's vapour `s`."""
    _, _, v2 = pair
    ids = v2.records.components
    block = IsentropicEnthalpyBlock(
        v2,
        ids,
        CONTEXT,
        block_id=isentropic_block_id("U1"),
        variant="additive-vapour",
        inlet_phase="VAPOR",
        isentropic_phase="VAPOR",
    )
    worst = max(_fd_worst(block, state) for state in ISENTROPIC_STATES)
    assert worst <= FD_TOL, worst


# -- S11.A78 -------------------------------------------------------------------------------------


def test_a78_n_derivatives_of_s_at_a_zero_fraction_are_refused(pair: tuple[str, Any, Any]) -> None:
    name, _, v2 = pair
    ids = v2.records.components
    zero = [entry for entry in _reference(name) if 0.0 in entry["state"]["n"]]
    assert zero
    for entry in zero:
        missing = ids[entry["state"]["n"].index(0.0)]
        for wrt in ids:
            refused = _ask(v2, entry, ("T", f"n_{wrt}"))
            assert refused.status == "unsupported"
            assert refused.values == {}
            assert refused.message == (f"derivative_singular: ds/dn_{missing} at n_{missing} = 0")
        answered = _ask(v2, entry, ("T", "P"))
        assert answered.status == "ok"
        assert set(answered.derivatives["s"]) == {"T", "P"}


def test_a78_v1s_refusals_are_returned_unchanged(pair: tuple[str, Any, Any]) -> None:
    _, v1, v2 = pair
    (t_lo, _), _ = v1.records.temperature_domain, None
    outside = StreamState(n=(1.0, 1.0, 1.0), temperature=t_lo - 1.0, pressure=101_325.0)
    for properties in (("s",), ("h", "s")):
        request = PropertyRequest(state=outside, phase="LIQUID", properties=properties)
        got = v2.evaluate_phase(request, CONTEXT)
        want = v1.evaluate_phase(
            dataclasses.replace(
                request,
                properties=(
                    *(p for p in properties if p != "s"),
                    *(f"lnphi_{c}" for c in v1.records.components),
                ),
            ),
            CONTEXT,
        )
        assert got.status == "out_of_domain"
        assert _hexed(got) == _hexed(want)


# -- the equilibrium form (§4.5, WO-D4) -----------------------------------------------------------


def test_v2_has_v1s_equilibrium_form(pair: tuple[str, Any, Any]) -> None:
    _, v1, v2 = pair
    old, new = form_of(v1.describe()), form_of(v2.describe())
    assert old is not None and new is not None
    assert new.form_id == old.form_id == FORM_GAMMA_PHI_IG
    assert composition_dependent(v2)
    assert dataclasses.replace(new, provider_id=old.provider_id) == old
    assert admission("COL", v2, CONTEXT) is None
