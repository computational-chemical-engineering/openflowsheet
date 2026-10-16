"""Build and verify the pinned reactor environment from pins (M02 design note §2.4; ADR 0033 D1).

    python -m openflowsheet.adapters.pymrm.env build --variant <id> [--source <clone>]
    python -m openflowsheet.adapters.pymrm.env verify --variant <id>
    python -m openflowsheet.adapters.pymrm.env lock --freeze <pip freeze> --out <lock>

`build` makes `<external root>/<env id>/` (`$OPENFLOWSHEET_EXTERNAL_ROOT`, default
`$XDG_CACHE_HOME/openflowsheet/external`), outside any repository, from what the variant pins:

1. A fresh clone of the variant's repository checked out at the pinned commit (or `--source`, a
   clone that must be clean with `HEAD` at the pin; it is not modified).
2. `git archive` of the commit into `export/`; its tree hash — SHA-256 of the canonical JSON
   list of `[relative path, file SHA-256]` sorted by path — into `export/EXPORT_TREE_SHA256`. The
   licence notice's SHA-256 must equal the variant's.
3. `merged-database.json`: the export's species database with M01's overlay rows
   (`benchmarks/m01/reactor-overlay.json`, its SHA-256 checked against the variant), exactly as
   `benchmarks/m01/reactor_probe.py:merged_database(clone_db, overlay, "N2")` makes it.
4. A venv of the variant's Python (another version only with `--allow-python-mismatch`), into
   which `pip install --require-hashes --no-deps -r reactor-env.lock` installs exactly the lock.
   The reactor package is **not** installed; the child imports it from the export.
5. The export, the database, the lock copy and the venv's `site-packages` made read-only, and
   `env-manifest.json`: `{variant_id, commit, export_tree_sha256, merged_database_sha256,
   lock_sha256, python, packages, licence_notice_sha256, created_at}` (`created_at` is outside
   every hash).

It builds in a sibling directory and renames it into place only when every step passed; an
existing environment is never overwritten. `verify` recomputes 2-5 and exits non-zero on any
difference. The application never builds an environment: a missing one is
`environment_unavailable` with this command in the message.

**The reactor's code is used by reference and never vendored**: nothing here copies it into this
repository, and the environment lives outside it.

`lock` is the build lane's one-time step: from a `pip freeze` of a resolution of the pinned
reactor (its `[test]` extra, as `reactor_probe.py`'s environment was made), it writes the
hash-pinned lock with every file hash PyPI publishes for each pinned version.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from importlib.resources import files
from pathlib import Path
from typing import Any, Final

from openflowsheet.adapters.experiments.backends import external_root
from openflowsheet.adapters.variants import Variant, registered_variant
from openflowsheet.canonical import canonical_json, file_sha256

__all__ = [
    "LOCK_FILE",
    "build",
    "environment_root",
    "locked_versions",
    "merged_database",
    "packaged_lock",
    "tree_sha256",
    "verify",
]

#: The environment's layout; `child.py` holds the same names as literals (a test asserts it).
EXPORT_DIR: Final = "export"
EXPORT_TREE_FILE: Final = "EXPORT_TREE_SHA256"
DATABASE_FILE: Final = "merged-database.json"
LOCK_FILE: Final = "reactor-env.lock"
MANIFEST_FILE: Final = "env-manifest.json"
VENV_DIR: Final = "venv"
#: The export's species database and licence notice, relative to the export.
CLONE_DATABASE: Final = Path("src/reactor/data/properties_database.json")
LICENCE_NOTICE: Final = Path("LICENSE")
#: Where the overlay is read from in a checkout of this repository (`--overlay` overrides).
OVERLAY: Final = Path("benchmarks/m01/reactor-overlay.json")
PYPI_JSON: Final = "https://pypi.org/pypi/{name}/{version}/json"


class EnvironmentBuildError(RuntimeError):
    """A pin that the source, the overlay, the interpreter or the result does not satisfy."""


def packaged_lock() -> Path:
    """The hash-pinned lock this package ships beside the child."""
    return Path(str(files("openflowsheet.adapters") / "pymrm" / LOCK_FILE))


def environment_root(variant: Variant, base: Path | None = None) -> Path:
    return (base if base is not None else external_root()) / str(
        variant.evaluation["environment"]["env_id"]
    )


def tree_sha256(root: Path) -> str:
    """SHA-256 of the canonical JSON (ADR 0002) list of `[relative path, file SHA-256]` of every
    file under `root`, sorted by path, `EXPORT_TREE_SHA256` itself excluded."""
    entries = sorted(
        [path.relative_to(root).as_posix(), file_sha256(path)]
        for path in root.rglob("*")
        if path.is_file() and path.relative_to(root).as_posix() != EXPORT_TREE_FILE
    )
    return hashlib.sha256(canonical_json(entries)).hexdigest()


def merged_database(clone_db: Path, overlay: Path) -> dict[str, Any]:
    """The pinned database plus M01's overlay rows: `reactor_probe.merged_database(..., "N2")`
    (M01 spec §8.6). The group's numbers are read from the export, never copied here."""
    database: dict[str, Any] = json.loads(clone_db.read_text(encoding="utf-8"))
    rows = json.loads(overlay.read_text(encoding="utf-8"))
    species = database["species_properties"]["data"]
    for name, row in rows["species_properties"].items():
        new = {key: value for key, value in row.items() if key != "copy_from"}
        source = row["copy_from"]["row"]
        for column in row["copy_from"]["columns"]:
            new[column] = species[source][column]
        species[name] = new
    binaries = database["binary_properties"]["data"]
    for pair, row in rows["binary_properties"].items():
        binaries[pair] = dict(binaries[row["copy_from"]])
    return database


