"""Basis functions `M05-basis-v1`: TRF's b(w) for every `ExternalFunction` of a projection (M05
design note §6.6, §16.4, §16.5; ADR 0038 D7 as amended; R-264, R-277).

A basis is mandatory (R-277: `trf.run_trf` refuses a missing one). This module builds the two
the note registers for M05's own runs:

- **Property EFs: the affine Taylor model at w₀**, b(w) = (y_k(w₀) + ∇y_k(w₀)ᵀ(w − w₀)) / s_k in
  the EF's scaled units, from one evaluation of each block's values and Jacobian at x₀ — the blocks
  called directly, never through their holders, so the holders' ledgers hold the run's requests
  only (as `Projection.set_state`). Because b is affine, TRF's r_k is exactly the Taylor model at
  w_k; the basis changes only the PMP, where it replaces b ≡ 0.
- **External links: the affine Taylor model at w₀** (R-277; it was the constant d(w₀)), from the
  link holder's value and Jacobian at the start inlet. For a finite-difference truth the Jacobian
  is the holder's `M05-fd-v1` gradient with its points labelled `basis_fd_point` (§8.3: n_in of
  them); after the study's gradient-quality check at the same w₀ they are memo or store hits.
  For a truth with an analytic gradient it is that gradient. These are ledgered requests: a
  link's truth is the expensive model, and the study accounts for every call to it.
- `constant_link_basis`: b = d(w₀)/s. It was stage A's basis; R-408 replaced it there by the
  promoted quadratic (a constant link basis freezes X̂ and ΔT̂ in the PMP, probe P14 b).
- **External links with a promoted M04 surrogate of the bound parent: its quadratic**
  (`surrogate_link_basis`, `promoted_basis`; §6.6, R-408), for stage A and for a promoted stage C.
  b_k(w) = β_kᵀφ(z(w)) / s_k, compiled from the manifest's coefficients on the clone's inlet
  arguments: u(s) = (T, P, n_H₂/n_N₂, y_NH₃, y_Ar, y_CH₄, n_tot/N_tubes) with n_tot summed left to
  right, z = (u − c)/h on the manifest's scaling, φ M04's 36 terms in M04's order (M04 spec §3.1,
  §3.4). The expression is M04's `predict` with the arithmetic of the arguments in place of
  `math.fsum`; WO-4's acceptance holds it to `predict` within 1e-14 relative at M04's J1–J3. It
  asks the truth nothing, so it adds no ledger entry.

**`M05-basis-v2`** (R-400, design note §20.1) is v1 with the truth's curvature along the decision
path added to every link EF: `m05_basis_v2`, for every stage-C run without a promoted surrogate.
With n_d = 1 and t = δ/h, M02's inner solve with the reactor pinned at the run's start coupling is
solved at d₀ ± t (or one-sided towards the interior at a bound), the link holder is asked d(w_i)
there (`basis_curvature_point`, the run's requests), and c_k = (α₁R_k(w₁) + α₂R_k(w₂))/t² from the
remainder R_k(w) = d_k(w) − d_k(w₀) − g_kᵀ(w − w₀) enters b_k as ½c_k p(w)², p the M-weighted
coordinate along the path direction v. At w₀ the added term and its gradient are exact zeros, so
b(w₀) and ∇b(w₀) are v1's bitwise. Any failure but a budget refusal leaves the link on v1's affine
basis with `status: failed` and the limitation `basis_without_curvature`.

Each basis is built on `ef_expr.args`, the clone's variables (`EFBasis.build`, never the original
model's), and is frozen for the run (blueprint L427; §20.1 "Freezing, corrected").

This module imports neither Pyomo nor any truth: the expressions are built by the arithmetic of
the arguments TRF hands it.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Any, Final, Protocol

from openflowsheet.studies.surrogate.plan import DIMENSION
from openflowsheet.studies.surrogate.quadratic import PAIRS, QuadraticSurrogate
from openflowsheet.studies.trust_region.holders import (
    BASIS_CURVATURE_POINT,
    BASIS_FD_POINT,
    TruthRefused,
)
from openflowsheet.studies.trust_region.trf_state import (
    TRF_CONFIGURATION_REFUSED,
    EFBasis,
    TrfConfigurationRefusedError,
)

if TYPE_CHECKING:
    from openflowsheet.studies.trust_region.projection import Projection

__all__ = [
    "BASIS_POLICY_ID",
    "BASIS_POLICY_V2",
    "BASIS_WITHOUT_CURVATURE",
    "BasisSet",
    "DecisionPath",
    "affine",
    "affine_block_basis",
    "affine_link_basis",
    "constant",
    "constant_link_basis",
    "curvature",
    "curvature_link_basis",
    "m05_basis",
    "m05_basis_v2",
    "promoted_basis",
    "surrogate_expression",
    "surrogate_link_basis",
]

BASIS_POLICY_ID: Final = "M05-basis-v1"
BASIS_POLICY_V2: Final = "M05-basis-v2"
#: R-400 step 9: the candidate limitation of a run whose link basis fell back to v1's affine one.
BASIS_WITHOUT_CURVATURE: Final = "basis_without_curvature"


def affine(value: float, gradient: Sequence[float], w0: Sequence[float], scale: float) -> EFBasis:
    """b(w) = (value + Σ_j gradient_j (w_j − w0_j)) / scale, an `affine_taylor` basis. At w = w₀
    every term is an exact zero, so b(w₀) = value / scale bitwise (scale is a power of two).

    Terms are built for variable arguments only: an argument that is a float is an eliminated
    zero flow, the constant +0.0 (R-296), whose term is the exact zero it has at w₀ — so TRF's
    Taylor model has no column for it. A float that differs from its w0_j is a `ValueError`."""
    frozen_gradient = tuple(float(entry) for entry in gradient)
    frozen_w0 = tuple(float(entry) for entry in w0)
    frozen_value = float(value)
    frozen_scale = float(scale)

    def build(args: Sequence[Any]) -> Any:
        terms = list(zip(frozen_gradient, args, frozen_w0, strict=True))
        moved = [a for _, a, w in terms if isinstance(a, float) and a != w]
        if moved:
            raise ValueError(f"a constant argument {moved!r} differs from its start value")
        variable = [(g, a, w) for g, a, w in terms if not isinstance(a, float)]
        return (frozen_value + sum(g * (a - w) for g, a, w in variable)) / frozen_scale

    return EFBasis("affine_taylor", build)


def constant(value: float, scale: float) -> EFBasis:
    """b ≡ value / scale, a `constant` basis."""
    frozen = float(value) / float(scale)

    def build(args: Sequence[Any]) -> float:
        return frozen

    return EFBasis("constant", build)


def _start(projection: Projection) -> dict[str, float]:
    """x₀ as the projection's model holds it (its `x`, which TRF's clone starts from, and +0.0
    for each eliminated zero flow, R-296)."""
    return projection.state_of()


def affine_block_basis(projection: Projection) -> dict[str, EFBasis]:
    """Every property-block EF's affine Taylor basis at x₀ (module docstring)."""
    spec = projection.spec
    start = _start(projection)
    blocks = {block.block_id: block for block in spec.blocks}
    produced: dict[str, tuple[Sequence[float], list[list[float]]]] = {}
    basis: dict[str, EFBasis] = {}
    for entry in projection.source_map["block_outputs"]:
        block = blocks[entry["block_id"]]
        w0 = [start[name] for name in entry["input_variable_ids"]]
        if block.block_id not in produced:
            dense = [[0.0] * len(w0) for _ in block.output_ids]
            for row, column, value in block.jacobian(w0):
                dense[row][column] += float(value)
            produced[block.block_id] = (block.values(w0), dense)
        values, jacobian = produced[block.block_id]
        k = list(block.output_ids).index(entry["output_id"])
        basis[entry["ef"]] = affine(float(values[k]), jacobian[k], w0, entry["output_scale"])
    return basis


