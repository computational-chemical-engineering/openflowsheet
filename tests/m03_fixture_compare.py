"""How an M03 fixture is compared with what the code emits today (M03 review F1; ADR 0008 D2.1).

**Not byte for byte.** The default gate runs on x86-64 and aarch64. On one commit and one lock the
two disagree in the last one to three ulps of converged floats, and the difference enters at
SuperLU (`openflowsheet.run.compare`'s header holds the measurement). A byte comparison would also
pin every `state_sha256` the study fixtures carry, which ADR 0008 D2.1 forbids, and FIT-U's
arbitrary final iterate, on which spec §7.4 (Amendment 1) forbids anything to depend.

So the comparison is `differences` under `CURRENT_POLICY_ID`: structure exactly, float digests for
shape, floats within the policy. A pre-pass first handles the M03 values the policy has no row for.
Each rule checks its value against a registered bound, and only then takes the value out of the
policy comparison, so nothing leaves the comparison unchecked.

1. **Scaled sensitivities** (`forward`/`adjoint` `scaled`) are floored at spec §4.7's
   `τ_abs = 1e-11`; below it an entry is a registered zero (measured roundoff 6.5e-15). The
   `unscaled` matrix is `S = S_y Ŝ S_p⁻¹` (spec §3.6), so its entry (i, j) is floored at
   `τ_abs s_yi / s_pj`, with the scales the committed record declares. `consistency`'s
   `max_abs_difference`, a difference of two scaled matrices, is floored at `τ_abs` too, and so are
   the scaled objective and constraint gradients of V5 (`kkt`), which are rows of the adjoint `Ŝ`
   (spec §8.5).
2. **A residual judged against a stated tolerance is floored at that tolerance**, because below it
   the residual is not a measurement. This is ADR 0007 D2.2's rule for a check's `value` and its
   `tolerance`, applied to M03's names:
   - Q1's `scaled_residual_inf` and Q2′'s `residual_normalized` take their sibling `threshold`, and
     the record's top-level `scaled_residual_inf` (Q1's) takes Q1's threshold;
   - V2's `scaled_difference_inf` takes its `threshold`; its `worst_variable`, the argmax of a
     difference inside that floor, is then checked for kind only;
   - V5's `stationarity_residual_inf` takes its `tau_kkt`;
   - a constraint value or slack (scaled, spec §8.5 V3) takes V3's `τ_feas = 1e-8`;
   - Ipopt's final primal infeasibility, dual infeasibility and complementarity take their §8.4
     tolerances (`constr_viol_tol`, `dual_inf_tol`, `compl_inf_tol`).
3. **A `LinearSolveRecord`'s pivot-path diagnostics** carry the dataclass names
   (`min_abs_u_diagonal`, `max_abs_u_diagonal`, `nnz_l`, `nnz_u`). The policy registers the same
   SuperLU quantities as `u_diag_min_abs`, `u_diag_max_abs` (post-pivoting, ADR 0025 D4) and
   `nnz_L`, `nnz_U` (unreproducible counts), so the fields are renamed to the registered names and
   the registered rows apply. A refusal's or reason's `detail` is text with floats in it, which
   the policy registers under `message` (ADR 0025 D6); it is renamed likewise.
4. **A fit's path** (review F1: "the path counters are recorded and not compared"). `nfev`,
   `njev`, the `evaluations` counts and trf's final `optimality` are checked for kind. A converged
   fit's `status` is checked to be one of trf's convergence statuses, and its `message` to be text,
   because which convergence test fired first belongs to the path too; `success` stays compared.
   A `normalized_residual` is `(observed − predicted)/√(σ² + SE²)`, which amplifies a difference
   in `predicted`. It is therefore floored at the policy's tolerance on `predicted`, propagated:
   `1e-9 |predicted| / √(σ² + SE²)`. *Measured*, perturbing every linear back-solve:
   - by two ulps, FIT-I's `njev` moves from 7 to 8 and its `optimality` from 1.7e-9 to 2.4e-9;
   - by two ulps with another seed, FIT-U ends on `ftol` rather than `xtol`;
   - by four ulps, FIT-I's S4.N normalized residual moves 1.3e-9 relative.
5. **An unidentifiable fit** (spec §7.4, Amendment 1; A27, A28). Every value set by the path along
   the null direction is checked against its registered bound, and then left out of the
   comparison:
   - an undetermined parameter's `final_iterate`, and its entry of `identifiability.theta`, lie
     inside the declared bounds (A27);
   - each singular value at or beyond `rank` is at most `1e-12 σ₁`, and `singular_value_ratio` is
     at most 1e-12 (A27's σ₂/σ₁ bound);
   - `null_directions_scaled` and `right_singular_vectors_scaled` are compared with A27's
     null-direction tolerance, 1e-8, as their absolute floor;
   - an undetermined prediction's `null_projection_relative` lies in the registered
     `null_projection_relative_range_over_box`, widened by 1e-6 on each side (A28);
   - a determined prediction's `null_projection_relative` is floored at the same 1e-8. That floor
     bounds it: the prediction's gradient has no component along the null direction in closed form
     (spec §7.5), so its projection is the null direction's own error.

   - an undetermined parameter's `at_bound` and `active_mask` entry are where the path stopped,
     checked for kind.

   *Measured:* the two-ulp perturbation sends FIT-U's r to 0.6178 instead of 0.96906, and an
   eight-ulp one to the bound 0.5. Every class (i)
   quantity stays in the policy comparison: the determined estimates, σ₁, χ², `cost` and a
   determined prediction.
6. **`wall_time_s`** (the NLP start records) is a measured time. It is checked to be a positive
   finite number and is not compared (review ruling Q3.3).
7. **The solver's environment record** (M03 review F2). The path of the loaded `libpynumero_ASL`
   names a directory of the machine, so it is checked for kind only. Its SHA-256, the thread
   variables and the effective OpenMP thread count are compared exactly: the NLP evidence holds
   only under them (review ruling Q2).

Every rule was found by regenerating every fixture with each linear back-solve's solution
perturbed by k ulps with random signs (eight regenerations, k = 1, 2, 2, 2, 4, 8, 16, 64): each
compares clean under these rules, against a raw difference in 1 100 to 1 350 leaves.

What this does not relax: every structural member, every status and outcome, every count the
policy compares, and every class (i) value at 1e-9 relative. The `test_..._still_catches_...` test
in `test_m03_schemas.py` shows that a perturbed fixture value is still caught.
"""

