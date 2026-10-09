"""`T08-numerical-policy-v2`'s data (ADR 0025 §8), emitted and checked (T08.A45, ADR 0025 A1).

`benchmarks/t08/numerical_policy_v2.yaml` is what `run.compare` compares a record under when the
record names `T08-numerical-policy-v2`. It is v1's policy (`benchmarks/k04/reference_values.yaml`,
`numerical_policy`, read and never edited) with the changes ADR 0025 D2–D6 make, and this script
is its only author. It refuses to emit unless (ADR 0025 A1):

- (a) each `kind_floors.floor` is `a + r·s` computed here **and** equals both
  `verify.checks.KIND_TOLERANCE` and `orchestrator.region.KIND_TOLERANCE`, as floats, exactly;
- (b) each carried v1 entry equals v1's exactly, and v1 has no `floors` key that v2 lacks other
  than the two `u_diag` rows (D4);
- (c) the D6.2 token pattern yields exactly §8's ten registered token lists;
- (d) `float_digests.names ∪ exact_sha256` is the set of `sha256`-bearing property names in
  `schemas/*.json`, and the two are disjoint (D2.3: a closed partition, so a fourth float digest
  cannot be missed the way three were).

The schemas M02 adds (`experiment`, `model-variant`, `model-replacement`) are classified beside v2,
not in it, so v2's content does not move: `benchmarks/m02/numerical_policy_external.yaml` names
them and lists the exact `sha256` names they introduce, and `--check` holds that table to the same
closed-partition rule (M02 design note §3.6). M05's `trust-region-study` follows the same pattern
(`benchmarks/m05/numerical_policy_external.yaml`, M05 build decision S11): `ADDENDA` lists the
tables, and each is audited in turn, a name an earlier table classified keeping its class.

Usage:
    PYTHONPATH=src .venv/bin/python scripts/t08_numerical_policy.py --check
    PYTHONPATH=src .venv/bin/python scripts/t08_numerical_policy.py --emit
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections.abc import Iterator, Mapping, Sequence
from pathlib import Path
from typing import Any, Final

import yaml

ROOT: Final = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

V1: Final = ROOT / "benchmarks" / "k04" / "reference_values.yaml"
V2: Final = ROOT / "benchmarks" / "t08" / "numerical_policy_v2.yaml"
#: M02 design note §3.6: the addendum that classifies the M02 schemas' floats and digests.
EXTERNAL: Final = ROOT / "benchmarks" / "m02" / "numerical_policy_external.yaml"
#: Every addendum, in the order `--check` audits them (M02's, then M05's: build decision S11).
ADDENDA: Final = (EXTERNAL, ROOT / "benchmarks" / "m05" / "numerical_policy_external.yaml")
SCHEMAS: Final = ROOT / "schemas"

V1_ID: Final = "K04-numerical-policy-v1"
V2_ID: Final = "T08-numerical-policy-v2"

#: §8: the v1 entries v2 carries verbatim.
CARRIED: Final = (
    "relative",
    "near_threshold_margin",
    "comparability_windows",
    "exact_fields",
    "unreproducible_counts",
)
#: D4: the pivot-path diagnostics, "recorded, not reproducible". v2 carries no floor row for any
#: of them, so it drops v1's two (`u_diag_min_abs`, `u_diag_max_abs`).
POST_PIVOTING: Final = ("u_diag_min_abs", "u_diag_max_abs", "u_diagonal_ratio")
#: D2.1 and ADR 0007 D1 row 3: the float digests, by name, and the suffix rule beside them.
FLOAT_DIGESTS: Final = (
    "state_sha256",
    "full_state_sha256",
    "target_state_sha256",
    "opening_state_sha256",
    "level_constants_sha256",
)
FLOAT_DIGEST_SUFFIX: Final = "state_sha256"
#: §8: every other `sha256`-bearing property name of `schemas/*.json`, registered by name. A name
#: in neither list is unclassified and the generator refuses (D2.3): it is never defaulted.
EXACT_SHA256: Final = (
    "artifact_r0_sha256",
    "check_policy_sha256",
    "constants_sha256",
    "content_sha256",
    "lock_sha256",
    "manifest_sha256",
    "policy_sha256",
    "request_sha256",
    "revision_content_sha256",
    "sha256",
    "stdout_sha256",
    "structural_sha256",
    "token_sha256",
    "variable_ids_sha256",
)

#: D5's table: ADR 0001 D6's acceptance rule `a + r·s` per declared kind. `s` is `None` where
#: `r` is 0 (the table's "—").
KINDS: Final[Mapping[str, tuple[float, float, float | None]]] = {
    "molar_flow": (1e-9, 1e-8, 3.0),
    "molar_flow_squared": (3e-9, 1e-8, 9.0),
    "heat_rate": (1e-5, 1e-8, 1e5),
    "temperature": (1e-6, 0.0, None),
    "pressure": (1e-2, 0.0, None),
}

#: D6.2: a float token as Python's `repr`/`str` renders a finite float.
TOKEN: Final = r"(?<![\w.+-])-?(?:\d+\.\d+(?:e[-+]\d+)?|\d+e[-+]\d+)(?![\w.])"

#: §8's ten registered examples and their token lists.
EXAMPLES: Final[tuple[tuple[str, tuple[str, ...]], ...]] = (
    (
        "H_S3_vapor: H_S3_vapor: temperature 52.11447523132472 K outside [280.0, 440.0] K",
        ("52.11447523132472", "280.0", "440.0"),
    ),
    ("FSR1-e3f2d5372330-syn001-67e472816d4d-44f894ff62f9-T06-revision-v2-execution", ()),
    ("no trial accepted in 21 steps from alpha = 0.0009765625", ("0.0009765625",)),
    (
        "the attempt controller closed the attempt: a persistent phase wall, not an overshoot "
        "(§4.6)",
        ("4.6",),
    ),
    (
        "hash 8e70 and 1e-05 and -4.530826668708299e-15 and 1e+16",
        ("1e-05", "-4.530826668708299e-15", "1e+16"),
    ),
    ("S3.T at U-FL2 SciPy 1.15.3", ()),
    ("x-1.5 and (-2.5)", ("-2.5",)),
    ("terminal_refinement(accepted): chord 0.5 at S3.T", ("0.5",)),
    ("value inf and nan", ()),
    (
        "P_in - dP = 99000.0 Pa outside [1000.0, 10000000.0] Pa",
        ("99000.0", "1000.0", "10000000.0"),
    ),
)


def v1_policy() -> dict[str, Any]:
    document = yaml.safe_load(V1.read_text(encoding="utf-8"))["numerical_policy"]
    assert document["id"] == V1_ID, document["id"]
    return dict(document)


def external_policy(path: Path = EXTERNAL) -> dict[str, Any]:
    """An addendum's table (`numerical_policy_external`), M02's by default."""
    document = yaml.safe_load(path.read_text(encoding="utf-8"))["numerical_policy_external"]
    return dict(document)


def schema_sha256_names(
    *, external: bool = False, addendum: Mapping[str, Any] | None = None
) -> set[str]:
    """Every property name containing `sha256` declared anywhere in `schemas/*.json` — outside
    every addendum's schemas, or (`external=True`) inside one addendum's (`addendum`, M02's by
    default)."""
    names: set[str] = set()
    if external:
        selected = set((external_policy() if addendum is None else addendum)["schemas"])
    else:
        selected = {name for path in ADDENDA for name in external_policy(path)["schemas"]}

    def walk(node: Any) -> Iterator[str]:
        if isinstance(node, dict):
            for key, value in node.items():
                if key in ("properties", "patternProperties") and isinstance(value, dict):
                    yield from (name for name in value if "sha256" in name)
                yield from walk(value)
        elif isinstance(node, list):
            for entry in node:
                yield from walk(entry)

    for path in sorted(SCHEMAS.glob("*.json")):
        if (path.name in selected) != external:
            continue
        names.update(walk(json.loads(path.read_text(encoding="utf-8"))))
    return names


def kind_floor(a: float, r: float, s: float | None) -> float:
    return a if s is None else a + r * s


def build(problems: list[str]) -> dict[str, Any]:
    """The policy document; every refusal condition of A1 appended to `problems`."""
    from openflowsheet.orchestrator.region import KIND_TOLERANCE as REGION_KIND_TOLERANCE
    from openflowsheet.verify.checks import KIND_TOLERANCE as CHECKS_KIND_TOLERANCE

    v1 = v1_policy()

    # (a) The floors are the acceptance rule, computed here and equal to both copies in the code.
    kind_floors: dict[str, Any] = {}
    for kind, (a, r, s) in KINDS.items():
        floor = kind_floor(a, r, s)
        for label, table in (
            ("verify.checks", CHECKS_KIND_TOLERANCE),
            ("orchestrator.region", REGION_KIND_TOLERANCE),
        ):
            if table.get(kind) != floor:
                problems.append(f"(a) {kind}: a + r*s = {floor!r}, {label} has {table.get(kind)!r}")
        kind_floors[kind] = {
            "floor": repr(floor),
            "a": repr(a),
            "r": repr(r),
            "s": None if s is None else repr(s),
            "why": "ADR 0001 D6 a + r*s; KIND_TOLERANCE",
        }
    if set(CHECKS_KIND_TOLERANCE) != set(KINDS) or set(REGION_KIND_TOLERANCE) != set(KINDS):
        problems.append("(a) the code registers a kind D5's table does not, or the reverse")

    # (b) v1's floors, verbatim, less the rows of the post-pivoting quantities (D4).
    floors = {name: entry for name, entry in v1["floors"].items() if name not in POST_PIVOTING}

    # (c) The token pattern against its registered examples.
    pattern = re.compile(TOKEN)
    for text, expected in EXAMPLES:
        found = tuple(pattern.findall(text))
        if found != expected:
            problems.append(f"(c) {text!r}: tokens {list(found)}, registered {list(expected)}")

    # (d) A closed partition of the schemas' sha256-bearing names, checked by `audit`.
    declared = schema_sha256_names()
    exact = sorted(EXACT_SHA256)

    policy: dict[str, Any] = {
        "id": V2_ID,
        "adr": "ADR 0025",
        **{name: v1[name] for name in CARRIED},
        "floors": floors,
        "self_floored": {"value": "tolerance", "sigma_min": "tolerance"},
        "limitation_floors": {"near_threshold": {"value": "threshold"}},
        "post_pivoting_floats": list(POST_PIVOTING),
        "float_digests": {"names": list(FLOAT_DIGESTS), "suffix": FLOAT_DIGEST_SUFFIX},
        "exact_sha256": exact,
        "derived_identifiers": {
            "certificate_id": {
                "digest_form": "cert- + target_state_sha256[:12]",
                "digest_form_rule": "emitted equals its own digest form",
                "other_forms": "exact",
            }
        },
        "kind_floors": kind_floors,
        "kind_floor_paths": {
            "solution_state_variables": "declared_kind",
            "phase_branch_flows": "molar_flow",
        },
        "text_with_floats": {
            "keys": ["message", "cause"],
            "token": TOKEN,
            "token_floor": "0",
            "examples": [{"text": text, "tokens": list(tokens)} for text, tokens in EXAMPLES],
        },
    }
    problems.extend(audit(policy, v1, declared))
    return {"numerical_policy": policy}


def audit(policy: Mapping[str, Any], v1: Mapping[str, Any], declared: set[str]) -> list[str]:
    """A1's conditions read back from a policy document (the built one, or the committed one)."""
    problems: list[str] = []
    for name in CARRIED:
        if policy.get(name) != v1[name]:
            problems.append(f"(b) {name} is not v1's")
    post_pivoting = set(policy["post_pivoting_floats"])
    for name, entry in v1["floors"].items():
        if name in post_pivoting:
            if name in policy["floors"]:
                problems.append(f"(b) {name} must not carry a floor (D4)")
        elif policy["floors"].get(name) != entry:
            problems.append(f"(b) floors.{name} is not v1's")
    if set(policy["floors"]) - set(v1["floors"]):
        problems.append("(b) v2 has a floor row v1 lacks")
    if set(v1["floors"]) - set(policy["floors"]) != {"u_diag_min_abs", "u_diag_max_abs"}:
        problems.append("(b) v2 lacks a v1 floor row other than the two u_diag rows")
    for kind, entry in policy["kind_floors"].items():
        a, r = float(entry["a"]), float(entry["r"])
        s = None if entry["s"] is None else float(entry["s"])
        if float(entry["floor"]) != kind_floor(a, r, s):
            problems.append(f"(a) kind_floors.{kind}.floor is not a + r*s")
    digests = set(policy["float_digests"]["names"])
    exact = set(policy["exact_sha256"])
    if digests & exact:
        problems.append(f"(d) both a float digest and exact: {sorted(digests & exact)}")
    if digests | exact != declared:
        problems.append(
            f"(d) unclassified sha256 names: {sorted(declared - digests - exact)}; "
            f"classified but undeclared: {sorted((digests | exact) - declared)}"
        )
    pattern = re.compile(policy["text_with_floats"]["token"])
    for example in policy["text_with_floats"]["examples"]:
        if pattern.findall(example["text"]) != example["tokens"]:
            problems.append(f"(c) {example['text']!r} does not yield its registered tokens")
    return problems


