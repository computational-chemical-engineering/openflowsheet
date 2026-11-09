"""V1 on the phase-boundary form (OPT design §9 A-1, WO-5c).

**Why a second basis.** A lifted split held LIQUID or VAPOR writes its equilibrium rows
homogeneous in the incipient phase's flows, so on the single-phase branch they hold identically;
linearised there, their block over the incipient flows is singular exactly when the phase test
reaches 1 — at the bubble or dew point — with its smallest singular value proportional to the
row `a`. That is the transcritical crossing of the trivial and the two-phase branch, at every
such boundary of every flowsheet, so K04's certificate there is rank-limited (`ILL_CONDITIONED`,
`RANK_DEFICIENT`) whatever the tolerance. The held-regime state is nevertheless unique and
regular: the regime pins the incipient flows at 0, and the singular direction is that one.

**The basis.** V1 passes on `phase_boundary_form` when all of these hold at the cold re-solve x̂
(else on `certificate`, a `VERIFIED` certificate, the unchanged rule):

- (e1) the re-solve converged, and its certificate is `UNVERIFIED` with a `rank_limitation` of
  status `ILL_CONDITIONED` or `RANK_DEFICIENT`;
- (e2) its attempt signature equals the start's held signature (V4's first clause);
- (e3) the boundary set A is non-empty: the guarded (§9 A-3) lifted splits held LIQUID or VAPOR
  whose phase row has `|a/N0| ≤ τ_active` at x̂ on the float reference path (V3's evaluation);
- (e4) for each s ∈ A, `P_s = s.pinned(regime)` and `D_s = s.dropped(regime)` have equal size,
  every column of `P_s` is `== 0.0` at x̂, `D_s` holds no alias-eliminated row, and both are ids
  of the certificate's matrix;
- (e5) the boundary form B screens `NO_RANK_LOSS_DETECTED` under the unchanged `screen`, its
  identity refusal armed with the certificate's pairing identities;
- (e6) the certificate's own `grade`, given its checks, its check policy and its derivative
  evidence with B's regularity, returns `VERIFIED` — so every other check must have passed, and
  a non-registered policy (`RELAXED`) never passes this way.

**The boundary form B** is the matrix the certificate screened — `assemble_target` on the
certificate's target (the declaration at x̂) and zero-flow tuple, both rebuilt here exactly as
`verify_revision` builds them — with, for each s ∈ A in the region's split order, the rows `D_s`
and the columns `P_s` deleted by id, and `D_s` from the scaled residual. Nothing is appended.
With A = ∅ B is the certificate's matrix and its screen document equals the certificate's
`regularity` document byte for byte (gate G10a): that identity ties this path to K04.

This module imports `assemble_target`, `screen` and `grade` and edits none of them; nothing under
`verify/` or `orchestrator/` imports it (an AST test asserts it), so no ordinary certificate can
take this path. The certificate and the bundle stay `UNVERIFIED`; V1's detail says which basis
passed.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final, Literal

import numpy as np
import scipy.sparse as sp

from openflowsheet.compile.casadi_backend import compile_problem
from openflowsheet.compile.reference import state_vector
from openflowsheet.orchestrator.region import LiftedSplit, Regime
from openflowsheet.studies.nlp.phase import PhaseRow
from openflowsheet.verify.certificate import (
    BoundDeclaration,
    CheckPolicy,
    SolutionCertificate,
    _staged_splits,
    fresh_provider,
    grade,
)
from openflowsheet.verify.regularity import (
    RegularityEvidence,
    TargetAssembly,
    assemble_target,
    screen,
)
from openflowsheet.verify.zero_flow import ZeroFlowSplit

Basis = Literal["certificate", "phase_boundary_form"]
CERTIFICATE: Final = "certificate"
PHASE_BOUNDARY_FORM: Final = "phase_boundary_form"
#: (e1): the regularity statuses a boundary point's certificate can carry.
RANK_LIMITED: Final = ("ILL_CONDITIONED", "RANK_DEFICIENT")
#: The phase-row kinds of a lifted split and the regime each holds.
SPLIT_ROW_REGIME: Final[Mapping[str, Regime]] = {"split_liquid": "LIQUID", "split_vapor": "VAPOR"}


def _finite(value: Any) -> Any:
    """A document with each non-finite float named (canonical JSON has no NaN or infinity)."""
    if isinstance(value, float):
        return value if math.isfinite(value) else repr(value)
    if isinstance(value, Mapping):
        return {key: _finite(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_finite(item) for item in value]
    return value


@dataclass(frozen=True)
class CertificateTarget:
    """The certificate's own target at x̂, rebuilt as `verify_revision` builds it: the
    declaration (`BoundDeclaration`), the zero-flow tuple (ZERO_FLOW splits, then dormant
    outlets), their assembly, and the ids of the assembled matrix's rows and columns."""

    target: BoundDeclaration
    zero_flow: tuple[ZeroFlowSplit, ...]
    assembly: TargetAssembly
    row_ids: tuple[str, ...]
    column_ids: tuple[str, ...]
    #: The alias-eliminated rows (K03 §7.2's procedure on the declaration at x̂).
    eliminated: frozenset[str]


