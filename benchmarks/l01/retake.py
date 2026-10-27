"""L01's development-only coverage re-take on a measurement-only binding (WO-L01-3a).

Normative text: ``docs/derivations/L01-spec.md`` §6.2 as amended by §14.3, assertions L01.A24–A27
(§14.4) and W27v2-A23. It answers whether the library route ``pr-lib-v1`` removes the component
reasons §6.3 projects, and whether W27 registration version 2 judges a real two-route build.

**The measurement binding.** ``measurement_binding()`` returns a module that is the installed
``revision_binding`` with one ``pr-lib-v1`` basis appended to ``SELECTABLE_BASES`` (§4.3's entry);
``MODEL_BASES`` and ``MODEL_BUILDERS`` are the installed ones, so the route has no models. It lives
here, outside ``src`` and outside the wheel; nothing under ``src/openflowsheet`` constructs or
imports it, and the installed build exposes nothing (L01.A27).

**Procedure.**

1. Load the 225 development ids (``split.json``) and filter ``case_facts.json`` to them first.
2. ``snapshot.build_snapshot(binding=measurement_binding())``.
3. ``coverage.check_snapshot`` under ``--registration-version`` (default 2). A refusal prints
   ``REFUSED: <text>``, exits 2, writes nothing and prints no count (version 1 is A24's control).
4. ``classify_case`` for each development case.
5. The "before" rows the same way from the committed ``coverage.json#/snapshot``; they must equal
   the committed development rows (W27v2-R10, SC-2).
6. Write ``evidence/S04/<commit>/retake.json`` (``--out`` overrides the path), after asserting
   that it holds development ids only (L01.A26).
7. Print one line: ``L01 re-take (development, 225): <after classes>; CANDIDATE <b>→<a>
   (measurement-only binding, W27 v2)``.

The committed ``coverage.json`` is read, never written.
"""

from __future__ import annotations

import argparse
import json
import sys
import types
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Final

from benchmarks.m06.w27 import coverage, registration, snapshot

SCHEMA: Final = "l01-retake-v1"
SPLIT_JSON: Final = registration.RECORDS / "split.json"
PROJECTION_JSON: Final = (
    registration.ROOT / "docs" / "derivations" / "scripts" / "l01_projection.json"
)
EVIDENCE: Final = registration.ROOT / "evidence" / "S04"
LIBRARY_PROVIDER: Final = "pr-lib-v1"
BINDING_TEXT: Final = (
    "measurement-only: pr-lib-v1 added to the installed binder's SELECTABLE_BASES inside "
    "benchmarks/l01/retake.py; not selectable in this build (L01 §14)"
)
#: The W27-R62 cause recorded for a unit-reason difference (L01.A25).
R62_CAUSE: Final = (
    "W27-R62: units are judged on the models of the route serving the case's cubic_pr package; "
    "it moved from {before!r} to {after!r}, and pr-lib-v1 carries no models (L01 §4.3)"
)


# -- the measurement binding (§14.3 item 2) -------------------------------------------------------


#: The providers of the installed binder's bases that W27 v1/v2 register provider lines for.
V2_BASIS_PROVIDERS: Final = frozenset({"syn001", "pr-c1-v1"})


def library_basis() -> Any:
    """§4.3's ``SELECTABLE_BASES`` entry: ``pr-lib-v1`` over the nine records in file order, with
    the records' molar masses (as the binder builds ``pr-c1-v1``'s basis)."""
    from types import MappingProxyType  # noqa: PLC0415

    from openflowsheet.models.revision_flowsheet import ComponentBasis  # noqa: PLC0415
    from openflowsheet.thermo import pr_lib  # noqa: PLC0415

    records = pr_lib.load_records()
    return ComponentBasis(
        pr_lib.PROVIDER_ID,
        tuple(r.id for r in records.components),
        MappingProxyType({r.id: r.molar_mass for r in records.components}),
        record_source=pr_lib.RECORDS_PATH,
    )


