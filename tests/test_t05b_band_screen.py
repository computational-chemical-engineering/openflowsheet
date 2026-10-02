"""T05b B32: the screen's regime of a flagged PH-type trial by the band's end enthalpies (spec §6.2
as amended 2026-09-25, ruling Q-S10, R-053; review S1).

At a flagged trial the screen no longer asks the full PH closure (a band route, ≈ 3 100 provider
calls, on a near-pure feed): (s1) a target outside `[Ḣ_TP(T_min), Ḣ_TP(T_max)]` — where
`ph_state` refuses `ph_outside_domain` — reports the TP flash's regime; (s2) else `LIQUID` /
`TWO_PHASE` / `VAPOR` by comparing `H_split` with `H_0 = Ḣ^L(n, T_b)` and `H_1 = Ḣ^V(n, T_d)`
with a `τ_E` margin; (s3) inside a `τ_E` zone, or on any failed evaluation, the full closure,
whose answer the opening at that state reuses.

- **(a)** At KS-1…KS-3 (spec §12.7) the screened regime equals the contract kernel's (the PH
  closure's, or its TP fallback's at the trial). On each of §12.1's eight compositions at `P_r`,
  `_band_regime` equals `ph_state`'s regime — or is (s1) exactly where `ph_state` refuses
  `out_of_domain` — at the five grid targets, `H_0 ± 2τ_E`, `H_1 ± 2τ_E` and the domain ends
  `∓ 1 W`, and is (s3) at exactly `H_0 ± τ_E/2` and `H_1 ± τ_E/2`. `H_0`, `H_1` are built here
  from `ref`'s band ends (`T_bubble_K`, `T_dew_K`) and the provider's enthalpies.
- **(b)** NP-1…NP-G from the liquid-form start of B33 (b), through `execute_plan` with the
  region's property meter: none ends `BUDGET_EXHAUSTED` (before W9.6 NP-1 and NP-2 did; the
  counts are in `docs/t05b-measurements.md` — property counts are not R0, R-015, so they are
  recorded there, not pinned).
- **(c)** R0 unchanged: the `t05b` key (`4f29500e…`, W9.4's), B07 and SC-3's records are the
  gate's own tests, unchanged.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping
from typing import Any

import pytest
from t05_support import CONTEXT, PROVIDER
from t05_w12_support import bind
from t05b_support import POLICY_V2, REF, near_pure, number, sc1

from openflowsheet.models.syn001 import ENERGY_TOLERANCE
from openflowsheet.models.syn001.ph_kernel import ph_state
from openflowsheet.models.syn001.tp_state import enthalpy_flow, tp_state
from openflowsheet.orchestrator import executor, revision
from openflowsheet.orchestrator import region as region_module
from openflowsheet.orchestrator.execution import ExecutionPlan
from openflowsheet.orchestrator.region import (
    TP_REGIME,
    ClosureMemo,
    _band_regime,
    _build_screen,
    _contract_kernel,
    _kernel,
    _split_enthalpy,
)
from openflowsheet.orchestrator.revision import TraversalStart, plan_revision
from openflowsheet.orchestrator.splits import closure_types, lifted_splits
from openflowsheet.thermo import StreamState

COMPONENTS = ("A", "B", "C")

# ---------------------------------------------------------------------------- (a) KS-1…KS-3


def _kernel_state(entry: Mapping[str, Any]) -> dict[str, float]:
    state = {"S2.T": number(entry["T_K"]), "S2.P": number(entry["P_Pa"])}
    for index, component in enumerate(COMPONENTS):
        state[f"S2.n.{component}"] = number(entry["feed_mol_per_s"][index])
        state[f"S2.vap.{component}"] = number(entry["vapor_mol_per_s"][index])
        state[f"S2.liq.{component}"] = number(entry["liquid_mol_per_s"][index])
    state["S2.V"] = sum(state[f"S2.vap.{c}"] for c in COMPONENTS)
    state["S2.L"] = sum(state[f"S2.liq.{c}"] for c in COMPONENTS)
    return state


@pytest.mark.parametrize("state_id", ["KS-1", "KS-2", "KS-3"])
def test_b32a_the_contract_kernel_states(state_id: str) -> None:
    """The screen's (s1)–(s2) at a valve outlet frozen `LIQUID` (SC-1's `U-VLV`) against the
    contract's kernel at the same state: KS-1 (saturation route) and KS-2 (band route) by (s2),
    `TWO_PHASE`; KS-3 below the domain by (s1), the TP flash's `LIQUID` with `fallback(…, tp)`."""
    entry = REF["contract_kernel_states"][state_id]
    flowsheet = bind(sc1()).flowsheet
    (split,) = lifted_splits(
        [(u.unit_id, u.model_id, flowsheet.wiring[u.unit_id]) for u in flowsheet.units()],
        flowsheet.components,
    )
    assert closure_types(flowsheet.units()) == {"U-VLV": "PH"}
    state = _kernel_state(entry)
    target = _split_enthalpy(flowsheet.provider, flowsheet.context, split, state)
    assert target is not None
    feed = tuple(state[name] for name in split.feed)
    screened = _band_regime(flowsheet.provider, flowsheet.context, feed, state["S2.P"], target)
    kernel = _contract_kernel(
        flowsheet.provider, flowsheet.context, split, state, frozenset({"U-VLV"})
    )
    assert kernel.regime == entry["expected_regime"]
    if state_id == "KS-3":
        assert screened == TP_REGIME and kernel.fallback == "tp"
        regime, _ = _kernel(flowsheet.provider, flowsheet.context, split, state)
        assert regime == kernel.regime
    else:
        assert screened == kernel.regime


