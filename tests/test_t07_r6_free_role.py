"""T07 ruling rounds 6 (R6-W6) and 7 (R7-W1): the free-role class reads the whole document — gates
G-R6-7 and G-R7-3.

Design note `docs/design/T07-jobs-and-bindings.md`, "Ruling round 6", R6-W6, and "Ruling round 7".
`legacy_eo` is admitted for a `role: free` specification the revision binder cannot read; the
legacy formulation must still state the document's problem under the models it names, or
`legacy_eo` would solve a different problem. The documents are `t07_r7_documents`' m1–m16.

G-R7-3: each validates `DRAFT`, STR-01…05 `NOT_RUN` with a message that contains the reported
code; `select_route` gives no route, its legacy part `unsupported(legacy_route_not_admitted(<code
token>))` (m1–m3: the legacy binder's own refusal); `inspect_structure`'s `hint` is the reported
refusal's; `submit_job` is refused `revision_not_ready` for m5, m9, m11 and m12; and the probe
never returns `inadmissible` on these documents or the corpus (R7-O2).
"""

from __future__ import annotations

import copy
import time
from collections.abc import Iterator
from typing import Any

import pytest
from t07_corpus import CORPUS
from t07_jobs_support import commit
from t07_r7_documents import BASE, MUTATIONS, mutated

from openflowsheet.application.binding import (
    Binding,
    Unbound,
    bind_revision_or_reason,
    legacy_answers,
    refusal_code,
    revision_probe,
)
from openflowsheet.application.contract import ApplicationError
from openflowsheet.application.local import LocalApplication
from openflowsheet.application.revision_binding import (
    RevisionBinding,
    bind_revision_flowsheet,
)
from openflowsheet.application.revision_run import NoRoute, route_structure, select_route
from openflowsheet.application.types import JobRequest
from openflowsheet.application.validation import structural_refusal, validate

STRUCTURAL = ("STR-01", "STR-02", "STR-03", "STR-04", "STR-05")
ROLE = "specification_role_unsupported(GUESS-heater-outlet-T)"
#: The hint of a refusal whose expectation the ruling's table leaves open (m4's).
UNSTATED = object()
#: A hint that must be present, with nothing more said of it.
PRESENT = ""

#: Mutation -> (the reported refusal's kind and code; its hint: `None`, `PRESENT`, a substring it
#: contains, or `UNSTATED`; the legacy binder's refusal, `None` where it binds). The ruling's
#: G-R7-3 table.
EXPECTED: dict[str, tuple[tuple[str, str], object, str | None]] = {
    # Ruling round 7, S1: the legacy binder refuses m1–m3 with the contract's code, and the
    # probe's refusal — the same code — replaces the free role on the revision side of the
    # `unsupported` tie (ruling round 3, Q2). Their legacy part is the legacy binder's refusal.
    "m1": (
        ("unsupported", "parameter_value_unsupported(flash.pressure_drop)"),
        None,
        "unsupported(parameter_value_unsupported(flash.pressure_drop))",
    ),
    "m2": (
        ("unsupported", "port_phase_unsupported(heater.outlet)"),
        PRESENT,
        "unsupported(port_phase_unsupported(heater.outlet))",
    ),
    "m3": (
        ("unsupported", "parameter_unsupported(heater.efficiency)"),
        None,
        "unsupported(parameter_unsupported(heater.efficiency))",
    ),
    "m4": (("unsupported", ROLE), UNSTATED, None),
    "m5": (("incomplete", "specification_missing(S4.P)"), "path: state.P", None),
    "m6": (("unsupported", "parameter_unsupported(heater.efficiency)"), None, None),
    "m7": (("unsupported", "specification_unsupported(X-x)"), PRESENT, None),
    "m8": (("unsupported", "specification_unconsumed(X-f6)"), PRESENT, None),
    "m9": (("unsupported", "specification_free_unused(X-f3)"), "SPEC-heater-outlet-T", None),
    "m10": (("unsupported", "parameter_value_unsupported(flash.pressure_drop)"), None, None),
    "m11": (("unsupported", "specification_unconsumed(X-mixQ)"), PRESENT, None),
    "m12": (("unsupported", "specification_unconsumed(X-f6)"), PRESENT, None),
    "m13": (("unsupported", "specification_free_unused(X-f3)"), "SPEC-heater-outlet-T", None),
    "m14": (("incomplete", "specification_missing(S5.T)"), PRESENT, None),
    "m15": (("incomplete", "specification_missing(S4.P)"), "path: state.P", None),
    "m16": (("unsupported", "specification_free_unused(X-fr)"), "parameters.split_fraction", None),
}
#: G-R7-3: the documents whose `submit_job` is asserted refused.
SUBMITTED = ("m5", "m9", "m11", "m12")


def test_the_table_covers_every_mutation() -> None:
    assert set(EXPECTED) == set(MUTATIONS)


def test_the_base_is_on_legacy_eo_and_ready() -> None:
    assert validate(CORPUS[BASE]()).status == "READY_FOR_SIMULATION"
    assert select_route(CORPUS[BASE]()).solve_path == "legacy_eo"  # type: ignore[union-attr]


