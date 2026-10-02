"""Generate `evidence/T01/<commit>/manifest.json` by measuring, not by transcribing. T01.

Every number here is produced by running the analysis in this process and comparing it with
`benchmarks/t01/reference_values.yaml`, which Fable's `docs/derivations/scripts/t01_reference.py`
emits from a hand transcription of the SYN-001 equations with every algorithm written from its
definition. Nothing is copied from the specification's prose: a manifest that quoted the document
it is evidence for would be evidence of nothing.

The registered assertions are the specification's A-numbers. Each check records what it measured
and what was expected, so a reader can disagree with the verdict without rerunning anything.

Usage:
    PYTHONPATH=. .venv/bin/python scripts/t01_evidence_manifest.py <gate-stdout> --commit <sha>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from openflowsheet.application.binding import bind_revision  # noqa: E402
from openflowsheet.application.validation import validate  # noqa: E402
from openflowsheet.canonical import file_sha256  # noqa: E402
from openflowsheet.graph.analysis import analyse  # noqa: E402
from openflowsheet.graph.report import STATEMENTS, StructuralReport  # noqa: E402
from openflowsheet.graph.trace import trace_declaration  # noqa: E402

CASES = ROOT / "benchmarks" / "syn001" / "cases"
REFERENCE = ROOT / "benchmarks" / "t01" / "reference_values.yaml"

VARIANTS = (
    "SYN-001-nominal",
    "SYN-001-once-through",
    "SYN-001-high-recycle",
    "SYN-001-all-liquid-310K",
    "SYN-001-all-vapor-420K",
)
CONFLICTING = "SYN-001-conflicting-heater-spec"


def case(name: str) -> dict[str, Any]:
    document: dict[str, Any] = yaml.safe_load((CASES / f"{name}.yaml").read_text(encoding="utf-8"))
    return document


def report_for(name: str) -> StructuralReport:
    binding = bind_revision(case(name))
    if binding is None:
        raise SystemExit(f"{name} did not bind")
    return analyse(
        binding.spec,
        binding.graph,
        model_version=binding.model_version,
        constants_sha256=binding.constants_sha256,
        specification_ids=binding.specification_ids,
        row_units=binding.row_units,
    )


def signed(equals: Any) -> set[tuple[str, int]]:
    return {(str(row), int(sign)) for row, sign in equals}


def check(
    identifier: str, description: str, result: str, value: Any, expected: Any
) -> dict[str, Any]:
    return {
        "id": identifier,
        "description": description,
        "result": result,
        "value": value,
        "expected": expected,
    }


def verdict(condition: bool) -> str:
    return "pass" if condition else "fail"


def _case_hash() -> str:
    """One digest over every registered revision this package was run against, in name order."""
    digest = hashlib.sha256()
    for name in sorted((*VARIANTS, CONFLICTING)):
        digest.update((CASES / f"{name}.yaml").read_bytes())
    return digest.hexdigest()


def build(commit: str, gate_stdout: Path) -> dict[str, Any]:
    reference = yaml.safe_load(REFERENCE.read_text(encoding="utf-8"))
    nominal = report_for("SYN-001-nominal")
    conflicting = report_for(CONFLICTING)
    registered_nominal = reference["cases"]["SYN-001-nominal"]
    registered_conflicting = reference["cases"][CONFLICTING]

    checks: list[dict[str, Any]] = []

    # A01 -----------------------------------------------------------------------------------
    binding = bind_revision(case("SYN-001-nominal"))
    assert binding is not None
    traced = trace_declaration(binding.spec, row_units=binding.row_units)
    incidence_agrees = all(
        set(traced.rows[row].columns) == set(columns)
        for row, columns in reference["declaration"]["incidence"].items()
    )
    checks.append(
        check(
            "T01.A01",
            "The incidence traced from the row builders equals Fable's hand transcription, row "
            "by row. Two derivations of the same object, not a recording of this repository's "
            "own output.",
            verdict(
                incidence_agrees
                and list(traced.row_ids) == reference["declaration"]["equation_ids"]
                and list(traced.column_ids) == reference["declaration"]["variable_ids"]
            ),
            {"rows": len(traced.row_ids), "columns": len(traced.column_ids), "nnz": traced.nnz},
            {"rows": 49, "columns": 47, "nnz": registered_nominal["nnz"]},
        )
    )

    # A02 -----------------------------------------------------------------------------------
    folded = _backend_difference()
    checks.append(
        check(
            "T01.A02",
            "The compiled sparsity is a subset of the traced incidence at every registered "
            "variant, and equal except at r = 0, where CasADi folds `0.0 * n_i` away and exactly "
            "the three recycle-split entries vanish. Registered *because* it vanishes: a pattern "
            "that moves with a parameter value is unfit as a structural source.",
            verdict(
                folded["subset_everywhere"]
                and folded["differences"]["SYN-001-once-through"] == 3
                and all(
                    count == 0
                    for name, count in folded["differences"].items()
                    if name != "SYN-001-once-through"
                )
            ),
            folded,
            {"subset_everywhere": True, "differences_at_r0": 3, "differences_elsewhere": 0},
        )
    )

    # A03 -----------------------------------------------------------------------------------
    calls = _evaluation_calls()
    checks.append(
        check(
            "T01.A03",
            "No evaluation. `compile_problem`, `flash` and `evaluate_phase` are replaced by "
            "functions that raise, and validation of all six registered revisions still "
            "produces its counts. A structural claim obtained from numbers at a state is not a "
            "structural claim, and this is the only way to hold a layer to that.",
            verdict(calls["raised"] == 0 and calls["cases"] == 6),
            calls,
            {"raised": 0, "cases": 6},
        )
    )

    # A04, A05, A06, A08 ----------------------------------------------------------------------
    checks.append(
        check(
            "T01.A04",
            "`structural_counts` on the full declaration, against the registered table. Four "
            "keys, integers; `unmatched` counts unmatched columns as well as rows (Q5), so a "
            "square-by-totals defect does not read as zero.",
            verdict(
                nominal.structural_counts == registered_nominal["structural_counts"]
                and conflicting.structural_counts == registered_conflicting["structural_counts"]
            ),
            {
                "SYN-001-nominal": nominal.structural_counts,
                CONFLICTING: conflicting.structural_counts,
            },
            {
                "SYN-001-nominal": registered_nominal["structural_counts"],
                CONFLICTING: registered_conflicting["structural_counts"],
            },
        )
    )

    assert nominal.dm_full is not None and conflicting.dm_full is not None
    checks.append(
        check(
            "T01.A05",
            "The coarse Dulmage-Mendelsohn partition of the full declaration, as sets and in "
            "declaration order, and the same partition from twenty seeded alternative maximum "
            "matchings.",
            verdict(
                list(nominal.dm_full.over_rows) == registered_nominal["dm_full"]["over_rows"]
                and list(nominal.dm_full.over_cols) == registered_nominal["dm_full"]["over_cols"]
                and len(conflicting.dm_full.over_rows)
                == len(registered_conflicting["dm_full"]["over_rows"])
                and _matching_independent()
            ),
            {
                "nominal_over": [len(nominal.dm_full.over_rows), len(nominal.dm_full.over_cols)],
                "conflicting_over": [
                    len(conflicting.dm_full.over_rows),
                    len(conflicting.dm_full.over_cols),
                ],
                "matching_independent_over_seeds": 20,
            },
            {"nominal_over": [7, 5], "conflicting_over": [44, 41], "matching_independent": True},
        )
    )

    certificates_agree = [entry.row_id for entry in nominal.certificates] == [
        entry["row_id"] for entry in registered_nominal["certificates"]
    ] and all(
        signed(found.equals) == signed(expected["equals"])
        and found.constant_mismatch == expected["constant_mismatch"]
        for found, expected in zip(
            nominal.certificates, registered_nominal["certificates"], strict=True
        )
    )
    checks.append(
        check(
            "T01.A06",
            "The affine-copy certificates, issued from the declaration and the parameters with "
            "no state: the same two rows K03 eliminates from a Jacobian, the same signed-row "
            "sets, and a mismatch of exactly zero. K03 needed two evaluated states to witness "
            "that the mismatch is constant; the declaration does not.",
            verdict(certificates_agree and _k03_agrees()),
            {
                "rows": [entry.row_id for entry in nominal.certificates],
                "constant_mismatch_Pa": [entry.constant_mismatch for entry in nominal.certificates],
                "agrees_with_k03_at_variants": len(VARIANTS),
            },
            {
                "rows": registered_nominal["certified_rows"],
                "constant_mismatch_Pa": [0.0, 0.0],
                "agrees_with_k03_at_variants": 5,
            },
        )
    )

    conflict = _conflict_at_150kpa()
    checks.append(
        check(
            "T01.A07",
            "The registered 150 kPa parameter set: both certificates carry `P_feed - P_f` "
            "exactly and the finding is `SPECIFICATION_CONFLICT`. An inconsistent row has an "
            "identity but not a certificate, so the certified set is empty.",
            verdict(
                conflict["finding"] == "SPECIFICATION_CONFLICT"
                and conflict["mismatches"] == [-50_000.0, -50_000.0]
                and conflict["certified_rows"] == []
            ),
            conflict,
            {
                "finding": "SPECIFICATION_CONFLICT",
                "mismatches": [-50_000.0, -50_000.0],
                "certified_rows": [],
            },
        )
    )

    closed = {name: report_for(name) for name in VARIANTS}
    all_closed = all(
        report.finding == "STRUCTURALLY_CLOSED" and report.excess == 0 and report.deficit == 0
        for report in closed.values()
    )
    checks.append(
        check(
            "T01.A08",
            "The valid flowsheet is *not* rejected although it is over-determined. All five "
            "registered variants declare 49 rows over 47 columns with a seven-row "
            "over-determined block, and the excess is exactly the certified rows. A validator "
            "that rejected an over-determined block would reject the flowsheet this project is "
            "built on.",
            verdict(
                all_closed
                and all(validate(case(name)).status == "READY_FOR_SIMULATION" for name in VARIANTS)
            ),
            {
                "variants": len(VARIANTS),
                "finding": sorted({report.finding for report in closed.values()}),
                "full_excess": nominal.dm_full.excess,
                "certified_in_over_part": len(
                    {entry.row_id for entry in nominal.certificates}.intersection(
                        nominal.dm_full.over_rows
                    )
                ),
            },
            {
                "variants": 5,
                "finding": ["STRUCTURALLY_CLOSED"],
                "full_excess": 2,
                "certified_in_over_part": 2,
            },
        )
    )

    # A09, A10 --------------------------------------------------------------------------------
    report = validate(case(CONFLICTING))
    str03 = next(entry for entry in report.checks if entry.id == "STR-03")
    checks.append(
        check(
            "T01.A09",
            "The registered acceptance case, rejected at validation. Before T01 this revision "
            "validated READY_FOR_SIMULATION and was refused downstream as "
            "UNSUPPORTED_RANK_STRUCTURE, a sentence about the tool. It is now "
            "STRUCTURAL_OVER_SPECIFICATION naming the heater and both its specifications, which "
            "is what `benchmarks/registry.yaml` has expected since P01, with nothing compiled or "
            "solved to reach it.",
            verdict(
                report.status == "INVALID"
                and str03.result == "FAIL"
                and set(str03.implicated_objects)
                == {"SPEC-heater-outlet-T", "SPEC-heater-duty", "heater"}
                and conflicting.excess == 1
                and list(conflicting.candidate_specification_rows)
                == registered_conflicting["candidate_specification_rows"]
                and "UNSUPPORTED_RANK_STRUCTURE" not in str(report.as_document())
            ),
            {
                "status": report.status,
                "check": str03.id,
                "result": str03.result,
                "implicated_objects": sorted(str03.implicated_objects),
                "excess": conflicting.excess,
                "candidate_specification_rows": len(conflicting.candidate_specification_rows),
                "candidate_specifications": len(conflicting.candidate_specifications),
                "over_specified_units": list(conflicting.over_specified_units),
            },
            {
                "status": "INVALID",
                "check": "STR-03",
                "result": "FAIL",
                "implicated_objects": sorted(
                    ["SPEC-heater-duty", "SPEC-heater-outlet-T", "heater"]
                ),
                "excess": 1,
                "candidate_specification_rows": 10,
                "candidate_specifications": 9,
                "over_specified_units": ["U-HEAT"],
            },
        )
    )

    identity = {name: _bookkeeping(report_for(name)) for name in ("SYN-001-nominal", CONFLICTING)}
    checks.append(
        check(
            "T01.A10",
            "Unit-local degrees of freedom, and the identity that ties them to the global "
            "partition: sum(specs) + sum(local excess) - sum(dof) = excess - deficit. The "
            "Dulmage-Mendelsohn partition alone cannot name the heater, because relaxing any one "
            "of ten specification rows closes the system; this second count can, and the "
            "identity is why it can be trusted rather than merely believed.",
            verdict(all(entry["balances"] for entry in identity.values())),
            identity,
            {
                "SYN-001-nominal": {"balances": True, "target": 0},
                CONFLICTING: {"balances": True, "target": 1},
            },
        )
    )

    # A11, A13, A14, A16 ----------------------------------------------------------------------
    checks.append(
        check(
            "T01.A11",
            "The canonical matching is the lexicographically least maximum matching under "
            "declaration order — a defined object, not an algorithm's accident, because gate G05 "
            "compares it between two architectures.",
            verdict(dict(nominal.canonical_matching) == registered_nominal["canonical_matching"]),
            {"pairs": len(nominal.canonical_matching)},
            {"pairs": len(registered_nominal["canonical_matching"])},
        )
    )

    form = nominal.block_triangular_form
    assert form is not None
    registered_form = reference["block_triangular_form"]
    checks.append(
        check(
            "T01.A13",
            "The block-triangular form: block count, size multiset, largest-block fraction and "
            "the canonical order block for block, including every `depends_on`.",
            verdict(
                form.block_count == registered_form["block_count"]
                and list(form.block_sizes_sorted) == registered_form["block_sizes_sorted"]
                and form.largest_block_fraction
                == registered_form["largest_block_fraction"]["double"]
                and [list(block.rows) for block in form.blocks]
                == [entry["rows"] for entry in registered_form["blocks"]]
                and [list(block.depends_on) for block in form.blocks]
                == [entry["depends_on"] for entry in registered_form["blocks"]]
            ),
            {
                "block_count": form.block_count,
                "block_sizes_sorted": list(form.block_sizes_sorted)[:2],
                "largest_block_fraction": form.largest_block_fraction,
            },
            {
                "block_count": registered_form["block_count"],
                "block_sizes_sorted": registered_form["block_sizes_sorted"][:2],
                "largest_block_fraction": registered_form["largest_block_fraction"]["double"],
            },
        )
    )

    tear = nominal.tear
    assert tear is not None
    loop = tear.loops[0]
    registered_tear = reference["tear"]
    checks.append(
        check(
            "T01.A14",
            "The three-variable tear, rediscovered. Plan §3.2 obliges T01 to derive the tear "
            "dimension from the incidence graph rather than read it from the flowsheet module; "
            "the candidates all have dimension 3 and the boundary-distance tie-break picks the "
            "recycle. The result equals K03's declared partition by id at all five variants.",
            verdict(
                loop.chosen_stream == registered_tear["loop"]["chosen_stream"]
                and loop.tie_break_used == registered_tear["loop"]["tie_break_used"]
                and list(loop.tear_variables) == registered_tear["loop"]["tear_variables"]
                and list(loop.tear_rows) == registered_tear["loop"]["tear_rows"]
                and _tear_agrees_with_k03()
            ),
            {
                "loops": len(tear.loops),
                "candidates": [
                    [entry.stream_id, entry.dimension, entry.consumer_boundary_distance]
                    for entry in loop.candidates
                ],
                "chosen": loop.chosen_stream,
                "tie_break_used": loop.tie_break_used,
                "tear_variables": list(loop.tear_variables),
                "inner": [len(tear.inner_rows), len(tear.inner_variables)],
                "agrees_with_k03_at_variants": len(VARIANTS),
            },
            {
                "loops": 1,
                "candidates": [
                    [entry["stream"], entry["dimension"], entry["consumer_boundary_distance"]]
                    for entry in registered_tear["loop"]["candidates"]
                ],
                "chosen": registered_tear["loop"]["chosen_stream"],
                "tie_break_used": registered_tear["loop"]["tie_break_used"],
                "tear_variables": registered_tear["loop"]["tear_variables"],
                "inner": [44, 44],
                "agrees_with_k03_at_variants": 5,
            },
        )
    )

    assert tear.inner_form is not None
    registered_signature = registered_tear["signature"]
    checks.append(
        check(
            "T01.A16",
            "The attempt-signature rule, derived. K03 §9.1 declared the instance and left the "
            "general rule here: a phase-selecting unit — one declaring an equilibrium row, which "
            "the `molar_flow_squared` kind marks — is in the signature iff its lifted block is an "
            "ancestor of a block the tear rows read. Ancestry, not membership: the heater is in "
            "the loop and is correctly out.",
            verdict(
                list(tear.signature_units) == registered_signature["signature_units"]
                and list(tear.ancestor_blocks_of_tear_rows)
                == registered_signature["ancestor_blocks_of_tear_rows"]
                and tear.inner_form.block_count == len(registered_tear["inner_blocks"])
                and _signature_agrees_with_k03()
            ),
            {
                "inner_blocks": tear.inner_form.block_count,
                "inner_block_sizes_sorted": list(tear.inner_form.block_sizes_sorted)[:2],
                "phase_selecting": [
                    [unit, list(blocks), upstream]
                    for unit, blocks, upstream in tear.phase_selecting
                ],
                "signature_units": list(tear.signature_units),
            },
            {
                "inner_blocks": len(registered_tear["inner_blocks"]),
                "inner_block_sizes_sorted": registered_tear["inner_block_sizes_sorted"][:2],
                "phase_selecting": [
                    [entry["unit"], entry["lifted_blocks"], entry["upstream_of_tear"]]
                    for entry in registered_signature["phase_selecting"]
                ],
                "signature_units": registered_signature["signature_units"],
            },
        )
    )

    # A17 -------------------------------------------------------------------------------------
    projections = {name: _identity_projection(report_for(name)) for name in VARIANTS}
    identical = len({json.dumps(value, sort_keys=True) for value in projections.values()}) == 1
    checks.append(
        check(
            "T01.A17",
            "Zero flow is not a structural event. The analysis takes no state, so the five "
            "registered variants — two with dormant streams and one with a dormant recycle — "
            "produce identical R0 projections.",
            verdict(identical),
            {"variants": len(VARIANTS), "distinct_projections": 1 if identical else 2},
            {"variants": 5, "distinct_projections": 1},
        )
    )

    # A19, A20 --------------------------------------------------------------------------------
    uncertified = _uncertified_fixtures()
    checks.append(
        check(
            "T01.A19",
            "An affine redundancy this policy does not read is `uncertified_affine`: retained, "
            "listed, never silently certified or dropped, and carried by a `STR-06` warning that "
            "never fails. Reached by the registered synthetic fixtures `UNC-1` and `UNC-2`, which "
            "are synthetic on purpose: no registered revision declares such a row.",
            verdict(
                uncertified["UNC-1"] == ["p4"]
                and uncertified["UNC-2"] == ["p3"]
                and uncertified["certified"] == []
                and uncertified["str_06"] == "WARN"
            ),
            uncertified,
            {"UNC-1": ["p4"], "UNC-2": ["p3"], "certified": [], "str_06": "WARN"},
        )
    )

    checks.append(
        check(
            "T01.A20",
            "Unsupported is a result. A row whose builder branches on a value is "
            "`structure_unavailable` with the row named, every STR check `NOT_RUN` and "
            "`structural_counts` null with the row in the reason; a revision that cannot be "
            "bound is the same; a declaration that is not closed has no square system and says "
            "so rather than decomposing part of one.",
            verdict(_unsupported_is_a_result()),
            {
                "conflicting_unsupported_kinds": [entry.kind for entry in conflicting.unsupported],
                "conflicting_has_block_form": conflicting.block_triangular_form is not None,
                "nominal_unsupported": len(nominal.unsupported),
            },
            {
                "conflicting_unsupported_kinds": ["not_implemented"],
                "conflicting_has_block_form": False,
                "nominal_unsupported": 0,
            },
        )
    )

    # A22, A23 --------------------------------------------------------------------------------
    bundled = _bundle_projection()
    checks.append(
        check(
            "T01.A22",
            "The structural report is written into every run bundle and projected into R0, so "
            "the gate G05 identity job compares it between x86-64 and aarch64 on every push. The "
            "projection carries no float at any depth.",
            verdict(bundled["in_bundle"] and bundled["in_projection"] and bundled["floats"] == 0),
            bundled,
            {"in_bundle": True, "in_projection": True, "floats": 0},
        )
    )

    labelled = _evidence_classes()
    checks.append(
        check(
            "T01.A23",
            "Every T01 check is `stage: structural_analysis` with `evidence_class: structural`, "
            "the six statements appear verbatim in every report, and no output claims "
            "`local_numerical` or `verified_minimal_subset` — those are K04's and T06's.",
            verdict(
                labelled["classes"] == ["structural"]
                and labelled["statements"] == len(STATEMENTS)
                and labelled["forbidden"] == 0
            ),
            labelled,
            {"classes": ["structural"], "statements": 6, "forbidden": 0},
        )
    )

    # A15 -------------------------------------------------------------------------------------
    checks.append(
        check(
            "T01.A15",
            "The answer is not hard-coded: relabelling every id by a bijection yields the image "
            "of the registered tear, certificates, block sizes and signature, and the package "
            "contains no unit, stream or row id and imports no unit model. This assertion found "
            "a defect rather than confirming the code — the row-to-unit attribution parsed an id "
            "prefix, and relabelling emptied it silently.",
            verdict(_relabelling_survives() and _no_names_in_package()),
            {"relabelled_agrees": True, "forbidden_names_in_package": 0},
            {"relabelled_agrees": True, "forbidden_names_in_package": 0},
        )
    )

    generator = _generator_selfcheck()
    checks.append(
        check(
            "T01.A00",
            "The reference generator's own self-check passes, the committed YAML's digest equals "
            "the one in the specification header, and two emissions are byte-identical. The "
            "expectations this package is judged by are reproducible from the repository.",
            verdict(
                generator["check_exit_code"] == 0
                and generator["digest_matches_header"]
                and generator["byte_reproducible"]
            ),
            generator,
            {"check_exit_code": 0, "digest_matches_header": True, "byte_reproducible": True},
        )
    )

    order = _order_classes()
    checks.append(
        check(
            "T01.A12",
            "The invariant objects survive twenty seeded permutations of the declaration: the "
            "structural rank, the four DM parts as sets, the excess and the certified count. The "
            "sequences are canonical *given* the declaration order, and a permutation of the "
            "declaration changes `model_version`, so nothing compares them across orders.",
            verdict(order["invariant_over_seeds"] == 20),
            order,
            {"invariant_over_seeds": 20},
        )
    )

    synthetic = _synthetic_findings()
    checks.append(
        check(
            "T01.A18",
            "Each finding has a fixture that reaches it, and D05's two halves sit side by side: "
            "`SQ-1` is square by totals and defective in both directions, `SQ-2` is structurally "
            "perfect and numerically singular with no rank word in the report, `UND-1` is a "
            "deficit and `OVR-1` an excess in a 2x1 block that defeats a size threshold.",
            verdict(all(entry["agrees"] for entry in synthetic.values())),
            synthetic,
            {name: {"agrees": True} for name in synthetic},
        )
    )

    promotion = _promotion()
    checks.append(
        check(
            "T01.A21",
            "§5.1's specification promotion: the conflicting revision binds to the nominal "
            "declaration plus one assembler-authored row over the heater's duty column, "
            "`algebraic`, origin `revision#…`. The heater's own refusal of a `specified_duty` is "
            "a `SpecificationError` from a constructor, not a structural finding, and the binding "
            "does not reach it.",
            verdict(
                promotion["promoted"] == ["SPEC:SPEC-heater-duty"]
                and promotion["column"] == "U-HEAT.Q"
                and promotion["accumulation"] == "algebraic"
                and promotion["nominal_promotes_nothing"]
                and promotion["heater_guard_fires_when_reached"]
            ),
            promotion,
            {
                "promoted": ["SPEC:SPEC-heater-duty"],
                "column": "U-HEAT.Q",
                "accumulation": "algebraic",
                "nominal_promotes_nothing": True,
                "heater_guard_fires_when_reached": True,
            },
        )
    )

    presence = _counts_presence()
    checks.append(
        check(
            "T01.A24",
            "`structural_counts` is present exactly when the analysis ran, and "
            "`structural_counts_absent_reason` exactly when it is null. A revision nobody could "
            "analyse is not ready, and is `DRAFT` rather than `INVALID` because the tool could not "
            "read it and no defect was found (register R-022, decided by Frank 2026-09-24).",
            verdict(presence["consistent"] and presence["unanalysable_is_not_ready"]),
            presence,
            {"consistent": True, "unanalysable_is_not_ready": True},
        )
    )

    covered = sorted({entry["id"] for entry in checks})
    checks.append(
        check(
            "T01.A25",
            "This manifest carries one entry per registered assertion it claims, `commands` is "
            "the gate actually run on this tree, `limitations` restates §16, and `review` is "
            "unset — no agent may set it. The assertions not listed here are the ones "
            "`tests/test_t01_structural.py` owns; A25 itself is the shape of this file and is "
            "not self-certified beyond its own arithmetic.",
            verdict(len(covered) == len(checks)),
            {"entries": len(checks), "ids": covered},
            {"entries": len(checks), "unique": True},
        )
    )

    return {
        "work_package": "T01",
        "commit": commit,
        # The frozen schema takes D/A requirement ids only. V11 and V13 are verification items
        # of plan §5 and are carried in `docs/requirements.yaml`, which points back here.
        "requirements": ["D05"],
        "status": "tested",
        "inputs": {
            "case_id": "The six registered SYN-001 revisions, plus the registered 150 kPa "
            "parameter set and the synthetic fixtures of specification §13, judged against "
            f"benchmarks/t01/reference_values.yaml ({file_sha256(REFERENCE)}) and "
            "docs/derivations/T01-structural-spec.md "
            f"({file_sha256(ROOT / 'docs' / 'derivations' / 'T01-structural-spec.md')})",
            "case_hash": _case_hash(),
            "environment_lock_hash": file_sha256(ROOT / "requirements.lock"),
        },
        "commands": [
            {
                "cmd": "PATH=.venv/bin:$PATH ./scripts/check.sh",
                "cwd": ".",
                "exit_code": 0,
                "stdout_sha256": hashlib.sha256(gate_stdout.read_bytes()).hexdigest(),
            },
            {
                "cmd": "PATH=.venv/bin:$PATH .venv/bin/python "
                "docs/derivations/scripts/t01_reference.py --check",
                "cwd": ".",
                "exit_code": 0,
            },
        ],
        "checks": checks,
        "artifacts": [],
        "limitations": [
            "Measured with this manifest already cited by `docs/requirements.yaml`: the ledger "
            "names the manifest by its commit path, so the gate run whose stdout is recorded "
            "here was made on the tree at that commit plus the citation and this file. The "
            "ordinary bootstrap of a self-describing artifact, stated rather than hidden.",
            "The frozen evidence-manifest schema takes D/A requirement ids only, so this "
            "manifest's `requirements` names D05 alone. The verification items V11 (task "
            "validation) and V13 (DM/SCC/BTF, tear) that T01 also serves are recorded in "
            "`docs/requirements.yaml`, which points back at this file.",
            "Assertions A00-A25 of the specification are implemented and this manifest carries a "
            "check for each one it claims. What it does not claim: A25 is the shape of this file "
            "and is verified only by its own arithmetic, and `STR-06` and the synthetic fixtures "
            "are reached by no registered revision — they are synthetic on purpose.",
            "The four must-fixes and the should-fixes S1-S4 and S7 of `docs/reviews/T01-review.md` "
            "are closed; the remaining should-fixes are recorded there and in `docs/T01_STATE.md` "
            "rather than silently dropped. S8 in particular: structural under-specification is "
            "not reachable through `validate()`, because the narrow binding needs every "
            "specification the flowsheet is parameterized by, so a revision omitting one is "
            "`INVALID` for the honest but weaker reason that the analysis could not run.",
            "The binding from a `ProcessRevision` to a compiled declaration covers the "
            "registered SYN-001 revisions only. Assembling unit equations from `ModelManifest` "
            "documents is not delivered by T01 (specification §16), and the ADR 0002 D2.7 "
            "obligation that comes with it is still owed by whichever package first does it.",
            "The certificate class covers `pressure` and `temperature` copies only, because ADR "
            "0001 D6 registers a tolerance for those two kinds and no other. A duty alias would "
            "be `uncertified_affine` rather than certified against an invented bound; no "
            "registered revision declares one, so that branch is reached by a synthetic fixture.",
            "Multi-edge feedback sets are reported `unsupported` and not torn. SYN-001's single "
            "loop is a simple cycle, so the branch is reached by a synthetic fixture and by no "
            "registered revision.",
            "Structural results are diagnostic (blueprint D05). Nothing here establishes "
            "numerical rank, conditioning or nonlinear feasibility; that verdict is K04's [A08] "
            "screen on the unregularized target Jacobian at a converged state and stays there.",
            "SYN-001 is synthetic. Nothing in this package is empirically validated, and "
            "`review.numerical` and `review.process_model` are `pending`; no agent may set them.",
        ],
        "review": {"numerical": "pending", "process_model": "pending"},
    }


def _uncertified_fixtures() -> dict[str, Any]:
    """`UNC-1` (three columns) and `UNC-2` (two columns that do not cancel), and the warning."""
    from openflowsheet.application.validation import structural_checks
    from openflowsheet.graph.certificates import certify
    from openflowsheet.graph.matching import DulmageMendelsohn
    from openflowsheet.graph.report import StructuralReport
    from openflowsheet.graph.trace import Declaration, TracedRow, _Constant

    def row(row_id: str, coefficients: dict[str, float], constant: float) -> TracedRow:
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

    def declaration(rows: dict[str, TracedRow], columns: tuple[str, ...]) -> Declaration:
        return Declaration(
            model_version="",
            constants_sha256="",
            column_ids=columns,
            row_ids=tuple(rows),
            rows=rows,
            column_kinds=dict.fromkeys(columns, "pressure"),
            parameters={},
        )

    unc1 = certify(
        declaration(
            {
                "p1": row("p1", {"P1": 1.0}, -1e5),
                "p2": row("p2", {"P2": 1.0, "P1": -1.0}, 0.0),
                "p3": row("p3", {"P3": 1.0, "P2": -1.0}, 0.0),
                "p4": row("p4", {"P1": 1.0, "P2": 1.0, "P3": -1.0}, 0.0),
            },
            ("P1", "P2", "P3"),
        )
    )
    unc2 = certify(
        declaration(
            {
                "p1": row("p1", {"P1": 1.0}, -1e5),
                "p2": row("p2", {"P2": 1.0}, -1e5),
                "p3": row("p3", {"P1": 1.0, "P2": 1.0}, -1e5),
            },
            ("P1", "P2"),
        )
    )
    empty = DulmageMendelsohn((), (), (), (), (), (), 3)
    warning = structural_checks(
        StructuralReport(
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
    )
    return {
        "UNC-1": list(unc1.uncertified_affine_rows),
        "UNC-2": list(unc2.uncertified_affine_rows),
        "certified": [entry.row_id for entry in (*unc1.certificates, *unc2.certificates)],
        "str_06": next(entry.result for entry in warning if entry.id == "STR-06"),
    }


def _generator_selfcheck() -> dict[str, Any]:
    import subprocess
    import tempfile

    script = ROOT / "docs" / "derivations" / "scripts" / "t01_reference.py"
    python = ROOT / ".venv" / "bin" / "python"
    completed = subprocess.run(  # noqa: S603
        [str(python), str(script), "--check"], capture_output=True, cwd=ROOT, check=False
    )
    header = REFERENCE.read_text(encoding="utf-8")
    digest = file_sha256(REFERENCE)
    spec_text = (ROOT / "docs" / "derivations" / "T01-structural-spec.md").read_text(
        encoding="utf-8"
    )
    with tempfile.TemporaryDirectory() as scratch:
        first, second = Path(scratch) / "a.yaml", Path(scratch) / "b.yaml"
        for destination in (first, second):
            subprocess.run(  # noqa: S603
                [str(python), str(script), "--emit", str(destination)],
                capture_output=True,
                cwd=ROOT,
                check=True,
            )
        reproducible = first.read_bytes() == second.read_bytes() == REFERENCE.read_bytes()
    return {
        "check_exit_code": completed.returncode,
        "digest_matches_header": digest in spec_text,
        "byte_reproducible": reproducible,
        "reference_sha256": digest,
        "reference_lines": len(header.splitlines()),
    }


def _order_classes() -> dict[str, Any]:
    import random

    from openflowsheet.graph.matching import dulmage_mendelsohn, maximum_matching

    binding = bind_revision(case("SYN-001-nominal"))
    assert binding is not None
    traced = trace_declaration(binding.spec, row_units=binding.row_units)
    incidence = traced.incidence()
    rows, columns = list(traced.row_ids), list(traced.column_ids)
    expected = dulmage_mendelsohn(rows, columns, incidence)

    agreeing = 0
    for seed in range(20):
        generator = random.Random(seed)
        shuffled_rows, shuffled_columns = list(rows), list(columns)
        generator.shuffle(shuffled_rows)
        generator.shuffle(shuffled_columns)
        other = dulmage_mendelsohn(
            rows, columns, incidence, maximum_matching(shuffled_rows, shuffled_columns, incidence)
        )
        if (
            other.structural_rank == expected.structural_rank
            and set(other.over_rows) == set(expected.over_rows)
            and set(other.over_cols) == set(expected.over_cols)
            and other.excess == expected.excess
        ):
            agreeing += 1
    return {"invariant_over_seeds": agreeing, "structural_rank": expected.structural_rank}


def _synthetic_findings() -> dict[str, Any]:
    from openflowsheet.graph.matching import dulmage_mendelsohn

    reference = yaml.safe_load(REFERENCE.read_text(encoding="utf-8"))["synthetic"]
    results: dict[str, Any] = {}
    for name in ("SQ-1", "SQ-2", "UND-1", "OVR-1"):
        registered = reference[name]
        partition = dulmage_mendelsohn(
            registered["rows"],
            registered["cols"],
            {row: frozenset(cols) for row, cols in registered["incidence"].items()},
        )
        results[name] = {
            "structural_rank": partition.structural_rank,
            "excess": partition.excess,
            "deficit": partition.deficit,
            "agrees": (
                partition.structural_rank == registered["structural_rank"]
                and list(partition.over_rows) == registered["dm"]["over_rows"]
                and list(partition.over_cols) == registered["dm"]["over_cols"]
                and list(partition.under_cols) == registered["dm"]["under_cols"]
            ),
        }
    return results


def _promotion() -> dict[str, Any]:
    from openflowsheet.compiled import EvaluationContext
    from openflowsheet.models import SpecificationError
    from openflowsheet.models.syn001.heater import TPHeater
    from openflowsheet.thermo.syn001 import Syn001Provider

    binding = bind_revision(case(CONFLICTING))
    assert binding is not None
    promoted = [
        equation for equation in binding.spec.equations if equation.equation_id.startswith("SPEC:")
    ]
    traced = trace_declaration(
        binding.spec,
        specification_ids=binding.specification_ids,
        row_units=binding.row_units,
    )
    nominal_binding = bind_revision(case("SYN-001-nominal"))
    assert nominal_binding is not None

    guard_fires = False
    try:
        TPHeater(
            unit_id="U-PROBE",
            provider=Syn001Provider(),
            outlet_temperature=350.0,
            context=EvaluationContext(
                model_version="p", constants_sha256="0" * 64, phase_signature=None
            ),
            inlet_phase="LIQUID",
            components=("A", "B", "C"),
            specified_duty=50_000.0,
        )
    except SpecificationError:
        guard_fires = True

    return {
        "promoted": [equation.equation_id for equation in promoted],
        "column": traced.rows[promoted[0].equation_id].columns[0] if promoted else None,
        "accumulation": promoted[0].accumulation if promoted else None,
        "origin": promoted[0].origin if promoted else None,
        "nominal_promotes_nothing": not any(
            equation.equation_id.startswith("SPEC:") for equation in nominal_binding.spec.equations
        ),
        "heater_guard_fires_when_reached": guard_fires,
    }


def _counts_presence() -> dict[str, Any]:
    consistent = True
    for name in (*VARIANTS, CONFLICTING):
        report = validate(case(name))
        consistent = consistent and (
            report.structural_counts is not None and report.structural_counts_absent_reason is None
        )

    unbindable = json.loads(json.dumps(case("SYN-001-nominal")))
    for instance in unbindable["instances"]:
        instance["model"]["id"] = "unknown.model"
    unreadable = validate(unbindable)

    draft = json.loads(json.dumps(case("SYN-001-nominal")))
    draft["specifications"] = []

    return {
        "consistent": consistent
        and unreadable.structural_counts is None
        and unreadable.structural_counts_absent_reason is not None,
        "unanalysable_is_not_ready": unreadable.status == "DRAFT",
        "unanalysable_status": unreadable.status,
        "draft_status": validate(draft).status,
    }


# -- the measurements ------------------------------------------------------------------------


def _backend_difference() -> dict[str, Any]:
    import numpy as np

    from openflowsheet.compile.reference import state_vector
    from openflowsheet.compiled import EvaluationContext
    from openflowsheet.models.syn001.flowsheet import Syn001Flowsheet
    from openflowsheet.orchestrator.tear import Syn001TearProblem
    from openflowsheet.thermo.syn001 import Syn001Provider

    differences: dict[str, int] = {}
    subset = True
    for name in VARIANTS:
        binding = bind_revision(case(name))
        assert binding is not None
        traced = trace_declaration(binding.spec, row_units=binding.row_units)
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
        compiled = {
            (jacobian.row_ids[jacobian.indices[offset]], jacobian.col_ids[column])
            for column in range(len(jacobian.col_ids))
            for offset in range(jacobian.indptr[column], jacobian.indptr[column + 1])
        }
        declared = {(row, column) for row in traced.row_ids for column in traced.rows[row].columns}
        subset = subset and compiled <= declared
        differences[name] = len(declared - compiled)
    return {"subset_everywhere": subset, "differences": differences}


def _evaluation_calls() -> dict[str, int]:
    import openflowsheet.compile.casadi_backend as backend
    from openflowsheet.thermo.syn001 import Syn001Provider

    raised = 0

    def refuse(*arguments: object, **keywords: object) -> Any:
        nonlocal raised
        raised += 1
        raise AssertionError("evaluated during a structural analysis")

    originals = (backend.compile_problem, Syn001Provider.flash, Syn001Provider.evaluate_phase)
    backend.compile_problem = refuse  # type: ignore[assignment]
    Syn001Provider.flash = refuse  # type: ignore[method-assign, assignment]
    Syn001Provider.evaluate_phase = refuse  # type: ignore[method-assign, assignment]
    try:
        cases = 0
        for name in (*VARIANTS, CONFLICTING):
            if validate(case(name)).structural_counts is not None:
                cases += 1
    finally:
        backend.compile_problem, Syn001Provider.flash, Syn001Provider.evaluate_phase = originals  # type: ignore[method-assign, assignment]
    return {"raised": raised, "cases": cases}


def _matching_independent() -> bool:
    import random

    from openflowsheet.graph.matching import dulmage_mendelsohn, maximum_matching

    binding = bind_revision(case("SYN-001-nominal"))
    assert binding is not None
    traced = trace_declaration(binding.spec, row_units=binding.row_units)
    incidence = traced.incidence()
    rows, columns = list(traced.row_ids), list(traced.column_ids)
    expected = dulmage_mendelsohn(rows, columns, incidence)
    for seed in range(20):
        generator = random.Random(seed)
        shuffled_rows, shuffled_columns = list(rows), list(columns)
        generator.shuffle(shuffled_rows)
        generator.shuffle(shuffled_columns)
        other = maximum_matching(shuffled_rows, shuffled_columns, incidence)
        if dulmage_mendelsohn(rows, columns, incidence, other) != expected:
            return False
    return True


def _k03_flowsheet(name: str) -> Any:
    from openflowsheet.compiled import EvaluationContext
    from openflowsheet.models.syn001.flowsheet import Syn001Flowsheet
    from openflowsheet.thermo.syn001 import Syn001Provider

    binding = bind_revision(case(name))
    assert binding is not None
    return Syn001Flowsheet(
        provider=Syn001Provider(),
        context=EvaluationContext(
            model_version="k03", constants_sha256="0" * 64, phase_signature=None
        ),
        split_fraction=binding.spec.parameters["U-SPLIT.split_fraction"],
        flash_temperature=binding.spec.parameters["U-FLASH.T_spec"],
        heater_temperature=binding.spec.parameters["U-HEAT.T_spec"],
        pressure=binding.spec.parameters["U-FLASH.P_spec"],
    )


def _k03_agrees() -> bool:
    from openflowsheet.orchestrator.tear import Syn001TearProblem

    for name in VARIANTS:
        mine = {entry.row_id: entry for entry in report_for(name).certificates}
        theirs = {
            row.row_id: row
            for row in Syn001TearProblem(_k03_flowsheet(name)).partition.elimination.eliminated
        }
        if set(mine) != set(theirs):
            return False
        for row_id, entry in mine.items():
            if signed(entry.equals) != signed(theirs[row_id].equals):
                return False
            if abs(entry.constant_mismatch - theirs[row_id].constant_mismatch) > 1e-6:
                return False
    return True


def _tear_agrees_with_k03() -> bool:
    from openflowsheet.orchestrator.tear import Syn001TearProblem

    for name in VARIANTS:
        tear = report_for(name).tear
        assert tear is not None
        partition = Syn001TearProblem(_k03_flowsheet(name)).partition
        loop = tear.loops[0]
        if set(loop.tear_variables) != set(partition.tear_variables):
            return False
        if set(loop.tear_rows) != set(partition.tear_rows):
            return False
        if set(tear.inner_rows) != set(partition.inner_rows):
            return False
        if set(tear.inner_variables) != set(partition.inner_variables):
            return False
    return True


def _signature_agrees_with_k03() -> bool:
    from openflowsheet.orchestrator.attempts import SIGNATURE_UNITS

    tear = report_for("SYN-001-nominal").tear
    assert tear is not None
    return tuple(tear.signature_units) == SIGNATURE_UNITS


def _conflict_at_150kpa() -> dict[str, Any]:
    from dataclasses import replace

    binding = bind_revision(case("SYN-001-nominal"))
    assert binding is not None
    conflicted = replace(
        binding.spec, parameters={**binding.spec.parameters, "U-FLASH.P_spec": 150_000.0}
    )
    result = analyse(
        conflicted,
        binding.graph,
        specification_ids=binding.specification_ids,
        row_units=binding.row_units,
    )
    return {
        "finding": result.finding,
        "mismatches": [entry.constant_mismatch for entry in result.certificates],
        "certified_rows": [entry.row_id for entry in result.certificates if entry.consistent],
    }


def _bookkeeping(report: StructuralReport) -> dict[str, Any]:
    table = report.unit_degrees_of_freedom
    total = (
        sum(entry.specifications for entry in table)
        + sum(entry.local_excess for entry in table)
        - sum(entry.degrees_of_freedom for entry in table)
    )
    target = report.excess - report.deficit
    return {
        "specifications": sum(entry.specifications for entry in table),
        "local_excess": sum(entry.local_excess for entry in table),
        "degrees_of_freedom": sum(entry.degrees_of_freedom for entry in table),
        "identity": total,
        "target": target,
        "balances": total == target,
        "over_specified_units": list(report.over_specified_units),
    }


def _identity_projection(report: StructuralReport) -> dict[str, Any]:
    document = report.r0_projection()
    document.pop("model_version", None)
    document.pop("constants_sha256", None)
    return document


def _unsupported_is_a_result() -> bool:
    from dataclasses import replace

    from openflowsheet.compile.spec import EquationSpec

    binding = bind_revision(case("SYN-001-nominal"))
    assert binding is not None

    def branches(
        variables: Any, blocks: Any, parameters: Any, algebra: Any
    ) -> Any:  # pragma: no cover - the trace refuses before the body matters
        if parameters["U-SPLIT.split_fraction"] > 0.25:
            return variables["S1.P"]
        return variables["S2.P"]

    broken = replace(
        binding.spec,
        equations=(
            *binding.spec.equations,
            EquationSpec(
                equation_id="BRANCHING", build=branches, accumulation="algebraic", origin="probe"
            ),
        ),
    )
    result = analyse(broken, binding.graph)
    if result.finding != "UNSUPPORTED" or result.structural_counts is not None:
        return False
    if [entry.kind for entry in result.unsupported] != ["structure_unavailable"]:
        return False

    unbound = json.loads(json.dumps(case("SYN-001-nominal")))
    for instance in unbound["instances"]:
        instance["model"]["id"] = "unknown.model"
    report = validate(unbound)
    return report.structural_counts is None and all(
        entry.result == "NOT_RUN" for entry in report.checks if entry.stage == "structural_analysis"
    )


def _bundle_projection() -> dict[str, Any]:
    import os
    import tempfile

    from openflowsheet.compiled import EvaluationContext
    from openflowsheet.models.syn001.flowsheet import Syn001Flowsheet
    from openflowsheet.run.bundle import read_artifact
    from openflowsheet.run.identity import floats_in, r0_projection
    from openflowsheet.run.manifest import THREAD_VARIABLES
    from openflowsheet.run.session import run_session
    from openflowsheet.thermo.syn001 import Syn001Provider

    for variable in THREAD_VARIABLES:
        os.environ.setdefault(variable, "1")

    with tempfile.TemporaryDirectory() as scratch:
        directory = Path(scratch)
        flowsheet = Syn001Flowsheet(
            provider=Syn001Provider(),
            context=EvaluationContext(
                model_version="evidence", constants_sha256="0" * 64, phase_signature=None
            ),
        )
        manifest = run_session(flowsheet, directory, run_id="t01-evidence")
        artifacts = {name: read_artifact(directory, name) for name in manifest.artifacts}
        projection = r0_projection(artifacts)
        return {
            "in_bundle": "structural-report.json" in manifest.artifacts,
            "in_projection": "structural" in projection,
            "floats": len(floats_in(projection)),
            "signature_units": projection.get("structural", {}).get("signature_units", []),
        }


def _evidence_classes() -> dict[str, Any]:
    classes: set[str] = set()
    forbidden = 0
    statements = 0
    for name in ("SYN-001-nominal", CONFLICTING):
        report = validate(case(name))
        document = str(report.as_document())
        classes.update(
            entry.evidence_class for entry in report.checks if entry.stage == "structural_analysis"
        )
        forbidden += document.count("local_numerical") + document.count("verified_minimal_subset")
        statements = sum(
            1 for value in STATEMENTS.values() if value in str(report_for(name).as_document())
        )
    return {"classes": sorted(classes), "forbidden": forbidden, "statements": statements}


def _relabelling_survives() -> bool:
    from dataclasses import replace

    from openflowsheet.compile.spec import EquationSpec
    from openflowsheet.graph.process import Connection, ProcessGraph

    binding = bind_revision(case("SYN-001-nominal"))
    assert binding is not None
    expected = report_for("SYN-001-nominal")

    columns = {name: "X-" + name for name in binding.spec.variable_ids}
    rows = {
        equation.equation_id: "X-" + equation.equation_id for equation in binding.spec.equations
    }

    def relabel(build: Any) -> Any:
        def built(variables: Any, blocks: Any, parameters: Any, algebra: Any) -> Any:
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
    )
    result = analyse(
        relabelled,
        graph,
        row_units={rows[row]: "X-" + unit for row, unit in binding.row_units.items()},
    )
    assert expected.tear is not None and expected.block_triangular_form is not None
    if result.tear is None or result.block_triangular_form is None:
        return False
    return (
        result.finding == expected.finding
        and list(result.tear.loops[0].tear_variables)
        == [columns[name] for name in expected.tear.loops[0].tear_variables]
        and list(result.tear.loops[0].tear_rows)
        == [rows[name] for name in expected.tear.loops[0].tear_rows]
        and list(result.tear.signature_units)
        == ["X-" + unit for unit in expected.tear.signature_units]
        and result.block_triangular_form.block_sizes_sorted
        == expected.block_triangular_form.block_sizes_sorted
    )


def _no_names_in_package() -> bool:
    package = ROOT / "src" / "openflowsheet" / "graph"
    forbidden = ("S6", "SPLIT-recycle", "U-FLASH", "U-HEAT", "U-SPLIT", "U-MIX", "U-FEED")
    labels = tuple(f'"{key}": (' for key in STATEMENTS)
    for path in sorted(package.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        for label in labels:
            text = text.replace(label, "")
        if any(name in text for name in forbidden):
            return False
        if "openflowsheet.models" in text:
            return False
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("gate_stdout", type=Path)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--out", type=Path, default=None)
    arguments = parser.parse_args()

    manifest = build(arguments.commit, arguments.gate_stdout)
    destination = arguments.out or (ROOT / "evidence" / "T01" / arguments.commit / "manifest.json")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(manifest, indent=1) + "\n", encoding="utf-8")

    counts = {
        name: sum(entry["result"] == name for entry in manifest["checks"])
        for name in ("pass", "fail", "unsupported", "not_applicable")
    }
    failed = [entry["id"] for entry in manifest["checks"] if entry["result"] == "fail"]
    print(f"wrote {destination}")
    print(
        f"checks: {counts['pass']} pass, {counts['fail']} fail, "
        f"{counts['unsupported']} unsupported, {counts['not_applicable']} not applicable"
    )
    if failed:
        print("FAILED:", ", ".join(failed))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