def measurement_binding() -> types.ModuleType:
    """The installed binder's tables with the library basis appended; outside the wheel."""
    from openflowsheet.application import revision_binding  # noqa: PLC0415
    from openflowsheet.thermo import pr_lib  # noqa: PLC0415

    library = library_basis()
    binding = types.ModuleType("l01_measurement_binding")

    def basis_provider(basis: Any) -> Any:
        if basis == library:
            return pr_lib.PrLibProvider()
        return revision_binding.basis_provider(basis)

    # The measurement is W27 v1/v2's (W27v2-A23): the bases those registrations carry provider
    # lines for, then the library basis. S11's added bases (ADR 0050) are W27 v3's and do not
    # enter it, so its output is unchanged.
    registered = tuple(
        b for b in revision_binding.SELECTABLE_BASES if b.provider_id in V2_BASIS_PROVIDERS
    )
    binding.SELECTABLE_BASES = (*registered, library)  # type: ignore[attr-defined]
    binding.MODEL_BASES = revision_binding.MODEL_BASES  # type: ignore[attr-defined]
    binding.MODEL_BUILDERS = revision_binding.MODEL_BUILDERS  # type: ignore[attr-defined]
    binding.basis_provider = basis_provider  # type: ignore[attr-defined]
    return binding


# -- the re-take ----------------------------------------------------------------------------------


