"""The immutable `RunManifest`: what ran, in what, and what it is comparable with. K05.

Blueprint §8.3: "The RunManifest pins process, data, model, solver, scaling, backend,
dependency artifacts, platform, threads, seeds, and policies." ADR 0007 D6 says which
environment facts specifically, and why: so that a difference *within* the declared numerical
policy is **attributable** rather than mysterious. A run that differs from another and cannot
say which of the two environments moved is not evidence of anything.

**Timing is recorded and never hashed.** Blueprint D20 separates deterministic structural
artifacts from adaptive numerical decisions and timing, and plan §4.2's K05 acceptance says
"timing excluded from structural identity" in as many words. So `elapsed_seconds` lives on the
manifest, where a reader can see it, and `structural_sha256` is computed over a document that
has never contained it. The exclusion is a list, and a test walks the real document to check
that nothing outside the list reaches the hash.

**The thread count is part of the environment, not a footnote.** ADR 0007 D6: a differing
thread count is a differing environment, and replay in that case is `compatible_reproduction`
at best. CI pins every thread variable to 1. This does not make single-threaded a product
requirement; it makes the count recorded and a change of it visible.
"""

from __future__ import annotations

import hashlib
import os
import platform
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Final

from openflowsheet.canonical import canonical_json, file_sha256

if TYPE_CHECKING:
    from pathlib import Path

#: ADR 0007 D6's thread variables, in the order a manifest records them.
THREAD_VARIABLES: Final[tuple[str, ...]] = (
    "OPENBLAS_NUM_THREADS",
    "OMP_NUM_THREADS",
    "MKL_NUM_THREADS",
)

#: Fields recorded on a run and **never** entering `structural_sha256` (blueprint D20; plan
#: §4.2 K05 "timing excluded from structural identity").
#:
#: Wall-clock timing is the obvious one. `run_id`, `started_at`, `parent_run_id` and `hostname`
#: go with it: two runs of the same thing are structurally identical and differ in when they
#: happened and what they were called.
#:
#: **`environment` and `artifacts` are here too, and that was a correction.** The first version
#: hashed them, and CI immediately produced two different `structural_sha256` values across
#: x86-64 and aarch64 while *every other R0 field was identical* — the model version, the plan,
#: the event sequence, the certificate's check results, the solver counters. The hash was the
#: only thing that moved, which meant it was measuring the wrong thing.
#:
#: It was. Blueprint §8.3 R0 is "same canonical model and structural policy yield identical
#: structural artifacts **on supported platforms**", so a structural identity that changes with
#: the platform cannot be it. The environment is *provenance*: ADR 0007 D6 requires it recorded
#: so a within-policy difference is attributable, which is a different job from identity. And
#: the artifact index hashes documents that contain floats, which §8.3 excludes from any
#: cross-platform bitwise promise — the index is how `verify_bundle` detects tampering within
#: one archive, not how two runs are compared.
#:
#: A changed dependency is still detected, and earlier: `decide_mode` compares lock hashes
#: before anything runs (D4), which is where G05's first clause actually lives.
NON_STRUCTURAL: Final[frozenset[str]] = frozenset(
    {
        "run_id",
        "started_at",
        "elapsed_seconds",
        "parent_run_id",
        "hostname",
        "environment",
        "artifacts",
    }
)


@dataclass(frozen=True)
class Environment:
    """ADR 0007 D6's pins, captured from the live interpreter.

    `blas` is what SciPy reports rather than what is installed: the question a replay needs
    answered is which library the arithmetic actually went through, and on a wheel-based
    install those can differ.
    """

    architecture: str
    os_name: str
    os_release: str
    python_version: str
    lock_sha256: str
    blas: Mapping[str, str]
    threads: Mapping[str, str | None]
    superlu_options_ref: str = "ADR 0004 D1"

    def as_document(self) -> dict[str, Any]:
        return {
            "architecture": self.architecture,
            "os_name": self.os_name,
            "os_release": self.os_release,
            "python_version": self.python_version,
            "lock_sha256": self.lock_sha256,
            "blas": dict(self.blas),
            "threads": dict(self.threads),
            "superlu_options_ref": self.superlu_options_ref,
        }

    #: ADR 0007 D3.3 lists the BLAS **vendor** as part of the platform identity, so it is in
    #: the tuple — S3 of the Fable review, which noticed it was recorded and then ignored.
    #: `os_release` stays out: a kernel patch is not a different registered platform, and
    #: calling it one would make every runner upgrade an inspection.
    def identity(self) -> tuple[str, str, str, str]:
        return (
            self.architecture,
            self.os_name,
            self.python_version,
            str(self.blas.get("name", "")),
        )

    def same_blas_version(self, other: Environment) -> bool:
        """The one thing a lock hash cannot see: a wheel rebuilt under an unchanged lock.

        The measured non-portability enters at the factorization, which is the code a BLAS
        build feeds, so a differing version is `compatible_reproduction` at best. That is the
        ADR author's own answer to the doubt this brief raised — the "every upgrade becomes an
        inspection" objection applies to `os_release`, not to the library the arithmetic went
        through, and the mode this produces is a reproduction, not an inspection.
        """
        return self.blas.get("version") == other.blas.get("version")

    def same_dependencies(self, other: Environment) -> bool:
        return self.lock_sha256 == other.lock_sha256

    def same_threads(self, other: Environment) -> bool:
        return dict(self.threads) == dict(other.threads)

    def threads_known(self) -> bool:
        """F4, answered by Frank on 2026-09-22: **unset is unknown, and unknown is never exact.**

        ADR 0007 D6 says the thread count is recorded "as set", and said nothing about unset.
        An unpinned machine records `None` for all three variables, so two unpinned machines
        with different core counts compared equal and replayed as `exact_replay` — with the
        effective OpenBLAS thread count, the quantity D6 actually cares about, unknown on both
        sides. A developer who wants `exact_replay` locally pins the three variables, as CI
        does.
        """
        return all(value is not None for value in self.threads.values())


