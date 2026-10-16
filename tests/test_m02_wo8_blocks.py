"""M02 WO-8.1: the `pr-c1-v1` property blocks, B17's dormancy convention and the solver-side
`classify` (design note §14.2 B11, B14, B17; register R-254, R-256, R-258; gate G7 (h)).

Expectations: the provider's own answers at M01's registered states (`benchmarks/m01/
reference_values.yaml` → `closed_form.phase_states`, `flash_states`), which M01.A05–A22 verified
against 50-digit closed forms; central finite differences for the flowing Jacobians; B17's table for
exact dormancy. Finite differences are not compared at exactly zero columns (the liquid's light-gas
flows, where any step leaves the provider's domain, and every column of a dormant stream): there
the convention is asserted instead (B17 *Consequence*).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any

import numpy as np
import pytest
from conftest import REPO_ROOT, load_yaml

from openflowsheet.compile.casadi_backend import compile_problem
from openflowsheet.compile.spec import DomainError, EquationSpec, ProblemSpec
from openflowsheet.compiled import EvaluationContext
from openflowsheet.models import SpecificationError
from openflowsheet.models.c1 import TAU_DEW
from openflowsheet.models.c1.blocks import (
    PROBE,
    LiquidEnthalpyFlow,
    LiquidLnPhiNH3,
    VapourEnthalpyFlow,
    VapourLnPhiNH3,
    block_feeding,
    hdot_block_id,
    lnphi_block_id,
)
from openflowsheet.models.c1.phase import classify
from openflowsheet.orchestrator.budget import PropertyMeter
from openflowsheet.thermo import (
    FlashRequest,
    Phase,
    PropertyRequest,
    PropertyResult,
    StreamState,
)
from openflowsheet.thermo.pr_c1 import COMPONENTS, PrC1Provider, h_ig
from openflowsheet.thermo.syn001 import Syn001Provider

CLOSED = load_yaml(REPO_ROOT / "benchmarks" / "m01" / "reference_values.yaml")["closed_form"]
PHASES: Mapping[str, Any] = CLOSED["phase_states"]
FLASH: Mapping[str, Any] = CLOSED["flash_states"]
CONTEXT = EvaluationContext(model_version="m02-wo8-blocks", constants_sha256="0" * 64)
PROVIDER = PrC1Provider()
INPUTS = (*(f"n_{c}" for c in COMPONENTS), "T", "P")
LIGHT_COLUMNS = (0, 1, 3, 4)

Block = VapourEnthalpyFlow | VapourLnPhiNH3 | LiquidEnthalpyFlow | LiquidLnPhiNH3


def _blocks(phase: Phase) -> tuple[Block, Block]:
    """The enthalpy-flow and ln φ blocks of one phase, on stream `S`."""
    if phase == "VAPOR":
        return (
            VapourEnthalpyFlow(PROVIDER, CONTEXT, block_id=hdot_block_id("S", "VAPOR")),
            VapourLnPhiNH3(PROVIDER, CONTEXT, block_id=lnphi_block_id("S", "VAPOR")),
        )
    return (
        LiquidEnthalpyFlow(PROVIDER, CONTEXT, block_id=hdot_block_id("S", "LIQUID")),
        LiquidLnPhiNH3(PROVIDER, CONTEXT, block_id=lnphi_block_id("S", "LIQUID")),
    )


def _provider(
    n: Sequence[float], t: float, p: float, phase: Phase, prop: str, derivatives: bool = False
) -> PropertyResult:
    result = PROVIDER.evaluate_phase(
        PropertyRequest(
            state=StreamState(n=tuple(n), temperature=t, pressure=p),
            phase=phase,
            properties=(prop,),
            derivatives=INPUTS if derivatives else (),
        ),
        CONTEXT,
    )
    assert result.status == "ok", result.message
    return result


def _f1(product: str) -> tuple[float, ...]:
    """F1's flash product (`vapor` or `liquid`), from the provider (M01.A15 checks it)."""
    state = FLASH["F1"]
    result = PROVIDER.flash(
        FlashRequest(
            state=StreamState(
                n=tuple(state["n_mol_s"]), temperature=state["T_K"], pressure=state["P_Pa"]
            )
        ),
        CONTEXT,
    )
    assert result.status == "ok" and result.phase_signature == "TWO_PHASE"
    outlet = result.vapor if product == "vapor" else result.liquid
    assert outlet is not None
    return outlet.n


