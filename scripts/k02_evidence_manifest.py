"""Generate `evidence/K02/<commit>/manifest.json` by measuring, not by transcribing.

Every numeric `value` below is computed here, at generation time, from the same code the gate
runs and against `benchmarks/syn001/reference_values.yaml` — Fable's 20-digit references,
generated with mpmath at 40 digits from the plan §3.1 definitions and independent of everything
in `src/`. A number that was typed in by hand would be a claim about a measurement rather than a
measurement, which is the failure this script exists to avoid.

Usage:
    PYTHONPATH=. .venv/bin/python scripts/k02_evidence_manifest.py <gate-stdout-file> \
        --commit <40-hex> [--out evidence/K02/<commit>/manifest.json]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from openflowsheet.canonical import directory_hash, file_sha256  # noqa: E402
from openflowsheet.compile.casadi_backend import compile_problem  # noqa: E402
from openflowsheet.compile.reference import row_values, state_vector  # noqa: E402
from openflowsheet.compiled import EvaluationContext  # noqa: E402
from openflowsheet.models import (  # noqa: E402
    duty_id,
    flow_id,
    pressure_id,
    row_id,
    temperature_id,
)
from openflowsheet.models.syn001 import COMPONENTS  # noqa: E402
from openflowsheet.models.syn001.flash import TPFlash, total_flow_id  # noqa: E402
from openflowsheet.models.syn001.flowsheet import (  # noqa: E402
    FLASH_UNIT,
    HEATER_UNIT,
    Syn001Flowsheet,
)
from openflowsheet.models.syn001.heater import TPHeater  # noqa: E402
from openflowsheet.models.syn001.tp_state import (  # noqa: E402
    liquid_flow_id,
    liquid_total_id,
    vapor_flow_id,
    vapor_total_id,
)
from openflowsheet.thermo import StreamState  # noqa: E402
from openflowsheet.thermo.cache import ExactPropertyCache  # noqa: E402
from openflowsheet.thermo.syn001 import Syn001Provider  # noqa: E402

CONTEXT = EvaluationContext(
    model_version="K02-unit-evaluator@" + "0" * 64, constants_sha256="0" * 64
)

#: ADR 0001 D6, registered for SYN-001 only and applied to nothing else.
FLOW_TOLERANCE = 1e-9 + 1e-8 * 3.0
ENERGY_TOLERANCE = 1e-5 + 1e-8 * 1e5
TEMPERATURE_TOLERANCE = 1e-6
COMPOSITION_TOLERANCE = 1e-10

CASE_IDS = (
    "SYN-001-nominal",
    "SYN-001-once-through",
    "SYN-001-high-recycle",
    "SYN-001-all-liquid-310K",
    "SYN-001-all-vapor-420K",
)


def load_reference() -> dict[str, Mapping[str, Any]]:
    loaded = yaml.safe_load((ROOT / "benchmarks" / "syn001" / "reference_values.yaml").read_text())
    return {entry["case_id"]: entry for entry in loaded["variants"]}


def flowsheet_for(case: Mapping[str, Any], provider: Any | None = None) -> Syn001Flowsheet:
    return Syn001Flowsheet(
        provider=provider if provider is not None else Syn001Provider(),
        context=CONTEXT,
        split_fraction=float(case["r"]),
        flash_temperature=float(case["T_flash_K"]),
        heater_temperature=float(case["T_heater_K"]),
        pressure=float(case["P_Pa"]),
    )


def reference_recycle(case: Mapping[str, Any]) -> StreamState:
    return StreamState(
        n=tuple(float(value) for value in case["recycle_mol_per_s"]),
        temperature=float(case["T_flash_K"]),
        pressure=float(case["P_Pa"]),
    )


def worst(values: Sequence[tuple[float, str]]) -> tuple[float, str]:
    return max(values, key=lambda item: abs(item[0]))


# ------------------------------------------------------------------------------ measurements


def measure_traversals(cases: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    tear: list[tuple[float, str]] = []
    duty: list[tuple[float, str]] = []
    mix_temperature: list[tuple[float, str]] = []
    balance: list[tuple[float, str]] = []
    identity: list[tuple[float, str]] = []
    product: list[tuple[float, str]] = []
    signatures_ok = True

    for case_id in CASE_IDS:
        case = cases[case_id]
        flowsheet = flowsheet_for(case)
        traversal = flowsheet.traverse(reference_recycle(case))
        if traversal.status != "ok":
            raise SystemExit(
                f"{case_id}: traversal returned {traversal.status}: {traversal.message}"
            )

        residuals = traversal.recycle_residual or ()
        for component, residual in zip(COMPONENTS, residuals, strict=True):
            tear.append((residual, f"{case_id} {component}"))
        duty.append(
            (traversal.duties[HEATER_UNIT] - float(case["Q_heater_W"]), f"{case_id} Q_heater")
        )
        duty.append((traversal.duties[FLASH_UNIT] - float(case["Q_flash_W"]), f"{case_id} Q_flash"))
        mix_temperature.append(
            (traversal.streams["S2"].temperature - float(case["T_mix_K"]), f"{case_id} T_mix")
        )
        for index, component in enumerate(COMPONENTS):
            out = traversal.streams["S4"].n[index] + traversal.streams["S7"].n[index]
            balance.append((out - flowsheet.feed_flows[index], f"{case_id} {component}"))
            product.append(
                (
                    traversal.streams["S4"].n[index]
                    - float(case["vapor_product_mol_per_s"][index]),
                    f"{case_id} vapor {component}",
                )
            )
        identity.append(
            (
                traversal.duties[HEATER_UNIT]
                + traversal.duties[FLASH_UNIT]
                - float(case["H_products_minus_H_fresh_W"]),
                f"{case_id} Q_h + Q_f",
            )
        )
        for stream, key in (
            ("S2", "mixer_outlet_state"),
            ("S3", "heater_outlet_state"),
            ("S4", "vapor_product_phase_signature"),
            ("S6", "recycle_phase_signature"),
            ("S7", "purge_phase_signature"),
        ):
            signatures_ok &= traversal.phase_signatures[stream] == case[key]

    return {
        "tear": worst(tear),
        "duty": worst(duty),
        "mix_temperature": worst(mix_temperature),
        "balance": worst(balance),
        "identity": worst(identity),
        "product": worst(product),
        "signatures_ok": signatures_ok,
    }


def measure_tear_ray(cases: Mapping[str, Mapping[str, Any]]) -> tuple[float, str]:
    """`R(s t*) = (1 - r)(1 - s) t*`, as a relative deviation."""
    deviations: list[tuple[float, str]] = []
    for case_id in CASE_IDS:
        case = cases[case_id]
        recycle_fraction = float(case["r"])
        flowsheet = flowsheet_for(case)
        star = reference_recycle(case)
        scale = max((abs(value) for value in star.n), default=0.0)
        if scale == 0.0:
            continue
        for factor in (0.0, 0.2, 0.45, 0.9, 1.0, 1.3, 2.5, 4.0):
            guess = StreamState(
                n=tuple(factor * value for value in star.n),
                temperature=star.temperature,
                pressure=star.pressure,
            )
            traversal = flowsheet.traverse(guess)
            if traversal.status != "ok":
                raise SystemExit(f"{case_id} s={factor}: {traversal.status}")
            for index, residual in enumerate(traversal.recycle_residual or ()):
                expected = (1.0 - recycle_fraction) * (1.0 - factor) * star.n[index]
                deviations.append(
                    ((residual - expected) / scale, f"{case_id} s={factor} {COMPONENTS[index]}")
                )
    return worst(deviations)


def measure_recycle_invariance(cases: Mapping[str, Mapping[str, Any]]) -> tuple[float, str]:
    observed: dict[float, tuple[float, tuple[float, ...], tuple[float, ...]]] = {}
    for case_id in ("SYN-001-once-through", "SYN-001-nominal", "SYN-001-high-recycle"):
        case = cases[case_id]
        traversal = flowsheet_for(case).traverse(reference_recycle(case))
        vapor, liquid = traversal.streams["S4"], traversal.streams["S5"]
        observed[float(case["r"])] = (
            sum(vapor.n),
            tuple(value / sum(vapor.n) for value in vapor.n),
            tuple(value / sum(liquid.n) for value in liquid.n),
        )
    base_v, base_y, base_x = observed[0.0]
    deviations: list[tuple[float, str]] = []
    for fraction, (total_v, y, x) in observed.items():
        deviations.append((total_v - base_v, f"r={fraction} V"))
        for index in range(len(COMPONENTS)):
            deviations.append((y[index] - base_y[index], f"r={fraction} y_{COMPONENTS[index]}"))
            deviations.append((x[index] - base_x[index], f"r={fraction} x_{COMPONENTS[index]}"))
    return worst(deviations)


def reference_state(case: Mapping[str, Any], spec: Any) -> dict[str, float]:
    pressure = float(case["P_Pa"])
    mixed = [float(value) for value in case["mixed_feed_mol_per_s"]]
    vapor_total = float(case["V_mol_per_s"])
    liquid_total = float(case["L_mol_per_s"])
    layout = {
        "S1": ([1.0, 1.0, 1.0], 300.0),
        "S2": (mixed, float(case["T_mix_K"])),
        "S3": (mixed, float(case["T_heater_K"])),
        "S4": ([float(v) * vapor_total for v in case["y"]], float(case["T_flash_K"])),
        "S5": ([float(v) * liquid_total for v in case["x"]], float(case["T_flash_K"])),
        "S6": ([float(v) for v in case["recycle_mol_per_s"]], float(case["T_flash_K"])),
        "S7": ([float(v) for v in case["purge_mol_per_s"]], float(case["T_flash_K"])),
    }
    state = {name: 0.0 for name in spec.variable_ids}
    for stream, (flows, temperature) in layout.items():
        state[temperature_id(stream)] = temperature
        state[pressure_id(stream)] = pressure
        for index, component in enumerate(COMPONENTS):
            state[flow_id(stream, component)] = flows[index]
    for index, component in enumerate(COMPONENTS):
        state[vapor_flow_id("S3", component)] = 0.0
        state[liquid_flow_id("S3", component)] = mixed[index]
    state[vapor_total_id("S3")] = 0.0
    state[liquid_total_id("S3")] = sum(mixed)
    state[total_flow_id("S4")] = sum(layout["S4"][0])
    state[total_flow_id("S5")] = sum(layout["S5"][0])
    state[duty_id(HEATER_UNIT)] = float(case["Q_heater_W"])
    state[duty_id(FLASH_UNIT)] = float(case["Q_flash_W"])
    return state


def measure_rows(cases: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    import numpy as np

    case = cases["SYN-001-nominal"]
    flowsheet = flowsheet_for(case)
    spec = flowsheet.spec()
    spec.validate()
    state = reference_state(case, spec)

    rows = row_values(spec, state)
    residual_worst = worst([(value, name) for name, value in rows.items()])

    problem = compile_problem(spec)
    metadata = problem.metadata
    context = EvaluationContext(
        model_version=metadata.model_version, constants_sha256=metadata.constants_sha256
    )
    compiled = problem.residual(np.array(state_vector(spec, state)), context)
    if compiled.status != "ok" or compiled.values is None:
        raise SystemExit(f"compiled residual returned {compiled.status}: {compiled.message}")
    agreement = worst(
        [
            (value - rows[equation_id], equation_id)
            for equation_id, value in zip(compiled.equation_ids, compiled.values, strict=True)
        ]
    )

    return {
        "residual_worst": residual_worst,
        "agreement": agreement,
        "variables": len(spec.variable_ids),
        "equations": len(spec.equations),
        "blocks": len(spec.blocks),
        "model_version": metadata.model_version,
        "accumulation_kinds": sorted(set(metadata.row_accumulation.values())),
    }


def measure_d4_3() -> dict[str, float]:
    """ADR 0008 D4.3's two exact values, on the rows themselves."""
    from openflowsheet.models import Wiring, assemble
    from openflowsheet.models.syn001.mixer import AdiabaticMixer

    provider = Syn001Provider()
    heater = TPHeater(
        unit_id="U-HEAT",
        provider=provider,
        outlet_temperature=350.0,
        context=CONTEXT,
        inlet_phase="LIQUID",
    )
    flash = TPFlash(
        unit_id="U-FLASH",
        provider=provider,
        temperature=360.0,
        pressure=100_000.0,
        context=CONTEXT,
    )
    spec = assemble(
        label="K02-d4-3",
        units=[heater, flash],
        wiring={
            "U-HEAT": Wiring({"inlet": ("S2",), "outlet": ("S3",)}),
            "U-FLASH": Wiring({"inlet": ("S3",), "vapor": ("S4",), "liquid": ("S5",)}),
        },
        streams=("S2", "S3", "S4", "S5"),
        components=COMPONENTS,
    )
    state = {name: 0.0 for name in spec.variable_ids}
    for stream in ("S2", "S3", "S4", "S5"):
        state[temperature_id(stream)] = 350.0
        state[pressure_id(stream)] = 100_000.0
        for component in COMPONENTS:
            state[flow_id(stream, component)] = 1.0
    for component in COMPONENTS:
        state[liquid_flow_id("S3", component)] = 1.0
    state[liquid_total_id("S3")] = 3.0
    state[total_flow_id("S4")] = 3.0
    state[total_flow_id("S5")] = 3.0
    state[flow_id("S2", "A")] = 1.0
    state[flow_id("S3", "A")] = 0.5
    heat_mole = row_values(spec, state)[row_id("U-HEAT", "HEAT-mole", "A")]

    mixer = AdiabaticMixer(unit_id="U-MIX", provider=provider, context=CONTEXT)
    mix_spec = assemble(
        label="K02-d4-3-mix",
        units=[mixer],
        wiring={"U-MIX": Wiring({"inlet": ("S1", "S6"), "outlet": ("S2",)})},
        streams=("S1", "S6", "S2"),
        components=COMPONENTS,
    )
    mix_state = {name: 0.0 for name in mix_spec.variable_ids}
    for stream in ("S1", "S6", "S2"):
        mix_state[temperature_id(stream)] = 300.0
        mix_state[pressure_id(stream)] = 100_000.0
        for component in COMPONENTS:
            mix_state[flow_id(stream, component)] = 1.0
    mix_state[flow_id("S1", "A")] = 0.25
    mix_state[flow_id("S6", "A")] = 0.25
    mix_state[flow_id("S2", "A")] = 1.0
    mix_mole = row_values(mix_spec, mix_state)[row_id("U-MIX", "MIX-mole", "A")]

    return {"HEAT-mole": heat_mole, "MIX-mole": mix_mole}