from __future__ import annotations

import copy
import math
from collections.abc import Callable
from typing import Any, Final

from m03_support import number, reference

from openflowsheet.run.compare import CURRENT_POLICY_ID, V2_RELATIVE_TOLERANCE, differences
from openflowsheet.studies.nlp.formulation import IPOPT_OPTIONS
from openflowsheet.studies.nlp.verification import TAU_FEAS
from openflowsheet.studies.sensitivity import TAU_CONSISTENCY_ABS

#: Spec §4.7: `τ_abs`, the registered-zero bound of a scaled sensitivity.
TAU_ABS: Final = TAU_CONSISTENCY_ABS
#: A27: an unidentifiable fit's σ₂/σ₁ bound and the null direction's tolerance.
TAU_RATIO_U: Final = 1e-12
TAU_NULL: Final = 1e-8
#: A28 (Amendment 1): the widening of the registered null-projection range.
TAU_PROJECTION: Final = 1e-6
#: Rule 2: Ipopt's final measures and the §8.4 option each is judged by.
IPOPT_FINAL_FLOORS: Final = {
    "primal_infeasibility": float(IPOPT_OPTIONS["constr_viol_tol"]),
    "dual_infeasibility": float(IPOPT_OPTIONS["dual_inf_tol"]),
    "complementarity": float(IPOPT_OPTIONS["compl_inf_tol"]),
}
#: Rule 3: a `LinearSolveRecord`'s field names, and the names the policy registers them under.
POLICY_NAMES: Final = {
    "min_abs_u_diagonal": "u_diag_min_abs",
    "max_abs_u_diagonal": "u_diag_max_abs",
    "nnz_l": "nnz_L",
    "nnz_u": "nnz_U",
    "detail": "message",
}
#: Rule 4: a fit's path counters.
PATH_COUNTERS: Final = {
    "estimator_result": ("nfev", "njev"),
    "evaluations": ("jacobian_calls", "residual_calls", "sensitivities", "solves"),
}
#: Rule 4: `scipy.optimize.least_squares`'s convergence statuses (gtol, ftol, xtol, ftol and xtol).
CONVERGED_STATUSES: Final = (1, 2, 3, 4)
#: Rule 6.
VOLATILE: Final = "wall_time_s"


