"""ST: the stream table and energy summary of a run, computed on read (ADR 0068).

`build` derives the `stream-table-v1` document from a run bundle's four members (the revision,
the solution state, the certificate and the run manifest) and a fresh provider of the revision's
basis; `from_bundle` reads those members from a bundle directory and resolves the provider. The
document is a report: it enters no identity, writes nothing, and holds no state between calls
(design note `docs/design/ST-stream-table.md` C-1, C-8).

Every per-stream value follows the note's §4: the phase rule `st-phase-rule-v1` (§4.2; foundation
rulings Q1.R11, Q1.R12, Q4.R11, Q4.R12), the property calls and formulas (§4.3; Q2.R11, Q4.R10),
the quoted checks (§4.4) and the energy summary at the stored state (§4.5). Where the report and
the verifier decide the same phases, the provider calls and the arithmetic are the verifier's, in
its order, so the enthalpy flows agree bitwise (D3). A value that cannot be given is `null` with a
typed reason in its object's `absent` map, and a quantity is `null` iff it has such an entry (D6).
"""

from __future__ import annotations

import json
import math
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from openflowsheet import __version__
from openflowsheet.compiled import EvaluationContext
from openflowsheet.models import duty_id, flow_id, pressure_id, temperature_id
from openflowsheet.models.revision_flowsheet import (
    InstanceView,
    RevisionError,
    RevisionView,
    component_basis,
    parse_revision,
)
from openflowsheet.models.syn001.pump import work_id
from openflowsheet.models.thermal.state import liquid_id, vapor_id
from openflowsheet.thermo import (
    FlashRequest,
    Phase,
    PropertyProvider,
    PropertyRequest,
    StreamState,
)
from openflowsheet.verify import column
from openflowsheet.verify.table import (
    EXTERNAL_DUTY_MODELS,
    FEED_MODELS,
    PRODUCT_MODELS,
    STAGED_DUTY_MODELS,
    WORK_MODELS,
)

SCHEMA_VERSION: Final = "stream-table-v1"
#: §4.2's phase rule, named in every document's header.
PHASE_RULE: Final = "st-phase-rule-v1"
#: v1 has one substream per stream (§4.2).
SUBSTREAM: Final = "mixed"
#: Q4.R12 (b) (i): a flashed substream with a listed minority fraction at or below this is
#: flagged `flash_near_phase_boundary`.
TAU_BETA: Final = 1e-8
#: Q4.R12 (b) (ii): the `independent_split` reasons for which the verifier could not recompute the
#: stream by a fresh flash.
DEGENERATE_REASONS: Final = frozenset({"temperature_degenerate", "fresh_flash_unresolved"})
#: The registered family order phases are listed in (Q4.R11 (a)).
FAMILY_ORDER: Final = ("VAPOR", "LIQUID", "FLUID", "SOLID")
#: Q4.R10 (a): the vapour group of v1.
VAPOUR_GROUP: Final = frozenset({"VAPOR"})
#: The certificate categories quoted on a stream (§4.4).
STREAM_CATEGORIES: Final = frozenset({"phase_admissibility", "independent_split"})
ENVELOPE_ROW: Final = "energy_balance.envelope"
#: The seven codes an `absent` entry may carry (§6.4).
CODES: Final = frozenset(
    {
        "zero_flow",
        "property_not_provided",
        "property_evaluation_failed",
        "flash_failed",
        "value_not_finite",
        "stream_enthalpy_absent",
        "energy_balance_undefined",
    }
)
#: The bundle members `build` reads (§4.1), in the order `from_bundle` looks for them.
MANIFEST: Final = "run-manifest.json"
ARTIFACTS: Final = ("revision.json", "solution-state.json", "solution-certificate.json")


# -- absence (D6) ---------------------------------------------------------------------------------


@dataclass(frozen=True)
class Absent:
    """A quantity that cannot be given: the typed reason its object's `absent` map carries."""

    code: str
    params: Mapping[str, Any]

    def entry(self) -> dict[str, Any]:
        return {"code": self.code, "params": dict(self.params)}


def absent(code: str, **params: Any) -> Absent:
    assert code in CODES, code
    return Absent(code, params)


#: A reported quantity: a number, or why it is absent.
Quantity = float | Absent


def _first_absent(*quantities: Quantity) -> Absent | None:
    for quantity in quantities:
        if isinstance(quantity, Absent):
            return quantity
    return None


def _finite(value: float, subject: str, name: str) -> Quantity:
    return (
        value
        if math.isfinite(value)
        else absent("value_not_finite", subject=subject, quantity=name)
    )


