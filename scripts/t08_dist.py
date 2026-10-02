"""T08.A43 (W4.2): build the sdist and the wheel twice from a commit, and inspect them.

T08 release spec §8.2 step 3 and §9 T08.A43: "sdist and wheel built twice — contents limited to
`openflowsheet/**`, the runtime data the package needs, `LICENSE`, `NOTICE`, metadata;
`Requires-Dist` pins equal `pyproject.toml`'s; the two builds' unpacked contents identical file by
file (zip bytes reported)". ADR 0006 mode A: the project's own bytes only, with `LICENSE` and
`NOTICE` (T08.A31's packaging half).

**What is built.** `git archive` of the commit (default `HEAD`), never the working tree, so an
untracked file, a stale `build/` or an `egg-info` cannot enter the artifacts, and a dirty tree is
recorded (`tree_clean`) but cannot leak into them. From that export the PEP 517 hooks of
`setuptools.build_meta` build the sdist, and the wheel is built from the *unpacked sdist* (as
`python -m build` does), which also shows the sdist is complete. `SOURCE_DATE_EPOCH` is the
commit's committer time (spec §8.2 step 3). The backend runs in a fresh virtual environment with
`setuptools` at `--setuptools` (default `SETUPTOOLS`), recorded, because `pyproject.toml`'s
`setuptools>=78.1.1` admits any later version and the artifacts' bytes depend on it.

**What is checked** (each a named check in the record; exit 0 iff all pass):

- `a43.sdist_contents`, `a43.wheel_contents`: every member is classified as package code,
  runtime data, licence or metadata, and nothing else is present. The package part is compared as
  a set with what the commit says it must be — every tracked `src/openflowsheet/**/*.py` plus
  every file `pyproject.toml`'s package-data patterns match — so a missing file fails as much as an
  extra one.
- `a43.bytes_equal_commit`: every package and runtime-data member, and `LICENSE` and `NOTICE`,
  equals the commit's bytes (the schemas and the two registered YAML files through the `_data/`
  links: T08 W4.2's byte-identity proof).
- `a43.requires_dist`: the wheel's and the sdist's `Requires-Dist` equal `pyproject.toml`'s
  dependencies and extras exactly; `a43.version`: `Version` equals `pyproject.toml`'s and the
  packaged `__version__`.
- `a43.two_builds`: the two builds' unpacked members are identical file by file (names and
  bytes); whether the archives' own bytes are equal is reported, not required (§9).
- `a31.licence_files`: `LICENSE` and `NOTICE` in both artifacts; `a31.no_casadi_bytes`: no member
  of either artifact belongs to a CasADi tree or is a compiled object.

    python scripts/t08_dist.py --out "$RUNNER_TEMP/dist" [--commit C] [--setuptools 84.0.0]

The record is `<out>/t08-a43-dist.json`; the artifacts of build 1 are copied to `<out>/dist/`.
"""

from __future__ import annotations

import argparse
import email.parser
import fnmatch
import hashlib
import io
import json
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import tomllib
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any, Final

