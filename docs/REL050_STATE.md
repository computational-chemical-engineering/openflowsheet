# REL050 state: the 0.5.0 release

Rewritten in place; history in `docs/REL050_DECISIONS.md` (append-only, grep it). Rules: `docs/REL050_RULES.md`.
Procedure: `.claude/skills/rel050/SKILL.md` (on this branch; worktree `.claude/worktrees/rel050`).

## Objective

Frank, 2026-11-21: "Will you take care of the release?" (answered yes). Scope fixed by R-1065 (ADR 0057 Amendment 1,
Frank 2026-11-20, "Let's go for the smaller 0.5 release"): **0.5 = X07a, F1, F3, X01's plugin docs**; F2, F8, X06
and X01's selectability lead 0.6. Procedure: RP (`docs/derivations/release-procedure.md`), ADR 0055; dispatch steps
in `docs/RELEASING.md`. Last release v0.4.0 (2026-11-11); main is `0.5.0.dev0`.

## Position (2026-11-21 ~14:45)

- main = d29f1a50 (F1 aa2d0a4d and F3 merged; S19's 0.5 blocking set merged at c4a91a75). wp/REL050 = this branch,
  base c4a91a75, holds R-1065 and the roadmap change (84a08a84, cc6e685e); not yet merged to main.
- X07a: a36 ruling applied (WO19, 277b52b9 + bd0b7df5, R-1068), CI 44902051410 running (macOS and codehealth
  green at 14:28). Then: manifest `tested` (WO17 leftovers in S19_DECISIONS 2026-11-21 X07a-WO17), merge card.
- X01 part A (plugin docs): manifest at a0e4c546 `tested` (6db80c8c); needs one `reviewer` pass, then a merge card;
  Q-1..Q-3 in `docs/X01_DECISIONS.md` (worktree x01) with defaults.
- S19 (repository code health, separate campaign `s19-refactor`): wp/S19 043879a4, CI 44909075689 running; then a
  G-END verdict and its own merge card. Behaviour is bitwise identical, so it is not a 0.5 item.
- Not started: `release/lines/0.5.json` (V04-after review N-3; `inherits: "0.4"`), K3, the RC job, m05 REAL replay
  re-take (RC step 14 has failed since the TRS2 -> TR09 move; ~35 min, reactor env, clean tree, mapping proof plus
  host column).

## Next actions

1. On X07a CI green (all four legs): manifest `tested` at the head, merge card via hub (action text per option).
2. X01: `reviewer` pass on part A (brief file), fixes, merge card.
3. Line file: one `specifier` pass (RP §13 (1)) for `release/lines/0.5.json`: `covers` 0.5.0, claim set (does 0.5
   claim anything new for X07a/F1/F3/X01 docs?), `packages` (+ F1, F3, X07a, X01?), `required_adrs` (0060, 0061,
   0057 Am. 1, X07a's ADR 0007 Am. 3), `rc_items`, `changelog_what_it_is_not`. Build-lane fields by the build lane.
   Then RP.L01-L11 at the draft (`scripts/release_gate.py` loader).
4. Merge wp/REL050 (+ line file) into main; K3 per RP §7.1 (version 0.5.0, envelope pin, fixtures, README); J
   (re-takes incl. m05) and C; RC job steps 1-17 (`scripts/release_rc.py`), §9.2 order: records, lapse report and
   Frank's message 1, `verdict` pass, ledger, manifest H1, H2, step 18 YES, H3, merge C into main.
5. Dry run of the release workflow; Frank: dispatch, PyPI approval.

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

- S19's merge into main relative to K3: only if its card is signed before K3; otherwise after the tag (D2.4 freeze).
- X01 Q-1..Q-3: their defaults in `docs/X01_DECISIONS.md`.