def _normalized(name: str) -> str:
    return name.lower().replace("_", "-").replace(".", "-")


def locked_versions(text: str) -> dict[str, str]:
    """`name -> version` of every `name==version` requirement of a lock (or a `pip freeze`)."""
    found: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith(("#", "--", "-e")):
            continue
        name, separator, version = line.split()[0].partition("==")
        if separator:
            found[_normalized(name)] = version
    return found


def _run(command: Sequence[str], **kwargs: Any) -> str:
    completed = subprocess.run(list(command), capture_output=True, text=True, **kwargs)
    if completed.returncode != 0:
        raise EnvironmentBuildError(
            f"{' '.join(command)} exited {completed.returncode}: {completed.stderr.strip()[-2000:]}"
        )
    return str(completed.stdout)


def _checked_clone(clone: Path, commit: str) -> None:
    head = _run(["git", "-C", str(clone), "rev-parse", "HEAD"]).strip()
    dirty = _run(["git", "-C", str(clone), "status", "--porcelain"]).strip()
    if head != commit or dirty:
        raise EnvironmentBuildError(
            f"clone {clone} is at {head} (dirty={bool(dirty)}); a clean clone at {commit} is needed"
        )


def _export(clone: Path, commit: str, target: Path) -> None:
    target.mkdir(parents=True)
    with tempfile.TemporaryFile() as archive:
        completed = subprocess.run(
            ["git", "-C", str(clone), "archive", "--format=tar", commit],
            stdout=archive,
            stderr=subprocess.PIPE,
        )
        if completed.returncode != 0:
            raise EnvironmentBuildError(f"git archive failed: {completed.stderr.decode()[-2000:]}")
        archive.seek(0)
        with tarfile.open(fileobj=archive) as tar:
            tar.extractall(target, filter="data")


def _read_only(path: Path) -> None:
    """Remove every write bit under `path` (files and directories)."""
    paths = [path, *path.rglob("*")] if path.is_dir() else [path]
    for item in sorted(paths, reverse=True):  # children before their directory
        if item.is_symlink():
            continue
        mode = item.stat().st_mode
        item.chmod(mode & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))


