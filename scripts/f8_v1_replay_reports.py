"""E-F8-1's expectation: the replay reports of every committed 0.3.0 bundle (ADR 0067, F8-WO3).

Each bundle under `tests/fixtures/f0/v0.3.0-bundles` is replayed through `run.replay.replay` in
four fixed scenarios, every input pinned so that the report is the same on every machine:

    inspect         no rerun; this side is the recorded environment
    self            the archive's own artifacts as the rerun; the recorded environment
    other_platform  as `self`, this side on the other registered architecture
    changed_lock    as `self`, this side with another lock hash

The SHA-256 of each report's canonical JSON is written, keyed `<set>/<name>` then scenario. The
committed expectation (`tests/fixtures/f8/v1-replay-reports.json`) was computed with this script
at `ddac950f` (F8-WO1b, before F8's replay; `run/replay.py`, `run/bundle.py` and `run/compare.py`
there are the branch point's), and `tests/test_f8_replay_v2.py` recomputes it at the head:
byte-identical reports, so the same mode, verdict and reasons.

    python scripts/f8_v1_replay_reports.py --write PATH   # compute and write
    python scripts/f8_v1_replay_reports.py --check        # compare with the committed file
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Final

from openflowsheet.canonical import canonical_json
from openflowsheet.run.bundle import read_artifact, read_manifest
from openflowsheet.run.replay import Rerun, replay

ROOT: Final = Path(__file__).resolve().parents[1]
BUNDLES: Final = ROOT / "tests" / "fixtures" / "f0" / "v0.3.0-bundles"
EXPECTED: Final = ROOT / "tests" / "fixtures" / "f8" / "v1-replay-reports.json"
SCENARIOS: Final = ("inspect", "self", "other_platform", "changed_lock")
OTHER_ARCHITECTURE: Final = {"x86_64": "aarch64", "aarch64": "x86_64"}


def bundle_directories(bundles: Path = BUNDLES) -> list[Path]:
    """Every committed bundle directory, sorted."""
    return sorted(path.parent for path in bundles.glob("*/*/run-manifest.json"))


def reports(directory: Path) -> dict[str, dict[str, Any]]:
    """The report documents of `directory` in each scenario."""
    manifest, _ = read_manifest(directory)
    recorded = manifest.environment
    archive = Rerun({name: read_artifact(directory, name) for name in sorted(manifest.artifacts)})
    other = dataclasses.replace(
        recorded, architecture=OTHER_ARCHITECTURE.get(recorded.architecture, "x86_64")
    )
    changed = dataclasses.replace(recorded, lock_sha256="f" * 64)
    found = {
        "inspect": replay(directory, None, current=recorded),
        "self": replay(directory, archive, current=recorded),
        "other_platform": replay(directory, archive, current=other),
        "changed_lock": replay(directory, archive, current=changed),
    }
    return {name: found[name].as_document() for name in SCENARIOS}


def digests(bundles: Path = BUNDLES) -> dict[str, dict[str, str]]:
    """`{<set>/<name>: {scenario: sha256 of the report's canonical JSON}}` over every bundle."""
    return {
        f"{directory.parent.name}/{directory.name}": {
            name: hashlib.sha256(canonical_json(document)).hexdigest()
            for name, document in reports(directory).items()
        }
        for directory in bundle_directories(bundles)
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--write", type=Path, help="write the digests to this file")
    group.add_argument("--check", action="store_true", help="compare with the committed file")
    arguments = parser.parse_args(argv)
    measured = digests()
    if arguments.write is not None:
        arguments.write.parent.mkdir(parents=True, exist_ok=True)
        arguments.write.write_text(json.dumps(measured, indent=1, sort_keys=True) + "\n")
        print(f"wrote {len(measured)} bundles x {len(SCENARIOS)} scenarios to {arguments.write}")
        return 0
    expected = json.loads(EXPECTED.read_text(encoding="utf-8"))
    moved = sorted(
        f"{key}:{name}"
        for key in sorted(set(expected) | set(measured))
        for name in SCENARIOS
        if expected.get(key, {}).get(name) != measured.get(key, {}).get(name)
    )
    print(f"{'FAIL' if moved else 'PASS'}: {len(measured)} bundles, {len(moved)} reports moved")
    for entry in moved:
        print(f"  {entry}")
    return 1 if moved else 0


if __name__ == "__main__":
    sys.exit(main())
