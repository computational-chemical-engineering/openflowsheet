"""T08 W4.1 (release spec §8.1 item 5; ADR 0021 D4): the draft `CHANGELOG.md` section for v0.1.0.

D4 fixes what the section carries and in which order; these tests hold the parts that can drift
from their sources: the gate table equals what `scripts/v0_1_gate.py --markdown` prints from the
ledger, the verdicts and ADR 0021 now; every limitation id the support envelope registered at
v0.1.0 is named, and no other (R-217); the review-status table equals every package manifest's
`status`; and the reproducibility promise is ADR 0007 F1's sentence verbatim.
"""

from __future__ import annotations

import json
import re
import sys

import yaml
from conftest import REPO_ROOT

sys.path.insert(0, str(REPO_ROOT / "scripts"))
import v0_1_gate  # noqa: E402

CHANGELOG = REPO_ROOT / "CHANGELOG.md"


def section() -> str:
    text = CHANGELOG.read_text(encoding="utf-8")
    start = text.index("## v0.1.0")
    return text[start : text.index("\n## ", start + 1)]


def test_the_section_is_first_and_names_the_release_candidate() -> None:
    text = CHANGELOG.read_text(encoding="utf-8")
    assert text.index("## v0.1.0") < text.index("## v0.0.0")
    assert section().splitlines()[0].startswith("## v0.1.0 — release candidate `C` = `67c66d9`")


def test_d4_order() -> None:
    body = section()
    headings = (
        "**What it does.**",
        "**Gates (V11–V20)",
        "**What it is not.**",
        "**Known limitations, by support-matrix id**",
        "**Reproducibility.**",
        "**Review status of every package**",
    )
    positions = [body.index(heading) for heading in headings]
    assert positions == sorted(positions)


def test_the_gate_table_is_what_the_gate_script_prints() -> None:
    report = v0_1_gate.build(
        ledger=yaml.safe_load((REPO_ROOT / v0_1_gate.LEDGER).read_text(encoding="utf-8")),
        verdict_text=(
            (REPO_ROOT / v0_1_gate.VERDICT_DOCUMENT).read_text(encoding="utf-8")
            if (REPO_ROOT / v0_1_gate.VERDICT_DOCUMENT).is_file()
            else None
        ),
        adr_text=(REPO_ROOT / v0_1_gate.ADR_0021).read_text(encoding="utf-8"),
        envelope=yaml.safe_load((REPO_ROOT / v0_1_gate.ENVELOPE).read_text(encoding="utf-8")),
        rc=None,
        candidate="0" * 40,
        version="0.1.0",
        differences=None,
        rc_record=None,
    )
    assert v0_1_gate.markdown(report) in section()


def test_what_it_is_not_names_every_d4_item() -> None:
    body = section()
    part = body[body.index("**What it is not.**") : body.index("**Known limitations")]
    for phrase in (
        "Not empirically validated",
        "Not a guarantee",
        "R-017",
        "Not general beyond the support matrix",
        "Not a certificate of solution accuracy",
        "ADR 0007 F3",
        "PTC is experimental",
        "MCP only",
    ):
        assert phrase in part, phrase


#: Limitation rows the envelope gained after the v0.1.0 release, which its section cannot name
#: without rewriting a release record (R-217, amended for M01 review F1). The 0.2.0 notes name
#: them (M07); an id here must be a row of the envelope, so the list cannot go stale silently.
ADDED_AFTER_V0_1_0 = ("L42",)


def test_every_registered_limitation_is_named_and_no_other() -> None:
    envelope = yaml.safe_load(
        (REPO_ROOT / "benchmarks" / "t08" / "support_envelope.yaml").read_text(encoding="utf-8")
    )
    body = section()
    part = body[body.index("**Known limitations") : body.index("**Reproducibility.**")]
    named = re.findall(r"`(L(?:\d{2}|-[A-Z]+-\d+))`", part)
    registered = [str(entry["id"]) for entry in envelope["limitations"]]
    assert set(ADDED_AFTER_V0_1_0) <= set(registered)
    assert named == [row for row in registered if row not in ADDED_AFTER_V0_1_0]


def test_the_reproducibility_promise_is_adr_0007_f1_verbatim() -> None:
    adr = (REPO_ROOT / "docs" / "adr" / "0007-reproducibility-certificate-policy.md").read_text(
        encoding="utf-8"
    )
    ruling = adr[adr.index("F1 — the project reports") : adr.index("F2 — the property-call")]
    words = " ".join(ruling[len("F1 — ") :].split())
    assert words.endswith("is the promise.")
    assert f'"{words}"' in " ".join(section().split())


def test_the_review_table_is_every_manifests_status() -> None:
    statuses = {}
    # The v0.1.0 section reviews the release's packages (P, K, T); v0.2's (M01 on) are not in it.
    for path in sorted((REPO_ROOT / "evidence").glob("[PKT]*/*/manifest.json")):
        document = json.loads(path.read_text(encoding="utf-8"))
        statuses[document["work_package"]] = document["status"]
    rows = dict(re.findall(r"^\| (\w+) \| `(\w+)` \|", section(), flags=re.MULTILINE))
    assert rows == statuses
