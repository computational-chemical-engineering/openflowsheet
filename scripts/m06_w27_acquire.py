"""M06 WO-14 (W27 Tier 0, items 1 and 2): acquire OpenIDAES-450, record its provenance, and
report which artifacts are, and are not, accessible.

Design note `docs/design/M06-web-shell.md` §9 (Tier 0) and §10 WO-14; gate G13.

    python scripts/m06_w27_acquire.py          # download, verify, extract, write both JSON files
    python scripts/m06_w27_acquire.py --check  # no network: re-verify the download, re-derive both
                                               # files and require them byte-identical

The archive and everything fetched with it live in `evidence/M06/W27/artifacts/` (git-ignored,
referenced by hash). `provenance.json` and `access_report.json` are deterministic functions of those
files and of the recorded acquisition time; `--check` never regenerates that time.

Pinned: the live release asset (220 802 919 bytes). The audit (`study/openidaes450`) recorded
220 433 394 bytes and no hash; the discrepancy is disclosed in `provenance.json`
(`size_disclosure`), not hidden.
"""

from __future__ import annotations

import argparse
import csv
import datetime
import hashlib
import json
import os
import re
import sys
import tarfile
import urllib.request
from pathlib import Path
from typing import Any, Final

ROOT: Final = Path(__file__).resolve().parent.parent
OUT_DIR: Final = ROOT / "benchmarks" / "m06" / "openidaes450"
ART_DIR: Final = ROOT / "evidence" / "M06" / "W27" / "artifacts"
GH_DIR: Final = ART_DIR / "github"
EXTRACT_DIR: Final = ART_DIR / "extracted"
PROVENANCE: Final = OUT_DIR / "provenance.json"
ACCESS_REPORT: Final = OUT_DIR / "access_report.json"

REPO: Final = "Galigeigei-Z/CRAFTS-Multi-agent-for-Equation-oriented-PSE"
COMMIT_SHORT: Final = "13ca57e"
RELEASE_TAG: Final = "openidaes450-demo-2026-09-26"
ARCHIVE_NAME: Final = "OpenIDAES-450-demo.tar.gz"
ARCHIVE_ROOT: Final = "OpenIDAES-450-demo"
PINNED_SIZE: Final = 220_802_919
PINNED_SHA256: Final = "6d42c02fdc7e8e4c81c861d77fd5b546198a2bfd7d9c87212c97149e50ea4526"
AUDIT_SIZE: Final = 220_433_394
SPLIT_PATH: Final = "demo/openidaes450/splits/full82.json"
RELEASE_MANIFEST_PATH: Final = "demo/openidaes450/RELEASE_MANIFEST.json"
PAPER_ID: Final = "arXiv:2608.01369"
PAPER_TITLE: Final = (
    "CRAFTS: Collaborative Role-Adaptive Fine-Tuning of LLM Agents for Chemical Process Simulation"
)

PERMISSION: Final = {
    "date": "2026-09-26",
    "holder": "Ziyun Zhang (first author of arXiv:2608.01369; National University of Singapore)",
    "quoted_sentence": (
        "Please feel free to use the benchmark cases, including using subsets for your simulator "
        "comparisons and publishing the resulting comparisons."
    ),
    "note": "Given by e-mail to Frank Peters; the e-mail itself is held by Frank and is not "
    "recorded here.",
}
ATTRIBUTION: Final = (
    "Cite the CRAFTS paper (arXiv:2608.01369) and acknowledge IDAES and the upstream projects "
    "named in "
    "the case provenance (demo/openidaes450/THIRD_PARTY_NOTICES.md in the repository)."
)

# The per-case file set of the audit ("What each case provides"): description and specification,
# topology and arcs, unit and property-package configuration, parameters, streams, unit and state
# variables, runtime versions, solver (Ipopt) summary, and the residual check. The runtime record is
# `environment.json` or `runtime_versions.json`; either satisfies it.
CASE_FILES: Final = (
    "case.json",
    "specification.json",
    "topology.json",
    "arcs.json",
    "units.json",
    "parameters.json",
    "property_packages.json",
    "streams.csv",
    "unit_and_state_variables.csv",
    "solver_summary.json",
    "model_checks.json",
)
RUNTIME_FILES: Final = ("environment.json", "runtime_versions.json")
IMPORT_AGENT_FRAMEWORK: Final = re.compile(rb"(?m)^\s*(?:import|from)\s+(?:langgraph|langchain)")
WEIGHT_SUFFIXES: Final = (".safetensors", ".gguf", ".ckpt", ".pt", ".pth", ".bin")