def _links(projection: Projection) -> Mapping[str, tuple[Any, list[float], list[dict[str, Any]]]]:
    """Each link holder with its start inlet and its source-map entries (X, then ΔT)."""
    start = _start(projection)
    holders = {holder.name: holder for holder in projection.holders}
    found: dict[str, tuple[Any, list[float], list[dict[str, Any]]]] = {}
    for entry in projection.source_map["external_links"]:
        name = f"link:{entry['unit_id']}"
        if name not in found:
            found[name] = (holders[name], [start[i] for i in entry["input_variable_ids"]], [])
        found[name][2].append(entry)
    return found


def affine_link_basis(projection: Projection) -> dict[str, EFBasis]:
    """Every external link EF's affine Taylor basis at the start inlet w₀ (R-277), from the link
    holder's value and Jacobian there (module docstring: the Jacobian's FD points, if any, are
    `basis_fd_point` requests). A refusal raises the holder's `TruthRefused`."""
    basis: dict[str, EFBasis] = {}
    for holder, w0, entries in _links(projection).values():
        values = holder.request_values(w0)
        jacobian = holder.request_jacobian(w0, purpose=BASIS_FD_POINT)
        for coordinate, entry in enumerate(entries):
            basis[entry["ef"]] = affine(
                values[coordinate], jacobian[coordinate], w0, entry["output_scale"]
            )
    return basis