def _venv_python(root: Path) -> Path:
    return root / VENV_DIR / "bin" / "python"


def _site_packages(root: Path) -> Path:
    found = sorted((root / VENV_DIR / "lib").glob("python*/site-packages"))
    if len(found) != 1:
        raise EnvironmentBuildError(f"no single site-packages under {root / VENV_DIR}")
    return found[0]


def _python_version(python: Path) -> str:
    return _run([str(python), "-c", "import platform; print(platform.python_version())"]).strip()


def _freeze(python: Path) -> dict[str, str]:
    return locked_versions(_run([str(python), "-m", "pip", "freeze", "--all"]))


def build(
    variant: Variant,
    *,
    source: Path | None = None,
    overlay: Path = OVERLAY,
    python: Path | None = None,
    allow_python_mismatch: bool = False,
    base: Path | None = None,
) -> Path:
    """Build the variant's environment (module docstring); return its root."""
    if variant.kind != "out_of_process":
        raise EnvironmentBuildError(f"{variant.variant_id} is not an out-of-process variant")
    evaluation = variant.evaluation
    reactor, pinned = evaluation["reactor"], evaluation["environment"]
    commit = str(reactor["commit"])
    root = environment_root(variant, base)
    if root.exists():
        raise EnvironmentBuildError(f"{root} exists; `verify` it, or remove it to rebuild")
    lock = packaged_lock()
    if file_sha256(lock) != pinned["lock_sha256"]:
        raise EnvironmentBuildError(f"{lock} does not hash to the variant's lock_sha256")
    if file_sha256(overlay) != evaluation["overlay_sha256"]:
        raise EnvironmentBuildError(f"{overlay} does not hash to the variant's overlay_sha256")
    interpreter = Path(python) if python is not None else Path(sys.executable)
    version = _python_version(interpreter)
    if version != pinned["python"] and not allow_python_mismatch:
        raise EnvironmentBuildError(
            f"{interpreter} is Python {version}; the variant pins {pinned['python']} "
            "(--allow-python-mismatch builds anyway, with another fingerprint)"
        )
    root.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=f".{root.name}.partial-", dir=root.parent))
    built = False
    try:
        with tempfile.TemporaryDirectory(prefix="ofs-reactor-clone-") as scratch:
            if source is None:
                clone = Path(scratch) / "clone"
                _run(
                    ["git", "clone", "--quiet", "--no-checkout", reactor["repository"], str(clone)]
                )
                _run(["git", "-C", str(clone), "checkout", "--quiet", "--detach", commit])
            else:
                clone = source
            _checked_clone(clone, commit)
            export = stage / EXPORT_DIR
            _export(clone, commit, export)
            _checked_clone(clone, commit)
        tree = tree_sha256(export)
        (export / EXPORT_TREE_FILE).write_text(tree + "\n", encoding="utf-8")
        licence = file_sha256(export / LICENCE_NOTICE)
        if licence != reactor["licence_notice_sha256"]:
            raise EnvironmentBuildError(f"the export's {LICENCE_NOTICE} is not the variant's")
        database = stage / DATABASE_FILE
        merged = merged_database(export / CLONE_DATABASE, overlay)
        database.write_text(json.dumps(merged), encoding="utf-8")
        shutil.copyfile(lock, stage / LOCK_FILE)
        _run([str(interpreter), "-m", "venv", str(stage / VENV_DIR)])
        venv_python = _venv_python(stage)
        _run(
            [
                str(venv_python),
                "-m",
                "pip",
                "install",
                "--quiet",
                "--no-input",
                "--disable-pip-version-check",
                "--no-deps",
                "--require-hashes",
                "-r",
                str(stage / LOCK_FILE),
            ]
        )
        installed = _freeze(venv_python)
        expected = locked_versions(lock.read_text(encoding="utf-8"))
        missing = {
            name: version for name, version in expected.items() if installed.get(name) != version
        }
        if missing:
            raise EnvironmentBuildError(f"installed versions differ from the lock: {missing}")
        manifest = {
            "variant_id": variant.variant_id,
            "commit": commit,
            "export_tree_sha256": tree,
            "merged_database_sha256": file_sha256(database),
            "lock_sha256": pinned["lock_sha256"],
            "python": _python_version(venv_python),
            "packages": installed,
            "licence_notice_sha256": licence,
            "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
        }
        (stage / MANIFEST_FILE).write_text(json.dumps(manifest, indent=1) + "\n", encoding="utf-8")
        for path in (export, database, stage / LOCK_FILE, stage / MANIFEST_FILE):
            _read_only(path)
        _read_only(_site_packages(stage))
        stage.rename(root)
        built = True
    finally:
        if not built:  # a partial build never stays behind
            _remove(stage)
    differences = verify(variant, base=base, overlay=overlay)
    if differences:
        raise EnvironmentBuildError(f"the built environment does not verify: {differences}")
    return root