class AcquireError(Exception):
    """A verification failed; nothing is recorded as if it had passed."""


def canonical(obj: Any) -> bytes:
    return (json.dumps(obj, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def http_get(url: str, dest: Path | None = None, accept: str | None = None) -> bytes:
    headers = {"User-Agent": "openflowsheet-m06-w27"}
    if accept:
        headers["Accept"] = accept
    token = os.environ.get("GITHUB_TOKEN")
    if token and "api.github.com" in url:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=120) as response:
        if dest is None:
            data: bytes = response.read()
            return data
        part = dest.with_suffix(dest.suffix + ".part")
        with part.open("wb") as f:
            while block := response.read(1 << 20):
                f.write(block)
        part.replace(dest)
    return b""


def api_json(path: str) -> Any:
    return json.loads(
        http_get(f"https://api.github.com/{path}", accept="application/vnd.github+json")
    )


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical(obj))


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


# ---- acquisition (network) -------------------------------------------------------------------


def acquire() -> None:
    GH_DIR.mkdir(parents=True, exist_ok=True)
    release = api_json(f"repos/{REPO}/releases/tags/{RELEASE_TAG}")
    assets = [a for a in release["assets"] if a["name"] == ARCHIVE_NAME]
    if len(assets) != 1:
        raise AcquireError(f"release {RELEASE_TAG} has {len(assets)} assets named {ARCHIVE_NAME}")
    asset = assets[0]
    commit = api_json(f"repos/{REPO}/commits/{COMMIT_SHORT}")
    sha = commit["sha"]
    if len(sha) != 40 or not sha.startswith(COMMIT_SHORT):
        raise AcquireError(f"commit {COMMIT_SHORT} resolved to {sha!r}")
    if asset["size"] != PINNED_SIZE:
        raise AcquireError(f"release asset size {asset['size']} != pinned {PINNED_SIZE}")

    archive = ART_DIR / ARCHIVE_NAME
    if not archive.exists() or archive.stat().st_size != PINNED_SIZE:
        http_get(asset["browser_download_url"], dest=archive)
    verify_archive(archive)
    digest = str(asset.get("digest", ""))
    if digest and digest != f"sha256:{PINNED_SHA256}":
        raise AcquireError(f"GitHub asset digest {digest} != pinned sha256:{PINNED_SHA256}")

    write_json(
        GH_DIR / "release.json",
        {
            "tag_name": release["tag_name"],
            "published_at": release["published_at"],
            "assets": [
                {
                    k: a.get(k)
                    for k in (
                        "name",
                        "size",
                        "digest",
                        "created_at",
                        "updated_at",
                        "browser_download_url",
                    )
                }
                for a in release["assets"]
            ],
        },
    )
    write_json(
        GH_DIR / "commit.json",
        {"sha": sha, "committer_date": commit["commit"]["committer"]["date"]},
    )
    tree = api_json(f"repos/{REPO}/git/trees/{sha}?recursive=1")
    if tree.get("truncated"):
        raise AcquireError("repository tree listing truncated")
    blobs = sorted((t["path"], t["size"]) for t in tree["tree"] if t["type"] == "blob")
    write_json(GH_DIR / "tree.json", [list(b) for b in blobs])
    head = api_json(f"repos/{REPO}/commits?per_page=1")[0]
    write_json(
        GH_DIR / "head.json",
        {"sha": head["sha"], "committer_date": head["commit"]["committer"]["date"]},
    )
    raw = f"https://raw.githubusercontent.com/{REPO}"
    for name, ref, path in (
        ("LICENSE", sha, "LICENSE"),
        ("full82.json", sha, SPLIT_PATH),
        ("RELEASE_MANIFEST.json", sha, RELEASE_MANIFEST_PATH),
        ("RELEASE_MANIFEST_head.json", head["sha"], RELEASE_MANIFEST_PATH),
    ):
        (GH_DIR / name).write_bytes(http_get(f"{raw}/{ref}/{path}"))

    if not (EXTRACT_DIR / ARCHIVE_ROOT).is_dir():
        EXTRACT_DIR.mkdir(parents=True, exist_ok=True)
        with tarfile.open(archive, "r:gz") as tar:
            tar.extractall(EXTRACT_DIR, filter="data")

    old = read_json(PROVENANCE)["acquisition_time_utc"] if PROVENANCE.exists() else None
    when = old or datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    emit(when)


def verify_archive(archive: Path) -> None:
    size = archive.stat().st_size
    if size != PINNED_SIZE:
        raise AcquireError(f"archive size {size} != pinned {PINNED_SIZE}")
    digest = sha256_file(archive)
    if digest != PINNED_SHA256:
        raise AcquireError(f"archive sha256 {digest} != pinned {PINNED_SHA256}")


