"""RC step 12's store-keeping wrappers and G11's collector (RP §6.4; R-909 A3-3, R-375, R-348).

Promoted unchanged in behaviour from 0.2.0's `evidence/M07/ce993651…/tools/g11keep.py.txt`,
`g11collect.py.txt` and `g12keep.py.txt` (run again by 0.3.0, `evidence/S13/a3e508e3…/tools/`), so
that the standing RC job (`scripts/release_rc.py`) runs a tracked script. The changes are in
packaging only: one script with three subcommands, the benchmark scripts found from this file's
checkout rather than the working directory, and the collected record's `description` naming this
script. Each benchmark script runs exactly as at C.

    python scripts/m07_rc_keep.py g11 <keep-dir> <g11_coverage_v3.py arguments...>
    python scripts/m07_rc_keep.py g11-collect <keep-dir> <runs.json> <out-dir>
    python scripts/m07_rc_keep.py g12 <keep-dir> <g12_real_loop.py arguments...>

**g12** runs `benchmarks/m02/g12_real_loop.py` with only the module's own `tempfile` name replaced,
by a shim whose `TemporaryDirectory(prefix=...)` makes `<keep-dir>/<prefix><n>` and does not
remove it, so that step 10 audits the certificates G12 emitted (R-348).

**g11** runs `benchmarks/m02/g11_coverage_v3.py` the same way, keeping each point's scratch
directory at `<keep-dir>/<run>/<prefix>` (W21 (e), R-375). G11 maps its points over a `spawn`
process pool, so: every worker re-runs this file as `__mp_main__` before it unpickles a point,
and the same shim is installed there (the module loaded under the same name, the keep directory
taken from the environment); and the module's `ProcessPoolExecutor` name is replaced by a
subclass that only sets `<run>` (`run1`, `run2`, ...) in the environment before its workers start,
and `after-runs` when the pool closes, so each run's points and the timing repeats land apart.

**g11-collect** writes, for run k (`<keep-dir>/run<k>/`, the k-th entry of `<runs.json>`),
`<out-dir>/g11-experiments-run<k>.json` (format `m07-g11-experiments-v1`): the RC provenance
block (`t08_rc.provenance()` and `machine_class()`), and for each point of the run, in the run's
order, its label, its path (`boundary` or `direct`) and, for a boundary point, every experiment of
its store (`records/experiments/<xx>/<key>/`): `request.json`, `result.json` (null when absent)
and `attempts/<n>.json` in attempt order, embedded as parsed, with each file's SHA-256. A direct
point evaluates without a store and has `experiments` null. Exits 1 if a run's points and its kept
directories differ.
"""

from __future__ import annotations

import hashlib
import importlib.util
import itertools
import json
import os
import sys
import types
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
G11 = ROOT / "benchmarks" / "m02" / "g11_coverage_v3.py"
G12 = ROOT / "benchmarks" / "m02" / "g12_real_loop.py"
#: The environment that carries G11's keep directory and current run into the spawn workers.
KEEP = "OPENFLOWSHEET_G11KEEP_DIR"
RUN = "OPENFLOWSHEET_G11KEEP_RUN"
#: G11's point scratch-directory prefix (`g11_coverage_v3.py`'s `TemporaryDirectory(prefix=...)`).
PREFIX = "m02-g11v3-"
FORMAT = "m07-g11-experiments-v1"
USAGE = __doc__.split("\n\n")[1] if __doc__ else ""