def _quotient(numerator: Quantity, denominator: Quantity, subject: str, name: str) -> Quantity:
    """An IEEE-754 quotient (Q4.R11 (c)): a non-finite result is `value_not_finite`, never a raise.
    An absent input's reason is copied (D6)."""
    missing = _first_absent(numerator, denominator)
    if missing is not None:
        return missing
    assert isinstance(numerator, float) and isinstance(denominator, float)
    try:
        value = numerator / denominator
    except (ZeroDivisionError, OverflowError):
        value = math.nan
    return _finite(value, subject, name)


def _product(left: Quantity, right: Quantity, subject: str, name: str) -> Quantity:
    missing = _first_absent(left, right)
    if missing is not None:
        return missing
    assert isinstance(left, float) and isinstance(right, float)
    return _finite(left * right, subject, name)


def _total(terms: Iterable[Quantity], subject: str, name: str) -> Quantity:
    """`Σ terms` accumulated from 0.0 in order; the first absent term's reason otherwise."""
    total = 0.0
    for term in terms:
        if isinstance(term, Absent):
            return term
        total += term
    return _finite(total, subject, name)


def _array(values: Sequence[Quantity]) -> list[float] | Absent:
    """An array is given whole or is absent whole (§5): the first absent element's reason."""
    missing = _first_absent(*values)
    if missing is not None:
        return missing
    return [value for value in values if isinstance(value, float)]


class _Record:
    """One document object's members and its `absent` map, kept in step: a member is `None` iff
    it has an entry."""

    def __init__(self, **members: Any) -> None:
        self.members: dict[str, Any] = dict(members)
        self.missing: dict[str, dict[str, Any]] = {}

    def put(self, name: str, value: Quantity | list[float] | Absent) -> None:
        if isinstance(value, Absent):
            self.members[name] = None
            self.missing[name] = value.entry()
        else:
            self.members[name] = value

    def document(self) -> dict[str, Any]:
        return {**self.members, "absent": self.missing}


# -- inputs (§4.1) --------------------------------------------------------------------------------


@dataclass(frozen=True)
class _Inputs:
    view: RevisionView
    state: Mapping[str, float]
    certificate: Mapping[str, Any]
    provider: PropertyProvider
    context: EvaluationContext
    provider_id: str
    #: Provider order: every provider call and every accumulation.
    components: tuple[str, ...]
    #: Declared order: every output array, filled by component id.
    declared: tuple[str, ...]
    molar_mass: Mapping[str, float]
    declared_phase: Mapping[str, Phase | None]
    #: The certificate's rows with their `checks` index.
    rows: tuple[tuple[int, Mapping[str, Any]], ...]
    #: Instance id -> the unit id its state variables and certificate rows carry.
    unit_ids: Mapping[str, str]


class StreamTableError(Exception):
    """A bundle the report cannot be derived from. `code` is an existing `ApiError` code
    (`not_found`, `unsupported`, `internal_error`; note §6.1) and `detail` its typed detail."""

    def __init__(self, code: str, message: str, **detail: Any) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.detail = detail


def _declared_phases(view: RevisionView) -> dict[str, Phase | None]:
    """Each stream's phase as its producer's outlet port declares it, `None` otherwise:
    `verify.forms.declared_phases`' rule (note §4.1)."""
    phases: dict[str, Phase | None] = dict.fromkeys(view.streams)
    for instance in view.instances:
        for port, streams in instance.ports.items():
            if instance.directions.get(port) != "outlet":
                continue
            for stream in streams:
                phases[stream] = instance.phases.get(port)
    return phases


def _inputs(
    revision: Mapping[str, Any],
    state_doc: Mapping[str, Any],
    certificate: Mapping[str, Any],
    provider: PropertyProvider,
) -> _Inputs:
    from openflowsheet.run.solution_state import inconsistencies  # noqa: PLC0415

    # The report reads no pin, so the revision is read without its specifications, as the legacy
    # binder reads it (`application.binding`): a `free` or `guess` specification of a legacy-route
    # revision is not refused, and nothing the report reads depends on one.
    try:
        view = parse_revision({**revision, "specifications": []})
        basis = component_basis(revision)
    except RevisionError as error:
        raise StreamTableError(
            "internal_error", f"the bundle's revision does not parse: {error.code}"
        ) from error
    reasons = inconsistencies(state_doc, certificate)
    if reasons:
        raise StreamTableError(
            "internal_error",
            "the bundle's solution state and certificate are inconsistent",
            reasons=list(reasons),
        )
    checks = certificate.get("checks", [])
    return _Inputs(
        view=view,
        state={name: float(value) for name, value in state_doc["variables"].items()},
        certificate=certificate,
        provider=provider,
        context=EvaluationContext(
            model_version=certificate["model_version"],
            constants_sha256=certificate["constants_sha256"],
            phase_signature=None,
        ),
        provider_id=provider.describe().provider_id,
        components=view.components,
        declared=view.input_mapping.declared_components or view.components,
        molar_mass={c: float(basis.molecular_weights[c]) for c in view.components},
        declared_phase=_declared_phases(view),
        rows=tuple(enumerate(checks)),
        unit_ids=_unit_ids(revision, view),
    )


