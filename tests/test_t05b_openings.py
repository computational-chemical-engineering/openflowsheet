"""T05b B31: an opening agrees with exact dormancy (spec §7.4, §7.8 (ii) as amended 2026-09-25,
ruling Q-S9, R-065; review M1 and N1).

At every v2 opening — attempt 0 after the start rules, every restart after the candidate's regimes,
pins and kernel answers — one fixed point over the lifted splits' `ZERO_FLOW` membership and the
dormancy items, in declaration order, until a pass changes nothing (`region._settle`). Before it,
the four restart cases below and CH-DORMANT's order variant raised an untyped `RuntimeError`
(`defect: U-PHF2 opens attempt … in ZERO_FLOW with its feed flowing`; *measured* at `906ef0a`).

Cases (spec B31), under `T05b-v2`; feed `(1,1,1)`, 300 K, `P_r`, liquid; `U-PHF` is C1's instance;
`U-PHF2`, `U-PHF3` are C1's `U-PHF` renamed, `Q = 0`, `ΔP = 0`, vapour inlet (SC-4's `U-PHF2`):

- **CH-UP**: `U-PHF` (`Q = 30 kW`) → `S2` vap → `U-PHF2` → `S4` vap, `S5` liq; `S3` liq → sink;
  from `initial_state` of the same revision with `Q = 0`.
- **CH-DOWN**: CH-UP's flowsheet with `Q = 0`, from `initial_state` of CH-UP.
- **CH-DZ12**: DZ-12's flowsheet plus `U-PHF2` on the exchanger's hot outlet `S4` (products `S7`
  vap, `S8` liq), from `initial_state` of it with `Q = 0`.
- **CH-3**: CH-UP plus `U-PHF3` on `S4` (products `S6` vap, `S7` liq), declared `U-PHF3`,
  `U-PHF2`, `U-PHF`, from CH-UP's start rule.
- **CH-DORMANT**: CH-UP's flowsheet with feed `(0,0,0)` and `Q = 0`, from `initial_state` of CH-UP
  with the feed's flows set to `0.0`.
- Order variants (`…/PHF2-first`): CH-UP, CH-DOWN, CH-DORMANT with `U-PHF2` declared first.
- B31 (i)'s companions (`…-DP`): CH-UP, CH-DZ12, CH-3 with every downstream flash at
  `pressure_drop = ref.downstream_flash_cases.downstream_pressure_drop_Pa` (10 kPa).

Expectations are closed forms: `U-PHF`'s streams are DZ-12's registered root
(`ref.dormant_non_lifted_cases.DZ-12.root`, the same feed and duty); a downstream flash at `Q = 0`
fed a saturated vapour passes it through unchanged (vapour product = feed at that `T` and at the
feed's `P` less the flash's `ΔP`, liquid product 0). Attempt structures, records and final regimes
are *regression* values (measured 2026-09-25, W9.3), except (i)'s final `VAPOR`, which is
determined.

**B31 (b)'s verdict (amended 2026-09-25, Q-S9 addendum).** At `ΔP = 0` the closed-form root puts
each downstream flash exactly on its dew point (`L = 0`, `Σ y/K = 1`), where the declared lifted
form K04 screens is singular — its equilibrium rows admit the condensation direction
`δl_i = y_i/K_i δL`, balanced by `δT` in the energy row (`ref.downstream_flash_cases`: CH-UP rank
30 of 31, CH-3 42 of 44). So the certificate is `UNVERIFIED`, `RANK_DEFICIENT`, rank loss one per
downstream flash, never `VERIFIED`. Off the dew point (i) the same restarts certify.
"""

from __future__ import annotations

import dataclasses
from decimal import Decimal
from functools import cache
from typing import Any

import pytest
from t05_w12_support import bind, connection_pin, duty_pin, planned_step
from t05b_support import (
    P_R,
    POLICY_V2,
    REF,
    Document,
    Link,
    Product,
    Source,
    instance,
    revision,
    solve_from_v2,
)

from openflowsheet.orchestrator import region as region_module
from openflowsheet.orchestrator.region import (
    DormancyForm,
    LiftedSplit,
    RegionResult,
    _contract_kernel,
    _items,
    _opening_order,
    _rederive,
    _settle,
    _trigger_dormant,
)
from openflowsheet.orchestrator.revision import initial_state, instances_of
from openflowsheet.orchestrator.splits import closure_types, dormancy_forms, lifted_splits
from openflowsheet.orchestrator.trace import Trace
from openflowsheet.verify.certificate import SolutionCertificate, verify_revision

