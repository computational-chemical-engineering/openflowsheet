"""F2-WO6b: v2 documents through the application (ADR 0062 D8, D12; ADR 0019 Amendment 9).

- **E-F2-3, run half.** Every revision of F0's run set (`scripts/corpus_identity.py`
  `run_corpus`: its 47 `g8` revisions and the 9 basis cases; the 5 `k05` runs are SYN-001 variants
  the CLI solves by name, not revision documents), raised to v2 and submitted as a run as F0
  submits it (`select_route`, `run_revision_session`), writes the bundle of its v1 run: the same
  artifact index (every artifact's SHA-256, `revision.json` and `solution-state.json` included),
  `artifact_r0_sha256` equal to the run's and to F0's registered M3, and the same state hashes.
  The three M1 revisions outside the run set route as their v1 documents do (no route, the same
  refusal).
- **The dispatch map** (`docs/F2_DECISIONS.md`, "WO6b dispatch map"): one test per row.
"""

from __future__ import annotations

import copy
import json
import sys
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from f2.legacy_providers import legacy_providers as test_providers

from openflowsheet.models.revision_flowsheet import (
    RevisionError,
    legacy_providers,
    lowered_document,
    parse_revision,
    pin_specifications,
)
from openflowsheet.revision_v2.raise_v1 import raise_v1

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import corpus_identity as gate  # noqa: E402
from t07_corpus import CORPUS  # noqa: E402

#: A SYN-001 revision of the corpus: three components, seven `nTP-v1` connections.
BASE = "SYN-001-T06-NET02"
#: F0's registered measures (`benchmarks/f0/corpus.json`).
REGISTRY = json.loads(gate.REGISTRY.read_text(encoding="utf-8"))["measures"]
#: The run set's revisions (`g8` and the basis cases), by `<set>/<name>`.
RUNS = [(run_set, name) for run_set, name in gate.run_corpus() if run_set != "k05"]


def _raised(document: dict[str, Any]) -> dict[str, Any]:
    return raise_v1(document, legacy_providers())


_SOLVED: dict[tuple[str, str], tuple[Path, Path]] = {}


@pytest.fixture(scope="module", autouse=True)
def _scratch(tmp_path_factory: pytest.TempPathFactory) -> Iterator[None]:
    """Where `_bundles` writes, for this module only."""
    _SOLVED.clear()
    _SOLVED[("", "")] = (tmp_path_factory.mktemp("f2-wo6b"), Path())
    yield
    _SOLVED.clear()


def _bundles(run_set: str, name: str) -> tuple[Path, Path]:
    """The v1 run and the raised v2 document's run of one revision, solved as F0 solves it."""
    if (run_set, name) in _SOLVED:
        return _SOLVED[(run_set, name)]
    scratch = _SOLVED[("", "")][0] / f"{run_set}-{name}"
    original = gate.revision_document(run_set, name)
    raised = _raised(copy.deepcopy(original))
    assert raised["schema_version"] == 2
    with gate.pinned_threads():
        gate.solve(run_set, name, scratch / "v1", original)
        gate.solve(run_set, name, scratch / "v2", raised)
    _SOLVED[(run_set, name)] = (scratch / "v1", scratch / "v2")
    return _SOLVED[(run_set, name)]


def test_e_f2_3_run_set_is_47_g8_and_9_basis_cases() -> None:
    """56 runs: F0's run set without the 5 `k05` cases, which are not revision documents."""
    assert sum(run_set == "g8" for run_set, _ in RUNS) == 47
    assert len(RUNS) == 56


