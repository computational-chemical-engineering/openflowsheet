"""M07a.A52 (V02 alpha release spec §10; MR-4, MR-5, MR-9): the `## v0.2.0a1` changelog section.

WO-9 holds the skeleton. Two things are pending until the cut and are recognised by their marker
(`PENDING`): `C_α` in the heading, and the gate table (clause (c)), which is pasted from
`scripts/v0_2_gate.py --markdown` after the verdicts. While a marker is present the clause that
needs it is not checked, and `test_the_pending_markers_are_the_cuts` says so; once the markers are
replaced, clause (c) is checked against the script's own output at the heading's `C_α`. The other
clauses hold now: (a) position, (b) ADR 0021 D4's headings in order, (d) §10.1's phrases,
(e) the limitation ids are the envelope's, in order, (f) ADR 0007 F1 verbatim, (g) the review
table is one row per package with a manifest, with that manifest's `status` and its human
`review` fields.

Clauses (e) and (g) read the candidate, not the working tree (R-320, ADR 0028 D3's "every package
manifest at the candidate"; R-216's and R-217's failure for v0.1.0): once the heading names
`C_α`, (e) reads the envelope at `C_α` and (g) MR-5's set from `C_α`'s tree, with committer times
from `git log C_α`; while the marker is present, both read the working tree. M07a has no row: its
manifest is written after `C_α`, the record of this gate rather than a package of the candidate.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys

import pytest
import yaml
from conftest import REPO_ROOT

sys.path.insert(0, str(REPO_ROOT / "scripts"))
import v0_2_gate  # noqa: E402

CHANGELOG = REPO_ROOT / "CHANGELOG.md"
ENVELOPE = REPO_ROOT / "benchmarks" / "t08" / "support_envelope.yaml"
PENDING = "[[PENDING: "
HEADING = "## v0.2.0a1 — release candidate `C_α` = `"
#: Packages with a manifest that are not a review-table row (R-320).
NOT_A_ROW = ("M07a",)
#: The human-review cell of a manifest `review` field: `pending`, or the signed date (R-017).
SIGNED = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")

#: ADR 0021 D4's six parts, in order (the v0.1.0 section's markers).
D4_HEADINGS = (
    "**What it does.**",
    "**Gates (V11–V20, W21, W22)",
    "**What it is not.**",
    "**Known limitations, by support-matrix id**",
    "**Reproducibility.**",
    "**Review status of every package**",
)

#: §10.1's phrases: ADR 0021 D4's, then the alpha's.
PHRASES = (
    "Not empirically validated",
    "Not a guarantee",
    "R-017",
    "Not general beyond the support matrix",
    "Not a certificate of solution accuracy",
    "ADR 0007 F3",
    "PTC is experimental",
    "MCP only",
    "Not 0.2.0",
    "W23–W27 are not claimed",
    "the web shell is included and not claimed",
    "not a sandbox",
    "Linux",
    "x86-64",
    "R3",
    "synthetic",
    "pure-component",
    "k_ij = 0",
    "no reactor result has been compared with experimental data",
    "T08.A34 covers the coupled-route certificates the RC job now emits.",
    "T08.A30 covers every extra that is new since v0.1.1, through its own audit.",
)


def section() -> str:
    text = CHANGELOG.read_text(encoding="utf-8")
    start = text.index("## v0.2.0a1")
    return text[start : text.index("\n## ", start + 1)]


def candidate() -> str | None:
    """The heading's `C_α`, or None while it is pending."""
    named = section().splitlines()[0][len(HEADING) :].split("`", 1)[0]
    return None if named.startswith(PENDING) else named


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, check=True
    ).stdout


def words(text: str) -> str:
    return " ".join(text.split())


def between(body: str, start: str, end: str) -> str:
    return body[body.index(start) : body.index(end)]


def test_a_the_section_is_first_and_names_the_candidate() -> None:
    text = CHANGELOG.read_text(encoding="utf-8")
    assert text.index("## v0.2.0a1") < text.index("## v0.1.1")
    assert text.index("\n## ") == text.index("\n## v0.2.0a1")  # the first section of the file
    heading = section().splitlines()[0]
    assert heading.startswith(HEADING)
    candidate = heading[len(HEADING) :].split("`", 1)[0]
    assert candidate.startswith(PENDING) or re.fullmatch(r"[0-9a-f]{40}", candidate), candidate


def test_b_d4_order() -> None:
    body = section()
    positions = [body.index(heading) for heading in D4_HEADINGS]
    assert positions == sorted(positions)