FEED = (1.0, 1.0, 1.0)
DORMANT = (0.0, 0.0, 0.0)
#: DZ-12's duty: `U-PHF`'s root is `ref…DZ-12.root`'s.
QUP = 30_000.0
#: B31 (i)'s downstream pressure drop (`ref.downstream_flash_cases.downstream_pressure_drop_Pa`).
DOWNSTREAM: dict[str, Any] = REF["downstream_flash_cases"]
DP = float(DOWNSTREAM["downstream_pressure_drop_Pa"])
DZ12: dict[str, Any] = REF["dormant_non_lifted_cases"]["DZ-12"]
#: Spec §13's EO allowances (T02 §6.4), as `ref.tolerances.coupled_allowances` states them.
ALLOWANCE: dict[str, float] = {
    kind: float(value) for kind, value in REF["tolerances"]["coupled_allowances"].items()
}


def _allowance(column: str) -> float:
    kind = column.rsplit(".", 1)[-1]
    return {"T": ALLOWANCE["T"], "P": ALLOWANCE["P"], "Q": ALLOWANCE["duty"]}.get(
        kind, ALLOWANCE["flow"]
    )


# ------------------------------------------------------------------------------ the revisions


def _phf2(identifier: str = "U-PHF2", dp: float = 0.0) -> Document:
    """C1's `U-PHF` renamed, at pressure drop `dp` (C1's is `0.0`); its duty pin is the
    revision's (`Q = 0`)."""
    document = instance("SYN-001-UL-C1", "U-PHF", identifier)
    if dp:
        document["parameters"]["pressure_drop"]["value"] = dp
    return document


def _dp(dp: float) -> str:
    """The revision-name suffix of B31 (i)'s companions (none for the dew-point cases)."""
    return f"-dp{dp:g}" if dp else ""


def ch(
    duty: float,
    *,
    feed: tuple[float, float, float] = FEED,
    phf2_first: bool = False,
    dp: float = 0.0,
) -> Document:
    """CH-UP's flowsheet: feed → `U-PHF` (`Q = duty`) → `S2` vap → `U-PHF2` (`ΔP = dp`) → `S4`
    vap, `S5` liq; `S3` liq → sink."""
    phf, phf2 = instance("SYN-001-UL-C1", "U-PHF"), _phf2(dp=dp)
    name = f"B31-CH-{duty:g}-{'x'.join(f'{f:g}' for f in feed)}{_dp(dp)}"
    return revision(
        name + ("-phf2-first" if phf2_first else ""),
        [phf2, phf] if phf2_first else [phf, phf2],
        [Source("S1", "U-PHF", "inlet", "liquid", feed, 300.0, P_R)],
        [Link("S2", ("U-PHF", "vapor"), ("U-PHF2", "inlet"), "vapor")],
        [
            Product("S3", ("U-PHF", "liquid"), "liquid"),
            Product("S4", ("U-PHF2", "vapor"), "vapor"),
            Product("S5", ("U-PHF2", "liquid"), "liquid"),
        ],
        [duty_pin("SPEC-phf-Q", "U-PHF", duty), duty_pin("SPEC-phf2-Q", "U-PHF2", 0.0)],
    )


def ch3(duty: float, *, dp: float = 0.0) -> Document:
    """CH-UP plus `U-PHF3` on `S4` (products `S6` vap, `S7` liq), declared `U-PHF3`, `U-PHF2`,
    `U-PHF`; both downstream flashes at `ΔP = dp`."""
    return revision(
        f"B31-CH3-{duty:g}{_dp(dp)}",
        [_phf2("U-PHF3", dp), _phf2(dp=dp), instance("SYN-001-UL-C1", "U-PHF")],
        [Source("S1", "U-PHF", "inlet", "liquid", FEED, 300.0, P_R)],
        [
            Link("S2", ("U-PHF", "vapor"), ("U-PHF2", "inlet"), "vapor"),
            Link("S4", ("U-PHF2", "vapor"), ("U-PHF3", "inlet"), "vapor"),
        ],
        [
            Product("S3", ("U-PHF", "liquid"), "liquid"),
            Product("S5", ("U-PHF2", "liquid"), "liquid"),
            Product("S6", ("U-PHF3", "vapor"), "vapor"),
            Product("S7", ("U-PHF3", "liquid"), "liquid"),
        ],
        [
            duty_pin("SPEC-phf-Q", "U-PHF", duty),
            duty_pin("SPEC-phf2-Q", "U-PHF2", 0.0),
            duty_pin("SPEC-phf3-Q", "U-PHF3", 0.0),
        ],
    )