def _unit_ids(revision: Mapping[str, Any], view: RevisionView) -> dict[str, str]:
    """Each instance's id in the state and the certificate.

    On the revision route an instance names its own variables and rows. A revision with a
    specification that is not `fixed` can only have been solved on `legacy_eo`, whose state and
    certificate name the units of the SYN-001 flowsheet (`U-HEAT`); each is the instance the
    legacy binder matched to it by stream topology (`application.binding`), read back from that
    binder's own match. Stream ids are the revision's on both routes.
    """
    own = {instance.unit_id: instance.unit_id for instance in view.instances}
    if all(entry.get("role") == "fixed" for entry in revision.get("specifications") or ()):
        return own
    from openflowsheet.application.binding import bind_revision  # noqa: PLC0415

    binding = bind_revision(revision)
    if binding is None:
        raise StreamTableError(
            "internal_error", "a legacy-route revision no longer binds on the legacy binder"
        )
    legacy = {instance: unit for unit, instance in binding.graph.instance_ids.items()}
    return {instance: legacy.get(instance, instance) for instance in own}


def _quote(index: int, row: Mapping[str, Any]) -> dict[str, Any]:
    """§4.4: a certificate row, quoted verbatim, with its position in `checks`."""
    return {
        "index": index,
        "id": row["id"],
        "result": row["result"],
        "scope": row["scope"],
        "value": row.get("value"),
        "tolerance": row.get("tolerance"),
        "reason": row.get("reason", ""),
        "near_threshold": bool(row.get("near_threshold", False)),
    }


def _quotes(inputs: _Inputs, keep: Callable[[Mapping[str, Any]], bool]) -> list[dict[str, Any]]:
    return [_quote(index, row) for index, row in inputs.rows if keep(row)]


# -- the phases of one substream (§4.2, §4.3) -----------------------------------------------------


@dataclass(frozen=True)
class _Listed:
    """One listed phase: its family, its amounts in provider order and the state its properties
    are requested at."""

    family: Phase
    n: tuple[float, ...]
    evaluated_at: StreamState


@dataclass(frozen=True)
class _Decision:
    source: str
    phases: tuple[_Listed, ...]
    #: Why every property-derived quantity is absent (a failed flash or `Tsat`), else `None`.
    blocked: Absent | None = None
    #: Why the phase list itself is undecided (a failed flash), else `None`.
    undecided: Absent | None = None
    near_boundary: bool = False


def _listed(family: Phase, n: tuple[float, ...], at: StreamState) -> tuple[_Listed, ...]:
    """Q4.R11 (a): listed iff the amount is `!= 0.0`, of either sign, never clamped."""
    return (_Listed(family, n, at),) if sum(n) != 0.0 else ()


def _carried_split(inputs: _Inputs, name: str, st: StreamState) -> _Decision:
    """R1 (Q1.R12): both phases at `(T_sat(P), P)`, `T_sat` the verifier's."""
    if len(inputs.components) != 1:
        raise StreamTableError(
            "internal_error",
            f"stream {name} carries a saturated split over {len(inputs.components)} components",
        )
    provider, pressure = inputs.provider, st.pressure
    t_lo = float(provider.describe().domain["T"][0])
    result = provider.evaluate_phase(
        PropertyRequest(StreamState((1.0,), t_lo, pressure), "LIQUID", ("Tsat",)), inputs.context
    )
    blocked: Absent | None = None
    t_sat = math.nan
    if result.status != "ok":
        blocked = absent(
            "property_evaluation_failed",
            stream=name,
            phase="LIQUID",
            property="Tsat",
            status=str(result.status),
        )
    else:
        t_sat = float(result.values["Tsat"])
        if not math.isfinite(t_sat):
            blocked = absent("value_not_finite", subject=name, quantity="Tsat")
    at = StreamState((1.0,), t_sat, pressure)
    vapor, liquid = inputs.state[vapor_id(name)], inputs.state[liquid_id(name)]
    phases = (*_listed("VAPOR", (vapor,), at), *_listed("LIQUID", (liquid,), at))
    return _Decision("carried_split", phases, blocked=blocked)


