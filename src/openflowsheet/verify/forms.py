"""The verifier's property forms by basis, and the declared-phase mixture form (S11 design §4.6).

ADR 0050 D5 (register R-804). `verify.table.revision_checks` resolves one form per revision from
its basis: `SYN` (SYN-001's lines, a fresh flash and `h_<c>`) and `PR` (`verify.pr_c1`'s) are the
code they always were; every other basis — `iapws95-v1`, `coolprop-heos-v1`, `wilson-ig-v1` —
takes `DECLARED_MIXTURE`, which never asks the provider for `lnK` or `h_<c>`:

- **Degeneracy and bands:** none, as for `PR`.
- **Enthalpy flow of a flowing stream:** `Ḣ = n_tot · h(T, P, phase)`, one `evaluate_phase` call
  for the mixture `h`, in the phase its producer declares (`liquid` → LIQUID, `vapor` → VAPOR). An
  undeclared or `vapor_liquid` stream is *unlifted*: every check reading its enthalpy is blocked
  by the table's existing mechanism. A dormant stream is 0.0 (ADR 0001 D3.1).
- **Admissibility** of each stream whose enthalpy is read in a declared phase, one check
  `phase_admissibility.stream.<S>`: for a composition-dependent (γ–φ) provider, SYN-001's
  intensive criterion `tp_state.single_phase_admissible` (which dispatches on the equilibrium
  form, S10-C); for a pure fluid, LIQUID iff `T < T_c` and `P ≥ Psat(T)·(1 − 1e-9)`, VAPOR iff
  `T ≥ T_c` or `P ≤ Psat(T)·(1 + 1e-9)`, with `T_c` from S07's table or `iapws95.T_C`.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import replace
from typing import Final, Literal

from openflowsheet.compiled import EvaluationContext
from openflowsheet.models.revision_flowsheet import RevisionView
from openflowsheet.models.syn001 import TEMPERATURE_TOLERANCE
from openflowsheet.models.syn001.equilibrium_form import composition_dependent
from openflowsheet.models.syn001.tp_state import single_phase_admissible
from openflowsheet.thermo import Phase, PropertyProvider, PropertyRequest, StreamState
from openflowsheet.verify import CheckResult, dormant, evaluated, unsupported
from openflowsheet.verify.checks import KIND_REFERENCE, VerifierError, stream_of

__all__ = [
    "DECLARED_MIXTURE",
    "GAMMA_PHI_UNITS",
    "PR",
    "PURE_FLUID_MARGIN",
    "SYN",
    "Form",
    "declared_phases",
    "enthalpy_flow",
    "form_of",
    "stream_admissibility",
]

Form = Literal["SYN", "PR", "DECLARED_MIXTURE", "GAMMA_PHI_UNITS"]
SYN: Final[Form] = "SYN"
PR: Final[Form] = "PR"
DECLARED_MIXTURE: Final[Form] = "DECLARED_MIXTURE"
#: Units design §4.8 (I1b): `wilson-ig-v2`'s form, `verify.gamma_phi_units` (its `GAMMA_PHI_UNITS`).
GAMMA_PHI_UNITS: Final[Form] = "GAMMA_PHI_UNITS"
_FORMS: Final[Mapping[str, Form]] = {
    "syn001": SYN,
    "pr-c1-v1": PR,
    "wilson-ig-v2": GAMMA_PHI_UNITS,
}
#: A09: the γ–φ admissibility criterion is the units' own implementation, not an independent one.
_SHARED: Final = (
    "; the admissibility criterion is models.syn001.tp_state.single_phase_admissible, the "
    "implementation the units use (not an independent check)"
)
#: S11 design §4.6: the relative margin on `Psat` of a pure fluid's declared phase.
PURE_FLUID_MARGIN: Final = 1e-9


def form_of(provider_id: str) -> Form:
    """The verifier's form for a revision on `provider_id`'s basis."""
    return _FORMS.get(provider_id, DECLARED_MIXTURE)


def declared_phases(view: RevisionView) -> dict[str, Phase | None]:
    """Each stream's phase as its producer's outlet port declares it (R4); `None` when it is
    `vapor_liquid` (a lifted port) or no producer declares one."""
    phases: dict[str, Phase | None] = dict.fromkeys(view.streams)
    for instance in view.instances:
        for port, streams in instance.ports.items():
            if instance.directions.get(port) != "outlet":
                continue
            for stream in streams:
                phases[stream] = instance.phases.get(port)
    return phases


def enthalpy_flow(
    provider: PropertyProvider, stream: StreamState, phase: Phase, context: EvaluationContext
) -> float:
    """`n_tot · h(T, P, phase)`: the mixture enthalpy in the declared phase; 0.0 when dormant."""
    if stream.is_dormant:
        return 0.0
    result = provider.evaluate_phase(
        PropertyRequest(state=stream, phase=phase, properties=("h",)), context
    )
    if result.status != "ok":
        raise VerifierError(
            f"the verifier's own enthalpy returned {result.status}: {result.message}"
        )
    return stream.total_flow * result.values["h"]


def _critical_temperature(component: str, provider_id: str) -> float:
    """`T_c` of a pure fluid, from package data (never the binder)."""
    if provider_id == "iapws95-v1":
        from openflowsheet.thermo.iapws95 import T_C  # noqa: PLC0415

        return T_C
    from openflowsheet.thermo._coolprop_heos_fluids import FLUIDS  # noqa: PLC0415

    (row,) = [row for row in FLUIDS if row["id"] == component]
    return float(row["T_c"])


def _pure_fluid_margin(
    provider: PropertyProvider, stream: StreamState, phase: Phase, context: EvaluationContext
) -> tuple[float | None, str]:
    """`(violation, message)`: 0.0 when `phase` is admissible by §4.6's rule, else the relative
    distance past the saturation boundary (1.0 for a liquid at or above `T_c`); `None` with the
    provider's message when `Psat` is refused."""
    described = provider.describe()
    (component,) = described.components
    t_c = _critical_temperature(component, described.provider_id)
    temperature, pressure = stream.temperature, stream.pressure
    if temperature >= t_c:
        return (0.0 if phase == "VAPOR" else 1.0), ""
    result = provider.evaluate_phase(
        PropertyRequest(state=stream, phase=phase, properties=("Psat",)), context
    )
    if result.status != "ok":
        return None, f"{result.status}: {result.message}"
    saturation = result.values["Psat"]
    if phase == "LIQUID":
        admissible = pressure >= saturation * (1.0 - PURE_FLUID_MARGIN)
        return (0.0 if admissible else 1.0 - pressure / saturation), ""
    admissible = pressure <= saturation * (1.0 + PURE_FLUID_MARGIN)
    return (0.0 if admissible else pressure / saturation - 1.0), ""