@pytest.mark.parametrize(("run_set", "name"), RUNS, ids=[f"{s}/{n}" for s, n in RUNS])
def test_e_f2_3_raised_run_writes_the_v1_bundle(run_set: str, name: str) -> None:
    """E-F2-3 (run half): the v2 run's manifest identity and artifact index equal the v1 run's,
    its `artifact_r0_sha256` is F0's registered M3, and `solution-state.json` is the same bytes."""
    v1, v2 = (gate.artifacts(directory) for directory in _bundles(run_set, name))
    (manifest1, documents1), (manifest2, documents2) = v1, v2
    for field in (
        "run_id",
        "model_version",
        "constants_sha256",
        "policy_id",
        "plan_id",
        "check_policy_sha256",
        "policy_sha256",
        "artifact_r0_sha256",
        "numerical_policy_id",
        "artifacts",
        "outcome",
        "verification_status",
        "reproducibility_class",
    ):
        assert getattr(manifest2, field) == getattr(manifest1, field), field
    key = f"{run_set}/{name}"
    assert manifest2.artifact_r0_sha256 == REGISTRY["M3"][key]["artifact_r0_sha256"]
    assert list(gate.state_hashes(documents2)) == list(gate.state_hashes(documents1))
    state = "solution-state.json"
    if state in documents1:
        directory1, directory2 = _bundles(run_set, name)
        assert (directory2 / "artifacts" / state).read_bytes() == (
            directory1 / "artifacts" / state
        ).read_bytes()
        assert documents2[state]["schema_version"] == "solution-state-v1"


def test_e_f2_3_m1_revisions_outside_the_run_set_route_as_v1() -> None:
    """The M1 revisions with no registered run: the raised document routes as the v1 one."""
    from openflowsheet.application.revision_run import NoRoute, Route, select_route  # noqa: PLC0415

    outside = sorted(set(CORPUS) - {name for _, name in RUNS})
    assert len(outside) == 3
    for name in outside:
        original = CORPUS[name]()
        v1, v2 = select_route(original), select_route(_raised(original))
        assert type(v1) is type(v2), name
        if isinstance(v1, NoRoute):
            assert isinstance(v2, NoRoute)
            assert (v2.reason, v2.hint) == (v1.reason, v1.hint), name
        else:
            assert isinstance(v1, Route) and isinstance(v2, Route)
            assert (v2.solve_path, v2.reason) == (v1.solve_path, v1.reason), name


# -- the dispatch map ---------------------------------------------------------------------------


def _base() -> dict[str, Any]:
    return CORPUS[BASE]()


def _energy(document: dict[str, Any]) -> dict[str, Any]:
    """`document` with its first connection made an energy connection: not v1-expressible."""
    changed = copy.deepcopy(document)
    connection = changed["connections"][0]
    connection["kind"] = "energy"
    connection["definition"] = "heat-v1"
    connection.pop("phase_capability", None)
    return changed


def test_row_14_legacy_providers_equal_the_test_builder() -> None:
    """Row 14 (F2 decisions WO6a-1, WO6b-1): the production selection is the test-only one,
    built independently from `component_basis` and the providers' modules."""
    assert legacy_providers() == test_providers()


def test_row_1_parse_revision_reads_v2_as_its_lowering() -> None:
    """Row 1: `parse_revision` dispatches on `schema_version`; a v1 document is read as given."""
    original = _base()
    raised = _raised(original)
    assert parse_revision(raised) == parse_revision(original)
    assert pin_specifications(raised) == pin_specifications(original)
    assert lowered_document(original) is original


def test_row_1_a_v2_document_is_never_read_as_v1() -> None:
    """ADR 0002 D7.5: a v2 document the v2 schema refuses is `schema_invalid`, not a v1 reading."""
    raised = _raised(_base())
    del raised["convention"]
    with pytest.raises(RevisionError) as caught:
        parse_revision(raised)
    assert (caught.value.kind, caught.value.code) == ("unsupported", "schema_invalid()")


def test_row_1_a_non_expressible_document_is_refused_typed() -> None:
    """Row 1: a v2 document `lower` refuses raises the first `construct_unavailable`."""
    raised = _energy(_raised(_base()))
    with pytest.raises(RevisionError) as caught:
        parse_revision(raised)
    assert caught.value.kind == "unsupported"
    assert caught.value.code.startswith("construct_unavailable(")


@pytest.mark.parametrize(
    "bind",
    [
        "openflowsheet.application.revision_binding:bind_revision_flowsheet",
        "openflowsheet.application.binding:bind_revision_or_reason",
    ],
)
def test_rows_2_3_binders_bind_the_lowered_document(bind: str) -> None:
    """Rows 2 and 3: each binder binds a v2 document as its lowering, digest included."""
    module, name = bind.split(":")
    binder: Callable[[dict[str, Any]], Any] = getattr(__import__(module, fromlist=[name]), name)
    original = _base()
    v1, v2 = binder(copy.deepcopy(original)), binder(_raised(original))
    assert type(v1) is type(v2)
    if hasattr(v1, "revision_sha256"):
        assert v2.revision_sha256 == v1.revision_sha256
    else:
        assert (v2.kind, v2.detail) == (v1.kind, v1.detail)