def _states() -> list[tuple[str, Phase, tuple[float, ...], float, float]]:
    states: list[tuple[str, Phase, tuple[float, ...], float, float]] = []
    for sid in ("V1", "V2", "L1"):
        entry = PHASES[sid]
        states.append((sid, entry["phase"], tuple(entry["n_mol_s"]), entry["T_K"], entry["P_Pa"]))
    f1 = FLASH["F1"]
    states.append(("F1-vapour", "VAPOR", _f1("vapor"), f1["T_K"], f1["P_Pa"]))
    states.append(("F1-liquid", "LIQUID", _f1("liquid"), f1["T_K"], f1["P_Pa"]))
    return states


STATES = _states()
IDS = [sid for sid, *_ in STATES]


def _jacobian(block: Block, inputs: Sequence[float]) -> list[float]:
    dense = [float("nan")] * len(INPUTS)
    entries = block.jacobian(inputs)
    assert sorted((row, column) for row, column, _ in entries) == sorted(block.jacobian_pattern())
    for _, column, value in entries:
        dense[column] = value
    return dense


# -- identity -------------------------------------------------------------------------------------


def test_block_ids_are_the_notes_with_underscores_and_name_the_stream() -> None:
    assert hdot_block_id("S4", "VAPOR") == "S4_Hdot_V"
    assert hdot_block_id("S5", "LIQUID") == "S5_Hdot_L"
    assert lnphi_block_id("S4", "VAPOR") == "S4_lnphi_NH3_V"
    assert lnphi_block_id("S5", "LIQUID") == "S5_lnphi_NH3_L"
    assert block_feeding("S4") == (
        *(f"S4.n.{c}" for c in COMPONENTS),
        "S4.T",
        "S4.P",
    )
    for block in (*_blocks("VAPOR"), *_blocks("LIQUID")):
        assert block.input_ids == INPUTS
        assert len(block.output_ids) == 1
        assert block.jacobian_pattern() == tuple((0, c) for c in range(7))


@pytest.mark.parametrize(
    "kind", [VapourEnthalpyFlow, VapourLnPhiNH3, LiquidEnthalpyFlow, LiquidLnPhiNH3]
)
def test_each_block_refuses_a_provider_other_than_pr_c1_v1(kind: Callable[..., Block]) -> None:
    with pytest.raises(SpecificationError, match="pr-c1-v1"):
        kind(Syn001Provider(), CONTEXT, block_id="S_x")


def test_a_metered_provider_is_accepted_and_describe_is_not_counted() -> None:
    meter = PropertyMeter(PrC1Provider())
    VapourEnthalpyFlow(meter, CONTEXT, block_id="S_Hdot_V")
    assert meter.calls == 0


# -- flowing values: the provider's, bitwise ------------------------------------------------------


@pytest.mark.parametrize(("sid", "phase", "n", "t", "p"), STATES, ids=IDS)
def test_flowing_values_are_the_providers_bitwise(
    sid: str, phase: Phase, n: tuple[float, ...], t: float, p: float
) -> None:
    hdot, lnphi = _blocks(phase)
    inputs = (*n, t, p)
    h = _provider(n, t, p, phase, "h").values["h"]
    assert list(hdot.values(inputs)) == [sum(n) * h]
    expected = _provider(n, t, p, phase, "lnphi_NH3").values["lnphi_NH3"]
    assert list(lnphi.values(inputs)) == [expected]


def test_registered_values_are_reached_through_the_blocks() -> None:
    """V1's h and ln φ_NH3 and L1's (M01.A05's registered closed forms, to 1e-12 relative)."""
    pairs: tuple[tuple[str, Phase], ...] = (("V1", "VAPOR"), ("L1", "LIQUID"))
    for sid, phase in pairs:
        entry = PHASES[sid]
        n = tuple(entry["n_mol_s"])
        hdot, lnphi = _blocks(phase)
        inputs = (*n, entry["T_K"], entry["P_Pa"])
        assert hdot.values(inputs)[0] == pytest.approx(sum(n) * entry["values"]["h"], rel=1e-12)
        assert lnphi.values(inputs)[0] == pytest.approx(entry["values"]["lnphi_NH3"], rel=1e-12)