def blas_identity() -> dict[str, str]:
    """What SciPy says it is linked against. Unavailable is recorded, never guessed."""
    try:
        import scipy  # noqa: PLC0415

        config = getattr(scipy, "__config__", None)
        if config is not None and hasattr(config, "CONFIG"):
            build = config.CONFIG.get("Build Dependencies", {}).get("blas", {})
            if build:
                return {
                    "name": str(build.get("name", "unknown")),
                    "version": str(build.get("version", "unknown")),
                }
        return {"name": "unknown", "version": str(scipy.__version__)}
    except Exception as failure:  # pragma: no cover - a broken SciPy is not a manifest problem
        return {"name": "unavailable", "version": f"{type(failure).__name__}"}


def environment(lock_path: str | os.PathLike[str] | None = None) -> Environment:
    """Capture the live environment. Every field is read, none is defaulted to a guess."""
    from pathlib import Path  # noqa: PLC0415

    resolved = Path(lock_path) if lock_path is not None else _repository_lock()
    return Environment(
        architecture=platform.machine(),
        os_name=platform.system(),
        os_release=platform.release(),
        python_version=platform.python_version(),
        lock_sha256=file_sha256(resolved) if resolved is not None and resolved.is_file() else "",
        blas=blas_identity(),
        threads={name: os.environ.get(name) for name in THREAD_VARIABLES},
    )


def _repository_lock() -> Path | None:
    return _checkout_lock(__file__)


def _checkout_lock(module: str | os.PathLike[str]) -> Path | None:
    """The `requirements.lock` of the source checkout `module` lives in, or `None`.

    T08 release spec Amendment R3 5 (R-140): the lookup is confined to the checkout — the
    directory holding `pyproject.toml` with `[project].name = "openflowsheet"` and the
    `src/openflowsheet/` package this module belongs to. An installed package (wheel or
    sdist) ships no lock, so it records `lock_sha256 = ""` and its bundles replay
    `inspected_archived_results` (envelope L41). The earlier lookup walked every parent
    directory and fell back to the working directory, so an installed package beneath any
    unrelated file named `requirements.lock` recorded that file's hash as its dependency set —
    a false identity, and an `exact_replay` between two such installs.
    """
    import tomllib  # noqa: PLC0415
    from pathlib import Path  # noqa: PLC0415

    here = Path(module).resolve()
    if len(here.parents) < 4:
        return None
    package, root = here.parents[1], here.parents[3]
    if package != (root / "src" / "openflowsheet").resolve():
        return None
    try:
        project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError):
        return None
    if project.get("project", {}).get("name") != "openflowsheet":
        return None
    lock = root / "requirements.lock"
    return lock if lock.is_file() else None