def _remove(path: Path) -> None:
    """Remove a partial build, read-only parts included."""
    if not path.exists():
        return
    for item in [path, *path.rglob("*")]:
        if not item.is_symlink():
            item.chmod(item.stat().st_mode | stat.S_IWUSR)
    shutil.rmtree(path)


def verify(variant: Variant, *, base: Path | None = None, overlay: Path | None = None) -> list[str]:
    """Every difference between the built environment and its pins (empty: it verifies)."""
    evaluation = variant.evaluation
    reactor, pinned = evaluation["reactor"], evaluation["environment"]
    root = environment_root(variant, base)
    manifest_path = root / MANIFEST_FILE
    if not manifest_path.is_file():
        return [f"no environment at {root}"]
    manifest: Mapping[str, Any] = json.loads(manifest_path.read_text(encoding="utf-8"))
    found: list[str] = []

    def expect(name: str, measured: Any, wanted: Any) -> None:
        if measured != wanted:
            found.append(f"{name}: {measured!r} != {wanted!r}")

    export = root / EXPORT_DIR
    tree = tree_sha256(export)
    expect("export tree", tree, manifest.get("export_tree_sha256"))
    marker = (export / EXPORT_TREE_FILE).read_text(encoding="utf-8").strip()
    expect("EXPORT_TREE_SHA256", marker, tree)
    expect("variant_id", manifest.get("variant_id"), variant.variant_id)
    expect("commit", manifest.get("commit"), reactor["commit"])
    expect("licence notice", file_sha256(export / LICENCE_NOTICE), reactor["licence_notice_sha256"])
    expect(
        "manifest licence", manifest.get("licence_notice_sha256"), reactor["licence_notice_sha256"]
    )
    expect("lock copy", file_sha256(root / LOCK_FILE), pinned["lock_sha256"])
    expect("packaged lock", file_sha256(packaged_lock()), pinned["lock_sha256"])
    expect("manifest lock", manifest.get("lock_sha256"), pinned["lock_sha256"])
    expect("database", file_sha256(root / DATABASE_FILE), manifest.get("merged_database_sha256"))
    if overlay is not None:
        rebuilt = json.dumps(merged_database(export / CLONE_DATABASE, overlay)).encode("utf-8")
        expect(
            "database rebuilt",
            hashlib.sha256(rebuilt).hexdigest(),
            manifest.get("merged_database_sha256"),
        )
    python = _venv_python(root)
    expect("python", _python_version(python), manifest.get("python"))
    installed = _freeze(python)
    expect("packages", installed, manifest.get("packages"))
    locked = locked_versions((root / LOCK_FILE).read_text(encoding="utf-8"))
    expect("locked packages", {name: installed.get(name) for name in locked}, locked)
    for path in (export, root / DATABASE_FILE, root / LOCK_FILE, _site_packages(root)):
        writable = [
            item
            for item in [path, *(path.rglob("*") if path.is_dir() else [])]
            if not item.is_symlink() and item.stat().st_mode & stat.S_IWUSR
        ]
        if writable:
            found.append(f"writable: {writable[0]} (+{len(writable) - 1})")
    return found


