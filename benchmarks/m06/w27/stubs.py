"""W27's stub sessions: the registered scorer states W27-S01…S18, with no model and no spend.

Normative text: registration §14.3 ("each state is a stub session (scripted transcript and store,
no model) scored against a registered coverage row") and design note §11 G15. Two kinds of stub,
because two kinds of store are needed:

- **Harness stubs** (S01–S10, S17, S18; the non-`CANDIDATE` row `variant_idaes_hx_ntu_e60_a80`):
  the real W27 harness (`harness.run`) launches a stand-in `claude` — a Python script that makes
  no network or model call. It reads the `mcp.json` the harness wrote, acts on the fresh project
  as `agent-w27` through the application (commit a registered SYN-001 revision, solve it, or
  alter a bundle file to simulate a system defect), and streams a scripted transcript whose last
  assistant message is the state's answer. Everything after the session — the export through
  `list_audit`, the bundle files, the replay in a fresh process, the score — is the production
  path. S17/S18 hit a short wall cap with a half-written line, as a killed session does.
- **Scripted stores** (S11–S16; the synthetic `CANDIDATE` row of W27-A13): no OpenFlowsheet build
  can commit a revision holding H₂, so the store export is written directly — a revision, a
  solve job, its RunResult, and a replay bundle written by `run.bundle.write_bundle` (so its
  integrity holds) with an empty recorded lock hash (so the system declines to replay it, and
  that certificate's system term is *not established*, as W27-R49 (s2) says). The candidate row
  is classified by the production classifier against today's snapshot plus a test route holding
  H₂ vapour; the reference streams are a stub case directory.

`run_states(root)` builds every state under `root` and scores it; `g15(results)` compares each
with the registered class and the counters §14.3 states.
"""

from __future__ import annotations

import base64
import copy
import json
import sys
import textwrap
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Final

from benchmarks.m06.w27 import coverage as classifier
from benchmarks.m06.w27 import harness, registration
from benchmarks.m06.w27 import scorer as w27_scorer
from benchmarks.t07.v17 import harness as v17

#: A pinned-looking id that names no model: the stub is never a model.
STUB_MODEL: Final[str] = "claude-w27-stub-no-model"
STUB_VERSION: Final[str] = "0.0.0-w27-stub"
STUB_ADDRESS: Final[str] = "operator@w27-stub.invalid"
NON_CANDIDATE: Final[str] = "variant_idaes_hx_ntu_e60_a80"
SYNTHETIC: Final[str] = "synthetic-w27"
TEST_PROVIDER: Final[str] = "test-pr"
#: Registered SYN-001 revisions the harness stubs commit: one ends VERIFIED, one does not.
VERIFIED_CASE: Final[str] = "benchmarks/t05/cases/SYN-001-UL-C1.yaml"
UNVERIFIED_CASE: Final[str] = "benchmarks/t05/cases/SYN-001-UL-C3X.yaml"
#: Seconds of wall cap for the states that must be killed (S17, S18).
SHORT_WALL_S: Final[float] = 3.0


@dataclass(frozen=True)
class State:
    """One registered state: the answer, the stub's actions, and what §14.3 expects."""

    state_id: str
    case: str
    expected: str
    answer: Any = None
    text: str | None = None
    actions: tuple[str, ...] = ()
    killed: bool = False
    #: Scripted-store variations (S11–S16).
    store: Mapping[str, Any] = field(default_factory=dict)
    counters: Mapping[str, Any] = field(default_factory=dict)


def _answer(case_id: str, status: str, **members: Any) -> dict[str, Any]:
    return {"case_id": case_id, "status": status, "claims": [], **members}


def _limitation(*items: tuple[str, str | None]) -> dict[str, Any]:
    return {
        "reasons": [{"kind": k, "subject": s} for k, s in items],
        "explanation": "stub answer",
    }