def certificate_target(
    binding: Any, revision: Mapping[str, Any], state: Mapping[str, float]
) -> CertificateTarget:
    """`verify_revision`'s target and zero-flow tuple at `state` (`verify/certificate.py`), from
    the binding's declaration and the revision's own reading of itself, and their assembly."""
    from openflowsheet.models.revision_flowsheet import component_basis, parse_revision
    from openflowsheet.orchestrator.splits import lifted_splits, split_owners
    from openflowsheet.verify.zero_flow import dormant_outlets, zero_flow_splits

    fresh = fresh_provider(component_basis(revision))
    compiled = compile_problem(binding.spec)
    target = BoundDeclaration(
        binding.spec, compiled, state, pressure_domain=fresh.describe().domain["P"]
    )
    view = parse_revision(revision)
    staged = _staged_splits(view)
    splits = lifted_splits(
        [(i.unit_id, i.model_id, i.wiring) for i in view.instances],
        view.components,
        staged=staged,
    )
    zero_flow = (
        *zero_flow_splits(view, splits, state, split_owners(staged)),
        *dormant_outlets(view, state),
    )
    assembly = assemble_target(target, state, zero_flow)
    # The assembled matrix's ids, by `assemble_target`'s own rules: the compiled rows minus the
    # alias-eliminated ones and the zero-flow forms' rows, then their label rows; every column
    # minus the zero-flow forms' columns.
    jacobian = compiled.jacobian(np.array(state_vector(target.spec, state)), target.context)
    eliminated = frozenset(row.row_id for row in target.partition.elimination.eliminated)
    removed_rows = {name for split in zero_flow for name in split.rows}
    removed_columns = {name for split in zero_flow for name in split.columns}
    rows = [name for name in jacobian.row_ids if name not in eliminated | removed_rows]
    rows += [split.label[0] for split in zero_flow if split.label is not None]
    columns = [name for name in jacobian.col_ids if name not in removed_columns]
    if assembly.matrix.shape != (len(rows), len(columns)):
        raise ValueError(
            f"defect: the certificate's matrix is {assembly.matrix.shape}, its ids "
            f"{len(rows)}x{len(columns)}"
        )
    return CertificateTarget(
        target, tuple(zero_flow), assembly, tuple(rows), tuple(columns), eliminated
    )


@dataclass(frozen=True)
class BoundaryForm:
    """B (§9 A-1): the boundary splits, the rows and columns deleted from the certificate's
    matrix, and B's screen."""

    splits: tuple[str, ...]
    rows_removed: tuple[str, ...]
    columns_removed: tuple[str, ...]
    regularity: RegularityEvidence

    def as_document(self) -> dict[str, Any]:
        return {
            "splits": list(self.splits),
            "rows_removed": list(self.rows_removed),
            "columns_removed": list(self.columns_removed),
            "regularity": _finite(self.regularity.as_document()),
        }


def boundary_form(
    certified: CertificateTarget, boundary: Sequence[tuple[LiftedSplit, Regime]]
) -> BoundaryForm:
    """B: the certificate's matrix with each boundary split's dropped rows and pinned columns
    deleted by id (in `boundary`'s order), screened by `screen` with the certificate's pairing
    identities. Raises `ValueError` for an id the matrix does not have ((e4) is checked first)."""
    rows_removed = [name for split, regime in boundary for name in split.dropped(regime)]
    columns_removed = [name for split, regime in boundary for name in split.pinned(regime)]
    missing = sorted(
        (set(rows_removed) - set(certified.row_ids))
        | (set(columns_removed) - set(certified.column_ids))
    )
    if missing:
        raise ValueError(f"the boundary form names ids the certificate's matrix lacks: {missing}")
    gone_rows, gone_columns = set(rows_removed), set(columns_removed)
    rows = [k for k, name in enumerate(certified.row_ids) if name not in gone_rows]
    columns = [k for k, name in enumerate(certified.column_ids) if name not in gone_columns]
    assembly = certified.assembly
    dense = assembly.matrix.toarray()
    matrix = sp.csc_matrix(dense[np.ix_(rows, columns)])
    residual = np.asarray(assembly.scaled_residual[rows], dtype=np.float64)
    regularity = screen(
        matrix,
        jacobian_identity=assembly.jacobian_identity,
        target_identity=assembly.residual_identity,
        scaled_residual=residual,
    )
    return BoundaryForm(
        tuple(split.unit for split, _ in boundary),
        tuple(rows_removed),
        tuple(columns_removed),
        regularity,
    )


def boundary_set(
    rows: Sequence[PhaseRow],
    values: Mapping[str, float],
    splits: Sequence[LiftedSplit],
    *,
    tau_active: float,
    unguarded: Sequence[str] = (),
) -> tuple[tuple[LiftedSplit, Regime], ...]:
    """(e3)'s A: each guarded lifted split held LIQUID or VAPOR whose phase row (a start's row,
    `values` on the float reference path at x̂) has `|a/N0| ≤ τ_active`, in `splits`' order (the
    region's), with the regime its row holds."""
    active: dict[str, Regime] = {}
    for row in rows:
        if row.kind in SPLIT_ROW_REGIME and row.unit not in unguarded:
            if abs(values[row.row_id]) <= tau_active:
                active[row.unit] = SPLIT_ROW_REGIME[row.kind]
    return tuple((split, active[split.unit]) for split in splits if split.unit in active)


