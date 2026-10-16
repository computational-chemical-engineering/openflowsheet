"""What a surrogate-backed certificate carries (M04 spec §8.6; ADR 0037 D5): per
`c1.reactor_surrogate` instance, the `bounds_and_domain` check `SURROGATE-DOMAIN:<unit>` and the
limitations `surrogate_model` and, outside the reference box, `surrogate_outside_reference_domain`.
No schema changes: a check id is free text and limitations are open objects keyed by `kind`.

**Read from** the converged state, the revision (the instance's wiring and `n_tubes`) and the
instance's SurrogateManifest, which the binder resolved by `model.artifact_ref` and checked (spec
§8.2) — never from the unit, its block or its rows (R-016). Hence:

- the scaled inlet z is formed here from the manifest's `input_map` (centre and half-width per
  coordinate), the excess is e(z) = max(0, ‖z‖∞ − 1) (spec §3.6);
- admissibility is judged on the state's own outputs, X = ξ / n_N2,in and ΔT = T_out − T_in, against
  the manifest's `output_map.admissible` (X ∈ [0, min(0.95, r/3)], ΔT ∈ [−50, 250] K, spec §3.2): at
  a converged state they equal the prediction to the residual tolerance, and reading them from the
  state is what makes the check independent of the solver;
- the hard domain is the manifest's verbatim copy of the parent's, with the parent's predicates
  (inclusive bounds; H2/N2 division-free).

The check's value is e(z), its tolerance `None` (spec §8.6): it passes iff the inlet is inside the
hard domain and the outputs are admissible; outside the box it still passes and the limitation says
that no coverage claim applies there. A dormant inlet is `not_applicable` (`ZERO_FLOW`): the
surrogate is not evaluated (spec §3.7).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from fractions import Fraction
from typing import Any, Final

from openflowsheet.models import flow_id, pressure_id, temperature_id
from openflowsheet.models.revision_flowsheet import InstanceView, RevisionView
from openflowsheet.models.syn001.conversion_reactor import extent_id
from openflowsheet.verify import CheckResult, Limitation, dormant

__all__ = ["CHECK_PREFIX", "MODEL_ID", "surrogate_items"]

#: The surrogate unit's model id (M04 spec §8.1).
MODEL_ID: Final = "c1.reactor_surrogate"
#: `SURROGATE-DOMAIN:<unit>` (spec §8.6).
CHECK_PREFIX: Final = "SURROGATE-DOMAIN"

_COMPONENTS: Final[tuple[str, ...]] = ("H2", "N2", "NH3", "Ar", "CH4")


def _within(value: float, bounds: Sequence[float]) -> bool:
    return float(bounds[0]) <= value <= float(bounds[1])


def _hard_bounds(
    n: Sequence[float], temperature: float, pressure: float, hard: Mapping[str, Any], n_tubes: float
) -> list[str]:
    total = (((n[0] + n[1]) + n[2]) + n[3]) + n[4]
    violated = []
    if not _within(temperature, hard["T_K"]):
        violated.append("T")
    if not _within(pressure, hard["P_Pa"]):
        violated.append("P")
    low, high = (float(b) for b in hard["H2_N2"])
    if not (n[1] > 0.0 and low * n[1] <= n[0] <= high * n[1]):
        violated.append("H2_N2")
    if not (n[3] + n[4]) <= float(hard["inert_max"]) * total:
        violated.append("inerts")
    flow = hard.get("tube_flow_mol_s")
    if flow is not None and not _within(total / n_tubes, flow):
        violated.append("F_tube")
    return violated


def _coverage(manifest: Mapping[str, Any]) -> dict[str, Any]:
    """Spec §8.6's coverage numbers, from the manifest alone (spec §18 A1.4)."""
    calibration, evaluation = manifest["calibration"], manifest["evaluation"]
    alpha = Fraction(str(calibration["alpha"]))
    k, n = calibration["k"], calibration["n"]
    return {
        "nominal": float(1 - alpha),
        "finite_sample": None if k is None else float(Fraction(k, n + 1)),
        "lower_bound": evaluation["lower_bound"],
        "minimum": evaluation["c_min"],
        "test_draws": evaluation["m"],
    }