def fixture_differences(emitted: Any, committed: Any) -> list[str]:
    """Every way `emitted` departs from `committed` beyond the rules above; empty when equal."""
    mine, theirs = copy.deepcopy(emitted), copy.deepcopy(committed)
    found: list[str] = []
    _prepass(mine, theirs, "<root>", found)
    return found + differences(mine, theirs, policy_id=CURRENT_POLICY_ID)


def measurement_differences(emitted: Any, committed: Any) -> list[str]:
    """`benchmarks/m03/nlp-measurements.json` (spec §14 Q-F2), for structure and margin.

    Each measured `value` has its registered `tolerance` beside it. An `upper` value is floored at
    that tolerance by the policy's own rule (ADR 0007 D2.2). A `lower` value, a regime margin, is
    compared relatively with no floor, because its tolerance is a minimum and not a noise floor.
    The `ratio` is the measurement's margin: it is checked to be at least `margin_factor`, or null
    for a zero measurement, and is not compared for value. Everything else is `fixture_differences`.
    """
    mine, theirs = copy.deepcopy(emitted), copy.deepcopy(committed)
    found: list[str] = []
    factor = theirs.get("q_f2", {}).get("margin_factor")
    for index, (start, reference_start) in enumerate(
        zip(
            mine.get("q_f2", {}).get("starts", []),
            theirs.get("q_f2", {}).get("starts", []),
            strict=False,
        )
    ):
        measured, reference_measured = start.get("measured", {}), reference_start.get("measured")
        for name in sorted(set(measured) & set(reference_measured or {})):
            left, right = measured[name], reference_measured[name]
            where = f"<root>.q_f2.starts[{index}].measured.{name}"
            ratio = left.get("ratio")
            if ratio is not None and not (_real(ratio) and _real(factor) and ratio >= factor):
                found.append(f"{where}.ratio: {ratio!r} is inside the margin factor {factor!r}")
            left["ratio"] = right["ratio"] = _checked("at least the margin factor")
            if right.get("sense") == "lower":
                _floored(left, right, "value", f"{where}.value", 0.0, "a lower bound", found)
    closest, reference_closest = (
        mine.get("q_f2", {}).get("closest"),
        theirs.get("q_f2", {}).get("closest"),
    )
    if isinstance(closest, dict) and isinstance(reference_closest, dict):
        ratio = closest.get("ratio")
        if not (_real(ratio) and _real(factor) and ratio >= factor):
            found.append(f"<root>.q_f2.closest.ratio: {ratio!r} is inside {factor!r}")
        closest["ratio"] = reference_closest["ratio"] = _checked("at least the margin factor")
    return found + fixture_differences(mine, theirs)


# -- the pre-pass ---------------------------------------------------------------------------------


def _checked(rule: str) -> str:
    """What a value becomes on both sides once its own rule has judged it."""
    return f"<checked: {rule}>"


def _real(value: Any) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool) and math.isfinite(value)


