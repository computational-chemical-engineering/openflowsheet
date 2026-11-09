"""OPT WO-1: the NLP host protocol and M03's SYN-001 path behind it (OPT design §4.1, gate G2).

`Syn001NlpHost` wraps M03's study functions verbatim: its certified point is `solve_certified` at
`with_pinned`, its held system the tear plan's 47 kept rows over every column, its regimes
`split_regimes`, its sensitivity `syn001_sensitivity`. The one thing it does differently is the
twin: compiled once from the base flowsheet and reused at every start, where M03 compiled one per
start from the start's pinned flowsheet. That is inert only because the decisions are symbolic in
the twin, so both are one function — checked here bitwise — and because `FullSpaceNlp` counts
property calls from its own construction. The records themselves are compared byte for byte by
`scripts/opt_m03_dump.py` (G2), not here.
"""

from __future__ import annotations

from functools import cache
from types import MappingProxyType

import numpy as np
import pytest
from m03_support import flowsheet, nlp_formulation

from openflowsheet.compile.casadi_backend import compile_parametric_twin
from openflowsheet.orchestrator.tear import Syn001TearProblem
from openflowsheet.studies.nlp.closure import SolverAvailability, optimization_readiness
from openflowsheet.studies.nlp.formulation import Decision, FullSpaceNlp, NlpFormulation
from openflowsheet.studies.nlp.host import (
    CertifiedPoint,
    DecisionRefusedError,
    HeldSystem,
    NlpHost,
    Syn001NlpHost,
    as_host,
)
from openflowsheet.studies.nlp.verification import verify_candidate
from openflowsheet.studies.syn001 import solve_certified, with_pinned


def available() -> SolverAvailability:
    return SolverAvailability(True, "test double: the audited extra is present")


@cache
def start_point() -> tuple[Syn001NlpHost, CertifiedPoint]:
    formulation = nlp_formulation()
    host = Syn001NlpHost(flowsheet({}))
    return host, host.certify(formulation.decision_values(formulation.starts[0]))


def test_the_syn001_host_is_an_nlp_host_and_a_flowsheet_becomes_one() -> None:
    host: NlpHost = Syn001NlpHost(flowsheet({}))
    assert host.kind == "syn001-tear"
    assert host.require_every_start is True
    assert as_host(host) is host
    wrapped = as_host(flowsheet({}))
    assert isinstance(wrapped, Syn001NlpHost)
    assert wrapped.model_record() == host.model_record()
    assert host.phase_rows(start_point()[1]) is None


def test_certify_is_m03s_certified_solve_at_the_pinned_inputs() -> None:
    formulation = nlp_formulation()
    values = formulation.decision_values(formulation.starts[0])
    _, point = start_point()
    solve = solve_certified(with_pinned(flowsheet({}), values))
    assert point.verified and solve.verified
    assert (point.outcome, point.message) == (solve.outcome, solve.message)
    assert point.state == solve.final_state
    assert point.certificate is not None and solve.certificate is not None
    assert point.certificate.certificate_id == solve.certificate.certificate_id
    assert dict(point.parameters) == values
    assert point.signature is None and point.bundle_ref is None
    spec = with_pinned(flowsheet({}), values).spec()
    assert point.spec is not None
    for member in ("label", "variable_ids", "equation_ids", "parameters"):
        assert getattr(point.spec, member) == getattr(spec, member)


def test_a_refused_pin_is_a_typed_refusal_and_verification_still_raises_m03s_error() -> None:
    host = Syn001NlpHost(flowsheet({}))
    with pytest.raises(DecisionRefusedError, match="cannot be moved alone") as raised:
        host.certify({"U-FLASH.P_spec": 1.0})
    assert type(raised.value.__cause__) is ValueError
    formulation = nlp_formulation()
    moved = NlpFormulation(
        problem_id="P",
        decisions=(Decision("U-FLASH.P_spec", 0.5, 2.0, 1.0),),
        objective=formulation.objective,
        constraints=formulation.constraints,
        starts=((1.0,),),
    )
    with pytest.raises(ValueError, match="cannot be moved alone") as error:
        verify_candidate(flowsheet({}), moved, (1.0,), regimes={})
    assert type(error.value) is ValueError