# -- flowing Jacobians: central finite differences ------------------------------------------------


#: The witness's relative step. WO-8.1's acceptance names 1e-6; measured there, the central
#: difference's own roundoff (ε |f| / h) reaches 1.9e-7 of the entry for the vapour ln φ's smallest
#: entries (V1, ∂/∂n_N2 = 1.25e-3 beside |ln φ| = 4.2e-3), and shrinks with the step — 7.3e-9 at
#: 1e-5, 2.8e-9 at 1e-4 over every entry — so at 1e-6 the comparison measures the witness, not the
#: Jacobian. The tolerance stays 1e-7 of each entry's magnitude; the step is 1e-4 (build log D34).
FD_STEP = 1e-4


def _central(block: Block, inputs: Sequence[float], column: int) -> float:
    step = FD_STEP * abs(inputs[column])
    up, down = list(inputs), list(inputs)
    up[column] += step
    down[column] -= step
    return (block.values(up)[0] - block.values(down)[0]) / (2.0 * step)


@pytest.mark.parametrize(("sid", "phase", "n", "t", "p"), STATES, ids=IDS)
def test_flowing_jacobians_match_central_differences(
    sid: str, phase: Phase, n: tuple[float, ...], t: float, p: float
) -> None:
    inputs = (*n, t, p)
    for block in _blocks(phase):
        analytic = _jacobian(block, inputs)
        for column, value in enumerate(analytic):
            if inputs[column] == 0.0:
                continue  # an exactly zero column: asserted below, not differenced
            witness = _central(block, inputs, column)
            assert abs(value - witness) <= 1e-7 * abs(value), (block.block_id, INPUTS[column])


@pytest.mark.parametrize(("sid", "phase", "n", "t", "p"), STATES, ids=IDS)
def test_flowing_jacobians_are_the_chain_rule_of_the_providers_derivatives(
    sid: str, phase: Phase, n: tuple[float, ...], t: float, p: float
) -> None:
    """`∂Ḣ/∂n_j = h + Σn ∂h/∂n_j`, `∂Ḣ/∂T = Σn ∂h/∂T` (and P), ln φ's as given — bitwise. On a
    liquid every flow derivative of h and ln φ is the provider's composition-free `0.0`, so the
    light-gas columns no step can reach read `h` and `0.0`."""
    hdot, lnphi = _blocks(phase)
    inputs = (*n, t, p)
    result = _provider(n, t, p, phase, "h", derivatives=True)
    h, by = result.values["h"], result.derivatives["h"]
    total = sum(n)
    expected = [h + total * by[name] for name in INPUTS[:5]] + [total * by["T"], total * by["P"]]
    assert _jacobian(hdot, inputs) == expected
    by_phi = _provider(n, t, p, phase, "lnphi_NH3", derivatives=True).derivatives["lnphi_NH3"]
    assert _jacobian(lnphi, inputs) == [by_phi[name] for name in INPUTS]
    if phase == "LIQUID":
        for column in LIGHT_COLUMNS:
            assert _jacobian(hdot, inputs)[column] == h
            assert _jacobian(lnphi, inputs)[column] == 0.0


# -- refusals of a flowing stream -----------------------------------------------------------------


def test_a_flowing_liquid_without_a_liquid_root_is_refused_as_an_invalid_trial() -> None:
    """673.15 K is above NH3's EOS critical temperature: no liquid root. The probe's fallback is
    never taken for a flowing liquid (B17)."""
    inputs = (0.0, 0.0, 1.0, 0.0, 0.0, 673.15, 1.0e7)
    for block in _blocks("LIQUID"):
        with pytest.raises(DomainError, match="no_liquid_root"):
            block.values(inputs)
        with pytest.raises(DomainError, match="no_liquid_root"):
            block.jacobian(inputs)


def test_a_liquid_carrying_light_gas_is_refused_as_an_invalid_trial() -> None:
    inputs = (1e-300, 0.0, 1.0, 0.0, 0.0, 268.15, 1.0e7)
    for block in _blocks("LIQUID"):
        with pytest.raises(DomainError, match="light_gas_in_liquid"):
            block.values(inputs)


