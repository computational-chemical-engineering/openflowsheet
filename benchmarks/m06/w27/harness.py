"""W27's agent harness: one headless Claude Code session per sampled case (M06 WO-16d).

Normative text: registration §8 (W27-R33, the agent configuration), §9 (W27-R34…R36, the card and
the prompt), §11.1 (W27-R42, the store export) and §13 (W27-R58, the run record); design note
`docs/design/M06-web-shell.md` §9 Tier 1. V17's harness (`benchmarks/t07/v17/harness.py`) is reused
for everything that is not W27's: the command line, the MCP configuration, the whitelisted
environment, operator identity isolation, the work directory outside the repository, the session
runner with its wall cap, infrastructure detection and the `init` checks.

What W27 adds:

- the **model is a recorded parameter** (Frank, F2): Claude Code's default on the campaign's
  login, read from the pinning canary attempt's `init` message and passed by exact id to every
  later attempt and run, never `claude-sonnet-5` (registration §23.5; `agent_config`,
  `model_pin`);
- the prompt is the registered template over the case card, whose SHA-256 must equal the
  registered one (W27-A21, A22);
- a **fresh, empty project per run**, seeded only by `project init` and `project grant` of
  `agent-w27` (`seed_project`);
- the export adds `audit` and `audit_all` read through `list_audit` as the local owner, and every
  replay bundle's files, which the scorer's system checks replay (`export_store`);
- `run.json` records the lock hash and the interpreter (V17's open finding), the commit and
  whether the tree is clean, the model, effort and Claude Code version and the pins, and the
  SHA-256 of the registration, coverage, snapshot, card and prompt (W27-R58, W27-A23).

The records follow registration §23.2's order, each naming the SHA-256 of the earlier ones
(`order_check`): `coverage.json`, `sample.json`, `confirmation/confirmation.json` (`confirm`,
W27-R66), the canary attempts `canary/<NN>-<case_id>/` (`canaries`, W27-R68), `preflight.json`
(written by `campaign` once P1–P8 pass, W27-R67), then the runs in the registered order of
`sample.json` and `campaign.json`. A run whose directory exists is never repeated. Nothing here
is run by the gate: the dry run (`benchmarks.m06.w27.dryrun`) drives it with a stub `claude` that
makes no model call.

`python -m benchmarks.m06.w27.harness` drives WO-17 (`main`): `confirm`, `canaries`,
`preflight`, `campaign`, `order` and `spend` over `RUNS_ROOT/<campaign>/`, whose `coverage.json`
and `sample.json` are written first by `benchmarks.m06.w27.coverage` and
`benchmarks.m06.w27.sample` (`docs/briefs/W27-runbook.md`).
"""

from __future__ import annotations

import argparse
import base64
import json
import platform
import re
import shutil
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from benchmarks.m06.w27 import facts, registration
from benchmarks.m06.w27 import scorer as w27_scorer
from benchmarks.t07.v17 import export as v17_export
from benchmarks.t07.v17 import harness as v17
from openflowsheet.canonical import canonical_json

HarnessError = v17.HarnessError
#: R58: the campaign record's place (U14, W27-R64: the campaign's records only under it).
RUNS_ROOT: Final[Path] = registration.RECORDS / "runs"
CANARY_DIR: Final[str] = "canary"
#: W27-R66, W27-R67: the confirmation and preflight records, relative to the campaign directory.
CONFIRMATION_FILE: Final[str] = "confirmation/confirmation.json"
PREFLIGHT_FILE: Final[str] = "preflight.json"
#: The command line's spend ceiling: the top of Frank's approval, USD 15–45 (P1's line).
SPEND_CEILING_USD: Final[float] = 45.0
PROJECT_ID: Final[str] = "w27-run"
#: Registration §3 F1: the campaign model is not V17's.
NOT_THE_MODEL: Final[str] = "claude-sonnet-5"
#: The registered tool and isolation flags (W27-R33), as V17's command line spells them.
TOOLS_TEXT: Final[str] = '--tools "" with --allowedTools "mcp__procsim__*" and --strict-mcp-config'
ISOLATION_TEXT: Final[str] = '--setting-sources ""'


class RefusalError(HarnessError):
    """A refusal registration §23 names: nothing was launched or written (exit 2)."""


@dataclass(frozen=True)
class AgentConfig(v17.AgentConfig):
    """V17's configuration, where `model` None is an unpinned canary attempt: the pinning attempt
    and every attempt before it run on Claude Code's default (registration §23.5)."""

    def check(self) -> None:
        if self.model is None:
            if not self.effort:
                raise HarnessError("the effort is not pinned")
            return
        super().check()


def campaign_records() -> Mapping[str, Any]:
    """`registration.json#/campaign_records` (registration §23)."""
    records: Mapping[str, Any] = registration.load()["campaign_records"]
    return records


def _registered() -> Mapping[str, Any]:
    configuration: Mapping[str, Any] = registration.load()["agent_configuration"]
    return configuration


def _principal() -> Mapping[str, Any]:
    principal: Mapping[str, Any] = registration.load()["scoring"]["agent_principal"]
    return principal


