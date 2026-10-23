"""C2: the OpenIDAES-450 development / held-out split (SPLIT-R01…R14).

Normative text: `docs/derivations/C2-OpenIDAES-450-split-registration.md`. Inputs are three
committed files, pinned by SHA-256 (SPLIT-R01); no archive, no network, no RNG library (SHA-256
ranks, SPLIT-R05).

Run (repository root):
    PYTHONPATH=src python docs/derivations/scripts/c2_openidaes450_split.py --emit
    PYTHONPATH=src python docs/derivations/scripts/c2_openidaes450_split.py --check

`--check` regenerates in memory and compares byte for byte with the committed record. A refusal
(SPLIT-R14) exits 2 and names the rule; no message ever prints a held-out case id (SPLIT-R10).

Amendment 1 (2026-10-22, R-555): `coverage.json` is re-taken at every version bump. When its
working copy no longer has the pinned SHA-256, the draw reads the pinned content from git history
(by its blob id), and the working copy's read fields (`case_id`, `family`, `class` of every row)
must still equal the pinned ones; drift is a SPLIT-R12 amendment trigger. Without the history the
generator refuses (SPLIT-R01/A1); it never falls back to the working copy.

Amendment 2 (2026-10-23, R-581/R-582): `case_facts-v2.json` (every case's topology units, written
by `c2_openidaes450_facts_v2.py`) is read from the working copy under a strict SHA-256 pin with no
history fallback (`F1_FACTS`; not one of the draw's three inputs). It is checked against
`case_facts.json` (item 14) and gives F-1's unit-level states (item 15).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

ROOT: Final = Path(__file__).resolve().parents[3]
REGISTRATION: Final = "docs/derivations/C2-OpenIDAES-450-split-registration.md"
GENERATOR: Final = "docs/derivations/scripts/c2_openidaes450_split.py"
OUT: Final = "benchmarks/m06/openidaes450/split.json"
SCHEMA: Final = "openidaes450-split-v1"

# SPLIT-R05: fixed before the draw; embeds the brief commit made before this package's session.
SEED_TEXT: Final = "OpenIDAES-450-split-v1/f39746770dd7f3f1ad96f75dbac8d29b4deef4f7"
HASH_IDIOM: Final = "sha256(seed_text \\x00 purpose \\x00 id), lowercase hex, ascending"
COMMITMENT_RULE: Final = "sha256 of the UTF-8 sorted held-out ids, each followed by \\n"
STRATA_BASIS: Final = "W27-R02"
EXPOSURE_COMMIT: Final = "f397467"

# SPLIT-R01: path -> SHA-256.
INPUTS: Final[Mapping[str, tuple[str, str]]] = {
    "coverage": (
        "benchmarks/m06/openidaes450/coverage.json",
        "b69626c7e908218e70f8726534a00c964674b2cbda7f582c8650ed939e48e3ba",
    ),
    "case_facts": (
        "benchmarks/m06/openidaes450/case_facts.json",
        "0ca8cffa146865971dd2a2d445b699cf484965cc052f7f37d8f6554c669e38f7",
    ),
    "sample": (
        "benchmarks/m06/openidaes450/runs/w27-m07-83f825d/sample.json",
        "33f146ece4fec078b8a464059f27d7256439941d6340de214352efb37b1a92bf",
    ),
}

# Amendment 1 (R-555): the git blob id (SHA-1 object id) of each re-taken input's pinned content.
# A locator only: the bytes it yields must still have the SPLIT-R01 SHA-256. `case_facts.json` and
# `sample.json` are not re-taken and keep the strict SPLIT-R01 refusal.
PINNED_BLOBS: Final[Mapping[str, str]] = {
    "coverage": "dea968a285c0243b582db19f1ef9fec1c21c2867",
}
# Amendment 1: the fields of `coverage.json` rows the draw reads (SPLIT-R01).
READ_FIELDS: Final = ("case_id", "family", "class")

# SPLIT-R04 (c): cases named in committed non-data files at f397467; first file naming each.
NAMED_EXPOSED: Final[Mapping[str, str]] = {
    "blind_synthesized_hda_flash": "docs/derivations/M06-W27-registration.md",
    "blind_synthesized_methanol_recycle": "docs/derivations/T08-release-spec.md",
    "dispatches_nuclear_double_loop": "docs/reviews/W27-verdict-83f825d.md",
    "idaes_feed_flash": "benchmarks/m06/w27/stubs.py",
    "idaes_ngcc_soec": "docs/derivations/M06-W27-registration.md",
    "idaes_temperature_swing_adsorption": "docs/reviews/W27-verdict-83f825d.md",
    "official_btx_flash_canary": "docs/derivations/M06-W27-registration.md",
    "official_idaes_eg_pfr_flowsheet": "docs/derivations/M06-W27-registration.md",
    "official_idaes_eg_stoichiometric_flowsheet": "docs/derivations/M06-W27-registration.md",
    "official_idaes_smr_equilibrium_flowsheet": "docs/derivations/M06-W27-registration.md",
    "official_idaes_smr_gibbs_flowsheet": "docs/derivations/M06-W27-registration.md",
    "pareto_produced_water_network": "docs/derivations/M06-W27-registration.md",
    "variant_hda_once_through_single_flash": "docs/derivations/M06-W27-registration.md",
    "variant_idaes_ammonia_synthesis_intercool_condense": (
        "docs/derivations/M06-W27-registration.md"
    ),
    "variant_idaes_hx_ntu_e60_a80": "benchmarks/m06/w27/stubs.py",
    "variant_idaes_iapws_pump_dp200k_eff75": "docs/derivations/M06-W27-registration.md",
    "variant_methanol_water_nrtl_partial_condensation": "docs/derivations/M06-W27-registration.md",
}

# SPLIT-R10 (a): the pre-split files that hold every case. (b): a `heldout` directory segment.
_RC17 = ("at-c.json.gz", "at-cw.json.gz", "coverage-at-C.json.gz")
ALL_CASE_FILES: Final[tuple[str, ...]] = (
    *(
        f"benchmarks/m06/openidaes450/{name}"
        for name in (
            "access_report.json",
            "case_facts.json",
            "case_facts-v2.json",
            "coverage.json",
            "dry_illustration.json",
            "registration.json",
        )
    ),
    "benchmarks/m06/openidaes450/runs/w27-m07-83f825d/coverage.json",
    *(
        f"evidence/M07/{c}/rc/step17/{name}"
        for c in (
            "c899c85ab43fb114cd85c69baf12e692b75a8eab",
            "ce993651ce37c1343e771b276160bd6623e43500",
        )
        for name in _RC17
    ),
)
HELDOUT_SEGMENT: Final = "heldout"

# SPLIT-R11: contaminated held-out cases by sha256(id) hex; date, cause, files naming them.
CONTAMINATED: Final[tuple[Mapping[str, Any], ...]] = (
    {
        "sha256": "c87ac13adc32bcd5f48aa846d3f511e12d5e4f8efef1bad090a0be6be7a45721",
        "date": "2026-10-21",
        "cause": (
            "named before the draw as the whole-token matching example in SPLIT-R04's text "
            "(commit 0211372); found by SPLIT-A09 at the first draw; no case content was read"
        ),
        "where": ["docs/derivations/C2-OpenIDAES-450-split-registration.md"],
    },
)

# SPLIT-R13: R02-F1 and the two kind-level states it must keep (W27-A08 restated; run 26).
BOUNDARY_KINDS: Final = frozenset({"Feed", "Product"})
F1_STATES: Final[Mapping[str, tuple[str, ...]]] = {
    "blind_synthesized_hda_flash": (),
    "official_idaes_skeleton_pervaporation": ("SkeletonUnitModel",),
}
F1_LACKING_FIELD: Final = "topology_units"
# Amendment 2 (§15.4): the facts R02-F1 needs, pinned strictly (no history fallback), and the
# unit-level states they give for the two cases of F1_STATES.
F1_FACTS: Final = (
    "benchmarks/m06/openidaes450/case_facts-v2.json",
    "4f5c5a65fe1b310e04b7e311464e4d87ba90ed4bfa7a90c240cde397cd0114ef",
)
F1_SCHEMA: Final = "openidaes450-case-facts-v2"
F1_WRITER: Final = "docs/derivations/scripts/c2_openidaes450_facts_v2.py"
F1_UNIT_STATES: Final[Mapping[str, Mapping[str, tuple[str, ...]]]] = {
    "blind_synthesized_hda_flash": {},
    "official_idaes_skeleton_pervaporation": {"topology:SkeletonUnitModel": ("pervap",)},
}
F1_KEY: Final = "case_facts_v2"
FORBIDDEN_KEYS: Final = frozenset({"reasons", "units", "components", "packages"})
INCOMPLETE: Final = "ARTIFACT_INCOMPLETE"


class SplitRefusedError(Exception):
    """SPLIT-R14: the generator will not emit; `rule` names the violated rule."""

    def __init__(self, rule: str, message: str, label: str | None = None) -> None:
        super().__init__(f"{rule} {label}: {message}" if label else f"{rule}: {message}")
        self.rule = rule
        self.label = label


def rank(purpose: str, ident: str) -> str:
    """SPLIT-R05: sha256(seed_text ‖ 0x00 ‖ purpose ‖ 0x00 ‖ id), lowercase hex."""
    data = b"\x00".join(s.encode("utf-8") for s in (SEED_TEXT, purpose, ident))
    return hashlib.sha256(data).hexdigest()


def id_tag(ident: str) -> str:
    """SPLIT-R10: how a message names a case without printing it."""
    return hashlib.sha256(ident.encode("utf-8")).hexdigest()[:12]


def commitment(ids: Iterable[str]) -> str:
    """SPLIT-R07: sha256 of the sorted ids, each followed by a newline."""
    return hashlib.sha256("".join(i + "\n" for i in sorted(ids)).encode("utf-8")).hexdigest()


def git_blob(root: Path, oid: str) -> bytes | None:
    """Amendment 1: a blob's bytes from the repository's object store, or None when they cannot be
    read here (no git, not a repository, a shallow clone, a missing object)."""
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "cat-file", "blob", oid],
            capture_output=True,
            check=False,
        )
    except OSError:
        return None
    return proc.stdout if proc.returncode == 0 else None


def read_field_rows(raw: bytes) -> list[tuple[str, ...]]:
    """Amendment 1: the read fields of every `coverage.json` row, as a sorted multiset."""
    return sorted(tuple(str(r[f]) for f in READ_FIELDS) for r in json.loads(raw)["rows"])


def _drift(pinned: list[tuple[str, ...]], working: list[tuple[str, ...]]) -> str:
    """Counts only: a drift message never names a case (SPLIT-R10)."""
    p = {row[0]: row[1:] for row in pinned}
    w = {row[0]: row[1:] for row in working}
    removed = len(p.keys() - w.keys())
    added = len(w.keys() - p.keys())
    changed = sum(1 for c in p.keys() & w.keys() if p[c] != w[c])
    duplicated = (len(pinned) - len(p)) + (len(working) - len(w))
    return f"removed {removed}, added {added}, changed {changed}, duplicate rows {duplicated}"


def pinned_inputs(
    working: Mapping[str, bytes],
    *,
    root: Path = ROOT,
    pins: Mapping[str, tuple[str, str]] = INPUTS,
    blobs: Mapping[str, str] = PINNED_BLOBS,
    fetch: Callable[[Path, str], bytes | None] = git_blob,
) -> dict[str, bytes]:
    """Amendment 1 (SPLIT-R12): the pinned content of each input. A re-taken input whose working
    copy moved on is read from git history; its working copy must keep the pinned read fields."""
    out = dict(working)
    for name, oid in blobs.items():
        path, sha = pins[name]
        if hashlib.sha256(working[name]).hexdigest() == sha:
            continue
        pinned = fetch(root, oid)
        if pinned is None:
            raise SplitRefusedError(
                "SPLIT-R01/A1",
                f"{path} has moved on from its pin and its pinned content (git blob {oid}) cannot"
                " be read here; Amendment 1 needs the repository's history (a full clone)",
            )
        got = hashlib.sha256(pinned).hexdigest()
        if got != sha:
            raise SplitRefusedError(
                "SPLIT-R01/R12", f"git blob {oid} has SHA-256 {got}, pinned {sha}; see SPLIT-R12"
            )
        before, now = read_field_rows(pinned), read_field_rows(working[name])
        if before != now:
            raise SplitRefusedError(
                "SPLIT-R12/A1",
                f"{path}: the read fields {'/'.join(READ_FIELDS)} differ from the pinned content"
                f" ({_drift(before, now)}); amend the registration under SPLIT-R12",
            )
        out[name] = pinned
    return out


def read_inputs(root: Path = ROOT) -> dict[str, bytes]:
    """The pinned content of the three inputs (SPLIT-R01; Amendment 1 for a re-taken input), and
    the working copy of `case_facts-v2.json` under `F1_KEY` when it exists (Amendment 2; its pin is
    item 13 of `build`)."""
    working = {name: (root / path).read_bytes() for name, (path, _) in INPUTS.items()}
    out = pinned_inputs(working, root=root)
    facts_v2 = root / F1_FACTS[0]
    if facts_v2.is_file():
        out[F1_KEY] = facts_v2.read_bytes()
    return out


@dataclass(frozen=True)
class Draw:
    held_out: frozenset[str]
    strata: list[dict[str, Any]]


def draw(
    rows: Mapping[str, tuple[str, str]],
    exposed: frozenset[str],
    *,
    purpose: str = "case",
    alternate_odd: bool = True,
    force_exposed: bool = True,
) -> Draw:
    """SPLIT-R03/R06 over the frame `rows` (case_id -> (family, class)). The keyword arguments
    exist only for the mutants of SPLIT-R14 item 7; the registered draw uses the defaults."""
    strata: dict[str, list[str]] = {}
    for case_id, (family, klass) in rows.items():
        strata.setdefault(f"{family}|{klass}", []).append(case_id)
    odd = sorted((k for k, v in strata.items() if len(v) % 2), key=lambda k: rank("stratum", k))
    odd_rank = {k: i for i, k in enumerate(odd)}
    held: set[str] = set()
    table: list[dict[str, Any]] = []
    for key in sorted(strata):
        ids = strata[key]
        n = len(ids)
        e = sum(1 for c in ids if c in exposed)
        r = odd_rank.get(key)
        target = n // 2 + (1 if alternate_odd and r is not None and r % 2 == 0 else 0)
        pool = [c for c in ids if c not in exposed] if force_exposed else list(ids)
        h = min(target, len(pool))
        held |= set(sorted(pool, key=lambda c: rank(purpose, c))[:h])
        family, klass = key.split("|")
        table.append(
            {
                "family": family,
                "class": klass,
                "n": n,
                "exposed": e,
                "odd_rank": r,
                "target": target,
                "held_out": h,
                "development": n - h,
                "shortfall": target - h,
            }
        )
    return Draw(frozenset(held), table)


def _covered(case: Mapping[str, Any]) -> set[str]:
    """§6: the kinds some W27-R02 unit group covers, by `topology_kind` or by its key's subject."""
    covered: set[str] = set()
    for unit in case["units"]:
        if "topology_kind" in unit:
            covered.add(unit["topology_kind"])
        namespace, _, subject = str(unit["key"]).partition(":")
        if namespace == "idaes":
            covered.add(subject)
    return covered