def external_audit(
    policy: Mapping[str, Any],
    external: Mapping[str, Any],
    earlier: Sequence[Mapping[str, Any]] = (),
) -> list[str]:
    """M02 design note §3.6: every `sha256` name of the addendum's schemas is classified — by v2's
    lists or an `earlier` addendum's (a name reused keeps its class) or by the addendum's own
    `exact_sha256` — and the addendum's names are new (in no earlier list) and declared, and its
    schemas are no earlier addendum's. Problems are tagged with the addendum's package, `(m02)`."""
    tag = "(" + external["id"].split("-", 1)[0].lower() + ")"
    declared = schema_sha256_names(external=True, addendum=external)
    digests = set(policy["float_digests"]["names"])
    exact = set(policy["exact_sha256"])
    before = {name for table in earlier for name in table["exact_sha256"]}
    added = set(external["exact_sha256"])
    problems: list[str] = []
    claimed = set(external["schemas"]) & {name for table in earlier for name in table["schemas"]}
    if claimed:
        problems.append(f"{tag} schemas of an earlier addendum: {sorted(claimed)}")
    if added & (digests | exact):
        problems.append(f"{tag} already classified by v2: {sorted(added & (digests | exact))}")
    if added & before:
        problems.append(
            f"{tag} already classified by an earlier addendum: {sorted(added & before)}"
        )
    unclassified = declared - digests - exact - before - added
    if unclassified:
        problems.append(f"{tag} unclassified sha256 names: {sorted(unclassified)}")
    if added - declared:
        problems.append(f"{tag} classified but undeclared: {sorted(added - declared)}")
    return problems