def _load(script: Path, name: str) -> types.ModuleType:
    spec = importlib.util.spec_from_file_location(name, script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# -- g11 ------------------------------------------------------------------------------------------


class _G11Kept:
    def __init__(self, prefix: str = "tmp", **_: object) -> None:
        self.name = str(Path(os.environ[KEEP]) / os.environ[RUN] / prefix.rstrip("-"))
        Path(self.name).mkdir(parents=True, exist_ok=False)

    def __enter__(self) -> str:
        return self.name

    def __exit__(self, *_: object) -> None:
        return None


class _Runs(ProcessPoolExecutor):
    runs = 0

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        _Runs.runs += 1
        os.environ[RUN] = f"run{_Runs.runs}"
        super().__init__(*args, **kwargs)

    def __exit__(self, *args: Any) -> Any:
        try:
            return super().__exit__(*args)
        finally:
            os.environ[RUN] = "after-runs"


def _install_g11() -> types.ModuleType:
    module = _load(G11, "g11_coverage_v3")
    module.tempfile = types.SimpleNamespace(TemporaryDirectory=_G11Kept)  # type: ignore[attr-defined]
    module.ProcessPoolExecutor = _Runs  # type: ignore[attr-defined]
    return module


if __name__ == "__mp_main__" and KEEP in os.environ:  # a spawn worker of `g11`
    _install_g11()


def g11(keep: Path, arguments: list[str]) -> int:
    os.environ[KEEP] = str(keep.resolve())
    os.environ[RUN] = "before-runs"
    module = _install_g11()
    sys.argv = [str(G11), *arguments]
    return int(module.main())


# -- g12 ------------------------------------------------------------------------------------------


def g12(keep: Path, arguments: list[str]) -> int:
    root = keep.resolve()
    counter = itertools.count()

    class _Kept:
        def __init__(self, prefix: str = "tmp", **_: object) -> None:
            self.name = str(root / f"{prefix}{next(counter)}")
            Path(self.name).mkdir(parents=True, exist_ok=False)

        def __enter__(self) -> str:
            return self.name

        def __exit__(self, *_: object) -> None:
            return None

    module = _load(G12, "g12_real_loop")
    module.tempfile = types.SimpleNamespace(TemporaryDirectory=_Kept)  # type: ignore[attr-defined]
    sys.argv = [str(G12), *arguments]
    return int(module.main())


# -- g11-collect ----------------------------------------------------------------------------------


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def experiment(directory: Path, store: Path) -> dict[str, Any]:
    """One experiment of a point's store: its files' SHA-256 and the files embedded as parsed."""
    names = ["request.json", "result.json"] + [
        f"attempts/{p.name}"
        for p in sorted((directory / "attempts").glob("*.json"), key=lambda p: int(p.stem))
    ]
    files = {
        (directory / name).relative_to(store).as_posix(): _sha256(directory / name)
        for name in names
        if (directory / name).is_file()
    }
    result = directory / "result.json"
    return {
        "experiment_key": directory.name,
        "files": files,
        "request": json.loads((directory / "request.json").read_text(encoding="utf-8")),
        "result": json.loads(result.read_text(encoding="utf-8")) if result.is_file() else None,
        "attempts": [
            json.loads((directory / name).read_text(encoding="utf-8"))
            for name in names
            if name.startswith("attempts/")
        ],
    }


def collect(keep: Path, runs_path: Path, out: Path, provenance: dict[str, Any]) -> int:
    runs = json.loads(runs_path.read_text(encoding="utf-8"))
    out.mkdir(parents=True, exist_ok=True)
    status = 0
    for k, run in enumerate(runs, start=1):
        root = keep / f"run{k}"
        kept = (
            {p.name[len(PREFIX) :] for p in root.iterdir() if p.is_dir()}
            if root.is_dir()
            else set()
        )
        labels = [p["label"] for p in run]
        if kept != set(labels) or len(labels) != len(set(labels)):
            print(f"run {k}: kept {len(kept)} directories, run has {len(labels)} points")
            status = 1
            continue
        points = []
        for point in run:
            entry: dict[str, Any] = {"label": point["label"], "path": point["path"]}
            if point["path"] == "boundary":
                store = root / f"{PREFIX}{point['label']}" / "records"
                entry["experiments"] = [
                    experiment(d, store)
                    for d in sorted((store / "experiments").glob("??/*"))
                    if (d / "request.json").is_file()
                ]
            else:
                entry["experiments"] = None
            points.append(entry)
        record = {
            "format": FORMAT,
            "description": "G11's experiment records of one run at C, kept and collected by "
            "scripts/m07_rc_keep.py (W21 (e), R-375, RP §6.4)",
            "provenance": provenance,
            "run": k,
            "runs_file_sha256": _sha256(runs_path),
            "points": points,
        }
        target = out / f"g11-experiments-run{k}.json"
        target.write_text(json.dumps(record, indent=1, ensure_ascii=False) + "\n", "utf-8")
        boundary = [p for p in points if p["experiments"] is not None]
        print(
            f"run {k}: {len(points)} points, {len(boundary)} boundary, "
            f"{sum(len(p['experiments']) for p in boundary)} experiments, "
            f"{target.stat().st_size} bytes"
        )
    return status


def _rc_provenance() -> dict[str, Any]:
    sys.path.insert(0, str(ROOT / "scripts"))
    import t08_rc  # noqa: PLC0415

    return {**t08_rc.provenance(), "machine_class": t08_rc.machine_class()}


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    command = arguments[0] if arguments else ""
    if command in ("g11", "g12") and len(arguments) >= 2:
        run = g11 if command == "g11" else g12
        return run(Path(arguments[1]), arguments[2:])
    if command == "g11-collect" and len(arguments) == 4:
        keep, runs, out = (Path(p).resolve() for p in arguments[1:])
        return collect(keep, runs, out, _rc_provenance())
    print(USAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