def f1_added_kinds(case: Mapping[str, Any]) -> tuple[str, ...]:
    """SPLIT-R13 at kind level: the non-boundary topology kinds no W27-R02 unit group covers."""
    if case["unit_source"] != "units.json":
        return ()
    return tuple(sorted(set(case["topology_kinds"]) - BOUNDARY_KINDS - _covered(case)))


def _a2(label: str, count: int, what: str = "case(s)") -> SplitRefusedError:
    return SplitRefusedError("SPLIT-R13/A2", f"{count} {what}", label=label)


def f1_identities(facts: Mapping[str, Any], facts_v2: Mapping[str, Any]) -> None:
    """Item 14 (§15.4): `case_facts-v2.json`'s identities with `case_facts.json`, in order; a
    failure names its label and a count, never a case. Callable below the pin (SPLIT-A21)."""
    source = facts_v2.get("source")
    binding = [
        facts_v2.get("schema") == F1_SCHEMA,
        isinstance(source, Mapping)
        and set(source)
        == {"access_report_sha256", "archive_sha256", "case_facts_v1_sha256", "generator"},
        isinstance(source, Mapping)
        and source.get("case_facts_v1_sha256") == INPUTS["case_facts"][1],
        isinstance(source, Mapping)
        and source.get("archive_sha256") == facts["source"]["archive_sha256"],
        isinstance(source, Mapping) and source.get("generator") == F1_WRITER,
    ]
    if not all(binding):
        raise _a2("binding", binding.count(False), "field(s)")
    cases = facts_v2.get("cases")
    cases = cases if isinstance(cases, list) else []
    want = [c["case_id"] for c in facts["cases"]]
    got = [c.get("case_id") if isinstance(c, Mapping) else None for c in cases]
    if got != want:
        raise _a2(
            "case_ids",
            sum(1 for i in range(max(len(got), len(want))) if got[i : i + 1] != want[i : i + 1]),
        )
    bad = sum(1 for c in cases if set(c) != {"case_id", "topology_units"})
    if bad:
        raise _a2("case_keys", bad)

    def unit_ok(u: Any) -> bool:
        return (
            isinstance(u, Mapping)
            and set(u) == {"id", "kind"}
            and isinstance(u["id"], str)
            and isinstance(u["kind"], str)
        )

    bad = sum(
        1
        for c in cases
        if not (isinstance(c["topology_units"], list) and all(map(unit_ok, c["topology_units"])))
    )
    if bad:
        raise _a2("unit_form", bad)
    bad = sum(
        1
        for c in cases
        if c["topology_units"] != sorted(c["topology_units"], key=lambda u: (u["id"], u["kind"]))
    )
    if bad:
        raise _a2("unit_order", bad)
    bad = sum(
        1 for c in cases if len({u["id"] for u in c["topology_units"]}) != len(c["topology_units"])
    )
    if bad:
        raise _a2("unit_ids", bad)
    kinds = {c["case_id"]: set(c["topology_kinds"]) for c in facts["cases"]}
    bad = sum(1 for c in cases if {u["kind"] for u in c["topology_units"]} != kinds[c["case_id"]])
    if bad:
        raise _a2("kind_sets", bad)