ROOT: Final = Path(__file__).resolve().parent.parent
FORMAT: Final = "t08-a43-dist-v1"
PACKAGE: Final = "openflowsheet"
#: The build backend version the RC is built with (the newest on 2026-10-01, satisfying
#: `pyproject.toml`'s `setuptools>=78.1.1`).
SETUPTOOLS: Final = "84.0.0"
#: Licence files ADR 0006 D5.1 and mode A require in every distributed artifact.
LICENCE_FILES: Final = ("LICENSE", "NOTICE")
#: sdist members at the top of `<name>-<version>/` that are metadata (setuptools writes
#: `PKG-INFO` and `setup.cfg`; `pyproject.toml`, `README.md` and `MANIFEST.in` are its sources).
SDIST_METADATA: Final = frozenset(
    {"PKG-INFO", "setup.cfg", "pyproject.toml", "README.md", "MANIFEST.in"}
)
#: wheel `.dist-info` members that are metadata.
WHEEL_METADATA: Final = frozenset(
    {"METADATA", "WHEEL", "RECORD", "entry_points.txt", "top_level.txt"}
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git(*arguments: str, cwd: Path = ROOT) -> str:
    return subprocess.run(
        ["git", *arguments], cwd=cwd, capture_output=True, text=True, check=True
    ).stdout


# -- what the commit says the artifacts must contain ------------------------------------------


def pyproject(export: Path) -> dict[str, Any]:
    return tomllib.loads((export / "pyproject.toml").read_text(encoding="utf-8"))


def expected_requires_dist(project: dict[str, Any]) -> list[str]:
    """`Requires-Dist` as setuptools writes it from `[project]`: each dependency, then each
    extra's with its `extra == "<name>"` marker."""
    found = [str(requirement) for requirement in project.get("dependencies", [])]
    for extra, requirements in project.get("optional-dependencies", {}).items():
        found += [f'{requirement}; extra == "{extra}"' for requirement in requirements]
    return sorted(found)


def expected_package_files(export: Path, document: dict[str, Any]) -> dict[str, bytes]:
    """`openflowsheet/**` as the commit defines it: every tracked `.py` file under the package
    and every file a package-data pattern matches (following the `_data/` links), by path inside
    the package tree, with its bytes."""
    root = export / "src"
    found: dict[str, bytes] = {}
    for path in sorted((root / PACKAGE).rglob("*.py")):
        if "__pycache__" not in path.parts:
            found[path.relative_to(root).as_posix()] = path.read_bytes()
    package_data = document["tool"]["setuptools"].get("package-data", {})
    for package, patterns in package_data.items():
        base = root.joinpath(*package.split("."))
        for pattern in patterns:
            for path in sorted(base.glob(pattern)):
                if path.is_file():
                    found[path.relative_to(root).as_posix()] = path.read_bytes()
    return found


def is_runtime_data(member: str) -> bool:
    return member.startswith(f"{PACKAGE}/_data/")


# -- reading the artifacts --------------------------------------------------------------------


def sdist_members(path: Path) -> dict[str, bytes]:
    """The sdist's regular files by path below its `<name>-<version>/` directory. A link or any
    other non-regular member is returned under its name with `None`-like empty bytes and fails
    classification (an sdist of this project carries no links: the `_data/` links are resolved)."""
    members: dict[str, bytes] = {}
    with tarfile.open(path, "r:gz") as archive:
        for member in archive.getmembers():
            if member.isdir():
                continue
            name = PurePosixPath(member.name)
            relative = PurePosixPath(*name.parts[1:]).as_posix()
            if not member.isfile():
                members[f"<non-regular>/{relative}"] = b""
                continue
            handle = archive.extractfile(member)
            assert handle is not None
            members[relative] = handle.read()
    return members


def wheel_members(path: Path) -> dict[str, bytes]:
    with zipfile.ZipFile(path) as archive:
        return {
            info.filename: archive.read(info) for info in archive.infolist() if not info.is_dir()
        }


def metadata_fields(text: str) -> dict[str, list[str]]:
    message = email.parser.Parser().parsestr(text)
    fields: dict[str, list[str]] = {}
    for key, value in message.items():
        fields.setdefault(key, []).append(str(value))
    return fields


# -- classification ---------------------------------------------------------------------------


def classify_sdist(member: str) -> str | None:
    if member in LICENCE_FILES:
        return "licence"
    if member in SDIST_METADATA or member.startswith(f"src/{PACKAGE}.egg-info/"):
        return "metadata"
    if member.startswith(f"src/{PACKAGE}/"):
        return "runtime_data" if is_runtime_data(member[len("src/") :]) else "package"
    return None


def classify_wheel(member: str, dist_info: str) -> str | None:
    if member in {f"{dist_info}/licenses/{name}" for name in LICENCE_FILES}:
        return "licence"
    if member.startswith(f"{dist_info}/") and member[len(dist_info) + 1 :] in WHEEL_METADATA:
        return "metadata"
    if member.startswith(f"{PACKAGE}/"):
        return "runtime_data" if is_runtime_data(member) else "package"
    return None


def is_casadi_or_compiled(member: str) -> bool:
    parts = PurePosixPath(member).parts
    name = parts[-1] if parts else member
    return (
        "casadi" in (part.lower() for part in parts)
        or fnmatch.fnmatch(name, "*.so")
        or fnmatch.fnmatch(name, "*.so.*")
        or name.endswith((".whl", ".a", ".dylib", ".dll", ".pyd"))
    )


# -- one build --------------------------------------------------------------------------------


def build_environment(directory: Path, setuptools: str) -> tuple[Path, str]:
    subprocess.run([sys.executable, "-m", "venv", str(directory)], check=True)
    python = directory / "bin" / "python"
    subprocess.run(
        [str(python), "-m", "pip", "install", "--quiet", f"setuptools=={setuptools}"],
        check=True,
    )
    version = subprocess.run(
        [str(python), "-c", "import setuptools; print(setuptools.__version__)"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    return python, version


def export_commit(commit: str, directory: Path) -> None:
    directory.mkdir(parents=True)
    archive = subprocess.run(
        ["git", "archive", "--format=tar", commit], cwd=ROOT, capture_output=True, check=True
    ).stdout
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        tar.extractall(directory, filter="tar")


def run_hook(python: Path, hook: str, source: Path, out: Path, epoch: str) -> Path:
    script = f"import setuptools.build_meta as b; print(b.{hook}({str(out)!r}))"
    environment = {**os.environ, "SOURCE_DATE_EPOCH": epoch}
    completed = subprocess.run(
        [str(python), "-c", script],
        cwd=source,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"{hook} failed:\n{completed.stdout[-3000:]}\n{completed.stderr[-3000:]}"
        )
    return out / completed.stdout.strip().splitlines()[-1]


def build_once(python: Path, commit: str, work: Path, epoch: str) -> dict[str, Path]:
    export = work / "export"
    export_commit(commit, export)
    out = work / "out"
    out.mkdir()
    sdist = run_hook(python, "build_sdist", export, out, epoch)
    unpacked = work / "unpacked"
    unpacked.mkdir()
    with tarfile.open(sdist, "r:gz") as tar:
        tar.extractall(unpacked, filter="data")
    (source,) = list(unpacked.iterdir())
    wheel = run_hook(python, "build_wheel", source, out, epoch)
    return {"export": export, "sdist": sdist, "wheel": wheel}


# -- the checks -------------------------------------------------------------------------------


def check(record: list[dict[str, Any]], check_id: str, passed: bool, **details: Any) -> None:
    record.append({"id": check_id, "result": "pass" if passed else "fail", **details})


def inspect(build: dict[str, Path], checks: list[dict[str, Any]]) -> dict[str, Any]:
    """Run every content check on one build; return its member digests for the comparison."""
    export = build["export"]
    document = pyproject(export)
    project = document["project"]
    expected = expected_package_files(export, document)
    sdist = sdist_members(build["sdist"])
    wheel = wheel_members(build["wheel"])
    dist_info = f"{PACKAGE}-{project['version']}.dist-info"

    sdist_classes = {member: classify_sdist(member) for member in sdist}
    wheel_classes = {member: classify_wheel(member, dist_info) for member in wheel}
    sdist_package = {
        m[len("src/") :] for m, c in sdist_classes.items() if c in ("package", "runtime_data")
    }
    wheel_package = {m for m, c in wheel_classes.items() if c in ("package", "runtime_data")}
    for kind, classes, package in (
        ("sdist", sdist_classes, sdist_package),
        ("wheel", wheel_classes, wheel_package),
    ):
        unclassified = sorted(member for member, value in classes.items() if value is None)
        missing = sorted(set(expected) - package)
        extra = sorted(package - set(expected))
        check(
            checks,
            f"a43.{kind}_contents",
            not unclassified and not missing and not extra,
            members=len(classes),
            by_class={
                name: sum(1 for value in classes.values() if value == name)
                for name in ("package", "runtime_data", "licence", "metadata")
            },
            unclassified=unclassified,
            missing=missing,
            extra=extra,
        )

    differing = sorted(
        [
            f"sdist:src/{m}"
            for m in sdist_package & set(expected)
            if sdist[f"src/{m}"] != expected[m]
        ]
        + [f"wheel:{m}" for m in wheel_package & set(expected) if wheel[m] != expected[m]]
        + [
            f"{kind}:{name}"
            for name in LICENCE_FILES
            for kind, members, member in (
                ("sdist", sdist, name),
                ("wheel", wheel, f"{dist_info}/licenses/{name}"),
            )
            if member in members and members[member] != (export / name).read_bytes()
        ]
    )
    data = sorted(member for member in wheel_package if is_runtime_data(member))
    check(
        checks,
        "a43.bytes_equal_commit",
        not differing and bool(data),
        differing=differing,
        runtime_data={member: sha256(wheel[member]) for member in data},
    )

    wanted = expected_requires_dist(project)
    wheel_meta = metadata_fields(wheel[f"{dist_info}/METADATA"].decode("utf-8"))
    sdist_meta = metadata_fields(sdist["PKG-INFO"].decode("utf-8"))
    found = {
        "wheel": sorted(wheel_meta.get("Requires-Dist", [])),
        "sdist": sorted(sdist_meta.get("Requires-Dist", [])),
    }
    check(
        checks,
        "a43.requires_dist",
        found["wheel"] == wanted and found["sdist"] == wanted,
        expected=wanted,
        found=found,
    )
    init = wheel[f"{PACKAGE}/__init__.py"].decode("utf-8")
    versions = {
        "pyproject": project["version"],
        "wheel_metadata": wheel_meta.get("Version", [""])[0],
        "sdist_metadata": sdist_meta.get("Version", [""])[0],
        "__version__": next(
            (
                line.split("=", 1)[1].strip().strip("\"'")
                for line in init.splitlines()
                if line.startswith("__version__")
            ),
            "",
        ),
    }
    check(checks, "a43.version", len(set(versions.values())) == 1, versions=versions)

    check(
        checks,
        "a31.licence_files",
        all(name in sdist for name in LICENCE_FILES)
        and all(f"{dist_info}/licenses/{name}" in wheel for name in LICENCE_FILES),
    )
    compiled = sorted(
        [f"sdist:{m}" for m in sdist if is_casadi_or_compiled(m)]
        + [f"wheel:{m}" for m in wheel if is_casadi_or_compiled(m)]
    )
    check(checks, "a31.no_casadi_bytes", not compiled, found=compiled)

    return {
        "sdist": {m: sha256(b) for m, b in sorted(sdist.items())},
        "wheel": {m: sha256(b) for m, b in sorted(wheel.items())},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--commit", default="HEAD")
    parser.add_argument("--setuptools", default=SETUPTOOLS)
    arguments = parser.parse_args()

    out: Path = arguments.out.resolve()
    if out.exists() and any(out.iterdir()):
        parser.error(f"{out} is not empty")
    out.mkdir(parents=True, exist_ok=True)
    commit = git("rev-parse", f"{arguments.commit}^{{commit}}").strip()
    epoch = git("log", "-1", "--format=%ct", commit).strip()
    python, setuptools = build_environment(out / "build-env", arguments.setuptools)

    builds = [build_once(python, commit, out / f"build{n}", epoch) for n in (1, 2)]
    checks: list[dict[str, Any]] = []
    digests = [inspect(build, checks if n == 0 else []) for n, build in enumerate(builds)]
    differences = {
        kind: sorted(
            name
            for name in set(digests[0][kind]) | set(digests[1][kind])
            if digests[0][kind].get(name) != digests[1][kind].get(name)
        )
        for kind in ("sdist", "wheel")
    }
    archives = [
        {
            kind: {
                "file": build[kind].name,
                "bytes": build[kind].stat().st_size,
                "sha256": sha256(build[kind].read_bytes()),
            }
            for kind in ("sdist", "wheel")
        }
        for build in builds
    ]
    check(
        checks,
        "a43.two_builds",
        not differences["sdist"] and not differences["wheel"],
        differing_members=differences,
        archive_bytes_equal={
            kind: archives[0][kind]["sha256"] == archives[1][kind]["sha256"]
            for kind in ("sdist", "wheel")
        },
    )

    dist = out / "dist"
    dist.mkdir()
    for kind in ("sdist", "wheel"):
        shutil.copy2(builds[0][kind], dist / builds[0][kind].name)
    lock = ROOT / "requirements.lock"
    record = {
        "format": FORMAT,
        "commit": commit,
        "tree_clean": git("status", "--porcelain").strip() == "",
        "environment_lock_sha256": sha256(lock.read_bytes()),
        "source_date_epoch": int(epoch),
        "machine": platform.machine(),
        "python": platform.python_version(),
        "setuptools": setuptools,
        "builds": archives,
        "members": {kind: digests[0][kind] for kind in ("sdist", "wheel")},
        "checks": checks,
        "passed": all(entry["result"] == "pass" for entry in checks),
    }
    (out / "t08-a43-dist.json").write_text(
        json.dumps(record, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    for entry in checks:
        print(f"{entry['result'].upper():4} {entry['id']}")
    for n, archive in enumerate(archives, 1):
        for kind in ("sdist", "wheel"):
            print(
                f"build {n} {kind}: {archive[kind]['file']} {archive[kind]['bytes']} bytes "
                f"sha256 {archive[kind]['sha256']}"
            )
    print(f"T08.A43: {'PASS' if record['passed'] else 'FAIL'} ({out / 't08-a43-dist.json'})")
    return 0 if record["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