def _flash(inputs: _Inputs, name: str, st: StreamState) -> _Decision:
    """R3 (Q4.R12): one TP flash at the stream's own `(n, T, P)`, no snap."""
    result = inputs.provider.flash(FlashRequest(state=st), inputs.context)
    if result.status != "ok":
        reason = absent("flash_failed", stream=name, status=str(result.status))
        return _Decision("flash", (), blocked=reason, undecided=reason)
    outlets: tuple[tuple[Phase, StreamState | None], ...] = (
        ("VAPOR", result.vapor),
        ("LIQUID", result.liquid),
    )
    phases: list[_Listed] = []
    for family, outlet in outlets:
        if outlet is not None:
            at = StreamState(outlet.n, st.temperature, st.pressure)
            phases += _listed(family, tuple(outlet.n), at)
    return _Decision("flash", tuple(phases), near_boundary=_near_boundary(inputs, name, phases))


def _near_boundary(inputs: _Inputs, name: str, phases: Sequence[_Listed]) -> bool:
    """Q4.R12 (b): (i) a listed minority fraction `≤ τ_β`, or (ii) a verifier `independent_split`
    row `not_applicable` for degeneracy or an unresolved fresh flash. A minority fraction whose
    quotient is not finite is flagged: the decision near it is not known to agree."""
    if len(phases) >= 2:
        amounts = [sum(phase.n) for phase in phases]
        total = 0.0
        for amount in amounts:
            total += amount
        fraction = _quotient(min(abs(a) for a in amounts), total, name, "minority_fraction")
        if isinstance(fraction, Absent) or fraction <= TAU_BETA:
            return True
    return any(
        row.get("category") == "independent_split"
        and row.get("subject") == name
        and row.get("result") == "not_applicable"
        and row.get("reason") in DEGENERATE_REASONS
        for _, row in inputs.rows
    )


def _decide(inputs: _Inputs, name: str, st: StreamState) -> _Decision:
    """§4.2's rule, in its order: R0 is decided by the caller, then R1, R2, R3."""
    if vapor_id(name) in inputs.state and liquid_id(name) in inputs.state:
        return _carried_split(inputs, name, st)
    family = inputs.declared_phase.get(name)
    if family is not None:
        return _Decision("declared", _listed(family, st.n, st))
    return _flash(inputs, name, st)


@dataclass(frozen=True)
class _PhaseValues:
    """One listed phase's extensive values, kept for the substream's sums."""

    family: Phase
    n_total: float
    m_total: float
    enthalpy: Quantity
    entropy: Quantity
    volume: Quantity


class _Properties:
    """§4.3's provider calls for one phase: `h` alone, then `s` and `v` each alone when declared."""

    def __init__(self, inputs: _Inputs, name: str) -> None:
        self.inputs = inputs
        self.name = name
        self.declared = set(inputs.provider.describe().properties)

    def _call(self, phase: _Listed, prop: str) -> Mapping[str, float] | Absent:
        result = self.inputs.provider.evaluate_phase(
            PropertyRequest(phase.evaluated_at, phase.family, (prop,)), self.inputs.context
        )
        if result.status != "ok":
            return absent(
                "property_evaluation_failed",
                stream=self.name,
                phase=phase.family,
                property=prop,
                status=str(result.status),
            )
        return result.values

    def enthalpy_flow(self, phase: _Listed, n_total: float) -> Quantity:
        """`H_p`: `n_p,tot·h` (mixture form), else `Σ_c n_p,c h_c` (SYN-001's form), summed as the
        verifier's `checks.enthalpy_flow` sums it (Python `sum`, provider order)."""
        values = self._call(phase, "h")
        if isinstance(values, Absent):
            return values
        if "h" in values:
            return _product(n_total, float(values["h"]), self.name, "H_flow")
        keys = [f"h_{c}" for c in self.inputs.components]
        if not all(key in values for key in keys):
            return absent("property_not_provided", provider=self.inputs.provider_id, property="h")
        per_component = [float(values[key]) for key in keys]
        if not all(math.isfinite(value) for value in per_component):
            return absent("value_not_finite", subject=self.name, quantity="h")
        flow = sum(n * h for n, h in zip(phase.n, per_component, strict=True))
        return _finite(flow, self.name, "H_flow")

    def mixture(self, phase: _Listed, prop: str) -> Quantity:
        """`s` or `v`: the mixture key only (Q2.R11 (b)); a per-component key is not summed."""
        if prop not in self.declared:
            return absent("property_not_provided", provider=self.inputs.provider_id, property=prop)
        values = self._call(phase, prop)
        if isinstance(values, Absent):
            return values
        if prop not in values:
            return absent("property_not_provided", provider=self.inputs.provider_id, property=prop)
        return _finite(float(values[prop]), self.name, prop)