def _prepass(mine: Any, theirs: Any, where: str, found: list[str]) -> None:
    """Rules 1-7, wherever their objects sit; a shape difference is left to `differences`."""
    if isinstance(theirs, list) and isinstance(mine, list) and len(mine) == len(theirs):
        for index, (left, right) in enumerate(zip(mine, theirs, strict=True)):
            _prepass(left, right, f"{where}[{index}]", found)
        return
    if not (isinstance(theirs, dict) and isinstance(mine, dict)):
        return
    # An invalid fixture is a valid one with its first required member removed, so an object is
    # recognized by a member that is never the first required one.
    if "derivative_provenance" in theirs and "qualification" in theirs:
        _sensitivity(mine, theirs, where, found)
    if "identifiability" in theirs and "estimator_result" in theirs:
        _fit_path(mine, theirs, where, found)
        if theirs.get("status") == "UNIDENTIFIABLE":
            _unidentifiable(mine, theirs, where, found)
    _verification(mine, theirs, where, found)
    for name, registered in POLICY_NAMES.items():
        if name in theirs and name in mine and registered not in theirs:
            theirs[registered] = theirs.pop(name)
            mine[registered] = mine.pop(name)
    if VOLATILE in theirs and VOLATILE in mine:
        for side, value in (("emitted", mine[VOLATILE]), ("committed", theirs[VOLATILE])):
            if not (_real(value) and value > 0):
                found.append(f"{where}.{VOLATILE}: {side} {value!r} is not a positive time")
        mine[VOLATILE] = theirs[VOLATILE] = _checked("a measured time")
    _solver_environment(mine, theirs, where, found)
    for key in sorted(set(mine) & set(theirs)):
        _prepass(mine[key], theirs[key], f"{where}.{key}", found)


def _floored(
    mine: Any, theirs: Any, key: Any, where: str, floor: float, source: str, found: list[str]
) -> None:
    """One number (or `null`) under `V2_RELATIVE_TOLERANCE` and `floor`, then set aside."""
    left, right = mine[key], theirs[key]
    if left is None or right is None:
        if (left is None) != (right is None):
            found.append(f"{where}: {left!r} against {right!r}")
    elif not (_real(left) and _real(right)):
        found.append(f"{where}: {left!r} against {right!r} is not a pair of finite numbers")
    elif not math.isclose(left, right, rel_tol=V2_RELATIVE_TOLERANCE, abs_tol=floor):
        found.append(
            f"{where}: {left!r} against {right!r}, outside {V2_RELATIVE_TOLERANCE:g} relative / "
            f"{floor:g} absolute ({source})"
        )
    mine[key] = theirs[key] = _checked(source)


def _vector(
    mine: Any,
    theirs: Any,
    where: str,
    floor: Callable[[int], float],
    source: str,
    found: list[str],
) -> None:
    """Each entry of two equally long lists; anything else is left to `differences`."""
    if isinstance(mine, list) and isinstance(theirs, list) and len(mine) == len(theirs):
        for j in range(len(mine)):
            _floored(mine, theirs, j, f"{where}[{j}]", floor(j), source, found)


def _matrix(
    mine: Any,
    theirs: Any,
    where: str,
    floor: Callable[[int, int], float],
    source: str,
    found: list[str],
) -> None:
    """A rows × columns matrix entry by entry; a shape difference is left to `differences`."""
    if isinstance(mine, list) and isinstance(theirs, list) and len(mine) == len(theirs):
        for i, (row, reference_row) in enumerate(zip(mine, theirs, strict=True)):
            _vector(row, reference_row, f"{where}[{i}]", lambda j, i=i: floor(i, j), source, found)


