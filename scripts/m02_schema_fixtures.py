"""Generate M02's round-trip fixtures (design note §3.6, gate G1 (a)).

One valid fixture per new `$def`, emitted by real code, and one invalid fixture per `$def` with its
first required member removed (`scripts/t07_schema_fixtures.py`'s pattern: `{expect_error,
document}`). Fixtures live under `tests/fixtures/schemas/<def>/{valid,invalid}/`.

- **`model_variant`**: the registered stand-in variant, as `adapters.variants` loads it at its
  pinned hash (the documents are package data, not run output; the record fixtures are).

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
}


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
    return {**variant_documents()}


def serialize(document: Any) -> str:
    return json.dumps(document, indent=2) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    arguments = parser.parse_args()
    status = 0
    for name, document in documents().items():
        path = FIXTURE_DIR / name
        same = path.is_file() and json.loads(path.read_text(encoding="utf-8")) == document
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
