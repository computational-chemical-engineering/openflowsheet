"""T06 W1b: a permuted component order is mapped onto the provider's (T06 spec §8.6, Amendment 1;
ADR 0014 D9; register R-076). Assertions A59–A61.

The expectation is the unpermuted twin's, bit for bit: after the mapping the declared order selects
no expression and no id, so STA-04 *is* `SYN-001-UL-C2` (A59) — label, `configuration_sha256`,
`constants_sha256`, `variable_ids`, trace and certificate — and only `revision_sha256`, which hashes
the document, differs. C2 is the right twin because every component-keyed input differs by
component (feed (2, 1, 0), `ν = (−2, −1, 3)`, splits (0.9, 0.8, 0.05)), so any of the five
non-identity orders applied positionally changes all three and moves the root (generator-checked);
A60 runs all six. On the legacy tear path (A61) SYN-001-nominal's K-values at 360 K are pairwise
distinct by more than 0.1 (generator-checked), so a positional error changes the flash — which is
how F7 crashed.

**Policy.** As in W1a's tests, the revision path runs under `T05b-v2`; `T06-revision-v1` does not
exist in code until F4's WO1 lands, and C2 reaches no EO recovery.
"""

from __future__ import annotations

import copy
import itertools
from functools import cache
from typing import Any

import pytest
from conftest import REPO_ROOT, load_yaml
from t05b_support import POLICY_V2

from openflowsheet.application.binding import Binding, Unbound, bind_revision_or_reason
from openflowsheet.application.revision_binding import RevisionBinding, bind_revision_flowsheet
from openflowsheet.application.validation import validate
from openflowsheet.canonical import canonical_json
from openflowsheet.models.revision_flowsheet import _COMPONENTS, canonical_components
from openflowsheet.orchestrator.execution import ExecutionPlan, declaration_identity
from openflowsheet.orchestrator.executor import execute_plan
from openflowsheet.orchestrator.revision import plan_revision
from openflowsheet.orchestrator.tear import solve_tear
from openflowsheet.orchestrator.trace import SolvePolicy
from openflowsheet.thermo.syn001 import Syn001Provider
from openflowsheet.verify.certificate import verify, verify_revision

Document = dict[str, Any]

NOMINAL = REPO_ROOT / "benchmarks" / "syn001" / "cases" / "SYN-001-nominal.yaml"
C2 = REPO_ROOT / "benchmarks" / "t05" / "cases" / "SYN-001-UL-C2.yaml"
STA04 = REPO_ROOT / "benchmarks" / "t06" / "cases" / "SYN-001-T06-STA04.yaml"

ORDERS = tuple(itertools.permutations(("A", "B", "C")))
NOT_PERMUTATIONS = (["A", "B"], ["A", "B", "C", "D"], ["A", "A", "B"], ["A", "B", "D"])
SETTINGS = (
    "components",
    "feed_flows",
    "feed_temperature",
    "pressure",
    "heater_temperature",
    "flash_temperature",
    "split_fraction",
)


@cache
def _load(path: str) -> Document:
    loaded: Document = load_yaml(REPO_ROOT / path)
    return loaded


def document(path: Any, order: tuple[str, ...] | list[str] | None = None) -> Document:
    revision = copy.deepcopy(_load(str(path)))
    if order is not None:
        revision["component_set"]["components"] = list(order)
    return revision


def revision_bound(revision: Document) -> RevisionBinding:
    binding = bind_revision_flowsheet(revision)
    assert isinstance(binding, RevisionBinding), binding
    return binding


def bits(value: Any) -> Any:
    if isinstance(value, float):
        return value.hex()
    if isinstance(value, tuple | list):
        return [bits(item) for item in value]
    return value


@cache
def revision_solved(
    path: str, order: tuple[str, ...] | None = None, policy: SolvePolicy = POLICY_V2
) -> tuple[tuple[bytes, ...], bytes, str]:
    """Plan, `execute_plan` and `verify_revision`: the trace's events and the certificate as
    canonical bytes, and the verdict."""
    revision = document(path, order)
    binding = revision_bound(revision)
    plan, _ = plan_revision(binding, policy)
    assert isinstance(plan, ExecutionPlan), plan
    run = execute_plan(plan=plan, flowsheet=binding.flowsheet, spec=binding.spec, policy=policy)
    assert run.outcome == "CONVERGED", run.outcome
    certificate = verify_revision(binding, revision, run, solve_plan=plan.steps[-1].solve_plan)
    return (
        tuple(canonical_json(event.as_document()) for event in run.trace.events),
        canonical_json(certificate.as_document()),
        certificate.verification_status,
    )


def test_the_canonical_order_is_the_providers() -> None:
    assert _COMPONENTS == Syn001Provider().describe().components


