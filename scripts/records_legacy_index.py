"""F3-WO3 (ADR 0061 D12): the legacy record index, generated from the seven v1 record files.

    python scripts/records_legacy_index.py --write   # writes records/legacy_index.json
    python scripts/records_legacy_index.py --check   # regenerates it in memory and compares

The index (`src/openflowsheet/records/legacy_index.json`) pins, per profiled file, its
`file_sha256` (LF-normalised bytes) and `reference_convention`, and per record its type, id,
position, SHA and findings (`records.importers.legacy.index_document`).
`--check` fails when

- the committed index differs from the one regenerated from the checkout's files;
- a fit input's committed SHA in `records/legacy_profiles.yaml` is not the SHA-256 of that file's
  LF-normalised bytes in the checkout;
- a tracked YAML file declaring `record_schema: schemas/component-record.schema.json` has no
  profile. A tracked symbolic link (the package's `_data/` copies, `openflowsheet.resources`)
  counts as the file it points to.

Each mode prints one summary line and exits 0 only on success.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any, Final

import yaml

ROOT: Final = Path(__file__).resolve().parent.parent
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from openflowsheet.records.importers import legacy  # noqa: E402

INDEX: Final = ROOT / "src" / "openflowsheet" / "records" / "legacy_index.json"


def render(document: Mapping[str, Any]) -> str:
    """The index's committed text: sorted keys, two-space indent, UTF-8, one final newline."""
    return json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def regenerated(root: Path = ROOT) -> str:
    """The index regenerated from the files below `root`."""
    imported = legacy.import_all(lambda path: root.joinpath(*path.split("/")).read_bytes())
    return render(legacy.index_document(imported))


def stale_inputs(root: Path = ROOT) -> list[str]:
    """One line per fit input whose committed SHA is not its file's (missing files included)."""
    found = []
    for profile in legacy.profiles():
        for field, row in profile.provenance.items():
            for item in row.get("inputs", ()):
                target = root.joinpath(*item["path"].split("/"))
                held = legacy.file_sha256(target.read_bytes()) if target.is_file() else None
                if held != item["sha256"]:
                    found.append(f"{profile.profile}.{field}: {item['path']} is {held}")
    return found


def unprofiled(root: Path, tracked: Iterable[str]) -> list[str]:
    """The tracked YAML paths (relative to `root`) that declare the v1 record schema and whose
    file, after following a symbolic link, is no profile's."""
    profiled = {profile.file for profile in legacy.profiles()}
    found = []
    for path in tracked:
        if not path.endswith((".yaml", ".yml")) or not _declares_v1(root / path):
            continue
        if _followed(root, path) not in profiled:
            found.append(path)
    return found


def _followed(root: Path, path: str) -> str:
    """`path`, or the root-relative path of the file a symbolic link at `path` points to."""
    target, base = (root / path).resolve(), root.resolve()
    return target.relative_to(base).as_posix() if target.is_relative_to(base) else path


def _declares_v1(path: Path) -> bool:
    """Whether the YAML file at `path` has the top-level `record_schema` of a v1 record file."""
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8", errors="replace")
    if legacy.V1_RECORD_SCHEMA not in text:
        return False
    try:
        document = yaml.safe_load(text)
    except yaml.YAMLError:
        return False
    return isinstance(document, dict) and document.get("record_schema") == legacy.V1_RECORD_SCHEMA


def tracked_files(root: Path = ROOT) -> list[str]:
    """`git ls-files` below `root`."""
    listed = subprocess.run(
        ["git", "ls-files", "-z"], cwd=root, check=True, capture_output=True
    ).stdout.decode("utf-8")
    return [path for path in listed.split("\0") if path]


def problems(root: Path = ROOT, tracked: Iterable[str] | None = None) -> list[str]:
    """Every reason `--check` fails, in the order the module docstring lists them."""
    found = []
    text = regenerated(root)
    if not INDEX.is_file() or INDEX.read_text(encoding="utf-8") != text:
        found.append(f"{INDEX.relative_to(ROOT)} is missing or stale")
    found += stale_inputs(root)
    found += [
        f"{path} declares {legacy.V1_RECORD_SCHEMA} and has no profile"
        for path in unprofiled(root, tracked_files(root) if tracked is None else tracked)
    ]
    return found


def _counts(text: str) -> str:
    document = json.loads(text)
    records = [record for entry in document["files"] for record in entry["records"]]
    return f"{len(records)} records in {len(document['files'])} files"


def check() -> int:
    found = problems()
    if found:
        print(f"records_legacy_index --check: FAILED, {'; '.join(found)}")
        return 1
    print(f"records_legacy_index --check: clean, {_counts(INDEX.read_text(encoding='utf-8'))}")
    return 0


def write() -> int:
    text = regenerated()
    INDEX.write_text(text, encoding="utf-8")
    print(f"records_legacy_index --write: {_counts(text)} to {INDEX.relative_to(ROOT)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n", 1)[0])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true", help="write the legacy index")
    mode.add_argument("--check", action="store_true", help="regenerate in memory and compare")
    arguments = parser.parse_args(argv)
    return write() if arguments.write else check()


if __name__ == "__main__":
    sys.exit(main())
