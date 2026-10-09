"""M02 G2 (i)–(ii): the T07 corpus's 50 revisions solved through the application, recorded.

Design note §14.2 *Gates as amended*: at every T07 corpus revision `view.components` is SYN-001's
basis components (i), and the corpus's certificates are byte-identical before and after WO-8.3 and
WO-8.4 (ii). This script commits each revision to a fresh inline `LocalApplication`, validates it,
submits a `solve` job under policy `default`, and records per revision: the parse view's
components, the validation status, the run's outcome and verification status, the SHA-256 of the
`solution_certificate` artifact's bytes and of its canonical document (ADR 0002), and the bundle's
`artifact_r0_sha256`. It prints one JSON document; its SHA-256 is the dump's identity.

Run it at two commits and compare the outputs byte for byte:

    PYTHONPATH=$PWD/src:$PWD/tests python scripts/m02_g2_corpus.py > before.json
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "scripts"))


def main() -> int:
    from t07_corpus import CORPUS
    from t07_identity import _commit

    from openflowsheet.application.contract import ApplicationError
    from openflowsheet.application.local import LocalApplication
    from openflowsheet.application.types import JobRequest, SolveBody
    from openflowsheet.canonical import document_sha256
    from openflowsheet.models.revision_flowsheet import parse_revision
    from openflowsheet.run.bundle import read_manifest

    out: dict[str, Any] = {}
    with tempfile.TemporaryDirectory() as scratch:
        application = LocalApplication.create(Path(scratch) / "p", project_id="m02-g2")
        try:
            for case, build in CORPUS.items():
                document = build()
                try:
                    components: Any = list(parse_revision(document).components)
                except Exception as error:  # noqa: BLE001 - recorded, never raised
                    components = f"unparsed: {type(error).__name__}"
                revision_id = _commit(application, document, f"m02-g2:{case}")
                report = application.validate(revision_id, "simulation")
                request = JobRequest(
                    "solve", f"m02-g2:{case}", SolveBody(revision_id=revision_id, policy_id="default")
                )
                try:
                    job = application.submit_job(request).job
                except ApplicationError as refused:
                    out[case] = {
                        "components": components,
                        "validation": report.as_document()["status"],
                        "refused": str(refused),
                    }
                    continue
                while job.ending is None:
                    application.wait_job(
                        job.job_id, after_sequence=job.event_count - 1, timeout_s=math.inf
                    )
                    job = application.get_job(job.job_id)
                result = application.get_job_result(job.job_id).run_result
                entry: dict[str, Any] = {
                    "components": components,
                    "validation": report.as_document()["status"],
                    "outcome": None if result is None else result.outcome,
                    "verification_status": None
                    if result is None
                    else result.verification_status,
                }
                for output in job.outputs:
                    row = application.store.artifact(output.artifact_id)
                    assert row is not None, output
                    path = application.files_root / row.relpath
                    if output.kind == "solution_certificate":
                        raw = path.read_bytes()
                        entry["certificate_bytes_sha256"] = hashlib.sha256(raw).hexdigest()
                        entry["certificate_document_sha256"] = document_sha256(json.loads(raw))
                    if output.kind == "replay_bundle":
                        manifest, _ = read_manifest(path)
                        entry["artifact_r0_sha256"] = manifest.artifact_r0_sha256
                out[case] = entry
        finally:
            application.close()
    text = json.dumps(out, indent=1, sort_keys=True)
    print(text)
    certified = sum("certificate_document_sha256" in entry for entry in out.values())
    print(
        f"revisions {len(out)}, certificates {certified}, dump sha256 "
        f"{hashlib.sha256(text.encode()).hexdigest()}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