def states() -> list[State]:
    """§14.3's eighteen states, in order."""
    nc, sy = NON_CANDIDATE, SYNTHETIC
    s01 = _answer(nc, "limitation", limitation=_limitation(("component_unavailable", "H2O")))
    built_nc = _answer(
        nc,
        "built",
        revision_id="$revision_id",
        job_id="$job_id",
        claims=[{"kind": "verified", "job_id": "$job_id"}],
    )
    built_sy = _answer(
        sy,
        "built",
        revision_id="rev-000001",
        job_id="job-000001",
        claims=[{"kind": "verified", "job_id": "job-000001"}],
    )
    return [
        State("W27-S01", nc, "CORRECT_LIMITATION", s01),
        State(
            "W27-S02",
            nc,
            "WRONG_LIMITATION",
            _answer(nc, "limitation", limitation=_limitation(("other", "x"))),
        ),
        State(
            "W27-S03",
            nc,
            "CORRECT_LIMITATION",
            _answer(
                nc,
                "limitation",
                limitation=_limitation(
                    ("unit_unavailable", "hot_feed"), ("component_unavailable", "MEA")
                ),
            ),
            counters={"contradicted": 1},
        ),
        State("W27-S04", nc, "AGENT_FALSE_VERIFICATION", built_nc, actions=("solve_verified",)),
        State(
            "W27-S05",
            nc,
            "AGENT_FALSE_VERIFICATION",
            {**s01, "claims": [{"kind": "verified", "job_id": "$job_id"}]},
            actions=("solve_unverified",),
        ),
        State("W27-S06", nc, "WRONG_LIMITATION", _answer(nc, "failed")),
        State(
            "W27-S07",
            nc,
            "WRONG_LIMITATION",
            text="I could not represent this case.",
            counters={"agent_count": 0},
        ),
        State(
            "W27-S08",
            nc,
            "WRONG_LIMITATION",
            {**s01, "case_id": "idaes_feed_flash"},
        ),
        State(
            "W27-S09",
            nc,
            "CORRECT_LIMITATION",
            _answer(nc, "limitation", limitation=_limitation(("component_unavailable", "water"))),
        ),
        State(
            "W27-S10",
            nc,
            "WRONG_LIMITATION",
            _answer(
                nc, "limitation", limitation=_limitation(("not_steady_state_simulation", None))
            ),
        ),
        State("W27-S11", sy, "CORRECT_BUILD", built_sy),
        State("W27-S12", sy, "AGENT_FALSE_VERIFICATION", built_sy, store={"T_offset": 3.0}),
        State(
            "W27-S13",
            sy,
            "AGENT_FALSE_VERIFICATION",
            {**built_sy, "claims": []},
            store={"verification_status": "UNVERIFIED"},
        ),
        State(
            "W27-S14",
            sy,
            "AGENT_FALSE_VERIFICATION",
            built_sy,
            store={"components": ["H2", "A"]},
        ),
        State(
            "W27-S15",
            sy,
            "WRONG_LIMITATION",
            _answer(sy, "limitation", limitation=_limitation(("component_unavailable", "H2"))),
        ),
        State("W27-S16", sy, "WRONG_BUILD", _answer(sy, "failed")),
        State(
            "W27-S17",
            nc,
            "INFRASTRUCTURE_FAILURE",
            s01,
            killed=True,
            counters={"agent_established": False},
        ),
        State(
            "W27-S18",
            nc,
            "SYSTEM_FALSE_VERIFICATION",
            s01,
            actions=("solve_verified", "alter_bundle"),
            killed=True,
        ),
    ]


def final_text(state: State) -> str:
    if state.text is not None:
        return state.text
    return "Stub session.\n\n```json\n" + json.dumps(state.answer, sort_keys=True) + "\n```"


# =================================================================================================
# The stand-in `claude` (harness stubs)
# =================================================================================================