def constant_link_basis(projection: Projection) -> dict[str, EFBasis]:
    """Every external link EF's constant basis d(w₀)/s (stage A, §6.6)."""
    basis: dict[str, EFBasis] = {}
    for holder, w0, entries in _links(projection).values():
        values = holder.request_values(w0)
        for coordinate, entry in enumerate(entries):
            basis[entry["ef"]] = constant(values[coordinate], entry["output_scale"])
    return basis


def surrogate_expression(
    coefficients: Sequence[float],
    surrogate: QuadraticSurrogate,
    n_tubes: float,
    args: Sequence[Any],
) -> Any:
    """β·φ(z(w)) on the inlet arguments w = (n₁…n₅, T, P) (module docstring), in the arithmetic of
    the arguments: Pyomo expressions on the clone's variables, or floats. A float flow argument is
    an eliminated zero flow (R-296) and enters as the constant it is."""
    n, temperature, pressure = args[:5], args[5], args[6]
    total = (((n[0] + n[1]) + n[2]) + n[3]) + n[4]
    u = (
        temperature,
        pressure,
        n[0] / n[1],
        n[2] / total,
        n[3] / total,
        n[4] / total,
        total / n_tubes,
    )
    scaling = surrogate.scaling
    z = [(u[k] - scaling.centre[k]) / scaling.half_width[k] for k in range(DIMENSION)]
    phi = [1.0, *z, *(z[i] * z[j] for i, j in PAIRS)]
    return sum(float(b) * f for b, f in zip(coefficients, phi, strict=True))


def surrogate_link_basis(
    projection: Projection, surrogate: QuadraticSurrogate, n_tubes: float
) -> dict[str, EFBasis]:
    """Every external link EF's promoted quadratic, b_k = β_kᵀφ(z(w)) / s_k (R-408, module
    docstring): X from `coefficients_x`, ΔT from `coefficients_dt`, in the source map's order."""
    frozen_tubes = float(n_tubes)
    basis: dict[str, EFBasis] = {}
    for _, _, entries in _links(projection).values():
        if [entry["coordinate"] for entry in entries] != ["X", "dT"]:
            raise ValueError(f"a link's outputs are (X, dT), got {entries!r}")
        for entry, coefficients in zip(
            entries, (surrogate.coefficients_x, surrogate.coefficients_dt), strict=True
        ):
            basis[entry["ef"]] = _surrogate_basis(
                coefficients, surrogate, frozen_tubes, float(entry["output_scale"])
            )
    return basis


def _surrogate_basis(
    coefficients: Sequence[float], surrogate: QuadraticSurrogate, n_tubes: float, scale: float
) -> EFBasis:
    def build(args: Sequence[Any]) -> Any:
        return surrogate_expression(coefficients, surrogate, n_tubes, args) / scale

    return EFBasis("surrogate", build)


def promoted_basis(
    projection: Projection, *, surrogate: QuadraticSurrogate, n_tubes: float
) -> dict[str, EFBasis]:
    """§6.6 with a promoted surrogate (stage A, and stage C when the bound parent's surrogate is
    promoted): the affine Taylor basis for every property EF, the promoted quadratic for every
    link EF (R-408)."""
    links = surrogate_link_basis(projection, surrogate, n_tubes)
    return {**affine_block_basis(projection), **links}


def m05_basis(projection: Projection) -> dict[str, EFBasis]:
    """`M05-basis-v1` without a promoted surrogate: the affine Taylor basis for every EF."""
    return {**affine_block_basis(projection), **affine_link_basis(projection)}


# == M05-basis-v2 (R-400) ==========================================================================


class DecisionPath(Protocol):
    """R-400 step 4: M02's inner solve with the reactor pinned at the run's start coupling, at a
    decision (`C1Parent.decision_path`). `state_at` returns the converged state by variable id and
    the solve's outcome, or `None` and the outcome when it failed; it makes no reactor call and
    writes no ledger entry. `tolerance` is the decision's tolerance δ, in its own units."""

    tolerance: float

    def state_at(
        self, decisions: Mapping[str, float]
    ) -> tuple[Mapping[str, float] | None, str]: ...