def ch_dz12(duty: float, *, dp: float = 0.0) -> Document:
    """DZ-12's flowsheet plus `U-PHF2` (`ΔP = dp`) on the exchanger's hot outlet `S4` (products
    `S7` vap, `S8` liq)."""
    return revision(
        f"B31-CH-DZ12-{duty:g}{_dp(dp)}",
        [instance("SYN-001-UL-C1", "U-PHF"), instance("SYN-001-UL-C3", "U-HX"), _phf2(dp=dp)],
        [
            Source("S1", "U-PHF", "inlet", "liquid", FEED, 300.0, P_R),
            Source("S5", "U-HX", "cold_inlet", "liquid", FEED, 300.0, P_R),
        ],
        [
            Link("S2", ("U-PHF", "vapor"), ("U-HX", "hot_inlet"), "vapor"),
            Link("S4", ("U-HX", "hot_outlet"), ("U-PHF2", "inlet"), "vapor"),
        ],
        [
            Product("S3", ("U-PHF", "liquid"), "liquid"),
            Product("S6", ("U-HX", "cold_outlet"), "liquid"),
            Product("S7", ("U-PHF2", "vapor"), "vapor"),
            Product("S8", ("U-PHF2", "liquid"), "liquid"),
        ],
        [
            duty_pin("SPEC-phf-Q", "U-PHF", duty),
            duty_pin("SPEC-hx-Q", "U-HX", 0.0),
            duty_pin("SPEC-phf2-Q", "U-PHF2", 0.0),
        ],
    )


def _traversal(document: Document) -> dict[str, float]:
    binding = bind(document)
    start = initial_state(binding.flowsheet, binding.spec.variable_ids)
    assert isinstance(start, dict), start
    return start


def _dormant_start(phf2_first: bool) -> dict[str, float]:
    """`initial_state` of CH-UP with the feed's flows set to `0.0`."""
    start = _traversal(ch(QUP, phf2_first=phf2_first))
    return {name: 0.0 if name.startswith("S1.n.") else value for name, value in start.items()}


#: `case → (target revision, start)`, spec B31.
CASES: dict[str, Any] = {
    "CH-UP": lambda: (ch(QUP), _traversal(ch(0.0))),
    "CH-DOWN": lambda: (ch(0.0), _traversal(ch(QUP))),
    "CH-DZ12": lambda: (ch_dz12(QUP), _traversal(ch_dz12(0.0))),
    "CH-3": lambda: (ch3(QUP), _traversal(ch3(0.0))),
    "CH-DORMANT": lambda: (ch(0.0, feed=DORMANT), _dormant_start(False)),
    "CH-UP/PHF2-first": lambda: (
        ch(QUP, phf2_first=True),
        _traversal(ch(0.0, phf2_first=True)),
    ),
    "CH-DOWN/PHF2-first": lambda: (
        ch(0.0, phf2_first=True),
        _traversal(ch(QUP, phf2_first=True)),
    ),
    "CH-DORMANT/PHF2-first": lambda: (
        ch(0.0, feed=DORMANT, phf2_first=True),
        _dormant_start(True),
    ),
    # B31 (i): every downstream flash at `ΔP = DP`, everything else the dew-point case's.
    "CH-UP-DP": lambda: (ch(QUP, dp=DP), _traversal(ch(0.0, dp=DP))),
    "CH-DZ12-DP": lambda: (ch_dz12(QUP, dp=DP), _traversal(ch_dz12(0.0, dp=DP))),
    "CH-3-DP": lambda: (ch3(QUP, dp=DP), _traversal(ch3(0.0, dp=DP))),
}


@dataclasses.dataclass(frozen=True)
class Run:
    result: RegionResult
    opened: list[str]
    initializer: list[str]
    certificate: SolutionCertificate | None
    signature_units: tuple[str, ...]


@cache
def solved(case: str) -> Run:
    document, start = CASES[case]()
    binding = bind(document)
    trace = Trace()
    result = solve_from_v2(binding, start, trace=trace)
    step = planned_step(binding, POLICY_V2)
    certificate = None
    if result.outcome == "CONVERGED":
        certificate = verify_revision(
            binding, document, result, state=dict(result.state), solve_plan=step.solve_plan
        )
    assert step.region is not None
    return Run(
        result,
        [e.message for e in trace.events if e.kind == "attempt_opened"],
        [e.message for e in trace.events if e.kind.startswith("initializer")],
        certificate,
        step.region.signature_units,
    )


def _signatures(result: RegionResult) -> list[list[list[str]]]:
    return [[list(entry) for entry in attempt.signature] for attempt in result.attempts]


def _final_regimes(result: RegionResult) -> dict[str, str]:
    return dict(result.attempts[-1].signature)


# ---------------------------------------------------------------- the closed-form comparisons

_ROOT_STREAMS = ("S2", "S3")


