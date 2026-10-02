# T08 — campaign state

Position, not history. Rewritten in place. Read after `CLAUDE.md` and `docs/progress.md`.

| | |
| --- | --- |
| Objective | Plan §4.3 row T08: v0.1 release evidence, supported envelope and v0.2 real-chemistry selection. Acceptance: gate V11–V20; a selected chemistry/data/kinetics/property/reference dossier (V19); a reproducible release candidate |
| Lead | Design / Build — `verdict` judges gates, `specifier` the envelope and the V19 dossier criteria; the session builds |
| Branch | `wp/T08`, from `main` at `16c4fbd` (T07 merged) |

## Where we are

- Started 2026-09-29 on Frank's "what is next?" after T07 merged.
- Step 1: recon of the V11–V20 evidence (which manifests, requirement statuses, known gaps) → a gate
  ledger; then the design lane judges each gate and names the work.
- Known inputs: T04 F1 (PTC experimental, V14's PTC clause incomplete); ADR 0006 D4/D5 (notice bundle
  before any mode-B artifact; the `LICENSE` question is Frank's); OpenIDAES-450 as a real-chemistry
  candidate (`study/openidaes450`); T07 hand-ons (`docs/T07_STATE.md`); the A89 aarch64 flake; the
  web-shell design on `design/web-shell-brief` is M06 input (v0.2), not T08.

## Needs Frank

Answered 2026-09-29 (`docs/T08_DECISIONS.md`): F1 and F2 **build first** (holdup CSTR to qualify PTC; warm
starts); F3 **ammonia loop**; F4 **approved** (substitution-only `t07` move). Open: the LICENSE file in the group reactor repository (Frank: MIT); which rate
law the kinetics implements; the use of the Rossetti et al. data and the property coefficients; F5 (carry V17 if the agent-facing surface is unchanged); tagging/publishing.

## Next action

**Running (Frank: "the defaults are good, please continue", 2026-09-29).** C_reg = `9f5f29d`. **W2 done**
(`e924d13`…`7467d52`: kinetic CSTR, B10–B19/B26 pass, check.sh 6405). **W3 (C_case) blocked on design-lane
Q1/Q2** (`docs/T08_DECISIONS.md`, 2026-09-29 W2 entry: PTC-R1 must carry `C = 0` because binding requires
`(A, B, C)`; B17's EO-row status) — a small `specifier` amendment, **asked Frank first** (budget). **W4 done but check.sh RED (5 tests)** —
`bb4fc1a`…`ff79cbe`; blocked on design-lane Stop 1 (V17 T10-C3 pins the offered policies), Q-W4-1, Q-W4-2.
**Amendment 1 committed as `C_A1` = `30243f9`** (PTC-R1 on (A,B,C) with a 2⁻¹⁰ C trace; T10
oracle via `t07_reference_t08.json`). Applied (`47b6c5f`…`f9a7f66`); **`C_case` = `c337fa1`**; check.sh green (6477). **Review done** (`docs/reviews/T08-review.md`, `3eb6051`: M0, S7, N7; W5 may run after S1–S3 and the
S5/S6 wording). Rulings: P-budget — the arms (with the 10000 cap) stand, no re-registration; P-trace — B21's
1e-10 governs, YAML 1e-12 is an erratum, YAML not regenerated before C_res; P-STR04 — one shared rewrite.
**Review fixes landed** (`e3518ef`…`485f944` + harness counts; check.sh 6484 green; identity unchanged;
R-128). **W5 done: `C_res` = `b11d7b3`** (results on ref-x86-64 local, ci-aarch64 and ci-x86-64 from CI
36590634080; class maps identical on all three). Newton L/M/H/F 113/161/166/1; PTC 182/149/109/1; PTC reaches 84
starts Newton does not; **PTC reports MID on 149 starts** (the saddle clause needs 0). CI's check jobs failed on
T08.A00 (generator read an ignored artifact) — fixed in `8d311b9`, push CI pending. **V14 (b) FAIL, accepted by Frank for v0.1** (ADR 0021 D3 row). Phase 2a done incl. W2.4; review 2
(`docs/reviews/T08-review-2.md`) and the MCP description review (`docs/reviews/T08-description-review.md`) applied;
V17 carried across the U05 change (Frank, R-133). Frank re-reviewed the two changed descriptions and amended B50 (R-134, 2026-10-01); **check.sh fully green
(6608)**. V13 (e): B40–B49 MET, B50 amended → MET on existing evidence (re-confirm at RC). **Phase 2b done**: A30 PASS on both architectures after Frank's ADR 0006 Amendment 1
(R-135: GCC runtime library allowed; LGPL-2.1 covered); A31, A32, A35 met; A89 20/20 aarch64 + 1 local (design lane
to amend T06 A89); warm-start opening-refusal test added. **T08 `tested`** at RC `C` = `67c66d9` (manifest `evidence/T08/67c66d9…/manifest.json`, 85 checks: 83 pass, 2 accepted
FAIL = V14 (b)); verdicts `docs/reviews/T08-verdicts.md`; gate script **YES**; check.sh 6864 passed. ADRs 0021–0025
Accepted. Next: merge to `main`; `0.1.0` bump; Frank: tag, squashed public push, PyPI. Open for a later design-lane
look (not blocking): build-lane decisions Q1 (B24 test written at close-out, `5323046`) and Q2 (A21 harvest excludes
`evidence/T08/`, `1305f87`); release spec Amendments R6/R7 had no design-lane review. **Phase 1 done** (`2476186`…`0c824e0`; `t07` key unmoved;
W1.1 ledger and W1.6 A89 left). **Ask Frank before** the `reviewer` pass on W2–W4 and before W5's
882 comparison runs. One agent at a time.