def stream_admissibility(
    view: RevisionView,
    declared: Mapping[str, Phase | None],
    state: Mapping[str, float],
    provider: PropertyProvider,
    context: EvaluationContext,
    note: str,
) -> list[CheckResult]:
    """`phase_admissibility.stream.<S>` for each stream whose enthalpy is read in a declared
    phase, in allocation order (S11 design §4.6). Each check carries A09's note."""
    checks: list[CheckResult] = []
    gamma_phi = composition_dependent(provider)
    components: Sequence[str] = view.components
    for stream in view.streams:
        phase = declared.get(stream)
        if phase is None:
            continue
        identifier = f"phase_admissibility.stream.{stream}"
        carried = stream_of(state, stream, components)
        if carried.is_dormant:
            checks.append(dormant(id=identifier, category="phase_admissibility", subject=stream))
            continue
        if gamma_phi:
            admissible, _, error, status, message = single_phase_admissible(
                provider, carried, phase, tuple(components), context
            )
            if status != "ok":
                checks.append(
                    unsupported(
                        id=identifier,
                        category="phase_admissibility",
                        subject=stream,
                        reason=f"single_phase_admissible({status}): {message}",
                    )
                )
                continue
            # The shared implementation's verdict, at its registered temperature bound; `error` is
            # the gap as a temperature (or the degeneracy distance) it judged.
            checks.append(
                replace(
                    evaluated(
                        id=identifier,
                        category="phase_admissibility",
                        subject=stream,
                        value=error,
                        tolerance=TEMPERATURE_TOLERANCE,
                        reference=KIND_REFERENCE["temperature"],
                        independence_qualification=note + _SHARED,
                    ),
                    result="pass" if admissible else "fail",
                )
            )
            continue
        violation, message = _pure_fluid_margin(provider, carried, phase, context)
        if violation is None:
            checks.append(
                unsupported(
                    id=identifier,
                    category="phase_admissibility",
                    subject=stream,
                    reason=f"saturation_refused: {message}",
                )
            )
            continue
        checks.append(
            evaluated(
                id=identifier,
                category="phase_admissibility",
                subject=stream,
                value=violation,
                tolerance=0.0,
                independence_qualification=note,
            )
        )
    return checks