@pytest.mark.parametrize("order", ORDERS, ids="".join)
def test_every_permutation_maps_to_the_providers_order(order: tuple[str, ...]) -> None:
    assert canonical_components(order) == _COMPONENTS


# -- A59: STA-04 ----------------------------------------------------------------------------------


def test_a59_sta04_binds_as_c2() -> None:
    sta04, c2 = document(STA04), document(C2)
    binding, twin = revision_bound(sta04), revision_bound(c2)
    assert binding.flowsheet.components == ("A", "B", "C")
    assert binding.input_mapping.declared_components == ("C", "A", "B")
    assert binding.input_mapping.conversions == ()
    assert twin.input_mapping.declared_components == ("A", "B", "C")
    assert binding.spec.variable_ids == twin.spec.variable_ids
    assert binding.flowsheet.label == twin.flowsheet.label
    assert binding.flowsheet.configuration_sha256 == twin.flowsheet.configuration_sha256
    assert declaration_identity(binding.spec) == declaration_identity(twin.spec)
    assert bits(list(binding.spec.parameters.items())) == bits(list(twin.spec.parameters.items()))
    assert binding.revision_sha256 != twin.revision_sha256


def test_a59_sta04_solves_and_certifies_as_c2() -> None:
    trace, certificate, status = revision_solved(str(STA04))
    assert status == "VERIFIED"
    assert (trace, certificate) == revision_solved(str(C2))[:2]


def test_a59_sta04_validation_is_unchanged() -> None:
    """F5: the two new checks pass. A59's clause "`validate()` `DRAFT`" (the legacy binding
    cannot read C2's topology) is superseded by ADR 0020 D5 (T07 design note §12.4, ruling round
    1 R1): the structural stage falls back to the revision binder, analyses C2's revision-built
    flowsheet and finds it closed, so STA-04 is `READY_FOR_SIMULATION` with STR-01…05 run."""
    report = validate(document(STA04))
    assert report.status == "READY_FOR_SIMULATION"
    results = {check.id: check.result for check in report.checks}
    assert results["DIM-01"] == "PASS" and results["COMP-03"] == "PASS"
    assert [results[f"STR-0{index}"] for index in range(1, 6)] == ["PASS"] * 5
    assert report.provenance["produced_by"].endswith("; revision binder fallback (T07)")


# -- A60: all six orders; four non-permutations ---------------------------------------------------


@pytest.mark.parametrize("order", ORDERS, ids="".join)
def test_a60_every_order_of_c2_is_c2(order: tuple[str, ...]) -> None:
    binding, twin = revision_bound(document(C2, order)), revision_bound(document(C2))
    assert binding.input_mapping.declared_components == order
    assert binding.spec.variable_ids == twin.spec.variable_ids
    assert binding.flowsheet.label == twin.flowsheet.label
    assert revision_solved(str(C2), order)[:2] == revision_solved(str(C2))[:2]


@pytest.mark.parametrize("order", NOT_PERMUTATIONS, ids=str)
def test_a60_a_non_permutation_is_refused_by_both_bindings(order: list[str]) -> None:
    refused = bind_revision_flowsheet(document(C2, order))
    assert refused == Unbound("unsupported", "components_unsupported")
    # The legacy binding reads SYN-001's topology only, so it is asked of SYN-001-nominal.
    assert bind_revision_or_reason(document(NOMINAL, order)) == Unbound(
        "unsupported", "components_unsupported"
    )


# -- A61: the legacy tear path (F7) ---------------------------------------------------------------


@cache
def tear_solved(order: tuple[str, ...] | None) -> tuple[Binding, tuple[bytes, ...], bytes, str]:
    binding = bind_revision_or_reason(document(NOMINAL, order))
    assert isinstance(binding, Binding), binding
    result, trace = solve_tear(binding.flowsheet)
    assert result.outcome == "CONVERGED", result.message
    certificate = verify(binding.flowsheet, result)
    return (
        binding,
        tuple(canonical_json(event.as_document()) for event in trace.events),
        canonical_json(certificate.as_document()),
        certificate.verification_status,
    )


@pytest.mark.parametrize("order", [("C", "A", "B"), ("B", "A", "C")], ids="".join)
def test_a61_a_permuted_syn001_revision_solves_as_nominal(order: tuple[str, ...]) -> None:
    assert validate(document(NOMINAL, order)).status == "READY_FOR_SIMULATION"
    binding, trace, certificate, status = tear_solved(order)
    nominal, nominal_trace, nominal_certificate, _ = tear_solved(None)
    assert binding.flowsheet.components == ("A", "B", "C")
    assert binding.input_mapping.declared_components == order
    for setting in SETTINGS:
        assert bits(getattr(binding.flowsheet, setting)) == bits(
            getattr(nominal.flowsheet, setting)
        ), setting
    assert status == "VERIFIED"
    assert trace == nominal_trace
    assert certificate == nominal_certificate