@dataclass(frozen=True)
class BoundaryVerdict:
    """V1's phase-boundary judgment: passed, or the first failing clause and why; with B and
    the certificate's regularity document once they were computed."""

    passed: bool
    clause: str | None
    reason: str
    certificate_status: str | None
    target_regularity: Mapping[str, Any] | None = None
    form: BoundaryForm | None = None

    def detail(self) -> dict[str, Any]:
        """V1's detail members for this judgment (the check adds outcome and resolve fields)."""
        if self.passed:
            assert self.form is not None
            return {
                "basis": PHASE_BOUNDARY_FORM,
                "target_regularity": dict(self.target_regularity or {}),
                "boundary_form": self.form.as_document(),
            }
        failed: dict[str, Any] = {"clause": self.clause, "reason": self.reason}
        if self.form is not None:
            failed["boundary_form"] = self.form.as_document()
        return {"basis": None, PHASE_BOUNDARY_FORM: failed}


def judge(
    *,
    converged: bool,
    certificate: SolutionCertificate | None,
    policy: CheckPolicy,
    held_signature: Any,
    signature: Any,
    state: Mapping[str, float] | None,
    boundary: Callable[[], Sequence[tuple[LiftedSplit, Regime]] | str],
    target: Callable[[], CertificateTarget],
) -> BoundaryVerdict:
    """(e1)–(e6) in order; the first failing clause fails the basis. `boundary` gives A (or why
    the rows cannot be evaluated at x̂) and `target` the certificate's target; each is called only
    once the clauses before it hold."""
    status = certificate.verification_status if certificate is not None else None

    def fail(clause: str, reason: str, **found: Any) -> BoundaryVerdict:
        return BoundaryVerdict(False, clause, reason, status, **found)

    # (e1)
    if not converged or state is None or certificate is None:
        return fail("e1", "the re-solve did not converge to a certified state")
    regularity = certificate.regularity
    rank = [
        item
        for item in certificate.limitations
        if item.kind == "rank_limitation" and item.detail.get("status") in RANK_LIMITED
    ]
    if (
        status != "UNVERIFIED"
        or regularity is None
        or regularity.status not in RANK_LIMITED
        or not rank
    ):
        return fail(
            "e1",
            f"certificate {status}, regularity "
            f"{regularity.status if regularity is not None else None}: not a rank limitation",
        )
    target_regularity = _finite(regularity.as_document())
    # (e2)
    if tuple(held_signature or ()) != tuple(signature or ()):
        return fail("e2", "the re-solve's attempt signature is not the start's held signature")
    # (e3)
    found = boundary()
    if isinstance(found, str):
        return fail("e3", f"phase rows not evaluable at the re-solve: {found}")
    if not found:
        return fail("e3", "no guarded LIQUID/VAPOR split's phase row is active at the re-solve")
    # (e4)
    certified = target()
    for split, regime in found:
        pinned, dropped = split.pinned(regime), split.dropped(regime)
        if len(pinned) != len(dropped):
            return fail("e4", f"{split.unit}: |P| = {len(pinned)} ≠ |D| = {len(dropped)}")
        nonzero = [name for name in pinned if not state[name] == 0.0]
        if nonzero:
            return fail("e4", f"{split.unit}: pinned columns not 0.0 at the re-solve: {nonzero}")
        aliased = sorted(set(dropped) & certified.eliminated)
        if aliased:
            return fail("e4", f"{split.unit}: dropped rows are alias-eliminated: {aliased}")
        missing = sorted(
            (set(dropped) - set(certified.row_ids)) | (set(pinned) - set(certified.column_ids))
        )
        if missing:
            return fail("e4", f"{split.unit}: ids not in the certificate's matrix: {missing}")
    # (e5)
    form = boundary_form(certified, found)
    if form.regularity.status != "NO_RANK_LOSS_DETECTED":
        return fail(
            "e5",
            f"the boundary form screens {form.regularity.status}",
            target_regularity=target_regularity,
            form=form,
        )
    # (e6)
    if policy.sha256 != certificate.check_policy_sha256:
        return fail(
            "e6",
            "the check policy is not the certificate's",
            target_regularity=target_regularity,
            form=form,
        )
    derivative_ok = all(
        check.result == "pass"
        for check in certificate.checks
        if check.category == "derivative_witness"
    )
    graded, _ = grade(
        certificate.checks,
        policy=policy,
        regularity_status=form.regularity.status,
        regularity_reason=form.regularity.ill_conditioned_reason,
        derivative_ok=derivative_ok,
    )
    if graded != "VERIFIED":
        return fail(
            "e6",
            f"the certificate's grade on the boundary form is {graded}",
            target_regularity=target_regularity,
            form=form,
        )
    return BoundaryVerdict(True, None, "", status, target_regularity, form)