class BasisSet(dict[str, EFBasis]):
    """A run's basis by EF name, with `record` — the run's `basis` block for a v2 basis (`None` for
    v1) — and the candidate `limitations` the basis adds."""

    def __init__(
        self,
        basis: Mapping[str, EFBasis],
        record: Mapping[str, Any] | None = None,
        limitations: Sequence[str] = (),
    ) -> None:
        super().__init__(basis)
        self.record = record
        self.limitations = tuple(limitations)


def curvature(
    value: float,
    gradient: Sequence[float],
    w0: Sequence[float],
    scale: float,
    c: float,
    direction: Sequence[float],
    weights: Sequence[float],
) -> EFBasis:
    """b(w) = (value + Σ_j g_j (w_j − w0_j) + ½ c p(w)²) / scale, with
    p(w) = Σ_j m_j v_j (w_j − w0_j) / Σ_j m_j v_j² (R-400 steps 7 and 8), an `affine_curvature`
    basis. At w₀ every added term is an exact zero, so b(w₀) and ∇b(w₀) are `affine`'s bitwise.
    A float argument (an eliminated zero flow, R-296) takes no term, as in `affine`; a non-zero
    v_j for one, or a float that differs from its w0_j, is a `ValueError`."""
    frozen_gradient = tuple(float(entry) for entry in gradient)
    frozen_w0 = tuple(float(entry) for entry in w0)
    frozen_v = tuple(float(entry) for entry in direction)
    frozen_m = tuple(float(entry) for entry in weights)
    frozen_value, frozen_scale, frozen_c = float(value), float(scale), float(c)
    norm = sum(m * v * v for m, v in zip(frozen_m, frozen_v, strict=True))
    if not norm > 0.0:
        raise ValueError(f"the path direction has no weighted length ({norm!r})")

    def build(args: Sequence[Any]) -> Any:
        terms = list(zip(frozen_gradient, args, frozen_w0, frozen_v, frozen_m, strict=True))
        moved = [a for _, a, w, _, _ in terms if isinstance(a, float) and a != w]
        if moved:
            raise ValueError(f"a constant argument {moved!r} differs from its start value")
        along = [v for _, a, _, v, _ in terms if isinstance(a, float) and v != 0.0]
        if along:
            raise ValueError(f"the path moves an eliminated zero flow (v = {along!r})")
        variable = [(g, a, w, v, m) for g, a, w, v, m in terms if not isinstance(a, float)]
        taylor = frozen_value + sum(g * (a - w) for g, a, w, _, _ in variable)
        p = sum(m * v * (a - w) for _, a, w, v, m in variable) / norm
        return (taylor + 0.5 * frozen_c * p**2) / frozen_scale

    return EFBasis("affine_curvature", build)


def _stencil(d0: float, t: float) -> tuple[str, float, float, float, float, int]:
    """R-400 step 3: (name, d₁, d₂, α₁, α₂, σ). Central when d₀ ± t lies in the box; otherwise
    one-sided towards the interior, σ = +1 at the lower side and −1 at the upper."""
    if d0 - t >= -1.0 and d0 + t <= 1.0:
        return "central", d0 + t, d0 - t, 1.0, 1.0, 0
    sigma = 1 if d0 - t < -1.0 else -1
    name = "forward" if sigma > 0 else "backward"
    return name, d0 + sigma * t, d0 + 2 * sigma * t, -2.0, 1.0, sigma