def f1_unit_level_states(
    facts: Mapping[str, Any], facts_v2: Mapping[str, Any]
) -> dict[str, dict[str, list[str]]]:
    """Item 15 (§15.4): for each case of F1_STATES, one group `topology:<k>` per added kind *k*,
    holding the ids of the case's units of kind *k* in file order; refused (SPLIT-R13) unless the
    added kinds are the kind-level state and the groups are F1_UNIT_STATES."""
    v1 = {c["case_id"]: c for c in facts["cases"]}
    v2 = {c["case_id"]: c for c in facts_v2["cases"]}
    states: dict[str, dict[str, list[str]]] = {}
    for c, want in F1_UNIT_STATES.items():
        units = v2[c]["topology_units"]
        added: set[str] = set()
        if v1[c]["unit_source"] == "units.json":
            added = {u["kind"] for u in units} - BOUNDARY_KINDS - _covered(v1[c])
        if tuple(sorted(added)) != f1_added_kinds(v1[c]):
            raise SplitRefusedError(
                "SPLIT-R13", f"F-1 state {c!r}: added kinds differ from the kind-level state"
            )
        groups = {
            f"topology:{k}": [u["id"] for u in units if u["kind"] == k] for k in sorted(added)
        }
        if groups != {k: list(v) for k, v in want.items()}:
            raise SplitRefusedError(
                "SPLIT-R13", f"F-1 state {c!r}: unit groups differ from the registered ones"
            )
        states[c] = groups
    return states