#: T08 review 3, N5: `exact_fields` is carried from v1 (§8) but no §5 row enforces it and neither
#: comparator reads it. The file says so where the key is, as a comment, so the data stay v1's.
EXACT_FIELDS_KEY: Final = "  exact_fields:\n"
EXACT_FIELDS_NOTE: Final = (
    "  # Inert: carried from v1 verbatim (ADR 0025 §8) and enforced by neither comparator; no §5\n"
    "  # row reads it. alpha, scales, bounds and tolerance are compared at 1e-9 relative, not\n"
    "  # exactly (T08 review 3, N5).\n"
)


def dump(data: Mapping[str, Any]) -> str:
    header = (
        "# Generated by scripts/t08_numerical_policy.py -- do not edit.\n"
        "# T08-numerical-policy-v2 (ADR 0025 §8). Check with --check; regenerate with --emit.\n"
    )
    body = yaml.safe_dump(dict(data), sort_keys=False, allow_unicode=True, width=100)
    if body.count(EXACT_FIELDS_KEY) != 1:
        raise ValueError(f"expected one {EXACT_FIELDS_KEY.strip()!r} key to annotate (N5)")
    return header + body.replace(EXACT_FIELDS_KEY, EXACT_FIELDS_NOTE + EXACT_FIELDS_KEY)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--check", action="store_true", help="ADR 0025 A1; exit 1 on a problem")
    action.add_argument("--emit", action="store_true", help=f"write {V2.relative_to(ROOT)}")
    arguments = parser.parse_args(argv)

    problems: list[str] = []
    data = dump(build(problems)).encode("utf-8")
    if arguments.check and V2.is_file():
        committed = yaml.safe_load(V2.read_text(encoding="utf-8"))["numerical_policy"]
        problems.extend(audit(committed, v1_policy(), schema_sha256_names()))
        earlier: list[dict[str, Any]] = []
        for path in ADDENDA:
            table = external_policy(path)
            problems.extend(external_audit(committed, table, earlier))
            earlier.append(table)
    for problem in problems:
        print(problem)
    if problems:
        print(f"{len(problems)} problem(s); nothing emitted")
        return 1
    digest = hashlib.sha256(data).hexdigest()
    if arguments.emit:
        V2.parent.mkdir(parents=True, exist_ok=True)
        V2.write_bytes(data)
        print(f"wrote {V2.relative_to(ROOT)} ({len(data)} bytes, sha256 {digest})")
        return 0
    same = V2.is_file() and V2.read_bytes() == data
    print(
        f"{V2.relative_to(ROOT)} {'equals' if same else 'DIFFERS FROM'} the regenerated bytes "
        f"(sha256 {digest})"
    )
    return 0 if same else 1


if __name__ == "__main__":
    raise SystemExit(main())
