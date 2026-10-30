# V03 brief: the 0.3.0 release policy and release specification (design lane, `specifier`)

Branch `wp/V03` from `main` (create it in a worktree `.claude/worktrees/v03`). E01 (cost + LCA, manifest id `S12`) is on
`wp/E01`, gated and in CI, and merges into `main` shortly; read it with `git show wp/E01:<path>` until then. Docs-only
deliverable; commit on `wp/V03`, do not push.

## 1. The question

Frank, 2026-10-29: **"cut 0.3.0 right after S11 and E01 merge, before starting the optimiser package, and leave Wilson in."**
Write the 0.3.0 release policy (ADR **0053**) and a short release specification
(`docs/derivations/V03-release-spec.md`) so that one build-lane engineer can prepare the release candidate C, run the RC job
and hand a `verdict` agent the evidence, with nothing left to choose.

## 2. Why the design lane

The claim set, the judgement rules and what 0.3.0 says it is *not* are scientific claims about the software; R-563 reserves
the version pin, the working form after the tag and M07a.A10's pairs for "v0.3's release-policy ADR".

## 3. Current state (read narrowly)

- 0.2.0 was released 2026-10-20 (tag `v0.2.0` → `5c82b4c`) under ADR 0042 (`docs/adr/0042-v0.2.0-release-policy.md`, 64
  lines: D1 claim set `v0.2-gate-v1` = V11–V20 + W21–W27; D2 judgement — `BLOCKED` blocks, a `FAIL` releasable only with
  Frank's dated acceptance in the D3 table; D4 one registry entry; D5 the tag is Frank's) and M07 spec §7–§8, §10, §13
  (`docs/derivations/M07-spec.md:262-435`). Gate script `scripts/v0_2_gate.py` (`GATE_SETS` at :207, `v0.2-gate-v1` at
  :230); RC job `scripts/m07a_rc.py`; procedure `docs/RELEASING.md` "Per release" (:82-105) and "After a tag" (~:150-165).
- **R-563** (`docs/decision-register.md:11248`): `main` keeps `v0.2-envelope-dev` / `0.2.0.dev0` until this ADR, which
  decides together the 0.3.0 pin, the working form after it (default: version-free, D1-O2) and A10's pairs
  (`tests/test_m07a_v0_2_gate.py:1030-1048`, `tests/test_m07_v0_2_gate.py:327, 372-378`).
- v0.3 content on `main` since 0.2.0 (each with a `tested` manifest under `evidence/<ID>/`, a design-lane review under
  `docs/reviews/`, and its decisions in the register): S01–S03 (column), S04, S05 (IAPWS-95 water, ADR 0045 Accepted),
  S06, S07 (CoolProp pure fluids, ADR 0046), S08/S08b (one-phase column sections, ADR 0048), S09, S10/S10c (Wilson liquid
  mixtures, ADRs 0047/0049), S11 (binding package: these bases selectable in flowsheets, `thermal.*` units, column as a
  flowsheet unit; ADRs 0050/0051), E01/S12 (cost + LCA as differentiable post-solve functionals; ADR 0052). ADRs
  0046–0052 are **Proposed**; decide how each becomes Accepted for the release (check each has a merged `tested` manifest
  and a review record; name any that cannot be accepted and why).
- Release-candidate-time items already registered by packages (find them all; at least): E01 **A48/G10** (every shipped
  `primary` cost range `verified: true`; QA1 below); S07 A31 and S11 R-843/R-845 classed lines (aarch64); T07 W4b.5 report
  line (R-796); `scripts/e01_evidence_manifest.py::a48_release_check()`.

## 4. Already decided, not open

- Frank's directives: as few limitations as possible; batch, then test once; finish lean (one specifier pass, one
  engineer for the build steps, Frank's items asked early); at most two agents; the tag and publication are Frank's.
- **Frank's answers, 2026-10-29** (`docs/FRANK_QUESTIONS.md` end): Wilson **in** 0.3.0, and the wheel ships the Wilson data
  — **fitted parameters and the transcribed Kurihara 1993 points**, plus the three CIAAW atomic weights (S10 Q-F3; update
  `docs/s10-rights-check.md`'s ship table accordingly, citing Frank's answer); the five IPCC AR6 GWP-100 values ship **as
  facts with the citation**; QA1 is checked against **Seider et al. 4th ed.** (2017, Zotero `seider2017product`; ch. 16,
  Table 16.32 pp. 481-485) by an agent, and Frank approves the one commit that sets `verified: true` (in progress now, a
  separate agent; your spec only names it as an RC precondition).
- Earlier: M03 N1 `nlp` licences accepted; IAPWS attribution in NOTICE (ADR 0045); CoolProp optional extra; Brightway
  optional extra `lca`; restricted LCA data labelled (R-870).
- Register from the next free id after `wp/E01`'s R-871 (check both `main` and `wp/E01` tails); ADR 0053.

## 5. Genuinely open (decide; give a default where Frank's preference decides)

1. **Claim set** for 0.3.0: which gates `v0.3-gate-v1` claims — the seventeen v0.2 gates re-judged at C (which can be
   carried, and on what rule, e.g. V17's agent evidence across v0.3's interface changes), plus what new claims the v0.3
   packages support (and how a gate reads their evidence). Lean: reuse the 0.2.0 machinery; no new billed agent campaign
   unless a claim cannot stand without one — if so, make it a "Needs Frank" item with the cost and a default.
2. Judgement rules (ADR 0042 D2/D3 carried or changed).
3. The 0.3.0 pin, the working form after the tag, A10's pairs (R-563).
4. ADR 0046–0052 acceptance route.
5. Release notes: `CHANGELOG.md` `## v0.3.0` "What it is not" (numerical verification ≠ empirical validation ≠ optimality;
   cost/LCA are assessment estimates with accuracy class; Wilson/VLE only, no liquid–liquid split; etc.).
6. Work orders for one engineer (version-carrying files, registry entry, packaging of the Wilson and E01 data, RC job,
   CHANGELOG), and what the `verdict` agent receives.

## 6. Verification

The full `scripts/gate.sh`; CI on x86-64 and aarch64; the RC job's report ending `v0.3.0 tag may be proposed: YES`;
assertions numbered and falsifiable (as M07 spec §11).

## 7. Deliverable

ADR `docs/adr/0053-v0.3.0-release-policy.md` (Proposed), `docs/derivations/V03-release-spec.md` (≤ ~400 lines: claim set,
registry entry, RC procedure, assertions, work orders, Needs Frank with defaults, what it does not establish), register
entries, and one docs-only commit on `wp/V03` including this brief. Report in at most 20 lines.

## 8. Out of scope and rules

No production code. No re-opening of closed ADRs or of Frank's answers. Do not start subagents. Do not send personal
identifiers (names, e-mail addresses) to any external service. New literature references, if any: list them in your report
(the orchestrator forwards them to the `zotero` session). Temp files under `/home/frankp/.cache/`. Context cap ~150k:
grep and read line ranges.