def _walk(node: Any) -> Iterable[tuple[str | None, Any]]:
    if isinstance(node, Mapping):
        for k, v in node.items():
            yield k, v
            yield from _walk(v)
    elif isinstance(node, list):
        for v in node:
            yield None, v
            yield from _walk(v)


def build(
    raw: Mapping[str, bytes],
    *,
    pins: Mapping[str, tuple[str, str]] = INPUTS,
    named_exposed: Mapping[str, str] = NAMED_EXPOSED,
) -> tuple[dict[str, Any], frozenset[str]]:
    """The record and the held-out set, or `SplitRefusedError` (SPLIT-R14 items 1–15)."""
    for name, (path, sha) in pins.items():
        got = hashlib.sha256(raw[name]).hexdigest()
        if got != sha:
            raise SplitRefusedError(
                "SPLIT-R01/R12", f"{path} has SHA-256 {got}, pinned {sha}; see SPLIT-R12"
            )
    coverage = json.loads(raw["coverage"])
    facts = json.loads(raw["case_facts"])
    sample = json.loads(raw["sample"])

    cov_ids = [r["case_id"] for r in coverage["rows"]]
    fact_ids = [c["case_id"] for c in facts["cases"]]
    if len(set(cov_ids)) != len(cov_ids) or len(set(fact_ids)) != len(fact_ids):
        raise SplitRefusedError(
            "SPLIT-R14.2", "duplicate case ids in coverage.json or case_facts.json"
        )
    if set(cov_ids) != set(fact_ids):
        raise SplitRefusedError(
            "SPLIT-R14.2", "coverage.json and case_facts.json hold different case ids"
        )
    all_ids = frozenset(cov_ids)
    rows = {
        r["case_id"]: (str(r["family"]), str(r["class"]))
        for r in coverage["rows"]
        if r["class"] != INCOMPLETE
    }
    excluded = sorted(all_ids - set(rows))
    if sorted(sample["excluded"]) != excluded:
        raise SplitRefusedError("SPLIT-R14.4", "sample.json#/excluded differs from the frame's")

    sources: dict[str, str] = {}
    for c in sample["cases"]:
        sources[c] = "w27_sample"
    for c in sample["canaries"]:
        sources.setdefault(c, "w27_canary")
    for c, path in named_exposed.items():
        sources.setdefault(c, f"named:{path}@{EXPOSURE_COMMIT}")
    for c in sources:
        if c not in all_ids:
            raise SplitRefusedError("SPLIT-R14.3", f"exposed id {c!r} is not a case id")
        if c not in rows:
            raise SplitRefusedError("SPLIT-R14.3", f"exposed id {c!r} lies outside the frame")
    exposed = frozenset(sources)

    result = draw(rows, exposed)
    held = result.held_out
    development = frozenset(rows) - held
    _check_partition(all_ids, rows, excluded, development, held, exposed, result)

    for label, mutant in (
        ("purpose 'order'", draw(rows, exposed, purpose="order")),
        ("odd strata all rounded down", draw(rows, exposed, alternate_odd=False)),
        ("exposure not forced", draw(rows, exposed, force_exposed=False)),
    ):
        if commitment(mutant.held_out) == commitment(held):
            raise SplitRefusedError(
                "SPLIT-R14.7", f"mutant ({label}) gives the registered commitment"
            )

    held_hashes = {hashlib.sha256(c.encode("utf-8")).hexdigest() for c in held}
    for entry in CONTAMINATED:
        if entry["sha256"] not in held_hashes:
            raise SplitRefusedError(
                "SPLIT-R11", f"contamination {entry['sha256'][:12]} is no held-out case"
            )

    by_id = {c["case_id"]: c for c in facts["cases"]}
    if any(F1_LACKING_FIELD in c for c in facts["cases"]):
        raise SplitRefusedError(
            "SPLIT-R13", f"case_facts has {F1_LACKING_FIELD}; amend the registration for R02-F1"
        )
    states = {c: f1_added_kinds(by_id[c]) for c in F1_STATES}
    for c, want in F1_STATES.items():
        if c not in development:
            raise SplitRefusedError("SPLIT-R13", f"F-1 state {c!r} is not a development case")
        if states[c] != want:
            raise SplitRefusedError(
                "SPLIT-R13", f"F-1 state {c!r}: added {states[c]}, registered {want}"
            )

    # Amendment 2: items 13 (strict pin, no fallback), 14 and 15.
    path_v2, sha_v2 = F1_FACTS
    raw_v2 = raw.get(F1_KEY)
    if raw_v2 is None:
        raise SplitRefusedError("SPLIT-R13/A2", f"{path_v2} is absent; R02-F1 needs its facts")
    got_v2 = hashlib.sha256(raw_v2).hexdigest()
    if got_v2 != sha_v2:
        raise SplitRefusedError("SPLIT-R13/A2", f"{path_v2} has SHA-256 {got_v2}, pinned {sha_v2}")
    facts_v2 = json.loads(raw_v2)
    f1_identities(facts, facts_v2)
    unit_states = f1_unit_level_states(facts, facts_v2)

    totals = {
        "cases": len(all_ids),
        "frame": len(rows),
        "excluded": len(excluded),
        "exposed": len(exposed),
        "development": len(development),
        "held_out": len(held),
        "contaminated": len(CONTAMINATED),
        "held_out_headline": len(held) - len(CONTAMINATED),
        "target_held_out": sum(s["target"] for s in result.strata),
        "shortfall": sum(s["shortfall"] for s in result.strata),
        "strata": len(result.strata),
        "odd_strata": sum(1 for s in result.strata if s["odd_rank"] is not None),
    }
    record: dict[str, Any] = {
        "schema": SCHEMA,
        "registration": REGISTRATION,
        "generator": GENERATOR,
        "seed_text": SEED_TEXT,
        "hash": HASH_IDIOM,
        "inputs": {name: {"path": p, "sha256": s} for name, (p, s) in pins.items()},
        "archive_sha256": facts["source"]["archive_sha256"],
        "coverage_snapshot": {
            "git_commit": coverage["snapshot"]["git_commit"],
            "snapshot_sha256": coverage["snapshot_sha256"],
        },
        "strata_basis": STRATA_BASIS,
        "frame": {"size": len(rows), "excluded": excluded},
        "exposed": {
            "count": len(exposed),
            "cases": [{"case_id": c, "source": sources[c]} for c in sorted(exposed)],
        },
        "development": {"count": len(development), "case_ids": sorted(development)},
        "held_out": {
            "count": len(held),
            "commitment": commitment(held),
            "commitment_rule": COMMITMENT_RULE,
        },
        "strata": result.strata,
        "totals": totals,
        "contaminated": [dict(c) for c in sorted(CONTAMINATED, key=lambda c: c["sha256"])],
        "f1": {
            "status": "facts_committed",
            "rule": "SPLIT-R13 (R02-F1)",
            "facts": {
                "path": path_v2,
                "schema": F1_SCHEMA,
                "sha256": sha_v2,
                "writer": F1_WRITER,
            },
            "boundary_kinds": sorted(BOUNDARY_KINDS),
            "kind_level_states": {c: list(v) for c, v in states.items()},
            "unit_level_states": unit_states,
        },
    }
    for key, value in _walk(record):
        if key in FORBIDDEN_KEYS:
            raise SplitRefusedError("SPLIT-R14.9", f"the record would carry a {key!r} key")
        if isinstance(value, str) and value in held:
            raise SplitRefusedError(
                "SPLIT-R14.9", f"the record would name held-out case {id_tag(value)}"
            )
    return record, held