_FAKE_CLAUDE: Final[str] = r"""
import json, os, sys, time
from pathlib import Path
sys.path[:0] = [__SRC__, __ROOT__]
if sys.argv[1:] == ["--version"]:
    print(__VERSION__)
    sys.exit(0)
plan = json.loads(Path(__PLAN__).read_text(encoding="utf-8"))
argv = sys.argv
model = argv[argv.index("--model") + 1]
mcp = json.loads(Path(argv[argv.index("--mcp-config") + 1]).read_text(encoding="utf-8"))
server = mcp["mcpServers"]["procsim"]
project = Path(server["args"][server["args"].index("--project") + 1])
token_file = Path(server["env"]["OPENFLOWSHEET_TOKEN_FILE"])
def emit(entry, end="\n"):
    sys.stdout.write(json.dumps(entry) + end)
    sys.stdout.flush()
emit({"type": "system", "subtype": "init", "model": model, "apiKeySource": "none",
      "claude_code_version": __VERSION__.split(" ")[0], "permissionMode": "default",
      "mcp_servers": [{"name": "procsim", "status": "connected"}],
      "tools": ["mcp__procsim__commit_change", "mcp__procsim__submit_job",
                "mcp__procsim__get_job_result"], "memory_paths": {}})
ids = {"revision_id": None, "job_id": None}
turn = 0
def tool(name, payload, result):
    global turn
    turn += 1
    use = "toolu_%02d" % turn
    emit({"type": "assistant", "message": {"id": "msg_%02d" % turn, "content": [
        {"type": "tool_use", "id": use, "name": "mcp__procsim__" + name, "input": payload}]}})
    emit({"type": "user", "message": {"content": [
        {"type": "tool_result", "tool_use_id": use, "content": json.dumps(result)}]}})
if plan["actions"]:
    from benchmarks.t07.v17 import fixtures
    from openflowsheet.application.local import LocalApplication
    from openflowsheet.application.serving import token_capability
    from openflowsheet.application.types import Change
    with LocalApplication.open(project, capability=token_capability(project, token_file)) as app:
        for action in plan["actions"]:
            if action in ("solve_verified", "solve_unverified"):
                case = __VERIFIED__ if action == "solve_verified" else __UNVERIFIED__
                document = fixtures.load_case(case)
                change = Change(edits=fixtures.edits_to(None, document),
                                new_revision_id="rev-000001")
                committed = app.commit_change(change, None, "w27-stub-commit")
                tool("commit_change", {"case": case}, {"status": committed.status,
                     "revision_id": committed.revision_id})
                ids["revision_id"] = committed.revision_id
                ids["job_id"] = fixtures._solve(app, committed.revision_id, "w27-stub-solve")
                tool("submit_job", {"revision_id": committed.revision_id},
                     {"job_id": ids["job_id"]})
            elif action == "alter_bundle":
                events = project / "jobs" / ids["job_id"] / "bundle" / "artifacts"
                path = events / "solve-events.json"
                path.write_bytes(path.read_bytes() + b"\n")
text = plan["text"]
for key, value in ids.items():
    if value is not None:
        text = text.replace("$" + key, value)
turn += 1
emit({"type": "assistant", "message": {"id": "msg_%02d" % turn,
      "content": [{"type": "text", "text": text}]}})
if plan["killed"]:
    sys.stdout.write('{"type": "result", "subty')
    sys.stdout.flush()
    time.sleep(600)
emit({"type": "result", "subtype": "success", "is_error": False, "num_turns": turn,
      "total_cost_usd": 0.0, "duration_ms": 1, "duration_api_ms": 0,
      "usage": {"input_tokens": 0, "output_tokens": 0, "cache_creation_input_tokens": 0,
                "cache_read_input_tokens": 0}})
"""


def write_fake_claude(directory: Path, state: State) -> Path:
    """The stand-in `claude` for `state`, with its plan beside it (outside any session cwd)."""
    directory.mkdir(parents=True, exist_ok=True)
    plan = directory / f"{state.state_id}.plan.json"
    plan.write_text(
        json.dumps(
            {"actions": list(state.actions), "text": final_text(state), "killed": state.killed}
        ),
        encoding="utf-8",
    )
    source = (
        _FAKE_CLAUDE.replace("__SRC__", repr(str(registration.ROOT / "src")))
        .replace("__ROOT__", repr(str(registration.ROOT)))
        .replace("__VERSION__", repr(f"{STUB_VERSION} (Claude Code stub)"))
        .replace("__PLAN__", repr(str(plan)))
        .replace("__VERIFIED__", repr(VERIFIED_CASE))
        .replace("__UNVERIFIED__", repr(UNVERIFIED_CASE))
    )
    script = directory / f"claude-{state.state_id}"
    script.write_text(f"#!{sys.executable}\n" + textwrap.dedent(source), encoding="utf-8")
    script.chmod(0o755)
    return script


