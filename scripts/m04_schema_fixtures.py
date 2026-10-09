"""Generate M04's round-trip fixtures (spec §10, M04.A35; WO-6).

One valid fixture per new document, emitted by real code, and one invalid fixture each with its
first required member removed (`scripts/m02_schema_fixtures.py`'s pattern: `{expect_error,
document}`). Fixtures live under `tests/fixtures/schemas/<def>/{valid,invalid}/`.

- **`surrogate_manifest`, `model_evidence`**: the records of M04.A19's run — the smooth synthetic
  parent (`tests/support/m04_synthetic_parents.py`) on the prefix plan `it1-prefix`, through
  `studies.surrogate.study.run_study` and M02's experiment runner, in a scratch store. This
  manifest is the promoted surrogate of M04.A25–A29.
- **`surrogate_study_body`**: the body of a `surrogate_study` job request for the registered
  stand-in on `it1-prefix`, as `JobRequest` normalizes it.
- **`surrogate_study_result`**: that job's answer (`get_job_result`'s `surrogate_study`), from a
  scratch project.

"Regenerates identically" is equality after `stable`: experiment keys, key-list and document
hashes and environment fingerprints move with the code (an experiment key carries the boundary
module's and the parent module's file hashes), so they are masked; every other number is compared
rounded to 10 significant digits, because the fit is a LAPACK QR whose last bits are the
platform's (spec §3.4; A10's tolerance is 10⁻¹⁰ × ‖β‖∞).

Usage:
    PYTHONPATH=src .venv/bin/python scripts/m04_schema_fixtures.py          # check
    PYTHONPATH=src .venv/bin/python scripts/m04_schema_fixtures.py --write  # missing or differing
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Final

ROOT: Final = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests" / "support"))

FIXTURE_DIR: Final = ROOT / "tests" / "fixtures" / "schemas"
_STUDY: Final = "surrogate-manifest.schema.json#/$defs/"
#: Each fixture directory's schema reference, as `application.types.schema_errors` takes it.
REFERENCES: Final[Mapping[str, str]] = {
    "surrogate_manifest": "surrogate-manifest.schema.json",
    "model_evidence": "model-evidence.schema.json",
    "surrogate_study_body": _STUDY + "surrogate_study_body",
    "surrogate_study_result": _STUDY + "surrogate_study_result",
}
#: Members that move with the code, the machine or the run; masked by `stable`.
VOLATILE: Final = frozenset(
    {
        "keys",
        "keys_sha256",
        "stencil_keys",
        "fingerprint_sha256s",
        "evidence_sha256",
        "manifest_sha256",
    }
)
SIGNIFICANT: Final = 10


def stable(document: Any) -> Any:
    """`document` with its volatile members masked and its floats rounded (module docstring)."""
    if isinstance(document, dict):
        return {
            key: "MASKED" if key in VOLATILE else stable(value) for key, value in document.items()
        }
    if isinstance(document, list):
        return [stable(item) for item in document]
    if isinstance(document, float):
        return float(f"{document:.{SIGNIFICANT}g}")
    return document


def _required(reference: str) -> list[str]:
    name, _, pointer = reference.partition("#")
    node: Any = json.loads((ROOT / "schemas" / name).read_text(encoding="utf-8"))
    for token in pointer.split("/")[1:]:
        node = node[token]
    required: list[str] = node["required"]
    return required


def _pair(directory: str, name: str, document: Mapping[str, Any]) -> dict[str, Any]:
    """The valid fixture and the invalid one with the first required member removed."""
    member = _required(REFERENCES[directory])[0]
    return {
        f"{directory}/valid/{name}.json": dict(document),
        f"{directory}/invalid/missing_{member}.json": {
            "expect_error": f"'{member}' is a required property",
            "document": {key: value for key, value in document.items() if key != member},
        },
    }


def record_documents() -> dict[str, Any]:
    """M04.A19's manifest and evidence."""
    import tempfile

    import m04_synthetic_parents as parents

    from openflowsheet.adapters.experiments.runner import ExperimentRunner
    from openflowsheet.adapters.experiments.store import ExperimentStore, ListArtifactSink
    from openflowsheet.compiled import EvaluationContext
    from openflowsheet.studies.surrogate.study import run_study
    from openflowsheet.thermo.pr_c1 import PrC1Provider

    variant = parents.synthetic_variant(parents.SMOOTH_ID)
    with tempfile.TemporaryDirectory() as scratch:
        runner = ExperimentRunner(
            ExperimentStore(Path(scratch), ListArtifactSink()),
            PrC1Provider(),
            EvaluationContext(model_version="m04-fixtures", constants_sha256="0" * 64),
            backend_for=parents.backend_for(),
        )
        outcome = run_study(runner, variant, "it1-prefix", 1000)
    assert outcome.manifest is not None and outcome.evidence is not None
    name = "a19_smooth_prefix"
    return {
        **_pair("surrogate_manifest", name, outcome.manifest),
        **_pair("model_evidence", name, outcome.evidence),
    }


def job_documents() -> dict[str, Any]:
    """The stand-in's `surrogate_study` body, normalized, and its job's answer."""
    import tempfile

    from openflowsheet.adapters import variants
    from openflowsheet.application.local import LocalApplication
    from openflowsheet.application.operations import dispatch
    from openflowsheet.application.types import JobRequest

    standin = variants.registered_variant("standin-x025-v1")
    request = {
        "operation": "surrogate_study",
        "idempotency_key": "fixture-surrogate-study",
        "body": {
            "parent": {
                "model_id": standin.model_id,
                "variant_id": standin.variant_id,
                "variant_sha256": standin.sha256,
            },
            "plan_id": "it1-prefix",
            "budget": {"max_cold_experiments": 199},
        },
    }
    normalized = JobRequest.from_document(request).as_document()
    with tempfile.TemporaryDirectory() as scratch:
        application = LocalApplication.create(Path(scratch) / "project")
        try:
            job = dispatch(application, "submit_job", normalized)["job"]
            answer = dispatch(application, "get_job_result", {"job_id": job["job_id"]})
        finally:
            application.close()
    name = "standin_prefix"
    return {
        **_pair("surrogate_study_body", name, normalized["body"]),
        **_pair("surrogate_study_result", name, answer["surrogate_study"]),
    }


def documents() -> dict[str, Any]:
    return {**record_documents(), **job_documents()}


def serialize(document: Any) -> str:
    return json.dumps(document, indent=2) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    arguments = parser.parse_args()
    status = 0
    for name, document in documents().items():
        path = FIXTURE_DIR / name
        same = path.is_file() and stable(json.loads(path.read_text(encoding="utf-8"))) == stable(
            document
        )
        if same:
            print(f"same {name}")
        elif arguments.write:
            # Only a missing or differing fixture is (re)written: a passed one is never
            # regenerated.
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(serialize(document), encoding="utf-8")
            print(f"wrote {name}")
        else:
            print(f"{'differs' if path.is_file() else 'missing'} {name}")
            status = 1
    return status


if __name__ == "__main__":
    raise SystemExit(main())