def _check_partition(
    all_ids: frozenset[str],
    rows: Mapping[str, tuple[str, str]],
    excluded: list[str],
    development: frozenset[str],
    held: frozenset[str],
    exposed: frozenset[str],
    result: Draw,
) -> None:
    """SPLIT-R14 items 5 and 6."""
    if development & held or (development | held) & set(excluded):
        raise SplitRefusedError("SPLIT-R14.5", "the halves and the excluded cases are not disjoint")
    if development | held | set(excluded) != all_ids:
        raise SplitRefusedError(
            "SPLIT-R14.5", "the halves and the excluded cases do not make the 450"
        )
    for s in result.strata:
        key = f"{s['family']}|{s['class']}"
        ids = [c for c, fc in rows.items() if f"{fc[0]}|{fc[1]}" == key]
        if s["n"] != len(ids) or s["held_out"] != sum(1 for c in ids if c in held):
            raise SplitRefusedError(
                "SPLIT-R14.5", f"stratum {key}: recorded counts differ from the cases"
            )
        if s["held_out"] + s["development"] != s["n"]:
            raise SplitRefusedError("SPLIT-R14.5", f"stratum {key}: held_out + development != n")
        if s["held_out"] != min(s["target"], s["n"] - s["exposed"]):
            raise SplitRefusedError(
                "SPLIT-R14.5", f"stratum {key}: held_out != min(target, n - exposed)"
            )
        if s["shortfall"] != s["target"] - s["held_out"]:
            raise SplitRefusedError("SPLIT-R14.5", f"stratum {key}: shortfall != target - held_out")
    if abs(2 * sum(s["target"] for s in result.strata) - len(rows)) > 1:
        raise SplitRefusedError(
            "SPLIT-R14.5", "the frame-wide target is not within one of half the frame"
        )
    if exposed & held:
        raise SplitRefusedError(
            "SPLIT-R14.6", f"{len(exposed & held)} exposed case(s) in the held-out set"
        )


