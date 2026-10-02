"""T01 increment 1: the declaration trace, matching, Dulmage-Mendelsohn, certificates, unit DOF.

Every expectation here comes from `benchmarks/t01/reference_values.yaml`, which Fable's
`docs/derivations/scripts/t01_reference.py` produces from a **hand transcription** of the SYN-001
equations with every algorithm written from its definition — no compiler, no graph layer, no
solver, no scipy. So these are not regression fixtures: the reference and the implementation are
two independent derivations of the same objects, and a test that passes here means they agree.

Assertion ids are the specification's (A01, A03-A11, A18-A21, A24). A02, A12-A17, A22-A23 and A25
belong to increment 2 or to the evidence manifest and are not here; A20(b) needs the tear search,
which increment 1 does not have.
"""

from __future__ import annotations

import random
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pytest
import yaml

from openflowsheet.application.binding import bind_revision
from openflowsheet.application.validation import validate
from openflowsheet.graph.analysis import analyse
from openflowsheet.graph.certificates import CERTIFIABLE_KINDS, certify
from openflowsheet.graph.matching import (
    canonical_matching,
    dulmage_mendelsohn,
    maximum_matching,
)
from openflowsheet.graph.report import STATEMENTS, StructuralReport
from openflowsheet.graph.trace import trace_declaration

REPO_ROOT = Path(__file__).resolve().parents[1]
CASES = REPO_ROOT / "benchmarks" / "syn001" / "cases"

#: The five registered revisions that must all give the *same* structural result (A17's premise).
VARIANTS = (
    "SYN-001-nominal",
    "SYN-001-once-through",
    "SYN-001-high-recycle",
    "SYN-001-all-liquid-310K",
    "SYN-001-all-vapor-420K",
)


@pytest.fixture(scope="module")
def reference() -> dict[str, Any]:
    text = (REPO_ROOT / "benchmarks" / "t01" / "reference_values.yaml").read_text()
    loaded: dict[str, Any] = yaml.safe_load(text)
    return loaded


def revision(case_id: str) -> dict[str, Any]:
    loaded: dict[str, Any] = yaml.safe_load((CASES / f"{case_id}.yaml").read_text())
    return loaded


def report_for(case_id: str) -> StructuralReport:
    binding = bind_revision(revision(case_id))
    assert binding is not None, f"{case_id} did not bind"
    return analyse(
        binding.spec,
        binding.graph,
        model_version=binding.model_version,
        constants_sha256=binding.constants_sha256,
        specification_ids=binding.specification_ids,
        row_units=binding.row_units,
    )


def signed_set(equals: Sequence[Sequence[Any]]) -> set[tuple[str, int]]:
    """A certificate's identity is a *sum*, so its `equals` is compared as a set (§19 finding 5)."""
    return {(str(row), int(sign)) for row, sign in equals}


# --------------------------------------------------------------- A01: the traced declaration


def test_a01_the_traced_incidence_equals_the_registered_declaration(
    reference: dict[str, Any],
) -> None:
    """The incidence, read from the row builders, against Fable's hand transcription."""
    declared = reference["declaration"]
    binding = bind_revision(revision("SYN-001-nominal"))
    assert binding is not None
    traced = trace_declaration(binding.spec)

    assert list(traced.column_ids) == declared["variable_ids"]
    assert list(traced.row_ids) == declared["equation_ids"]
    assert traced.nnz == reference["cases"]["SYN-001-nominal"]["nnz"] == 170

    for row_id, columns in declared["incidence"].items():
        assert set(traced.rows[row_id].columns) == set(columns), row_id
    assert dict(traced.column_kinds) == declared["variable_kinds"]


def test_a01_the_affine_classification_matches_the_registered_one(
    reference: dict[str, Any],
) -> None:
    """A parameter-scaled row is not affine-with-literal-coefficients, and the split rows are it."""
    binding = bind_revision(revision("SYN-001-nominal"))
    assert binding is not None
    traced = trace_declaration(binding.spec)

    registered = set(reference["declaration"]["affine_rows"])
    found = {row_id for row_id in traced.row_ids if traced.rows[row_id].is_affine}
    assert found == registered

    for component in ("A", "B", "C"):
        row = traced.rows[f"U-SPLIT:SPLIT-recycle:{component}"]
        assert row.coefficients is None, "a parameter coefficient is not a literal one"
        assert set(row.columns) == {f"S5.n.{component}", f"S6.n.{component}"}


def test_a01_the_incidence_does_not_move_when_a_parameter_is_zero() -> None:
    """The measurement that overturned brief §4.1, as a test.

    The compiled backend folds `0.0 * S5.n_i` away at `r = 0` and reports 167 declared entries
    instead of 170 — so the once-through revision would have no recycle edge in its graph. The
    declaration-traced incidence does not move, and this is the test that keeps it that way.
    """
    counts = {}
    for case_id in ("SYN-001-nominal", "SYN-001-once-through", "SYN-001-high-recycle"):
        binding = bind_revision(revision(case_id))
        assert binding is not None
        counts[case_id] = trace_declaration(binding.spec).nnz
    assert set(counts.values()) == {170}, counts

    binding = bind_revision(revision("SYN-001-once-through"))
    assert binding is not None
    assert binding.spec.parameters["U-SPLIT.split_fraction"] == 0.0, "the case really is r = 0"
    traced = trace_declaration(binding.spec)
    assert set(traced.rows["U-SPLIT:SPLIT-recycle:A"].columns) == {"S5.n.A", "S6.n.A"}


# ------------------------------------------------------ A03: the analysis evaluates nothing


def test_a03_the_analysis_makes_no_evaluation_call(monkeypatch: pytest.MonkeyPatch) -> None:
    """The assertion that keeps the layer honest: no compile, no residual, no flash.

    A structural claim obtained by looking at numbers at a state is not a structural claim, and
    the only way to hold a layer to that is to make evaluating *impossible* while it runs.
    """
    import openflowsheet.compile.casadi_backend as backend
    from openflowsheet.thermo.syn001 import Syn001Provider

    def refuse(*arguments: object, **keywords: object) -> Any:
        raise AssertionError("the structural analysis evaluated something")

    monkeypatch.setattr(backend, "compile_problem", refuse)
    monkeypatch.setattr(Syn001Provider, "flash", refuse)
    monkeypatch.setattr(Syn001Provider, "evaluate_phase", refuse)

    for case_id in (*VARIANTS, "SYN-001-conflicting-heater-spec"):
        result = validate(revision(case_id))
        assert result.structural_counts is not None, case_id


# ------------------------------------------------------------------ A04: the four counts


@pytest.mark.parametrize("case_id", [*VARIANTS, "SYN-001-conflicting-heater-spec"])
def test_a04_structural_counts_match_the_registered_table(
    case_id: str, reference: dict[str, Any]
) -> None:
    registered = reference["cases"][
        "SYN-001-conflicting-heater-spec"
        if case_id == "SYN-001-conflicting-heater-spec"
        else "SYN-001-nominal"
    ]["structural_counts"]
    counts = report_for(case_id).structural_counts
    assert counts == registered
    assert set(counts or {}) == {"free_variables", "equations", "matched", "unmatched"}


def test_a04_unmatched_counts_columns_as_well_as_rows() -> None:
    """Specification §12.1 and open question Q5: one integer must serve both findings.

    `SQ-1` is square by totals and structurally defective in both directions at once. A definition
    counting only unmatched rows would report 1 and a reader would not see the free variables.
    """
    rows, columns = ["r1", "r2", "r3"], ["x1", "x2", "x3"]
    incidence = {
        "r1": frozenset({"x1"}),
        "r2": frozenset({"x1"}),
        "r3": frozenset({"x2", "x3"}),
    }
    partition = dulmage_mendelsohn(rows, columns, incidence)
    matched = partition.structural_rank
    unmatched = (len(rows) - matched) + (len(columns) - matched)
    assert matched == 2
    assert unmatched == 2


# ---------------------------------------------------------- A05: Dulmage-Mendelsohn


def test_a05_the_full_partition_matches_the_registered_sets(reference: dict[str, Any]) -> None:
    for case_id, key in (
        ("SYN-001-nominal", "SYN-001-nominal"),
        ("SYN-001-conflicting-heater-spec", "SYN-001-conflicting-heater-spec"),
    ):
        registered = reference["cases"][key]["dm_full"]
        partition = report_for(case_id).dm_full
        assert partition is not None
        assert list(partition.over_rows) == registered["over_rows"], case_id
        assert list(partition.over_cols) == registered["over_cols"], case_id
        assert list(partition.under_rows) == registered["under_rows"], case_id
        assert list(partition.under_cols) == registered["under_cols"], case_id
        assert partition.structural_rank == reference["cases"][key]["structural_counts"]["matched"]


def test_a05_the_partition_is_the_same_from_twenty_other_maximum_matchings() -> None:
    """Matching-independence is a theorem; a permutation is what would expose a broken one."""
    binding = bind_revision(revision("SYN-001-nominal"))
    assert binding is not None
    traced = trace_declaration(binding.spec)
    incidence = traced.incidence()
    rows, columns = list(traced.row_ids), list(traced.column_ids)
    expected = dulmage_mendelsohn(rows, columns, incidence)

    for seed in range(20):
        generator = random.Random(seed)
        shuffled_rows, shuffled_columns = list(rows), list(columns)
        generator.shuffle(shuffled_rows)
        generator.shuffle(shuffled_columns)
        other = maximum_matching(shuffled_rows, shuffled_columns, incidence)
        partition = dulmage_mendelsohn(rows, columns, incidence, other)
        assert partition.over_rows == expected.over_rows, seed
        assert partition.over_cols == expected.over_cols, seed
        assert partition.under_rows == expected.under_rows, seed
        assert partition.under_cols == expected.under_cols, seed
        assert partition.structural_rank == expected.structural_rank, seed


