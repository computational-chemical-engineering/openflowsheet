"""T07 W6d, gate G19: the licence inventory of the optional `server` extra's closure.

Design note §11.1 and D-Q5. The closure is every distribution reachable from the `server` extra's
requirements in `pyproject.toml`, walked through each installed distribution's `Requires-Dist`
with its environment markers evaluated for the running interpreter (so `pywin32`, which `mcp`
requires on Windows only, is not in a Linux closure) and with requested extras followed
(`pyjwt[crypto]` brings `cryptography`). Every term is **read from the installed distribution** —
`License-Expression`, else `License` plus the licence classifiers, and the SHA-256 of every licence
file under `.dist-info/` — never guessed, per ADR 0006's rule that a term is read from a shipped
notice or recorded as unresolved.

The verdict fails on

- a **GPL-family** licence (LGPL and AGPL included) anywhere in the closure: D-Q5 sends it to the
  design lane;
- an **unresolved** licence: no expression, no `License` field, no classifier and no licence file;
- a licence **outside `ALLOWED`**: G19 itself only forbids the two above, but a new licence family
  is a design-lane question too (T07 W6d brief), so the list is closed and every entry is justified.

`compiled` is read from the installed wheel's `WHEEL` file (`Root-Is-Purelib: false`, or a tag other
than `*-none-any`). The wheel SHA-256s are of the wheel files themselves, which an installed
environment does not keep; `--wheels DIR` hashes the files in a directory filled by `pip download`
(both CI architectures, W0.6's commands), and without it the record's `wheels` are empty.

Usage (in an environment that has the extra, e.g. `pip install -r requirements.lock`):
    python scripts/t07_licence_inventory.py [--wheels DIR] [--out docs/t07-server-licences.json]

Exit status 0 when the verdict passes, 1 when it fails; the record is written either way.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata as metadata
import json
import re
import sys
import tomllib
from pathlib import Path
from typing import Any

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name, parse_wheel_filename

ROOT = Path(__file__).resolve().parent.parent
FORMAT = "t07-server-licences-v1"

GPL_FAMILY = re.compile(r"\b(A|L)?GPL|GNU (Lesser |Affero |Library )?General Public", re.IGNORECASE)

# Every licence the closure may carry, as the distribution declares it (`License-Expression`, else
# the `License` field). A licence not listed here fails the verdict and goes to the design lane.
ALLOWED: dict[str, str] = {
    "MIT": "permissive",
    "MIT-0": "permissive (MIT without the attribution condition); cffi",
    "BSD-3-Clause": "permissive",
    "Apache-2.0": "permissive",
    "Apache-2.0 OR BSD-3-Clause": "permissive, dual; cryptography",
    "PSF-2.0": "permissive (Python Software Foundation licence); typing_extensions, already in the "
    "base closure through jsonschema",
    "MPL-2.0": "weak, file-level copyleft, used unmodified; certifi (httpx's CA bundle, no drop-in "
    "replacement). Accepted by the build lane under ADR 0006: docs/T07_DECISIONS.md, decision E5",
}


def server_requirements(pyproject: Path) -> list[Requirement]:
    with pyproject.open("rb") as handle:
        project = tomllib.load(handle)["project"]
    return [Requirement(text) for text in project["optional-dependencies"]["server"]]


def _wanted(requirement: Requirement, extras: set[str]) -> bool:
    if requirement.marker is None:
        return True
    return any(requirement.marker.evaluate({"extra": extra}) for extra in extras | {""})


def closure(roots: list[Requirement]) -> dict[str, metadata.Distribution]:
    """Every installed distribution reachable from `roots`, keyed by canonical name."""
    found: dict[str, metadata.Distribution] = {}
    extras: dict[str, set[str]] = {}
    queue = [requirement for requirement in roots if _wanted(requirement, set())]
    while queue:
        requirement = queue.pop()
        name = canonicalize_name(requirement.name)
        requested = set(requirement.extras)
        if name in found and requested <= extras[name]:
            continue
        # An absent distribution is a broken environment, not a licence question: let it raise.
        distribution = found.get(name) or metadata.distribution(requirement.name)
        if not requirement.specifier.contains(distribution.version, prereleases=True):
            raise SystemExit(f"{name} {distribution.version} does not satisfy {requirement}")
        found[name] = distribution
        extras[name] = extras.get(name, set()) | requested
        for text in distribution.requires or []:
            child = Requirement(text)
            if _wanted(child, extras[name]):
                queue.append(child)
    return found


def _licence_files(distribution: metadata.Distribution) -> dict[str, str]:
    files: dict[str, str] = {}
    for entry in distribution.files or []:
        path = str(entry)
        if ".dist-info/" not in path:
            continue
        inside = path.split(".dist-info/", 1)[1]
        base = inside.rsplit("/", 1)[-1].upper()
        if inside.startswith("licenses/") or base.startswith(
            ("LICENSE", "LICENCE", "COPYING", "NOTICE", "AUTHORS")
        ):
            files[inside] = hashlib.sha256(Path(str(entry.locate())).read_bytes()).hexdigest()
    return dict(sorted(files.items()))


def _compiled(distribution: metadata.Distribution) -> bool:
    wheel = distribution.read_text("WHEEL") or ""
    fields = [line.split(":", 1) for line in wheel.splitlines() if ":" in line]
    purelib = [value.strip().lower() for key, value in fields if key.strip() == "Root-Is-Purelib"]
    tags = [value.strip() for key, value in fields if key.strip() == "Tag"]
    return purelib != ["true"] or any(not tag.endswith("-none-any") for tag in tags)


def _wheels(directory: Path | None, name: str, version: str) -> dict[str, dict[str, str]]:
    """The downloaded wheels of one distribution, keyed by platform (`any`, `x86_64`, `aarch64`)."""
    if directory is None:
        return {}
    found: dict[str, dict[str, str]] = {}
    for path in sorted(directory.glob("*.whl")):
        wheel_name, wheel_version, _, tags = parse_wheel_filename(path.name)
        if wheel_name != name or str(wheel_version) != version:
            continue
        platforms = {tag.platform for tag in tags}
        key = (
            "any"
            if platforms == {"any"}
            else next(
                (arch for arch in ("x86_64", "aarch64") if any(arch in p for p in platforms)),
                "other",
            )
        )
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        found[key] = {"file": path.name, "sha256": digest}
    return found


def verdict_of(entry: dict[str, Any]) -> str:
    declared = entry["license_expression"] or entry["license"]
    text = " ".join(filter(None, [declared, *entry["license_classifiers"]]))
    if GPL_FAMILY.search(text):
        return "gpl-family"
    if not (declared or entry["license_classifiers"] or entry["license_files"]):
        return "unresolved"
    if declared not in ALLOWED:
        return "not-allowed"
    return "ok"


def inventory(pyproject: Path, wheels: Path | None) -> dict[str, Any]:
    roots = server_requirements(pyproject)
    rows = []
    for name, distribution in sorted(closure(roots).items()):
        meta = distribution.metadata
        licence = meta.get("License")
        entry: dict[str, Any] = {
            "name": name,
            "version": distribution.version,
            "license_expression": meta.get("License-Expression"),
            # A few distributions put the whole licence text in `License`; its first line names it.
            "license": None if licence is None else licence.strip().splitlines()[0],
            "license_classifiers": sorted(
                value.removeprefix("License :: ")
                for value in meta.get_all("Classifier") or []
                if value.startswith("License ::")
            ),
            "license_files": _licence_files(distribution),
            "compiled": _compiled(distribution),
            "wheels": _wheels(wheels, name, distribution.version),
        }
        entry["verdict"] = verdict_of(entry)
        rows.append(entry)
    return {
        "format": FORMAT,
        "extra": "server",
        "requirements": [str(requirement) for requirement in roots],
        "python": ".".join(str(part) for part in sys.version_info[:3]),
        "distributions": rows,
        "failures": [f"{row['name']}: {row['verdict']}" for row in rows if row["verdict"] != "ok"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--pyproject", type=Path, default=ROOT / "pyproject.toml")
    parser.add_argument("--wheels", type=Path, help="a directory of `pip download`ed wheels")
    parser.add_argument("--out", type=Path, help="write the record here (JSON)")
    args = parser.parse_args()
    record = inventory(args.pyproject, args.wheels)
    text = json.dumps(record, indent=1, sort_keys=True) + "\n"
    if args.out:
        args.out.write_text(text, encoding="utf-8")
    for row in record["distributions"]:
        declared = row["license_expression"] or row["license"] or "—"
        compiled = "compiled" if row["compiled"] else "pure"
        print(f"{row['name']} {row['version']}: {declared} ({compiled}) {row['verdict']}")
    count = len(record["distributions"])
    if record["failures"]:
        print(f"G19 FAILED ({count} distributions): " + "; ".join(record["failures"]))
        return 1
    print(f"G19: {count} distributions, no GPL-family, unresolved or unlisted licence")
    return 0


if __name__ == "__main__":
    sys.exit(main())
