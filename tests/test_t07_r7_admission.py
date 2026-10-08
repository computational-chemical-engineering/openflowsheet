"""T07 ruling round 7, M1 and M2 (R7-W1): `legacy_eo` is admitted only when the legacy
formulation states the document's problem — gates G-R7-1, G-R7-2 and G-R7-4, and each clause of
`legacy_admission`.

Design note `docs/design/T07-jobs-and-bindings.md`, "Ruling round 7", replacing round 6's
predicate in R2.1, §12.1 and §12.4:

- **C0** round 6's class (`legacy_answers`); **C1** every free specification reaches a coordinate
  no fixed one reaches; **C2** the revision binder binds with every free specification read as
  fixed, once the cross-unit targets it refuses as unconsumed are removed (`revision_probe`);
  **C3** the legacy binding frees every free specification's columns; **C4** it promotes exactly
  those targets' columns.
- **G-R7-1** (G-R6-1 re-run): 36 `revision_eo`, 11 `legacy_eo` — the 11 A02 files, `86ab418`'s —
  and 3 with no route; every admitted `route_reason` is `86ab418`'s.
- **G-R7-2** (G-R6-2 re-run): `test_t07_r6_routes.py::test_g_r6_2_every_corpus_report_is_9165894s`,
  unchanged, and the identity protocol (`docs/T07_DECISIONS.md`, rf5).
- **G-R7-3** is `test_t07_r6_free_role.py` (m1–m16); **G-R7-5** is G-R6-3/-4 unchanged and G9
  over m1–m16 (`test_t07_w3b_validation.py`).
- **G-R7-4** (M2's invariant): each admitted revision's probe binds after removing
  `SPEC-flash-duty` alone, its binding frees a coordinate, and `legacy_plan` has a `solve_eo` step.
- **C5** (review-2 S3, rf6): the binding frees exactly one coordinate and promotes exactly one
  target — T02 §7.1's v0.1 pairing, which `specification_regions` otherwise refuses untyped at
  plan time, after the revision validated `READY`. And `solve_route` ends typed,
  `plan_refused(UNSUPPORTED_RANK_STRUCTURE)`, on a route that reaches it without admission (a
  recorded route re-bound by `bind_route`).
"""

from __future__ import annotations

import copy
import time
from collections.abc import Callable, Iterator
from dataclasses import replace
from typing import Any

import pytest
from t07_corpus import A02_FILES, CORPUS
from t07_jobs_support import commit
from t07_r7_documents import mutated

import openflowsheet.application.revision_binding as revision_binding_module
from openflowsheet.application.binding import (
    Binding,
    Unbound,
    _declared_default,
    bind_revision_or_reason,
    legacy_admission,
    revision_probe,
)
from openflowsheet.application.contract import ApplicationError
from openflowsheet.application.local import LocalApplication
from openflowsheet.application.policies import DEFAULT_POLICY_ID, T04_W12, resolve_policy
from openflowsheet.application.revision_binding import RevisionBinding, bind_revision_flowsheet
from openflowsheet.application.revision_run import (
    NoRoute,
    Route,
    RunUnsupportedError,
    bind_route,
    legacy_plan,
    route_structure,
    select_route,
    solve_route,
)
from openflowsheet.application.types import JobRequest
from openflowsheet.application.validation import structural_refusal, validate
from openflowsheet.orchestrator.revision import plan_revision
from openflowsheet.verify.certificate import CheckPolicy

#: Every A02 file's revision refusal, the admitted route's `route_reason` at `86ab418`.
ROUTE_REASON = "unsupported(specification_role_unsupported(GUESS-heater-outlet-T))"
TARGET = "SPEC-flash-duty"


def _bound(document: dict[str, Any]) -> tuple[Unbound, Binding]:
    """The revision binder's refusal and the legacy binding of a revision both are expected of."""
    refusal = bind_revision_flowsheet(copy.deepcopy(document))
    legacy = bind_revision_or_reason(copy.deepcopy(document))
    assert isinstance(refusal, Unbound) and isinstance(legacy, Binding)
    return refusal, legacy


# -- G-R7-1 -------------------------------------------------------------------------------------