def _sensitivity(
    mine: dict[str, Any], theirs: dict[str, Any], where: str, found: list[str]
) -> None:
    """Rules 1 and 2 on one `sensitivity_result`."""
    output_scales = [float(output["scale"]) for output in theirs.get("outputs", [])]
    parameter_scales = [float(parameter["scale"]) for parameter in theirs.get("parameters", [])]
    for mode in ("forward", "adjoint"):
        left, right = mine.get(mode), theirs.get(mode)
        if not (isinstance(left, dict) and isinstance(right, dict)):
            continue
        _matrix(
            left.get("scaled"),
            right.get("scaled"),
            f"{where}.{mode}.scaled",
            lambda i, j: TAU_ABS,
            "spec §4.7 tau_abs",
            found,
        )
        _matrix(
            left.get("unscaled"),
            right.get("unscaled"),
            f"{where}.{mode}.unscaled",
            lambda i, j: TAU_ABS * output_scales[i] / parameter_scales[j],
            "spec §4.7 tau_abs, unscaled by S_y and S_p (spec §3.6)",
            found,
        )
    consistency, emitted = theirs.get("consistency"), mine.get("consistency")
    if isinstance(consistency, dict) and isinstance(emitted, dict):
        if "max_abs_difference" in consistency and "max_abs_difference" in emitted:
            _floored(
                emitted,
                consistency,
                "max_abs_difference",
                f"{where}.consistency.max_abs_difference",
                TAU_ABS,
                "spec §4.7 tau_abs",
                found,
            )
    qualification, emitted = theirs.get("qualification"), mine.get("qualification")
    if not (isinstance(qualification, dict) and isinstance(emitted, dict)):
        return
    outcomes, emitted_outcomes = qualification.get("outcomes"), emitted.get("outcomes")
    if not (
        isinstance(outcomes, list)
        and isinstance(emitted_outcomes, list)
        and len(outcomes) == len(emitted_outcomes)
    ):
        return
    q1_threshold = None
    for index, (left, right) in enumerate(zip(emitted_outcomes, outcomes, strict=True)):
        threshold = right.get("threshold")
        if not (_real(threshold) and isinstance(left, dict)):
            continue
        source = f"its sibling threshold {threshold:g}, ADR 0007 D2.2"
        label = f"{where}.qualification.outcomes[{index}]"
        if right.get("qualification") == "Q1":
            q1_threshold = threshold
        if "scaled_residual_inf" in right and "scaled_residual_inf" in left:
            _floored(
                left,
                right,
                "scaled_residual_inf",
                f"{label}.scaled_residual_inf",
                threshold,
                source,
                found,
            )
        _vector(
            left.get("residual_normalized"),
            right.get("residual_normalized"),
            f"{label}.residual_normalized",
            lambda j, floor=threshold: floor,
            source,
            found,
        )
    if q1_threshold is not None and "scaled_residual_inf" in qualification:
        if "scaled_residual_inf" in emitted:
            _floored(
                emitted,
                qualification,
                "scaled_residual_inf",
                f"{where}.qualification.scaled_residual_inf",
                q1_threshold,
                f"Q1's threshold {q1_threshold:g}, ADR 0007 D2.2",
                found,
            )