def curvature_link_basis(projection: Projection, path: DecisionPath) -> BasisSet:
    """Every external link EF's `M05-basis-v2` basis at the run's start (module docstring;
    R-400 steps 1-10), with the run's `basis` block and limitation. A budget refusal raises the
    holder's `TruthRefused`; any other failure leaves that link on v1's affine basis."""
    if len(projection.decisions) != 1:
        raise TrfConfigurationRefusedError(
            [f"{TRF_CONFIGURATION_REFUSED}(basis_curvature_nd:{len(projection.decisions)})"]
        )
    half_width = projection.half_widths[0]
    t = path.tolerance / half_width
    d0 = float(projection.model.d[0].value)
    name, d1, d2, alpha1, alpha2, sigma = _stencil(d0, t)
    basis: dict[str, EFBasis] = {}
    links: dict[str, Any] = {}
    limitations: list[str] = []
    for holder, w0, entries in _links(projection).values():
        values = holder.request_values(w0)
        jacobian = holder.request_jacobian(w0, purpose=BASIS_FD_POINT)
        ids = entries[0]["input_variable_ids"]
        scales = [projection.scaling.column[i] for i in ids]
        record: dict[str, Any] = {
            "stencil": name,
            "t": t,
            "d_points": [d1, d2],
            "solves": [],
            "w_points": [],
            "v": None,
            "c": None,
            "status": "ok",
            "reason": None,
            "noise_ratio": None,
        }
        remainders, inlets, reason = _link_curvature(
            projection, path, holder, w0, values, jacobian, ids, (d1, d2), record
        )
        c: list[float] | None = None
        v: list[float] | None = None
        if reason is None:
            c, v, reason = _finish(
                remainders, inlets, scales, (alpha1, alpha2, t, sigma), record, w0
            )
        if reason is not None:
            record.update(status="failed", reason=reason, c=[0.0] * len(entries))
            limitations.append(BASIS_WITHOUT_CURVATURE)
            for coordinate, entry in enumerate(entries):
                basis[entry["ef"]] = affine(
                    values[coordinate], jacobian[coordinate], w0, entry["output_scale"]
                )
        else:
            assert c is not None and v is not None
            weights = [1.0 / (scale * scale) for scale in scales]
            for coordinate, entry in enumerate(entries):
                basis[entry["ef"]] = curvature(
                    values[coordinate],
                    jacobian[coordinate],
                    w0,
                    entry["output_scale"],
                    c[coordinate],
                    v,
                    weights,
                )
        links[holder.name] = record
    return BasisSet(
        basis,
        {"policy": BASIS_POLICY_V2, "links": links},
        tuple(dict.fromkeys(limitations)),
    )


def _link_curvature(
    projection: Projection,
    path: DecisionPath,
    holder: Any,
    w0: Sequence[float],
    values: Sequence[float],
    jacobian: Sequence[Sequence[float]],
    ids: Sequence[str],
    points: tuple[float, float],
    record: dict[str, Any],
) -> tuple[list[float] | None, list[list[float]] | None, str | None]:
    """Steps 4-6: the path points' inlets w₁, w₂ (the pinned inner solve's link inputs) and the
    remainders R_k(w₁)..., R_k(w₂)... there, or the failure reason (a failed solve, a refusal
    other than a budget one, which raises)."""
    parameter = projection.decisions[0].parameter_id
    inlets: list[list[float]] = []
    for d in points:
        state, outcome = path.state_at({parameter: projection.parameter_value(0, d)})
        record["solves"].append(outcome)
        if state is None:
            return None, None, f"inner_solve:{outcome}"
        inlets.append([float(state[i]) for i in ids])
    record["w_points"] = [list(w) for w in inlets]
    remainders: list[float] = []
    for w in inlets:
        try:
            at = holder.request_values(w, purpose=BASIS_CURVATURE_POINT)
        except TruthRefused as refusal:
            if refusal.status == "budget":
                raise
            return None, None, f"refused:{refusal.code}"
        for k in range(len(values)):
            linear = sum(g * (wj - w0j) for g, wj, w0j in zip(jacobian[k], w, w0, strict=True))
            remainders.append(at[k] - values[k] - linear)
    return remainders, inlets, None


def _finish(
    remainders: list[float] | None,
    inlets: list[list[float]] | None,
    scales: Sequence[float],
    alphas_t: tuple[float, float, float, int],
    record: dict[str, Any],
    w0: Sequence[float],
) -> tuple[list[float] | None, list[float] | None, str | None]:
    """Steps 6-7: c_k = (α₁R_k(w₁) + α₂R_k(w₂))/t² and the direction v; or the failure reason."""
    assert remainders is not None and inlets is not None
    alpha1, alpha2, t, sigma = alphas_t
    n_out = len(remainders) // 2
    c = [(alpha1 * remainders[k] + alpha2 * remainders[n_out + k]) / (t * t) for k in range(n_out)]
    w1, w2 = inlets
    if sigma == 0:
        v = [(a - b) / (2 * t) for a, b in zip(w1, w2, strict=True)]
    else:
        v = [sigma * (4 * a - 3 * z - b) / (2 * t) for a, z, b in zip(w1, w0, w2, strict=True)]
    record.update(v=v, c=c)
    if not sum(vj * vj / (s * s) for vj, s in zip(v, scales, strict=True)) > 0.0:
        return None, None, "zero_direction"
    if not all(math.isfinite(ck) for ck in c):
        return None, None, "non_finite_curvature"
    return c, v, None


def m05_basis_v2(projection: Projection, *, path: DecisionPath) -> BasisSet:
    """`M05-basis-v2` without a promoted surrogate (R-400): v1's affine Taylor basis for every
    property EF, the curvature basis for every link EF."""
    links = curvature_link_basis(projection, path)
    return BasisSet({**affine_block_basis(projection), **links}, links.record, links.limitations)