@pytest.mark.parametrize("name", sorted(EXPECTED, key=lambda name: int(name[1:])))
def test_g_r7_3_each_mutation_validates_draft_with_its_reported_refusal(name: str) -> None:
    """R6-O4 measured m1–m3 `READY_FOR_SIMULATION` on `legacy_eo` at R6-W6's first commit, and
    ruling round 7 measured m5–m16 `READY` on `legacy_eo` at `86ab418`; each is `DRAFT` now, and
    every surface reports one refusal."""
    (kind, detail), hint, legacy = EXPECTED[name]
    report = validate(mutated(name))
    assert report.status == "DRAFT"
    checks = {check.id: check for check in report.checks}
    for check_id in STRUCTURAL:
        assert checks[check_id].result == "NOT_RUN"
        assert detail in checks[check_id].message

    reported = structural_refusal(mutated(name))
    assert reported is not None
    assert (reported.kind, reported.detail) == (kind, detail)
    if hint is None:
        assert reported.hint is None
    elif hint is not UNSTATED:
        assert reported.hint is not None and str(hint) in reported.hint

    route = select_route(mutated(name))
    assert isinstance(route, NoRoute)
    if legacy is None:
        # The legacy binder binds and `legacy_admission` refuses: `NoRoute.revision` is the
        # refusal `validate()` reports, and the legacy part names its code.
        assert route.revision == reported
        assert route.legacy == Unbound(
            "unsupported", f"legacy_route_not_admitted({refusal_code(detail)})"
        )
    else:
        # The legacy binder refuses: `select_route` is `NoRoute(<revision refusal>, <legacy
        # refusal>)` as ruled, so its revision part stays the binder's first refusal.
        assert not isinstance(bind_revision_or_reason(mutated(name)), Binding)
        assert route.revision == bind_revision_flowsheet(mutated(name))
        assert f"{route.legacy.kind}({route.legacy.detail})" == legacy

    structure = route_structure(mutated(name))
    assert set(structure) == {"not_run_reason", "hint"}
    assert detail in structure["not_run_reason"]
    assert structure["hint"] == reported.hint


def test_g_r6_7_m4_fails_through_legacy_answers() -> None:
    """m4's legacy binding and the revision binder's refusal are the base's; only the added
    `decision` role takes it out of the class."""
    document = mutated("m4")
    refusal = bind_revision_flowsheet(copy.deepcopy(document))
    assert isinstance(refusal, Unbound)
    assert refusal == bind_revision_flowsheet(CORPUS[BASE]())
    assert not isinstance(bind_revision_or_reason(copy.deepcopy(document)), Unbound)
    assert legacy_answers(CORPUS[BASE](), refusal)
    assert not legacy_answers(document, refusal)


def _probed(document: dict[str, Any]) -> Unbound | None:
    """The probe's refusal where ruling round 7 runs it — the free class, with the legacy binding
    when there is one and otherwise only when every free specification has a value — or `None`."""
    refusal = bind_revision_flowsheet(copy.deepcopy(document))
    if isinstance(refusal, RevisionBinding) or not legacy_answers(document, refusal):
        return None
    legacy = bind_revision_or_reason(copy.deepcopy(document))
    if isinstance(legacy, Binding):
        return revision_probe(document, legacy)[0]
    free = [e for e in document["specifications"] if e.get("role") == "free"]
    if any(entry.get("value") is None for entry in free):
        return None
    return revision_probe(document, None)[0]


def test_g_r7_3_the_probe_never_returns_inadmissible() -> None:
    """R7-O2: over the 50 and m1–m16 the probe, wherever it runs, never gives `inadmissible`."""
    documents = {name: build() for name, build in CORPUS.items()}
    documents.update({name: mutated(name) for name in MUTATIONS})
    probed = {name: _probed(document) for name, document in documents.items()}
    assert [name for name, p in probed.items() if p is not None and p.kind == "inadmissible"] == []


@pytest.fixture(scope="module")
def application(tmp_path_factory: pytest.TempPathFactory) -> Iterator[LocalApplication]:
    root = tmp_path_factory.mktemp("g-r7-3")
    with LocalApplication.create(root / "p", project_id="t07-g-r7-3") as app:
        yield app


@pytest.mark.parametrize("name", SUBMITTED)
def test_g_r7_3_submit_job_is_refused_revision_not_ready(
    application: LocalApplication, name: str
) -> None:
    revision = commit(application, mutated(name))
    before = len(application.list_jobs(limit=200).items)
    with pytest.raises(ApplicationError) as refused:
        application.submit_job(
            JobRequest.from_document(
                {
                    "operation": "solve",
                    "idempotency_key": f"g-r7-3-{name}-{time.monotonic_ns()}",
                    "body": {"revision_id": revision, "policy_id": "default"},
                }
            )
        )
    assert refused.value.code == "revision_not_ready"
    assert len(application.list_jobs(limit=200).items) == before