# ------------------------------------------------------------------- A06: certificates


def test_a06_the_certificates_match_the_registered_identities(reference: dict[str, Any]) -> None:
    registered = reference["cases"]["SYN-001-nominal"]["certificates"]
    certificates = report_for("SYN-001-nominal").certificates

    assert [entry.row_id for entry in certificates] == [entry["row_id"] for entry in registered]
    for found, expected in zip(certificates, registered, strict=True):
        assert signed_set(found.equals) == signed_set(expected["equals"]), found.row_id
        assert found.constant_mismatch == expected["constant_mismatch"] == 0.0
        assert found.tolerance == expected["tolerance"]
        assert found.consistent is True
    assert report_for("SYN-001-nominal").uncertified_affine_rows == ()


@pytest.mark.parametrize("case_id", VARIANTS)
def test_a06_t01_and_k03_certify_the_same_rows_by_the_same_identities(case_id: str) -> None:
    """The same certificate, issued twice: from the declaration here, from a Jacobian in K03.

    K03 needed two evaluated states to witness that the mismatch is constant; T01 reads it from
    the declaration. They must name the same rows and the same signed sums, and their mismatches
    must agree well inside the registered pressure tolerance. A wrong sign or a wrong path moves
    the mismatch by 1e5 Pa at the 150 kPa state, so `1e-6` is eleven orders below the defect.
    """
    from openflowsheet.compiled import EvaluationContext
    from openflowsheet.models.syn001.flowsheet import Syn001Flowsheet
    from openflowsheet.orchestrator.tear import Syn001TearProblem
    from openflowsheet.thermo.syn001 import Syn001Provider

    binding = bind_revision(revision(case_id))
    assert binding is not None
    mine = {entry.row_id: entry for entry in certify(trace_declaration(binding.spec)).certificates}

    settings = {
        "split_fraction": binding.spec.parameters["U-SPLIT.split_fraction"],
        "flash_temperature": binding.spec.parameters["U-FLASH.T_spec"],
        "heater_temperature": binding.spec.parameters["U-HEAT.T_spec"],
        "pressure": binding.spec.parameters["U-FLASH.P_spec"],
    }
    flowsheet = Syn001Flowsheet(
        provider=Syn001Provider(),
        context=EvaluationContext(
            model_version="k03", constants_sha256="0" * 64, phase_signature=None
        ),
        **settings,
    )
    theirs = {
        row.row_id: row for row in Syn001TearProblem(flowsheet).partition.elimination.eliminated
    }

    assert set(mine) == set(theirs), case_id
    for row_id, entry in mine.items():
        assert signed_set(entry.equals) == signed_set(theirs[row_id].equals), row_id
        assert abs(entry.constant_mismatch - theirs[row_id].constant_mismatch) <= 1e-6, row_id


# ------------------------------------------------------ A07: a certificate seen to fail


def test_a07_an_inconsistent_pressure_specification_is_a_conflict(
    reference: dict[str, Any],
) -> None:
    """K03 §7.2's registered conflict, decided from the declaration with nothing compiled.

    The flash at 150 kPa against a feed at 100 kPa: the closed form is `P_feed - P_f`, so both
    certificates carry `-50 000 Pa` exactly and the declaration has no state satisfying it. This
    is a registered *parameter set* and not a registered revision (specification §13) — SYN-001's
    flowsheet is parameterized by a single pressure, so no revision can express it — which is why
    it is reached here through the declaration rather than through `validate()`.
    """
    from dataclasses import replace

    registered = reference["cases"]["SYN-001-flash-150kPa"]
    binding = bind_revision(revision("SYN-001-nominal"))
    assert binding is not None
    conflicted = replace(
        binding.spec,
        parameters={**binding.spec.parameters, "U-FLASH.P_spec": 150_000.0},
    )
    assert conflicted.parameters["U-FEED.P_spec"] == 100_000.0, "the substitution landed"

    result = analyse(conflicted, binding.graph, specification_ids=binding.specification_ids)
    assert result.finding == registered["finding"] == "SPECIFICATION_CONFLICT"
    assert registered["certified_rows"] == [], "an inconsistent row is not certified"
    assert [entry.row_id for entry in result.certificates] == [
        entry["row_id"] for entry in registered["certificates"]
    ]
    assert [entry.constant_mismatch for entry in result.certificates] == [-50_000.0, -50_000.0]
    assert [entry["constant_mismatch"] for entry in registered["certificates"]] == [
        -50_000.0,
        -50_000.0,
    ]
    assert all(not entry.consistent for entry in result.certificates)
    assert result.implicated_objects[0] == "U-FLASH:FLASH-P:inlet"


# ------------------------------------------------- A08: the nominal case is *not* rejected


@pytest.mark.parametrize("case_id", VARIANTS)
def test_a08_a_valid_but_over_determined_declaration_is_accepted(case_id: str) -> None:
    """The measurement that shapes the package: over-determination is not a defect.

    All five registered variants declare 49 rows over 47 columns with a seven-row over-determined
    block. A validator that rejected an over-determined block would reject every one of them.
    """
    result = report_for(case_id)
    assert result.finding == "STRUCTURALLY_CLOSED", case_id
    assert result.excess == 0 and result.deficit == 0

    full = result.dm_full
    assert full is not None
    assert len(full.over_rows) == 7 and len(full.over_cols) == 5, "it *is* over-determined"
    certified = {entry.row_id for entry in result.certificates}
    assert full.excess == len(certified.intersection(full.over_rows)) == 2

    report = validate(revision(case_id))
    assert report.status == "READY_FOR_SIMULATION", case_id
    assert [check.id for check in report.checks if check.result == "FAIL"] == []


# ----------------------------------------- A09: the registered acceptance case, rejected


def test_a09_the_conflicting_heater_revision_is_rejected_at_validation(
    reference: dict[str, Any],
) -> None:
    """The first registered assertion, and the gap T01 exists to close.

    Before T01 this revision validated `READY_FOR_SIMULATION` and was refused downstream as
    `UNSUPPORTED_RANK_STRUCTURE` — a sentence about the tool. It is now rejected at validation,
    naming the heater and both of its specifications, and nothing is compiled or solved to do it.
    """
    registered = reference["cases"]["SYN-001-conflicting-heater-spec"]
    result = report_for("SYN-001-conflicting-heater-spec")

    assert result.finding == "STRUCTURAL_OVER_SPECIFICATION"
    assert result.excess == registered["excess"] == 1
    after = result.dm_after_certificates
    assert after is not None
    assert list(after.over_rows) == registered["dm_after_certificates"]["over_rows"]
    assert list(after.over_cols) == registered["dm_after_certificates"]["over_cols"]
    assert list(result.candidate_specification_rows) == registered["candidate_specification_rows"]
    # The reference serialises this one sorted; the report keeps declaration order, which is the
    # order every other sequence in it uses. The registered object is the set.
    assert sorted(result.candidate_specifications) == registered["candidate_specifications"]
    assert list(result.over_specified_units) == registered["over_specified_units"]

    report = validate(revision("SYN-001-conflicting-heater-spec"))
    assert report.status == "INVALID"
    check = next(entry for entry in report.checks if entry.id == "STR-03")
    assert check.result == "FAIL"
    assert check.stage == "structural_analysis"
    assert set(check.implicated_objects) == {
        "SPEC-heater-outlet-T",
        "SPEC-heater-duty",
        "heater",
    }
    assert "UNSUPPORTED_RANK_STRUCTURE" not in str(report.as_document())


def test_a09_the_candidate_list_is_complete_and_says_it_is_not_minimal() -> None:
    """Statement S4: relaxing *any* candidate closes the system, so none of them is "the" fault."""
    result = report_for("SYN-001-conflicting-heater-spec")
    assert len(result.candidate_specification_rows) == 10
    assert len(result.candidate_specifications) == 9
    assert "SPEC-feed-T" in result.candidate_specifications, "even the feed temperature qualifies"

    report = validate(revision("SYN-001-conflicting-heater-spec"))
    message = next(entry for entry in report.checks if entry.id == "STR-03").message
    assert STATEMENTS["S4"] in message
    assert STATEMENTS["S5"] in message
    assert "is not a minimal conflict set" in message


# ------------------------------------------------------------ A10: unit-local degrees of freedom


#: The reference file calls the vapour-product sink `U-PRODUCT`; the repository's constant is
#: `U-PROD` (`models/syn001/flowsheet.py`). A transcription difference in a unit that owns no
#: column and authors no row, so it changes no number — but it is a difference between the
#: specification's reference and the code, and it is named here rather than silently mapped.
REFERENCE_UNIT_NAMES = {"U-PRODUCT": "U-PROD"}


def test_a10_the_unit_degree_of_freedom_table_matches(reference: dict[str, Any]) -> None:
    for case_id in ("SYN-001-nominal", "SYN-001-conflicting-heater-spec"):
        registered = reference["cases"][case_id]["unit_degrees_of_freedom"]
        table = {entry.unit_id: entry for entry in report_for(case_id).unit_degrees_of_freedom}
        assert set(table) == {REFERENCE_UNIT_NAMES.get(name, name) for name in registered}
        for name, expected in registered.items():
            unit_id = REFERENCE_UNIT_NAMES.get(name, name)
            entry = table[unit_id]
            assert len(entry.columns) == expected["columns"], (case_id, unit_id)
            assert len(entry.model_rows) == expected["model_rows"], (case_id, unit_id)
            assert entry.model_rank == expected["model_rank"], (case_id, unit_id)
            assert entry.degrees_of_freedom == expected["dof"], (case_id, unit_id)
            assert entry.specifications == len(expected["specifications"]), (case_id, unit_id)
            assert entry.over_specified == expected["over_specified"], (case_id, unit_id)
            assert list(entry.local_excess_rows) == expected["local_excess_rows"], (
                case_id,
                unit_id,
            )