def _mass(inputs: _Inputs, n: Sequence[float]) -> tuple[list[float], float]:
    """`m_c = M_c n_c` and `m_tot = Σ_c m_c` from 0.0, provider order."""
    masses = [inputs.molar_mass[c] * flow for c, flow in zip(inputs.components, n, strict=True)]
    total = 0.0
    for mass in masses:
        total += mass
    return masses, total


def _by_id(inputs: _Inputs, values: Sequence[Quantity]) -> list[Quantity]:
    """Provider-order values in the declared order, by component id (§4.1)."""
    keyed = dict(zip(inputs.components, values, strict=True))
    return [keyed[c] for c in inputs.declared]


def _fractions(
    inputs: _Inputs, values: Sequence[float], total: float, name: str, quantity: str
) -> list[float] | Absent:
    return _array(_by_id(inputs, [_quotient(v, total, name, quantity) for v in values]))


def _phase(
    inputs: _Inputs,
    name: str,
    phase: _Listed,
    decision: _Decision,
    properties: _Properties,
) -> tuple[_Record, _PhaseValues]:
    n_total = sum(phase.n)
    masses, m_total = _mass(inputs, phase.n)
    record = _Record(id={"family": phase.family, "qualifier": None, "ordinal": 1})
    record.put("n", [v + 0.0 for v in _by_id(inputs, phase.n) if isinstance(v, float)])
    record.put("m", [v + 0.0 for v in _by_id(inputs, masses) if isinstance(v, float)])
    record.put("x", _fractions(inputs, phase.n, n_total, name, "x"))
    record.put("w", _fractions(inputs, masses, m_total, name, "w"))
    record.put("n_total", n_total)
    record.put("m_total", m_total)
    if decision.blocked is not None:
        enthalpy: Quantity = decision.blocked
        entropy: Quantity = decision.blocked
        volume: Quantity = decision.blocked
        s_value: Quantity = decision.blocked
        v_value: Quantity = decision.blocked
    else:
        enthalpy = properties.enthalpy_flow(phase, n_total)
        s_value = properties.mixture(phase, "s")
        v_value = properties.mixture(phase, "v")
        entropy = _product(n_total, s_value, name, "S_flow")
        volume = _product(n_total, v_value, name, "V_flow")
    record.put("H_flow", enthalpy)
    record.put("S_flow", entropy)
    record.put("V_flow", volume)
    record.put("h", _quotient(enthalpy, n_total, name, "h"))
    record.put("h_mass", _quotient(enthalpy, m_total, name, "h_mass"))
    record.put("s", s_value)
    record.put("s_mass", _quotient(entropy, m_total, name, "s_mass"))
    record.put("v", v_value)
    record.put("rho", _quotient(m_total, volume, name, "rho"))
    return record, _PhaseValues(phase.family, n_total, m_total, enthalpy, entropy, volume)


# -- one stream -----------------------------------------------------------------------------------


def _dormant_substream(inputs: _Inputs, name: str, st: StreamState) -> _Record:
    """R0 (Q1.R11): no provider call; every amount and extensive exactly `+0.0`."""
    zero_flow = absent("zero_flow", stream=name)
    masses, _ = _mass(inputs, st.n)
    record = _substream_header(inputs, "zero_flow", near_boundary=False)
    record.put("n", [v + 0.0 for v in _by_id(inputs, st.n) if isinstance(v, float)])
    record.put("m", [v + 0.0 for v in _by_id(inputs, masses) if isinstance(v, float)])
    for member in ("n_total", "m_total", "H_flow", "S_flow", "V_flow"):
        record.put(member, 0.0)
    for member in ("x", "w", "h", "h_mass", "s", "s_mass", "rho"):
        record.put(member, zero_flow)
    record.put("vapor_fraction_molar", zero_flow)
    record.put("vapor_fraction_mass", zero_flow)
    record.members["phases"] = []
    return record


