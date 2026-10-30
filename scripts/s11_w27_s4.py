"""W27 v3 snapshot S4 of the S11 build, and its classification of the development half.

W27v3-R08 (`docs/derivations/W27-registration-v3.md`; S11 units design §4.10, §9): S4 is the S11
build's version 3 snapshot (127 routes, the Wilson route on `wilson-ig-v2`), generated at WO-I1b and
registered with its SHA-256. `docs/reviews/S11-rulings.md` item 3, acceptance 4: S4 classifies under
version 3 on all 225 development rows (the C2 split) with no refusal, and the counts are recorded.

The record holds S4 in W27-R22's committed form, its SHA-256, and the tally of the 225 rows (L01's
`retake.tally` form). `--check` rebuilds the snapshot from the build at hand and requires it to
equal S4 in every member but `git_commit` (S11.A40), and the 225 rows to reproduce the tally.

    python scripts/s11_w27_s4.py --emit
    python scripts/s11_w27_s4.py --check
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Final

from benchmarks.l01 import retake
from benchmarks.m06.w27 import registration, snapshot

OUT: Final = registration.RECORDS / "snapshot_s4.json"
SCHEMA: Final = "w27-v3-s4-record-v1"
VERSION: Final = 3


def build() -> dict[str, Any]:
    """S4 from the build at hand, and the version 3 tally of the 225 development rows. Refuses
    (`coverage.RefusalError`, `snapshot.SnapshotUnsupportedError`) rather than records a refusal."""
    s4 = snapshot.build_snapshot(registration_version=VERSION)
    dev, cases, _, _ = retake.development_inputs()
    rows = retake.classify_all(cases, s4, VERSION)
    if sorted(rows) != sorted(dev):
        raise RuntimeError("the classified rows are not the 225 development ids")
    providers = [r["provider_id"] for r in s4["routes"]]
    return {
        "schema": SCHEMA,
        "rule": "W27v3-R08; S11-rulings item 3 acceptance 4",
        "scope": "development half only (C2 split, 225 ids); no held-out row is read",
        "registration_version": VERSION,
        "routes": len(providers),
        "wilson_route": [p for p in providers if p.startswith("wilson-")],
        "snapshot_sha256": registration.sha256_bytes(registration.dump(s4)),
        "snapshot": s4,
        "development": {"rows": len(rows), "tally": retake.tally(rows)},
    }


def problems(record: dict[str, Any], built: dict[str, Any]) -> list[str]:
    """S11.A40 and acceptance 4 against the committed record: one line per difference."""
    found: list[str] = []
    stored = record["snapshot"]
    if record["snapshot_sha256"] != registration.sha256_bytes(registration.dump(stored)):
        found.append("snapshot_sha256 is not the SHA-256 of the stored snapshot")
    live = built["snapshot"]
    # R-902: the build provenance, `git_commit` and `package_version`, is not compared.
    provenance = ("git_commit", "package_version")
    for key in sorted(set(stored) | set(live)):
        if key not in provenance and stored.get(key) != live.get(key):
            found.append(f"snapshot member {key!r} differs from the build's")
    for key in ("routes", "wilson_route", "development", "registration_version", "schema"):
        if record.get(key) != built[key]:
            found.append(f"{key} differs: recorded {record.get(key)!r}, built {built[key]!r}")
    return found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--emit", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    built = build()
    if args.check:
        found = problems(json.loads(OUT.read_bytes()), built)
        for line in found:
            print(line)
        print(f"S4 {'OK' if not found else 'DIFFERS'}: {len(found)} problem(s)")
        return 1 if found else 0
    OUT.write_bytes(registration.dump(built))
    tally = built["development"]["tally"]["classes"]
    print(
        f"wrote {OUT.relative_to(registration.ROOT)}: {built['routes']} routes, "
        f"S4 {built['snapshot_sha256']}, classes {tally}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