def _verification(
    mine: dict[str, Any], theirs: dict[str, Any], where: str, found: list[str]
) -> None:
    """Rules 1 and 2 on a V check, a candidate, its `kkt` block and a start's Ipopt measures."""
    check = theirs.get("check")
    if check == "V2" and "scaled_difference_inf" in theirs and "scaled_difference_inf" in mine:
        threshold = theirs.get("threshold")
        committed = theirs["scaled_difference_inf"]
        inside = _real(threshold) and _real(committed) and committed <= threshold
        if inside:
            _floored(
                mine,
                theirs,
                "scaled_difference_inf",
                f"{where}.scaled_difference_inf",
                float(threshold),
                f"its sibling threshold {threshold:g}, ADR 0007 D2.2",
                found,
            )
            if "worst_variable" in mine and "worst_variable" in theirs:
                if not isinstance(mine["worst_variable"], str):
                    found.append(f"{where}.worst_variable: {mine['worst_variable']!r}")
                mine["worst_variable"] = theirs["worst_variable"] = _checked(
                    "the argmax of a difference inside its threshold"
                )
    if "stationarity_residual_inf" in theirs and "stationarity_residual_inf" in mine:
        tau = theirs.get("tau_kkt")
        if _real(tau):
            _floored(
                mine,
                theirs,
                "stationarity_residual_inf",
                f"{where}.stationarity_residual_inf",
                float(tau),
                f"its sibling tau_kkt {tau:g}, ADR 0007 D2.2",
                found,
            )
    if "objective_gradient_scaled" in theirs and "objective_gradient_scaled" in mine:
        _vector(
            mine["objective_gradient_scaled"],
            theirs["objective_gradient_scaled"],
            f"{where}.objective_gradient_scaled",
            lambda j: TAU_ABS,
            "spec §4.7 tau_abs, a row of the adjoint sensitivity",
            found,
        )
    gradients, emitted = (
        theirs.get("constraint_gradients_scaled"),
        mine.get("constraint_gradients_scaled"),
    )
    if isinstance(gradients, dict) and isinstance(emitted, dict):
        for name in sorted(set(gradients) & set(emitted)):
            _vector(
                emitted[name],
                gradients[name],
                f"{where}.constraint_gradients_scaled.{name}",
                lambda j: TAU_ABS,
                "spec §4.7 tau_abs, a row of the adjoint sensitivity",
                found,
            )
    source = f"V3's tau_feas {TAU_FEAS:g}, ADR 0007 D2.2"
    values, emitted = theirs.get("constraint_values"), mine.get("constraint_values")
    if isinstance(values, dict) and isinstance(emitted, dict):
        for name in sorted(set(values) & set(emitted)):
            _floored(
                emitted, values, name, f"{where}.constraint_values.{name}", TAU_FEAS, source, found
            )
    slacks, emitted = theirs.get("slacks"), mine.get("slacks")
    if isinstance(slacks, dict) and isinstance(emitted, dict):
        for name in sorted(set(slacks) & set(emitted)):
            if isinstance(slacks[name], dict) and isinstance(emitted[name], dict):
                for side in sorted(set(slacks[name]) & set(emitted[name])):
                    _floored(
                        emitted[name],
                        slacks[name],
                        side,
                        f"{where}.slacks.{name}.{side}",
                        TAU_FEAS,
                        source,
                        found,
                    )
    if theirs.get("kind") in ("constraint", "bound") and "slack" in theirs and "slack" in mine:
        _floored(mine, theirs, "slack", f"{where}.slack", TAU_FEAS, source, found)
    final, emitted = theirs.get("ipopt_final"), mine.get("ipopt_final")
    if isinstance(final, dict) and isinstance(emitted, dict):
        for name, floor in IPOPT_FINAL_FLOORS.items():
            if name in final and name in emitted:
                _floored(
                    emitted,
                    final,
                    name,
                    f"{where}.ipopt_final.{name}",
                    floor,
                    f"its spec §8.4 tolerance {floor:g}",
                    found,
                )


def _fit_path(mine: dict[str, Any], theirs: dict[str, Any], where: str, found: list[str]) -> None:
    """Rule 4 on one estimation report."""
    for block, counters in PATH_COUNTERS.items():
        left, right = mine.get(block), theirs.get(block)
        if not (isinstance(left, dict) and isinstance(right, dict)):
            continue
        for counter in counters:
            if counter in left and counter in right:
                if not (isinstance(left[counter], int) and left[counter] > 0):
                    found.append(f"{where}.{block}.{counter}: {left[counter]!r} is not a count")
                left[counter] = right[counter] = _checked("a path counter, recorded")
        if block != "estimator_result":
            continue
        if "optimality" in left and "optimality" in right:
            if not (_real(left["optimality"]) and left["optimality"] >= 0):
                found.append(f"{where}.{block}.optimality: {left['optimality']!r}")
            left["optimality"] = right["optimality"] = _checked("path-dependent, recorded")
        # `success` stays compared; which of trf's convergence tests fired is the path's.
        if "status" in left and "status" in right and left.get("success") is True:
            if left["status"] not in CONVERGED_STATUSES:
                found.append(f"{where}.{block}.status: {left['status']!r} is not a convergence")
            left["status"] = right["status"] = _checked("a convergence status, path-dependent")
            if "message" in left and "message" in right:
                if not isinstance(left["message"], str):
                    found.append(f"{where}.{block}.message: {left['message']!r}")
                left["message"] = right["message"] = _checked("the convergence test's message")
    for index, (left, right) in enumerate(
        zip(mine.get("validation", []), theirs.get("validation", []), strict=False)
    ):
        predicted, sigma = right.get("predicted"), right.get("sigma")
        error = right.get("prediction_standard_error")
        if not (_real(predicted) and _real(sigma) and "normalized_residual" in left):
            continue
        spread = math.hypot(sigma, error if _real(error) else 0.0)
        _floored(
            left,
            right,
            "normalized_residual",
            f"{where}.validation[{index}].normalized_residual",
            V2_RELATIVE_TOLERANCE * abs(predicted) / spread,
            "the policy's tolerance on `predicted`, propagated (spec §7.4)",
            found,
        )