@pytest.mark.parametrize(
    ("case_id", "expected"), [("SYN-001-nominal", 0), ("SYN-001-conflicting-heater-spec", 1)]
)
def test_a10_the_bookkeeping_identity_ties_the_two_layers_together(
    case_id: str, expected: int
) -> None:
    """`sum(specs) + sum(local excess) - sum(dof) = excess - deficit`, executable.

    It is the reason the localization can be trusted as a second opinion rather than a heuristic:
    if a unit's count drifted from the global partition, this would not balance.
    """
    result = report_for(case_id)
    table = result.unit_degrees_of_freedom
    total = (
        sum(entry.specifications for entry in table)
        + sum(entry.local_excess for entry in table)
        - sum(entry.degrees_of_freedom for entry in table)
    )
    assert total == result.excess - result.deficit == expected


def test_a10_the_mixers_two_pressure_rows_are_a_constraint_on_its_inlets() -> None:
    """ADR 0001 D4.5: a zero drop is an equation. Two of them is one constraint, not a defect."""
    result = report_for("SYN-001-nominal")
    table = {entry.unit_id: entry for entry in result.unit_degrees_of_freedom}
    mixer = table["U-MIX"]
    assert set(mixer.local_excess_rows) == {"U-MIX:MIX-pressure:0", "U-MIX:MIX-pressure:1"}
    assert mixer.local_excess == 1
    assert not mixer.over_specified


# --------------------------------------------------------------- A11: the canonical matching


def test_a11_the_canonical_matching_matches_the_registered_one(reference: dict[str, Any]) -> None:
    registered = reference["cases"]["SYN-001-nominal"]
    binding = bind_revision(revision("SYN-001-nominal"))
    assert binding is not None
    traced = trace_declaration(binding.spec)
    matching = canonical_matching(list(traced.row_ids), list(traced.column_ids), traced.incidence())
    assert matching == registered["canonical_matching"]
    unmatched = [row for row in traced.row_ids if row not in set(matching.values())]
    assert unmatched == registered["unmatched_rows_canonical"]


def test_a11_tie_1_defeats_a_greedy_row_first_matcher(reference: dict[str, Any]) -> None:
    """A canonical rule needs a case where the obvious algorithm disagrees, or it proves nothing."""
    registered = reference["synthetic"]["TIE-1"]
    matching = canonical_matching(
        registered["rows"], registered["cols"], _synthetic(registered["incidence"])
    )
    assert matching == registered["canonical_matching"] == {"x1": "r2", "x2": "r1"}


def test_a11_the_recorded_matching_is_verified_minimal_by_an_oracle() -> None:
    """The recorded object is a *minimum*, checked by enumeration rather than trusted.

    §6.2 defines the canonical matching as the lexicographically least maximum matching. On the
    small fixtures the whole set can be enumerated, so minimality is proved rather than asserted.
    """
    import itertools

    fixtures = (
        (["r1", "r2"], ["x1", "x2"], {"r1": {"x1", "x2"}, "r2": {"x1"}}),
        (["r1", "r2", "r3"], ["x1", "x2", "x3"], {"r1": {"x1"}, "r2": {"x1"}, "r3": {"x2", "x3"}}),
    )
    for rows, columns, raw in fixtures:
        incidence = {row: frozenset(entries) for row, entries in raw.items()}
        found = canonical_matching(rows, columns, incidence)
        size = len(found)

        def key(
            candidate: Mapping[str, str],
            columns: Sequence[str] = columns,
            rows: Sequence[str] = rows,
        ) -> tuple[int, ...]:
            return tuple(
                rows.index(candidate[column]) if column in candidate else len(rows)
                for column in columns
            )

        best: dict[str, str] | None = None
        for count in range(size, size + 1):
            for chosen in itertools.permutations(rows, count):
                for picked in itertools.combinations(columns, count):
                    candidate = dict(zip(picked, chosen, strict=True))
                    if any(column not in incidence[row] for column, row in candidate.items()):
                        continue
                    if best is None or key(candidate) < key(best):
                        best = candidate
        assert best is not None
        assert found == best, "the recorded matching is not the lexicographically least one"


# ----------------------------------------------- A18/A19: the synthetic findings, each reached


def _synthetic(raw: Mapping[str, Sequence[str]]) -> Mapping[str, frozenset[str]]:
    return {row: frozenset(columns) for row, columns in raw.items()}


def test_a18_sq_1_is_square_by_totals_and_defective_in_both_directions(
    reference: dict[str, Any],
) -> None:
    """The plan's "square structural defect": a count-based validator passes this and is wrong."""
    registered = reference["synthetic"]["SQ-1"]
    partition = dulmage_mendelsohn(
        registered["rows"], registered["cols"], _synthetic(registered["incidence"])
    )
    assert partition.structural_rank == registered["structural_rank"] == 2
    assert list(partition.over_rows) == registered["dm"]["over_rows"]
    assert list(partition.over_cols) == registered["dm"]["over_cols"]
    assert list(partition.under_cols) == registered["dm"]["under_cols"]
    assert partition.excess == 1 and partition.deficit == 1
    assert (
        canonical_matching(
            registered["rows"], registered["cols"], _synthetic(registered["incidence"])
        )
        == registered["canonical_matching"]
    )


def test_a18_sq_2_is_structurally_closed_and_says_nothing_about_rank(
    reference: dict[str, Any],
) -> None:
    """D05's other half: `[[1, 1], [2, 2]]` is numerically singular and structurally perfect.

    The report must not reach for a rank word, in either direction. That verdict is K04's [A08]
    on the unregularized target Jacobian at a converged state, and T01 does not have one.
    """
    registered = reference["synthetic"]["SQ-2"]
    partition = dulmage_mendelsohn(
        registered["rows"], registered["cols"], _synthetic(registered["incidence"])
    )
    assert partition.structural_rank == registered["structural_rank"] == 2
    assert partition.excess == 0 and partition.deficit == 0

    spoken = " ".join(STATEMENTS.values())
    assert "makes no such claim, in either direction" in spoken
    assert "rank" not in " ".join(value for key, value in STATEMENTS.items() if key in {"S1", "S2"})


def test_a18_und_1_and_ovr_1_each_reach_their_finding(reference: dict[str, Any]) -> None:
    und = reference["synthetic"]["UND-1"]
    under = dulmage_mendelsohn(und["rows"], und["cols"], _synthetic(und["incidence"]))
    assert under.deficit == 1
    assert list(under.under_cols) == und["dm"]["under_cols"]
    assert list(under.under_rows) == und["dm"]["under_rows"]

    registered = reference["synthetic"]["OVR-1"]
    over = dulmage_mendelsohn(
        registered["rows"], registered["cols"], _synthetic(registered["incidence"])
    )
    assert over.excess == 1
    assert list(over.over_rows) == registered["dm"]["over_rows"]
    assert list(over.over_cols) == registered["dm"]["over_cols"]
    assert len(over.over_rows) == 2 and len(over.over_cols) == 1, (
        "a threshold on block size would accept this genuine over-specification"
    )


# ------------------------------------------------------------ A20/A24: unsupported is a result


def test_a20_a_row_that_cannot_be_traced_is_unsupported_and_never_a_pass() -> None:
    """A builder that branches on a value defeats the trace, loudly rather than silently."""
    from dataclasses import replace

    from openflowsheet.compile.spec import EquationSpec

    binding = bind_revision(revision("SYN-001-nominal"))
    assert binding is not None

    def branches(
        variables: Mapping[str, Any],
        blocks: Mapping[str, Any],
        parameters: Mapping[str, float],
        algebra: Any,
    ) -> Any:
        if parameters["U-SPLIT.split_fraction"] > 0.25:  # the trace cannot follow this
            return variables["S1.P"]
        return variables["S2.P"]

    broken = replace(
        binding.spec,
        equations=(
            *binding.spec.equations,
            EquationSpec(
                equation_id="BRANCHING", build=branches, accumulation="algebraic", origin="test"
            ),
        ),
    )
    result = analyse(broken, binding.graph)
    assert result.finding == "UNSUPPORTED"
    assert result.structural_counts is None
    assert [entry.kind for entry in result.unsupported] == ["structure_unavailable"]
    assert result.unsupported[0].row_id == "BRANCHING"


def test_a20_what_is_not_applicable_is_named_rather_than_left_out() -> None:
    """A declaration that is not closed has no square system; that is said, not implied.

    Increment 1 carried `not_implemented` entries here. Increment 2 built both, so the only
    absence left is the honest one: §7.1 defines the block-triangular form on a square, perfectly
    matched incidence, and the conflicting revision has none.
    """
    closed = report_for("SYN-001-nominal")
    assert closed.unsupported == ()
    assert closed.block_triangular_form is not None
    assert closed.tear is not None

    conflicting = report_for("SYN-001-conflicting-heater-spec")
    assert conflicting.block_triangular_form is None
    assert conflicting.tear is None
    assert [entry.kind for entry in conflicting.unsupported] == ["not_applicable"]
    assert "structurally closed system" in conflicting.unsupported[0].detail

    report = validate(revision("SYN-001-conflicting-heater-spec"))
    metrics = next(check for check in report.checks if check.id == "STR-05")
    assert metrics.result == "NOT_RUN"
    assert "STRUCTURAL_OVER_SPECIFICATION" in metrics.message