def agent_config(model: str | None, *, claude: str = "claude") -> AgentConfig:
    """W27-R33's configuration with `model` as given (None: no `--model`, registration §23.5):
    effort, turns, wall cap, budget guard, tools and isolation from `registration.json`;
    operator isolation on."""
    table = _registered()
    if table["tools"] != TOOLS_TEXT or table["isolation"] != ISOLATION_TEXT:
        raise HarnessError("the registered tools or isolation are not V17's command line")
    if model == NOT_THE_MODEL:
        raise HarnessError(f"{NOT_THE_MODEL} is V17's model, not W27's (registration §3 F1)")
    config = AgentConfig(
        model=model,
        effort=str(table["effort"]),
        max_turns=int(table["max_turns"]),
        max_turns_flag=bool(table["max_turns_flag"]),
        wall_cap_s=float(table["wall_cap_s"]),
        max_budget_usd=float(table["max_budget_usd"]),
        isolation=("--setting-sources", ""),
        claude=claude,
        operator_isolation=bool(table["operator_isolation"]),
    )
    config.check()
    return config


# =================================================================================================
# W27-R34…R36: the card and the prompt
# =================================================================================================


def case_card(case_id: str, cases_root: Path | None = None) -> str:
    """The case's card; refused unless its SHA-256 is the registered one (W27-A21)."""
    root = registration.ARCHIVE_DIR / "cases" if cases_root is None else cases_root
    text = facts.case_card(root / case_id)
    registered = registration.load()["prompt"]["card"]["sha256_by_case"].get(case_id)
    if registration.sha256_bytes(text.encode("utf-8")) != registered:
        raise HarnessError(f"{case_id}: the card does not hash as registered (W27-A21)")
    return text


def prompt(case_id: str, card: str) -> str:
    """W27-R35/R36: the template with the registered markers, the card, and the footer with the
    case id filled; nothing else (W27-A22)."""
    table = registration.load()["prompt"]
    digest = registration.sha256_bytes(card.encode("utf-8"))
    return str(table["template"]).format(
        envelope_begin=str(table["envelope_begin"]).format(case_id=case_id, card_sha256=digest),
        card=card,
        envelope_end=str(table["envelope_end"]).format(case_id=case_id),
        footer=str(table["footer"]).format(case_id=case_id),
    )


# =================================================================================================
# The project: init, grant, export
# =================================================================================================


def seed_project(project: Path, token_file: Path) -> dict[str, int]:
    """`project init` and `project grant` of `agent-w27` (W27-R33), nothing else; returns the
    session boundary (V17 §4.3)."""
    from benchmarks.t07.v17 import fixtures  # noqa: PLC0415
    from openflowsheet.application.authz import grant  # noqa: PLC0415
    from openflowsheet.application.local import LocalApplication  # noqa: PLC0415
    from openflowsheet.application.types import Limits  # noqa: PLC0415

    table = _principal()
    LocalApplication.create(project, project_id=PROJECT_ID).close()
    _, token = grant(
        project,
        principal_id=str(table["principal_id"]),
        rights=list(table["rights"]),
        limits=Limits(
            default_wall_time_s=float(table["default_wall_time_s"]),
            max_wall_time_s=float(table["max_wall_time_s"]),
            max_active_jobs=int(table["max_active_jobs"]),
        ),
        capability_id=str(table["capability_id"]),
    )
    token_file.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    token_file.write_text(token + "\n", encoding="utf-8")
    token_file.chmod(0o600)
    with LocalApplication.open(project) as app:
        return fixtures.session_start(app)


def _audit(app: Any, principal_id: str | None) -> list[dict[str, Any]]:
    """`list_audit` ascending, paged to the end (ADR 0019 Amendment 3)."""
    rows: list[dict[str, Any]] = []
    cursor: str | None = None
    while True:
        page = app.list_audit(principal_id=principal_id, order="ascending", cursor=cursor)
        rows += [item.as_document() for item in page.items]
        cursor = page.next_cursor
        if cursor is None:
            return rows


def export_store(project: Path, session_start: Mapping[str, int], directory: Path) -> Path:
    """W27-R42's `store-export.json`: V17 §4.8's members, `audit` (agent-w27's rows) and
    `audit_all` (every principal's) by `list_audit` as the local owner, and `bundle_files`, each
    replay bundle's files as base64 under their bundle-relative paths."""
    from openflowsheet.application.local import LocalApplication  # noqa: PLC0415

    document = v17_export.export(project, dict(session_start))
    with LocalApplication.open(project) as app:
        document["audit"] = _audit(app, str(_principal()["principal_id"]))
        document["audit_all"] = _audit(app, None)
        bundles: dict[str, dict[str, str]] = {}
        for row in document["artifacts"]:
            if row["kind"] != "replay_bundle":
                continue
            stored = app.store.artifact(row["artifact_id"])
            assert stored is not None
            root = app.files_root / stored.relpath
            bundles[row["artifact_id"]] = {
                path.relative_to(root).as_posix(): base64.b64encode(path.read_bytes()).decode()
                for path in sorted(root.rglob("*"))
                if path.is_file()
            }
        document["bundle_files"] = bundles
    path = directory / w27_scorer.STORE_EXPORT_FILE
    path.write_bytes(canonical_json(document))
    return path


# =================================================================================================
# Provenance (W27-R58): the lock, the interpreter, the tree
# =================================================================================================


def lock_sha256() -> str:
    """The value `run/manifest.py` records for this checkout; a run refuses an empty one."""
    from openflowsheet.run.manifest import environment  # noqa: PLC0415

    return environment().lock_sha256


def interpreter() -> dict[str, str]:
    return {
        "executable": sys.executable,
        "version": sys.version,
        "implementation": platform.python_implementation(),
        "platform": platform.platform(),
    }