# ------------------------------------------------------------------ (a) the §12.1 grid's points


def _compositions() -> dict[str, tuple[tuple[float, ...], float, float, float]]:
    """`{name: (n, P, T_b, T_d)}` of §12.1's eight compositions, from `ref.kernel_grid`."""
    found: dict[str, tuple[tuple[float, ...], float, float, float]] = {}
    for state_id, state in REF["kernel_grid"].items():
        name = state_id.rsplit("-", 1)[0]
        inputs = state["inputs"]
        found[name] = (
            tuple(number(value) for value in inputs["n_mol_per_s"]),
            number(inputs["P_Pa"]),
            number(state["band"]["T_bubble_K"]),
            number(state["band"]["T_dew_K"]),
        )
    return found


COMPOSITIONS = _compositions()


def _targets(name: str) -> Iterator[tuple[str, float, bool]]:
    """`(label, H_split, is (s3))` at one composition: B32 (a)'s fifteen points."""
    n, pressure, t_b, t_d = COMPOSITIONS[name]
    for state_id, state in REF["kernel_grid"].items():
        if state_id.rsplit("-", 1)[0] == name:
            yield f"target {state_id}", number(state["inputs"]["H_target_W"]), False
    ends = {}
    for label, temperature, phase in (("H_0", t_b, "LIQUID"), ("H_1", t_d, "VAPOR")):
        stream = StreamState(n=n, temperature=temperature, pressure=pressure)
        status, value, _ = enthalpy_flow(PROVIDER, stream, phase, ("A", "B", "C"), CONTEXT)
        assert status == "ok"
        ends[label] = value
    for label, end in ends.items():
        for sign in (-1.0, 1.0):
            yield f"{label} {sign:+g} tau/2", end + sign * ENERGY_TOLERANCE / 2, True
            yield f"{label} {sign:+g} 2 tau", end + sign * 2 * ENERGY_TOLERANCE, False
    t_min, t_max = PROVIDER.describe().domain["T"]
    for label, temperature, offset in (("T_min - 1 W", t_min, -1.0), ("T_max + 1 W", t_max, 1.0)):
        at = tp_state(
            PROVIDER, StreamState(n=n, temperature=temperature, pressure=pressure), CONTEXT
        )
        assert at.status == "ok" and at.enthalpy_flow is not None
        yield label, at.enthalpy_flow + offset, False


def _regime(signature: str | None) -> str:
    return signature if signature in ("LIQUID", "VAPOR") else "TWO_PHASE"


@pytest.mark.parametrize("name", sorted(COMPOSITIONS))
def test_b32a_the_grid_regimes_equal_ph_states(name: str) -> None:
    n, pressure, _, _ = COMPOSITIONS[name]
    points = list(_targets(name))
    assert len(points) == 15
    for label, target, zone in points:
        screened = _band_regime(PROVIDER, CONTEXT, n, pressure, target)
        if zone:
            assert screened is None, (name, label, screened)
            continue
        assert screened is not None, (name, label)
        closure = ph_state(PROVIDER, n, pressure, target, CONTEXT)
        if screened == TP_REGIME:
            assert closure.status == "out_of_domain", (name, label, closure.message)
            assert closure.code.startswith("ph_outside_domain("), (name, label, closure.code)
            continue
        assert closure.status == "ok", (name, label, closure.message)
        assert closure.split is not None
        assert screened == _regime(closure.split.phase_signature), (name, label)