def test_a_negative_flow_is_refused_as_an_invalid_trial() -> None:
    inputs = (1.0, -1.0, 0.0, 0.0, 0.0, 300.0, 1.0e7)
    for block in _blocks("VAPOR"):
        with pytest.raises(DomainError, match="out_of_domain"):
            block.values(inputs)


# -- exact dormancy: B17's table, bitwise (G7 (h)) ------------------------------------------------

DORMANT_POINTS = [
    (268.15, 1.0e7),  # the separator: pure NH3 has a liquid root
    (300.0, 1.0e7),
    (673.15, 1.0e7),  # above T_c,EOS: the liquid probe falls back to VAPOR
]


def _probe(t: float, p: float, phase: Phase, prop: str) -> PropertyResult:
    return _provider(PROBE, t, p, phase, prop, derivatives=True)


def _dormancy_expectations(t: float, p: float) -> dict[str, tuple[float, list[float]]]:
    """B17's table at `(T, P)`: block kind → (value, Jacobian row)."""
    has_liquid = PROVIDER.evaluate_phase(
        PropertyRequest(
            state=StreamState(n=PROBE, temperature=t, pressure=p),
            phase="LIQUID",
            properties=("h",),
        ),
        CONTEXT,
    )
    probe_phase: Phase = "LIQUID" if has_liquid.status == "ok" else "VAPOR"
    if probe_phase == "VAPOR":
        assert has_liquid.message.startswith("no_liquid_root")
    h_probe = _probe(t, p, probe_phase, "h").values["h"]
    phi = _probe(t, p, probe_phase, "lnphi_NH3")
    return {
        "Hdot_V": (0.0, [h_ig(t, j) for j in range(5)] + [0.0, 0.0]),
        "lnphi_V": (0.0, [0.0] * 7),
        "Hdot_L": (0.0, [h_probe] * 5 + [0.0, 0.0]),
        "lnphi_L": (
            phi.values["lnphi_NH3"],
            [0.0] * 5 + [phi.derivatives["lnphi_NH3"]["T"], phi.derivatives["lnphi_NH3"]["P"]],
        ),
    }


@pytest.mark.parametrize(("t", "p"), DORMANT_POINTS)
@pytest.mark.parametrize("zero", [0.0, -0.0])
def test_b17_dormancy_values_on_the_blocks(t: float, p: float, zero: float) -> None:
    expected = _dormancy_expectations(t, p)
    inputs = (zero,) * 5 + (t, p)
    hdot_v, lnphi_v = _blocks("VAPOR")
    hdot_l, lnphi_l = _blocks("LIQUID")
    for name, block in (
        ("Hdot_V", hdot_v),
        ("lnphi_V", lnphi_v),
        ("Hdot_L", hdot_l),
        ("lnphi_L", lnphi_l),
    ):
        value, row = expected[name]
        assert list(block.values(inputs)) == [value], name
        assert _jacobian(block, inputs) == row, name


def test_the_liquid_probe_falls_back_to_vapour_exactly_above_the_eos_critical_temperature() -> None:
    """At 673.15 K the probe's LIQUID answer is `no_liquid_root`; the blocks answer from VAPOR."""
    expected = _dormancy_expectations(673.15, 1.0e7)
    vapour = _probe(673.15, 1.0e7, "VAPOR", "lnphi_NH3").values["lnphi_NH3"]
    assert expected["lnphi_L"][0] == vapour
    assert expected["Hdot_L"][1][0] == _probe(673.15, 1.0e7, "VAPOR", "h").values["h"]