def test_g_r7_1_routes_over_the_corpus() -> None:
    routes = {name: select_route(CORPUS[name]()) for name in CORPUS}
    paths = {
        name: route.solve_path if isinstance(route, Route) else None
        for name, route in routes.items()
    }
    assert {path: list(paths.values()).count(path) for path in set(paths.values())} == {
        "revision_eo": 36,
        "legacy_eo": 11,
        None: 3,
    }
    assert len(A02_FILES) == 11
    assert {name for name, path in paths.items() if path == "legacy_eo"} == set(A02_FILES)
    for name in A02_FILES:
        route = routes[name]
        assert isinstance(route, Route)
        assert route.reason == ROUTE_REASON, name


# -- G-R7-4 -------------------------------------------------------------------------------------


@pytest.mark.parametrize("name", A02_FILES)
def test_g_r7_4_every_admitted_revision_frees_a_coordinate_and_plans_a_solve(name: str) -> None:
    document = CORPUS[name]()
    refusal, legacy = _bound(document)
    assert legacy_admission(document, refusal, legacy) is None
    probed, targets = revision_probe(document, legacy)
    assert probed is None
    assert [target for target, _ in targets] == [TARGET]
    ((_, unconsumed),) = targets
    assert (unconsumed.kind, unconsumed.detail) == (
        "unsupported",
        f"specification_unconsumed({TARGET})",
    )
    assert legacy.freed and set(legacy.freed.values()) == {"S3.T"}
    assert set(legacy.promoted.values()) == {"U-FLASH.Q"}
    plan, _ = legacy_plan(legacy, T04_W12)
    assert [step.kind for step in plan.steps].count("solve_eo") == 1