def test_b32a_the_domain_ends_are_s1_and_the_band_ends_are_s2() -> None:
    """Every composition's domain-end points are (s1), and its `H_0 ± 2τ_E`, `H_1 ± 2τ_E` points
    name `LIQUID`, `TWO_PHASE`, `TWO_PHASE`, `VAPOR` — the regions' order by enthalpy."""
    for name in COMPOSITIONS:
        n, pressure, _, _ = COMPOSITIONS[name]
        got = {
            label: _band_regime(PROVIDER, CONTEXT, n, pressure, target)
            for label, target, _ in _targets(name)
        }
        assert got["T_min - 1 W"] == got["T_max + 1 W"] == TP_REGIME, name
        assert got["H_0 -1 2 tau"] == "LIQUID", name
        assert got["H_0 +1 2 tau"] == got["H_1 -1 2 tau"] == "TWO_PHASE", name
        assert got["H_1 +1 2 tau"] == "VAPOR", name


# ------------------------------------------------------ (b) NP through the executor's meter


def _liquid_form(real: Callable[..., Any]) -> Callable[..., Any]:
    def start(flowsheet: Any, variable_ids: Any) -> TraversalStart:
        traversed = real(flowsheet, variable_ids)
        assert isinstance(traversed, TraversalStart), traversed
        values = dict(traversed.values)
        for component in COMPONENTS:
            values[f"S3.n.{component}"] = values[f"S2.n.{component}"] + values[f"S3.n.{component}"]
            values[f"S2.n.{component}"] = 0.0
        values["S2.N"] = 0.0
        values["S3.N"] = sum(values[f"S3.n.{component}"] for component in COMPONENTS)
        values["S2.T"] = values["S3.T"] = 300.0
        return TraversalStart(values, traversed.band_routes)

    return start


@pytest.mark.parametrize("case", ["NP-1", "NP-2", "NP-3", "NP-G"])
def test_b32b_near_pure_restarts_fit_the_region_meter(
    case: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(revision, "traversal_start", _liquid_form(revision.traversal_start))
    binding = bind(near_pure(case))
    plan, _ = plan_revision(binding, POLICY_V2)
    assert isinstance(plan, ExecutionPlan), plan
    run = executor.execute_plan(
        plan=plan, flowsheet=binding.flowsheet, spec=binding.spec, policy=POLICY_V2
    )
    assert run.outcome == "CONVERGED", run.message
    assert run.counters.property_calls < POLICY_V2.max_property_calls
    (step,) = run.steps
    assert [a.signature for a in step.detail.attempts] == [
        (("U-PHF", "LIQUID"),),
        (("U-PHF", "TWO_PHASE"),),
    ]


# ------------------------------------------------------------------ (s3): carried to the opening


def test_s3_the_closure_the_screen_asks_is_carried_to_the_opening(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With (s1)–(s2) forced to give no answer, the screen asks the full closure at KS-2 once and
    keeps it (with the opening's temperature columns); the contract's kernel at the same state
    reuses it without asking `ph_state` again (spec §6.2 as amended, "carrying")."""
    entry = REF["contract_kernel_states"]["KS-2"]
    flowsheet = bind(sc1()).flowsheet
    (split,) = lifted_splits(
        [(u.unit_id, u.model_id, flowsheet.wiring[u.unit_id]) for u in flowsheet.units()],
        flowsheet.components,
    )
    state = _kernel_state(entry)
    asked: list[float] = []
    real = region_module.ph_state

    def counted(*args: Any, **kwargs: Any) -> Any:
        asked.append(args[3])
        return real(*args, **kwargs)

    monkeypatch.setattr(region_module, "_band_regime", lambda *args: None)
    monkeypatch.setattr(region_module, "ph_state", counted)
    memo: ClosureMemo = {}
    screen = _build_screen(
        [split],
        {"U-VLV": "LIQUID"},
        flowsheet.provider,
        flowsheet.context,
        POLICY_V2.admissibility_epsilon,
        frozenset({"U-VLV"}),
        v2=True,
        temperatures={"U-VLV": (split.temperature,)},
        memo=memo,
    )
    assert screen(dict(state)) == (("U-VLV", "TWO_PHASE"),)
    assert len(asked) == 1 and len(memo) == 1
    kernel = _contract_kernel(
        flowsheet.provider,
        flowsheet.context,
        split,
        state,
        frozenset({"U-VLV"}),
        v2=True,
        regime="LIQUID",
        temperatures=(split.temperature,),
        memo=memo,
    )
    assert len(asked) == 1
    assert kernel == next(iter(memo.values()))
    assert (kernel.regime, kernel.fallback) == ("TWO_PHASE", "ph-band")