def _cpython313(filename: str) -> bool:
    """Whether a release file can install on CPython 3.13 (the variant's interpreter): an sdist,
    or a wheel tagged for `cp313`, for any `py3`, or for the stable ABI."""
    if not filename.endswith(".whl"):
        return filename.endswith((".tar.gz", ".zip"))
    python, abi = filename[: -len(".whl")].split("-")[-3:-1]
    tags = python.split(".")
    return "cp313" in tags or any(tag.startswith("py3") for tag in tags) or abi == "abi3"


def lock_from_freeze(freeze: str) -> str:
    """A hash-pinned lock: each `name==version` of `freeze` with the hash of every file PyPI
    publishes for that version that can install on CPython 3.13 (the build lane's one-time
    step)."""
    lines = [
        "# The pinned reactor environment (M02 design note §2.4): each distribution, its hashes.",
        "# Generated by `python -m openflowsheet.adapters.pymrm.env lock` from a pip freeze of the",
        "# resolution of ammonia_synthesis_reactor@6089593[test] (reactor_probe.py's recipe), not",
        "# edited by hand. Install: pip install --require-hashes --no-deps -r reactor-env.lock",
    ]
    for name, version in sorted(locked_versions(freeze).items()):
        with urllib.request.urlopen(PYPI_JSON.format(name=name, version=version)) as response:
            release = json.load(response)
        hashes = sorted(
            {item["digests"]["sha256"] for item in release["urls"] if _cpython313(item["filename"])}
        )
        if not hashes:
            raise EnvironmentBuildError(f"PyPI lists no files for {name}=={version}")
        lines.append(f"{name}=={version} \\")
        lines.extend(f"    --hash=sha256:{digest} \\" for digest in hashes[:-1])
        lines.append(f"    --hash=sha256:{hashes[-1]}")
    return "\n".join(lines) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m openflowsheet.adapters.pymrm.env")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("build", "verify"):
        command = commands.add_parser(name)
        command.add_argument("--variant", required=True)
        command.add_argument("--overlay", type=Path, default=OVERLAY)
        command.add_argument("--root", type=Path, default=None, help="the external root")
        if name == "build":
            command.add_argument("--source", type=Path, default=None)
            command.add_argument("--python", type=Path, default=None)
            command.add_argument("--allow-python-mismatch", action="store_true")
    lock = commands.add_parser("lock")
    lock.add_argument("--freeze", type=Path, required=True)
    lock.add_argument("--out", type=Path, required=True)
    arguments = parser.parse_args(argv)
    if arguments.command == "lock":
        arguments.out.write_text(lock_from_freeze(arguments.freeze.read_text("utf-8")), "utf-8")
        print(f"{arguments.out}: sha256 {file_sha256(arguments.out)}")
        return 0
    variant = registered_variant(arguments.variant)
    if arguments.command == "build":
        try:
            root = build(
                variant,
                source=arguments.source,
                overlay=arguments.overlay,
                python=arguments.python,
                allow_python_mismatch=arguments.allow_python_mismatch,
                base=arguments.root,
            )
        except EnvironmentBuildError as error:
            print(f"build refused: {error}", file=sys.stderr)
            return 1
        print(f"built {root}")
        return 0
    differences = verify(variant, base=arguments.root, overlay=arguments.overlay)
    for line in differences:
        print(line, file=sys.stderr)
    print("verified" if not differences else f"{len(differences)} difference(s)")
    return 0 if not differences else 1


if __name__ == "__main__":
    os.umask(0o022)
    raise SystemExit(main())