def stub_operator(directory: Path) -> v17.Operator:
    """Operator isolation with a stub address and a stub token: the code path of `v17-c2`."""
    secret = directory / "operator"
    secret.mkdir(mode=0o700, parents=True, exist_ok=True)
    token = secret / "oauth-token"
    token.write_text("w27-stub-oauth-token\n", encoding="utf-8")
    token.chmod(0o600)
    return v17.Operator(address=STUB_ADDRESS, token_file=token)


def harness_run(
    state: State, root: Path, campaign: str = "dry-run", work: Path | None = None
) -> Path:
    """One harness stub: the production `harness.run` over the stand-in `claude`. The session's
    work directory (`work`, default `root/work`) must lie outside the repository."""
    config = harness.agent_config(STUB_MODEL, claude=str(write_fake_claude(root / "bin", state)))
    if state.killed:
        config = replace(config, wall_cap_s=SHORT_WALL_S)
    return harness.run(
        state.case,
        int(state.state_id.removeprefix("W27-S")),
        campaign,
        work=root / "work" if work is None else work,
        config=config,
        coverage_path=registration.COVERAGE_JSON,
        pinned_claude_code_version=STUB_VERSION,
        runs_root=root / "runs",
        environment={"HOME": str(root / "home"), "PATH": "/usr/bin:/bin"},
        operator=stub_operator(root),
        name=state.state_id,
    )


# =================================================================================================
# Scripted stores (S11–S16)
# =================================================================================================


def synthetic_row_case() -> dict[str, Any]:
    """W27-A13's synthetic facts row, as `dry_illustration.json` stores it."""
    dry = json.loads(registration.DRY_JSON.read_bytes())
    (case,) = [s["case"] for s in dry["adversarial_states"] if s["state"] == "A13-a base row"]
    return dict(copy.deepcopy(case))


def candidate_coverage() -> dict[str, Any]:
    """A coverage document holding the synthetic `CANDIDATE` row, classified by the production
    classifier against today's snapshot plus a test route with H₂ vapour."""
    today = json.loads(registration.COVERAGE_JSON.read_bytes())["snapshot"]
    h2 = {
        "id": "H2",
        "name": "hydrogen",
        "formula": "H2",
        "cas": "1333-74-0",
        "synthetic": False,
        "phases": ["vapor"],
    }
    snapshot = {
        **today,
        "routes": [
            *today["routes"],
            {"provider_id": TEST_PROVIDER, "components": [h2], "model_ids": []},
        ],
        "basis": "TEST: today's snapshot plus a test route (W27-A13); not a registry",
    }
    methods = {**registration.provider_methods(), TEST_PROVIDER: "cubic_pr"}
    row = classifier.classify_case(synthetic_row_case(), snapshot, methods)
    if row["class"] != "CANDIDATE":
        raise RuntimeError(f"the synthetic row is {row['class']}, not CANDIDATE")
    return {
        "schema": classifier.SCHEMA,
        "snapshot": snapshot,
        "snapshot_sha256": registration.sha256_bytes(registration.dump(snapshot)),
        "list_models_sha256": snapshot["list_models_sha256"],
        "rows": [row],
        "summary": classifier.summarise([row]),
    }