def git_state(runs_root: Path) -> dict[str, Any]:
    """The commit, and whether anything outside `runs_root` differs from it."""

    def git(*arguments: str) -> str:
        return subprocess.run(
            ["git", "-C", str(registration.ROOT), *arguments],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

    exclude: list[str] = []
    root = runs_root.resolve()
    if registration.ROOT in root.parents:
        exclude = [f":(exclude){root.relative_to(registration.ROOT).as_posix()}"]
    try:
        dirty = git("status", "--porcelain", "--", ".", *exclude)
        return {"commit": git("rev-parse", "HEAD"), "tree_clean": not dirty}
    except (OSError, subprocess.CalledProcessError):
        return {"commit": None, "tree_clean": None}


# =================================================================================================
# A run
# =================================================================================================


def run(
    case_id: str,
    order: int,
    campaign: str,
    *,
    work: Path,
    config: AgentConfig,
    coverage_path: Path,
    pinned_claude_code_version: str | None,
    runs_root: Path = RUNS_ROOT,
    cases_root: Path | None = None,
    environment: Mapping[str, str] | None = None,
    operator: v17.Operator | None = None,
    name: str | None = None,
    replay: w27_scorer.ReplayRunner = w27_scorer.replay_in_fresh_process,
    chain: Mapping[str, str] | None = None,
) -> Path:
    """One case: a fresh project, the session, the record, the export, the score. Returns
    `runs_root/<campaign>/<order:02d>-<case_id>` (or `.../<name>`). `chain` holds the digests of
    the earlier records `run.json` names (registration §23.2): `sample_sha256` with
    `confirmation_sha256` for a canary attempt, or with `preflight_sha256` for a campaign run.
    `model` is the requested model, None for an attempt run without `--model`."""
    config.check()
    coverage_bytes = coverage_path.read_bytes()
    coverage = json.loads(coverage_bytes)
    row = w27_scorer.coverage_row(coverage, case_id)
    lock = lock_sha256()
    if not lock:
        raise HarnessError("the checkout records an empty lock hash (W27-R58)")
    oauth_token = v17._session_token(config, operator)
    card = case_card(case_id, cases_root)
    text = prompt(case_id, card)
    name = f"{order:02d}-{case_id}" if name is None else name
    run_dir = runs_root / campaign / name
    paths = v17.work_paths(work, campaign, name)
    if run_dir.exists():
        raise HarnessError(f"{run_dir} exists; a run is never repeated")
    v17.prepare(paths)
    run_dir.mkdir(parents=True)
    version = v17.claude_version(config.claude)
    git = git_state(runs_root)
    base: dict[str, Any] = {
        "campaign": campaign,
        "order": order,
        "case_id": case_id,
        "case_class": row["class"],
        "session_principal": str(_principal()["principal_id"]),
        "cost_basis": v17.COST_BASIS,
        "model": config.model,
        "effort": config.effort,
        "claude_code_version": version,
        "pinned": {
            "model": config.model,
            "effort": config.effort,
            "claude_code_version": pinned_claude_code_version,
        },
        "commit": git["commit"],
        "tree_clean": git["tree_clean"],
        "lock_sha256": lock,
        "interpreter": interpreter(),
        "registration_sha256": registration.sha256_file(registration.REGISTRATION_JSON),
        "coverage_sha256": registration.sha256_bytes(coverage_bytes),
        **(chain or {}),
        "snapshot_sha256": coverage["snapshot_sha256"],
        "card_sha256": registration.sha256_bytes(card.encode("utf-8")),
        "prompt_sha256": v17.sha256_text(text),
    }
    _write(
        run_dir / w27_scorer.RUN_FILE,
        {**base, "infrastructure_failure": {"reason": v17.INCOMPLETE}},
    )
    session_start = seed_project(paths.project, paths.token_file)
    session = v17.launch(
        config, text, paths, run_dir, environment=environment, oauth_token=oauth_token
    )
    record = {
        **base,
        **session.record,
        "session_start": session_start,
        "infrastructure_failure": v17.infrastructure_failure(session.outcome),
    }
    if config.model is None:
        _unpinned(record)
    _write(run_dir / w27_scorer.RUN_FILE, record)
    export_store(paths.project, session_start, run_dir)
    if config.operator_isolation:
        assert operator is not None
        hits = v17.identifier_hits(run_dir, operator.address)
        record["operator_identifier_hits"] = sum(hits.values())
        record["operator_identifier_hits_by_file"] = hits
        _write(run_dir / w27_scorer.RUN_FILE, record)
    scores = w27_scorer.score(run_dir, coverage, cases_root=cases_root, replay=replay)
    (run_dir / w27_scorer.SCORES_FILE).write_bytes(w27_scorer.dump(scores))
    return run_dir


def _unpinned(record: dict[str, Any]) -> None:
    """An attempt run without `--model` (registration §23.5): its model check is that the
    `init` model is non-empty (V17 `session_checks`) and not `claude-sonnet-5`. That model is
    the pin this attempt establishes, so it is recorded as `pinned.model` (the scorer's pin
    check, W27-R58 `pinned`); `model`, the requested model, stays None. BUILD DECISION
    (WO-17a, logged in docs/design/M07-build-decisions.md): §23 does not say what `pinned.model`
    holds for such an attempt, and with None the scorer's `pin_mismatch(model)` fails every
    unpinned canary."""
    session = record["session"]
    model = (session["init"] or {}).get("model")
    if model == NOT_THE_MODEL:
        session["checks"].append(
            f"model {NOT_THE_MODEL!r} is V17's, not W27's (registration §3 F1, §23.5)"
        )
    elif isinstance(model, str) and model:
        record["pinned"] = {**record["pinned"], "model": model}


def _write(path: Path, document: Any) -> None:
    path.write_text(json.dumps(document, indent=1, sort_keys=True) + "\n", encoding="utf-8")


# =================================================================================================
# The confirmation record (W27-R66)
# =================================================================================================


def sampled_candidates(coverage: Mapping[str, Any], sample: Mapping[str, Any]) -> list[str]:
    """The sorted ids of the sampled cases whose `coverage.json` row has class `CANDIDATE`."""
    rows = {row["case_id"]: row for row in coverage["rows"]}
    return sorted(c for c in sample["cases"] if rows[c]["class"] == "CANDIDATE")


def confirm(name: str, *, runs_root: Path = RUNS_ROOT) -> Path:
    """W27-R66: `confirmation/confirmation.json` after the draw, at a clean HEAD. A non-empty C
    is refused (`RefusalError`, nothing written): §7's reference builds have no registered
    record."""
    coverage_path, sample_path = _campaign_files(runs_root, name)
    state = git_state(runs_root)
    if state["tree_clean"] is not True:
        raise HarnessError("confirm: the tree is not clean (registration §23.3)")
    coverage_bytes, sample_bytes = coverage_path.read_bytes(), sample_path.read_bytes()
    candidates = sampled_candidates(json.loads(coverage_bytes), json.loads(sample_bytes))
    if candidates:
        raise RefusalError(
            f"confirmation: {len(candidates)} sampled CANDIDATE case(s); §7's reference builds "
            "have no registered record (registration §23.3)"
        )
    document = {
        "schema": campaign_records()["confirmation"]["schema"],
        "campaign": name,
        "commit": state["commit"],
        "tree_clean": True,
        "coverage_sha256": registration.sha256_bytes(coverage_bytes),
        "sample_sha256": registration.sha256_bytes(sample_bytes),
        "candidates": candidates,
        "empty": candidates == [],
    }
    path = runs_root / name / CONFIRMATION_FILE
    path.parent.mkdir(exist_ok=True)
    path.write_bytes(registration.dump(document))
    return path


# =================================================================================================
# Canaries (W27-R31, W27-R68) and the model pin (registration §23.5)
# =================================================================================================


def canary_verdict(run_dir: Path) -> dict[str, Any]:
    """A canary passes when its session was in the configuration (V17 `session_checks`), it is
    not an infrastructure failure, its files hold no operator identifier, and it was scored."""
    record = json.loads((run_dir / w27_scorer.RUN_FILE).read_text(encoding="utf-8"))
    scores_path = run_dir / w27_scorer.SCORES_FILE
    scores = json.loads(scores_path.read_text(encoding="utf-8")) if scores_path.is_file() else None
    checks = v17.recorded_checks(run_dir)
    hits = record.get("operator_identifier_hits")
    infrastructure = scores.get("infrastructure_failure") if scores is not None else "unscored"
    init = (record.get("session") or {}).get("init") or {}
    return {
        "passed": not checks and infrastructure is None and hits == 0 and scores is not None,
        "session_checks": checks,
        "infrastructure_failure": infrastructure,
        "operator_identifier_hits": hits,
        "init_model": init.get("model"),
        "init_claude_code_version": init.get("claude_code_version"),
    }


@dataclass(frozen=True)
class CanaryAttempt:
    """One directory `canary/<NN>-<case_id>/` (W27-R68), as P6, P7 and the pin read it."""

    name: str
    n: int | None  # None when the name is not `<digits>-<case_id>`
    case_id: str
    commit: str | None
    tree_clean: bool | None
    model: str | None  # requested: None for an attempt run without `--model`
    init_model: str | None  # the transcript's `init` message, None without one
    init_claude_code_version: str | None
    passed: bool  # `canary_verdict`
    path: Path


def _transcript_init(run_dir: Path) -> Mapping[str, Any]:
    counter = v17.TurnCounter()
    transcript = run_dir / w27_scorer.TRANSCRIPT_FILE
    if transcript.is_file():
        for line in transcript.read_bytes().splitlines():
            counter.feed(line)
    return counter.init or {}


def canary_attempts(campaign_dir: Path) -> list[CanaryAttempt]:
    """Every attempt directory under `campaign_dir/canary/`, in attempt order."""
    root = campaign_dir / CANARY_DIR
    attempts = []
    for path in sorted(p for p in root.iterdir() if p.is_dir()) if root.is_dir() else []:
        match = re.match(r"^([0-9]+)-(.+)$", path.name)
        run_json = path / w27_scorer.RUN_FILE
        record = json.loads(run_json.read_bytes()) if run_json.is_file() else {}
        init = _transcript_init(path)
        model = init.get("model")
        attempts.append(
            CanaryAttempt(
                name=path.name,
                n=int(match[1]) if match else None,
                case_id=match[2] if match else path.name,
                commit=record.get("commit"),
                tree_clean=record.get("tree_clean"),
                model=record.get("model"),
                init_model=model if isinstance(model, str) and model else None,
                init_claude_code_version=init.get("claude_code_version"),
                passed=run_json.is_file() and canary_verdict(path)["passed"],
                path=path,
            )
        )
    return sorted(attempts, key=lambda a: (a.n is None, a.n or 0, a.name))


def counted_attempts(
    attempts: Sequence[CanaryAttempt], canary_cases: Sequence[str]
) -> dict[str, CanaryAttempt | None]:
    """Each canary case's latest attempt, its *counted* attempt (W27-R68); None if none."""
    return {
        case_id: next((a for a in reversed(attempts) if a.case_id == case_id), None)
        for case_id in canary_cases
    }


def pinning_attempt(attempts: Sequence[CanaryAttempt]) -> CanaryAttempt | None:
    """The earliest attempt whose transcript has an `init` message with a model id (§23.5)."""
    return next((a for a in attempts if a.init_model is not None), None)


def model_pin(attempts: Sequence[CanaryAttempt]) -> str | None:
    """The pin, the pinning attempt's `init` model, or None before one exists. Refused when it
    would be V17's model (Frank, §3 F1) or is no full model id (the design lane, A4-Q1)."""
    pinning = pinning_attempt(attempts)
    if pinning is None or pinning.init_model is None:
        return None
    pin = pinning.init_model
    if pin == NOT_THE_MODEL:
        raise RefusalError(
            f"the pin would be {NOT_THE_MODEL} ({pinning.name}): Frank (registration §3 F1, §23.5)"
        )
    if pin in v17.MODEL_ALIASES or not pin.startswith("claude-"):
        raise RefusalError(
            f"{pinning.name}'s init model {pin!r} is no full model id: the design lane rules "
            "before the next attempt (registration §23.10 A4-Q1)"
        )
    return pin


def canaries(
    campaign: str,
    *,
    work: Path,
    claude: str = "claude",
    runs_root: Path = RUNS_ROOT,
    operator: v17.Operator | None = None,
    run_one: Callable[..., Path] = run,
) -> list[dict[str, Any]]:
    """W27-R31, W27-R68: at HEAD, the canary cases of `sample.json` in order, skipping a case
    that already passed at HEAD; each attempt is `<campaign>/canary/<NN>-<case_id>/`, numbered on
    from the attempts already there. Stops after the first attempt that fails. Refuses a seventh
    attempt (`RefusalError`, nothing launched). The model is read from the directory (`model_pin`):
    none until an attempt's `init` names one, that one after. Returns the attempts' verdicts.
    Harness checks, not campaign data."""
    directory = runs_root / campaign
    coverage_path, sample_path = _campaign_files(runs_root, campaign)
    confirmation_path = directory / CONFIRMATION_FILE
    if not confirmation_path.is_file():
        raise HarnessError(f"write the confirmation first (`confirm`): {confirmation_path}")
    sample = json.loads(sample_path.read_bytes())
    chain = {
        "sample_sha256": registration.sha256_file(sample_path),
        "confirmation_sha256": registration.sha256_file(confirmation_path),
    }
    head = git_state(runs_root)["commit"]
    limit = int(campaign_records()["canary_attempts_max"])
    verdicts: list[dict[str, Any]] = []
    for case_id in sample["canaries"]:
        attempts = canary_attempts(directory)
        if any(a.case_id == case_id and a.commit == head and a.passed for a in attempts):
            continue
        n = 1 + max((a.n or 0 for a in attempts), default=0)
        if n > limit:
            raise RefusalError("re-canary allowance exhausted (registration §17 Q3): Frank")
        run_dir = run_one(
            case_id,
            n,
            f"{campaign}/{CANARY_DIR}",
            work=work,
            config=agent_config(model_pin(attempts), claude=claude),
            coverage_path=coverage_path,
            pinned_claude_code_version=None,
            runs_root=runs_root,
            operator=operator,
            chain=chain,
        )
        verdicts.append({"attempt": run_dir.name, "case_id": case_id, **canary_verdict(run_dir)})
        if not verdicts[-1]["passed"]:
            break
    return verdicts


# =================================================================================================
# The preflight record (W27-R67) and the campaign (M07; WO-17 runs them, not WO-16)
# =================================================================================================


def write_preflight(
    name: str,
    runs_root: Path,
    *,
    model: str,
    claude_code_version: str,
    checks: Mapping[str, Mapping[str, Any]],
) -> Path:
    """W27-R67: `preflight.json`, once, after P1–P8 passed and before run 01."""
    if not checks or not all(verdict["passed"] for verdict in checks.values()):
        raise HarnessError("preflight.json records a preflight that passed, nothing else")
    directory = runs_root / name
    path = directory / PREFLIGHT_FILE
    if path.exists():
        raise HarnessError(f"{path} exists; it is written once")
    sample_path = directory / "sample.json"
    confirmation_path = directory / CONFIRMATION_FILE
    sample = json.loads(sample_path.read_bytes())
    counted = counted_attempts(canary_attempts(directory), sample["canaries"])
    missing = [case_id for case_id, attempt in counted.items() if attempt is None]
    if missing:
        raise HarnessError(f"no counted canary attempt for {missing}")
    state = git_state(runs_root)
    document = {
        "schema": campaign_records()["preflight"]["schema"],
        "campaign": name,
        "commit": state["commit"],
        "tree_clean": state["tree_clean"],
        "registration_sha256": registration.sha256_file(registration.REGISTRATION_JSON),
        "coverage_sha256": registration.sha256_file(directory / "coverage.json"),
        "sample_sha256": registration.sha256_file(sample_path),
        "confirmation_sha256": registration.sha256_file(confirmation_path),
        "canaries": [
            {
                "attempt": attempt.name,
                "case_id": attempt.case_id,
                "run_json_sha256": registration.sha256_file(attempt.path / w27_scorer.RUN_FILE),
            }
            for attempt in counted.values()
            if attempt is not None
        ],
        "model": model,
        "claude_code_version": claude_code_version,
        "checks": dict(checks),
        "passed": True,
    }
    path.write_bytes(registration.dump(document))
    return path


def campaign(
    name: str,
    *,
    work: Path,
    config: AgentConfig,
    claude_code_version: str,
    coverage_path: Path,
    sample_path: Path,
    runs_root: Path = RUNS_ROOT,
    resume: bool = False,
    operator: v17.Operator | None = None,
    preflight: Callable[[], Mapping[str, Mapping[str, Any]]],
    run_one: Callable[..., Path] = run,
    spend_ceiling_usd: float | None = None,
) -> Path:
    """W27-R58: every sampled case once, in the registered run order; a run whose directory
    exists is never run again. The campaign starts only after `preflight` (P1–P8) passes; it
    returns their verdicts, which `preflight.json` records before run 01 (W27-R67); a failing
    preflight writes nothing. It stops at a run outside the configuration (the run is kept and
    counts). With `spend_ceiling_usd` it also stops before a run that could take the spend past
    it (`within_spend_ceiling`); `resume` continues on the recorded `preflight.json`. Each run
    names the digests of `sample.json` and `preflight.json`. Writes `campaign.json`."""
    config.check()
    if config.model is None:
        raise HarnessError("a campaign run passes --model <pin> (registration §23.5)")
    campaign_dir = runs_root / name
    if not resume:
        checks = preflight()
        prepare_campaign(name, coverage_path, sample_path, runs_root)
        write_preflight(
            name,
            runs_root,
            model=config.model,
            claude_code_version=claude_code_version,
            checks=checks,
        )
    elif not campaign_dir.is_dir():
        raise HarnessError(f"{campaign_dir} does not exist; nothing to resume")
    preflight_path = campaign_dir / PREFLIGHT_FILE
    if not preflight_path.is_file():
        raise HarnessError(f"{preflight_path} is missing: the preflight never passed")
    coverage_path = campaign_dir / "coverage.json"
    sample_path = campaign_dir / "sample.json"
    chain = {
        "sample_sha256": registration.sha256_file(sample_path),
        "preflight_sha256": registration.sha256_file(preflight_path),
    }
    sample = json.loads(sample_path.read_text(encoding="utf-8"))
    coverage = json.loads(coverage_path.read_bytes())
    for order, case_id in enumerate(sample["run_order"], start=1):
        if (campaign_dir / f"{order:02d}-{case_id}").exists():
            continue
        if spend_ceiling_usd is not None:
            within_spend_ceiling(campaign_dir, config, spend_ceiling_usd)
        run_dir = run_one(
            case_id,
            order,
            name,
            work=work,
            config=config,
            coverage_path=coverage_path,
            pinned_claude_code_version=claude_code_version,
            runs_root=runs_root,
            operator=operator,
            chain=chain,
        )
        problems = v17.recorded_checks(run_dir)
        if problems:
            raise HarnessError(f"{run_dir.name} ran outside the configuration: {problems}")
    scores = [
        json.loads((campaign_dir / f"{k:02d}-{c}" / w27_scorer.SCORES_FILE).read_bytes())
        for k, c in enumerate(sample["run_order"], start=1)
    ]
    aggregate = w27_scorer.aggregate(
        scores,
        coverage,
        registered_runs=len(sample["run_order"]),
        surface=surface(),
    )
    (campaign_dir / w27_scorer.CAMPAIGN_FILE).write_bytes(w27_scorer.dump(aggregate))
    return campaign_dir


def surface() -> dict[str, Any]:
    """W27-R54: the served MCP tool list's SHA-256, and whether any tool lists components or
    property routes (registration F3)."""
    from openflowsheet.application.bindings import mcp  # noqa: PLC0415

    names = sorted(tool.name for tool in mcp.tools())
    return {
        "tool_descriptions_sha256": v17.tool_descriptions_sha256(),
        "tools": names,
        "lists_components_or_routes": any(
            "component" in n or "route" in n or "propert" in n for n in names
        ),
    }


def prepare_campaign(name: str, coverage_path: Path, sample_path: Path, runs_root: Path) -> Path:
    """The campaign directory with its coverage and sample (W27-R58); the canaries may already
    be there. A file already present must be byte-identical."""
    campaign_dir = runs_root / name
    campaign_dir.mkdir(parents=True, exist_ok=True)
    for source, target in ((coverage_path, "coverage.json"), (sample_path, "sample.json")):
        destination = campaign_dir / target
        if destination.exists():
            if destination.read_bytes() != source.read_bytes():
                raise HarnessError(f"{destination} differs from {source}")
        else:
            shutil.copyfile(source, destination)
    return campaign_dir


# =================================================================================================
# The order (registration §23.2; M07.A50 restated)
# =================================================================================================


def order_check(campaign_dir: Path) -> dict[str, Any]:
    """M07.A50 (W27-A78): every record of `campaign_records.digest_chain` names the SHA-256 of
    the earlier records listed for it, each equal to that file's; and the commit rule: the
    confirmation, the counted canary attempts, `preflight.json` and every campaign `run.json`
    carry `coverage.json`'s snapshot commit C_W with `tree_clean` true. `problems` names each
    broken link as `<record>#<member>` (a missing record as `<record>#missing`)."""
    records = campaign_records()
    documents: dict[str, Any] = {}

    def load(relative: str) -> Any:
        if relative not in documents:
            path = campaign_dir / relative
            documents[relative] = json.loads(path.read_bytes()) if path.is_file() else None
        return documents[relative]

    def digest(relative: str) -> str | None:
        path = campaign_dir / relative
        return registration.sha256_file(path) if path.is_file() else None

    sample = load("sample.json") or {}
    counted = [
        attempt
        for attempt in counted_attempts(
            canary_attempts(campaign_dir), sample.get("canaries", [])
        ).values()
        if attempt is not None
    ]
    canary_files = [f"{CANARY_DIR}/{a.name}/{w27_scorer.RUN_FILE}" for a in counted]
    pattern = re.compile(str(records["run_dir_pattern"]))
    run_files = sorted(
        f"{p.name}/{w27_scorer.RUN_FILE}"
        for p in (campaign_dir.iterdir() if campaign_dir.is_dir() else [])
        if p.is_dir() and pattern.match(p.name)
    )
    files = {
        "coverage": ["coverage.json"],
        "sample": ["sample.json"],
        "confirmation": [CONFIRMATION_FILE],
        "canaries": canary_files,
        "preflight": [PREFLIGHT_FILE],
        "runs": run_files,
    }
    single = {record: paths[0] for record, paths in files.items() if len(paths) == 1}
    problems = [f"{p}#missing" for p in single.values() if load(p) is None]
    for link in records["digest_chain"]:
        for relative in files[link["record"]]:
            document = load(relative)
            if document is None:
                problems.append(f"{relative}#missing")
                continue
            for member, earlier in link["names"].items():
                if member == "canaries[].run_json_sha256":
                    expected = [
                        {"attempt": a.name, "case_id": a.case_id, "run_json_sha256": digest(f)}
                        for a, f in zip(counted, canary_files, strict=True)
                    ]
                    if document.get("canaries") != expected:
                        problems.append(f"{relative}#canaries")
                elif digest(single[earlier]) is None or document.get(member) != digest(
                    single[earlier]
                ):
                    problems.append(f"{relative}#{member}")
    coverage = load("coverage.json") or {}
    commit = (coverage.get("snapshot") or {}).get("git_commit")
    for relative in [CONFIRMATION_FILE, *canary_files, PREFLIGHT_FILE, *run_files]:
        document = load(relative)
        if document is None:
            continue
        if commit is None or document.get("commit") != commit:
            problems.append(f"{relative}#commit")
        if document.get("tree_clean") is not True:
            problems.append(f"{relative}#tree_clean")
    return {"passed": not problems, "commit": commit, "problems": sorted(set(problems))}


#: W27-A23: the members a run record must carry, each non-empty.
RUN_RECORD_MEMBERS: Final[tuple[str, ...]] = (
    "lock_sha256",
    "interpreter",
    "commit",
    "tree_clean",
    "model",
    "effort",
    "claude_code_version",
    "registration_sha256",
    "coverage_sha256",
    "snapshot_sha256",
    "card_sha256",
    "prompt_sha256",
)


def a23(record: Mapping[str, Any]) -> dict[str, Any]:
    """W27-A23 on one `run.json`: every member present; the digests 64 hex digits; the lock
    hash non-empty; the interpreter's four fields; `tree_clean` a boolean."""
    problems = [m for m in RUN_RECORD_MEMBERS if m not in record or record[m] in (None, "")]
    for member in RUN_RECORD_MEMBERS:
        if member.endswith("sha256") and not (
            isinstance(record.get(member), str) and len(record[member]) == 64
        ):
            problems.append(f"{member}_not_a_sha256")
    interpreter = record.get("interpreter")
    if not isinstance(interpreter, Mapping) or set(interpreter) != {
        "executable",
        "version",
        "implementation",
        "platform",
    }:
        problems.append("interpreter_fields")
    if not isinstance(record.get("tree_clean"), bool):
        problems.append("tree_clean_not_a_boolean")
    return {"passed": not problems, "problems": sorted(set(problems))}


# =================================================================================================
# The command line (WO-17): confirm, canaries, preflight, campaign, order, spend
# =================================================================================================


def spend(campaign_dir: Path) -> dict[str, Any]:
    """The campaign's recorded spend: the sum of `total_cost_usd` of every `result.json` under
    `campaign_dir` (canaries included), Claude Code's estimate on the login (`v17.COST_BASIS`).
    A run directory without a recorded cost is listed in `uncosted`."""
    run_dirs = sorted(p.parent for p in campaign_dir.glob("**/" + w27_scorer.RUN_FILE))
    total = 0.0
    uncosted = []
    for run_dir in run_dirs:
        result = run_dir / w27_scorer.RESULT_FILE
        cost = json.loads(result.read_bytes()).get("total_cost_usd") if result.is_file() else None
        if isinstance(cost, int | float) and not isinstance(cost, bool):
            total += float(cost)
        else:
            uncosted.append(str(run_dir.relative_to(campaign_dir)))
    return {
        "cost_basis": v17.COST_BASIS,
        "runs": len(run_dirs),
        "total_cost_usd": total,
        "uncosted": uncosted,
    }


def within_spend_ceiling(campaign_dir: Path, config: AgentConfig, ceiling_usd: float) -> None:
    """Refuses the next run unless the recorded spend, plus the per-run cap for each run with no
    recorded cost and for the next run, stays within `ceiling_usd` (Frank's approval): the
    campaign then never spends past it, whatever a run costs."""
    recorded = spend(campaign_dir)
    cap = config.max_budget_usd
    bound = recorded["total_cost_usd"] + cap * (len(recorded["uncosted"]) + 1)
    if bound > ceiling_usd:
        raise HarnessError(
            f"spend ceiling USD {ceiling_usd:g}: recorded {recorded['total_cost_usd']:.2f}, "
            f"{len(recorded['uncosted'])} uncosted run(s) and the next run at the USD {cap:g} cap "
            f"bound USD {bound:.2f}; stop (Frank's approval), then --resume"
        )


def _campaign_files(runs_root: Path, name: str) -> tuple[Path, Path]:
    """`<campaign>/coverage.json` and `<campaign>/sample.json`, which must exist."""
    directory = runs_root / name
    paths = (directory / "coverage.json", directory / "sample.json")
    missing = [str(p) for p in paths if not p.is_file()]
    if missing:
        raise HarnessError(f"write the campaign's coverage and sample first: {missing}")
    return paths


def main(argv: Sequence[str] | None = None) -> int:
    from benchmarks.m06.w27 import preflight  # noqa: PLC0415 (preflight imports this module)

    parser = argparse.ArgumentParser(
        description="W27 WO-17: confirm, canaries, preflight, campaign, order, spend"
    )
    parser.add_argument("--claude", default="claude", help="the claude binary (default: claude)")
    parser.add_argument("--runs-root", type=Path, default=RUNS_ROOT, help="default: RUNS_ROOT")
    sub = parser.add_subparsers(dest="command", required=True)
    record = sub.add_parser("confirm", help="confirmation/confirmation.json (W27-R66)")
    probe = sub.add_parser("canaries", help="the canary attempts at HEAD (W27-R31, W27-R68)")
    check = sub.add_parser("preflight", help="P1-P8, written nowhere; exit 1 unless all pass")
    many = sub.add_parser("campaign", help="preflight.json, the registered runs, campaign.json")
    chain = sub.add_parser("order", help="the digest chain and the commit rule (M07.A50)")
    cost = sub.add_parser("spend", help="the recorded spend of the campaign (canaries included)")
    for each in (record, probe, check, many, chain, cost):
        each.add_argument("--campaign", required=True)
    for each in (check, many):
        each.add_argument("--model", required=True, help="the pin (registration §23.5)")
        each.add_argument("--claude-code-version", required=True, help="as the canaries ran")
    for each in (probe, many):
        each.add_argument("--work", required=True, type=Path, help="outside the repository")
        each.add_argument("--oauth-token-file", required=True, type=Path)
    many.add_argument("--resume", action="store_true")
    many.add_argument(
        "--spend-ceiling-usd",
        type=float,
        default=SPEND_CEILING_USD,
        help="stop before a run that could pass it (default: Frank's approval, USD 45)",
    )
    arguments = parser.parse_args(argv)
    runs_root: Path = arguments.runs_root
    directory = runs_root / arguments.campaign
    try:
        return _command(arguments, runs_root, directory, preflight)
    except RefusalError as refusal:
        print(refusal, file=sys.stderr)
        return 2


def _command(
    arguments: argparse.Namespace, runs_root: Path, directory: Path, preflight: Any
) -> int:
    if arguments.command == "spend":
        print(json.dumps(spend(directory), indent=1, sort_keys=True))
        return 0
    if arguments.command == "order":
        verdict = order_check(directory)
        print(json.dumps(verdict, indent=1, sort_keys=True))
        return 0 if verdict["passed"] else 1
    if arguments.command == "confirm":
        print(confirm(arguments.campaign, runs_root=runs_root))
        return 0
    coverage_path, sample_path = _campaign_files(runs_root, arguments.campaign)
    if arguments.command == "canaries":
        operator = v17.login_operator(
            arguments.oauth_token_file, agent_config(None, claude=arguments.claude)
        )
        verdicts = canaries(
            arguments.campaign,
            work=arguments.work,
            claude=arguments.claude,
            runs_root=runs_root,
            operator=operator,
        )
        print(json.dumps(verdicts, indent=1, sort_keys=True))
        return 1 if verdicts and not verdicts[-1]["passed"] else 0
    context = preflight.Campaign(
        name=arguments.campaign,
        runs_root=runs_root,
        coverage_path=coverage_path,
        sample_path=sample_path,
        model=arguments.model,
        claude_code_version=arguments.claude_code_version,
    )
    if arguments.command == "preflight":
        results = preflight.run_all(context)
        print(json.dumps(results, indent=1, sort_keys=True))
        return 0 if all(v["passed"] for v in results.values()) else 1
    config = agent_config(arguments.model, claude=arguments.claude)
    operator = v17.login_operator(arguments.oauth_token_file, config)
    campaign_dir = campaign(
        arguments.campaign,
        work=arguments.work,
        config=config,
        claude_code_version=arguments.claude_code_version,
        coverage_path=coverage_path,
        sample_path=sample_path,
        runs_root=runs_root,
        resume=arguments.resume,
        operator=operator,
        preflight=lambda: preflight.require(context),
        spend_ceiling_usd=arguments.spend_ceiling_usd,
    )
    print(campaign_dir / w27_scorer.CAMPAIGN_FILE)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
