"""T06 F4 WO3: the restart initializer `traversal-G0-pass8-v1` (`revision.restart_start`).

Design note `docs/design/T06-F4-recovery.md` §5.3 (ADR 0015 D2): the traversal from dormant torn
streams continued to eight passes; a pass `j ≥ 3` a unit refuses truncates the sequence to
`j − 1`, recorded; a reconstruction the kernel refuses at a kept pass `≥ 3` falls back one pass;
passes 1 and 2 must succeed. The expectations are the note's *measured* ones (§2, WO3): C1 is
acyclic (one pass), C2 keeps all eight, NET-02 keeps eight, and C3X fails as `traversal_start`
does. C3 keeps all eight since ADR 0017 (T06 spec A77): its pass 4 was refused in `U-MIX`
(finding F6, SYN-001's flash at a stream within one rounding of its bubble point) until the
provider was fixed; the truncation that refusal exercised is now exercised by an injected one.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from typing import Any

import pytest
import yaml
from conftest import REPO_ROOT
from t05_w12_support import bind
from test_t05_w11_cases import case_document

from openflowsheet.application.revision_binding import RevisionBinding
from openflowsheet.compile.casadi_backend import CasadiCompiledProblem
from openflowsheet.models.revision_flowsheet import FlowsheetPass
from openflowsheet.orchestrator import revision

NET02 = REPO_ROOT / "benchmarks" / "t06" / "cases" / "SYN-001-T06-NET02.yaml"


def _binding(case: str) -> RevisionBinding:
    if case == "NET-02":
        return bind(yaml.safe_load(NET02.read_text(encoding="utf-8")))
    return bind(case_document(case))


def _restart(case: str) -> revision.RestartStart | revision.InitialStateFailure:
    binding = _binding(case)
    return revision.restart_start(binding.flowsheet, binding.spec.variable_ids)


def _started(case: str) -> revision.RestartStart:
    start = _restart(case)
    assert isinstance(start, revision.RestartStart), start
    return start


def test_wo3_the_initializer_id_names_its_pass_count() -> None:
    assert revision.RESTART_INITIALIZER_ID == "traversal-G0-pass8-v1"
    assert revision.RESTART_PASSES == 8


def test_wo3_c1_is_acyclic_and_its_restart_start_is_traversal_start() -> None:
    binding = _binding("SYN-001-UL-C1")
    registered = revision.traversal_start(binding.flowsheet, binding.spec.variable_ids)
    start = revision.restart_start(binding.flowsheet, binding.spec.variable_ids)
    assert isinstance(registered, revision.TraversalStart)
    assert isinstance(start, revision.RestartStart)
    assert (start.passes_used, start.rejected) == (1, ())
    assert list(start.values) == list(binding.spec.variable_ids)
    assert {k: v.hex() for k, v in start.values.items()} == {
        k: v.hex() for k, v in registered.values.items()
    }
    assert start.band_routes == registered.band_routes


def test_wo3_c2_keeps_all_eight_passes() -> None:
    start = _started("SYN-001-UL-C2")
    assert (start.passes_used, start.rejected) == (8, ())


def test_wo3_c3_keeps_all_eight_passes() -> None:
    """T06 spec A77 (ADR 0017): F6 no longer refuses pass 4 in `U-MIX`."""
    start = _started("SYN-001-UL-C3")
    assert (start.passes_used, start.rejected) == (8, ())


def test_wo3_a_unit_refusing_pass_j_truncates_the_sequence_to_j_minus_1(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """§5.3: a pass `j ≥ 3` a unit refuses ends the sequence at pass `j − 1`, recorded with the
    unit's status and first message line. C3's pass 4 as F6 refused it before ADR 0017, injected:
    the fourth traversal (pass 4) comes back refused by `U-MIX`."""
    traverse = revision.RevisionFlowsheet.traverse
    calls: list[int] = []

    def refusing_pass_4(self: Any, *args: Any, **kwargs: Any) -> FlowsheetPass:
        result = traverse(self, *args, **kwargs)
        calls.append(1)
        if len(calls) == 4:
            return replace(
                result,
                status="not_converged",
                failed_unit="U-MIX",
                code="liquid enthalpy: injected refusal",
            )
        return result

    monkeypatch.setattr(revision.RevisionFlowsheet, "traverse", refusing_pass_4)
    start = _started("SYN-001-UL-C3")
    assert start.passes_used == 3
    assert start.rejected == ((4, "U-MIX", "not_converged", "liquid enthalpy: injected refusal"),)


def test_wo3_net02_keeps_all_eight_passes() -> None:
    start = _started("NET-02")
    assert (start.passes_used, start.rejected) == (8, ())
    assert list(start.values) == list(_binding("NET-02").spec.variable_ids)


def test_wo3_c3x_fails_as_traversal_start_does() -> None:
    binding = _binding("SYN-001-UL-C3X")
    registered = revision.traversal_start(binding.flowsheet, binding.spec.variable_ids)
    start = revision.restart_start(binding.flowsheet, binding.spec.variable_ids)
    assert isinstance(registered, revision.InitialStateFailure)
    assert isinstance(start, revision.InitialStateFailure)
    assert start.message == registered.message


def test_wo3_no_compiled_residual_or_jacobian_is_called(monkeypatch: pytest.MonkeyPatch) -> None:
    """T05 A27's clause: an initializer reads the traversal and nothing else."""

    def refuse(*_: Any, **__: Any) -> Any:
        raise AssertionError("an initializer called the compiled problem")

    monkeypatch.setattr(CasadiCompiledProblem, "residual", refuse)
    monkeypatch.setattr(CasadiCompiledProblem, "jacobian", refuse)
    for case in ("SYN-001-UL-C2", "SYN-001-UL-C3", "NET-02"):
        assert isinstance(_restart(case), revision.RestartStart)