def development_inputs() -> tuple[list[str], list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    """Step 1: the development ids, their facts, their committed rows and the committed snapshot.
    Held-out rows are dropped before anything else reads them."""
    dev = list(json.loads(SPLIT_JSON.read_bytes())["development"]["case_ids"])
    keep = set(dev)
    if len(dev) != 225 or len(keep) != 225:
        raise RuntimeError(f"development ids are not 225 distinct ({len(dev)}, {len(keep)})")
    cases = [
        c
        for c in json.loads(registration.CASE_FACTS_JSON.read_bytes())["cases"]
        if c["case_id"] in keep
    ]
    committed_doc = json.loads(registration.COVERAGE_JSON.read_bytes())
    committed = {r["case_id"]: r for r in committed_doc["rows"] if r["case_id"] in keep}
    if {c["case_id"] for c in cases} != keep or set(committed) != keep:
        raise RuntimeError("a development id lacks facts or a committed coverage row")
    return dev, cases, committed, committed_doc["snapshot"]


def classify_all(
    cases: Sequence[Mapping[str, Any]], snap: Mapping[str, Any], version: int
) -> dict[str, dict[str, Any]]:
    """Steps 3–4: refuse (``coverage.RefusalError``) or classify every case."""
    coverage.check_snapshot(snap, {"cases": list(cases)}, registration_version=version)
    return {
        c["case_id"]: coverage.classify_case(c, snap, registration_version=version) for c in cases
    }


def tally(rows: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    """§6.3's tally form (as ``l01_projection.py``'s)."""
    order = registration.classes()
    classes = Counter(r["class"] for r in rows.values())
    comps: Counter[str] = Counter()
    for r in rows.values():
        for x in r["reasons"]:
            if x["kind"] == "COMPONENT_UNAVAILABLE":
                comps[str(x["subject"])] += 1
    kinds = Counter(x["kind"] for r in rows.values() for x in r["reasons"])
    return {
        "classes": {k: classes.get(k, 0) for k in order},
        "reason_kinds": dict(sorted(kinds.items())),
        "component_reasons_by_subject": dict(sorted(comps.items())),
    }


def _reason_text(x: Mapping[str, Any]) -> str:
    return f"{x['kind']}:{x['subject']}:{x['detail']}"


def transitions(
    dev: Sequence[str], before: Mapping[str, Any], after: Mapping[str, Any]
) -> list[dict[str, Any]]:
    """Every case whose class or reasons changed, in the projection's form, plus the reasons of
    other kinds that disappeared (the projection has none: its SC-8)."""
    out = []
    for cid in sorted(dev):
        b, a = before[cid], after[cid]
        gone = [x for x in b["reasons"] if x not in a["reasons"]]
        new = [x for x in a["reasons"] if x not in b["reasons"]]
        if gone or new or a["class"] != b["class"]:
            out.append(
                {
                    "case_id": cid,
                    "class_before": b["class"],
                    "class_after": a["class"],
                    "component_reasons_removed": sorted(
                        str(x["subject"]) for x in gone if x["kind"] == "COMPONENT_UNAVAILABLE"
                    ),
                    "other_reasons_removed": sorted(
                        _reason_text(x) for x in gone if x["kind"] != "COMPONENT_UNAVAILABLE"
                    ),
                    "reasons_added": sorted(_reason_text(x) for x in new),
                }
            )
    return out


def unit_reason_differences(
    dev: Sequence[str], before: Mapping[str, Any], after: Mapping[str, Any]
) -> list[dict[str, Any]]:
    """L01.A25: per case, the unit reasons that differ from before (the projection projects none),
    with their W27-R62 cause."""
    out = []
    for cid in sorted(dev):
        b, a = before[cid], after[cid]
        b_units = [x for x in b["reasons"] if x["kind"] == "UNIT_UNAVAILABLE"]
        a_units = [x for x in a["reasons"] if x["kind"] == "UNIT_UNAVAILABLE"]
        removed = sorted(_reason_text(x) for x in b_units if x not in a_units)
        added = sorted(_reason_text(x) for x in a_units if x not in b_units)
        if removed or added:
            out.append(
                {
                    "case_id": cid,
                    "units_judged_on_before": b["units_judged_on"],
                    "units_judged_on_after": a["units_judged_on"],
                    "unit_reasons_removed": removed,
                    "unit_reasons_added": added,
                    "cause": R62_CAUSE.format(
                        before=b["units_judged_on"], after=a["units_judged_on"]
                    ),
                }
            )
    return out


def retake(version: int) -> dict[str, Any]:
    """Steps 1–5 and the record of step 6. Raises ``coverage.RefusalError`` (or
    ``snapshot.SnapshotUnsupportedError``) on a refused snapshot, before any case is classified."""
    from openflowsheet.thermo import pr_lib  # noqa: PLC0415

    dev, cases, committed, committed_snapshot = development_inputs()
    snap = snapshot.build_snapshot(binding=measurement_binding())
    after = classify_all(cases, snap, version)
    before = classify_all(cases, committed_snapshot, version)
    drift = sorted(k for k in committed if before[k] != committed[k])
    if drift:
        raise RuntimeError(f"step 5: before rows differ from the committed rows: {drift[:5]}")
    described = pr_lib.PrLibProvider().describe()
    inputs = {
        p: registration.sha256_file(registration.RECORDS / p)
        for p in (
            "split.json",
            "case_facts.json",
            "coverage.json",
            "registration.json",
            "registration_v2.json",
        )
    } | {pr_lib.RECORDS_PATH: registration.sha256_file(registration.ROOT / pr_lib.RECORDS_PATH)}
    return {
        "schema": SCHEMA,
        "scope": "development half only (C2 split, 225 ids); no held-out row is read",
        "registration_version": version,
        "binding": BINDING_TEXT,
        "selectable_in_build": False,
        "pr_lib_data_sha256": described.data_sha256,
        "pr_lib_implementation_sha256": described.implementation_sha256,
        "snapshot_sha256": registration.sha256_bytes(registration.dump(snap)),
        "snapshot": snap,
        "inputs": inputs,
        "before": tally(before),
        "after": tally(after),
        "transitions": transitions(dev, before, after),
        "unit_reason_differences": unit_reason_differences(dev, before, after),
    }


def development_only(document: Mapping[str, Any], dev: Sequence[str]) -> None:
    """L01.A26: every case id the record names is a development id."""
    keep = set(dev)
    named = {t["case_id"] for t in document["transitions"]} | {
        u["case_id"] for u in document["unit_reason_differences"]
    }
    stray = sorted(named - keep)
    if stray:
        raise RuntimeError(f"L01.A26: non-development ids in the record: {stray[:5]}")


def default_out() -> Path:
    commit = snapshot.git_commit()
    if commit is None:
        raise RuntimeError("no git commit to name the evidence directory")
    return EVIDENCE / commit / "retake.json"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="L01 development-only coverage re-take (§14.3)")
    parser.add_argument(
        "--registration-version",
        type=int,
        choices=(1, 2),
        default=2,
        help="W27v2-R01; 1 is A24's control",
    )
    parser.add_argument(
        "--out", type=Path, default=None, help="default: evidence/S04/<commit>/retake.json"
    )
    args = parser.parse_args(argv)
    try:
        document = retake(args.registration_version)
    except (coverage.RefusalError, snapshot.SnapshotUnsupportedError) as refusal:
        print(f"REFUSED: {refusal}", file=sys.stderr)
        return 2
    development_only(document, development_inputs()[0])
    out: Path = default_out() if args.out is None else args.out
    if out.resolve() == registration.COVERAGE_JSON.resolve():
        print("REFUSED: the re-take never writes the committed coverage.json", file=sys.stderr)
        return 2
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(registration.dump(document))
    a, b = document["after"]["classes"], document["before"]["classes"]
    shown = ", ".join(f"{k} {v}" for k, v in a.items())
    print(
        f"L01 re-take (development, 225): {shown}; CANDIDATE {b['CANDIDATE']}→{a['CANDIDATE']} "
        f"(measurement-only binding, W27 v{args.registration_version})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