def candidate_case_dir(directory: Path) -> Path:
    """The synthetic case's reference: one product port at 350 K, 1 bar, 10 mol/s of H₂."""
    case_dir = directory / SYNTHETIC
    case_dir.mkdir(parents=True, exist_ok=True)
    (case_dir / "specification.json").write_text(
        json.dumps({"terminal_product_ports": ["product.inlet"]}), encoding="utf-8"
    )
    rows = [
        "port,member,index,model_variable,value,units",
        "fs.product.inlet,temperature,0.0,fs.product.properties[0.0].temperature,350.0,K",
        "fs.product.inlet,pressure,0.0,fs.product.properties[0.0].pressure,100000.0,Pa",
        "fs.product.inlet,flow_mol_comp,\"(0.0, 'H2')\",fs.product.flow_mol_comp[H2],10.0,mol/s",
    ]
    (case_dir / "streams.csv").write_text("\n".join(rows) + "\n", encoding="utf-8")
    return case_dir


def _synthetic_bundle(
    directory: Path, revision: Mapping[str, Any], variables: Mapping[str, float], status: str
) -> dict[str, str]:
    """A replay bundle written by `write_bundle` (integrity holds) whose manifest records an
    empty lock hash (the system declines to replay it). Returns its files, base64."""
    from openflowsheet.canonical import state_sha256  # noqa: PLC0415
    from openflowsheet.run.bundle import write_bundle  # noqa: PLC0415
    from openflowsheet.run.compare import CURRENT_POLICY_ID  # noqa: PLC0415
    from openflowsheet.run.manifest import RunManifest, environment  # noqa: PLC0415

    ids = sorted(variables)
    digest = state_sha256({k: float(variables[k]) for k in ids}, ids)
    artifacts = {
        "revision.json": dict(revision),
        "solution-state.json": {
            "schema_version": "solution-state-v1",
            "state_sha256": digest,
            "variable_ids": ids,
            "variables": {k: float(variables[k]) for k in ids},
        },
        "solution-certificate.json": {
            "verification_status": status,
            "target_state_sha256": digest,
            "limitations": [],
        },
    }
    zero = "0" * 64
    manifest = RunManifest(
        run_id="run-job-000001",
        model_version="w27-stub",
        constants_sha256=zero,
        policy_id="default",
        plan_id="w27-stub",
        check_policy_sha256=zero,
        policy_sha256=zero,
        artifact_r0_sha256=zero,
        numerical_policy_id=CURRENT_POLICY_ID,
        environment=replace(environment(), lock_sha256=""),
        artifacts={},
        outcome="CONVERGED",
        verification_status=status,
    )
    write_bundle(directory, manifest, artifacts)
    return {
        path.relative_to(directory).as_posix(): base64.b64encode(path.read_bytes()).decode()
        for path in sorted(directory.rglob("*"))
        if path.is_file()
    }