def _substream_header(inputs: _Inputs, source: str, *, near_boundary: bool) -> _Record:
    return _Record(
        id=SUBSTREAM,
        kind=SUBSTREAM,
        components=list(inputs.declared),
        convention=inputs.provider.describe().reference_convention,
        phase_source=source,
        flash_near_phase_boundary=near_boundary,
    )


def _flowing_substream(inputs: _Inputs, name: str, st: StreamState) -> tuple[_Record, Quantity]:
    decision = _decide(inputs, name, st)
    properties = _Properties(inputs, name)
    phases = [_phase(inputs, name, phase, decision, properties) for phase in decision.phases]
    values = [value for _, value in phases]

    n_listed, m_listed, n_vapour, m_vapour = 0.0, 0.0, 0.0, 0.0
    for value in values:
        n_listed += value.n_total
        m_listed += value.m_total
    for value in values:
        if value.family in VAPOUR_GROUP:
            n_vapour += value.n_total
            m_vapour += value.m_total
    for record, value in phases:
        record.put(
            "phase_fraction_molar", _quotient(value.n_total, n_listed, name, "phase_fraction_molar")
        )
        record.put(
            "phase_fraction_mass", _quotient(value.m_total, m_listed, name, "phase_fraction_mass")
        )

    n_total = sum(st.n)
    masses, m_total = _mass(inputs, st.n)
    record = _substream_header(inputs, decision.source, near_boundary=decision.near_boundary)
    record.put("n", [v + 0.0 for v in _by_id(inputs, st.n) if isinstance(v, float)])
    record.put("m", [v + 0.0 for v in _by_id(inputs, masses) if isinstance(v, float)])
    record.put("x", _fractions(inputs, st.n, n_total, name, "x"))
    record.put("w", _fractions(inputs, masses, m_total, name, "w"))
    record.put("n_total", n_total)
    record.put("m_total", m_total)

    blocked = decision.undecided
    enthalpy = blocked or _total((v.enthalpy for v in values), name, "H_flow")
    entropy = blocked or _total((v.entropy for v in values), name, "S_flow")
    volume = blocked or _total((v.volume for v in values), name, "V_flow")
    record.put("H_flow", enthalpy)
    record.put("S_flow", entropy)
    record.put("V_flow", volume)
    record.put("h", _quotient(enthalpy, n_total, name, "h"))
    record.put("h_mass", _quotient(enthalpy, m_total, name, "h_mass"))
    record.put("s", _quotient(entropy, n_total, name, "s"))
    record.put("s_mass", _quotient(entropy, m_total, name, "s_mass"))
    record.put("rho", _quotient(m_total, volume, name, "rho"))
    record.put(
        "vapor_fraction_molar",
        blocked or _quotient(n_vapour, n_listed, name, "vapor_fraction_molar"),
    )
    record.put(
        "vapor_fraction_mass",
        blocked or _quotient(m_vapour, m_listed, name, "vapor_fraction_mass"),
    )
    record.members["phases"] = [phase.document() for phase, _ in phases]
    return record, enthalpy


def _stream(
    inputs: _Inputs, name: str, ends: tuple[str | None, str | None]
) -> tuple[dict[str, Any], Quantity]:
    state = inputs.state
    st = StreamState(
        n=tuple(state[flow_id(name, c)] for c in inputs.components),
        temperature=state[temperature_id(name)],
        pressure=state[pressure_id(name)],
    )
    record = _Record(id=name, **{"from": ends[0], "to": ends[1]})
    if st.is_dormant:
        substream = _dormant_substream(inputs, name, st)
        enthalpy: Quantity = 0.0
        record.put("T", absent("zero_flow", stream=name))
    else:
        substream, enthalpy = _flowing_substream(inputs, name, st)
        record.put("T", st.temperature)
    record.put("P", st.pressure)
    record.members["dormant"] = st.is_dormant
    record.members["substreams"] = [substream.document()]
    record.members["checks"] = _quotes(
        inputs, lambda row: row.get("category") in STREAM_CATEGORIES and row.get("subject") == name
    )
    return record.document(), enthalpy


# -- the energy summary (§4.5) --------------------------------------------------------------------


def _feeds(view: RevisionView) -> list[str]:
    """The outlet streams of feed instances: `verify.table._feeds`' order."""
    return [
        stream
        for instance in view.instances
        if instance.model_id in FEED_MODELS
        for port, direction in instance.directions.items()
        if direction == "outlet"
        for stream in instance.ports[port]
    ]