def test_rows_2_3_a_non_expressible_document_is_unbound() -> None:
    from openflowsheet.application.binding import bind_revision_or_reason  # noqa: PLC0415
    from openflowsheet.application.revision_binding import (  # noqa: PLC0415
        bind_revision_flowsheet,
    )

    raised = _energy(_raised(_base()))
    for refused in (bind_revision_flowsheet(raised), bind_revision_or_reason(raised)):
        assert refused.kind == "unsupported"
        assert refused.detail.startswith("construct_unavailable(")


def test_rows_4_5_6_readers_of_a_bundle_read_the_lowered_document() -> None:
    """Rows 4 to 6: the stream table, the verifier and the NLP boundary read a v2 revision as its
    lowering. The verifier and the stream table are driven through a v2 run's bundle; the NLP
    boundary's target reads it as the binder did."""
    from openflowsheet.application.revision_binding import (  # noqa: PLC0415
        bind_revision_flowsheet,
    )
    from openflowsheet.application.stream_table import _inputs  # noqa: PLC0415
    from openflowsheet.studies.nlp.boundary import certificate_target  # noqa: PLC0415
    from openflowsheet.thermo import syn001  # noqa: PLC0415

    _, directory = _bundles("g8", BASE)
    _, documents = gate.artifacts(directory)
    raised = _raised(_base())
    state = documents["solution-state.json"]
    certificate = documents["solution-certificate.json"]
    provider = syn001.Syn001Provider()
    v2 = _inputs(raised, state, certificate, provider, "revision_eo")
    v1 = _inputs(_base(), state, certificate, provider, "revision_eo")
    assert v2 == v1
    binding = bind_revision_flowsheet(raised)
    values = dict(state["variables"])
    target2 = certificate_target(binding, raised, values)
    target1 = certificate_target(binding, _base(), values)
    assert (target2.row_ids, target2.column_ids) == (target1.row_ids, target1.column_ids)


def test_row_11_content_hash_of_a_v2_document_is_revision_v2s() -> None:
    from openflowsheet.application.revisions import Revision, content_hash  # noqa: PLC0415
    from openflowsheet.revision_v2 import content_hash as v2_content_hash  # noqa: PLC0415

    original = _base()
    raised = _raised(original)
    assert content_hash(raised) == v2_content_hash(raised)
    assert content_hash(raised) != content_hash(original)
    assert Revision(raised["revision_id"], raised).content_hash == v2_content_hash(raised)


def test_row_12_the_bundle_holds_the_lowered_revision() -> None:
    """Row 12 (D8): `revision.json` of a v2 run is the lowered v1 document."""
    _, directory = _bundles("g8", BASE)
    _, documents = gate.artifacts(directory)
    assert documents["revision.json"]["schema_version"] == 1


def test_row_13_verify_bundle_judges_a_v2_state_by_its_own_rules() -> None:
    """Row 13: `verify_bundle` dispatches on the solution state's version: a v2 run's bundle (v1
    state) verifies, and a `solution-state-v2` is judged by `inconsistencies_v2`."""
    from openflowsheet.run import bundle  # noqa: PLC0415
    from openflowsheet.run import solution_state as states  # noqa: PLC0415

    _, directory = _bundles("g8", BASE)
    assert bundle.verify_bundle(directory).ok
    seen: list[str] = []

    def spy(name: str) -> Callable[..., tuple[str, ...]]:
        def judged(state: Any, certificate: Any) -> tuple[str, ...]:
            seen.append(name)
            return ()

        return judged

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(states, "inconsistencies", spy("v1"))
        patch.setattr(states, "inconsistencies_v2", spy("v2"))
        document = json.loads((directory / "artifacts" / "solution-state.json").read_bytes())
        for version, expected in (("solution-state-v1", "v1"), ("solution-state-v2", "v2")):
            document["schema_version"] = version
            patch.setattr(bundle, "read_artifact", lambda _d, _n, doc=document: doc)
            bundle._cross_check_solution_state(
                directory, {states.NAME: ""}, missing=[], tampered=[]
            )
            assert seen[-1] == expected