def scripted_store(state: State, scratch: Path) -> dict[str, Any]:
    """The store export of a session that committed one revision and solved it."""
    from openflowsheet.verify.checks import KIND_TOLERANCE  # noqa: PLC0415

    principal = "agent-w27"
    components = list(state.store.get("components", ["H2"]))
    status = str(state.store.get("verification_status", "VERIFIED"))
    revision = {
        "revision_id": "rev-000001",
        "component_set": {"components": components},
        "instances": [
            {"id": "U-FEED", "model": {"id": "syn001.feed_source"}},
            {"id": "U-HEAT", "model": {"id": "syn001.tp_heater"}},
            {"id": "U-SINK", "model": {"id": "syn001.product_sink"}},
        ],
        "connections": [
            {"id": "S1", "from": {"instance": "U-FEED"}, "to": {"instance": "U-HEAT"}},
            {"id": "S2", "from": {"instance": "U-HEAT"}, "to": {"instance": "U-SINK"}},
        ],
    }
    variables = {
        "S1.T": 300.0,
        "S1.P": 100000.0,
        "S2.T": 350.0 + float(state.store.get("T_offset", 0.0)),
    }
    variables |= {"S2.P": 100000.0}
    for component in components:
        variables[f"S1.n.{component}"] = 10.0 if component == "H2" else 0.0
        variables[f"S2.n.{component}"] = 10.0 if component == "H2" else 0.0
    bundle_id = "job-000001:bundle"
    files = _synthetic_bundle(scratch / state.state_id / "bundle", revision, variables, status)
    members = {
        "revision_document": "revision.json",
        "solution_state": "solution-state.json",
        "solution_certificate": "solution-certificate.json",
        "run_manifest": "run-manifest.json",
    }
    artifacts = [
        {
            "artifact_id": bundle_id,
            "job_id": "job-000001",
            "kind": "replay_bundle",
            "name": "bundle",
            "sha256": "",
            "parent_artifact_id": None,
        }
    ]
    documents: dict[str, Any] = {}
    for kind, name in members.items():
        relative = name if name == "run-manifest.json" else f"artifacts/{name}"
        artifact_id = f"{bundle_id}/{name}"
        data = base64.b64decode(files[relative])
        artifacts.append(
            {
                "artifact_id": artifact_id,
                "job_id": "job-000001",
                "kind": kind,
                "name": name,
                "sha256": registration.sha256_bytes(data),
                "parent_artifact_id": bundle_id,
            }
        )
        documents[artifact_id] = json.loads(data)
    audit = [
        {"seq": 3, "principal_id": principal, "operation": "commit_change", "outcome": "allowed",
         "code": None, "effect": "revision:rev-000001"},
        {"seq": 4, "principal_id": principal, "operation": "submit_job", "outcome": "allowed",
         "code": None, "effect": "job:job-000001"},
    ]  # fmt: skip
    owner = [
        {"seq": 1, "principal_id": "local-owner", "operation": "project_init",
         "outcome": "allowed", "code": None, "effect": "project:w27-run"},
        {"seq": 2, "principal_id": "local-owner", "operation": "project_grant",
         "outcome": "allowed", "code": None, "effect": "capability:cap-agent-w27"},
    ]  # fmt: skip
    return {
        "session_start": {"audit_seq": 2, "job_ordinal": 0, "revision_ordinal": 0},
        "revisions": [
            {
                "ordinal": 1,
                "revision_id": "rev-000001",
                "principal_id": principal,
                "content_sha256": registration.sha256_bytes(registration.dump(revision)),
                "document": revision,
            }
        ],
        "refs": {"head": "rev-000001"},
        "ledger": [
            {
                "revision_id": "rev-000001",
                "status": "committed",
                "validation": {"status": "READY_FOR_SIMULATION"},
            }
        ],
        "jobs": [
            {
                "job_id": "job-000001",
                "operation": "solve",
                "principal_id": principal,
                "request": {
                    "operation": "solve",
                    "idempotency_key": "w27-stub-solve",
                    "body": {"revision_id": "rev-000001", "policy_id": "default"},
                },
                "status": "completed",
                "outputs": [{"kind": "replay_bundle", "artifact_id": bundle_id}],
                "effective_budgets": {"wall_time_s": None},
            }
        ],
        "events": {},
        "run_results": {
            "job-000001": {
                "job_id": "job-000001",
                "revision_id": "rev-000001",
                "outcome": "CONVERGED",
                "verification_status": status,
            }
        },
        "artifacts": artifacts,
        "artifact_documents": documents,
        "audit": audit,
        "audit_all": owner + audit,
        "registered_check_tolerances": dict(KIND_TOLERANCE),
        "bundle_files": {bundle_id: files},
    }