def _products(view: RevisionView) -> list[str]:
    """The inlet streams of product instances: `verify.table._products`' order."""
    return [
        stream
        for instance in view.instances
        if instance.model_id in PRODUCT_MODELS
        for port, direction in instance.directions.items()
        if direction == "inlet"
        for stream in instance.ports[port]
    ]


def _duty(inputs: _Inputs, instance: InstanceView) -> float:
    if instance.model_id in EXTERNAL_DUTY_MODELS:
        return inputs.state[duty_id(inputs.unit_ids[instance.unit_id])]
    if instance.model_id in STAGED_DUTY_MODELS:
        return column.duty(instance, inputs.state, inputs.components)
    return 0.0


def _work(inputs: _Inputs, instance: InstanceView) -> float:
    if instance.model_id in WORK_MODELS:
        return inputs.state[work_id(inputs.unit_ids[instance.unit_id])]
    return 0.0


def _stream_sum(streams: Sequence[str], enthalpy: Mapping[str, Quantity], subject: str) -> Quantity:
    """`Σ Ḣ(S)` from 0.0 in order; `stream_enthalpy_absent` naming every absent stream."""
    missing = [stream for stream in streams if isinstance(enthalpy[stream], Absent)]
    if missing:
        return absent("stream_enthalpy_absent", subject=subject, streams=missing)
    return _total((enthalpy[stream] for stream in streams), subject, "H_flow")


def _sum_by_direction(
    ports: Sequence[tuple[str, Quantity]], direction: str, subject: str, name: str
) -> Quantity:
    return _total((value for side, value in ports if side == direction), subject, name)


def _unit(
    inputs: _Inputs, instance: InstanceView, enthalpy: Mapping[str, Quantity]
) -> dict[str, Any]:
    unit = instance.unit_id
    subject = inputs.unit_ids[unit]
    ports: list[dict[str, Any]] = []
    flows: list[tuple[str, Quantity]] = []
    for port, streams in instance.ports.items():
        direction = instance.directions[port]
        flow = _stream_sum(streams, enthalpy, unit)
        entry = _Record(port=port, direction=direction, streams=list(streams))
        entry.put("H_flow", flow)
        ports.append(entry.document())
        flows.append((direction, flow))
    duty, work = _duty(inputs, instance), _work(inputs, instance)
    quoted = _quotes(
        inputs,
        lambda row: row.get("category") == "energy_balance" and row.get("subject") == subject,
    )
    record = _Record(id=unit, model=instance.model_id, ports=ports, Q=duty, W=work, checks=quoted)
    h_in = _sum_by_direction(flows, "inlet", unit, "H_in")
    h_out = _sum_by_direction(flows, "outlet", unit, "H_out")
    record.put("H_in", h_in)
    record.put("H_out", h_out)
    if not quoted:
        record.put(
            "closure", absent("energy_balance_undefined", unit=unit, model=instance.model_id)
        )
    else:
        record.put("closure", _closure(duty, work, h_out, h_in, unit))
    return record.document()


def _closure(duty: float, work: float, out: Quantity, into: Quantity, subject: str) -> Quantity:
    """`(Q + W) − (Ḣ_out − Ḣ_in)`: the verifier's residual sign (C-5)."""
    missing = _first_absent(out, into)
    if missing is not None:
        return missing
    assert isinstance(out, float) and isinstance(into, float)
    return _finite((duty + work) - (out - into), subject, "closure")


def _overall(inputs: _Inputs, enthalpy: Mapping[str, Quantity]) -> dict[str, Any]:
    """`_envelope_energy`'s arithmetic, in its order, at the stored state."""
    view = inputs.view
    feeds, products = _feeds(view), _products(view)
    duty = 0.0
    for instance in view.instances:
        if instance.model_id in EXTERNAL_DUTY_MODELS or instance.model_id in STAGED_DUTY_MODELS:
            duty += _duty(inputs, instance)
    work = 0.0
    for instance in view.instances:
        if instance.model_id in WORK_MODELS:
            work += _work(inputs, instance)
    record = _Record(
        feeds=feeds,
        products=products,
        Q=duty,
        W=work,
        checks=_quotes(inputs, lambda row: row.get("id") == ENVELOPE_ROW),
    )
    h_products = _stream_sum(products, enthalpy, "flowsheet")
    h_feeds = _stream_sum(feeds, enthalpy, "flowsheet")
    record.put("H_feeds", h_feeds)
    record.put("H_products", h_products)
    record.put("closure", _closure(duty, work, h_products, h_feeds, "flowsheet"))
    return record.document()


# -- the document ---------------------------------------------------------------------------------