def test_g_r7_4_a_free_specification_without_a_value_starts_at_the_declared_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`SYN-001-A02-360-no-guess`: the probe reads the guess at `_declared_default("S3.T")`, in K,
    with no `bounds` — the start the legacy binder assembled with."""
    document = CORPUS["SYN-001-A02-360-no-guess"]()
    _, legacy = _bound(document)
    seen: list[dict[str, Any]] = []
    binder = revision_binding_module.bind_revision_flowsheet

    def recording(probe: dict[str, Any]) -> RevisionBinding | Unbound:
        seen.append(copy.deepcopy(probe))
        return binder(probe)

    monkeypatch.setattr(revision_binding_module, "bind_revision_flowsheet", recording)
    assert revision_probe(document, legacy)[0] is None
    assert len(seen) == 2
    (guess,) = [e for e in seen[0]["specifications"] if e["id"] == "GUESS-heater-outlet-T"]
    default = _declared_default("S3.T")
    assert default is not None
    assert (guess["role"], guess["value"], guess["unit"]) == ("fixed", default, "K")
    assert "bounds" not in guess
    assert TARGET not in {e["id"] for e in seen[1]["specifications"]}
    # The caller's document is not touched.
    assert document == CORPUS["SYN-001-A02-360-no-guess"]()


def test_a_valueless_free_specification_without_a_legacy_binding_is_a_caller_error() -> None:
    with pytest.raises(ValueError, match="no legacy binding"):
        revision_probe(CORPUS["SYN-001-A02-360-no-guess"](), None)


# -- each clause --------------------------------------------------------------------------------


def test_c0_a_refusal_outside_round_6s_class_is_returned_as_it_is() -> None:
    document = CORPUS["SYN-001-A02-360"]()
    _, legacy = _bound(document)
    refusal = Unbound("incomplete", "specification_missing(S4.P)")
    assert legacy_admission(document, refusal, legacy) is refusal


def test_c1_a_free_specification_that_reaches_no_coordinate() -> None:
    """m16: the free role on a parameter path; the hint lists the paths, generated from the
    target-path table."""
    document = mutated("m16")
    refused = legacy_admission(document, *_bound(document))
    assert refused == Unbound("unsupported", "specification_free_unused(X-fr)")
    assert refused.hint == (
        "A free specification releases a coordinate that a fixed specification could pin: path "
        "state.n, state.T or state.P on a connection, or outlet.T, outlet.P or duty.Q on an "
        "instance. X-fr targets parameters.split_fraction."
    )


@pytest.mark.parametrize("name", ["m9", "m13"])
def test_c1_a_free_specification_that_shares_a_fixed_coordinate(name: str) -> None:
    """m9 (358 K, a different value) and m13 (350 K, the same): refused before the probe, which
    would read the start as a value — a conflict for m9, nothing for m13."""
    document = mutated(name)
    refused = legacy_admission(document, *_bound(document))
    assert refused == Unbound("unsupported", "specification_free_unused(X-f3)")
    assert refused.hint == (
        "X-f3 and fixed specification SPEC-heater-outlet-T both target S3.T. A coordinate is "
        "fixed or free, not both: remove one of them."
    )


def test_c2_the_probe_runs_until_the_binder_binds() -> None:
    """m12: the flash's target is refused first; a second unread pin, the free `X-f6`, is not a
    target and is the refusal."""
    document = mutated("m12")
    refusal, legacy = _bound(document)
    probed, targets = revision_probe(document, legacy)
    assert [target for target, _ in targets] == [TARGET]
    assert probed == Unbound("unsupported", "specification_unconsumed(X-f6)")
    assert legacy_admission(document, refusal, legacy) == probed


def test_c3_a_free_coordinate_the_legacy_binding_does_not_free() -> None:
    document = CORPUS["SYN-001-A02-360"]()
    refusal, legacy = _bound(document)
    refused = legacy_admission(document, refusal, replace(legacy, freed={}))
    assert refused == Unbound("unsupported", "specification_free_unused(GUESS-heater-outlet-T)")
    assert refused.hint == (
        "GUESS-heater-outlet-T targets S3.T, which the SYN-001 formulation that solves free "
        "specifications does not pin, so it cannot be freed."
    )


def test_c4_a_target_the_legacy_binding_does_not_promote() -> None:
    """m11: the mixer duty is a target the revision binder removes (the mixer's pins are read
    before the flash's), and a column the legacy binder drops; the target's own refusal is
    reported."""
    document = mutated("m11")
    refusal, legacy = _bound(document)
    _, targets = revision_probe(document, legacy)
    assert [target for target, _ in targets] == ["X-mixQ", TARGET]
    assert legacy_admission(document, refusal, legacy) == targets[0][1]
    # The same clause on the base, with its one promotion withheld.
    base = CORPUS["SYN-001-A02-360"]()
    refusal, legacy = _bound(base)
    assert legacy_admission(base, refusal, replace(legacy, promoted={})) == Unbound(
        "unsupported", f"specification_unconsumed({TARGET})"
    )


def test_c4_a_promotion_no_target_asks_for_refuses_with_the_revision_refusal() -> None:
    document = CORPUS["SYN-001-A02-360"]()
    refusal, legacy = _bound(document)
    extra = replace(legacy, promoted={**legacy.promoted, "SPEC:extra": "S2.T"})
    assert legacy_admission(document, refusal, extra) is refusal


def test_a_unit_column_is_named_by_its_instance_id() -> None:
    """A shared unit column in the hint is `<instance id>.Q`, not the declaration's unit id."""
    document = CORPUS["SYN-001-A02-360"]()
    specification = copy.deepcopy(next(e for e in document["specifications"] if e["id"] == TARGET))
    specification.update(id="X-freeQ", role="free")
    document["specifications"].append(specification)
    refused = legacy_admission(document, *_bound(document))
    assert refused == Unbound("unsupported", "specification_free_unused(X-freeQ)")
    assert refused.hint is not None and f"{TARGET} both target flash.Q." in refused.hint


# -- C5 (review-2 S3, rf6) ----------------------------------------------------------------------

Document = dict[str, Any]
PAIRING = "The SYN-001 formulation that solves free specifications pairs exactly one freed "


def _specification(document: Document, name: str) -> Document:
    found: Document = next(e for e in document["specifications"] if e["id"] == name)
    return found


def _purge_target(document: Document) -> Document:
    """A fixed purge-flow target, `X-purge-nA` on `S7` `state.n` `A`, 0.05 (review-2 S3)."""
    target = copy.deepcopy(_specification(document, "SPEC-feed-n-A"))
    target.update(id="X-purge-nA", value=0.05, role="fixed")
    target["target"] = {
        "object_type": "connection",
        "object_id": "S7",
        "path": "state.n",
        "component": "A",
    }
    document["specifications"].append(target)
    return document


def two_pairs() -> Document:
    """Review-2 S3's document: A02-360 with `SPEC-feed-n-A` made free and the purge target added —
    two design-specification pairs, `READY_FOR_SIMULATION` on `legacy_eo` before C5."""
    document = CORPUS["SYN-001-A02-360"]()
    _specification(document, "SPEC-feed-n-A")["role"] = "free"
    return _purge_target(document)


def _flash_p_free() -> Document:
    """R7-O5's document: `SPEC-flash-P` made free (it frees both flash outlets' pressures)."""
    document = CORPUS["SYN-001-A02-360"]()
    _specification(document, "SPEC-flash-P")["role"] = "free"
    return document


def _feed_free() -> Document:
    document = CORPUS["SYN-001-A02-360"]()
    _specification(document, "SPEC-feed-n-A")["role"] = "free"
    return document


def _no_target() -> Document:
    document = CORPUS["SYN-001-A02-360"]()
    document["specifications"] = [e for e in document["specifications"] if e["id"] != TARGET]
    return document


def _two_targets() -> Document:
    return _purge_target(CORPUS["SYN-001-A02-360"]())


#: Document -> (its builder; freed, promoted): each shape C0–C4 admit and T02 §7.1's v0.1
#: pairing does not.
SHAPES: dict[str, tuple[Callable[[], Document], tuple[int, int]]] = {
    "two_pairs": (two_pairs, (2, 2)),
    "flash_p_free": (_flash_p_free, (3, 1)),
    "feed_free": (_feed_free, (2, 1)),
    "no_target": (_no_target, (1, 0)),
    "two_targets": (_two_targets, (1, 2)),
}


def test_c5_two_design_specification_pairs_are_refused_with_a_hint_naming_both() -> None:
    document = two_pairs()
    refusal, legacy = _bound(document)
    # C0–C4 hold: the probe binds once both targets are removed, and the binding frees and
    # promotes exactly what the specifications reach.
    probed, targets = revision_probe(document, legacy)
    assert probed is None and [name for name, _ in targets] == [TARGET, "X-purge-nA"]
    refused = legacy_admission(document, refusal, legacy)
    assert refused == Unbound("unsupported", "specification_pairing_unsupported(2,2)")
    assert refused.hint == (
        PAIRING + "coordinate with exactly one target (T02 §7.1); this revision frees 2 against "
        "2: SPEC-feed-n-A frees S1.n.A, GUESS-heater-outlet-T frees S3.T, SPEC-flash-duty "
        "targets flash.Q, X-purge-nA targets S7.n.A. State one free coordinate and one target: "
        "fix the other free specifications or remove the other targets."
    )


@pytest.mark.parametrize("name", SHAPES)
def test_c5_every_other_count_is_refused(name: str) -> None:
    build, (freed, promoted) = SHAPES[name]
    document = build()
    refusal, legacy = _bound(document)
    assert (len(legacy.freed), len(legacy.promoted)) == (freed, promoted)
    refused = legacy_admission(document, refusal, legacy)
    assert refused == Unbound(
        "unsupported", f"specification_pairing_unsupported({freed},{promoted})"
    )
    assert refused.hint is not None and refused.hint.startswith(PAIRING)
    assert isinstance(select_route(document), NoRoute)


def test_c5_the_hint_names_a_multi_column_free_specification_and_no_target() -> None:
    refused = legacy_admission(_flash_p_free(), *_bound(_flash_p_free()))
    assert refused is not None and refused.hint is not None
    assert "SPEC-flash-P frees S4.P and S5.P" in refused.hint
    refused = legacy_admission(_no_target(), *_bound(_no_target()))
    assert refused is not None and refused.hint is not None
    assert "frees 1 against no target: GUESS-heater-outlet-T frees S3.T." in refused.hint


def test_c5_the_two_pair_revision_validates_draft_with_no_route() -> None:
    """Review-2 S3: `READY_FOR_SIMULATION` on `legacy_eo` before C5, then an untyped
    `UnsupportedRankStructureError` from `solve_route`. Now `DRAFT`, no route, one typed refusal
    on every surface."""
    detail = "specification_pairing_unsupported(2,2)"
    report = validate(two_pairs())
    assert report.status == "DRAFT"
    checks = {check.id: check for check in report.checks}
    for check_id in ("STR-01", "STR-02", "STR-03", "STR-04", "STR-05"):
        assert checks[check_id].result == "NOT_RUN"
        assert detail in checks[check_id].message
    reported = structural_refusal(two_pairs())
    assert reported is not None and (reported.kind, reported.detail) == ("unsupported", detail)
    assert reported.hint is not None and "X-purge-nA targets S7.n.A" in reported.hint
    route = select_route(two_pairs())
    assert isinstance(route, NoRoute)
    assert route.revision == reported
    assert route.legacy == Unbound(
        "unsupported", "legacy_route_not_admitted(specification_pairing_unsupported)"
    )
    structure = route_structure(two_pairs())
    # ADR 0019 Amendment 3 (A3.1) adds three members, by addition only (M06 WO-1).
    assert set(structure) == {
        "not_run_reason",
        "hint",
        "validation_structural_report",
        "rows",
        "columns",
    }
    assert detail in structure["not_run_reason"]
    assert structure["hint"] == reported.hint


@pytest.fixture(scope="module")
def application(tmp_path_factory: pytest.TempPathFactory) -> Iterator[LocalApplication]:
    root = tmp_path_factory.mktemp("rf6-c5")
    with LocalApplication.create(root / "p", project_id="t07-rf6-c5") as app:
        yield app


def test_c5_submit_job_is_refused_revision_not_ready(application: LocalApplication) -> None:
    revision = commit(application, two_pairs())
    before = len(application.list_jobs(limit=200).items)
    with pytest.raises(ApplicationError) as refused:
        application.submit_job(
            JobRequest.from_document(
                {
                    "operation": "solve",
                    "idempotency_key": f"rf6-c5-{time.monotonic_ns()}",
                    "body": {"revision_id": revision, "policy_id": "default"},
                }
            )
        )
    assert refused.value.code == "revision_not_ready"
    assert len(application.list_jobs(limit=200).items) == before


def test_every_admitted_corpus_route_plans_with_one_pair_on_legacy_eo() -> None:
    """Whether the rank refusal can arise on an admitted route: every route `select_route` gives
    over the 50 builds its plan under the default policy, and every `legacy_eo` binding pairs one
    freed coordinate with one target — C5, by construction."""
    for name, build in CORPUS.items():
        route = select_route(build())
        if not isinstance(route, Route):
            continue
        policy = resolve_policy(DEFAULT_POLICY_ID, route.solve_path)
        assert policy is not None
        if route.solve_path == "legacy_eo":
            assert (len(route.binding.freed), len(route.binding.promoted)) == (1, 1), name
            legacy_plan(route.binding, policy)
        else:
            plan_revision(route.binding, policy)


def test_a_route_bound_without_admission_ends_typed_at_plan_time() -> None:
    """R2.5: a recorded route is re-bound by `bind_route`, which never re-admits (a rerun, a
    reproduction of a bundle someone handed over). The two-pair revision binds on `legacy_eo`
    there, and `solve_route` ends typed — T02's code in `plan_refused(<code>)`, §12.3's form for
    a refused plan with no registered bundle — rather than raising the untyped rank error."""
    route = bind_route("legacy_eo", two_pairs())
    assert isinstance(route, Route)
    policy = resolve_policy(DEFAULT_POLICY_ID, "legacy_eo")
    assert policy is not None
    with pytest.raises(RunUnsupportedError) as raised:
        solve_route(route, two_pairs(), policy=policy, check_policy=CheckPolicy())
    assert raised.value.code == "plan_refused(UNSUPPORTED_RANK_STRUCTURE)"