def test_a20_a_revision_that_cannot_be_bound_is_not_run_and_not_ready() -> None:
    """A validator that passed a revision because it could not look would be a placeholder."""
    document = revision("SYN-001-nominal")
    for instance in document["instances"]:
        instance["model"]["id"] = "unknown.model"

    report = validate(document)
    assert report.structural_counts is None
    assert report.structural_counts_absent_reason is not None
    assert "cannot be analysed" in report.structural_counts_absent_reason
    assert {check.result for check in report.checks if check.stage == "structural_analysis"} == {
        "NOT_RUN"
    }
    # The assertion this test is named for, and did not make until the Fable review of T01 pointed
    # it out (M3, M5(d)): a revision is not ready because nobody could look at it. Nor is it
    # wrong — the tool could not read it — so it is `DRAFT`, not `INVALID` (R-022).
    assert report.status == "DRAFT"
    assert not report.ready


def test_a24_structural_counts_are_present_exactly_when_the_analysis_ran() -> None:
    """The absent reason and the counts are never both present and never both missing."""
    for case_id in (*VARIANTS, "SYN-001-conflicting-heater-spec"):
        report = validate(revision(case_id))
        assert report.structural_counts is not None, case_id
        assert report.structural_counts_absent_reason is None, case_id

    broken = {"revision_id": "broken"}
    report = validate(broken)
    assert report.structural_counts is None
    assert report.structural_counts_absent_reason is not None


# ------------------------------------------------------------ A21: specification promotion


def test_a21_the_conflicting_duty_is_promoted_to_an_assembler_authored_row() -> None:
    """§5.1, and what it deliberately avoids.

    The heater's own constructor refuses a `specified_duty`. That refusal is a `SpecificationError`
    from Python, not a structural finding, and it names nothing a report can carry — so the
    binding must not reach it.
    """
    from openflowsheet.compiled import EvaluationContext
    from openflowsheet.models import SpecificationError
    from openflowsheet.models.syn001.heater import TPHeater
    from openflowsheet.thermo.syn001 import Syn001Provider

    context = EvaluationContext(
        model_version="probe", constants_sha256="0" * 64, phase_signature=None
    )

    binding = bind_revision(revision("SYN-001-conflicting-heater-spec"))
    assert binding is not None
    promoted = [
        equation
        for equation in binding.spec.equations
        if equation.equation_id == "SPEC:SPEC-heater-duty"
    ]
    assert len(promoted) == 1
    assert promoted[0].accumulation == "algebraic"
    assert promoted[0].origin == "revision#SPEC-heater-duty"
    assert binding.specification_ids["SPEC:SPEC-heater-duty"] == "SPEC-heater-duty"

    traced = trace_declaration(binding.spec, specification_ids=binding.specification_ids)
    assert traced.rows["SPEC:SPEC-heater-duty"].columns == ("U-HEAT.Q",)
    assert len(traced.row_ids) == 50 and traced.nnz == 171

    # The guard exists and would fire if the binding reached it. An earlier version of this test
    # raised the exception itself inside `pytest.raises`, which cannot fail and asserted nothing
    # (M5(c) of the Fable review of T01). This constructs the heater the way the binding must not.
    with pytest.raises(SpecificationError):
        TPHeater(
            unit_id="U-PROBE",
            provider=Syn001Provider(),
            outlet_temperature=350.0,
            context=context,
            inlet_phase="LIQUID",
            components=("A", "B", "C"),
            specified_duty=50_000.0,
        )


def test_a21_a_specification_already_pinned_by_a_unit_row_is_not_promoted() -> None:
    """Promotion is for a column *no unit row already pins*; the flash's T and P are pinned."""
    binding = bind_revision(revision("SYN-001-nominal"))
    assert binding is not None
    promoted = [
        equation.equation_id
        for equation in binding.spec.equations
        if equation.equation_id.startswith("SPEC:")
    ]
    assert promoted == []
    assert len(binding.spec.equations) == 49


# ------------------------------------------------------------ the report's own honesty


def test_the_report_carries_the_six_statements_verbatim() -> None:
    document = report_for("SYN-001-nominal").as_document()
    assert document["statements"] == dict(STATEMENTS)
    assert len(STATEMENTS) == 6


def test_every_t01_check_is_labelled_structural() -> None:
    """Blueprint §4.3: a rank or conflict search labels its evidence class. T01 has exactly one."""
    for case_id in ("SYN-001-nominal", "SYN-001-conflicting-heater-spec"):
        report = validate(revision(case_id))
        structural = [check for check in report.checks if check.stage == "structural_analysis"]
        assert structural
        assert {check.evidence_class for check in structural} == {"structural"}
        assert "local_numerical" not in str(report.as_document())
        assert "verified_minimal_subset" not in str(report.as_document())


def test_the_r0_projection_carries_no_floats() -> None:
    """ADR 0007: what gate G05 compares between architectures must be exactly reproducible."""

    def floats_in(value: Any, path: str = "") -> list[str]:
        if isinstance(value, bool):
            return []
        if isinstance(value, float):
            return [path]
        if isinstance(value, dict):
            return [
                found for key, item in value.items() for found in floats_in(item, f"{path}/{key}")
            ]
        if isinstance(value, list):
            return [found for index, item in enumerate(value) for found in floats_in(item, path)]
        return []

    for case_id in ("SYN-001-nominal", "SYN-001-conflicting-heater-spec"):
        projection = report_for(case_id).r0_projection()
        assert floats_in(projection) == [], case_id


def test_there_is_no_heat_rate_certificate_class() -> None:
    """ADR 0001 D6 registers no `heat_rate` tolerance, so a duty alias is never certified.

    Specification §19 finding 9: not a defect today, because SYN-001 declares no duty copy. It
    becomes one the day a unit does, and the fix is a D6 line rather than a rule invented here.
    """
    assert set(CERTIFIABLE_KINDS) == {"pressure", "temperature"}
    assert CERTIFIABLE_KINDS["pressure"] == 1e-2
    assert CERTIFIABLE_KINDS["temperature"] == 1e-6


# ============================================================ increment 2: SCC, BTF, tear


# ------------------------------------------------------------------ A13: block-triangular form


def test_a13_the_block_triangular_form_matches_block_for_block(reference: dict[str, Any]) -> None:
    """24 blocks, `[17, 8, 1x22]`, and the canonical order, against an independent derivation."""
    registered = reference["block_triangular_form"]
    form = report_for("SYN-001-nominal").block_triangular_form
    assert form is not None

    assert form.block_count == registered["block_count"] == 24
    assert list(form.block_sizes_sorted) == registered["block_sizes_sorted"]
    assert form.largest_block_fraction == registered["largest_block_fraction"]["double"]
    assert form.largest_block_fraction == 17 / 47

    for found, expected in zip(form.blocks, registered["blocks"], strict=True):
        assert list(found.rows) == expected["rows"]
        assert sorted(found.cols) == sorted(expected["cols"])
        assert list(found.depends_on) == expected["depends_on"]


def test_a13_the_recycle_block_is_the_largest_and_the_lifted_split_depends_on_it() -> None:
    """The 8-block is a *consequence* of the loop, never a cause: S3's split follows the recycle."""
    form = report_for("SYN-001-nominal").block_triangular_form
    assert form is not None
    sized = {block.size: index for index, block in enumerate(form.blocks) if block.size > 1}
    assert set(sized) == {17, 8}
    recycle, lifted = sized[17], sized[8]
    assert recycle in form.blocks[lifted].depends_on
    assert lifted not in form.ancestors_of([recycle])


def test_a13_btf_1_defeats_a_first_in_first_out_topological_sort(
    reference: dict[str, Any],
) -> None:
    """A canonical order needs a case where the obvious algorithm disagrees."""
    from openflowsheet.graph.blocks import block_triangular_form

    registered = reference["synthetic"]["BTF-1"]
    incidence = _synthetic(registered["incidence"])
    matching = canonical_matching(registered["rows"], registered["cols"], incidence)
    form = block_triangular_form(registered["rows"], incidence, matching)
    assert [list(block.rows) for block in form.blocks] == registered["block_order"]
    assert [list(block.rows) for block in form.blocks] == [["a"], ["b"], ["c"], ["d"]]


# ------------------------------------------------------------------------------- A14: the tear


def test_a14_the_three_variable_tear_is_rediscovered(reference: dict[str, Any]) -> None:
    """Plan §3.2's obligation: derived from the incidence graph, never read from the flowsheet."""
    registered = reference["tear"]
    tear = report_for("SYN-001-nominal").tear
    assert tear is not None

    assert [list(loop.units) for loop in tear.loops] == registered["process_loops"]
    loop = tear.loops[0]
    assert list(loop.cycle_edges) == registered["loop"]["cycle_edges"]

    found = {candidate.stream_id: candidate for candidate in loop.candidates}
    for expected in registered["loop"]["candidates"]:
        candidate = found[expected["stream"]]
        assert candidate.breaks_loop is expected["breaks_loop"]
        assert candidate.dimension == expected["dimension"] == 3
        assert list(candidate.torn_variables) == expected["torn_variables"]
        assert list(candidate.not_torn) == expected["not_torn"]
        assert candidate.consumer_boundary_distance == expected["consumer_boundary_distance"], (
            expected["stream"]
        )

    assert loop.chosen_stream == registered["loop"]["chosen_stream"]
    assert loop.tie_break_used == registered["loop"]["tie_break_used"] == "boundary_distance"
    assert list(loop.tear_variables) == registered["loop"]["tear_variables"]
    assert list(loop.tear_rows) == registered["loop"]["tear_rows"]