def build(
    revision: Mapping[str, Any],
    state_doc: Mapping[str, Any],
    certificate: Mapping[str, Any],
    manifest: Mapping[str, Any],
    *,
    provider: PropertyProvider,
    source: Mapping[str, str | None],
) -> dict[str, Any]:
    """The `stream-table-v1` document of one run (note §4, §5). Pure: no store, no files.

    `provider` is a fresh instance of the revision's basis (C-8); `source` carries the `job_id`
    and `bundle_id` the caller knows (`None` for a bundle directory). Raises `StreamTableError`
    (`internal_error`) when the state and certificate are inconsistent or the revision does not
    parse.
    """
    inputs = _inputs(revision, state_doc, certificate, provider)
    view = inputs.view
    described = provider.describe()
    ends = {stream: (producer, consumer) for stream, producer, consumer in view.edges}
    streams: list[dict[str, Any]] = []
    enthalpy: dict[str, Quantity] = {}
    for name in view.streams:
        document, enthalpy[name] = _stream(inputs, name, ends.get(name, (None, None)))
        streams.append(document)
    units = [
        _unit(inputs, instance, enthalpy)
        for instance in view.instances
        if instance.model_id not in FEED_MODELS and instance.model_id not in PRODUCT_MODELS
    ]
    projection = certificate.get("transformations", {}).get("projection", {})
    return {
        "schema_version": SCHEMA_VERSION,
        "source": {
            "job_id": source.get("job_id"),
            "bundle_id": source.get("bundle_id"),
            "run_id": manifest.get("run_id"),
            "revision_id": revision["revision_id"],
        },
        "state_sha256": state_doc["state_sha256"],
        "certificate_id": certificate["certificate_id"],
        "verification_status": certificate["verification_status"],
        "judged_at": projection.get("judged_at"),
        "basis": {
            "provider_id": described.provider_id,
            "implementation_sha256": described.implementation_sha256,
            "data_sha256": described.data_sha256,
            "convention": described.reference_convention,
            "record_source": view.basis.record_source,
        },
        "evaluator": {"phase_rule": PHASE_RULE, "package_version": __version__},
        "components": [{"id": c, "molar_mass": inputs.molar_mass[c]} for c in inputs.declared],
        "streams": streams,
        "energy": {
            "convention": described.reference_convention,
            "units": units,
            "overall": _overall(inputs, enthalpy),
        },
    }


def _read(directory: Path, relative: str, present: Sequence[str]) -> Any:
    path = directory / relative
    if not path.is_file():
        member = Path(relative).name
        raise StreamTableError(
            "not_found",
            f"the bundle has no {member}",
            bundle_id=None,
            member=member,
            members=list(present),
            job_id=None,
            run_outcome=None,
        )
    return json.loads(path.read_text(encoding="utf-8"))


def from_bundle(
    directory: str | Path, *, source: Mapping[str, str | None] | None = None
) -> dict[str, Any]:
    """The `stream-table-v1` document of the bundle in `directory` (note §6.2; a library helper,
    not contract). 0.3.0 bundles included. `source` is `build`'s (the `job_id` and `bundle_id`
    the caller knows); both are null when it is omitted.

    Raises `StreamTableError`: `not_found` naming the first missing member, `unsupported` when the
    revision's basis cannot be bound here (`basis_unavailable(<id>)`, its hint in `detail`), and
    `internal_error` as `build` does.
    """
    from openflowsheet.application.binding import Unbound  # noqa: PLC0415
    from openflowsheet.application.revision_binding import provider_for  # noqa: PLC0415
    from openflowsheet.run.bundle import ARTIFACT_DIR  # noqa: PLC0415

    root = Path(directory)
    artifacts = root / ARTIFACT_DIR
    present = sorted(p.name for p in artifacts.iterdir()) if artifacts.is_dir() else []
    manifest = _read(root, MANIFEST, present)
    revision, state_doc, certificate = (
        _read(root, f"{ARTIFACT_DIR}/{member}", present) for member in ARTIFACTS
    )
    try:
        basis = component_basis(revision)
    except RevisionError as error:
        raise StreamTableError(
            "internal_error", f"the bundle's revision does not parse: {error.code}"
        ) from error
    provider = provider_for(basis)
    if isinstance(provider, Unbound):
        raise StreamTableError("unsupported", provider.detail, hint=provider.hint)
    return build(
        revision,
        state_doc,
        certificate,
        manifest,
        provider=provider,
        source=source if source is not None else {"job_id": None, "bundle_id": None},
    )
