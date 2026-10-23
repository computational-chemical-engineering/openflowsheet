"""C2 Amendment 2: `case_facts-v2.json`, every case's topology units (SPLIT-R13, R02-F1).

Normative text: `docs/derivations/C2-OpenIDAES-450-split-registration.md` §15.2. The file holds,
for every case, its topology units as `[{"id", "kind"}]` sorted by `(id, kind)`, read from the
archive's `cases/<id>/topology.json` exactly as W27's `facts` stage reads that file; it is bound to
`case_facts.json` by hash. W27's generator is loaded by path and used unedited (its SHA-256 is
pinned by `benchmarks/m06/w27/preflight.py`).

Run (repository root; the archive is untrusted data, read as JSON only, nothing imported from it):
    python -I docs/derivations/scripts/c2_openidaes450_facts_v2.py --emit   # or --check
    python -I docs/derivations/scripts/c2_openidaes450_facts_v2.py --check --archive DIR

Exit codes: 0 written or byte-identical; 1 differs or missing (`--check`); 2 refused (W1-W5) or not
checked (no archive). A refusal gives counts only and names no case.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Final

ROOT: Final = Path(__file__).resolve().parents[3]
W27_GENERATOR: Final = ROOT / "docs/derivations/scripts/m06_w27_registration.py"
WRITER: Final = "docs/derivations/scripts/c2_openidaes450_facts_v2.py"
OUT: Final = ROOT / "benchmarks/m06/openidaes450/case_facts-v2.json"
SCHEMA: Final = "openidaes450-case-facts-v2"
# SPLIT-R01's pin of case_facts.json (W2).
FACTS_V1_SHA256: Final = "0ca8cffa146865971dd2a2d445b699cf484965cc052f7f37d8f6554c669e38f7"


def _load_w27() -> Any:
    """W27's generator by file path (under `python -I` no script directory is on `sys.path`)."""
    spec = importlib.util.spec_from_file_location("m06_w27_registration", W27_GENERATOR)
    if spec is None or spec.loader is None:
        raise SystemExit(f"cannot load {W27_GENERATOR}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


w27: Final = _load_w27()


class FactsRefusedError(Exception):
    """W1-W5: the writer will neither emit nor check."""


def extract_facts_v2(archive: Path) -> dict[str, Any]:
    """§15.2's reading rule: WS1's `extract_facts_v2` (7b5c07f) with this writer's path."""
    case_root = archive / "cases"
    names = sorted(p.name for p in case_root.iterdir() if p.is_dir())
    cases = []
    for name in names:
        topo = w27._load(case_root / name / "topology.json")
        topo = topo if isinstance(topo, dict) else {}
        units = [u for u in topo.get("units") or [] if isinstance(u, dict)]
        topology_units: list[dict[str, str]] = sorted(
            ({"id": str(u.get("id")), "kind": str(u.get("kind"))} for u in units),
            key=lambda u: (u["id"], u["kind"]),
        )
        cases.append({"case_id": name, "topology_units": topology_units})
    return {
        "schema": SCHEMA,
        "source": {
            "archive_sha256": json.loads(w27.PROVENANCE_JSON.read_bytes())["archive"]["sha256"],
            "access_report_sha256": w27._sha256_file(w27.ACCESS_JSON),
            "case_facts_v1_sha256": w27._sha256_file(w27.FACTS_JSON),
            "generator": WRITER,
        },
        "cases": cases,
    }


def self_claims(document: dict[str, Any]) -> None:
    """W1-W5 (§15.2), in order; each message gives counts only."""
    access = json.loads(w27.ACCESS_JSON.read_bytes())
    access_ids = sorted(row["case_id"] for row in access["rows"])
    ids = [c["case_id"] for c in document["cases"]]
    if ids != access_ids:
        raise FactsRefusedError(
            f"W1: the archive has {len(ids)} case directories, {len(set(ids) ^ set(access_ids))}"
            f" differing from access_report.json's {len(access_ids)} ids"
        )
    got = w27._sha256_file(w27.FACTS_JSON)
    if got != FACTS_V1_SHA256:
        raise FactsRefusedError(f"W2: case_facts.json has SHA-256 {got}, pinned {FACTS_V1_SHA256}")
    v1 = json.loads(w27.FACTS_JSON.read_bytes())["cases"]
    if ids != [c["case_id"] for c in v1]:
        raise FactsRefusedError("W3: the case-id list differs from case_facts.json's")
    kinds = {c["case_id"]: set(c["topology_kinds"]) for c in v1}
    bad = sum(
        1
        for c in document["cases"]
        if {u["kind"] for u in c["topology_units"]} != kinds[c["case_id"]]
    )
    if bad:
        raise FactsRefusedError(f"W4: {bad} case(s) whose kind set differs from topology_kinds")
    bad = sum(
        1
        for c in document["cases"]
        if len({u["id"] for u in c["topology_units"]}) != len(c["topology_units"])
    )
    if bad:
        raise FactsRefusedError(f"W5: {bad} case(s) repeating a unit id")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--emit", action="store_true", help=f"write {OUT.name}")
    mode.add_argument("--check", action="store_true", help=f"compare with the committed {OUT.name}")
    parser.add_argument("--archive", type=Path, default=w27.ARCHIVE_DIR)
    args = parser.parse_args(argv)
    if not (args.archive / "cases").is_dir():
        print(
            f"NOT CHECKED: archive absent at {args.archive}; {OUT.name} is not verified "
            "(run scripts/m06_w27_acquire.py)"
        )
        return 2
    document = extract_facts_v2(args.archive)
    try:
        self_claims(document)
    except FactsRefusedError as exc:
        print(f"refused: {exc}")
        return 2
    fresh = w27.dump_facts(document)
    if args.check:
        return 0 if w27._compare(OUT, fresh) else 1
    w27._write(OUT, fresh)
    return 0


if __name__ == "__main__":
    sys.exit(main())
