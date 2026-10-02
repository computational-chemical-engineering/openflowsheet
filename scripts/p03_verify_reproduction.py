"""Reproduce a candidate in a clean environment and diff it against the recorded P03 inventory.

Plan §8.1 day 9 asks Opus to "reproduce both candidates in a clean environment". An inventory that
only describes the machine that produced it is a description, not evidence; this script turns it
into a falsifiable claim by installing the same pinned version again, from PyPI, with the pip cache
bypassed, and comparing every file against the hashes `p03_binary_inventory.py` recorded.

Files whose content is *generated at install time* rather than shipped in the wheel cannot match and
are not expected to: CPython writes `__pycache__/*.pyc` on first import and embeds the source path
and mtime in them. They are reported in their own category rather than counted as failures, and the
verdict states the number so the exemption is visible instead of silent.

Usage (the caller builds the clean environments; this script only reads them and writes `--out`)::

    python3 -m venv /tmp/repro-casadi
    /tmp/repro-casadi/bin/pip install --no-cache-dir casadi==3.8.0
    .venv/bin/python scripts/p03_verify_reproduction.py \
        --casadi-root /tmp/repro-casadi --pyomo-root /tmp/repro-pyomo \
        --out spikes/p03/results/reproduction.json

Only the *wheel* half of the Pyomo candidate is checked. PyNumero's ASL library is compiled by
`pyomo build-extensions` into the shared `~/.pyomo`, so re-deriving it would overwrite the exact
artifact the P02 evidence manifest references by hash. That is recorded as not attempted, with the
reason, rather than done silently or claimed as verified.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

GENERATED_SUFFIXES = (".pyc",)


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def is_generated(relative: str) -> bool:
    return relative.endswith(GENERATED_SUFFIXES) or "__pycache__/" in relative


def compare_tree(recorded: list[dict[str, Any]], root: Path) -> dict[str, Any]:
    expected = {entry["path"]: (int(entry["bytes"]), str(entry["sha256"])) for entry in recorded}
    present = {
        str(path.relative_to(root))
        for path in root.rglob("*")
        if path.is_file() and not path.is_symlink()
    }
    missing = sorted(set(expected) - present)
    unexpected = sorted(present - set(expected))
    identical: list[str] = []
    differing: list[str] = []
    generated_differing: list[str] = []
    for relative in sorted(set(expected) & present):
        path = root / relative
        size, digest = expected[relative]
        if path.stat().st_size == size and sha256_of(path) == digest:
            identical.append(relative)
        elif is_generated(relative):
            generated_differing.append(relative)
        else:
            differing.append(relative)
    return {
        "root": str(root),
        "recorded_files": len(expected),
        "clean_install_files": len(present),
        "identical": len(identical),
        "differing": differing,
        "generated_differing": generated_differing,
        "missing_from_clean_install": missing,
        "unexpected_in_clean_install": unexpected,
        "reproduced": not (differing or missing or unexpected),
    }


def compare_selected(recorded: dict[str, Any], root: Path) -> dict[str, Any]:
    """Check the binaries and notices of a candidate that ships almost nothing compiled."""
    checked: list[dict[str, Any]] = []
    for entry in recorded["shipped_binaries"]:
        path = root / str(entry["path"])
        checked.append(
            {
                "path": str(entry["path"]),
                "expected_sha256": entry["sha256"],
                "match": path.is_file()
                and path.stat().st_size == int(entry["bytes"])
                and sha256_of(path) == entry["sha256"],
            }
        )
    dist_info = recorded["dist_info"]
    if dist_info.get("present"):
        dist_root = root.parent / str(dist_info["path"])
        for entry in dist_info["notice_files"]:
            path = dist_root / str(entry["path"])
            checked.append(
                {
                    "path": f"{dist_info['path']}/{entry['path']}",
                    "expected_sha256": entry["sha256"],
                    "match": path.is_file() and sha256_of(path) == entry["sha256"],
                }
            )
    return {
        "root": str(root),
        "checked": checked,
        "reproduced": all(item["match"] for item in checked) and bool(checked),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, default=Path("spikes/p03/results"))
    parser.add_argument("--casadi-root", type=Path, required=True, help="clean venv prefix")
    parser.add_argument("--pyomo-root", type=Path, required=True, help="clean venv prefix")
    parser.add_argument("--out", type=Path, default=Path("spikes/p03/results/reproduction.json"))
    arguments = parser.parse_args()

    casadi_recorded = json.loads(
        (arguments.inventory / "casadi-inventory.json").read_text(encoding="utf-8")
    )
    pyomo_recorded = json.loads(
        (arguments.inventory / "pyomo-inventory.json").read_text(encoding="utf-8")
    )

    casadi_tree = next(arguments.casadi_root.glob("lib/python*/site-packages/casadi"))
    pyomo_tree = next(arguments.pyomo_root.glob("lib/python*/site-packages/pyomo"))

    report = {
        "method": (
            "Each candidate was installed again from PyPI at its pinned version into a fresh "
            "virtual environment with `pip install --no-cache-dir`, so the wheel was re-downloaded "
            "rather than re-used, and every file was compared against the SHA-256 recorded by "
            "scripts/p03_binary_inventory.py."
        ),
        "casadi": compare_tree(casadi_recorded["files"], casadi_tree),
        "pyomo_wheel": compare_selected(pyomo_recorded, pyomo_tree),
        "pyomo_asl_not_attempted": (
            "The PyNumero ASL library is built by `pyomo build-extensions` into the shared "
            "~/.pyomo, so rebuilding it would overwrite the artifact the P02 evidence manifest "
            "references by hash. It is recorded as not re-derived, not as verified."
        ),
    }
    arguments.out.parent.mkdir(parents=True, exist_ok=True)
    arguments.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    casadi = report["casadi"]
    assert isinstance(casadi, dict)
    print(
        f"casadi: {casadi['identical']}/{casadi['recorded_files']} byte-identical, "
        f"{len(casadi['differing'])} shipped files differ, "
        f"{len(casadi['generated_differing'])} install-generated files differ"
    )
    pyomo = report["pyomo_wheel"]
    assert isinstance(pyomo, dict)
    print(f"pyomo wheel: reproduced={pyomo['reproduced']} over {len(pyomo['checked'])} artifacts")
    print(f"wrote {arguments.out}")
    return 0 if not casadi["differing"] and pyomo["reproduced"] else 1


if __name__ == "__main__":
    sys.exit(main())