def closed_form(case: str) -> dict[str, str]:
    """`{column: expected}` of B31 (b)–(c)'s comparison at §13's EO allowances (20-digit strings
    from `ref`, or the exact values the closed form gives)."""
    root = DZ12["root"]
    base = case.split("/")[0].removesuffix("-DP")
    if base == "CH-DOWN":
        expected = {f"S3.n.{c}": "1" for c in "ABC"}
        expected["S3.T"] = "300"
        return expected
    if base == "CH-DZ12":
        expected = dict(root)
        downstream = {"S7": "S4"}
        empty = ("S8",)
    else:
        expected = {k: v for k, v in root.items() if k.split(".")[0] in _ROOT_STREAMS}
        expected["U-PHF.Q"] = root["U-PHF.Q"]
        downstream = {"S4": "S2", "S6": "S2"} if base == "CH-3" else {"S4": "S2"}
        empty = ("S5", "S7") if base == "CH-3" else ("S5",)
    for product, feed in downstream.items():
        for c in "ABC":
            expected[f"{product}.n.{c}"] = root[f"{feed}.n.{c}"]
        expected[f"{product}.T"] = root[f"{feed}.T"]
    for product in empty:
        for c in "ABC":
            expected[f"{product}.n.{c}"] = "0"
    if case.endswith("-DP"):
        # B31 (i): each downstream flash's products at its feed's `P` less `DP` (`P_r` upstream).
        for product, stages in DP_STAGES[base].items():
            expected[f"{product}.P"] = repr(P_R - stages * DP)
    return expected


#: B31 (i): how many downstream flashes (each `ΔP = DP`) lie between the feed and each product.
DP_STAGES: dict[str, dict[str, int]] = {
    "CH-UP": {"S4": 1, "S5": 1},
    "CH-DZ12": {"S7": 1, "S8": 1},
    "CH-3": {"S4": 1, "S5": 1, "S6": 2, "S7": 2},
}


def realized_ratio(case: str) -> tuple[float, str]:
    """The largest `|x_final − expected| / allowance` over `closed_form(case)` (K04-F9 X26 (a))."""
    state = solved(case).result.state
    return max(
        (float(abs(Decimal(state[column]) - Decimal(value))) / _allowance(column), column)
        for column, value in closed_form(case).items()
    )


# ------------------------------------------------------------------------------ (a) no raise

TYPED = {"CONVERGED", "ACTIVE_SET_CYCLING", "LINEAR_SOLVE_FAILED", "BOUND_BLOCKED"}


@pytest.mark.parametrize("case", CASES)
def test_b31a_no_case_raises(case: str) -> None:
    """(a) Each case ends in a typed outcome (before the fixed point, all but CH-DORMANT raised)."""
    assert solved(case).result.outcome in TYPED


# --------------------------------------------------------------- (b) CH-UP, CH-DZ12, CH-3

#: Regression values (W9.3): each case's attempts and `attempt_opened` messages. Re-registered at
#: W10.4 (B36, Q-S14 — the leaving flash at the feed's `T`, written to both products): attempt 1's
#: iterations fell 1 → 0 in CH-UP and CH-3 (the opening is the root); CH-DZ12's stay 1 (its
#: `U-PHF2` feed is the exchanger's reset hot outlet). Outcomes, signatures and messages unchanged.
RESTARTS: dict[str, tuple[list[tuple[str, int, list[list[str]], str]], list[str]]] = {
    "CH-UP": (
        [
            (
                "PHASE_UPDATE_REQUIRED",
                2,
                [["U-PHF", "LIQUID"], ["U-PHF2", "ZERO_FLOW"]],
                "phase_wall(patience, U-PHF:LIQUID->TWO_PHASE)",
            ),
            ("CONVERGED", 0, [["U-PHF", "TWO_PHASE"], ["U-PHF2", "VAPOR"]], ""),
        ],
        [
            "initial",
            "phase_update(phase_wall(patience, U-PHF:LIQUID->TWO_PHASE); fallback(U-PHF2, tp))",
        ],
    ),
    "CH-DZ12": (
        [
            (
                "PHASE_UPDATE_REQUIRED",
                2,
                [["U-PHF", "LIQUID"], ["U-PHF2", "ZERO_FLOW"], ["U-HX.hot_outlet", "ZERO_FLOW"]],
                "phase_wall(patience, U-PHF:LIQUID->TWO_PHASE)",
            ),
            ("CONVERGED", 1, [["U-PHF", "TWO_PHASE"], ["U-PHF2", "VAPOR"]], ""),
        ],
        [
            "initial",
            "phase_update(phase_wall(patience, U-PHF:LIQUID->TWO_PHASE); fallback(U-PHF2, tp))",
        ],
    ),
    "CH-3": (
        [
            (
                "PHASE_UPDATE_REQUIRED",
                2,
                [["U-PHF3", "ZERO_FLOW"], ["U-PHF2", "ZERO_FLOW"], ["U-PHF", "LIQUID"]],
                "phase_wall(patience, U-PHF:LIQUID->TWO_PHASE)",
            ),
            (
                "CONVERGED",
                0,
                [["U-PHF3", "VAPOR"], ["U-PHF2", "VAPOR"], ["U-PHF", "TWO_PHASE"]],
                "",
            ),
        ],
        [
            "initial",
            "phase_update(phase_wall(patience, U-PHF:LIQUID->TWO_PHASE); "
            "fallback(U-PHF3, tp), fallback(U-PHF2, tp))",
        ],
    ),
}


