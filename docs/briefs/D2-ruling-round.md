# D2 — design-lane ruling round after S05/S06 (specifier; docs only)

Worktree `.claude/worktrees/d2`, branch `wp/D2` from `main`. One commit per ruling; register entries at the next free
R-numbers (grep `^## R-` in `docs/decision-register.md`). No code. Report ≤150 words.

1. **ADR 0045 (S05 IAPWS-95) acceptance.** Status lists five conditions (`docs/adr/0045-*.md` l.3–9). Facts: S05 manifest
   `evidence/S05/4ac00a0…` is `tested`; review `docs/reviews/S05-review.md` (F1 fixed, R-595…R-600); Frank 2026-10-23
   (`docs/FRANK_QUESTIONS.md`, C10 section): C10-Q1 "Yes, as described" — build from CoolProp-transcribed coefficients,
   nothing ships until a person reads IAPWS's terms and checks Tables 6–8 (a workstation engineer is fetching and
   comparing them now, branch `wp/S05-tables`); C10-Q2 "Always vapour". Do condition 5 yourself: write spec
   `docs/derivations/S05-IAPWS95-spec.md` §8 F-1 into ADR 0001 D5 and `docs/interfaces-frozen.md` (or wherever the frozen
   interface text lives) as the design lane. Then rule whether ADR 0045 can be Accepted now with "ships only after the
   Tables 6–8 check" as a release condition, or stays Proposed until that check lands; write the Status accordingly.
2. **S06 §17.4's A04 set is inadmissible.** `docs/C11_DECISIONS.md:54`: the set (purity of A 0.75 at the condenser,
   bottoms rate 0.55) is refused by I6 at either feed (`d_A = 0.75·(F − 0.55) > F_A`); the test evaluates the rows without
   `validate`. Amend §17.4 with an admissible set or record that the row-form test needs none.
3. **D08 in `docs/requirements.yaml` (l.170) does not list S04** (nor S05). Add what the evidence supports.
4. **S04's WO-L01-3 vs Frank's C12 ruling.** `docs/derivations/L01-spec.md` §4.3/§4.4/§6.2: the re-take adds the
   `pr-lib-v1` record path to `openflowsheet.resources.PACKAGED` and a `SELECTABLE_BASES` entry, i.e. ships the records.
   Frank 2026-10-23 (`docs/C12_DECISIONS.md` last line): keep the nine records out of every release. Also W27 v2 (C9,
   `docs/derivations/W27-registration-v2.md`) is now the registration that can judge the route. Rule how WO-L01-3 is
   amended so the development-half re-take can be measured without packaging the records (e.g. a test/measurement-only
   binding outside the wheel), or that it waits for the clean-up package. Write the amended work order.
