# REL050 state: the 0.5.0 release

Rewritten in place; history in `docs/REL050_DECISIONS.md` (append-only, grep it). Rules: `docs/REL050_RULES.md`.
Procedure: `.claude/skills/rel050/SKILL.md` (on this branch; worktree `.claude/worktrees/rel050`).

## Objective

Frank, 2026-11-21: "Will you take care of the release?" (answered yes). Scope fixed by R-1065 (ADR 0057 Amendment 1,
Frank 2026-11-20, "Let's go for the smaller 0.5 release"): **0.5 = X07a, F1, F3, X01's plugin docs**; F2, F8, X06
and X01's selectability lead 0.6. Procedure: RP (`docs/derivations/release-procedure.md`), ADR 0055; dispatch steps
in `docs/RELEASING.md`. Last release v0.4.0 (2026-11-11); main is `0.5.0.dev0`.

## Position (2026-11-21 ~15:30)

- main = d29f1a50 (F1, F3, S19's blocking set). wp/REL050 = bc6e6fe9 (not pushed): R-1065, campaign files, and the
  **line file draft** `release/lines/0.5.json` + note `docs/briefs/REL050-line-0.5.md` (specifier, ~283k): claim set
  unchanged from 0.4 (17 gates byte-identical, no RP amendment); `changed` = 10 fields; packages 0.4's 20 + F1, F3,
  X07a, X01; required_adrs 0.4's 26 + 0007, 0057, 0060, 0061, 0076, 0077 (all Accepted at d29f1a50); "Linux only"
  replaced by three platform phrases (true whatever X07a's legs do); three new phrases (no v2 revisions; no solve
  reads the component store; no plugin unit model or method a solve uses); **new rc_item `WHEEL-F1-F3`** (wheel vs
  checkout `registry_sha256` and the 149-record legacy list; its `--f1-f3` flag does not exist yet: note WF-1..WF-5
  and four controls). RP.L01-L11 PASS at bc6e6fe9 except ADR 0061 not Accepted on this branch (passes at d29f1a50:
  merge main first). Release tests 107 passed.
- X07a: a36 ruling applied (WO19 277b52b9 + bd0b7df5, R-1068); CI 44902051410 (macOS, codehealth green at 14:28).
  Manifest still `implemented`; WO17 leftovers for the move (S19_DECISIONS 2026-11-21 X07a-WO17).
- X01: review (reviewer, Opus) "merge after fixes"; X01-WO2 (sonnet) applied all: merge main 1bd587ed, fixes
  5634fa7f (F3 kinds, list_capabilities wording, guide-reading tests, new PAYLOAD_DEFS test with negative control),
  79 tests passed; CI 44909945712 + Site 44909945705 running. Then: manifest `tested` at the head, merge card.
- S19 separate (wp/S19 043879a4, CI 44909075689 running); not a 0.5 item.

## Background waits running at the reset (their notices arrive in the new context)

- `gh run watch 44909945712` then `44909945705` (X01 CI and Site): green -> X01 manifest move (sonnet brief), card.
- `gh run watch 44902051410` (X07a): green on all legs -> X07a manifest move (WO17 leftovers), card.
- `gh run watch 44909075689` (wp/S19): see S19_STATE.

## Next actions

1. Merge main into wp/REL050 (ADR 0061 then Accepted on the branch); rerun the note §7 loader command (PASS).
2. Build lane: `WHEEL-F1-F3`'s `--f1-f3` per note (WF-1..WF-5, four controls): opus-engineer brief file.
3. One scoped `reviewer` pass (Q-D1: release scripts and RP changed since 0.4.0, plus WHEEL-F1-F3).
4. X07a and X01 manifests `tested` and their merge cards (one DECISION-REQUEST each via hub); both must be `tested`
   before K3, else X07a/X01 leave `packages` and Frank is told.
5. Merge card for wp/REL050 into main; then K3 (RP §7.1), J (re-takes incl. m05 REAL on TR09), C, RC steps 1-17,
   RP §9.2 (lapse report and message 1: Q-F1, Q-F2 and the predicted lapses V17 carry, V14 (b), M02 N1; verdict;
   ledger; H1, H2, step 18 YES, H3), merge C, dry run, Frank's dispatch.

## Gates (criteria fixed before the run)

| gate | pass criterion | result |
| --- | --- | --- |
| P1-P6 (RP §5.3) at K3 | every package `tested`/`reviewed` at an ancestor of K3; RP.L01-L11 hold; required ADRs Accepted or routed; host prints `ref-x86-64` | |
| RC steps 1-17 at C | no RP §12 stop; every step's result recorded, none `unsupported` | |
| verdict | every claimed gate met (verdict document), or Frank's answer row | |
| step 18 at H2 | exit 0, last line exactly `v0.5.0 tag may be proposed: YES` | |
| CI | green on both architectures at C and at the merge into main | |
| dry run | release workflow dry run: gate YES, build, `t08-a43-dist.json` all passed | |

## Open decisions (defaults stand unless Frank says otherwise)

- Q-F1 (note §8): the 0.5 line acceptance's "ADR-F1 to ADR-F8 Accepted" (0062-0067 Proposed) -> default: the clause
  moves to 0.6, as for 0.4. Frank, message 1.
- Q-F2: Windows and macOS CI legs not judged at C (step 1 reads the Linux legs) -> default: no change. Message 1.

- S19's merge into main relative to K3: only if its card is signed before K3; otherwise after the tag (D2.4 freeze).
- X01 Q-1..Q-3: their defaults in `docs/X01_DECISIONS.md`.