@dataclass(frozen=True)
class RunManifest:
    """Blueprint Appendix A: model/data/solver/backend/dependency hashes, environment,
    threads and seeds, policies, artifacts, parent run, reproducibility class.

    Frozen, and `structural_sha256` is computed from the document rather than stored, so a
    manifest cannot carry a hash that disagrees with its own contents.
    """

    run_id: str
    model_version: str
    constants_sha256: str
    policy_id: str
    plan_id: str
    check_policy_sha256: str
    #: S1 of the Fable review: `policy_id` is a *name*. Measured — a `SolvePolicy` with the
    #: same id and `max_iterations_per_attempt + 1` produced an identical `structural_sha256`,
    #: while ADR 0007 D1 makes every `SolvePolicy` value R0. This is the values, mirroring
    #: `check_policy_sha256`, which had one from the start.
    policy_sha256: str
    #: S1(b): the digest of the R0 projection of this run's artifacts (`run/identity.py`).
    #: Without it the identity covered what the run was *called* and not what it *did*: two
    #: runs with different event sequences, different attempt trees or different solver
    #: counters shared an identity whenever their outcome words agreed.
    artifact_r0_sha256: str
    numerical_policy_id: str
    environment: Environment
    artifacts: Mapping[str, str]
    outcome: str
    verification_status: str | None = None
    seeds: Mapping[str, int] = field(default_factory=dict)
    reproducibility_class: str = "R1"
    parent_run_id: str | None = None
    started_at: str = ""
    elapsed_seconds: float | None = None
    hostname: str = ""

    def _base_document(self) -> dict[str, Any]:
        """Everything except the hash. Both public documents derive from this one."""
        return {
            "run_id": self.run_id,
            "parent_run_id": self.parent_run_id,
            "model_version": self.model_version,
            "constants_sha256": self.constants_sha256,
            "policy_id": self.policy_id,
            "plan_id": self.plan_id,
            "check_policy_sha256": self.check_policy_sha256,
            "policy_sha256": self.policy_sha256,
            "artifact_r0_sha256": self.artifact_r0_sha256,
            "numerical_policy_id": self.numerical_policy_id,
            "environment": self.environment.as_document(),
            "artifacts": dict(self.artifacts),
            "outcome": self.outcome,
            "verification_status": self.verification_status,
            "seeds": dict(self.seeds),
            "reproducibility_class": self.reproducibility_class,
            "started_at": self.started_at,
            "elapsed_seconds": self.elapsed_seconds,
            "hostname": self.hostname,
        }

    def as_document(self) -> dict[str, Any]:
        return {
            **self._base_document(),
            "structural_sha256": self.structural_sha256,
            "manifest_sha256": self.manifest_sha256,
        }

    @property
    def manifest_sha256(self) -> str:
        """A self-hash over the **whole** base document, environment and index included.

        `structural_sha256` deliberately excludes both, so that two runs of the same model on
        different machines share an identity. Removing them from that hash also removed the
        only thing detecting an edit to them — the Fable review of K05 found the hole and
        measured it: change `environment.lock_sha256` in a written manifest, or tamper an
        artifact and re-index its hash, and the bundle verified clean either way.

        So identity and integrity are two hashes now, because they are two questions. This one
        covers everything the manifest says about itself.

        **It is a self-hash and not a signature.** Anyone who can edit the manifest can
        recompute it. What it catches is an edit that forgot to, which is every accidental one
        and every careless deliberate one; what it does not catch is an adversary, and nothing
        in a plain directory could.
        """
        return hashlib.sha256(canonical_json(self._base_document())).hexdigest()

    @property
    def structural_document(self) -> dict[str, Any]:
        """Everything the structural hash covers: the document minus `NON_STRUCTURAL`.

        Built by *removing* from the full document rather than by listing what to include, so
        a field added to the manifest is hashed by default. The failure this avoids is the one
        where a new field silently escapes the hash because nobody added it to a whitelist.
        """
        return {
            key: value for key, value in self._base_document().items() if key not in NON_STRUCTURAL
        }

    @property
    def structural_sha256(self) -> str:
        """ADR 0002's canonical JSON of the structural document. R0's identity.

        **Conditional, per ADR 0007 D2.4.** `outcome`, `verification_status` and the check
        results inside `artifact_r0_sha256` are R0 only while no quantity they depend on sits
        within the near-threshold margin of its threshold. At such a state two registered
        platforms may legitimately produce different identities, and the R0 projection carries
        each check's `near_threshold` flag so that the difference is diagnosable as D2.4
        rather than read as a defect. SYN-001 nominal has no flags at all (K04 A33), so the
        condition is invisible today and will matter the day a registered case lands in the
        band.
        """
        return hashlib.sha256(canonical_json(self.structural_document)).hexdigest()


def started_now() -> str:
    """An ISO-8601 UTC timestamp. Recorded, never hashed (`NON_STRUCTURAL`)."""
    from datetime import UTC, datetime  # noqa: PLC0415

    return datetime.now(UTC).isoformat(timespec="microseconds")


def policy_sha256(policy: Any) -> str:
    """S1: the `SolvePolicy`'s *values*, not its name.

    `CheckPolicy` had a hash from the start and `SolvePolicy` did not, so the manifest carried
    the check policy's contents and the solve policy's label. Measured: two policies with the
    same `policy_id` and different iteration caps produced an identical structural identity,
    while ADR 0007 D1 makes every `SolvePolicy` value R0.
    """
    return hashlib.sha256(canonical_json(policy.as_document())).hexdigest()
