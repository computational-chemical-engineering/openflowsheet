"""Generate `evidence/M07a/<C_α>/manifest.json` at the alpha's release candidate `C_α`, by
measuring, not by transcribing. V02 alpha release spec §15 WO-10, §8.1 item 5 (T08's pattern:
`scripts/t08_evidence_manifest.py`, whose evidence readers this script imports).

The manifest carries one check per assertion of the specification's §10 catalogue (`M07a.Axx`),
read from the document itself, so that an assertion cannot be left out: an id without a check here,
or a check without an id there, stops the script. Each check is decided from the evidence that
measured it, and its `value` names that evidence:

1. **Tests, run here** (`pytest --junitxml`) at the checked-out commit, whose distribution trees
   (ADR 0021 D2.4) must equal `C_α`'s; the script refuses to run otherwise. A failed node fails its
   check, a skipped one leaves it `unsupported`, a selector that ran no node fails it.
2. **The RC records** (§8.3): the committed copies under `evidence/M07a/<C_α>/rc/`, each re-hashed
   against `rc/records.json` and read for its own verdict (T08's `_record`: `passed` and every
   check `pass`, `commit` = `C_α`, `tree_clean`; the A30 summaries' `verdict.pass`; the CI `check`
   logs' `check.sh: PASSED`; the `identity` log's G05 line).
3. **CI**, read only from the runs named on the command line (`--ci-run ID`): a run counts only if
   its head is `C_α`.
4. **Direct measurements**: M07a.A43's provenance over every `t08-rc-v1` and dist record (the class
   registered and agreeing, R-347), MR-11's step 12 in step 10's inputs and its committed kept
   certificates re-audited, counted and bound to the step-12 record (R-348), MR-12's extras, the
   push run at `C_α`.
5. **The design lane's verdicts** (A60–A63) are `unsupported` with the state `pending`; this script
   does not judge them.
6. **At the tag candidate** (Amendment 3 §19.4, R-373): M07a.A52 and the ledger (M07a.A64) are
   judged by their tests (`tests/test_m07a_changelog.py`, `tests/test_m07a_ledger.py`) run here,
   once §9.2 step 5 is done: the `## v0.2.0a1` heading names `C_α` and the ledger cites
   `evidence/M07a/<C_α>/manifest.json`. Until then each is `unsupported` with the state `pending`.
   Once judged, each check's value carries `judged_at`, the commit the tests ran at (the candidate).

Status is `tested` iff every check M07a.A00–A51 and A53 is `pass` (Amendment 3 §19.4, R-373);
otherwise `implemented`. A52 and A64 are outside that set, so judging them cannot change it.
`reviewed` is never set, and both review fields stay `pending`.

Usage:
    PYTHONPATH=src:. .venv/bin/python scripts/m07a_evidence_manifest.py --commit C_α \\
        --ci-run 38667458248 --ci-run 38667452347 [--out PATH]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tomllib
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import t08_evidence_manifest as t08  # noqa: E402
import v0_1_gate  # noqa: E402

SPEC = ROOT / "docs" / "derivations" / "V02-alpha-release-spec.md"
RC_RECORD = ROOT / "docs" / "v02-alpha-rc-record.md"
VERDICTS = ROOT / "docs" / "reviews" / "V02-alpha-verdicts.md"
ENVELOPE = ROOT / "benchmarks" / "t08" / "support_envelope.yaml"
LEDGER = ROOT / "docs" / "requirements.yaml"
CHANGELOG = ROOT / "CHANGELOG.md"
#: The release-gate requirements T08's manifest supplies evidence for; the alpha re-runs T08's
#: acceptance at `C_α` (build decision B-WO10-9).
REQUIREMENTS = ("D04", "A10", "D17", "D20")
#: R-373 (Amendment 3 §19.4): the manifest is `tested` iff A00–A51 and A53 pass; A52 is judged at
#: the candidate, and the verdicts and the ledger come after the manifest.
STATUS_IDS = re.compile(r"A(?:[0-4]\d|5[013])$")
#: The checks judged at the tag candidate after §9.2 step 5, each by its tests (§19.4).
AT_CANDIDATE = ("A52", "A64")
#: The tag whose extras MR-12 compares against.
V0_1_1 = "v0.1.1"
CHECK_JOBS = ("check (ubuntu-latest)", "check (ubuntu-24.04-arm)")
STEPS_JOBS = ("rc-steps (ubuntu-latest)", "rc-steps (ubuntu-24.04-arm)")
INSTALL_JOBS = ("clean-install (ubuntu-latest)", "clean-install (ubuntu-24.04-arm)")
REPLAY_JOBS = ("bundle-replay (ubuntu-latest)", "bundle-replay (ubuntu-24.04-arm)")


# ----------------------------------------------------------------------------- the catalogue


@dataclass(frozen=True)
class Spec:
    """One assertion's evidence; its result is the worst of the parts."""

    id: str
    tests: tuple[str, ...] = ()
    records: tuple[str, ...] = ()
    jobs: tuple[str, ...] = ()
    measure: str | None = None


