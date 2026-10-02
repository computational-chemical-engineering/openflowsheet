"""Generate the K05 round-trip fixtures from real runs and real replays. Register R-015.

Four documents, and the interesting ones are the two that did not match. A `RunManifest` and a
clean `exact_replay`/`MATCH` prove the happy path; the changed-dependency report and the
tampered-archive report are what a reader consults when something has gone wrong, and they are
the ones that must be right.

**The environment in these fixtures is whatever machine generated them.** That is unavoidable
and it is also why the comparison rule treats the environment as provenance: the fixtures are
regenerated on both CI architectures and compared under ADR 0007 D2, where architecture, OS
release and BLAS version are expected to differ.

Usage:
    PYTHONPATH=. .venv/bin/python scripts/k05_schema_fixtures.py [--write]

The check below compares bytes, so it always reports the run manifest as differing
(`elapsed_seconds`, `started_at`, …). That file "regenerates identically" when
`tests/test_k05_schemas.py` passes — `differences()` empty with `VOLATILE_FIELDS` excluded, and
Q-S7's certificate hash equal on its platform (T06 spec A81 (b)) — and `--write` is for when
one of those fails, not for a volatile field.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from dataclasses import replace
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from k03_schema_fixtures import POLICY, flowsheet  # noqa: E402

from openflowsheet.run.bundle import ARTIFACT_DIR, read_artifact  # noqa: E402
from openflowsheet.run.manifest import THREAD_VARIABLES  # noqa: E402
from openflowsheet.run.replay import Rerun, replay  # noqa: E402
from openflowsheet.run.session import run_session  # noqa: E402

FIXTURE_DIR = ROOT / "tests" / "fixtures" / "schemas"


def resolved_artifacts(directory: Path) -> dict[str, Any]:
    """Solve the same flowsheet **again** and return the fresh documents. M6.

    Re-reading the archive and calling it a rerun measures `differences(x, x)`, which is true
    of any two identical objects and says nothing about the solver. The Fable review of K05
    caught that in the evidence script, the fixture generator and the test at once. A second
    solve is what ADR 0007 D3.2 means by observing bitwise agreement.
    """
    import tempfile

    with tempfile.TemporaryDirectory() as scratch:
        second = Path(scratch)
        manifest = run_session(flowsheet(), second, policy=POLICY, run_id="rerun")
        return {name: read_artifact(second, name) for name in manifest.artifacts}


def documents() -> dict[str, Any]:
    # F4: an unpinned machine cannot produce an `exact_replay`, by design. The fixtures show
    # the real modes, so they are generated with the pins CI uses.
    for variable in THREAD_VARIABLES:
        os.environ.setdefault(variable, "1")

    with tempfile.TemporaryDirectory() as scratch:
        directory = Path(scratch)
        manifest = run_session(flowsheet(), directory, policy=POLICY, run_id="syn001-nominal")
        # M6: a *second solve*, not the archive re-read. Re-reading measures
        # `differences(x, x)` and would report bitwise agreement for any archive at all.
        fresh = resolved_artifacts(directory)

        clean = replay(directory, Rerun(fresh))
        if clean.mode != "exact_replay" or clean.verdict != "MATCH":
            raise SystemExit(f"the clean replay was {clean.mode}/{clean.verdict}")

        changed = replay(
            directory,
            Rerun(fresh),
            current=replace(manifest.environment, lock_sha256="0" * 64),
        )
        if changed.verdict != "NOT_RUN":
            raise SystemExit("a changed dependency must never produce a rerun verdict")

        # Tamper with a stored artifact, then ask for a replay that would otherwise match.
        target = directory / ARTIFACT_DIR / "solve-events.json"
        edited = json.loads(target.read_text())
        edited[-1]["message"] = "edited after the fact"
        target.write_text(json.dumps(edited))
        tampered = replay(directory, Rerun(fresh))
        if tampered.integrity.ok or tampered.verdict != "NOT_RUN":
            raise SystemExit("a tampered archive must not be re-run")

        return {
            "run_manifest/valid/syn001_nominal.json": manifest.as_document(),
            "replay_report/valid/exact_match.json": clean.as_document(),
            "replay_report/valid/changed_dependency.json": changed.as_document(),
            "replay_report/valid/tampered_archive.json": tampered.as_document(),
        }


def serialize(document: Any) -> str:
    return json.dumps(document, indent=1, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    arguments = parser.parse_args()

    differing = []
    for name, document in documents().items():
        path = FIXTURE_DIR / name
        text = serialize(document)
        if not path.exists() or path.read_text(encoding="utf-8") != text:
            differing.append(name)
            if arguments.write:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding="utf-8")
    if not differing:
        print("all K05 fixtures match what the code emits")
        return 0
    verb = "rewrote" if arguments.write else "differ (rerun with --write)"
    print(f"{verb}: {', '.join(differing)}")
    return 0 if arguments.write else 1


if __name__ == "__main__":
    raise SystemExit(main())