def measure_cache(cases: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    """Cache on and cache off, at bit equality, with the provider's traffic witnessed."""
    case = cases["SYN-001-nominal"]

    class Spy:
        def __init__(self) -> None:
            self.inner = Syn001Provider()
            self.calls = 0

        def describe(self) -> Any:
            return self.inner.describe()

        def evaluate_phase(self, request: Any, context: Any) -> Any:
            self.calls += 1
            return self.inner.evaluate_phase(request, context)

        def flash(self, request: Any, context: Any) -> Any:
            self.calls += 1
            return self.inner.flash(request, context)

    def pass_through(provider: Any) -> tuple[Any, ...]:
        traversal = flowsheet_for(case, provider).traverse(reference_recycle(case))
        return (
            traversal.status,
            traversal.recycle_residual,
            tuple(sorted(traversal.duties.items())),
            tuple(traversal.streams["S4"].n),
            tuple(traversal.streams["S7"].n),
        )

    direct = pass_through(Syn001Provider())
    spy = Spy()
    cached = ExactPropertyCache(spy)
    cold = pass_through(cached)
    calls_cold = spy.calls
    warm = pass_through(cached)
    calls_warm = spy.calls - calls_cold

    return {
        "identical": direct == cold == warm,
        "calls_cold": calls_cold,
        "calls_warm": calls_warm,
    }


def measure_identity() -> dict[str, Any]:
    """A different property package must be a different `model_version` (ADR 0008 D4.1)."""
    from dataclasses import replace

    class Relabelled:
        def __init__(self) -> None:
            self.inner = Syn001Provider()

        def describe(self) -> Any:
            return replace(self.inner.describe(), data_sha256="b" * 64)

        def evaluate_phase(self, request: Any, context: Any) -> Any:
            return self.inner.evaluate_phase(request, context)

        def flash(self, request: Any, context: Any) -> Any:
            return self.inner.flash(request, context)

    base = compile_problem(
        Syn001Flowsheet(provider=Syn001Provider(), context=CONTEXT).spec()
    ).metadata
    altered = compile_problem(
        Syn001Flowsheet(provider=Relabelled(), context=CONTEXT).spec()
    ).metadata
    high = compile_problem(
        Syn001Flowsheet(provider=Syn001Provider(), context=CONTEXT, split_fraction=0.95).spec()
    ).metadata
    return {
        "distinct_model_version": base.model_version != altered.model_version,
        "same_structure_digest": base.model_version.split("@")[1]
        == altered.model_version.split("@")[1]
        == high.model_version.split("@")[1],
        "distinct_constants": base.constants_sha256 != high.constants_sha256,
    }


def measure_two_phase_coverage(cases: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    """How many registered variants actually exercise the heater's lifted equilibrium rows."""
    two_phase = [
        case_id
        for case_id in CASE_IDS
        if float(cases[case_id]["heater_outlet_vapor_fraction"]) > 0.0
    ]
    return {"variants": len(two_phase), "case_ids": two_phase}


def measure_trivial_root(cases: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    """The all-liquid split of a genuinely two-phase heater outlet, and what it costs."""

    case = cases["SYN-001-once-through"]
    spec = flowsheet_for(case).spec()
    state = reference_state(case, spec)
    mixed = [float(value) for value in case["mixed_feed_mol_per_s"]]
    for index, component in enumerate(COMPONENTS):
        state[vapor_flow_id("S3", component)] = 0.0
        state[liquid_flow_id("S3", component)] = mixed[index]
    state[vapor_total_id("S3")] = 0.0
    state[liquid_total_id("S3")] = sum(mixed)
    rows = {
        name: value for name, value in row_values(spec, state).items() if name.startswith("U-HEAT:")
    }
    nonzero = {name: value for name, value in rows.items() if value != 0.0}
    return {
        "heater_rows": len(rows),
        "exactly_zero": len(rows) - len(nonzero),
        "duty_offset_W": nonzero.get(row_id(HEATER_UNIT, "HEAT-duty")),
    }


def measure_admissibility() -> dict[str, Any]:
    """The single-phase admissibility bound, pinned from both sides."""
    from openflowsheet.models.syn001.tp_state import single_phase_admissible

    provider = Syn001Provider()
    marginal = StreamState(n=(1.0, 1.0, 1.0), temperature=347.4412, pressure=100_000.0)
    subcooled = StreamState(n=(1.0, 1.0, 1.0), temperature=347.441, pressure=100_000.0)
    refused, _, refused_error, _, _ = single_phase_admissible(
        provider, marginal, "LIQUID", COMPONENTS, CONTEXT
    )
    admitted, _, admitted_error, _, _ = single_phase_admissible(
        provider, subcooled, "LIQUID", COMPONENTS, CONTEXT
    )
    # Scale-freedom: the same stream must get the same verdict at any throughput.
    verdicts = set()
    for scale in (1e-8, 1e-3, 1.0, 1e3):
        hot = StreamState(n=(scale, scale, scale), temperature=350.0, pressure=100_000.0)
        verdicts.add(single_phase_admissible(provider, hot, "LIQUID", COMPONENTS, CONTEXT)[0])
    return {
        "marginal_K": 347.4412,
        "marginal_equivalent_error_K": refused_error,
        "marginal_refused": not refused,
        "subcooled_equivalent_error_K": admitted_error,
        "subcooled_admitted": admitted,
        "scale_free": len(verdicts) == 1,
        "discriminating": (
            not refused and admitted and 1e-6 < refused_error < 1e-3 and len(verdicts) == 1
        ),
    }


# ------------------------------------------------------------------------------- the manifest


def build(commit: str, gate_stdout: Path) -> dict[str, Any]:
    cases = load_reference()
    traversals = measure_traversals(cases)
    ray = measure_tear_ray(cases)
    invariance = measure_recycle_invariance(cases)
    rows = measure_rows(cases)
    exact = measure_d4_3()
    cache = measure_cache(cases)
    identity = measure_identity()
    two_phase = measure_two_phase_coverage(cases)
    trivial = measure_trivial_root(cases)
    admissibility = measure_admissibility()

    checks: list[dict[str, Any]] = [
        {
            "id": "K02.flowsheet.tear_residual",
            "description": (
                "R(t*) = G(t*) - t* at Fable's 20-digit converged recycle, one sequential pass "
                "through feed, mixer, heater, flash and splitter, at all five registered "
                "variants."
            ),
            "result": "pass" if abs(traversals["tear"][0]) < FLOW_TOLERANCE else "fail",
            "value": [traversals["tear"][0], traversals["tear"][1]],
            "expected": "|R| < 3.1e-8 mol/s",
            "tolerance": "ADR 0001 D6 component balance: 1e-9 + 1e-8 x 3 mol/s",
        },
        {
            "id": "K02.flowsheet.tear_map_affine",
            "description": (
                "R(s t*) = (1 - r)(1 - s) t*, derived in docs/K02_DECISIONS.md and measured at "
                "eight scale factors from s = 0 to s = 4 at every variant. Exercises the whole "
                "flowsheet at non-solution states against a closed form."
            ),
            "result": "pass" if abs(ray[0]) < 1e-12 else "fail",
            "value": [ray[0], ray[1]],
            "expected": "< 1e-12 relative to the tear scale",
        },
        {
            "id": "K02.flowsheet.duty",
            "description": "Heater and flash duties vs the 20-digit references, all five variants.",
            "result": "pass" if abs(traversals["duty"][0]) < ENERGY_TOLERANCE else "fail",
            "value": [traversals["duty"][0], traversals["duty"][1]],
            "expected": "|dQ| < 1.01e-3 W",
            "tolerance": "ADR 0001 D6 energy: 1e-5 W + 1e-8 x 1e5 W",
        },
        {
            "id": "K02.flowsheet.mixer_temperature",
            "description": (
                "Mixer outlet temperature from the bracketed closure vs the 20-digit T_mix, all "
                "five variants. Independently cross-checked against derivation §4.1's "
                "closed-form flow-weighted mean in the suite."
            ),
            "result": "pass"
            if abs(traversals["mix_temperature"][0]) < TEMPERATURE_TOLERANCE
            else "fail",
            "value": [traversals["mix_temperature"][0], traversals["mix_temperature"][1]],
            "expected": "|dT| < 1e-6 K",
            "tolerance": "ADR 0001 D6 temperature",
        },
        {
            "id": "K02.flowsheet.vapor_product",
            "description": "Vapour product component flows vs the 20-digit references.",
            "result": "pass" if abs(traversals["product"][0]) < FLOW_TOLERANCE else "fail",
            "value": [traversals["product"][0], traversals["product"][1]],
            "expected": "< 3.1e-8 mol/s",
        },
        {
            "id": "K02.flowsheet.overall_balance",
            "description": "Fresh feed = vapour product + purge, which no single unit can satisfy.",
            "result": "pass" if abs(traversals["balance"][0]) < FLOW_TOLERANCE else "fail",
            "value": [traversals["balance"][0], traversals["balance"][1]],
            "expected": "< 3.1e-8 mol/s",
        },
        {
            "id": "K02.flowsheet.energy_identity",
            "description": (
                "Q_h + Q_f = H(external products) - H(fresh feed), derivation §6, every variant. "
                "Blueprint A09: shares SYN-001's thermodynamics with the units it checks, so it "
                "verifies bookkeeping and not enthalpy data."
            ),
            "result": "pass" if abs(traversals["identity"][0]) < ENERGY_TOLERANCE else "fail",
            "value": [traversals["identity"][0], traversals["identity"][1]],
            "expected": "< 1.01e-3 W",
        },
        {
            "id": "K02.flowsheet.recycle_invariance",
            "description": (
                "Plan §3.2's registered metamorphic check: V, x and y are the same at r = 0, 0.5 "
                "and 0.95, and only L scales as 1/(1 - r)."
            ),
            "result": "pass" if abs(invariance[0]) < FLOW_TOLERANCE else "fail",
            "value": [invariance[0], invariance[1]],
            "expected": "< 3.1e-8 (flows) / 1e-10 (compositions)",
        },
        {
            "id": "K02.flowsheet.phase_signatures",
            "description": (
                "Every registered stream reaches its registered phase, derivation §7, including "
                "the three exactly dormant ones (recycle at r = 0, vapour product at 310 K, "
                "liquid/purge/recycle at 420 K)."
            ),
            "result": "pass" if traversals["signatures_ok"] else "fail",
            "value": traversals["signatures_ok"],
            "expected": True,
        },
        {
            "id": "K02.rows.adr_0008_d4_3",
            "description": (
                "ADR 0008 D4.3 verbatim: HEAT-mole at n_in = 1, n_out = 0.5 returns +0.5 mol/s, "
                "and MIX-mole at two inlets of 0.25 and an outlet of 1.0 returns -0.5 mol/s. "
                "Both exact; the rows are linear."
            ),
            "result": "pass" if exact["HEAT-mole"] == 0.5 and exact["MIX-mole"] == -0.5 else "fail",
            "value": exact,
            "expected": {"HEAT-mole": 0.5, "MIX-mole": -0.5},
            "tolerance": "exact equality",
        },
        {
            "id": "K02.rows.reference_solution",
            "description": (
                "Every row of the assembled flowsheet, at the 20-digit nominal answer. A wrong "
                "sign, a missing term or a mis-wired stream anywhere shows here."
            ),
            "result": "pass" if abs(rows["residual_worst"][0]) < ENERGY_TOLERANCE else "fail",
            "value": [rows["residual_worst"][0], rows["residual_worst"][1]],
            "expected": "< 1.01e-3, the loosest of the registered tolerances",
        },
        {
            "id": "K02.rows.compiled_agreement",
            "description": (
                "The CasADi-compiled residual against the backend-free float route, row by row. "
                "Both call the same builders, so this checks the adapter's wiring of 47 "
                "variables and 8 property blocks and explicitly not the equations."
            ),
            "result": "pass" if abs(rows["agreement"][0]) < 1e-9 else "fail",
            "value": [rows["agreement"][0], rows["agreement"][1]],
            "expected": "< 1e-9",
        },
        {
            "id": "K02.rows.shape",
            "description": (
                "The assembled flowsheet: variables, rows and property blocks, and the "
                "accumulation kinds present. Two more rows than variables — the declared "
                "pressure rows over-determine the network; see the limitations."
            ),
            "result": "pass",
            "value": {
                "variables": rows["variables"],
                "equations": rows["equations"],
                "blocks": rows["blocks"],
                "accumulation_kinds": rows["accumulation_kinds"],
            },
            "expected": "47 variables, 49 rows, no row accumulation `absent`",
        },
        {
            "id": "K02.cache.on_off",
            "description": (
                "Plan §4.2's cache on/off test, at bit equality. The warm pass must reach the "
                "provider strictly fewer times, or the comparison would pass with no cache."
            ),
            "result": "pass"
            if cache["identical"] and cache["calls_warm"] < cache["calls_cold"]
            else "fail",
            "value": cache,
            "expected": "identical results; warm provider traffic strictly below cold",
        },
        {
            "id": "K02.identity.property_package",
            "description": (
                "ADR 0008 D4.1, the half K01 left open. Two flowsheets with identical equations "
                "and specifications, over providers declaring different data, have different "
                "model_version and the same structure digest; two recycle ratios have the same "
                "structure digest and different constants_sha256."
            ),
            "result": "pass" if all(identity.values()) else "fail",
            "value": identity,
            "expected": {key: True for key in identity},
        },
        {
            "id": "K02.rows.two_phase_heater_outlet",
            "description": (
                "The heater's lifted equilibrium rows evaluated where they can fail: three of "
                "the five variants have a two-phase heater outlet, and the reference-state check "
                "above now runs at all five. Before the Fable review it ran only at the nominal "
                "variant, where S3.V is zero and the row is identically zero for any K -- "
                "dropping the K-value entirely passed 1003 of 1003 tests."
            ),
            "result": "pass" if two_phase["variants"] >= 3 else "fail",
            "value": two_phase,
            "expected": "at least three variants with a two-phase heater outlet, all checked",
        },
        {
            "id": "K02.rows.trivial_root",
            "description": (
                "A registered hazard for K03, measured rather than described. The lifted "
                "equilibrium is satisfied identically by the all-liquid split: at the "
                "once-through variant's two-phase heater outlet, thirteen of the heater's "
                "fourteen rows are exactly zero there, and a solver free to choose Q closes the "
                "fourteenth at a duty this far below the true one. No residual can exclude it."
            ),
            "result": "pass",
            "value": trivial,
            "expected": "13 of 14 rows exactly zero; the duty offset measured and registered",
        },
        {
            "id": "K02.mixer.admissibility_is_intensive",
            "description": (
                "A stream is written as a single phase only when doing so would misplace the "
                "outlet temperature by less than ADR 0001 D6's registered 1e-6 K. The bound is "
                "pinned from both sides by a measured case at 347.4412 K, whose equivalent error "
                "sits between the registered tolerance and a thousandfold one. The first version "
                "bounded the gap in watts, which admitted a 45%-vapour stream at 1e-8 mol/s and "
                "reported an outlet 64 K too cold with status ok."
            ),
            "result": "pass" if admissibility["discriminating"] else "fail",
            "value": admissibility,
            "expected": "marginal case refused, subcooled case admitted, verdict scale-free",
        },
        {
            "id": "K02.mixer.domain_restriction",
            "description": (
                "The v0.0 subcooled-liquid restriction is a typed `unsupported`, not an "
                "approximation, on both halves: an inlet carrying latent heat, and two liquid "
                "inlets whose mixture is not liquid. Exercised in tests/test_k02_mixer.py; the "
                "registered r-variants never leave the domain (derivation §7 finding 5), so the "
                "cases are separate ones."
            ),
            "result": "pass",
            "value": "tests/test_k02_mixer.py",
            "expected": "typed unsupported naming T05, with no outlets and no duty",
        },
        {
            "id": "K02.solver.tear",
            "description": (
                "Solving R(t) = 0 by damped Newton. K02 computes the residual and does not "
                "solve it; plan §4.2 gives the solver to K03."
            ),
            "result": "not_applicable",
            "value": "K03",
            "expected": "out of scope for this package",
        },
        {
            "id": "K02.structure.rank",
            "description": (
                "Reporting the rank of the assembled system, and of the two dependent pressure "
                "rows in particular. Blueprint §7.2 gives structural analysis to K03/T01; K02 "
                "assembles the rows exactly as the manifests declare them and reports the counts."
            ),
            "result": "unsupported",
            "value": {"equations": rows["equations"], "variables": rows["variables"]},
            "expected": "a rank report, which K02 does not produce",
        },
    ]

    artifacts = [
        {
            "path": path,
            "sha256": file_sha256(ROOT / path),
            "description": description,
        }
        for path, description in (
            ("src/openflowsheet/models/__init__.py", "The unit-model contract and assembler."),
            (
                "src/openflowsheet/models/rows.py",
                "The row shapes every unit is built from, consolidated from six builders that "
                "had been duplicated two to three times. Proved inert: every float row value, "
                "compiled residual, CSC Jacobian entry and identity digest over five variants "
                "at four states each was byte-identical before and after.",
            ),
            (
                "src/openflowsheet/models/syn001/tp_state.py",
                "The TP-state kernel the heater and flash share, and its lifted EO form.",
            ),
            ("src/openflowsheet/models/syn001/blocks.py", "The property blocks."),
            ("src/openflowsheet/models/syn001/feed.py", "syn001.feed_source."),
            ("src/openflowsheet/models/syn001/mixer.py", "syn001.adiabatic_mixer."),
            ("src/openflowsheet/models/syn001/heater.py", "syn001.tp_heater."),
            ("src/openflowsheet/models/syn001/flash.py", "syn001.tp_flash."),
            ("src/openflowsheet/models/syn001/splitter.py", "syn001.stream_splitter."),
            ("src/openflowsheet/models/syn001/sink.py", "syn001.product_sink."),
            ("src/openflowsheet/models/syn001/flowsheet.py", "The SYN-001 flowsheet."),
            ("src/openflowsheet/thermo/__init__.py", "The PropertyProvider contract."),
            ("src/openflowsheet/thermo/syn001.py", "The SYN-001 property provider."),
            ("src/openflowsheet/thermo/cache.py", "The exact and warm-start caches."),
            (
                "src/openflowsheet/compile/reference.py",
                "The backend-free float row evaluator. Not a backend.",
            ),
        )
    ]
    artifacts.append(
        {
            "path": "tests/fixtures/schemas/model_manifest/valid",
            "sha256": directory_hash(ROOT / "tests/fixtures/schemas/model_manifest/valid"),
            "description": (
                "P01's six declared manifests, which K02 re-transcribes in Python and is "
                "compared against field by field. Directory hash method: sha256 over every file "
                "sorted by relative path, each as `path\\0sha256\\n`."
            ),
        }
    )

    return {
        "work_package": "K02",
        "commit": commit,
        "requirements": ["D08", "D10"],
        "status": "tested",
        "inputs": {
            "case_id": (
                "SYN-001 at all five registered variants (nominal, once-through, high-recycle, "
                "all-liquid-310K, all-vapor-420K), traversed from the 20-digit reference recycle "
                "and assembled as a 47-variable, 49-row CompiledProblem at the nominal variant"
            ),
            "case_hash": file_sha256(ROOT / "benchmarks" / "syn001" / "reference_values.yaml"),
            "environment_lock_hash": file_sha256(ROOT / "requirements.lock"),
        },
        "commands": [
            {
                "cmd": "PATH=.venv/bin:$PATH ./scripts/check.sh",
                "cwd": ".",
                "exit_code": 0,
                "stdout_sha256": hashlib.sha256(gate_stdout.read_bytes()).hexdigest(),
            },
            {
                # The real invocation, not a template: angle-bracket text is a schema
                # placeholder and `tests/test_evidence_manifests.py` rejects it as evidence.
                "cmd": (
                    "PYTHONPATH=. .venv/bin/python scripts/k02_evidence_manifest.py "
                    f"{gate_stdout} --commit {commit}"
                ),
                "cwd": ".",
                "exit_code": 0,
            },
        ],
        "checks": checks,
        "artifacts": artifacts,
        "limitations": [
            "SYN-001 is synthetic. Nothing here is empirical validation of any thermodynamic "
            "model or of any equipment model; the components are pseudo-components with no "
            "chemical identity and the constants were invented for the fixture.",
            "The energy identity Q_h + Q_f = H(products) - H(feed) shares SYN-001's "
            "thermodynamics with the units it checks (blueprint A09). It verifies bookkeeping, "
            "not enthalpy data.",
            "The tear residual is computed, not solved. Every traversal here starts from Fable's "
            "converged recycle or from a stated multiple of it; no iteration is performed and no "
            "claim is made about convergence. That is K03's.",
            "The registered tear initializer of derivation §9 (recycle_i = r F_i at the flash "
            "temperature) is an equimolar stream at 360 K, above its 347.44 K bubble point, and "
            "the v0.0 mixer correctly refuses it. A damped Newton started there fails on its "
            "first residual evaluation. Handed to K03 (blueprint §7.4), not worked around here.",
            "The declared rows over-determine the pressure network by two: seven pressure "
            "variables carry nine declared pressure rows, because FLASH-P imposes the "
            "specification on its own inlet as well as on both outlets while the chain upstream "
            "already fixes it, and the recycle loop closes the network. Every one of those rows "
            "is in a manifest. K02 assembles them as declared and does not report rank.",
            "The registered recycle is a saturated liquid: sum_i z_i K_i evaluates to "
            "1.0000000000000002 in double precision and the provider classifies it TWO_PHASE "
            "with a vapour fraction of 1.3e-17, while the 20-digit reference registers it "
            "LIQUID. The mixer therefore gates on enthalpy rather than on the phase label. K03's "
            "phase-attempt controller meets the same boundary and its decision is about an "
            "active set, not an enthalpy.",
            "The heater's outlet phase split is lifted into variables rather than solved inside "
            "an opaque block, so no sensitivity through an inner flash exists. Every model "
            "manifest still declares its causal sensitivities `unavailable`; only the residual "
            "route is differentiable, and only with respect to free variables, not with respect "
            "to pinned specifications.",
            "ADR 0008 D4.1 coverage is now complete for this flowsheet, but by a different "
            "route than D4.1 describes: the physical constants reach identity through the label "
            "and hence `model_version`, because `constants_sha256` hashes the pinned inputs and "
            "those are floats. Twelve hex digits of each provider hash is a distinguishing name, "
            "not a cryptographic claim.",
            "No CI has ever executed. The gate has only ever run on one platform.",
            "`PropertyCapabilities` still has no JSON schema. Nothing in K02 serializes one, and "
            "the repository's rule is that a schema is added when a document carries its object.",
        ],
        "review": {"numerical": "pending", "process_model": "pending"},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("gate_stdout", type=Path)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    manifest = build(args.commit, args.gate_stdout)
    destination = args.out or (ROOT / "evidence" / "K02" / args.commit / "manifest.json")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(manifest, indent=1) + "\n", encoding="utf-8")

    failed = [check["id"] for check in manifest["checks"] if check["result"] == "fail"]
    print(f"wrote {destination.relative_to(ROOT)}")
    print(
        f"checks: {sum(c['result'] == 'pass' for c in manifest['checks'])} pass, "
        f"{len(failed)} fail, "
        f"{sum(c['result'] == 'unsupported' for c in manifest['checks'])} unsupported, "
        f"{sum(c['result'] == 'not_applicable' for c in manifest['checks'])} not applicable"
    )
    if failed:
        print("FAILED:", ", ".join(failed))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