@pytest.mark.parametrize("case", ["CH-UP", "CH-DZ12", "CH-3"])
def test_b31b_leaving_zero_flow_downstream_converges(case: str) -> None:
    """(b) `CONVERGED`; the attempt whose opening takes a downstream flash out of `ZERO_FLOW`
    carries `fallback(<U>, tp)` for it on its `attempt_opened` (the fixed point's leaving, spec
    §7.4, §7.8 (ii) 3); every signature agrees with exact dormancy of its opening."""
    run = solved(case)
    result = run.result
    assert result.outcome == "CONVERGED", result.message
    attempts, opened = RESTARTS[case]
    assert [
        (a.outcome, a.iterations, [list(e) for e in a.signature], a.reason) for a in result.attempts
    ] == attempts
    assert run.opened == opened
    for index in range(1, len(result.attempts)):
        before = dict(result.attempts[index - 1].signature)
        after = dict(result.attempts[index].signature)
        for unit in ("U-PHF2", "U-PHF3"):
            if before.get(unit) == "ZERO_FLOW" and after.get(unit) != "ZERO_FLOW":
                assert f"fallback({unit}, tp)" in run.opened[index], (unit, run.opened[index])


@pytest.mark.parametrize("case", ["CH-UP", "CH-DZ12", "CH-3", "CH-DOWN"])
def test_b31bc_the_final_state_is_the_closed_form(case: str) -> None:
    """(b), (c): the final state within §13's EO allowances of the closed form — `U-PHF`'s
    streams DZ-12's registered root, each downstream flash's vapour product its feed at that `T`
    and its liquid product 0 (CH-DZ12: the exchanger as DZ-12's root); CH-DOWN's `S3` the feed
    at 300 K. K04-F9 X26 (a) holds these at a tenth of the allowance."""
    ratio, column = realized_ratio(case)
    assert ratio <= 1.0, (case, column, ratio)


#: (b)'s verdict (Q-S9 addendum): rank loss exactly one per downstream flash on its dew point
#: (`ref.downstream_flash_cases`: `CH-UP/dp=0` rank 30 of 31, `CH-3/dp=0` 42 of 44); the order
#: variant as its declared-first case (e).
RANK_LOSS = {"CH-UP": 1, "CH-DZ12": 1, "CH-3": 2, "CH-UP/PHF2-first": 1}


@pytest.mark.parametrize("case", RANK_LOSS)
def test_b31b_the_certificate_is_unverified_at_the_dew_point(case: str) -> None:
    """(b)'s verdict (amended, Q-S9 addendum): `UNVERIFIED`, never `VERIFIED`, with regularity
    `RANK_DEFICIENT`, rank loss one per downstream flash on its dew point (where the declared
    lifted equilibrium rows are singular, §17), and no check `fail` or `unsupported` (a dormant
    liquid product's `not_applicable` checks aside)."""
    certificate = solved(case).certificate
    assert certificate is not None
    assert certificate.verification_status != "VERIFIED"
    assert certificate.verification_status == "UNVERIFIED"
    regularity = certificate.regularity
    assert regularity is not None and regularity.status == "RANK_DEFICIENT"
    assert regularity.escalation is not None
    assert regularity.dimension - regularity.escalation["rank"] == RANK_LOSS[case]
    failing = [c.id for c in certificate.checks if c.result in ("fail", "unsupported")]
    assert failing == []


# ----------------------------------------------------------------- (i) off the dew point

#: B31 (i)'s companions and the dew-point case each repeats.
OFF_DEW = {"CH-UP-DP": "CH-UP", "CH-DZ12-DP": "CH-DZ12", "CH-3-DP": "CH-3"}
#: Regression values of their own (W10.1): each companion's iteration counts per attempt.
#: Re-registered at W10.4 (B36): `[2, 1]` → `[2, 0]` for CH-UP-DP and CH-3-DP, as their
#: dew-point cases.
OFF_DEW_ITERATIONS: dict[str, list[int]] = {
    "CH-UP-DP": [2, 0],
    "CH-DZ12-DP": [2, 1],
    "CH-3-DP": [2, 0],
}


@pytest.mark.parametrize("case", OFF_DEW)
def test_b31i_off_the_dew_point_the_restart_certifies(case: str) -> None:
    """(i) `CONVERGED`, `VERIFIED`, regularity `NO_RANK_LOSS_DETECTED`: at `ΔP = 10 kPa` every
    downstream flash's feed is superheated at its outlet pressure (`ref.downstream_flash_cases`,
    `boundary_function` −0.0997, −0.1995), so its declared lifted form is regular. (b)'s verdict
    and this one discriminate: a screen that never reports rank loss fails (b), one that always
    does fails (i)."""
    run = solved(case)
    assert run.result.outcome == "CONVERGED", run.result.message
    certificate = run.certificate
    assert certificate is not None
    assert certificate.verification_status == "VERIFIED", [
        (c.id, c.value) for c in certificate.checks if c.result in ("fail", "unsupported")
    ]
    assert certificate.regularity is not None
    assert certificate.regularity.status == "NO_RANK_LOSS_DETECTED"