def _refusing_reconstruction(
    monkeypatch: pytest.MonkeyPatch, refuse_at: set[int]
) -> list[FlowsheetPass]:
    """`_start_from_pass` refusing the kept passes whose 1-based index is in `refuse_at`;
    returns the passes it was called on, in order."""
    reconstruct: Callable[..., Any] = revision._start_from_pass
    seen: list[FlowsheetPass] = []
    traversed: list[FlowsheetPass] = []

    def spy_traverse(original: Callable[..., FlowsheetPass]) -> Callable[..., FlowsheetPass]:
        def traverse(*args: Any, **kwargs: Any) -> FlowsheetPass:
            result = original(*args, **kwargs)
            traversed.append(result)
            return result

        return traverse

    def refusing(flowsheet: Any, variable_ids: Any, chosen: FlowsheetPass) -> Any:
        seen.append(chosen)
        index = next(i for i, p in enumerate(traversed, start=1) if p is chosen)
        if index in refuse_at:
            return revision.InitialStateFailure("U-PHF", f"kernel_refused(S3@{index})")
        return reconstruct(flowsheet, variable_ids, chosen)

    monkeypatch.setattr(revision, "_start_from_pass", refusing)
    monkeypatch.setattr(
        revision.RevisionFlowsheet,
        "traverse",
        spy_traverse(revision.RevisionFlowsheet.traverse),
    )
    return seen


def test_wo3_a_refused_reconstruction_falls_back_one_pass(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    binding = _binding("NET-02")
    seen = _refusing_reconstruction(monkeypatch, {8, 7})
    start = revision.restart_start(binding.flowsheet, binding.spec.variable_ids)
    assert isinstance(start, revision.RestartStart)
    assert len(seen) == 3
    assert start.passes_used == 6
    assert start.rejected == (
        (8, "U-PHF", "kernel_refused", "kernel_refused(S3@8)"),
        (7, "U-PHF", "kernel_refused", "kernel_refused(S3@7)"),
    )


def test_wo3_a_refused_reconstruction_at_pass_2_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    binding = _binding("NET-02")
    _refusing_reconstruction(monkeypatch, {2, 3, 4, 5, 6, 7, 8})
    start = revision.restart_start(binding.flowsheet, binding.spec.variable_ids)
    assert isinstance(start, revision.InitialStateFailure)
    assert start.message == "initializer_failed(U-PHF): kernel_refused(S3@2)"