def _model_limitation(unit: str, sha256: str | None, manifest: Mapping[str, Any]) -> Limitation:
    q_hat = manifest["calibration"]["q_hat"]
    scales = manifest["score"]["scales"]
    band = (
        None
        if q_hat is None
        else {"X": q_hat * float(scales["X"]), "dT_K": q_hat * float(scales["dT_K"])}
    )
    return Limitation(
        "surrogate_model",
        {
            "unit": unit,
            "surrogate_id": manifest["surrogate_id"],
            "manifest_sha256": sha256,
            "band": band,
            "coverage": _coverage(manifest),
            "qualifications": list(manifest["qualifications"]),
        },
    )


def _domain_check(
    instance: InstanceView,
    state: Mapping[str, float],
    manifest: Mapping[str, Any],
    limitations: list[Limitation],
) -> CheckResult:
    unit = instance.unit_id
    identifier = f"{CHECK_PREFIX}:{unit}"
    inlet, outlet = instance.ports["inlet"][0], instance.ports["outlet"][0]
    n = tuple(state[flow_id(inlet, c)] for c in _COMPONENTS)
    if all(value == 0.0 for value in n):
        return dormant(id=identifier, category="bounds_and_domain", subject=unit)
    t_in, p_in = state[temperature_id(inlet)], state[pressure_id(inlet)]
    n_tubes = float(instance.parameters["n_tubes"])
    total = (((n[0] + n[1]) + n[2]) + n[3]) + n[4]
    if n[1] == 0.0 or total == 0.0:
        return CheckResult(
            id=identifier,
            category="bounds_and_domain",
            subject=unit,
            result="fail",
            reason=f"surrogate_input_undefined({unit})",
        )
    u = (t_in, p_in, n[0] / n[1], n[2] / total, n[3] / total, n[4] / total, total / n_tubes)
    box = manifest["input_map"]["coordinates"]
    z = [(u[k] - float(c["centre"])) / float(c["half_width"]) for k, c in enumerate(box)]
    excess = max(0.0, max(abs(x) for x in z) - 1.0)
    outside = [str(c["name"]) for c, x in zip(box, z, strict=True) if abs(x) > 1.0]
    if outside:
        limitations.append(
            Limitation(
                "surrogate_outside_reference_domain",
                {"unit": unit, "scaled_excess": excess, "coordinates": outside},
            )
        )

    reasons = [
        f"surrogate_outside_hard_domain({unit}:{bound})"
        for bound in _hard_bounds(n, t_in, p_in, manifest["domain"]["hard"], n_tubes)
    ]
    admissible = manifest["output_map"]["admissible"]
    x = state[extent_id(unit)] / n[1]
    rise = state[temperature_id(outlet)] - t_in
    if not (_within(x, admissible["X"]) and (not admissible["X_le_r_over_3"] or x <= u[2] / 3.0)):
        reasons.append(f"surrogate_output_inadmissible({unit}:X)")
    if not _within(rise, admissible["dT_K"]):
        reasons.append(f"surrogate_output_inadmissible({unit}:dT)")
    return CheckResult(
        id=identifier,
        category="bounds_and_domain",
        subject=unit,
        result="fail" if reasons else "pass",
        value=excess,
        reason="; ".join(reasons),
    )


def surrogate_items(
    view: RevisionView,
    state: Mapping[str, float],
    manifests: Mapping[str, Mapping[str, Any]],
) -> tuple[list[CheckResult], list[Limitation]]:
    """Every surrogate instance's check and limitations, in declaration order: the check, then
    `surrogate_model`, then `surrogate_outside_reference_domain` when e(z) > 0. An instance whose
    manifest the binding does not hold is `unsupported` (it caps the verdict at UNVERIFIED)."""
    checks: list[CheckResult] = []
    limitations: list[Limitation] = []
    for instance in view.instances:
        if instance.model_id != MODEL_ID:
            continue
        manifest = manifests.get(instance.unit_id)
        if manifest is None:
            checks.append(
                CheckResult(
                    id=f"{CHECK_PREFIX}:{instance.unit_id}",
                    category="bounds_and_domain",
                    subject=instance.unit_id,
                    result="unsupported",
                    scope="unsupported",
                    reason=f"surrogate_manifest_mismatch({instance.unit_id})",
                )
            )
            continue
        outside: list[Limitation] = []
        checks.append(_domain_check(instance, state, manifest, outside))
        limitations.append(
            _model_limitation(instance.unit_id, instance.model_artifact_ref, manifest)
        )
        limitations.extend(outside)
    return checks, limitations