@pytest.mark.parametrize("case", OFF_DEW)
def test_b31i_the_same_restarts_end_in_vapor(case: str) -> None:
    """(i) The attempts' outcomes, signatures and reasons and the `attempt_opened` messages are the
    dew-point case's under (b), `fallback(<U>, tp)` included; iteration counts are *regression*
    values of their own; every downstream flash `VAPOR` in the final signature — determined, not
    regression: its feed is superheated at its outlet pressure."""
    run = solved(case)
    attempts, opened = RESTARTS[OFF_DEW[case]]
    assert [(a.outcome, [list(e) for e in a.signature], a.reason) for a in run.result.attempts] == [
        (outcome, signature, reason) for outcome, _, signature, reason in attempts
    ]
    assert run.opened == opened
    assert [a.iterations for a in run.result.attempts] == OFF_DEW_ITERATIONS[case]
    final = _final_regimes(run.result)
    downstream = [unit for unit in ("U-PHF2", "U-PHF3") if unit in run.signature_units]
    assert downstream and all(final[unit] == "VAPOR" for unit in downstream)


@pytest.mark.parametrize("case", OFF_DEW)
def test_b31i_the_final_state_is_the_closed_form(case: str) -> None:
    """(i) The final state within §13's EO allowances of (b)'s closed form with each downstream
    flash's products at its feed's `P` less 10 kPa (CH-UP-DP `S4.P = S5.P = 90 000`; CH-3-DP also
    `S6.P = S7.P = 80 000`; CH-DZ12-DP `S7.P = S8.P = 90 000`), its vapour product still its feed
    at the feed's `T` (SYN-001's `h^V` has no pressure term) and its liquid product 0."""
    ratio, column = realized_ratio(case)
    assert ratio <= 1.0, (case, column, ratio)


# ------------------------------------------------------------------------------ (c) CH-DOWN


def test_b31c_ch_down() -> None:
    """(c) `CONVERGED`, `VERIFIED`; `U-PHF` `LIQUID`; `U-PHF2` `ZERO_FLOW` in the final
    signature, every flow of `S4`, `S5` exactly `0.0`, `S4.T` on `S2.T` to 1e-9 K."""
    run = solved("CH-DOWN")
    result = run.result
    assert result.outcome == "CONVERGED", result.message
    assert run.certificate is not None
    assert run.certificate.verification_status == "VERIFIED"
    assert _final_regimes(result) == {"U-PHF": "LIQUID", "U-PHF2": "ZERO_FLOW"}
    state = result.state
    assert all(state[f"{s}.n.{c}"] == 0.0 for s in ("S4", "S5") for c in "ABC")
    assert abs(state["S4.T"] - state["S2.T"]) <= 1e-9
    # Regression values (W9.3).
    assert [(a.outcome, a.iterations, a.reason) for a in result.attempts] == [
        ("PHASE_UPDATE_REQUIRED", 1, "phase_disappeared(U-PHF, vapor, S2.n.C)"),
        ("CONVERGED", 1, ""),
    ]
    assert run.opened == ["initial", "phase_update(phase_disappeared(U-PHF, vapor, S2.n.C))"]


# --------------------------------------------------------------------------- (d) CH-DORMANT


@pytest.mark.parametrize("case", ["CH-DORMANT", "CH-DORMANT/PHF2-first"])
def test_b31d_ch_dormant(case: str) -> None:
    """(d) Attempt 0's signature is both splits in `ZERO_FLOW`, in plan order; each overwrite is
    recorded `projected(<S>, <branch>, ZERO_FLOW)` — the order variant's `U-PHF2` by the fixed
    point, after `U-PHF`'s start rule made its feed dormant; `CONVERGED` at iteration 0 or 1,
    `VERIFIED`; every flow `0.0`; `S2.T`, `S4.T` within 1e-9 K of 300 K."""
    run = solved(case)
    result = run.result
    assert result.outcome == "CONVERGED", result.message
    assert run.certificate is not None
    assert run.certificate.verification_status == "VERIFIED"
    assert result.attempts[0].signature == tuple(
        (unit, "ZERO_FLOW") for unit in run.signature_units
    )
    assert set(run.signature_units) == {"U-PHF", "U-PHF2"}
    assert len(result.attempts) == 1 and result.attempts[0].iterations in (0, 1)
    assert run.initializer == [
        "projected(S1, two_phase, ZERO_FLOW)",
        "projected(S2, all_vapor, ZERO_FLOW)",
        "the start with 2 split(s) projected onto the kernel's",
    ]
    assert result.projections == ("S1", "S2")
    state = result.state
    flows = [v for k, v in state.items() if k.split(".")[1] in ("n", "vap", "liq", "N", "V", "L")]
    assert flows and all(value == 0.0 for value in flows)
    for stream in ("S2", "S4"):
        assert abs(state[f"{stream}.T"] - 300.0) <= 1e-9


