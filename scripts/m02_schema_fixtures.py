"""Generate M02's round-trip fixtures (design note §3.6, gate G1 (a)).

One valid fixture per new `$def`, emitted by real code, and one invalid fixture per `$def` with its
first required member removed (`scripts/t07_schema_fixtures.py`'s pattern: `{expect_error,
document}`). Fixtures live under `tests/fixtures/schemas/<def>/{valid,invalid}/`.

- **`model_variant`**: the registered stand-in variant, as `adapters.variants` loads it at its
  pinned hash (the documents are package data, not run output; the record fixtures are).
- **`experiment` `request`, `result`, `attempt`**: one real `ExperimentRunner.run` of the
  registered stand-in at M01's nominal inlet scaled to 1000 tubes, in a scratch project; and one
  out-of-process attempt by the synthetic child (`tests/support/synthetic_child.py`) for the same
  inlet. Keys, environment hashes, timings, logs and fingerprints differ between machines and
  code versions, so "regenerates identically" is equality with those members masked (`stable`).

Usage:
    PYTHONPATH=src .venv/bin/python scripts/m02_schema_fixtures.py          # check
    PYTHONPATH=src .venv/bin/python scripts/m02_schema_fixtures.py --write  # missing or differing
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

FIXTURE_DIR: Final = ROOT / "tests" / "fixtures" / "schemas"
#: Each fixture directory's schema reference, as `application.types.schema_errors` takes it.
REFERENCES: Final[Mapping[str, str]] = {
    "model_variant": "model-variant.schema.json",
    "experiment_request": "experiment.schema.json#/$defs/request",
    "experiment_result": "experiment.schema.json#/$defs/result",
    "experiment_attempt": "experiment.schema.json#/$defs/attempt",
}
#: Members that differ between machines, code versions and runs; masked by `stable`.
VOLATILE: Final = frozenset(
    {
        "experiment_key",
        "request_sha256",
        "environment_fingerprint_sha256",
        "fingerprint_sha256",
        "provider_identity_sha256",
        "configuration_sha256",
        "timing",
        "logs",
        "fingerprint",
    }
)
SYNTHETIC_CHILD: Final = ROOT / "tests" / "support" / "synthetic_child.py"
#: M01 spec §8.15's nominal composition at the nominal per-tube flow, over 1000 tubes.
NOMINAL_Y: Final = (0.6975, 0.2325, 0.03, 0.017142857142857144, 0.022857142857142857)
NOMINAL_TUBE_FLOW: Final = 0.007146961299302104
N_TUBES: Final = 1000.0


def stable(document: Any) -> Any:
    """`document` with its volatile members masked."""
    if isinstance(document, dict):
        return {
            key: "MASKED" if key in VOLATILE else stable(value) for key, value in document.items()
        }
    if isinstance(document, list):
        return [stable(item) for item in document]
    return document


def synthetic_variant(name: str, hooks: list[str], **execution: Any) -> Any:
    """A test-only out-of-process variant run by the synthetic child (never registered)."""
    from openflowsheet.adapters import variants
    from openflowsheet.canonical import file_sha256

    standin = variants.registered_variant("standin-x025-v1").document
    document = {
        **standin,
        "model_id": "c1.reactor",
        "variant_id": f"test-synthetic-{name}",
        "evaluation": {
            "kind": "out_of_process",
            "reactor": {
                "repository": "tests/support/synthetic_child.py",
                "commit": "0" * 40,
                "model_class": "synthetic_child",
                "licence": "test-only",
                "licence_notice_sha256": "0" * 64,
                "used_by_reference": True,
            },
            "environment": {"python": "project", "lock_sha256": "0" * 64, "env_id": "synthetic"},
            "runner_sha256": file_sha256(SYNTHETIC_CHILD),
            "overlay_sha256": "0" * 64,
            "configuration": {"hooks": hooks, "sweep_ratio": 1.0},
            "profile": {"id": "synthetic"},
        },
        "execution": {"timeout_s": 30.0, "max_retries": 1, "kill_grace_s": 2.0, **execution},
    }
    return variants.variant_from_document(document)


def synthetic_backend(environment_root: Path) -> Any:
    """`backend_for` running every out-of-process variant on the synthetic child."""
    from openflowsheet.adapters.experiments.backends import InProcessBackend, OutOfProcessBackend
    from openflowsheet.adapters.external.launcher import ChildProgram
    from openflowsheet.canonical import file_sha256

    environment_root.mkdir(parents=True, exist_ok=True)
    program = ChildProgram(Path(sys.executable), SYNTHETIC_CHILD, environment_root)

    def backend_for(variant: Any) -> Any:
        if variant.kind == "in_process":
            return InProcessBackend(variant)
        return OutOfProcessBackend(
            variant, program, expected={"runner_sha256": file_sha256(SYNTHETIC_CHILD)}
        )

    return backend_for


def nominal_inlet() -> Any:
    from openflowsheet.thermo import StreamState

    total = NOMINAL_TUBE_FLOW * N_TUBES
    return StreamState(n=tuple(total * y for y in NOMINAL_Y), temperature=673.15, pressure=1.0e7)


def record_documents() -> dict[str, Any]:
    import tempfile

    from openflowsheet.adapters import variants
    from openflowsheet.adapters.experiments.runner import ExperimentRunner
    from openflowsheet.adapters.experiments.store import ExperimentStore
    from openflowsheet.compiled import EvaluationContext
    from openflowsheet.models.c1 import COMPONENTS
    from openflowsheet.thermo.pr_c1 import PrC1Provider

    context = EvaluationContext(model_version="m02-fixtures", constants_sha256="0" * 64)
    with tempfile.TemporaryDirectory() as scratch:
        root = Path(scratch)
        runner = ExperimentRunner(
            ExperimentStore(root),
            PrC1Provider(),
            context,
            backend_for=synthetic_backend(root / "env"),
        )
        standin = variants.registered_variant("standin-x025-v1")
        inside = runner.run(standin, nominal_inlet(), COMPONENTS, N_TUBES)
        outside = runner.run(synthetic_variant("ok", ["ok"]), nominal_inlet(), COMPONENTS, N_TUBES)
    assert inside.result is not None and outside.result is not None
    documents: dict[str, Any] = {}
    documents.update(_pair("experiment_request", "standin_nominal", inside.request))
    documents.update(_pair("experiment_result", "standin_nominal", inside.result))
    documents.update(_pair("experiment_attempt", "in_process_completed", inside.attempts[0]))
    documents["experiment_attempt/valid/out_of_process_completed.json"] = dict(outside.attempts[0])
    return documents


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


def variant_documents() -> dict[str, Any]:
    from openflowsheet.adapters import variants

    standin = variants.registered_variant("standin-x025-v1")
    return _pair("model_variant", standin.variant_id, standin.document)


def documents() -> dict[str, Any]:
    return {**variant_documents(), **record_documents()}


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
