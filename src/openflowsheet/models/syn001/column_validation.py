"""`syn001.column`'s refusals: S02 spec §5 (S1 to S10) with S06's inverse refusals I1 to I6, the
§5 S10 split feasibility and the energy pre-check, and the column's warnings.

Moved verbatim from `column` (S19 B2), which re-exports every name here and keeps the regime forms
and the §6 initializer. This module imports only `column_spec` among the column modules.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from fractions import Fraction
from typing import Final

from openflowsheet.compiled import EvaluationContext
from openflowsheet.models import pressure_id, temperature_id
from openflowsheet.models.syn001 import P_MAX, P_MIN, T_MAX, T_MIN
from openflowsheet.models.syn001.cascade import (
    INLET_PHASES,
    CascadeFailure,
    EnergyPrecheck,
    _enthalpy_flow,
    _in_domain,
    _invalid,
    _is_dormant,
    _phase,
    inlet_stream,
    stage_pressure_id,
    stage_temperature_id,
)
from openflowsheet.models.syn001.column_spec import (
    COMPONENT_KINDS,
    CONDENSER,
    CONDENSER_KINDS,
    END_KINDS,
    GAMMA_PHI_KINDS,
    INVERSE_KINDS,
    NOT_OFFERED,
    REBOILER,
    REBOILER_KINDS,
    ColumnSpec,
    _specification,
    product_flow_id,
    product_total_id,
)
from openflowsheet.models.syn001.equilibrium_form import (
    EquilibriumForm,
    admission,
    equilibrium_form,
)
from openflowsheet.models.syn001.tp_state import single_phase_admissible
from openflowsheet.thermo import Phase, PropertyProvider, StreamState
from openflowsheet.thermo import syn001 as syn001_thermo

# -- spec §5: validation -------------------------------------------------------------------------


def _feed_total(spec: ColumnSpec) -> float:
    return sum(sum(inlet.state.n) for inlet in spec.inlets())


def component_feeds(spec: ColumnSpec) -> tuple[float, ...]:
    """S06 §1: `F_c = Σ_k n_{k,c}` over the present inlets in `inlets()` order, binary64, one per
    component of `spec.components`."""
    inlets = spec.inlets()
    return tuple(sum(inlet.state.n[i] for inlet in inlets) for i in range(len(spec.components)))


def purity_reference(spec: ColumnSpec) -> float:
    """S06 §1: `F = Σ_c F_c`, binary64, summed in component order."""
    return sum(component_feeds(spec))


def inverse_parameter(spec: ColumnSpec, end: str) -> float:
    """S06 §2: the pinned slot parameter of an inverse end: `T*`, `ν* = fl(r*·F_c)` or
    `π* = fl(x*·F)`."""
    given = _specification(spec, end)
    if given.kind == "temperature":
        return given.value
    if given.kind == "recovery":
        assert given.component is not None, "validate first"
        return given.value * component_feeds(spec)[spec.components.index(given.component)]
    if given.kind == "purity":
        return given.value * purity_reference(spec)
    raise ValueError(f"{given.kind!r} is not an inverse specification")


def specified_quantity(spec: ColumnSpec, end: str, state: Mapping[str, float]) -> float:
    """S06 §7.3: an inverse end's quantity at `state`, binary64: `n_c / P` (purity), `n_c / F_c`
    (recovery) or `T_s` (temperature)."""
    given = _specification(spec, end)
    if given.kind == "temperature":
        assert given.stage is not None, "validate first"
        return float(state[stage_temperature_id(spec.unit_id, given.stage)])
    if given.kind not in COMPONENT_KINDS:
        raise ValueError(f"{given.kind!r} is not an inverse specification")
    assert given.component is not None, "validate first"
    flow = float(state[product_flow_id(spec, end, given.component)])
    if given.kind == "recovery":
        return flow / component_feeds(spec)[spec.components.index(given.component)]
    return flow / float(state[product_total_id(spec, end)])


def saturation_temperature(component: str, pressure: float) -> float:
    """S06 §4: SYN-001's `T_sat,i(P) = (L_i − V_i (P − P_ref)) / (L_i / T_b,i + R ln(P_ref / P))`,
    the root of `ln K_i(T, P) = 0`, in binary64 (K)."""
    i = syn001_thermo.COMPONENTS.index(component)
    latent = syn001_thermo.L_VAP[i]
    numerator = latent - syn001_thermo.V_MOLAR[i] * (pressure - syn001_thermo.P_REF)
    return numerator / (
        latent / syn001_thermo.T_BOIL[i]
        + syn001_thermo.R * math.log(syn001_thermo.P_REF / pressure)
    )


def stage_band(spec: ColumnSpec, stage: int) -> tuple[float, float]:
    """S06 §4: the open band `(T_sat,lightest(P_s*), T_sat,heaviest(P_s*))` over the components
    with `F_c > 0`, as the least and the greatest of their saturation temperatures (§4 shows they
    are ordered A < B < C at every P). Needs a present component; `validate` refuses a feedless
    column first (S10)."""
    pressure = spec.pressures[stage - 1]
    present = [
        saturation_temperature(c, pressure)
        for c, feed in zip(spec.components, component_feeds(spec), strict=True)
        if feed > 0.0
    ]
    if not present:
        raise ValueError(f"{spec.unit_id}: no present component; validate first (S10)")
    return min(present), max(present)


def validate(
    spec: ColumnSpec, provider: PropertyProvider, context: EvaluationContext
) -> CascadeFailure | None:
    """§5, before any row is evaluated: the first refusal that applies, or `None`.

    Order: S01's R1, R2, R3, R4, R6, R5 as written for the present inlets (S01's order), then
    S1–S10, then R7 when every slot is a duty. A malformed object (a pressure or duty list that is
    not one per stage, a non-finite duty, a `None` duty anywhere but a column-specification stage,
    a flow vector of the wrong length, a duplicated port) is misuse and raises `ValueError`.

    S03 §9 S11, as S10-C §4.1 amends it for the column, precedes R1: a provider outside the
    equilibrium forms' allow-list is refused by identity (`equilibrium_form.admission`) before
    anything else is read or evaluated. For a composition-dependent form the domain bounds of R3
    are the provider's declared `T` and `P` boxes, and the specification kinds are narrowed after
    S10 (S10-C §4.8); SYN-001 keeps its constants.
    """
    unit, components = spec.unit_id, spec.components
    # S11 (S03 §9; S10-C §4.1)
    refused = admission(unit, provider, context)
    if refused is not None:
        return refused
    form = equilibrium_form(provider)
    t_bounds, p_bounds = _domain(form)
    count = spec.stage_count
    # R1
    if isinstance(count, bool) or not isinstance(count, int) or count < 1:
        return _invalid("stage_count", f"{unit}: N = {count!r} is not an integer >= 1")
    if len(spec.pressures) != count or len(spec.duties) != count:
        raise ValueError(
            f"{unit}: {len(spec.pressures)} pressures and {len(spec.duties)} duties for "
            f"{count} stages"
        )
    for stage, duty in enumerate(spec.duties, start=1):
        if duty is not None and not math.isfinite(duty):
            raise ValueError(f"{unit}: Q_{stage}* = {duty!r} is not finite")
    inlets = spec.inlets()
    ports = [inlet.port for inlet in inlets]
    if len(set(ports)) != len(ports):
        raise ValueError(f"{unit}: inlet ports {ports} are not distinct")
    for inlet in inlets:
        if len(inlet.state.n) != len(components):
            raise ValueError(
                f"{unit}: inlet {inlet.port} carries {len(inlet.state.n)} flows for "
                f"{len(components)} components"
            )
    # R2
    for inlet in inlets:
        if not all(math.isfinite(a) and a >= 0.0 for a in inlet.state.n):
            return _invalid(
                f"inlet_flow:{inlet.port}",
                f"{unit}: inlet {inlet.port} flows {inlet.state.n} are not finite and >= 0",
            )
    # R3
    for inlet in inlets:
        stream = inlet_stream(unit, inlet.port)
        for column, value, bounds in (
            (temperature_id(stream), inlet.state.temperature, t_bounds),
            (pressure_id(stream), inlet.state.pressure, p_bounds),
        ):
            if not _in_domain(value, bounds):
                return _invalid(f"domain:{column}", f"{column} = {value!r} outside {bounds}")
    for stage, value in enumerate(spec.pressures, start=1):
        column = stage_pressure_id(unit, stage)
        if not _in_domain(value, p_bounds):
            return _invalid(f"domain:{column}", f"{column} = {value!r} outside {p_bounds}")
    # R4
    taken: set[int] = set()
    for side in spec.sides:
        stage = side.stage
        if (
            isinstance(stage, bool)
            or not isinstance(stage, int)
            or not 1 <= stage <= count
            or stage in taken
        ):
            return _invalid(
                f"side_feed_stage:{side.port}",
                f"{unit}: side feed {side.port} at stage {stage!r} (N = {count}; one side feed "
                "per stage)",
            )
        taken.add(stage)
    # R6
    for inlet in inlets:
        if inlet.state.phase not in INLET_PHASES:
            return CascadeFailure(
                "CAPABILITY_UNAVAILABLE",
                f"unsupported(two_phase_inlet:{inlet.port})",
                f"{unit}: inlet {inlet.port} declared {inlet.state.phase!r}; a column takes a "
                "declared LIQUID or VAPOR inlet only",
            )
    # R5
    for inlet in inlets:
        state = inlet.state
        if _is_dormant(state):
            continue
        phase: Phase = "LIQUID" if state.phase == "LIQUID" else "VAPOR"
        admissible, _, error, status, message = single_phase_admissible(
            provider,
            StreamState(n=state.n, temperature=state.temperature, pressure=state.pressure),
            phase,
            components,
            context,
        )
        if not admissible:
            detail = f"equivalent temperature error {error!r} K" if status == "ok" else message
            return CascadeFailure(
                "INVALID_SPECIFICATION",
                f"inadmissible_inlet({inlet.port}, {state.phase})",
                f"{unit}: inlet {inlet.port} is not an admissible {state.phase} ({detail})",
            )

    refusal = _column_refusal(spec, form)
    if refusal is not None:
        return refusal

    # R7, only when every slot is a duty (§5).
    if all(_specification(spec, end).kind == "duty" for end in spec.ends()):
        if all(_is_dormant(inlet.state) for inlet in inlets):
            # No end (S10 refused the others): S01 §4.6's all-dormant cascade.
            return None
        precheck = energy_precheck(spec, provider, context)
        if not precheck.lower <= precheck.target <= precheck.upper:
            return CascadeFailure(
                "INVALID_SPECIFICATION",
                "infeasible_spec(energy_outside_domain)",
                f"{unit}: H* = {precheck.target!r} W outside "
                f"[{precheck.lower!r}, {precheck.upper!r}] W",
            )
    return None


#: C8 (Frank, Q-S02-4): the notice on every duty-only column specification. Spec §18.1 item 3 and
#: §14: a `(duty, duty)` column may have several regular roots, and no root-selection claim is made.
MULTIPLE_STEADY_STATES_WARNING: Final = "multiple_steady_states_possible(duty_only)"


def column_warnings(spec: ColumnSpec) -> tuple[str, ...]:
    """C8: the warnings a column answer carries, decided from the specification alone. A column
    is duty-only when it has at least one end and every end's specification is of kind `duty`
    (the §5 R7 condition, which a column without ends satisfies vacuously and gets no warning)."""
    ends = spec.ends()
    given = tuple(spec.end_specification(end) for end in ends)
    if ends and all(found is not None and found.kind == "duty" for found in given):
        return (MULTIPLE_STEADY_STATES_WARNING,)
    return ()


def _domain(form: EquilibriumForm | None) -> tuple[tuple[float, float], tuple[float, float]]:
    """The `T` and `P` bounds the column checks: SYN-001's constants, or a composition-dependent
    form's declared domain (S10-C §4.8; SYN-001's constants do not describe its records)."""
    if form is not None and form.composition_dependent:
        return form.domain["T"], form.domain["P"]
    return (T_MIN, T_MAX), (P_MIN, P_MAX)


def _column_refusal(spec: ColumnSpec, form: EquilibriumForm | None = None) -> CascadeFailure | None:
    """§5 S1–S10, in that order, on a specification that passed R1–R6."""
    unit, count = spec.unit_id, spec.stage_count
    # S1
    if spec.condenser not in CONDENSER_KINDS:
        return CascadeFailure(
            "CAPABILITY_UNAVAILABLE",
            f"unsupported(condenser:{spec.condenser})",
            f"{unit}: condenser kind {spec.condenser!r} is not one of {CONDENSER_KINDS}",
        )
    if spec.reboiler not in REBOILER_KINDS:
        return CascadeFailure(
            "CAPABILITY_UNAVAILABLE",
            f"unsupported(reboiler:{spec.reboiler})",
            f"{unit}: reboiler kind {spec.reboiler!r} is not one of {REBOILER_KINDS}",
        )
    # S2
    for end in (CONDENSER, REBOILER):
        given = spec.end_specification(end)
        present = spec.end_kind(end) != "none"
        if given is None and present:
            return _invalid(f"specification:{end}", f"{unit}: no {end} specification")
        if given is None:
            continue
        if not present:
            return _invalid(
                f"specification:{end}", f"{unit}: a {end} specification at a `none` {end}"
            )
        if given.kind in NOT_OFFERED:
            return CascadeFailure(
                "CAPABILITY_UNAVAILABLE",
                f"unsupported(specification:{given.kind})",
                f"{unit}: {given.kind!r} is a specification S02 and S06 do not offer",
            )
        if given.kind not in END_KINDS[end]:
            return _invalid(
                f"specification:{end}",
                f"{unit}: {given.kind!r} is not a {end} specification ({END_KINDS[end]})",
            )
    kinds = {end: _specification(spec, end).kind for end in spec.ends()}
    # S3
    if kinds.get(CONDENSER) == "distillate_rate" and kinds.get(REBOILER) == "bottoms_rate":
        return _invalid(
            "redundant_specification",
            f"{unit}: distillate and bottoms rates are linearly dependent through the overall "
            "balance (§3)",
        )
    # S4, direct kinds only (S06 §5; I1, I2 take the inverse kinds)
    for end in spec.ends():
        given = _specification(spec, end)
        if given.kind in INVERSE_KINDS:
            continue
        value = given.value
        if given.kind == "duty":
            wrong = value >= 0.0 if end == CONDENSER else value <= 0.0
        else:
            wrong = value <= 0.0
        if not math.isfinite(value) or wrong:
            return _invalid(f"{given.kind}:{end}", f"{unit}: {end} {given.kind} = {value!r}")
    # S5
    feed = _feed_total(spec)
    for end in spec.ends():
        given = _specification(spec, end)
        if given.kind in ("distillate_rate", "bottoms_rate") and given.value >= feed:
            return CascadeFailure(
                "INVALID_SPECIFICATION",
                f"infeasible_spec({given.kind}_exceeds_feed)",
                f"{unit}: {given.kind} {given.value!r} mol/s >= F = {feed!r} mol/s",
            )
    # S6
    with_condenser, with_reboiler = spec.condenser != "none", spec.reboiler != "none"
    if (spec.top is not None) == with_condenser:
        return _invalid(
            "top_inlet",
            f"{unit}: a column {'with' if with_condenser else 'without'} a condenser "
            f"{'has no' if with_condenser else 'needs a'} top inlet",
        )
    if (spec.bottom is not None) == with_reboiler:
        return _invalid(
            "bottom_inlet",
            f"{unit}: a column {'with' if with_reboiler else 'without'} a reboiler "
            f"{'has no' if with_reboiler else 'needs a'} bottom inlet",
        )
    # S7
    ends = spec.slot_stages()
    for side in spec.sides:
        if side.stage in ends:
            return _invalid(
                f"side_feed_stage:{side.port}",
                f"{unit}: side feed {side.port} at the {ends[side.stage]} stage {side.stage}",
            )
    # S8
    if count < 1 + int(with_condenser) + int(with_reboiler):
        return _invalid(
            "stage_count", f"{unit}: N = {count} cannot hold a condenser and a reboiler apart"
        )
    misplaced = [
        stage
        for stage, duty in enumerate(spec.duties, start=1)
        if (duty is None) != (stage in ends)
    ]
    if misplaced:
        raise ValueError(
            f"{unit}: Q_j* must be None exactly at the column-specification stages "
            f"{sorted(ends)}; stages {misplaced} disagree"
        )
    # S9
    for stage in range(1, count):
        if spec.pressures[stage] < spec.pressures[stage - 1]:
            return _invalid(
                "pressure_profile",
                f"{unit}: P_{stage + 1}* = {spec.pressures[stage]!r} Pa < "
                f"P_{stage}* = {spec.pressures[stage - 1]!r} Pa",
            )
    # S10
    if spec.ends() and feed == 0.0:
        return _invalid("no_feed", f"{unit}: a column with a condenser or reboiler and no feed")
    # S10-C §4.8: the kinds a composition-dependent form admits, decided before I1, so that
    # `stage_band` and `saturation_temperature` (SYN-001's closed forms) are never reached for it
    if form is not None and form.composition_dependent:
        for end in spec.ends():
            kind = _specification(spec, end).kind
            if kind not in GAMMA_PHI_KINDS:
                return CascadeFailure(
                    "CAPABILITY_UNAVAILABLE",
                    f"unsupported(column_specification:{kind}:{form.provider_id})",
                    f"{unit}: a {kind!r} {end} specification is not offered for "
                    f"{form.provider_id}; a column on it admits {GAMMA_PHI_KINDS} "
                    "(S10-C §4.8, ADR 0049 D7)",
                )
    return _inverse_refusal(spec)


def _inverse_refusal(spec: ColumnSpec) -> CascadeFailure | None:
    """S06 §5 I1–I6, in that order, on a specification that passed S1–S10. Each rule is applied
    to the condenser end, then the reboiler end, before the next rule."""
    unit, count, components = spec.unit_id, spec.stage_count, spec.components
    given = {end: _specification(spec, end) for end in spec.ends()}
    # I1: the attribute
    for end, found in given.items():
        if found.kind == "temperature":
            stage = found.stage
            wrong = (
                found.component is not None
                or isinstance(stage, bool)
                or not isinstance(stage, int)
                or not 1 <= stage <= count
            )
        elif found.kind in COMPONENT_KINDS:
            wrong = found.stage is not None or found.component not in components
        else:
            wrong = found.component is not None or found.stage is not None
        if wrong:
            return _invalid(
                f"{found.kind}:{end}",
                f"{unit}: {end} {found.kind} with component {found.component!r} and stage "
                f"{found.stage!r} (N = {count}, components {components})",
            )
    # I2: the value
    for end, found in given.items():
        if found.kind not in INVERSE_KINDS:
            continue
        value = found.value
        if not math.isfinite(value) or (found.kind in COMPONENT_KINDS and not 0.0 < value < 1.0):
            return _invalid(f"{found.kind}:{end}", f"{unit}: {end} {found.kind} = {value!r}")
    feeds = component_feeds(spec)
    # I3: an absent component
    for end, found in given.items():
        if found.kind in COMPONENT_KINDS:
            assert found.component is not None
            if feeds[components.index(found.component)] == 0.0:
                return CascadeFailure(
                    "INVALID_SPECIFICATION",
                    f"infeasible_spec(absent_component:{end})",
                    f"{unit}: {end} {found.kind} of {found.component}, which no inlet carries",
                )
    # I4: the stage band (§4)
    for found in given.values():
        if found.kind == "temperature":
            assert found.stage is not None
            low, high = stage_band(spec, found.stage)
            if not low < found.value < high:
                return CascadeFailure(
                    "INVALID_SPECIFICATION",
                    f"infeasible_spec(temperature_outside_band:{found.stage})",
                    f"{unit}: T_{found.stage}* = {found.value!r} K outside the open band "
                    f"({low!r}, {high!r}) K at P_{found.stage}*",
                )
    # I5: redundant specifications
    stages = [found.stage for found in given.values() if found.kind == "temperature"]
    totals = [Fraction(feed) for feed in feeds]
    rows, rhs = _split_rows(spec, totals)
    if len(stages) != len(set(stages)) or (rows and _rank(rows) < len(rows)):
        return _invalid(
            "redundant_specification",
            f"{unit}: two temperatures name one stage, or the specifications linear in the "
            "product split are linearly dependent (S06 §5 I5)",
        )
    # I6: no product split
    if rows and not _split_feasible(totals, rows, rhs):
        return CascadeFailure(
            "INVALID_SPECIFICATION",
            "infeasible_spec(mass_balance)",
            f"{unit}: no top product with 0 < t_c < F_c for every present c meets the "
            "specifications linear in it (S06 §5 I6)",
        )
    return None


def _split_rows(
    spec: ColumnSpec, totals: list[Fraction]
) -> tuple[list[list[Fraction]], list[Fraction]]:
    """S06 §5's table: the end specifications linear in the top product `t`, as rows `a·t = b`,
    exact on the binary64 inputs. Ratios, duties and temperatures give none."""
    feed = sum(totals, Fraction(0))
    rows: list[list[Fraction]] = []
    rhs: list[Fraction] = []
    for end in spec.ends():
        found = _specification(spec, end)
        value = Fraction(found.value)
        if found.kind == "distillate_rate":
            rows.append([Fraction(1)] * len(totals))
            rhs.append(value)
        elif found.kind == "bottoms_rate":
            rows.append([Fraction(1)] * len(totals))
            rhs.append(feed - value)
        elif found.kind in COMPONENT_KINDS:
            assert found.component is not None
            k = spec.components.index(found.component)
            unit_vector = [Fraction(int(i == k)) for i in range(len(totals))]
            if found.kind == "recovery":
                rows.append(unit_vector)
                rhs.append((value if end == CONDENSER else 1 - value) * totals[k])
            elif end == CONDENSER:
                rows.append([e - value for e in unit_vector])
                rhs.append(Fraction(0))
            else:
                rows.append([value - e for e in unit_vector])
                rhs.append(value * feed - totals[k])
    return rows, rhs


def _reduce(
    rows: list[list[Fraction]], rhs: list[Fraction], n: int
) -> tuple[list[Fraction] | None, list[list[Fraction]]]:
    """Gauss–Jordan in exact arithmetic: a particular solution `t⁰` of `rows·t = rhs` (`None`
    when inconsistent) and a basis of the null space, so every solution is `t⁰ + N s`."""
    matrix = [[*row, b] for row, b in zip(rows, rhs, strict=True)]
    pivots: list[int] = []
    r = 0
    for col in range(n):
        found = next((i for i in range(r, len(matrix)) if matrix[i][col] != 0), None)
        if found is None:
            continue
        matrix[r], matrix[found] = matrix[found], matrix[r]
        pivot = matrix[r][col]
        matrix[r] = [entry / pivot for entry in matrix[r]]
        for i in range(len(matrix)):
            if i != r and matrix[i][col] != 0:
                factor = matrix[i][col]
                matrix[i] = [a - factor * b for a, b in zip(matrix[i], matrix[r], strict=True)]
        pivots.append(col)
        r += 1
    if any(row[n] != 0 for row in matrix[r:]):
        return None, []
    particular = [Fraction(0)] * n
    for i, col in enumerate(pivots):
        particular[col] = matrix[i][n]
    basis: list[list[Fraction]] = []
    for free in (col for col in range(n) if col not in pivots):
        vector = [Fraction(0)] * n
        vector[free] = Fraction(1)
        for i, col in enumerate(pivots):
            vector[col] = -matrix[i][free]
        basis.append(vector)
    return particular, basis


def _rank(rows: list[list[Fraction]]) -> int:
    """The rank of `rows` over every component (S06 §5 I5)."""
    n = len(rows[0])
    _, basis = _reduce(rows, [Fraction(0)] * len(rows), n)
    return n - len(basis)


def _split_feasible(
    totals: list[Fraction], rows: list[list[Fraction]], rhs: list[Fraction]
) -> bool:
    """S06 §5 I6: is there a `t` with `0 < t_c < F_c` for every present c (`t_c = 0` for an
    absent one) meeting `rows·t = rhs`? Decided exactly: with no free direction test the point;
    with one intersect the open intervals per coordinate; with one row test
    `Σ min(0, a_c F_c) < b < Σ max(0, a_c F_c)`."""
    present = [c for c, total in enumerate(totals) if total > 0]
    box = [totals[c] for c in present]
    reduced = [[row[c] for c in present] for row in rows]
    particular, basis = _reduce(reduced, rhs, len(present))
    if particular is None:
        return False
    if not basis:
        return all(0 < t < high for t, high in zip(particular, box, strict=True))
    if len(basis) == 1:
        (direction,) = basis
        low: Fraction | None = None
        high: Fraction | None = None
        for t, d, upper in zip(particular, direction, box, strict=True):
            if d == 0:
                if not 0 < t < upper:
                    return False
                continue
            a, b = sorted(((0 - t) / d, (upper - t) / d))
            low = a if low is None else max(low, a)
            high = b if high is None else min(high, b)
        return low is None or high is None or low < high
    if len(reduced) == 1:
        (row,) = reduced
        lower = sum((min(Fraction(0), a * f) for a, f in zip(row, box, strict=True)), Fraction(0))
        upper = sum((max(Fraction(0), a * f) for a, f in zip(row, box, strict=True)), Fraction(0))
        return lower < rhs[0] < upper
    # Two independent rows and two or more free directions: four or more present components,
    # which SYN-001 (three) cannot declare. Not decided here rather than guessed.
    raise ValueError(
        f"S06 §5 I6 is decided for at most three present components; {len(present)} given"
    )


def energy_precheck(
    spec: ColumnSpec, provider: PropertyProvider, context: EvaluationContext
) -> EnergyPrecheck:
    """S01 §5 R7 on a column whose every slot is a duty, W, with
    `H* = H_in + Σ_j Q_j*` over every stage's duty, the ends' included, and the bounds
    `Σ_i F_i h_i^L(T_min, P_N*)`, `Σ_i F_i h_i^V(T_max)`. For a composition-dependent form
    `T_min`, `T_max` are the provider's declared domain and the enthalpies are mixture flows
    `n_tot h` (`_enthalpy_flow` dispatches; S10-C §4.8)."""
    components, inlets = spec.components, spec.inlets()
    (t_min, t_max), _ = _domain(equilibrium_form(provider))
    totals = [sum(inlet.state.n[i] for inlet in inlets) for i in range(len(components))]
    h_in = sum(
        _enthalpy_flow(
            provider,
            context,
            components,
            inlet.state.n,
            inlet.state.temperature,
            inlet.state.pressure,
            _phase(inlet.state),
        )
        for inlet in inlets
    )
    duties = [duty for duty in spec.duties if duty is not None]
    duties.extend(_specification(spec, end).value for end in spec.ends())
    p_bottom = spec.pressures[-1]
    return EnergyPrecheck(
        inflow=h_in,
        target=h_in + sum(duties),
        lower=_enthalpy_flow(provider, context, components, totals, t_min, p_bottom, "LIQUID"),
        upper=_enthalpy_flow(provider, context, components, totals, t_max, p_bottom, "VAPOR"),
    )