# ---- derivation of the two JSON files (no network) -------------------------------------------


def provenance(when: str) -> dict[str, Any]:
    release = read_json(GH_DIR / "release.json")
    commit = read_json(GH_DIR / "commit.json")
    asset = next(a for a in release["assets"] if a["name"] == ARCHIVE_NAME)
    licence = GH_DIR / "LICENSE"
    manifest = read_json(GH_DIR / "RELEASE_MANIFEST.json")
    head = read_json(GH_DIR / "head.json")
    head_manifest = read_json(GH_DIR / "RELEASE_MANIFEST_head.json")
    return {
        "acquisition_time_utc": when,
        "archive": {
            "name": ARCHIVE_NAME,
            "sha256": sha256_file(ART_DIR / ARCHIVE_NAME),
            "size_bytes": (ART_DIR / ARCHIVE_NAME).stat().st_size,
            "url": asset["browser_download_url"],
        },
        "attribution": ATTRIBUTION,
        "commit": {
            "committer_date": commit["committer_date"],
            "sha": commit["sha"],
            "short": COMMIT_SHORT,
        },
        "licence": {
            "copyright_line": next(
                (
                    line.strip()
                    for line in licence.read_text(encoding="utf-8").splitlines()
                    if line.startswith("Copyright")
                ),
                None,
            ),
            "path": "LICENSE",
            "sha256": sha256_file(licence),
            "spdx": "MIT",
        },
        "paper": {"id": PAPER_ID, "title": PAPER_TITLE},
        "permission": PERMISSION,
        "release": {"published_at": release["published_at"], "tag": release["tag_name"]},
        "repository_url": f"https://github.com/{REPO}",
        "size_disclosure": {
            "asset_created_at": asset["created_at"],
            "asset_updated_at": asset["updated_at"],
            "audit_recorded_hash": None,
            "audit_recorded_size_bytes": AUDIT_SIZE,
            "pinned_size_bytes": PINNED_SIZE,
            "release_published_at": release["published_at"],
            "release_manifest_bytes_at_audited_commit": manifest["bytes"],
            "release_manifest_at_repository_head": {
                "bytes": head_manifest["bytes"],
                "committer_date": head["committer_date"],
                "sha": head["sha"],
            },
            "statement": (
                "The audit (study/openidaes450, 2026-09-26) recorded the archive as "
                f"{AUDIT_SIZE} bytes, as did RELEASE_MANIFEST.json at the audited commit. The "
                f"live release asset, pinned here, is {PINNED_SIZE} bytes: it was created and "
                "updated after the release "
                "was published and after the audited commit (timestamps above), and "
                "RELEASE_MANIFEST.json at the repository head states the pinned size. The earlier "
                "upload is therefore most likely the audited one, but the audit recorded no hash, "
                "so its bytes cannot be identified. That the pinned archive is the audited data is "
                "established only by the audit's counts reproducing (access_report.json summary)."
            ),
        },
    }


def case_row(case_dir: Path, catalog: dict[str, Any], full82: set[str]) -> dict[str, Any]:
    present: list[str] = []
    missing: list[str] = []
    errors: list[str] = []
    for name in CASE_FILES:
        path = case_dir / name
        if not path.is_file():
            missing.append(name)
            continue
        present.append(name)
        try:
            if name.endswith(".json"):
                json.loads(path.read_text(encoding="utf-8"))
            else:
                with path.open(newline="", encoding="utf-8") as f:
                    for _ in csv.reader(f):
                        pass
        except (ValueError, csv.Error, UnicodeDecodeError) as exc:
            errors.append(f"{name}: {type(exc).__name__}")
    runtime = [n for n in RUNTIME_FILES if (case_dir / n).is_file()]
    if runtime:
        present.extend(runtime)
    else:
        missing.append("|".join(RUNTIME_FILES))
    checks = case_dir / "model_checks.json"
    flag = "absent"
    if checks.is_file() and "model_checks.json" not in {e.split(":")[0] for e in errors}:
        flag = (
            "pass"
            if json.loads(checks.read_text(encoding="utf-8")).get("constraints_pass")
            else "fail"
        )
    cid = case_dir.name
    return {
        "case_id": cid,
        "family": catalog["family"],
        "files_missing": sorted(missing),
        "files_present": sorted(present),
        "in_full82": cid in full82,
        "model_type": catalog["model_type"],
        "parse_errors": sorted(errors),
        "residual_check": flag,
    }