def test_the_held_system_is_every_row_but_the_two_alias_rows_over_every_column() -> None:
    host, point = start_point()
    system = host.held_system(point)
    assert host.held_system(point) is system
    tear = Syn001TearProblem(with_pinned(flowsheet({}), dict(point.parameters)))
    eliminated = tuple(row.row_id for row in tear.partition.elimination.eliminated)
    assert system.eliminated == eliminated and len(eliminated) == 2
    assert system.rows == tuple(n for n in tear.spec.equation_ids if n not in eliminated)
    assert (len(system.rows), len(system.free)) == (47, 47)
    assert system.free == tuple(tear.spec.variable_ids)
    assert not system.held and system.labels == ()


def test_a_held_system_must_be_square_alias_free_and_partition_the_columns() -> None:
    spec = start_point()[1].spec
    assert spec is not None
    rows, columns = spec.equation_ids, spec.variable_ids
    empty: MappingProxyType[str, float] = MappingProxyType({})
    with pytest.raises(ValueError, match="not square"):
        HeldSystem(spec, rows, columns, empty, (), ())
    with pytest.raises(ValueError, match="alias rows"):
        HeldSystem(spec, rows[:47], columns, empty, (), (rows[0],))
    with pytest.raises(ValueError, match="partition"):
        HeldSystem(spec, rows[:47], columns, MappingProxyType({columns[0]: 1.0}), (), ())
    with pytest.raises(ValueError, match="not in the problem"):
        HeldSystem(spec, (*rows[:46], "NO-SUCH-ROW"), columns, empty, (), ())


def test_regimes_are_the_two_tp_splits_and_declare_readinesss_regimes() -> None:
    host, point = start_point()
    record = host.regimes(point)
    assert [split.kind for split in record.splits] == ["TP", "TP"]
    readiness = optimization_readiness(nlp_formulation(), flowsheet({}), solver_probe=available)
    assert record.declared() == readiness.starts[0].regimes


def test_one_twin_per_decision_ids_is_the_pinned_starts_twin_bitwise() -> None:
    formulation = nlp_formulation()
    host = Syn001NlpHost(flowsheet({}))
    ids = formulation.decision_ids
    assert host.twin(ids) is host.twin(list(ids))
    for start in formulation.starts:
        decisions = formulation.decision_values(start)
        point = host.certify(decisions)
        assert point.state is not None and point.spec is not None
        pinned = compile_parametric_twin(point.spec, ids)
        x = np.array([point.state[name] for name in point.spec.variable_ids])
        for move in (1.0, 1.0 + 1e-6):
            at = {name: value * move for name, value in decisions.items()}
            shared, own = host.twin(ids), pinned
            assert np.asarray(shared.residual(x, at)).tobytes() == (
                np.asarray(own.residual(x, at)).tobytes()
            )
            for jacobian in ("jacobian_x", "jacobian_p"):
                a, b = getattr(shared, jacobian)(x, at), getattr(own, jacobian)(x, at)
                assert np.asarray(a.data).tobytes() == np.asarray(b.data).tobytes()
                assert list(a.indices) == list(b.indices) and list(a.indptr) == list(b.indptr)


def test_the_full_space_from_a_host_point_is_m03s_and_counts_from_its_construction() -> None:
    formulation = nlp_formulation()
    host, point = start_point()
    start = formulation.starts[0]
    pinned = with_pinned(flowsheet({}), formulation.decision_values(start))
    assert point.state is not None
    legacy = FullSpaceNlp(pinned, formulation, point.state, start)
    hosted = FullSpaceNlp(host, formulation, point, start)
    assert hosted.as_document() == legacy.as_document()
    z = legacy.initial_point()
    assert hosted.initial_point().tobytes() == z.tobytes()
    assert hosted.equality_residual(z).tobytes() == legacy.equality_residual(z).tobytes()
    a, b = hosted.equality_jacobian(z), legacy.equality_jacobian(z)
    assert a.data.tobytes() == b.data.tobytes() and (a.indices == b.indices).all()
    assert hosted.property_calls() == legacy.property_calls() > 0
    again = FullSpaceNlp(host, formulation, point, start)
    assert again.twin is hosted.twin
    assert again.property_calls() == 0


def test_a_mapping_state_needs_the_syn001_host() -> None:
    formulation = nlp_formulation()
    _, point = start_point()
    assert point.state is not None

    class Foreign:
        """Any host but SYN-001's (the revision host, WO-2)."""

    with pytest.raises(TypeError, match="certified point"):
        FullSpaceNlp(Foreign(), formulation, point.state, formulation.starts[0])  # type: ignore[arg-type]
