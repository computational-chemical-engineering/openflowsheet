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
- `constant_link_basis`: b = d(w₀)/s, stage A's basis (§6.6: the surrogate as truth is already
  exact and cheap).

Each basis is built on `ef_expr.args`, the clone's variables (`EFBasis.build`, never the original
model's), and is frozen for the run and the study (blueprint L427, L437).

This module imports neither Pyomo nor any truth: the expressions are built by the arithmetic of
the arguments TRF hands it.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Any, Final

from openflowsheet.studies.trust_region.holders import BASIS_FD_POINT
from openflowsheet.studies.trust_region.trf_state import EFBasis

if TYPE_CHECKING:
    from openflowsheet.studies.trust_region.projection import Projection

__all__ = [
    "BASIS_POLICY_ID",
    "affine",
    "affine_block_basis",
    "affine_link_basis",
    "constant",
    "constant_link_basis",
    "m05_basis",
]

BASIS_POLICY_ID: Final = "M05-basis-v1"


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


def m05_basis(projection: Projection) -> dict[str, EFBasis]:
    """`M05-basis-v1` without a promoted surrogate: the affine Taylor basis for every EF."""
    return {**affine_block_basis(projection), **affine_link_basis(projection)}