def render(record: Mapping[str, Any]) -> bytes:
    return (json.dumps(record, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def held_out_ids(root: Path = ROOT) -> list[str]:
    """For mechanical consumers only (SPLIT-R10): the held-out ids, verified against the committed
    commitment. Never print the result."""
    record, held = build(read_inputs(root))
    committed = json.loads((root / OUT).read_bytes())
    if committed["held_out"]["commitment"] != record["held_out"]["commitment"]:
        raise SplitRefusedError(
            "SPLIT-R07", "the regenerated held-out set differs from the commitment"
        )
    return sorted(held)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--emit", action="store_true", help=f"write {OUT}")
    mode.add_argument("--check", action="store_true", help=f"compare with the committed {OUT}")
    args = parser.parse_args(argv)
    try:
        record, _ = build(read_inputs())
    except SplitRefusedError as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2
    data = render(record)
    out = ROOT / OUT
    if args.emit:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(data)
        t = record["totals"]
        print(f"wrote {OUT}: development {t['development']}, held-out {t['held_out']}")
        return 0
    if not out.exists() or out.read_bytes() != data:
        print(f"{OUT} differs from its regeneration (SPLIT-A01)", file=sys.stderr)
        return 1
    print(f"{OUT}: byte-identical")
    return 0


if __name__ == "__main__":
    sys.exit(main())