_GATE = "tests/test_m07a_v0_2_gate.py::test_"
_REL = "tests/test_release_workflows.py::test_"
_RCR = "tests/test_m07a_rc_records.py::test_"
_CI_STEPS = ("ci/rc-steps-ubuntu-latest", "ci/rc-steps-ubuntu-24.04-arm")

SPECS: tuple[Spec, ...] = (
    Spec(
        "A00",
        tests=(
            "tests/test_t08_reference_generators.py::test_a00_generator_check_passes"
            "[v02a_reference.py]",
        ),
    ),
    *(Spec(f"A{n:02d}", tests=(f"{_GATE}a{n:02d}_*",)) for n in range(1, 15)),
    Spec("A20", tests=(f"{_REL}m07a_a20_*",)),
    Spec("A21", tests=(f"{_REL}m07a_a21_*",)),
    Spec("A22", tests=("tests/test_changelog_section.py::test_m07a_a22_*",)),
    Spec("A23", tests=(f"{_REL}m07a_a23_*",)),
    Spec("A24", tests=(f"{_REL}dispatch_only_a_dry_run_by_default_and_c_by_default",)),
    Spec(
        "A30",
        records=("ci/job-logs/check-ubuntu-latest.log", "ci/job-logs/check-ubuntu-24.04-arm.log"),
        jobs=CHECK_JOBS,
        measure="push_run",
    ),
    Spec(
        "A31",
        records=(
            "identity/rc-identity.json",
            *(f"{d}/identity/rc-identity.json" for d in _CI_STEPS),
            "ci/job-logs/identity.log",
        ),
        jobs=("identity", *STEPS_JOBS),
    ),
    Spec("A32", records=("ci/rc-dist/t08-a43-dist.json",), jobs=("dist",), measure="a43_version"),
    Spec(
        "A33",
        records=tuple(
            f"ci/rc-install-{arch}/{name}-{arch}.json"
            for arch in ("ubuntu-latest", "ubuntu-24.04-arm")
            for name in ("install", "lock-installed", "lock-checkout")
        ),
        jobs=INSTALL_JOBS,
    ),
    Spec(
        "A34",
        records=(
            "ci/rc-bundles/index.json",
            "ci/rc-replay-ubuntu-latest/replay-ubuntu-latest.json",
            "ci/rc-replay-ubuntu-24.04-arm/replay-ubuntu-24.04-arm.json",
        ),
        jobs=("bundle-set", *REPLAY_JOBS),
    ),
    Spec(
        "A35",
        records=(
            "ensemble/rc-ensemble-ref-x86-64.json",
            "ci/rc-ensemble-ubuntu-24.04-arm/rc-ensemble-ci-aarch64.json",
        ),
        jobs=("rc-ensemble",),
        measure="cp_bound",
    ),
    Spec(
        "A36",
        records=(
            "corpus-ref-x86-64.json",
            "ci/rc-steps-ubuntu-latest/corpus-ubuntu-latest.json",
            "ci/rc-steps-ubuntu-24.04-arm/corpus-ubuntu-24.04-arm.json",
        ),
        jobs=STEPS_JOBS,
    ),
    Spec(
        "A37",
        tests=("tests/test_m07a_surface_chain.py",),
        records=(
            "surface/rc-alpha-surface.json",
            *(f"{d}/surface/rc-alpha-surface.json" for d in _CI_STEPS),
        ),
        jobs=STEPS_JOBS,
    ),
    Spec(
        "A38",
        records=(
            "a30/t08-a30-x86_64.json",
            "ci/rc-steps-ubuntu-latest/a30/t08-a30-x86_64.json",
            "ci/rc-steps-ubuntu-24.04-arm/a30/t08-a30-aarch64.json",
        ),
        jobs=STEPS_JOBS,
        measure="mr12_extras",
    ),
    Spec(
        "A39",
        records=(
            "certificates-ref-x86-64.json",
            *(f"{d}/certificates-{d.split('rc-steps-')[1]}.json" for d in _CI_STEPS),
            "ci/rc-install-ubuntu-latest/certificates-ubuntu-latest.json",
            "ci/rc-install-ubuntu-24.04-arm/certificates-ubuntu-24.04-arm.json",
            "ci/rc-bundle-set-certificates/rc-certificates.json",
        ),
        measure="mr11_step12",
    ),
    Spec("A40", records=("step11/rc-step11.json",)),
    Spec("A41", records=("step12/rc-step12.json",)),
    Spec("A42", tests=("tests/test_m07a_v011_bundle.py",)),
    Spec("A43", tests=(f"{_RCR}a43_*",), measure="provenance"),
    Spec("A44", tests=(f"{_RCR}a44_*",)),
    Spec(
        "A50",
        tests=("tests/test_m07a_harvest.py", "tests/test_t08_w2_support_envelope.py"),
        measure="envelope",
    ),
    Spec("A51", tests=("tests/test_t08_b50_surface_content.py::test_m07a_a51_*",)),
    Spec("A52", tests=("tests/test_m07a_changelog.py",), measure="changelog"),
    Spec(
        "A53",
        tests=(
            "tests/test_t08_w4_changelog.py::test_the_gate_table_is_what_the_gate_script_prints",
            "tests/test_t08_w4_changelog.py::test_the_gate_table_does_not_read_the_live_ledger",
        ),
    ),
    *(Spec(f"A6{n}", measure="verdict") for n in range(4)),
    Spec("A64", tests=("tests/test_m07a_ledger.py",), measure="ledger"),
)