def _unidentifiable(
    mine: dict[str, Any], theirs: dict[str, Any], where: str, found: list[str]
) -> None:
    """Rule 5 on one `UNIDENTIFIABLE` estimation report."""
    declared = {entry["id"]: entry for entry in theirs.get("parameters_declared", [])}
    order = list(declared)
    undetermined = {
        entry["id"] for entry in theirs.get("parameters", []) if entry.get("determined") is False
    }
    bounded = _checked("inside its bounds, A27")

    def inside_bounds(value: Any, parameter_id: str, label: str) -> None:
        low, high = (float(bound) for bound in declared[parameter_id]["bounds"])
        if not (_real(value) and low <= value <= high):
            found.append(
                f"{label}: {value!r} is outside {parameter_id}'s bounds [{low}, {high}] (A27: an "
                "undetermined parameter's final iterate is checked only to lie inside them)"
            )

    for index, (left, right) in enumerate(
        zip(mine.get("parameters", []), theirs.get("parameters", []), strict=False)
    ):
        if right.get("id") in undetermined and "final_iterate" in left:
            inside_bounds(
                left["final_iterate"], right["id"], f"{where}.parameters[{index}].final_iterate"
            )
            left["final_iterate"] = right["final_iterate"] = bounded
            if "at_bound" in left and "at_bound" in right:
                if not isinstance(left["at_bound"], bool):
                    found.append(f"{where}.parameters[{index}].at_bound: {left['at_bound']!r}")
                left["at_bound"] = right["at_bound"] = _checked("where the path stopped")
    result, reference_result = mine.get("estimator_result"), theirs.get("estimator_result")
    if isinstance(result, dict) and isinstance(reference_result, dict):
        mask, reference_mask = result.get("active_mask"), reference_result.get("active_mask")
        if isinstance(mask, list) and isinstance(reference_mask, list):
            for index, parameter_id in enumerate(order):
                if parameter_id in undetermined and index < min(len(mask), len(reference_mask)):
                    if mask[index] not in (-1, 0, 1):
                        found.append(f"{where}.estimator_result.active_mask[{index}]")
                    mask[index] = reference_mask[index] = _checked("where the path stopped")

    for block in ("identifiability", "identifiability_at_start"):
        left, right = mine.get(block), theirs.get(block)
        if isinstance(left, dict) and isinstance(right, dict):
            _identifiability(left, right, f"{where}.{block}", found)
    # The final iterate is `identifiability.theta`; the start's θ₀ is the problem's and is compared.
    final, reference_final = mine.get("identifiability"), theirs.get("identifiability")
    if isinstance(final, dict) and isinstance(reference_final, dict):
        theta, reference_theta = final.get("theta"), reference_final.get("theta")
        if isinstance(theta, list) and isinstance(reference_theta, list):
            for index, parameter_id in enumerate(order):
                if parameter_id in undetermined and index < min(len(theta), len(reference_theta)):
                    label = f"{where}.identifiability.theta[{index}]"
                    inside_bounds(theta[index], parameter_id, label)
                    theta[index] = reference_theta[index] = bounded

    registered = _registered_ranges(theirs.get("fit_id"))
    key = "null_projection_relative"
    for index, (left, right) in enumerate(
        zip(mine.get("validation", []), theirs.get("validation", []), strict=False)
    ):
        if key not in left or key not in right:
            continue
        label = f"{where}.validation[{index}].{key}"
        if right.get("determined") is not False:
            _floored(left, right, key, label, TAU_NULL, "A27's null-direction tolerance", found)
            continue
        low, high = registered.get(str(right.get("id")), (math.nan, math.nan))
        value = left[key]
        if not (_real(value) and low - TAU_PROJECTION <= value <= high + TAU_PROJECTION):
            found.append(
                f"{label}: {value!r} is outside the registered range [{low}, {high}] widened by "
                f"{TAU_PROJECTION:g} (A28)"
            )
        left[key] = right[key] = _checked("inside its registered range, A28")