# ---------------------------------------------------------------------- (e) the order variants


@pytest.mark.parametrize("case", ["CH-UP", "CH-DOWN", "CH-DORMANT"])
def test_b31e_an_order_variant_is_its_declared_first_case(case: str) -> None:
    """(e) The same outcome, verdict, final regimes and final state (within the allowances) as
    the declared-first case; attempt counts are *regression* (equal here)."""
    first, variant = solved(case), solved(f"{case}/PHF2-first")
    assert variant.result.outcome == first.result.outcome
    assert first.certificate is not None and variant.certificate is not None
    assert variant.certificate.verification_status == first.certificate.verification_status
    assert _final_regimes(variant.result) == _final_regimes(first.result)
    assert len(variant.result.attempts) == len(first.result.attempts)
    for column, value in first.result.state.items():
        got = variant.result.state[column]
        assert abs(got - value) <= _allowance(column), (column, got, value)


# ---------------------------------------------------- (f) a chain of forms, at the function level


def pump_chain(*, pump2_first: bool = False) -> Document:
    """Feed `(1,1,1)` 300 K → `U-PHF` (`Q = 30 kW`) → `S2` vap → sink; `S3` liq → `U-PUMP1`
    (`P = 1.5e5 Pa`) → `S4` → `U-PUMP2` (`P = 2e5 Pa`) → `S5` → sink."""
    pump1 = instance("SYN-001-UL-C1", "U-PUMP", "U-PUMP1")
    pump2 = instance("SYN-001-UL-C1", "U-PUMP", "U-PUMP2")
    phf = instance("SYN-001-UL-C1", "U-PHF")
    return revision(
        "B31-pump-chain" + ("-pump2-first" if pump2_first else ""),
        [phf, pump2, pump1] if pump2_first else [phf, pump1, pump2],
        [Source("S1", "U-PHF", "inlet", "liquid", FEED, 300.0, P_R)],
        [
            Link("S3", ("U-PHF", "liquid"), ("U-PUMP1", "inlet"), "liquid"),
            Link("S4", ("U-PUMP1", "outlet"), ("U-PUMP2", "inlet"), "liquid"),
        ],
        [
            Product("S2", ("U-PHF", "vapor"), "vapor"),
            Product("S5", ("U-PUMP2", "outlet"), "liquid"),
        ],
        [
            duty_pin("SPEC-phf-Q", "U-PHF", QUP),
            connection_pin("SPEC-pump1-P", "S4", "state.P", 1.5e5),
            connection_pin("SPEC-pump2-P", "S5", "state.P", 2.0e5),
        ],
    )


def _chain_opening(pump2_first: bool) -> tuple[Any, tuple[Any, ...], dict[str, float]]:
    """The chain's splits, its fixed-point order, and a restart opening whose kernel answer made
    `S3` flow (`U-PHF` `TWO_PHASE`, the traversal's split) while `S4`, `S5` are still exactly
    dormant from the closing attempt."""
    binding = bind(pump_chain(pump2_first=pump2_first))
    flowsheet = binding.flowsheet
    instances = instances_of(flowsheet)
    splits = lifted_splits(instances, flowsheet.components)
    forms = dormancy_forms(instances, flowsheet.units(), flowsheet.components)
    region = planned_step(binding, POLICY_V2).region
    assert region is not None
    order = _opening_order(splits, forms, region.units)
    state = _traversal(pump_chain(pump2_first=pump2_first))
    assert all(state[f"S3.n.{c}"] > 0.0 for c in "ABC")
    for stream in ("S4", "S5"):
        for c in "ABC":
            state[f"{stream}.n.{c}"] = 0.0
    return (binding, splits, forms), order, state


def _no_leave(split: LiftedSplit, state: Any) -> Any:
    raise AssertionError(f"{split.unit} should not leave ZERO_FLOW here")


@pytest.mark.parametrize("pump2_first", [False, True])
def test_b31f_a_chain_of_resets_settles(pump2_first: bool) -> None:
    """(f) The opening's fixed point resets `S4 := S3`, then `S5 := S4`, exactly, in either
    declaration order, and opens with no pump item; no split changes."""
    (_, _, forms), order, state = _chain_opening(pump2_first)
    reference = frozenset({"U-PUMP1.outlet", "U-PUMP2.outlet"})
    opened, regimes, records, changes = _settle(
        state, {"U-PHF": "TWO_PHASE"}, order=order, reference=reference, leave=_no_leave
    )
    for c in "ABC":
        assert opened[f"S4.n.{c}"] == opened[f"S3.n.{c}"]
        assert opened[f"S5.n.{c}"] == opened[f"S4.n.{c}"]
    assert _items(forms, opened) == ()
    assert regimes == {"U-PHF": "TWO_PHASE"} and records == {} and changes == []
    assert [getattr(entry, "item", getattr(entry, "unit", "")) for entry in order] == (
        ["U-PHF", "U-PUMP2.outlet", "U-PUMP1.outlet"]
        if pump2_first
        else ["U-PHF", "U-PUMP1.outlet", "U-PUMP2.outlet"]
    )


