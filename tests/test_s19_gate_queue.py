"""S19 gate queue: `enqueue --batch` refuses a head that contains the batch's close K.

Review R-W5-N-close item 4d. `scripts/w5_gate.py close` records K in
`<queue>/batches/closed-<B>.json`; `gate_queue.py enqueue --batch` then refuses (exit 2, nothing
queued) a job whose head contains K, and accepts the same job without --batch. Every run here
uses a temporary git repository and a temporary queue directory, never the real queue.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import w5_gate  # noqa: E402

QUEUE_SCRIPT = ROOT / ".claude" / "skills" / "s19-refactor" / "gate_queue.py"

#: X07a platform limit (docs/X07a_DECISIONS.md, platform-limit table): the gate queue takes its
#: locks with `fcntl` (POSIX only); it runs on the Linux gate host. Run 44945609131, 3 errors.
pytestmark = pytest.mark.skipif(
    sys.platform == "win32", reason="the S19 gate queue locks with fcntl: POSIX only"
)


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("s19_gate_queue_under_test", QUEUE_SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Repository:
    """A temporary git repository: B, then K and its child H on one line, S beside K."""

    def __init__(self, path: Path) -> None:
        self.path = path
        path.mkdir()
        self.git("init", "-q", "-b", "main")
        self.base = self.commit("b")
        self.k = self.commit("k")
        self.head = self.commit("h")
        self.git("checkout", "-q", "-b", "side", self.base)
        self.side = self.commit("s")
        self.git("checkout", "-q", "main")

    def git(self, *arguments: str) -> str:
        done = subprocess.run(
            ["git", "-c", "user.name=t", "-c", "user.email=t@t", *arguments],
            cwd=self.path,
            check=True,
            capture_output=True,
            text=True,
        )
        return done.stdout.strip()

    def commit(self, name: str) -> str:
        (self.path / f"{name}.txt").write_text(f"{name}\n")
        self.git("add", f"{name}.txt")
        self.git("commit", "-q", "-m", name)
        return self.git("rev-parse", "HEAD")


@pytest.fixture
def setup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[ModuleType, Repository, Path]:
    """The queue module pointed at a temporary repository and queue; `w5_batch` (the worktree's
    `w5_gate.py validate`) replaced by a stub that leaves a candidate copy as the real one does."""
    queue_module = _load()
    repository = Repository(tmp_path / "repo")
    queue = tmp_path / "queue"
    common = Path(repository.git("rev-parse", "--path-format=absolute", "--git-common-dir"))
    monkeypatch.setattr(queue_module, "COMMON", common)
    monkeypatch.setattr(queue_module, "QUEUE", queue)
    for name in ("pending", "running", "done", "batches"):
        monkeypatch.setattr(queue_module, name.upper(), queue / name)

    def w5_batch(worktree: Path, source: str, head: str) -> tuple[Path, str, str]:
        copy = queue / "batches" / f".stub-{Path(source).name}.tmp"
        copy.write_text(Path(source).read_text())
        return copy, "a" * 64, repository.base

    monkeypatch.setattr(queue_module, "w5_batch", w5_batch)
    return queue_module, repository, queue


def _enqueue(
    queue_module: ModuleType, repository: Repository, label: str, head: str, batch: Path | None
) -> int:
    argv = ["enqueue", "--worktree", str(repository.path), "--base", repository.base]
    argv += ["--mode", "merge-check", "--label", label, "--head", head]
    result: int = queue_module.main([*argv, *(["--batch", str(batch)] if batch else [])])
    return result


def _pending(queue: Path) -> list[dict[str, Any]]:
    return [json.loads(path.read_text()) for path in sorted((queue / "pending").glob("*.json"))]


def test_a_batch_job_on_a_head_that_contains_k_is_refused(
    setup: tuple[ModuleType, Repository, Path], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    queue_module, repository, queue = setup
    batch = tmp_path / "n.json"
    batch.write_text(json.dumps({"batch": "N", "base": repository.base}))
    # before the close, the batch job on H is queued
    assert _enqueue(queue_module, repository, "before", repository.head, batch) == 0
    assert [job["label"] for job in _pending(queue)] == ["before"]
    record = w5_gate.record_close(
        queue, {"batch": "N", "base": repository.base}, repository.k, "a" * 64, []
    )
    assert record == queue / "batches" / f"closed-{repository.base}.json"
    capsys.readouterr()
    for label, head in (("on-k", repository.k), ("after-k", repository.head)):
        with pytest.raises(SystemExit) as refused:
            _enqueue(queue_module, repository, label, head, batch)
        assert refused.value.code == 2
        assert capsys.readouterr().err.strip() == (
            f"W5 batch REFUSED: batch base {repository.base[:10]} closed at K "
            f"{repository.k[:10]}, which the head {head[:10]} contains: gate it without --batch"
        )
    # nothing queued, no candidate copy left behind, the sequence number not taken
    assert [job["label"] for job in _pending(queue)] == ["before"]
    assert sorted(path.name for path in (queue / "batches").iterdir()) == [
        "000001-before.json",
        record.name,
    ]
    assert (queue / "seq").read_text() == "1\n"


def test_without_batch_or_on_a_head_without_k_it_is_accepted(
    setup: tuple[ModuleType, Repository, Path], tmp_path: Path
) -> None:
    queue_module, repository, queue = setup
    batch = tmp_path / "n.json"
    batch.write_text(json.dumps({"batch": "N", "base": repository.base}))
    w5_gate.record_close(queue, {"batch": "N", "base": repository.base}, repository.k, "a", [])
    assert _enqueue(queue_module, repository, "k-merge-check", repository.k, None) == 0
    assert _enqueue(queue_module, repository, "beside-k", repository.side, batch) == 0
    jobs = {job["label"]: job for job in _pending(queue)}
    assert jobs["k-merge-check"]["batch"] is None
    assert jobs["k-merge-check"]["head"] == repository.k
    assert jobs["beside-k"]["batch_base"] == repository.base
    assert jobs["beside-k"]["head"] == repository.side


def test_an_unreadable_close_record_refuses(
    setup: tuple[ModuleType, Repository, Path], tmp_path: Path
) -> None:
    queue_module, repository, queue = setup
    batch = tmp_path / "n.json"
    batch.write_text(json.dumps({"batch": "N", "base": repository.base}))
    (queue / "batches").mkdir(parents=True)
    (queue / "batches" / f"closed-{repository.base}.json").write_text("{}")
    with pytest.raises(SystemExit) as refused:
        _enqueue(queue_module, repository, "x", repository.head, batch)
    assert refused.value.code == 2
    assert _pending(queue) == []
    assert [path.name for path in (queue / "batches").iterdir()] == [
        f"closed-{repository.base}.json"
    ]