@pytest.mark.parametrize("case_id", VARIANTS)
def test_a14_the_tear_equals_k03s_partition_by_id(case_id: str) -> None:
    """The same partition, derived twice: from the graph here, declared in K03's plan.

    K03 chose its three-variable tear from plan §3.2 and was told not to generalize it. T01 has to
    arrive at the same rows and columns from the incidence alone, or the reduction was a guess.
    """
    from openflowsheet.compiled import EvaluationContext
    from openflowsheet.models.syn001.flowsheet import Syn001Flowsheet
    from openflowsheet.orchestrator.tear import Syn001TearProblem
    from openflowsheet.thermo.syn001 import Syn001Provider

    binding = bind_revision(revision(case_id))
    assert binding is not None
    tear = report_for(case_id).tear
    assert tear is not None
    loop = tear.loops[0]

    flowsheet = Syn001Flowsheet(
        provider=Syn001Provider(),
        context=EvaluationContext(
            model_version="k03", constants_sha256="0" * 64, phase_signature=None
        ),
        split_fraction=binding.spec.parameters["U-SPLIT.split_fraction"],
        flash_temperature=binding.spec.parameters["U-FLASH.T_spec"],
        heater_temperature=binding.spec.parameters["U-HEAT.T_spec"],
        pressure=binding.spec.parameters["U-FLASH.P_spec"],
    )
    partition = Syn001TearProblem(flowsheet).partition

    assert set(loop.tear_variables) == set(partition.tear_variables)
    assert set(loop.tear_rows) == set(partition.tear_rows)
    assert set(tear.inner_rows) == set(partition.inner_rows)
    assert set(tear.inner_variables) == set(partition.inner_variables)


# ------------------------------------------------------- A15: the answer is not hard-coded


def test_a15_relabelling_every_id_gives_the_image_of_the_registered_answer() -> None:
    """The strongest test here: rename everything and the same structure must come back.

    If any of the tear, the certificates or the signature were recognised by name rather than
    derived, a bijection on the ids would break it. Nothing in the flowsheet's *structure*
    changes, so every answer must be the image of the registered one under the same bijection.
    """
    from dataclasses import replace

    from openflowsheet.compile.spec import EquationSpec
    from openflowsheet.graph.process import Connection, ProcessGraph

    binding = bind_revision(revision("SYN-001-nominal"))
    assert binding is not None
    expected = report_for("SYN-001-nominal")

    def rename(name: str) -> str:
        return "X-" + name

    columns = {name: rename(name) for name in binding.spec.variable_ids}
    rows = {
        equation.equation_id: rename(equation.equation_id) for equation in binding.spec.equations
    }

    def relabel_builder(build: Any) -> Any:
        def built(
            variables: Mapping[str, Any],
            blocks: Mapping[str, Any],
            parameters: Mapping[str, float],
            algebra: Any,
        ) -> Any:
            return build(
                {original: variables[renamed] for original, renamed in columns.items()},
                blocks,
                parameters,
                algebra,
            )

        return built

    relabelled = replace(
        binding.spec,
        variable_ids=tuple(columns[name] for name in binding.spec.variable_ids),
        equations=tuple(
            EquationSpec(
                equation_id=rows[equation.equation_id],
                build=relabel_builder(equation.build),
                accumulation=equation.accumulation,
                origin=equation.origin,
            )
            for equation in binding.spec.equations
        ),
        variable_kinds={columns[name]: kind for name, kind in binding.spec.variable_kinds.items()},
        row_kinds={rows[name]: kind for name, kind in binding.spec.row_kinds.items()},
        block_inputs={
            block: tuple(columns[name] for name in inputs)
            for block, inputs in binding.spec.block_inputs.items()
        },
        column_scales={columns[name]: value for name, value in binding.spec.column_scales.items()},
        row_scales={rows[name]: value for name, value in binding.spec.row_scales.items()},
    )
    graph = ProcessGraph(
        units=tuple(rename(unit) for unit in binding.graph.units),
        connections=tuple(
            Connection(
                stream_id=rename(connection.stream_id),
                producer=rename(connection.producer),
                consumer=rename(connection.consumer),
                state_columns=tuple(columns[name] for name in connection.state_columns),
            )
            for connection in binding.graph.connections
        ),
        instance_ids={rename(unit): name for unit, name in binding.graph.instance_ids.items()},
    )
    result = analyse(
        relabelled,
        graph,
        row_units={
            rows[row]: rename(unit) for row, unit in binding.row_units.items() if row in rows
        },
    )

    assert result.finding == expected.finding
    assert result.structural_counts == expected.structural_counts
    assert result.nnz == expected.nnz
    assert [entry.row_id for entry in result.certificates] == [
        rows[entry.row_id] for entry in expected.certificates
    ]
    assert result.block_triangular_form is not None
    assert expected.block_triangular_form is not None
    assert (
        result.block_triangular_form.block_sizes_sorted
        == expected.block_triangular_form.block_sizes_sorted
    )
    assert result.tear is not None and expected.tear is not None
    assert list(result.tear.loops[0].tear_variables) == [
        columns[name] for name in expected.tear.loops[0].tear_variables
    ]
    assert list(result.tear.loops[0].tear_rows) == [
        rows[name] for name in expected.tear.loops[0].tear_rows
    ]
    assert list(result.tear.signature_units) == [
        rename(unit) for unit in expected.tear.signature_units
    ]


def test_a15_the_graph_package_names_no_syn001_object() -> None:
    """Grep: the answer cannot be recognised by name if the name is not in the package.

    The one collision is `"S6"`, which in `report.py` is §11's sixth *statement* label and not a
    stream id. It is stripped by name rather than by weakening the search, so a stream id of that
    spelling appearing anywhere else would still be caught.
    """
    package = REPO_ROOT / "src" / "openflowsheet" / "graph"
    forbidden = ("S6", "SPLIT-recycle", "U-FLASH", "U-HEAT", "U-SPLIT", "U-MIX", "U-FEED")
    statement_labels = tuple(f'"{key}": (' for key in STATEMENTS)

    offenders = []
    for path in sorted(package.glob("*.py")):
        text = path.read_text()
        for label in statement_labels:
            text = text.replace(label, "")
        offenders += [f"{path.name}: {name}" for name in forbidden if name in text]
    assert offenders == [], offenders

    imports = [
        path.name
        for path in sorted(package.glob("*.py"))
        if "openflowsheet.models" in path.read_text()
    ]
    assert imports == [], "the graph layer imports no unit model"


def test_a15_loop_3_chooses_an_edge_that_is_neither_first_nor_last() -> None:
    """§9.3's tie chain, on a loop where "first" and "last" rules give different answers."""
    from openflowsheet.graph.blocks import block_triangular_form
    from openflowsheet.graph.process import Connection, ProcessGraph
    from openflowsheet.graph.tear import analyse_tear
    from openflowsheet.graph.trace import Declaration, TracedRow

    units = ("FEED", "A", "B", "C")
    edges = (
        Connection("s_in", "FEED", "C", ("s_in.x",)),
        Connection("s_ab", "A", "B", ("s_ab.x",)),
        Connection("s_bc", "B", "C", ("s_bc.x",)),
        Connection("s_ca", "C", "A", ("s_ca.x",)),
    )
    graph = ProcessGraph(units=units, connections=edges, instance_ids={})
    distances = {connection.stream_id: connection for connection in edges}
    assert set(distances) == {"s_in", "s_ab", "s_bc", "s_ca"}

    # A coupled block over the three loop streams, so every candidate has dimension 1.
    columns = ("s_ab.x", "s_bc.x", "s_ca.x")
    rows = ("r_ab", "r_bc", "r_ca")
    incidence = {
        "r_ab": frozenset(columns),
        "r_bc": frozenset(columns),
        "r_ca": frozenset(columns),
    }
    declaration = Declaration(
        model_version="",
        constants_sha256="",
        column_ids=columns,
        row_ids=rows,
        rows={
            row: TracedRow(
                row_id=row,
                columns=columns,
                coefficients=None,
                kind=None,
                unit={"r_ab": "A", "r_bc": "B", "r_ca": "C"}[row],
                specification_id=None,
                origin="",
                _constant=_zero_constant(),
            )
            for row in rows
        },
        column_kinds={},
        parameters={},
    )
    matching = canonical_matching(list(rows), list(columns), incidence)
    form = block_triangular_form(list(rows), incidence, matching)
    tear = analyse_tear(declaration, graph, retained_rows=rows, square_form=form)

    loop = tear.loops[0]
    chosen = loop.chosen_stream
    order = [connection.stream_id for connection in edges if connection.stream_id != "s_in"]
    assert chosen == "s_bc"
    assert chosen != order[0] and chosen != order[-1], "'first' and 'last' rules would differ"
    assert loop.tie_break_used == "boundary_distance"


def _zero_constant() -> Any:
    from openflowsheet.graph.trace import _Constant

    return _Constant.of(0.0)


# -------------------------------------------------- A16: the inner system and the signature