def _compiled_dormancy(t: float, p: float) -> tuple[list[float], dict[tuple[str, str], float]]:
    """The four blocks compiled into one problem (a row per block output) at a dormant stream."""
    blocks = (*_blocks("VAPOR"), *_blocks("LIQUID"))
    feeding = block_feeding("S")

    def row(key: str) -> Any:
        def build(variables: Any, outputs: Any, parameters: Any, algebra: Any) -> Any:
            return outputs[key]

        return build

    spec = ProblemSpec(
        label="m02-wo8-g7h",
        variable_ids=feeding,
        equations=tuple(
            EquationSpec(
                equation_id=block.block_id,
                build=row(f"{block.block_id}.{block.output_ids[0]}"),
                accumulation="algebraic",
            )
            for block in blocks
        ),
        parameter_ids=(),
        parameters={},
        blocks=blocks,
        block_inputs={block.block_id: feeding for block in blocks},
    )
    compiled = compile_problem(spec)
    x = np.array([0.0] * 5 + [t, p], dtype=np.float64)
    context = EvaluationContext(
        model_version=compiled.metadata.model_version,
        constants_sha256=compiled.metadata.constants_sha256,
    )
    residual = compiled.residual(x, context)
    jacobian = compiled.jacobian(x, context)
    assert residual.status == "ok" and jacobian.status == "ok"
    assert residual.values is not None
    entries: dict[tuple[str, str], float] = {}
    for column, column_id in enumerate(jacobian.col_ids):
        for k in range(jacobian.indptr[column], jacobian.indptr[column + 1]):
            entries[(jacobian.row_ids[jacobian.indices[k]], column_id)] = jacobian.data[k]
    return list(residual.values), entries


@pytest.mark.parametrize(("t", "p"), DORMANT_POINTS)
def test_g7h_dormancy_values_on_the_compiled_blocks(t: float, p: float) -> None:
    """G7 (h): B17's table, read back through the compiled residual and Jacobian."""
    expected = _dormancy_expectations(t, p)
    values, entries = _compiled_dormancy(t, p)
    names = ("Hdot_V", "lnphi_V", "Hdot_L", "lnphi_L")
    ids = (
        hdot_block_id("S", "VAPOR"),
        lnphi_block_id("S", "VAPOR"),
        hdot_block_id("S", "LIQUID"),
        lnphi_block_id("S", "LIQUID"),
    )
    assert values == [expected[name][0] for name in names]
    for name, row in zip(names, ids, strict=True):
        compiled_row = [entries.get((row, column), 0.0) for column in block_feeding("S")]
        assert compiled_row == expected[name][1], name


# -- classify: M01 §7 rule 3 with τ_dew ----------------------------------------------------------


def test_tau_dew_is_adr_0001_d6s_composition_tolerance() -> None:
    assert TAU_DEW == 1e-10


@pytest.mark.parametrize("fid", list(FLASH))
def test_classify_on_the_registered_flash_states(fid: str) -> None:
    """The provider's phase on F1–F14, except F4: at its own dew point it is VAPOR by the band
    (whatever O(ε) liquid the flash reports there, M01 F4)."""
    state = FLASH[fid]
    n, t, p = tuple(state["n_mol_s"]), state["T_K"], state["P_Pa"]
    regime, value, result = classify(PROVIDER, CONTEXT, n, t, p)
    assert result.status == "ok"
    total = sum(n)
    if fid == "F4":
        assert regime == "VAPOR"
        if result.phase_signature == "TWO_PHASE":
            assert result.liquid is not None
            assert value == result.liquid.n[2] / total <= TAU_DEW
        else:
            assert value == 0.0
        return
    assert regime == result.phase_signature == state["phase_signature"]
    if regime == "TWO_PHASE":
        assert result.liquid is not None
        assert value == result.liquid.n[2] / total > TAU_DEW
    elif regime == "LIQUID":
        assert value == (n[0] + n[1] + n[3] + n[4]) / total
    else:
        assert value == 0.0


def test_classify_reads_a_band_two_phase_answer_as_vapour_and_a_wider_one_as_two_phase() -> None:
    """F4's feed with NH3 raised by δ: `l/n_tot ≈ 0.0616 δ` (design note §14.2, G7 (k))."""
    base = FLASH["F4"]
    n = list(base["n_mol_s"])
    t, p = base["T_K"], base["P_Pa"]
    for delta, expected in ((8.1e-10, "VAPOR"), (3.2e-9, "TWO_PHASE")):
        raised = (*n[:2], n[2] * (1.0 + delta), *n[3:])
        regime, value, result = classify(PROVIDER, CONTEXT, raised, t, p)
        assert result.phase_signature == "TWO_PHASE"
        assert regime == expected, (delta, value)


def test_classify_passes_a_refusal_through() -> None:
    regime, value, result = classify(PROVIDER, CONTEXT, (1.0, 0.0, 0.0, 0.0, 0.0), 100.0, 1.0e7)
    assert regime is None and value != value and result.status == "out_of_domain"