def test_b31f_a_single_pass_leaves_the_second_pump_stale() -> None:
    """(f)'s control: one pass with `U-PUMP2` declared first visits it while `S4` is still
    dormant — it keeps its item and `S5` stays `0.0` — and only then resets `S4`, so the opening
    would carry a stale item over a flowing trigger (F7's singular first Jacobian)."""
    (_, _, forms), order, state = _chain_opening(True)
    reference = frozenset({"U-PUMP1.outlet", "U-PUMP2.outlet"})
    regimes: dict[str, Any] = {"U-PHF": "TWO_PHASE"}
    present_at_visit: dict[str, bool] = {}
    for entry in order:
        if isinstance(entry, DormancyForm):
            present_at_visit[entry.item] = _trigger_dormant(entry, state)
        _rederive(entry, state, regimes, reference, _no_leave, {}, [])
    assert present_at_visit == {"U-PUMP2.outlet": True, "U-PUMP1.outlet": False}
    assert all(state[f"S4.n.{c}"] == state[f"S3.n.{c}"] for c in "ABC")
    assert all(state[f"S5.n.{c}"] == 0.0 for c in "ABC")


# ---------------------------------------------------- (g) a fixed point that never settles


def _never_settles(entry: Any, *args: Any) -> str:
    return entry.item if isinstance(entry, DormancyForm) else entry.unit


def test_b31g_attempt_0_that_never_settles_is_typed(monkeypatch: pytest.MonkeyPatch) -> None:
    """(g) With the re-derivation stubbed to report a change at every entry, attempt 0's opening
    closes `ACTIVE_SET_CYCLING` with `opening_not_settled(<first entry>)`, no exception."""
    monkeypatch.setattr(region_module, "_rederive", _never_settles)
    document, start = CASES["CH-UP"]()
    result = solve_from_v2(bind(document), start)
    assert result.outcome == "ACTIVE_SET_CYCLING"
    assert result.message.splitlines()[0] == "opening_not_settled(U-PHF)"
    assert result.attempts == ()


def test_b31g_a_restart_that_never_settles_is_typed(monkeypatch: pytest.MonkeyPatch) -> None:
    """(g) The same at a restart opening: attempt 0 opens and closes as in CH-UP, and the restart's
    fixed point, stubbed never to settle, closes the region `ACTIVE_SET_CYCLING`,
    `opening_not_settled(U-PHF)`, with attempt 0 kept on the record."""
    real = region_module._rederive
    at_restart = {"on": False}
    settled = region_module._LiftedOps._settled

    def rederive(entry: Any, *args: Any) -> str:
        return _never_settles(entry) if at_restart["on"] else real(entry, *args)

    def restart(self: Any, *args: Any, **kwargs: Any) -> Any:
        at_restart["on"] = True
        try:
            return settled(self, *args, **kwargs)
        finally:
            at_restart["on"] = False

    monkeypatch.setattr(region_module, "_rederive", rederive)
    monkeypatch.setattr(region_module._LiftedOps, "_settled", restart)
    document, start = CASES["CH-UP"]()
    result = solve_from_v2(bind(document), start)
    assert result.outcome == "ACTIVE_SET_CYCLING"
    assert result.message.splitlines()[0] == "opening_not_settled(U-PHF)"
    assert [a.outcome for a in result.attempts] == ["ACTIVE_SET_CYCLING"]


# ------------------------------------------------------------------- the leaving kernel's record


def test_the_leaving_kernel_is_the_tp_flash_recorded_tp() -> None:
    """§7.4's leaving, as the fixed point calls it: a PH-type split in `ZERO_FLOW` whose feed
    flows takes the TP flash's regime and split, recorded `tp`."""
    binding = bind(ch(QUP))
    flowsheet = binding.flowsheet
    instances = instances_of(flowsheet)
    splits = {s.unit: s for s in lifted_splits(instances, flowsheet.components)}
    types = closure_types(flowsheet.units())
    ph_units = frozenset(unit for unit, kind in types.items() if kind == "PH")
    state = _traversal(ch(QUP))
    answer = _contract_kernel(
        flowsheet.provider,
        flowsheet.context,
        splits["U-PHF2"],
        state,
        ph_units,
        v2=True,
        regime="ZERO_FLOW",
    )
    assert answer.fallback == "tp" and answer.regime in ("VAPOR", "TWO_PHASE")