def test_the_pending_markers_are_the_cuts() -> None:
    """Names what is not yet checked; fails once only one of the two markers is left."""
    body = section()
    pending = [PENDING in body.splitlines()[0], PENDING + "gate table" in body]
    assert pending[0] == pending[1], "C_α and the gate table are pasted together, at the cut"
    if pending[0]:
        pytest.skip("pending: C_α and the gate table are filled at the cut (clause (c))")


def test_c_the_gate_table_is_what_the_gate_script_prints() -> None:
    body = section()
    if PENDING + "gate table" in body:
        pytest.skip("pending: the gate table comes from `--markdown` after the verdicts")
    candidate = body.splitlines()[0][len(HEADING) :].split("`", 1)[0]
    table = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "v0_2_gate.py"),
            "--rc",
            candidate,
            "--markdown",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert table in body


def test_d_what_it_is_not_names_every_phrase() -> None:
    body = section()
    part = words(between(body, "**What it is not.**", "**Known limitations"))
    for phrase in PHRASES:
        assert phrase in part, phrase


def test_e_the_limitation_ids_are_the_envelopes_in_order() -> None:
    rc = candidate()
    if rc is None:
        text = ENVELOPE.read_text(encoding="utf-8")
    else:
        text = git("show", f"{rc}:{ENVELOPE.relative_to(REPO_ROOT).as_posix()}")
    envelope = yaml.safe_load(text)
    part = between(section(), "**Known limitations", "**Reproducibility.**")
    named = re.findall(r"`(L(?:\d{2}|-[A-Z]+-\d+))`", part)
    assert named == [str(entry["id"]) for entry in envelope["limitations"]]
    assert {"L42", "L-WEB-1", "L-WEB-2", "L-WEB-3", "L-WEB-4"} <= set(named)


def test_f_the_reproducibility_promise_is_adr_0007_f1_verbatim() -> None:
    adr = (REPO_ROOT / "docs" / "adr" / "0007-reproducibility-certificate-policy.md").read_text(
        encoding="utf-8"
    )
    ruling = adr[adr.index("F1 — the project reports") : adr.index("F2 — the property-call")]
    promise = words(ruling[len("F1 — ") :])
    assert promise.endswith("is the promise.")
    assert f'"{promise}"' in words(section())


def manifests(rc: str | None) -> dict[str, tuple[int, dict]]:
    """`evidence/<package>/<commit>/manifest.json` -> (committer time, document): at `rc`'s tree
    and `git log rc`, or the working tree and `git log HEAD` while `rc` is None."""
    if rc is None:
        paths = [
            path.relative_to(REPO_ROOT).as_posix()
            for path in sorted((REPO_ROOT / "evidence").glob("*/*/manifest.json"))
        ]
    else:
        paths = [
            path
            for path in git("ls-tree", "-r", "--name-only", rc, "--", "evidence").splitlines()
            if re.fullmatch(r"evidence/[^/]+/[^/]+/manifest\.json", path)
        ]
    found = {}
    for path in paths:
        if rc is None:
            text = (REPO_ROOT / path).read_text(encoding="utf-8")
        else:
            text = git("show", f"{rc}:{path}")
        time = git("log", "-1", "--format=%ct", rc or "HEAD", "--", path).strip()
        found[path] = (int(time or 0), json.loads(text))
    return found


def human(review: dict) -> str:
    """The table's third cell from a manifest's `review` fields."""
    cells = []
    for field in ("numerical", "process_model"):
        value = review[field]
        if value == "pending":
            cells.append("pending")
        else:
            date = SIGNED.search(value)
            assert date, value
            cells.append(f"signed {date.group(1)} (R-017)")
    return " / ".join(cells)


def test_g_the_review_table_is_every_manifests_status() -> None:
    """MR-5: one row per package with a manifest at the candidate, M07a excepted (R-320); where
    several, the latest committer time's: its `status` and its human `review` fields."""
    latest: dict[str, tuple[int, str, str]] = {}
    for time, document in manifests(candidate()).values():
        package = document["work_package"]
        if package in NOT_A_ROW:
            continue
        if package not in latest or time > latest[package][0]:
            latest[package] = (time, document["status"], human(document["review"]))
    expected = {package: (status, cell) for package, (_, status, cell) in latest.items()}
    part = section()
    part = part[part.index("**Review status of every package**") :]
    rows = re.findall(r"^\| (\w+) \| `(\w+)` \| (.+?) \|$", part, flags=re.MULTILINE)
    assert [package for package, _, _ in rows] == sorted(expected)
    assert {package: (status, cell) for package, status, cell in rows} == expected


def test_the_gate_script_is_the_alphas() -> None:
    """The table's source exists and covers the alpha version (guards a renamed script)."""
    assert v0_2_gate.gate_set_of("0.2.0a1") is not None