def scripted_run(state: State, root: Path, coverage: Mapping[str, Any]) -> Path:
    """A candidate state's run directory: `run.json`, transcript, result and store export."""
    run_dir = root / "runs" / "dry-run" / state.state_id
    run_dir.mkdir(parents=True)
    config = harness.agent_config(STUB_MODEL, claude="claude-stub")
    result = {
        "type": "result",
        "subtype": "success",
        "is_error": False,
        "num_turns": 1,
        "total_cost_usd": 0.0,
        "duration_ms": 1,
        "duration_api_ms": 0,
        "usage": {"input_tokens": 0, "output_tokens": 0},
    }
    init = {
        "type": "system",
        "subtype": "init",
        "model": STUB_MODEL,
        "apiKeySource": "none",
        "claude_code_version": STUB_VERSION,
        "mcp_servers": [{"name": "procsim", "status": "connected"}],
        "tools": ["mcp__procsim__commit_change"],
    }
    message = {
        "type": "assistant",
        "message": {"id": "msg_01", "content": [{"type": "text", "text": final_text(state)}]},
    }
    lines = [json.dumps(entry) for entry in (init, message, result)]
    (run_dir / w27_scorer.TRANSCRIPT_FILE).write_text("\n".join(lines) + "\n", encoding="utf-8")
    (run_dir / w27_scorer.RESULT_FILE).write_text(json.dumps(result) + "\n", encoding="utf-8")
    store = scripted_store(state, root / "scratch")
    (run_dir / w27_scorer.STORE_EXPORT_FILE).write_bytes(registration.dump(store))
    record = {
        "campaign": "dry-run",
        "case_id": state.case,
        "case_class": coverage["rows"][0]["class"],
        "scripted_store": True,
        "agent_configuration": config.as_document(),
        "model": STUB_MODEL,
        "effort": config.effort,
        "claude_code_version": STUB_VERSION,
        "pinned": {
            "model": STUB_MODEL,
            "effort": config.effort,
            "claude_code_version": STUB_VERSION,
        },
        "cost_basis": v17.COST_BASIS,
        "infrastructure_failure": None,
    }
    (run_dir / w27_scorer.RUN_FILE).write_text(
        json.dumps(record, indent=1) + "\n", encoding="utf-8"
    )
    return run_dir


# =================================================================================================
# All states, and G15's judgement
# =================================================================================================


def run_states(
    root: Path, selected: Sequence[str] | None = None, work: Path | None = None
) -> dict[str, dict[str, Any]]:
    """Build and score every state (or `selected`) under `root`: `{state: {run_dir, scores}}`.
    Harness sessions run in `work` (default `root/work`), outside the repository."""
    results: dict[str, dict[str, Any]] = {}
    coverage = candidate_coverage()
    (root / "candidate-coverage.json").parent.mkdir(parents=True, exist_ok=True)
    (root / "candidate-coverage.json").write_bytes(registration.dump(coverage))
    cases_root = candidate_case_dir(root / "cases")
    for state in states():
        if selected is not None and state.state_id not in selected:
            continue
        if state.case == SYNTHETIC:
            run_dir = scripted_run(state, root, coverage)
            scores = w27_scorer.score(run_dir, coverage, cases_root=cases_root.parent)
            (run_dir / w27_scorer.SCORES_FILE).write_bytes(w27_scorer.dump(scores))
        else:
            run_dir = harness_run(state, root, work=work)
            scores = json.loads((run_dir / w27_scorer.SCORES_FILE).read_bytes())
        results[state.state_id] = {"run_dir": str(run_dir), "scores": scores}
    return results


def judge(state: State, scores: Mapping[str, Any]) -> dict[str, Any]:
    """One state against §14.3: its class, and the counters the table states."""
    checks: dict[str, bool] = {"class": scores["outcome"] == state.expected}
    agent = scores["agent_false_verification"]
    if "contradicted" in state.counters:
        counts = (scores["limitation"] or {}).get("counts") or {}
        checks["contradicted"] = counts.get("contradicted") == state.counters["contradicted"]
    if "agent_count" in state.counters:
        checks["agent_count"] = (
            agent["established"] and agent["count"] == state.counters["agent_count"]
        )
    if "agent_established" in state.counters:
        checks["agent_established"] = agent["established"] is state.counters["agent_established"]
    return {
        "expected": state.expected,
        "outcome": scores["outcome"],
        "passed": all(checks.values()),
        "checks": checks,
    }


def g15(results: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    by_id = {s.state_id: s for s in states()}
    verdicts = {k: judge(by_id[k], v["scores"]) for k, v in sorted(results.items())}
    return {
        "passed": len(verdicts) == 18 and all(v["passed"] for v in verdicts.values()),
        "states": verdicts,
    }