def count(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for r in rows:
        out[str(r[key])] = out.get(str(r[key]), 0) + 1
    return dict(sorted(out.items()))


def content_scan(root: Path) -> dict[str, Any]:
    needles = (b"langgraph", b"langchain")
    mentions = 0
    imports = 0
    weights: list[str] = []
    files = 0
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        files += 1
        if path.suffix.lower() in WEIGHT_SUFFIXES:
            weights.append(path.relative_to(root).as_posix())
        if path.stat().st_size > 8 << 20:
            continue
        data = path.read_bytes()
        if any(n in data.lower() for n in needles):
            mentions += 1
        if path.suffix == ".py" and IMPORT_AGENT_FRAMEWORK.search(data):
            imports += 1
    return {
        "files_scanned": files,
        "files_importing_langgraph_or_langchain": imports,
        "files_mentioning_langgraph_or_langchain": mentions,
        "model_weight_files": weights,
    }


def inaccessible_assets(
    tree: list[list[Any]], release: dict[str, Any], scan: dict[str, Any]
) -> list[Any]:
    paths = [p for p, _ in tree]
    n_blobs = len(paths)
    top = sorted({p.split("/")[0] for p in paths})
    asset_names = [a["name"] for a in release["assets"]]
    outside = [
        p
        for p in paths
        if not p.startswith("demo/openidaes450/cases/")
        and not p.startswith("demo/openidaes450/sources/workspace/")
        and any(
            w in p.lower()
            for w in (
                "lora",
                "adapter",
                "safetensors",
                "gguf",
                "checkpoint",
                "prompt",
                "scor",
                "sft",
            )
        )
    ]
    n_hist = sum(
        "registered_originals/historical/orchestrator/runs/" in p and p.endswith("summary.json")
        for p in paths
    )
    where = [
        {
            "location": "release assets",
            "result": f"{len(asset_names)} asset(s): {', '.join(asset_names)}; no model weights "
            f"({len(scan['model_weight_files'])} weight-like files in the extracted archive)",
        },
        {
            "location": f"repository tree at {COMMIT_SHORT}",
            "result": f"{n_blobs} blobs; top level {', '.join(top)}; path search for "
            "lora/adapter/safetensors/"
            f"gguf/checkpoint/prompt/scor/sft outside cases/ and vendored sources/workspace/ found "
            f"{len(outside)} path(s)",
        },
        {
            "location": f"paper {PAPER_ID} (arXiv PDF v1, link annotations)",
            "result": f"the only repository link is https://github.com/{REPO}; no model-hub, "
            "archive "
            "or dataset link",
        },
    ]

    def entry(
        aid: str, asset: str, needed: str, note: str, extra: list[dict[str, str]] | None = None
    ) -> dict[str, Any]:
        return {
            "asset": asset,
            "id": aid,
            "needed_for": needed,
            "note": note,
            "sought_where": where + (extra or []),
            "status": "absent",
        }

    return [
        entry(
            "visual_descriptor_adapter",
            "Fine-tuned Visual Descriptor: LoRA adapter on Qwen3-VL-8B-Instruct",
            "the paper's VisualGraphIR results",
            "Named in the paper (role-specific fine-tuning); not released.",
        ),
        entry(
            "topology_agent_adapter",
            "Fine-tuned Topology Agent: LoRA adapter on Qwen2.5-Coder-7B-Instruct",
            "the paper's TopologyIR results",
            "Named in the paper; not released.",
        ),
        entry(
            "specification_agent_adapter",
            "Fine-tuned Specification Agent: LoRA adapter on Qwen2.5-Coder-7B-Instruct",
            "the paper's SpecIR results",
            "Named in the paper; not released.",
        ),
        entry(
            "sft_training_records",
            "SFT train/validation/test records (5000/1000/1000 per text adapter) and the chemical-"
            "engineering knowledge base",
            "reproducing or auditing the fine-tuned roles",
            "The 368-case complement of the 82-split is derivable by set difference from the "
            "case list; "
            "the training records and the knowledge base are not released.",
        ),
        entry(
            "role_prompts_and_workflow",
            "The seven-role LangChain/LangGraph workflow: role prompts, schemas, structured-output "
            "parsers, orchestration code",
            "running CRAFTS or its controls",
            "Absent. The release carries deterministic IDAES/Pyomo builders and gates "
            "(sources/workspace: core, stage3_specs_solve, stage4_optimization) and "
            f"{n_hist} historical orchestrator run summaries "
            f"(sources/registered_originals/historical/"
            "orchestrator/runs), which are not the manuscript score run.",
            [
                {
                    "location": "extracted archive, content scan",
                    "result": f"{scan['files_mentioning_langgraph_or_langchain']} of "
                    f"{scan['files_scanned']} files mention langgraph or langchain; "
                    f"{scan['files_importing_langgraph_or_langchain']} Python files import either",
                }
            ],
        ),
        entry(
            "scoring_harness",
            "Scoring harness: fixed-denominator completion contract, "
            "unit/stream/directed-connection F1, "
            "request-satisfaction and residual reporting",
            "reproducing the 91.5% completion and the F1 scores",
            "Absent; the paper's text defines the metrics, the code is not released.",
        ),
        entry(
            "score_run_binding_82",
            "Binding of splits/full82.json to the manuscript's score run",
            "knowing that the 82 cases are the evaluated cases",
            "Present only as a disclaimer inside full82.json: 'Registry membership recovered; "
            "exact "
            "manuscript score-run binding not independently verified.'",
        ),
        entry(
            "agent_outputs_82",
            "The agents' own outputs on the 82 cases (VisualGraphIR, TopologyIR, SpecIR, "
            "BuildPlan, "
            "SolveReport, per-case scores) and the GPT-5 mini architecture and framework controls",
            "the paper's reported results and baselines",
            "The release holds the 450 reference models and results, not the agent trajectories.",
        ),
        entry(
            "supplementary_material",
            "Supplementary material: full training settings, software versions, hardware and "
            "role-level "
            "configurations",
            "reproducing training and inference",
            "Referred to by the paper; not found as a file in the release or repository.",
        ),
    ]


def access_report() -> dict[str, Any]:
    root = EXTRACT_DIR / ARCHIVE_ROOT
    catalog = {c["case_id"]: c for c in read_json(root / "catalog.json")}
    split = read_json(GH_DIR / "full82.json")
    full82 = set(split["case_ids_in_registry_order"])
    case_dirs = sorted(p for p in (root / "cases").iterdir() if p.is_dir())
    if {p.name for p in case_dirs} != set(catalog):
        raise AcquireError("catalog.json and cases/ disagree")
    rows = [case_row(p, catalog[p.name], full82) for p in case_dirs]
    in82 = [r for r in rows if r["in_full82"]]
    scan = content_scan(root)
    return {
        "inaccessible_assets": inaccessible_assets(
            read_json(GH_DIR / "tree.json"), read_json(GH_DIR / "release.json"), scan
        ),
        "per_case_file_set": {"required": list(CASE_FILES), "runtime_one_of": list(RUNTIME_FILES)},
        "rows": rows,
        "scan_of_extracted_archive": scan,
        "source": {
            "archive_sha256": PINNED_SHA256,
            "commit_short": COMMIT_SHORT,
            "split_file": {
                "case_count": len(split["case_ids_in_registry_order"]),
                "paper_evaluation_binding": split["paper_evaluation_binding"],
                "path": SPLIT_PATH,
                "sha256": sha256_file(GH_DIR / "full82.json"),
            },
        },
        "summary": {
            "families": count(rows, "family"),
            "full82_families": count(in82, "family"),
            "full82_residual_check": count(in82, "residual_check"),
            "full82_total": len(in82),
            "model_types": count(rows, "model_type"),
            "residual_check": count(rows, "residual_check"),
            "total": len(rows),
        },
    }


def emit(when: str) -> None:
    write_json(PROVENANCE, provenance(when))
    write_json(ACCESS_REPORT, access_report())


def check() -> None:
    verify_archive(ART_DIR / ARCHIVE_NAME)
    recorded = read_json(PROVENANCE)
    for name, expected in (("size_bytes", PINNED_SIZE), ("sha256", PINNED_SHA256)):
        if recorded["archive"][name] != expected:
            raise AcquireError(f"provenance.json archive {name} is not the pinned value")
    for path, content in (
        (PROVENANCE, canonical(provenance(recorded["acquisition_time_utc"]))),
        (ACCESS_REPORT, canonical(access_report())),
    ):
        if path.read_bytes() != content:
            raise AcquireError(f"{path.relative_to(ROOT)} differs from its regeneration")
    print(
        f"OK: archive {PINNED_SIZE} bytes sha256 {PINNED_SHA256}; both JSON files reproduce "
        f"byte-identically"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0] if __doc__ else None)
    parser.add_argument("--check", action="store_true", help="re-verify and regenerate; no network")
    args = parser.parse_args()
    try:
        check() if args.check else acquire()
    except AcquireError as exc:
        print(f"FAILED: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