def catalogue() -> dict[str, tuple[str, str]]:
    """`M07a.<id>` → (subject, judged by), from §10 of the specification."""
    found: dict[str, tuple[str, str]] = {}
    for line in SPEC.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^\| M07a\.(A\d\d) \|", line)
        if match:
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            found[match[1]] = (cells[1], cells[-1])
    return dict(sorted(found.items()))


def _test_modules() -> list[str]:
    """Every module a selector names, once."""
    return sorted({selector.split("::")[0] for spec in SPECS for selector in spec.tests})


# ----------------------------------------------------------------------------- inputs


@dataclass
class Inputs:
    """What the checks judge (the attributes T08's readers use). `main` measures it."""

    commit: str
    tests: t08.TestRun
    ci: list[dict[str, Any]] = field(default_factory=list)
    manifest_exists: bool = False
    evidence: Path = ROOT / "evidence" / "M07a"
    #: The commit the tests ran at: the tag candidate once §9.2 step 5 is done (§19.4).
    judged_at: str | None = None

    @property
    def rc_dir(self) -> Path:
        return self.evidence / self.commit / "rc"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json(inputs: Inputs, path: str) -> dict[str, Any]:
    loaded = json.loads((inputs.rc_dir / path).read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def _check(document: Mapping[str, Any], check_id: str) -> Mapping[str, Any]:
    (found,) = [entry for entry in document["checks"] if entry["id"] == check_id]
    assert isinstance(found, dict)
    return found


# ----------------------------------------------------------------------------- measurements

Part = tuple[str, dict[str, Any]]


def _m_push_run(inputs: Inputs) -> Part:
    pushes = [run for run in inputs.ci if run.get("headSha") == inputs.commit]
    pushes = [run for run in pushes if run.get("event") == "push"]
    value = {"push_runs": {str(run.get("databaseId")): run.get("conclusion") for run in pushes}}
    if not pushes:
        return "unsupported", {**value, "state": "pending", "reason": "no push run at C was given"}
    return ("pass" if any(run.get("conclusion") == "success" for run in pushes) else "fail"), value


def _m_a43_version(inputs: Inputs) -> Part:
    """M07a.A32: `a43.version` gives `0.2.0a1` from every source it reads."""
    versions = _check(_json(inputs, "ci/rc-dist/t08-a43-dist.json"), "a43.version")["versions"]
    ok = len(versions) >= 3 and set(versions.values()) == {"0.2.0a1"}
    return ("pass" if ok else "fail"), {"a43.version": versions}


def _m_cp_bound(inputs: Inputs) -> Part:
    """M07a.A35: the Clopper–Pearson bound is reported in each class's report (never gated)."""
    found: dict[str, str | None] = {}
    for path in (
        "ensemble/rc-ref-x86-64.report.txt",
        "ci/rc-ensemble-ubuntu-24.04-arm/rc-ci-aarch64.report.txt",
    ):
        text = (inputs.rc_dir / path).read_text(encoding="utf-8")
        line = next((ln for ln in text.splitlines() if "Clopper" in ln), None)
        found[path] = line.strip() if line else None
    return ("pass" if all(found.values()) else "fail"), {"reported": found}


def _extras(pyproject: str) -> list[str]:
    return sorted(tomllib.loads(pyproject)["project"].get("optional-dependencies", {}))


def _m_mr12_extras(inputs: Inputs) -> Part:
    """MR-12: every extra `C_α` declares and `v0.1.1` did not needs its own [A10] audit; none is
    accepted here, so a new extra fails this part."""
    ours = _extras(t08._git("show", f"{inputs.commit}:pyproject.toml"))
    theirs = _extras(t08._git("show", f"{V0_1_1}:pyproject.toml"))
    new = sorted(set(ours) - set(theirs))
    value = {"extras_at_c": ours, "extras_at_v0_1_1": theirs, "new_since_v0_1_1": new}
    return ("pass" if not new else "fail"), value


#: MR-12 at the M07 release candidate (M07 spec §24.1 action 4, R-478): each extra declared since
#: `v0.1.1` and the [A10] audit, inventory, RC check and recorded licence decision that close it.
MR12_AUDITS: dict[str, dict[str, str]] = {
    "nlp": {
        "audit": "docs/m03-ipopt-audit.md",
        "inventory": "benchmarks/m03/ipopt-inventory-x86_64.json",
        "check": "a60.w24.nlp_tier_and_inventory",
        "decision": "R-450",
    }
}
#: Step 14's RC record, which carries each audit's inventory check (M07 spec §24.1).
STEP14_RECORD = "step14/rc-step14.json"
#: Step 9's three A30 summaries (M07a.A38's records).
A30_SUMMARIES = (
    "a30/t08-a30-x86_64.json",
    "ci/rc-steps-ubuntu-latest/a30/t08-a30-x86_64.json",
    "ci/rc-steps-ubuntu-24.04-arm/a30/t08-a30-aarch64.json",
)
#: S9.2 and S9.3: what each A30 summary's `measured_project_load` must say at the M07 RC.
A30_NLP_EXTRA_MODULES = {
    "openflowsheet.studies.nlp.greybox": "cyipopt",
    "openflowsheet.studies.trust_region.projection": "pyomo",
    "openflowsheet.studies.trust_region.trf": "pyomo",
}
A30_MODULES_WALKED = 182
A30_MODULES_IMPORTED = 179


def mr12_extras_v02(
    commit: str,
    new: Sequence[str],
    show: Callable[[str], str | None],
    step14: Mapping[str, Any],
    summaries: Mapping[str, Mapping[str, Any] | None],
) -> Part:
    """MR-12 at the M07 RC (§24.1 action 4, S9.2–S9.4). `show(path)` is the file at `commit`, or
    `None`. Every new extra needs an `MR12_AUDITS` entry (without one it fails, the alpha's rule);
    for each entry both files exist at `commit`, step 14's record has the check `pass` and its
    provenance names `commit`, and the register at `commit` has the decision's `## R-… — ` line.
    Each A30 summary of step 9 says S9.2's `nlp_extra_modules` and S9.3's counts."""
    register = show("docs/decision-register.md") or ""
    provenance = step14.get("provenance") or {}
    results = {entry.get("id"): entry.get("result") for entry in step14.get("checks", [])}
    extras: dict[str, dict[str, Any]] = {}
    ok = True
    for extra in new:
        audit = MR12_AUDITS.get(extra)
        if audit is None:
            extras[extra] = {"audit": None, "reason": "no MR12_AUDITS entry"}
            ok = False
            continue
        files = {key: show(audit[key]) is not None for key in ("audit", "inventory")}
        check = results.get(audit["check"])
        decided = any(
            line.startswith(f"## {audit['decision']} — ") for line in register.splitlines()
        )
        extras[extra] = {
            **audit,
            "files_at_commit": files,
            "check_result": check,
            "step14_commit": provenance.get("commit"),
            "decision_in_register": decided,
        }
        ok = ok and all(files.values()) and check == "pass" and decided
        ok = ok and provenance.get("commit") == commit
    a30: dict[str, Any] = {}
    for path, summary in summaries.items():
        load = (summary or {}).get("measured_project_load", {})
        said = {
            "nlp_extra_modules": load.get("nlp_extra_modules"),
            "modules_walked": load.get("modules_walked"),
            "modules_imported": load.get("modules_imported"),
            "solve_exit": load.get("solve_exit"),
        }
        a30[path] = said
        ok = ok and said == {
            "nlp_extra_modules": A30_NLP_EXTRA_MODULES,
            "modules_walked": A30_MODULES_WALKED,
            "modules_imported": A30_MODULES_IMPORTED,
            "solve_exit": 0,
        }
    value = {"new_since_v0_1_1": list(new), "extras": extras, "a30_summaries": a30}
    return ("pass" if ok and bool(summaries) else "fail"), value


def _m_mr12_extras_v02(inputs: Inputs) -> Part:
    """`mr12_extras_v02` at `inputs.commit`, from git and the committed RC records. Not in the
    alpha's `SPECS`: the alpha's records stay judged by `_m_mr12_extras`."""
    ours = _extras(t08._git("show", f"{inputs.commit}:pyproject.toml"))
    theirs = _extras(t08._git("show", f"{V0_1_1}:pyproject.toml"))
    new = sorted(set(ours) - set(theirs))

    def show(path: str) -> str | None:
        if not t08._git_ok("cat-file", "-e", f"{inputs.commit}:{path}"):
            return None
        return t08._git("show", f"{inputs.commit}:{path}")

    def read(path: str) -> dict[str, Any] | None:
        return _json(inputs, path) if (inputs.rc_dir / path).is_file() else None

    step14 = read(STEP14_RECORD) or {}
    summaries = {path: read(path) for path in A30_SUMMARIES}
    return mr12_extras_v02(inputs.commit, new, show, step14, summaries)


#: MR-12 v03 (V03 spec §9.3, S07 F-9, R-879): each extra declared since `v0.2.0` and the audit,
#: inventory, check and recorded decision that close it. A table of its own, so that the v02
#: measure, judged at `RELEASE_0_2_0_COMMIT`, is not re-judged (R-879's rejected alternative).
#: `check` is the command whose result step 17c's RC record carries under that id.
MR12_AUDITS_V03: dict[str, dict[str, str]] = {
    "coolprop": {
        "audit": "docs/derivations/S07-spec.md",
        "audit_section": "§17",
        "inventory": "docs/s07-coolprop-licences.json",
        "check": "scripts/t07_licence_inventory.py --extra coolprop",
        "decision": "R-624",
    },
    "lca": {
        "audit": "docs/derivations/E01-design.md",
        "audit_section": "§4.8.4 and WO-B1",
        "inventory": "docs/e01-lca-licences.json",
        "check": "scripts/e01_d04_inventory.py --check",
        "decision": "R-900",
    },
}
V0_2_0 = "v0.2.0"
#: Step 17c's RC record (V03 spec §4), which carries each v03 audit's check at C.
STEP17C_RECORD = "step17/rc-step17c.json"


def mr12_extras_v03(
    commit: str,
    new: Sequence[str],
    show: Callable[[str], str | None],
    step17c: Mapping[str, Any],
) -> Part:
    """MR-12 v03 (V03 spec §9.3, step 17c). `show(path)` is the file at `commit`, or `None`.
    Every extra new since `v0.2.0` needs an `MR12_AUDITS_V03` entry (without one it fails); for
    each entry both files exist at `commit`, step 17c's record has the check `pass` and its
    provenance names `commit`, and the register at `commit` has the decision's `## R-… — ` line."""
    register = show("docs/decision-register.md") or ""
    provenance = step17c.get("provenance") or {}
    results = {entry.get("id"): entry.get("result") for entry in step17c.get("checks", [])}
    extras: dict[str, dict[str, Any]] = {}
    ok = True
    for extra in new:
        audit = MR12_AUDITS_V03.get(extra)
        if audit is None:
            extras[extra] = {"audit": None, "reason": "no MR12_AUDITS_V03 entry"}
            ok = False
            continue
        files = {key: show(audit[key]) is not None for key in ("audit", "inventory")}
        check = results.get(audit["check"])
        decided = any(
            line.startswith(f"## {audit['decision']} — ") for line in register.splitlines()
        )
        extras[extra] = {
            **audit,
            "files_at_commit": files,
            "check_result": check,
            "step17c_commit": provenance.get("commit"),
            "decision_in_register": decided,
        }
        ok = ok and all(files.values()) and check == "pass" and decided
        ok = ok and provenance.get("commit") == commit
    value = {"new_since_v0_2_0": list(new), "extras": extras}
    return ("pass" if ok else "fail"), value


def mr12_extras_v03_at(commit: str, step17c: Mapping[str, Any]) -> Part:
    """`mr12_extras_v03` at `commit`, its new extras and files read from git, over the step 17c
    record `step17c` (V03 spec §9.3). `scripts/v03_rc.py step17c` calls it on the record it is
    writing, and the measure on the committed record."""
    ours = _extras(t08._git("show", f"{commit}:pyproject.toml"))
    theirs = _extras(t08._git("show", f"{V0_2_0}:pyproject.toml"))
    new = sorted(set(ours) - set(theirs))

    def show(path: str) -> str | None:
        if not t08._git_ok("cat-file", "-e", f"{commit}:{path}"):
            return None
        return t08._git("show", f"{commit}:{path}")

    return mr12_extras_v03(commit, new, show, step17c)


def _m_mr12_extras_v03(inputs: Inputs) -> Part:
    """`mr12_extras_v03` at `inputs.commit`, from git and step 17c's committed RC record (a
    missing record fails: its checks are absent)."""
    record = inputs.rc_dir / STEP17C_RECORD
    step17c = _json(inputs, STEP17C_RECORD) if record.is_file() else {}
    return mr12_extras_v03_at(inputs.commit, step17c)


STEP12_CERTIFICATES = "step12/certificates"
STEP12_BUNDLE = "g12-bundles/m02-g12-0/bundle/solution-certificate.json"


def _m_mr11_step12(inputs: Inputs) -> Part:
    """MR-11 and R-348 (spec §18.2 items 2–4): step 10's local audit read step 12's output among its
    inputs; the committed kept copies of step 12's certificates (`rc/step12/certificates/<kept
    bundle path>/solution-certificate.json`) pass T08.A34's rule again here
    (`t08_rc.audit_certificate`, imported), their number is 3 + the edges record's `len(edges)`,
    and the `m02-g12-0` bundle's `document_sha256` equals the step-12 G12 record's
    `certificate_sha256`. The other certificates' hashes are listed, not judged."""
    import t08_rc  # noqa: PLC0415

    from openflowsheet.canonical import document_sha256  # noqa: PLC0415

    record = _json(inputs, "certificates-ref-x86-64.json")
    step12 = [path for path in record.get("inputs", []) if path.rstrip("/").endswith("/step12")]
    audited = _check(record, "a34.certificates_audited").get("certificates")
    kept = inputs.rc_dir / STEP12_CERTIFICATES
    paths = sorted(kept.rglob("solution-certificate.json")) if kept.is_dir() else []
    validator = t08_rc._schema_validator()  # noqa: SLF001
    violations: dict[str, list[str]] = {}
    hashes: dict[str, str] = {}
    for path in paths:
        document = json.loads(path.read_text(encoding="utf-8"))
        shown = path.relative_to(kept).as_posix()
        hashes[shown] = document_sha256(document)
        problems = t08_rc.audit_certificate(document, validator)
        if problems:
            violations[shown] = problems
    edges = _json(inputs, "step12/g12-real-loop-v3-edges.json").get("edges", [])
    expected = 3 + len(edges)
    recorded = _json(inputs, "step12/g12-real-loop-v3.json").get("certificate_sha256")
    bound = recorded is not None and hashes.get(STEP12_BUNDLE) == recorded
    value = {
        "step12_inputs": step12,
        "audited": audited,
        "step12_certificates": len(paths),
        "step12_certificates_expected": expected,
        "step12_violations": violations,
        "bundle_document_sha256": hashes.get(STEP12_BUNDLE),
        "recorded_certificate_sha256": recorded,
        "document_sha256": hashes,
    }
    ok = bool(step12) and len(paths) == expected and not violations and bound
    return ("pass" if ok else "fail"), value


def _m_provenance(inputs: Inputs) -> Part:
    """M07a.A43: every committed `t08-rc-v1` record (and the A43 dist record) carries `commit` =
    `C_α`, `tree_clean` true, the lock's SHA-256 and its machine class. The class (spec §18.3,
    R-347) is a key of the registry's `ensemble.machine_classes`, and agrees with the record's
    `architecture` (or the dist record's `machine`) and `github_actions` where it carries them."""
    sys.path.insert(0, str(ROOT))
    from benchmarks.t06 import ensemble  # noqa: PLC0415

    classes = ensemble.registered()["machine_classes"]
    lock = _sha256(ROOT / "requirements.lock")
    unattributable: list[str] = []
    no_class: list[str] = []
    unregistered: list[str] = []
    disagreeing: list[str] = []
    seen = 0
    for path in sorted(inputs.rc_dir.rglob("*.json")):
        document = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(document, dict) or document.get("format") not in (
            "t08-rc-v1",
            "t08-a43-dist-v1",
        ):
            continue
        seen += 1
        shown = path.relative_to(inputs.rc_dir).as_posix()
        provenance = document.get("provenance") or document
        if (
            provenance.get("commit"),
            provenance.get("tree_clean"),
            provenance.get("environment_lock_sha256"),
        ) != (inputs.commit, True, lock):
            unattributable.append(shown)
        label = provenance.get("machine_class") or document.get("machine_class")
        if not label:
            no_class.append(shown)
            continue
        if label not in classes:
            unregistered.append(shown)
            continue
        registered = classes[label]
        architecture = provenance.get("architecture") or document.get("machine")
        on_ci = provenance.get("github_actions")
        if (architecture is not None and architecture != registered["architecture"]) or (
            on_ci is not None and bool(on_ci) != bool(registered["github_actions"])
        ):
            disagreeing.append(shown)
    value = {
        "records": seen,
        "not_attributable": unattributable,
        "no_machine_class": no_class,
        "unregistered_machine_class": unregistered,
        "machine_class_disagrees": disagreeing,
    }
    ok = seen and not (unattributable or no_class or unregistered or disagreeing)
    return ("pass" if ok else "fail"), value


def _m_envelope(inputs: Inputs) -> Part:
    """MR-3: the envelope pinned to the alpha at `C_α`."""
    import yaml  # noqa: PLC0415

    document = yaml.safe_load(t08._git("show", f"{inputs.commit}:{ENVELOPE.relative_to(ROOT)}"))
    value = {"envelope_id": document.get("envelope_id"), "release": document.get("release")}
    ok = value == {"envelope_id": "v0.2-alpha-envelope-1", "release": "0.2.0a1"}
    return ("pass" if ok else "fail"), value


def _m_verdict(inputs: Inputs) -> Part:
    if not VERDICTS.is_file():
        return "unsupported", {
            "state": "pending",
            "reason": f"{VERDICTS.relative_to(ROOT)} does not exist (the verdict agent, §6.3)",
        }
    return "unsupported", {"state": "pending", "reason": "judged by the verdict agent, not here"}


def _m_changelog(inputs: Inputs) -> Part:
    """R-373: A52 (c) and (a) need the gate table and `C_α` pasted at the candidate, after the
    verdicts; until the heading names `C_α` it is recorded `unsupported`. Then its tests decide,
    and this part records where they ran."""
    text = CHANGELOG.read_text(encoding="utf-8")
    heading = next((ln for ln in text.splitlines() if ln.startswith("## v0.2.0a1")), "")
    if "[[PENDING: " in heading:
        return "unsupported", {
            "state": "pending",
            "reason": "judged at the candidate after §9.2 step 5 (Amendment 3 §19.4)",
        }
    named = f"`C_α` = `{inputs.commit}`" in heading
    return ("pass" if named else "fail"), {"names_c": named}


def _m_ledger(inputs: Inputs) -> Part:
    """M07a.A64, after WO-11: its tests decide, and this part records where they ran."""
    wanted = f"evidence/M07a/{inputs.commit}/manifest.json"
    if wanted not in LEDGER.read_text(encoding="utf-8"):
        return "unsupported", {
            "state": "pending",
            "reason": f"the ledger does not cite {wanted} (WO-11)",
        }
    return "pass", {"cites": wanted}


MEASURES: dict[str, Callable[[Inputs], Part]] = {
    "push_run": _m_push_run,
    "a43_version": _m_a43_version,
    "cp_bound": _m_cp_bound,
    "mr12_extras": _m_mr12_extras,
    "mr12_extras_v02": _m_mr12_extras_v02,
    "mr12_extras_v03": _m_mr12_extras_v03,
    "mr11_step12": _m_mr11_step12,
    "provenance": _m_provenance,
    "envelope": _m_envelope,
    "verdict": _m_verdict,
    "changelog": _m_changelog,
    "ledger": _m_ledger,
}


# ----------------------------------------------------------------------------- the checks


def decide(spec: Spec, subject: str, judged_by: str, inputs: Inputs) -> dict[str, Any]:
    parts: list[str] = []
    value: dict[str, Any] = {"judged_by": judged_by}
    sources: list[tuple[str, Callable[[], Part]]] = []
    if spec.tests:
        sources.append(("tests", lambda: t08._tests(spec.tests, inputs)))  # type: ignore[arg-type]
    if spec.records:
        sources.append(("records", lambda: t08._records(spec.records, inputs)))  # type: ignore[arg-type]
    if spec.jobs:
        sources.append(("ci", lambda: t08._jobs(spec.jobs, inputs)))  # type: ignore[arg-type]
    if spec.measure is not None:
        measure = spec.measure
        sources.append(("measured", lambda: MEASURES[measure](inputs)))
    for name, read in sources:
        try:
            result, said = read()
        except Exception as error:  # noqa: BLE001 - evidence that could not be read did not pass
            result, said = "fail", {"error": f"{type(error).__name__}: {error}"}
        parts.append(result)
        value[name] = said
    if spec.id in AT_CANDIDATE and value.get("measured", {}).get("state") != "pending":
        value["judged_at"] = inputs.judged_at
    description = re.sub(r"<([^<>]*)>", r"{\1}", subject)
    return {
        "id": f"M07a.{spec.id}",
        "description": description,
        "result": t08._result(parts),
        "value": value,
    }


def checks(inputs: Inputs) -> list[dict[str, Any]]:
    listed = catalogue()
    specs = {spec.id: spec for spec in SPECS}
    if set(listed) != set(specs) or len(specs) != len(SPECS):
        raise SystemExit(
            "the catalogue and the checks differ: catalogue only "
            f"{sorted(set(listed) - set(specs))}, checks only {sorted(set(specs) - set(listed))}"
        )
    return [decide(specs[i], subject, judged, inputs) for i, (subject, judged) in listed.items()]


def status(entries: Sequence[Mapping[str, Any]]) -> str:
    """`tested` iff every check M07a.A00–A51 and A53 passes (R-373); never `reviewed`."""
    gated = [entry for entry in entries if STATUS_IDS.fullmatch(entry["id"].split(".")[1])]
    return "tested" if gated and all(e["result"] == "pass" for e in gated) else "implemented"


def limitations(entries: Sequence[Mapping[str, Any]]) -> list[str]:
    found = [
        "Evidence class: numerical and software verification at the alpha's release candidate "
        "C_α (tests run here, the RC job's records on ref-x86-64, ci-x86-64 and ci-aarch64, CI); "
        "the design lane's verdicts (A60-A63) are not judged here; M07a.A52 and A64 are judged at "
        "the tag candidate after §9.2 step 5, by their tests run here (Amendment 3 §19.4).",
        "Step 13 (`scripts/v0_2_gate.py --rc C_α`) needs the verdicts and is not run; M07a.A12 is "
        "judged by its fixture tests only.",
    ]
    for entry in entries:
        if entry["result"] != "pass":
            state = (entry["value"].get("measured") or {}).get("state")
            found.append(
                f"{entry['id']} is {entry['result']}"
                + (f" ({state})" if state else "")
                + ": see its value."
            )
    return found


def _artifact_rows(inputs: Inputs, artifacts: Path | None) -> list[dict[str, str]]:
    rows = [
        (RC_RECORD, "the RC record at C_α (§8.3)"),
        (inputs.rc_dir / "records.json", "the RC records: sha256, size and how each is kept"),
        (ROOT / "release" / "rc-trees" / f"{inputs.commit}.json", "the tree record of C_α (A44)"),
    ]
    found = [
        {"path": t08._shown(path), "sha256": _sha256(path), "description": description}
        for path, description in rows
    ]
    junit = artifacts / "t08-tests.junit.xml" if artifacts is not None else None
    if junit is not None and junit.is_file():
        found.append(
            {
                "path": t08._shown(junit),
                "sha256": _sha256(junit),
                "description": "the tests run here, per node (not committed)",
            }
        )
    return found


def build(
    inputs: Inputs, commands: Sequence[Mapping[str, Any]] = (), artifacts: Path | None = None
) -> dict[str, Any]:
    entries = checks(inputs)
    return {
        "work_package": "M07a",
        "commit": inputs.commit,
        "requirements": list(REQUIREMENTS),
        "status": status(entries),
        "inputs": {
            "case_id": "M07a's acceptance at C_α: one check per assertion of "
            f"docs/derivations/V02-alpha-release-spec.md §10 ({_sha256(SPEC)})",
            "case_hash": _sha256(inputs.rc_dir / "records.json"),
            "environment_lock_hash": _sha256(ROOT / "requirements.lock"),
        },
        "commands": [dict(command) for command in commands],
        "checks": entries,
        "artifacts": _artifact_rows(inputs, artifacts),
        "limitations": limitations(entries),
        "review": {"numerical": "pending", "process_model": "pending"},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    parser.add_argument("--commit", required=True, help="the release candidate C_α")
    parser.add_argument("--ci-run", action="append", default=[], help="a CI run id (repeatable)")
    parser.add_argument("--out", type=Path, default=None)
    arguments = parser.parse_args()

    commit = t08._git("rev-parse", f"{arguments.commit}^{{commit}}").strip()
    differing = v0_1_gate.tree_differences(commit, "HEAD")
    if differing:
        raise SystemExit(f"HEAD's distribution trees differ from C_α's (D2.4): {differing}")
    dirty = [ln for ln in t08._git("status", "--porcelain").splitlines() if "evidence/" not in ln]
    if dirty:
        raise SystemExit(f"the tree is not clean: {dirty[:5]}")
    destination = arguments.out or (ROOT / "evidence" / "M07a" / commit / "manifest.json")
    artifacts = ROOT / "evidence" / "M07a" / commit / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)

    head = t08._git("rev-parse", "HEAD").strip()
    commands: list[dict[str, Any]] = []
    ci: list[dict[str, Any]] = []
    for run_id in arguments.ci_run:
        run, command = t08.fetch_ci(run_id, artifacts)
        ci.append(run)
        commands.append(command)
    t08._test_modules = _test_modules  # T08's runner, over this catalogue's modules
    tests, test_command = t08.run_tests(artifacts)
    commands.append(test_command)
    inputs = Inputs(commit, tests, ci, manifest_exists=destination.is_file(), judged_at=head)

    manifest = build(inputs, commands, artifacts)
    manifest["commands"].append(
        {
            "cmd": "PYTHONPATH=src:. .venv/bin/python scripts/m07a_evidence_manifest.py "
            f"--commit {commit}"
            + "".join(f" --ci-run {run_id}" for run_id in arguments.ci_run)
            + f" (run at {head})",
            "cwd": ".",
            "exit_code": 0,
        }
    )
    found = t08.problems(manifest)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(manifest, indent=1, ensure_ascii=False, allow_nan=False) + "\n", "utf-8"
    )
    counts = Counter(entry["result"] for entry in manifest["checks"])
    print(f"wrote {t08._shown(destination)}")
    print(f"tests run here: pytest exit {tests.exit_code}, {len(tests.nodes)} nodes")
    print(
        f"checks: {len(manifest['checks'])}: {counts['pass']} pass, {counts['fail']} fail, "
        f"{counts['unsupported']} unsupported; status {manifest['status']}"
    )
    for entry in manifest["checks"]:
        if entry["result"] != "pass":
            print(f"  {entry['id']}: {entry['result']}")
    for problem in found:
        print(f"invalid: {problem}")
    return 1 if found or manifest["status"] != "tested" else 0


if __name__ == "__main__":
    raise SystemExit(main())