def _identifiability(
    mine: dict[str, Any], theirs: dict[str, Any], where: str, found: list[str]
) -> None:
    rank = theirs.get("rank")
    values = mine.get("singular_values_scaled")
    reference_values = theirs.get("singular_values_scaled")
    if isinstance(rank, int) and isinstance(values, list) and isinstance(reference_values, list):
        largest = values[0] if values and _real(values[0]) else math.nan
        for index in range(rank, min(len(values), len(reference_values))):
            value = values[index]
            if not (_real(value) and 0 <= value <= TAU_RATIO_U * largest):
                found.append(
                    f"{where}.singular_values_scaled[{index}]: {value!r} exceeds "
                    f"{TAU_RATIO_U:g} sigma_1 (A27)"
                )
            values[index] = reference_values[index] = _checked("<= 1e-12 sigma_1, A27")
    if "singular_value_ratio" in mine and "singular_value_ratio" in theirs:
        ratio = mine["singular_value_ratio"]
        if not (_real(ratio) and 0 <= ratio <= TAU_RATIO_U):
            found.append(f"{where}.singular_value_ratio: {ratio!r} exceeds {TAU_RATIO_U:g} (A27)")
        mine["singular_value_ratio"] = theirs["singular_value_ratio"] = _checked("A27")
    for key in ("null_directions_scaled", "right_singular_vectors_scaled"):
        _matrix(
            mine.get(key),
            theirs.get(key),
            f"{where}.{key}",
            lambda i, j: TAU_NULL,
            "A27's null-direction tolerance",
            found,
        )


def _solver_environment(
    mine: dict[str, Any], theirs: dict[str, Any], where: str, found: list[str]
) -> None:
    """Rule 7: the loaded `libpynumero_ASL`'s path is the machine's; everything else is compared."""
    solver, emitted = theirs.get("solver"), mine.get("solver")
    if not (isinstance(solver, dict) and isinstance(emitted, dict)):
        return
    environment, emitted_environment = solver.get("environment"), emitted.get("environment")
    if not (isinstance(environment, dict) and isinstance(emitted_environment, dict)):
        return
    library, emitted_library = (
        environment.get("pynumero_asl"),
        emitted_environment.get("pynumero_asl"),
    )
    if isinstance(library, dict) and isinstance(emitted_library, dict):
        if "path" in library and "path" in emitted_library:
            if not isinstance(emitted_library["path"], str) or not emitted_library["path"]:
                found.append(f"{where}.solver.environment.pynumero_asl.path: not a path")
            library["path"] = emitted_library["path"] = _checked("a path on this machine")


def _registered_ranges(fit_id: Any) -> dict[str, tuple[float, float]]:
    """A28: each undetermined prediction's registered null-projection range over the box."""
    fits: dict[str, Any] = reference()["estimation"]["fits"]
    ranges: dict[str, tuple[float, float]] = {}
    for entry in fits.get(str(fit_id), {}).get("validation", []):
        if "null_projection_relative_range_over_box" in entry:
            low, high = entry["null_projection_relative_range_over_box"]
            ranges[entry["id"]] = (number(low), number(high))
    return ranges