def test_a16_the_attempt_signature_is_derived_and_equals_k03s_declared_instance(
    reference: dict[str, Any],
) -> None:
    """K03 §9.1 declared `(U-FLASH,)` and left the general rule to T01. Here is the rule.

    Ancestry, not membership in the loop: the heater is in the recycle loop and its lifted block
    is *not* upstream of the tear rows, which is why freezing its regime put a spurious phase wall
    at the nominal state. A membership rule would have frozen it.
    """
    from openflowsheet.orchestrator.attempts import SIGNATURE_UNITS

    registered = reference["tear"]["signature"]
    tear = report_for("SYN-001-nominal").tear
    assert tear is not None
    assert tear.inner_form is not None

    assert tear.inner_form.block_count == len(reference["tear"]["inner_blocks"])
    assert (
        list(tear.inner_form.block_sizes_sorted) == (reference["tear"]["inner_block_sizes_sorted"])
    )
    assert list(tear.ancestor_blocks_of_tear_rows) == registered["ancestor_blocks_of_tear_rows"]

    found = {unit: (blocks, upstream) for unit, blocks, upstream in tear.phase_selecting}
    for expected in registered["phase_selecting"]:
        blocks, upstream = found[expected["unit"]]
        assert list(blocks) == expected["lifted_blocks"], expected["unit"]
        assert upstream is expected["upstream_of_tear"], expected["unit"]

    assert list(tear.signature_units) == registered["signature_units"] == ["U-FLASH"]
    assert tuple(tear.signature_units) == SIGNATURE_UNITS, "K03's declared instance, derived"


# --------------------------------------------------- A12/A17: order classes and state freedom


def test_a12_the_invariant_objects_survive_twenty_permutations_of_the_declaration() -> None:
    """§6.4: the sets are invariant; the sequences are canonical *given* the declaration order.

    The permutation is applied to the *matching* that the partition is computed from, which is
    what a different declaration order would change.
    """
    binding = bind_revision(revision("SYN-001-nominal"))
    assert binding is not None
    traced = trace_declaration(binding.spec)
    incidence = traced.incidence()
    expected = report_for("SYN-001-nominal")
    assert expected.block_triangular_form is not None

    for seed in range(20):
        generator = random.Random(seed)
        rows, columns = list(traced.row_ids), list(traced.column_ids)
        generator.shuffle(rows)
        generator.shuffle(columns)
        partition = dulmage_mendelsohn(
            list(traced.row_ids),
            list(traced.column_ids),
            incidence,
            maximum_matching(rows, columns, incidence),
        )
        assert partition.structural_rank == 47, seed
        assert partition.over_rows == (expected.dm_full.over_rows if expected.dm_full else ()), seed


@pytest.mark.parametrize("case_id", VARIANTS)
def test_a17_every_registered_variant_gives_the_same_structural_result(case_id: str) -> None:
    """Zero-flow is not a structural event: the analysis takes no state, so nothing can move.

    Two of these variants have dormant streams (`S4` at 310 K, the liquid side at 420 K) and one
    has a dormant recycle at `r = 0`. The declared structure does not depend on flow, and the R0
    projections are identical once the identity fields are removed.
    """

    def projection(name: str) -> dict[str, Any]:
        document = report_for(name).r0_projection()
        document.pop("model_version", None)
        document.pop("constants_sha256", None)
        return document

    assert projection(case_id) == projection("SYN-001-nominal"), case_id


# -------------------------------------------------- A02: the backend pattern, as a cross-check


def test_a02_the_backend_pattern_is_a_subset_and_differs_only_where_a_parameter_folds() -> None:
    """The measurement that overturned brief §4.1, stated as the cross-check the spec asks for.

    The compiled sparsity is a fact about the *compiled function*, not about the declaration: it
    equals the traced incidence at every registered variant except `r = 0`, where CasADi folds
    `0.0 * S5.n_i` and exactly the three recycle entries disappear. The difference is registered
    **because** it vanishes.
    """
    import numpy as np

    from openflowsheet.compile.casadi_backend import compile_problem
    from openflowsheet.compile.reference import state_vector
    from openflowsheet.compiled import EvaluationContext
    from openflowsheet.models.syn001.flowsheet import Syn001Flowsheet
    from openflowsheet.orchestrator.tear import Syn001TearProblem
    from openflowsheet.thermo.syn001 import Syn001Provider

    assert compile_problem is not None
    differences: dict[str, set[tuple[str, str]]] = {}
    for case_id in VARIANTS:
        binding = bind_revision(revision(case_id))
        assert binding is not None
        traced = trace_declaration(binding.spec)

        flowsheet = Syn001Flowsheet(
            provider=Syn001Provider(),
            context=EvaluationContext(
                model_version="x", constants_sha256="0" * 64, phase_signature=None
            ),
            split_fraction=binding.spec.parameters["U-SPLIT.split_fraction"],
            flash_temperature=binding.spec.parameters["U-FLASH.T_spec"],
            heater_temperature=binding.spec.parameters["U-HEAT.T_spec"],
            pressure=binding.spec.parameters["U-FLASH.P_spec"],
        )
        problem = Syn001TearProblem(flowsheet)
        state = problem.reconstruct(flowsheet.initial_recycle())
        jacobian = problem.compiled.jacobian(
            np.array(state_vector(problem.spec, state)), problem.context
        )
        assert jacobian.status == "ok"
        assert jacobian.pattern_provenance == "backend-declared"

        compiled = {
            (jacobian.row_ids[jacobian.indices[offset]], jacobian.col_ids[column])
            for column in range(len(jacobian.col_ids))
            for offset in range(jacobian.indptr[column], jacobian.indptr[column + 1])
        }
        declared = {
            (row_id, column) for row_id in traced.row_ids for column in traced.rows[row_id].columns
        }
        assert compiled <= declared, case_id
        differences[case_id] = declared - compiled

    assert differences["SYN-001-once-through"] == {
        ("U-SPLIT:SPLIT-recycle:A", "S5.n.A"),
        ("U-SPLIT:SPLIT-recycle:B", "S5.n.B"),
        ("U-SPLIT:SPLIT-recycle:C", "S5.n.C"),
    }
    for case_id in VARIANTS:
        if case_id != "SYN-001-once-through":
            assert differences[case_id] == set(), case_id


# ----------------------------------------------- A22/A23: the report travels, and stays labelled


def test_a22_the_structural_report_is_in_the_bundle_and_in_the_g05_comparison(
    tmp_path: Path,
) -> None:
    """Open question Q4 and assertion A22: what G05 compares must include this.

    Gate G05 compares structural artifacts between x86-64 and aarch64 on every push. A structural
    analysis that never entered that comparison would be the one artifact in the bundle nobody
    checked for platform agreement — and it is the one that is *entirely* structural.
    """
    import os

    from openflowsheet.compiled import EvaluationContext
    from openflowsheet.models.syn001.flowsheet import Syn001Flowsheet
    from openflowsheet.run.bundle import read_artifact
    from openflowsheet.run.identity import floats_in, r0_projection
    from openflowsheet.run.session import run_session
    from openflowsheet.thermo.syn001 import Syn001Provider

    for variable in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
        os.environ.setdefault(variable, "1")

    flowsheet = Syn001Flowsheet(
        provider=Syn001Provider(),
        context=EvaluationContext(
            model_version="bundle", constants_sha256="0" * 64, phase_signature=None
        ),
    )
    manifest = run_session(flowsheet, tmp_path, run_id="t01-a22")
    assert "structural-report.json" in manifest.artifacts

    artifacts = {name: read_artifact(tmp_path, name) for name in manifest.artifacts}
    projection = r0_projection(artifacts)
    assert "structural" in projection
    structural = projection["structural"]
    assert structural["finding"] == "STRUCTURALLY_CLOSED"
    assert structural["block_triangular_form"]["block_count"] == 24
    assert structural["tear"]["loops"][0]["tear_variables"] == ["S6.n.A", "S6.n.B", "S6.n.C"]
    assert structural["tear"]["signature_units"] == ["U-FLASH"]
    assert floats_in(projection) == [], "R0 carries no float, at any depth"

    # S3: the comparison sees the *sequences* §6.4 says it exists to compare, not a subset that
    # happens to be handy. The canonical block order and every `depends_on` are in it.
    blocks = structural["block_triangular_form"]["blocks"]
    assert [block["rows"] for block in blocks][:1] == [["U-FEED:FEED-n:A"]]
    assert any(block["depends_on"] for block in blocks)
    assert structural["canonical_matching"]


def test_a23_every_structural_check_is_labelled_and_claims_only_structure() -> None:
    """Blueprint §4.3's evidence class, and the two words T01 must never emit."""
    for case_id in ("SYN-001-nominal", "SYN-001-conflicting-heater-spec"):
        report = validate(revision(case_id))
        structural = [check for check in report.checks if check.stage == "structural_analysis"]
        assert len(structural) >= 5
        assert {check.evidence_class for check in structural} == {"structural"}
        document = str(report.as_document())
        assert "local_numerical" not in document
        assert "verified_minimal_subset" not in document


def test_a23_the_report_never_reaches_for_a_rank_word() -> None:
    """D05's separation, enforced on the text a reader actually sees.

    `structural rank` is the size of a maximum matching and is not a numerical rank; every other
    rank word belongs to K04's [A08] screen, which runs on a Jacobian at a converged state.
    """
    forbidden = ("RANK_DEFICIENT", "ILL_CONDITIONED", "NO_RANK_LOSS_DETECTED", "INCONCLUSIVE")
    for case_id in ("SYN-001-nominal", "SYN-001-conflicting-heater-spec"):
        document = str(validate(revision(case_id)).as_document())
        for word in forbidden:
            assert word not in document, (case_id, word)
        # Two uses of the word are legitimate and no others: `structural rank`, which is the size
        # of a maximum matching, and statement S3, which *disclaims* a numerical rank claim.
        # Strip the disclaimer, then every remaining occurrence must be the structural one.
        remaining = document.replace(STATEMENTS["S3"], "")
        assert "rank" in STATEMENTS["S3"], "S3 is the disclaimer being stripped"
        assert remaining.count("rank") == remaining.count("structural rank"), (
            case_id,
            "the report used the word 'rank' for something other than the structural one",
        )
        assert remaining.count("structural rank") >= 1, case_id


