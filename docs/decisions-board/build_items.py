# ruff: noqa: E501  (question texts are prose data; wrapping them would only fragment the sentences)
"""Build the decision board's question documents (one JSON file per item) from the repository.

The board is the claude.ai artifact https://claude.ai/artifact/WBLrhuGuG9zosGy46Z1b2A (page source: index.html here).
Its `items` collection is written from these files with the ArtifactData tool; answers come back in `answers`.
Run: python docs/decisions-board/build_items.py  (writes docs/decisions-board/items/<id>.json).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "items"
GH = "https://github.com/computational-chemical-engineering/openflowsheet/blob"
DESC = "src/openflowsheet/application/bindings/descriptions"


def show(ref: str, path: str) -> str:
    return subprocess.run(
        ["git", "show", f"{ref}:{path}"], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


def diff_sentences(old: str, new: str) -> list[dict[str, str]]:
    olds, news = old.split("\n"), new.split("\n")
    rows = []
    for o, n in zip(olds, news, strict=False):
        if o != n:
            rows.append({"old": o, "new": n})
    return rows


def link(label: str, ref: str, path: str) -> dict[str, str]:
    return {"label": label, "url": f"{GH}/{ref}/{path}"}


def adr(num: str, name: str) -> dict[str, str]:
    return link(f"ADR {num} (full text)", "main", f"docs/adr/{num}-{name}.md")


def choice(key: str, label: str, detail: str = "") -> dict[str, str]:
    return {"key": key, "label": label, "detail": detail}


OTHER = choice("other", "Something else", "Say what in the note.")

items: list[dict] = []


def add(**kw) -> None:
    kw.setdefault("status", "open")
    kw["order"] = len(items)
    items.append(kw)


# ---------------------------------------------------------------- blocking: texts to read, ADRs to accept
explain = show("wp/MSG", f"{DESC}/explain.md")
add(
    id="msg-explain",
    section="blocking",
    pkg="MSG",
    pkgTitle="Messages that say what, where, why and what to do",
    kind="review",
    title="The `explain` tool's description",
    body=[
        "MSG adds an `explain` tool: given any message code (an error, a refusal, a check), it returns the catalogue "
        "entry that explains it. The text below is what an AI agent reads to decide when to call the tool.",
        "Every agent-facing description needs two reviews before it ships: the design lane's (done, after two "
        "wording edits) and yours. Approve it, or write what to change.",
    ],
    text=explain,
    textLabel=f"{DESC}/explain.md on wp/MSG",
    textCap=1500,
    unblocks="MSG merges into main; the stream table (ST) and units of measure (X04) follow it.",
    links=[link("Design-lane review (Q6)", "main", "docs/reviews/MSG-review.md")],
)

for f, title in (
    ("validate", "The `validate` tool's description (changed by OPT)"),
    ("submit_job", "The `submit_job` tool's description (changed by OPT)"),
):
    new = show("wp/OPT", f"{DESC}/{f}.md")
    old = show("main", f"{DESC}/{f}.md")
    add(
        id=f"opt-{f.replace('_', '-')}",
        section="blocking",
        pkg="OPT",
        pkgTitle="Optimising your own flowsheets",
        kind="review",
        title=title,
        body=[
            "OPT adds optimisation to the existing tools, so their agent-facing texts gained a few sentences. "
            "The full new text is below; the changed sentences are under the diff.",
        ],
        text=new,
        textLabel=f"{DESC}/{f}.md on wp/OPT",
        textCap=1500,
        diff=diff_sentences(old, new),
        unblocks="OPT's evidence can be marked tested and OPT can merge (with ADR 0071).",
    )

add(
    id="adr-0071",
    section="blocking",
    pkg="OPT",
    pkgTitle="Optimising your own flowsheets",
    kind="adr",
    title="Accept ADR 0071: optimisation of revision flowsheets",
    body=[
        'Lifts the old "optimisation unsupported" refusal and adds an `optimize` job: decisions and an objective '
        "are declared in a separate optimisation request (the flowsheet is never edited), Ipopt solves it, and the "
        "optimum is certified like a solve. It adds to the frozen application contract (ADR 0019 Amendment 16).",
        "The questions below (Q1–Q9) carry defaults that are already built.",
    ],
    links=[
        adr("0071", "OPT-revision-optimisation"),
        link("Design note", "main", "docs/design/OPT-revision-optimisation.md"),
        link("Review", "main", "docs/reviews/OPT-review.md"),
    ],
    unblocks="OPT merges; RRC (continuation) merges after it.",
)
add(
    id="opt-q7",
    section="blocking",
    pkg="OPT",
    pkgTitle="Optimising your own flowsheets",
    kind="choice",
    title="Q7: an optimum exactly at a boiling or dew point",
    body=[
        "At a bubble or dew point the flowsheet equations are singular by nature, so the ordinary certificate "
        "cannot verify an optimum that sits exactly there (measured: it happens on real cases).",
        "The amended design checks such an optimum on a reduced form that removes exactly that one direction and "
        "flags the result as a phase-boundary optimum. The ordinary solve certificate stays unverified, and the "
        "record says which check passed.",
    ],
    defaultKey="flag",
    options=[
        choice("flag", "Verify on the reduced form, with the flag", "Built this way."),
        choice("unverified", "Report such optima as found but not verified"),
        OTHER,
    ],
    links=[link("Design §9 amendment", "main", "docs/design/OPT-revision-optimisation.md")],
)

add(
    id="adr-0070",
    section="blocking",
    pkg="X02",
    pkgTitle="Warm starts for external and coupled units",
    kind="adr",
    title="Accept ADR 0070 (and ADR 0019 Amendment 15): declared warm starts",
    body=[
        "A solve may declare a starting point taken from an earlier solution, recorded in the run so it replays. "
        "Measured: restarting a coupled run from the same design's solution takes 1 reactor iteration instead of 4 "
        "(25 s instead of 194 s).",
        "Two claims were withdrawn after measurement (questions Q1 and Q7 under Defaults): the reactor's own warm-start "
        "variant was about 21 % slower, and starting from a neighbouring design did not save iterations.",
    ],
    links=[
        adr("0070", "X02-warm-starts"),
        link("Design note", "main", "docs/design/X02-warm-starts.md"),
    ],
    unblocks="X02 merges (it is built, tested and green on CI).",
)

add(
    id="adr-0072",
    section="blocking",
    pkg="RRC",
    pkgTitle="Continuing from an earlier solved version",
    kind="adr",
    title="Accept ADR 0072: revision-region continuation",
    body=[
        "When an edit to a flowsheet fails to converge, RRC walks the operating values step by step from the "
        "nearest earlier version that solved and verified to the new values; every step is a real flowsheet. "
        "Measured: it rescued 5 failing edits; the existing restart also rescued all 5, in fewer iterations.",
        "It is opt-in, by the policy name `RRC-revision-v1`.",
    ],
    links=[
        adr("0072", "RRC-revision-region-continuation"),
        link("Design note", "main", "docs/design/RRC-revision-region-continuation.md"),
        link("Review", "main", "docs/reviews/RRC-review.md"),
    ],
    unblocks="RRC merges, after OPT.",
)
add(
    id="rrc-fq1",
    section="blocking",
    pkg="RRC",
    pkgTitle="Continuing from an earlier solved version",
    kind="choice",
    title="FQ1: three frozen schemas each accept one more value",
    body=[
        "The solver setting `globalization.eo_recovery` gains the new recovery value. `continuation.type`, in the "
        "attempt context and in the certificate's branch provenance, changes from the single value "
        "`specification_continuation` to a choice of it or `revision_continuation`.",
        "No member is added, and every existing document validates unchanged.",
    ],
    defaultKey="yes",
    options=[
        choice("yes", "Yes, widen them", "Built this way; merge after your yes."),
        choice("no", "No", "RRC cannot merge as designed."),
        OTHER,
    ],
)

st_text = show("wp/ST", f"{DESC}/get_stream_table.md")
add(
    id="st-get-stream-table",
    section="blocking",
    pkg="ST",
    pkgTitle="Stream table and energy summary",
    kind="review",
    title="The `get_stream_table` tool's description",
    body=[
        "ST adds a stream table: for each stream of a finished run, T, P, flows, composition, vapour fractions and, "
        "per phase, h, s, density and enthalpy flow, plus each unit's duty, work and energy closure. The text below "
        "is what an AI agent reads.",
        "The design lane approved it after three wording edits, which are in this text.",
    ],
    text=st_text,
    textLabel=f"{DESC}/get_stream_table.md on wp/ST",
    textCap=1500,
    unblocks="ST's merge (it also waits for MSG and ADR 0068).",
    links=[link("Design-lane review", "main", "docs/reviews/ST-review.md")],
)
add(
    id="adr-0068",
    section="blocking",
    pkg="ST",
    pkgTitle="Stream table and energy summary",
    kind="adr",
    title="Accept ADR 0068 (as amended by the review): the stream table",
    body=[
        "A new read-only operation `get_stream_table(job)` on every surface (Python, CLI `openflowsheet streams` as "
        "text, JSON or CSV, HTTP, MCP). It is computed when asked from the run's replay bundle: nothing is stored, no "
        "released number or replay changes, and 0.3.0 runs get a table too. Values a provider cannot give are shown "
        "as absent with a reason, never estimated.",
        "Amended by the review (rule R1′): a stream whose phase split a flash cannot determine (a temperature-"
        "degenerate split) takes the split the solver carries, as the certificate check does, or reports the value "
        "as absent. This fixed a 2016 W error on one test case.",
    ],
    links=[
        adr("0068", "stream-table"),
        link("Design note", "main", "docs/design/ST-stream-table.md"),
        link("Review", "main", "docs/reviews/ST-review.md"),
    ],
    unblocks="ST merges, after MSG.",
)

add(
    id="wit-q2",
    section="blocking",
    pkg="WIT",
    pkgTitle="Certificate derivative check at very small or zero flows (merged)",
    kind="choice",
    title="Q-WIT-2: correct one outdated sentence in the flash model's description",
    body=[
        "With the fixed derivative check, an ammonia flash state near its dew point now verifies honestly, so the "
        '"near-dew window" sentence in the `c1.tp_flash` model\'s manifest text '
        "(`src/openflowsheet/models/c1/flash.py:343-349`) states an outdated edge.",
        "Correcting it changes that model's artifact hash and one frozen identity-corpus entry (F0 M9), but not its "
        "`model_version` or any result.",
    ],
    defaultKey="yes",
    options=[
        choice("yes", "Yes, correct it", "In its own commit, with the corpus entry re-recorded."),
        choice(
            "no", "No, leave the sentence", "The stale edge stays documented as a known inaccuracy."
        ),
        OTHER,
    ],
)


# ---------------------------------------------------------------- defaults in effect
def dq(id_, pkg, pkg_title, title, body, default_label, default_detail="", alts=(), links=()):
    opts = (
        [choice("default", default_label, default_detail)]
        + [choice(f"alt{i}", a[0], a[1] if len(a) > 1 else "") for i, a in enumerate(alts, 1)]
        + [OTHER]
    )
    add(
        id=id_,
        section="defaults",
        pkg=pkg,
        pkgTitle=pkg_title,
        kind="choice",
        title=title,
        body=body,
        defaultKey="default",
        options=opts,
        links=list(links),
    )


X02T = "Warm starts for external and coupled units"
dq(
    "x02-q1",
    "X02",
    X02T,
    "Q1: register a warm-start variant of the reactor?",
    [
        "Measured on 8 inlets: cold runs match today's reactor bit for bit, but warm calls were about 21 % slower overall "
        "(later stages and certificates ran longer) and differed from cold by up to 1.9e-7 relative."
    ],
    "No, do not register it",
    "Keep the gains that work (restarting a coupled run from a previous solution).",
    [("Register it anyway",)],
)
dq(
    "x02-q7",
    "X02",
    X02T,
    "Q7: the speed-up claim for neighbouring designs",
    [
        "Restarting a coupled run from a neighbouring design's solution (feed temperature +2 K) was meant to need fewer "
        "outer iterations. On the real reactor loop both took 4 iterations, and the warm run took longer (223 s against "
        "182 s). Restarting the same design still works (1 iteration, 25 s instead of 194 s)."
    ],
    "Record the check as failed and withdraw that claim",
    "Everything else stays.",
    [("Hold X02 for a redesign",)],
)
dq(
    "x02-q2",
    "X02",
    X02T,
    "Q2: extend the `T08-warm-v1` policy to coupled starts?",
    ["A start is declared per solve instead."],
    "No",
    "",
    [("Yes, extend the policy",)],
)
dq(
    "x02-q3",
    "X02",
    X02T,
    "Q3: allow warm starts on the `experiment` operation?",
    [],
    "No",
    "",
    [("Yes",)],
)
dq(
    "x02-q6",
    "X02",
    X02T,
    "Q6: the variant id `pymrm-6089593-g2-nz800-s123w-v1`",
    ["Only matters if Q1 is reversed."],
    "Keep the id as given",
    "",
    [("Use a different id",)],
)

OPTT = "Optimising your own flowsheets"
dq(
    "opt-q1",
    "OPT",
    OPTT,
    "Q1: where decisions are declared",
    [
        "Decision variables and the objective live in a separate optimisation request; the optimiser never edits the "
        "flowsheet document."
    ],
    "In the request only",
    "",
    [("Also inside the flowsheet document",)],
)
dq(
    "opt-q2",
    "OPT",
    OPTT,
    "Q2: optimise flowsheets on the older (legacy) solve route in 0.4?",
    [
        "Flowsheets with an external reactor are refused with a reason; the trust-region method is their route."
    ],
    "No, the standard route only",
    "",
    [("Yes, the legacy route too",)],
)
dq(
    "opt-q3",
    "OPT",
    OPTT,
    "Q3: cost and LCA as standalone operations, not only as objectives?",
    [],
    "A later package",
    "",
    [("Add them in 0.4",)],
)
dq(
    "opt-q4",
    "OPT",
    OPTT,
    "Q4: should replaying an optimisation re-run Ipopt?",
    [
        "Replay re-checks the certified optimum instead, so it also works on ARM machines without Ipopt."
    ],
    "No, re-check the certified optimum",
    "",
    [("Yes, re-run Ipopt",)],
)
dq(
    "opt-q5",
    "OPT",
    OPTT,
    "Q5: limits per optimisation job",
    [],
    "32 starts, 500 iterations and 120 s per start",
    "",
    [("Different limits",)],
)
dq(
    "opt-q6",
    "OPT",
    OPTT,
    "Q6: commit the optimum as a new revision automatically?",
    ["The result carries a change you commit yourself."],
    "No",
    "",
    [("Yes, commit it automatically",)],
)
dq(
    "opt-q8",
    "OPT",
    OPTT,
    "Q8: audit Ipopt for ARM in 0.4?",
    ["ARM machines replay optimisations but do not run them."],
    "No, x86-64 only",
    "",
    [("Yes, audit ARM now",)],
)
dq(
    "opt-q9",
    "OPT",
    OPTT,
    "Q9: should ordinary solves use the reduced boiling/dew-point check too?",
    ["The check from Q7, applied to `solve` runs that end exactly at a bubble or dew point."],
    "Not in 0.4",
    "",
    [("Yes, in 0.4",)],
)

RRCT = "Continuing from an earlier solved version"
dq(
    "rrc-fq2",
    "RRC",
    RRCT,
    "FQ2: make continuation the default for every revision solve?",
    [],
    "No, opt-in by policy name in 0.4",
    "",
    [("Yes, make it the default",)],
)
dq(
    "rrc-fq3",
    "RRC",
    RRCT,
    "FQ3: if continuation stalls, also try the existing restart?",
    [
        "In all five cases where the new policy rescued a failing edit, the existing policy (`T06-revision-v2`) also "
        "converged through its restart, in fewer iterations (5 against 10–12; 8 against 22–29). With one recovery per "
        "step, a stalled continuation ends the step without the restart, so the new policy can fail where the old one "
        "succeeds; this is declared."
    ],
    "One recovery per step, opt-in only",
    "Any rescue claim, or making it the default, first needs a case where the restart fails and continuation works.",
    [("Restart after a stalled continuation (two recoveries per step)",)],
)
dq(
    "rrc-fq4",
    "RRC",
    RRCT,
    "FQ4: which edits may be continued?",
    [
        "Continuation walks values gradually, so only edits that keep the flowsheet's structure qualify."
    ],
    "Operating values only",
    "Temperatures, pressures, flows, duties, split fractions; not stage counts, feed stages, "
    "stoichiometry or kinetic constants.",
    [("A wider set",)],
)

STT = "Stream table and energy summary"
dq(
    "st-o3",
    "ST",
    STT,
    "O3: show the stream table in the web shell?",
    [],
    "Later, in another package",
    "",
    [("Include it in ST now",)],
)

WITT = "Certificate derivative check at very small or zero flows (merged)"
dq(
    "wit-q1",
    "WIT",
    WITT,
    "Q-WIT-1: VERIFIED with a declared partial derivative check at a held-zero vapour side?",
    [
        "On a Wilson property basis, a unit whose vapour side is held at exactly zero cannot have its zero liquid-side "
        "columns differenced (no derivative exists there). The certificate then says VERIFIED with "
        "`derivative_witness_partial` declared, as already done for zero flows on `pr-c1-v1` (R-281)."
    ],
    "Yes",
    "",
    [("No, report it as unverified",)],
)
add(
    id="adr-0073",
    section="defaults",
    pkg="WIT",
    pkgTitle=WITT,
    kind="adr",
    title="Accept ADR 0073: the derivative check at small and dormant flows",
    body=[
        "The certificate's finite-difference check of the Jacobian now refines its step where the registered step "
        "leaves the domain or is dominated by truncation, and steps one-sided at held-zero sides. No certificate "
        "that passed before changed; former spurious failures became honest verdicts. Merged on its default."
    ],
    links=[
        adr("0073", "WIT-derivative-witness-small-and-dormant-flows"),
        link("Review", "main", "docs/reviews/WIT-review.md"),
    ],
)

X05T = "Replay from the installed package (merged)"
add(
    id="adr-0069",
    section="defaults",
    pkg="X05",
    pkgTitle=X05T,
    kind="adr",
    title="Accept ADR 0069: an installed package replays its own bundles",
    body=[
        "An installed `openflowsheet` replays its own replay bundles once it checks that its nine runtime "
        "dependencies are at the locked versions. It amends ADR 0007's replay-mode rule. Merged on its default."
    ],
    links=[adr("0069", "X05-replay-from-the-wheel")],
)
dq(
    "x05-qf1",
    "X05",
    X05T,
    "Q-F1: pin four transitive dependencies exactly?",
    [
        "attrs, jsonschema-specifications, referencing and rpds-py, pinned in `pyproject.toml`, so a plain "
        "`pip install openflowsheet` can replay its bundles exactly. Cost: users cannot freely upgrade those four."
    ],
    "Yes, pin them",
    "",
    [("No, leave them unpinned",)],
)
dq(
    "x05-qf2",
    "X05",
    X05T,
    "Q-F2: warn when a bundle is written without a verified lock?",
    [],
    "No; decide it with the messages work",
    "",
    [("Yes, warn",)],
)
dq(
    "x05-qf3",
    "X05",
    X05T,
    "Q-F3: record the writer's lock findings inside the bundle?",
    ["That would be a schema change."],
    "No; they appear in the replay reason only",
    "",
    [("Yes, record them",)],
)

# ---------------------------------------------------------------- before the 0.4.0 release
RPT = "Release procedure"
add(
    id="adr-0055",
    section="later",
    pkg="RP",
    pkgTitle=RPT,
    kind="adr",
    title="Accept ADR 0055: the standing release procedure",
    body=[
        "Every release is judged by one fixed procedure: a release line file, standing acceptances that lapse when "
        "the accepted thing changes, a release-candidate run, verdicts per clause and a release evidence manifest. "
        "Accepted on its restated condition (review M-3), it closes K-2 before 0.4.0's cut."
    ],
    links=[
        adr("0055", "standing-release-procedure"),
        link("Release procedure", "main", "docs/derivations/release-procedure.md"),
        link("Review", "main", "docs/reviews/RP-review.md"),
    ],
)
add(
    id="rp-f8",
    section="later",
    pkg="RP",
    pkgTitle=RPT,
    kind="choice",
    title="F-8: one or two messages to you per release?",
    body=[
        "ADR 0055 says each release asks you one message. The procedure plans up to two: the first, before the "
        "verdict, asks about lapsed decision items and any claim-set change; the second, after the verdicts, asks "
        "about each failing clause without a standing acceptance (at 0.4.0: V14 (b)). An empty message is not sent.",
        "One message after the verdicts would bring back the `BLOCKED` row and 0.3.0's re-judgement round.",
    ],
    defaultKey="two",
    options=[
        choice("two", "Two, the first only when non-empty", "Reviewer's recommendation."),
        choice("one", "One message after the verdicts"),
        OTHER,
    ],
)
add(
    id="rp-q11",
    section="later",
    pkg="RP",
    pkgTitle=RPT,
    kind="choice",
    title="Q-11: your licence acceptance for the coolprop and lca extras",
    body=[
        "Your 2026-10-30 acceptance is carried as a standing acceptance that lapses when the accepted thing changes."
    ],
    defaultKey="one",
    options=[
        choice("one", "One row for both extras"),
        choice("per", "One row per extra", "A change to the lca lock re-asks you only about lca."),
        OTHER,
    ],
)

W1T = "Foundation designs for 0.5–0.7 (not urgent)"
add(
    id="adr-0060-0067",
    section="later",
    pkg="W1",
    pkgTitle=W1T,
    kind="choice",
    title="Accept ADRs 0060–0067, the foundation designs",
    body=[
        "0060 extension registry and 0061 component data (built in 0.5); 0062 v2 stream and document grammar, 0063 "
        "property methods from records, 0064 an N-phase flash that discovers phases (0.5–0.6); 0065 the unit-model "
        "framework, 0066 dynamic problems and run kinds, 0067 v2 identity and replay (0.6–0.7). All were reviewed "
        "and fixed; each amends the frozen application contract additively, so each needs your yes.",
        "Two reviewer defaults inside 0067/0065: S1, older v2 bundles re-run after a built-in unit changes and report "
        "differences (instead of refusing); S7, retiring a legacy unit family affects only revisions built by the "
        "new compiler.",
    ],
    defaultKey="proposed",
    options=[
        choice("accept", "Accept all eight"),
        choice(
            "proposed", "Keep them Proposed for now", "The next designs build on them as written."
        ),
        choice("other", "Accept some, or change S1/S7", "Say which in the note."),
    ],
    links=[
        link("P1 review", "main", "docs/reviews/W1-P1-review.md"),
        link("P2 review", "main", "docs/reviews/W1-P2-review.md"),
        link("P3 review", "main", "docs/reviews/W1-P3-review.md"),
    ],
)
dq(
    "w1-o11",
    "W1",
    W1T,
    "O-11: how an equation-of-state phase is labelled vapour-like or liquid-like",
    [
        "When a unit (a flash, for example) has a single dense or supercritical phase, this label decides whether that "
        "phase leaves by the top (vapour) or the bottom (liquid) outlet, so it can change results."
    ],
    "Venkatarathnam and Oellrich's phase identification parameter",
    "",
    [("Another rule",)],
)
dq(
    "w1-a2a",
    "W1",
    W1T,
    "A2-a: a tank that empties completely and refills",
    [
        "A vented vessel that drains to zero and refills is kept out of the first dynamics release (TX) by your ADR 0008 "
        'answer Q-A5. Until it is admitted, the "vessel drains to zero" rule only covers evacuating a rigid vessel.'
    ],
    "Keep it out of TX's first release; decide when X25 is designed",
    "",
    [("Admit it in TX",)],
)


def main() -> None:
    OUT.mkdir(exist_ok=True)
    for old in OUT.glob("*.json"):
        old.unlink()
    for it in items:
        doc = {k: v for k, v in it.items() if k != "id"}
        (OUT / f"{it['id']}.json").write_text(
            json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
        )
    print(len(items), "items:", " ".join(i["id"] for i in items))


if __name__ == "__main__":
    main()