# ============================================ the Fable review of T01: the four must-fixes


def _pressure_row(row_id: str, coefficients: Mapping[str, float], constant: float) -> Any:
    from openflowsheet.graph.trace import TracedRow, _Constant

    return TracedRow(
        row_id=row_id,
        columns=tuple(coefficients),
        coefficients=dict(coefficients),
        kind="pressure",
        unit=None,
        specification_id=None,
        origin="",
        _constant=_Constant.of(constant),
    )


def _pressure_declaration(rows: Mapping[str, Any], columns: Sequence[str]) -> Any:
    from openflowsheet.graph.trace import Declaration

    return Declaration(
        model_version="",
        constants_sha256="",
        column_ids=tuple(columns),
        row_ids=tuple(rows),
        rows=dict(rows),
        column_kinds=dict.fromkeys(columns, "pressure"),
        parameters={},
    )


def test_m4_a_two_column_row_whose_coefficients_do_not_cancel_is_not_a_copy() -> None:
    """`UNC-2`: `P1 + P2 - s` is a sum, not a copy, and certifying it asserts a falsehood.

    Measured by the Fable review of T01 (M4). The row passed the "at most two columns, every
    coefficient ±1" test, took `P1` as its positive node and the constant node as its negative,
    and was certified as equal to `P1 - s` — an identity false at every state. With a matching
    constant it would have been removed from the closure count on that false identity, which is
    exactly what blueprint §7.7 forbids.

    The defect was in three places at once: here, the specification's §8.2 wording, and the
    reference generator. A copy is a *difference*.
    """
    declaration = _pressure_declaration(
        {
            "p1": _pressure_row("p1", {"P1": 1.0}, -100_000.0),
            "p2": _pressure_row("p2", {"P2": 1.0}, -100_000.0),
            "p3": _pressure_row("p3", {"P1": 1.0, "P2": 1.0}, -100_000.0),
        },
        ["P1", "P2"],
    )
    result = certify(declaration)
    assert result.certificates == ()
    assert list(result.uncertified_affine_rows) == ["p3"]


def test_m4_a_genuine_copy_chain_still_certifies() -> None:
    """The fix must not close the door it exists to keep open: `P2 - P1` is a copy."""
    declaration = _pressure_declaration(
        {
            "q1": _pressure_row("q1", {"P1": 1.0}, -100_000.0),
            "q2": _pressure_row("q2", {"P2": 1.0, "P1": -1.0}, 0.0),
            "q3": _pressure_row("q3", {"P2": 1.0}, -100_000.0),
        },
        ["P1", "P2"],
    )
    result = certify(declaration)
    assert [entry.row_id for entry in result.certificates] == ["q3"]
    assert result.certificates[0].constant_mismatch == 0.0
    assert result.certificates[0].consistent
    assert result.uncertified_affine_rows == ()


def test_m1_two_recycles_sharing_a_unit_are_a_multi_edge_feedback_set() -> None:
    """A20(b): no single edge breaks a figure-eight, and saying otherwise leaves a loop inside.

    Measured by the Fable review of T01 (M1). `breaks_loop` asked whether the strongly connected
    component was still the *whole* unit set, which is False as soon as the loop splits in two —
    so every edge read as breaking, one tear was chosen, and a recycle survived in the supposedly
    acyclic inner system. SYN-001's single simple cycle cannot tell the two tests apart, which is
    why this fixture exists.
    """
    from openflowsheet.graph.blocks import block_triangular_form
    from openflowsheet.graph.process import Connection, ProcessGraph
    from openflowsheet.graph.tear import analyse_tear
    from openflowsheet.graph.trace import Declaration, TracedRow, _Constant

    units = ("F", "A", "B", "C")
    columns = ("s_ab.x", "s_ba.x", "s_bc.x", "s_cb.x")
    connections = (
        Connection("s_in", "F", "A", ("s_in.x",)),
        Connection("s_ab", "A", "B", ("s_ab.x",)),
        Connection("s_ba", "B", "A", ("s_ba.x",)),
        Connection("s_bc", "B", "C", ("s_bc.x",)),
        Connection("s_cb", "C", "B", ("s_cb.x",)),
    )
    graph = ProcessGraph(units=units, connections=connections, instance_ids={})

    rows = ("r_a", "r_b", "r_c", "r_d")
    owners = {"r_a": "A", "r_b": "B", "r_c": "C", "r_d": "B"}
    incidence = dict.fromkeys(rows, frozenset(columns))
    declaration = Declaration(
        model_version="",
        constants_sha256="",
        column_ids=columns,
        row_ids=rows,
        rows={
            row: TracedRow(
                row_id=row,
                columns=columns,
                coefficients=None,
                kind=None,
                unit=owners[row],
                specification_id=None,
                origin="",
                _constant=_Constant.of(0.0),
            )
            for row in rows
        },
        column_kinds={},
        parameters={},
    )
    matching = canonical_matching(list(rows), list(columns), incidence)
    form = block_triangular_form(list(rows), incidence, matching)
    tear = analyse_tear(declaration, graph, retained_rows=rows, square_form=form)

    loop = tear.loops[0]
    assert set(loop.units) == {"A", "B", "C"}
    assert not any(candidate.breaks_loop for candidate in loop.candidates)
    assert loop.chosen_stream is None
    assert loop.unsupported == "multi_edge_feedback_set"
    assert loop.tear_variables == () and loop.tear_rows == ()


def test_m1_a_simple_cycle_is_still_broken_by_every_one_of_its_edges() -> None:
    """The fix must not turn SYN-001's own loop into an unsupported one."""
    tear = report_for("SYN-001-nominal").tear
    assert tear is not None
    loop = tear.loops[0]
    assert all(candidate.breaks_loop for candidate in loop.candidates)
    assert loop.unsupported is None
    assert loop.chosen_stream == "S6"


def test_m2_a_revision_that_declares_a_different_flash_pressure_is_bound_with_it() -> None:
    """A07 through `validate()`, which is where it was registered and where it was not reached.

    Measured by the Fable review of T01 (M2). `Syn001Flowsheet` takes a single pressure, so the
    binding read one value and pinned both the feed and the flash with it: K03 §7.2's registered
    conflict — flash at 150 kPa against a feed at 100 kPa — bound to 100 kPa everywhere and
    validated `READY_FOR_SIMULATION` with `STR-04 PASS, 2 certified redundant rows, all
    consistent`. The declaration now carries what the revision declares.
    """
    document = revision("SYN-001-nominal")
    for specification in document["specifications"]:
        if specification["id"] == "SPEC-flash-P":
            specification["value"] = 150_000.0

    binding = bind_revision(document)
    assert binding is not None
    assert binding.spec.parameters["U-FLASH.P_spec"] == 150_000.0, "the substitution landed"
    assert binding.spec.parameters["U-FEED.P_spec"] == 100_000.0

    report = validate(document)
    assert report.status == "INVALID"
    conflict = next(check for check in report.checks if check.id == "STR-04")
    assert conflict.result == "FAIL"
    assert "SPECIFICATION_CONFLICT" in conflict.message
    assert "-50000" in conflict.message.replace(" ", "") or "-5e+04" in conflict.message


def test_m2_the_nominal_revisions_bind_to_the_values_they_declare() -> None:
    """The override is inert where the revision agrees with the flowsheet's parameterization."""
    expectations = {
        "SYN-001-nominal": {"U-FLASH.T_spec": 360.0, "U-HEAT.T_spec": 350.0},
        "SYN-001-all-liquid-310K": {"U-FLASH.T_spec": 310.0},
        "SYN-001-all-vapor-420K": {"U-FLASH.T_spec": 420.0},
    }
    for case_id, expected in expectations.items():
        binding = bind_revision(revision(case_id))
        assert binding is not None
        for parameter, value in expected.items():
            assert binding.spec.parameters[parameter] == value, (case_id, parameter)
        assert binding.spec.parameters["U-FEED.P_spec"] == 100_000.0
        assert binding.spec.parameters["U-FLASH.P_spec"] == 100_000.0


def test_m3_an_analysis_that_could_not_run_withdraws_the_ready_verdict() -> None:
    """Blueprint §4.3 and T01 §12.4: not looking is not a pass — and it is not a fault either.

    Measured by the Fable review of T01 (M3): a revision the binding could not read validated
    `READY_FOR_SIMULATION` with all five structural checks `NOT_RUN`. Which status replaces the
    ready verdict depends on why the analysis did not run, decided by Frank on 2026-09-24
    (register R-022). Incomplete is `DRAFT` because blueprint §4.3 says "`DRAFT` revisions may be
    incomplete or under-specified"; unreadable is `DRAFT` because `INVALID` would state a defect
    nobody found; contradictory specifications are `INVALID` because that defect is real.
    """
    unbindable = revision("SYN-001-nominal")
    for instance in unbindable["instances"]:
        instance["model"]["id"] = "unknown.model"
    report = validate(unbindable)
    assert report.status == "DRAFT"
    assert "cannot be analysed" in (report.structural_counts_absent_reason or "")

    incomplete = revision("SYN-001-nominal")
    incomplete["specifications"] = [
        entry for entry in incomplete["specifications"] if entry["id"] != "SPEC-feed-T"
    ]
    report = validate(incomplete)
    assert report.status == "DRAFT"
    assert "feed temperature" in (report.structural_counts_absent_reason or ""), (
        "an incomplete revision says what is missing"
    )

    draft = revision("SYN-001-nominal")
    draft["specifications"] = []
    assert validate(draft).status == "DRAFT", "a draft is not a failure (D16)"

    for case_id in VARIANTS:
        assert validate(revision(case_id)).status == "READY_FOR_SIMULATION", case_id


def test_r022_two_specifications_fixing_one_quantity_differently_are_invalid() -> None:
    """The one binding failure that *is* a defect in the revision (register R-022).

    A second specification pins the vapour outlet's temperature to 370 K while the flash's own
    specification pins both outlets to 360 K. Both reach the flash's one temperature parameter,
    no state satisfies both, and the report names the two specifications as `STR-04`'s finding.
    """
    document = revision("SYN-001-nominal")
    document["specifications"].append(
        {
            "id": "SPEC-vapor-T",
            "target": {
                "object_type": "connection",
                "object_id": "S4",
                "path": "state.T",
                "component": None,
            },
            "kind": "temperature",
            "unit": "K",
            "value": 370.0,
            "tolerance": {"absolute": 1.0e-06},
            "role": "fixed",
            # The frozen revision schema requires it, and SCHEMA-01 applies that schema (T07
            # ruling round 5, S3); without it the document would stop at SCHEMA-01.
            "provenance": document["specifications"][0]["provenance"],
        }
    )
    report = validate(document)
    assert report.status == "INVALID"
    conflict = next(check for check in report.checks if check.id == "STR-04")
    assert conflict.result == "FAIL"
    assert "SPECIFICATION_CONFLICT" in conflict.message
    assert set(conflict.implicated_objects) == {"SPEC-flash-T", "SPEC-vapor-T"}

    agreeing = revision("SYN-001-nominal")
    agreeing["specifications"].append({**document["specifications"][-1], "value": 360.0})
    assert validate(agreeing).status == "READY_FOR_SIMULATION", "agreement is not a conflict"


def test_s1_a_block_output_is_opaque_even_with_an_empty_declared_pattern() -> None:
    """A block the compiler cannot see into is not a literal, whatever its pattern declares.

    Should-fix S1 of the Fable review of T01. `exp(block_output)` collapsed to a plain constant
    when the block declared no inputs, so a row reading it classified as a *specification row*
    pinning a parameter. Latent — no SYN-001 block declares an empty pattern — and wrong the day
    one does.
    """
    from dataclasses import replace

    from openflowsheet.compile.spec import EquationSpec

    binding = bind_revision(revision("SYN-001-nominal"))
    assert binding is not None
    block = binding.spec.blocks[0]
    output = f"{block.block_id}.{block.output_ids[0]}"

    def reads_a_block(
        variables: Mapping[str, Any],
        blocks: Mapping[str, Any],
        parameters: Mapping[str, float],
        algebra: Any,
    ) -> Any:
        return variables["S1.T"] - algebra.exp(blocks[output])

    spec = replace(
        binding.spec,
        equations=(
            *binding.spec.equations,
            EquationSpec(
                equation_id="READS-A-BLOCK",
                build=reads_a_block,
                accumulation="algebraic",
                origin="test",
            ),
        ),
    )
    traced = trace_declaration(spec, row_units=binding.row_units)
    row = traced.rows["READS-A-BLOCK"]
    assert not row.is_affine, "a block output has no affine form"
    assert not row.is_specification_row, "and is certainly not a pinned specification"
    assert "S1.T" in row.columns


def test_s2_comparing_a_traced_term_raises_rather_than_answering() -> None:
    """The escapes a builder could take must all be loud. Should-fix S2 of the Fable review."""
    from openflowsheet.graph.trace import _Term

    term = _Term.variable("x")
    for operation in (
        lambda: bool(term),
        lambda: term == 0,
        lambda: term != 0,
        lambda: term < 1,
        lambda: term > 1,
        lambda: float(term),
    ):
        with pytest.raises(TypeError):
            operation()


def test_s4_the_unit_degree_of_freedom_table_survives_relabelling() -> None:
    """Column ownership is given too, and A15 must be able to see it.

    Should-fix S4 of the Fable review of T01: ownership was derived by splitting a column id on
    its first dot, and A15's bijection preserves the dot, so the relabelling test could not catch
    it. Register R-019 says this layer parses no id; this is the assertion that holds it to that.
    """
    from dataclasses import replace

    from openflowsheet.compile.spec import EquationSpec
    from openflowsheet.graph.process import Connection, ProcessGraph

    binding = bind_revision(revision("SYN-001-nominal"))
    assert binding is not None
    expected = report_for("SYN-001-nominal")

    columns = {name: "X-" + name for name in binding.spec.variable_ids}
    rows = {
        equation.equation_id: "X-" + equation.equation_id for equation in binding.spec.equations
    }

    def relabel(build: Any) -> Any:
        def built(
            variables: Mapping[str, Any],
            blocks: Mapping[str, Any],
            parameters: Mapping[str, float],
            algebra: Any,
        ) -> Any:
            return build(
                {original: variables[renamed] for original, renamed in columns.items()},
                blocks,
                parameters,
                algebra,
            )

        return built

    relabelled = replace(
        binding.spec,
        variable_ids=tuple(columns[name] for name in binding.spec.variable_ids),
        equations=tuple(
            EquationSpec(
                equation_id=rows[equation.equation_id],
                build=relabel(equation.build),
                accumulation=equation.accumulation,
                origin=equation.origin,
            )
            for equation in binding.spec.equations
        ),
        variable_kinds={columns[k]: v for k, v in binding.spec.variable_kinds.items()},
        row_kinds={rows[k]: v for k, v in binding.spec.row_kinds.items()},
        block_inputs={
            block: tuple(columns[name] for name in inputs)
            for block, inputs in binding.spec.block_inputs.items()
        },
        column_scales={columns[k]: v for k, v in binding.spec.column_scales.items()},
        row_scales={rows[k]: v for k, v in binding.spec.row_scales.items()},
    )
    graph = ProcessGraph(
        units=tuple("X-" + unit for unit in binding.graph.units),
        connections=tuple(
            Connection(
                stream_id="X-" + connection.stream_id,
                producer="X-" + connection.producer,
                consumer="X-" + connection.consumer,
                state_columns=tuple(columns[name] for name in connection.state_columns),
            )
            for connection in binding.graph.connections
        ),
        instance_ids={"X-" + unit: name for unit, name in binding.graph.instance_ids.items()},
        column_owners={
            columns[column]: "X-" + unit for column, unit in binding.graph.column_owners.items()
        },
    )
    result = analyse(
        relabelled,
        graph,
        row_units={rows[row]: "X-" + unit for row, unit in binding.row_units.items()},
        specification_ids={
            rows[row]: name for row, name in binding.specification_ids.items() if row in rows
        },
    )

    found = {entry.unit_id: entry for entry in result.unit_degrees_of_freedom}
    for entry in expected.unit_degrees_of_freedom:
        image = found["X-" + entry.unit_id]
        assert len(image.columns) == len(entry.columns), entry.unit_id
        assert image.model_rank == entry.model_rank, entry.unit_id
        assert image.degrees_of_freedom == entry.degrees_of_freedom, entry.unit_id
        assert image.specifications == entry.specifications, entry.unit_id
    assert sum(len(entry.columns) for entry in result.unit_degrees_of_freedom) == 47


def test_a19_an_uncertified_affine_row_is_warned_about_and_never_dropped() -> None:
    """`UNC-1` and `STR-06`: consistency not established is a result, not silence.

    Assertion A19 had no test at all before the Fable review of T01 pointed it out (M5(b)); the
    manifest recorded it `unsupported` because SYN-001 declares no such row, which is true of the
    registered revisions and beside the point — the fixture is synthetic on purpose.
    """
    declaration = _pressure_declaration(
        {
            "p1": _pressure_row("p1", {"P1": 1.0}, -100_000.0),
            "p2": _pressure_row("p2", {"P2": 1.0, "P1": -1.0}, 0.0),
            "p3": _pressure_row("p3", {"P3": 1.0, "P2": -1.0}, 0.0),
            "p4": _pressure_row("p4", {"P1": 1.0, "P2": 1.0, "P3": -1.0}, 0.0),
        },
        ["P1", "P2", "P3"],
    )
    result = certify(declaration)
    assert list(result.uncertified_affine_rows) == ["p4"], "three columns is not a copy"
    assert result.certificates == ()


def test_str_06_warns_about_a_row_whose_consistency_is_not_established() -> None:
    """The `STR-06` check itself, which no registered revision provokes.

    It is informational — a `WARN`, never a `FAIL` — because an uncertified affine redundancy may
    well be consistent; T01 cannot say, says so, and does not let the solver find out.
    """
    from openflowsheet.application.validation import structural_checks
    from openflowsheet.graph.matching import DulmageMendelsohn
    from openflowsheet.graph.report import StructuralReport

    empty = DulmageMendelsohn((), (), (), (), (), (), 3)
    report = StructuralReport(
        model_version="",
        constants_sha256="",
        finding="STRUCTURALLY_CLOSED",
        structural_counts={
            "free_variables": 3,
            "equations": 3,
            "matched": 3,
            "unmatched": 0,
        },
        nnz=5,
        dm_full=empty,
        dm_after_certificates=empty,
        uncertified_affine_rows=("p4",),
    )
    checks = {check.id: check for check in structural_checks(report)}
    assert "STR-06" in checks
    assert checks["STR-06"].result == "WARN"
    assert "not established" in checks["STR-06"].message
    assert checks["STR-06"].implicated_objects == ("p4",)
    assert checks["STR-06"].evidence_class == "structural"
    assert all(check.result != "FAIL" for check in checks.values()), "a warning is not a failure"
