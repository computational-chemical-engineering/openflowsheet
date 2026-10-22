# S01 design-step handoff (specifier, 2026-10-21)

Done (branch `wp/S01`; commits 8bc23bf and 73000b0; not pushed):
- `docs/derivations/S01-spec.md`: §2 rows and DOF, §4 phase/zero flow, §5 refusals, §6 initializer, §7 solve path,
  §10 assertions A01–A20, §12 WO-1 to WO-3, §13 manifest, §14 non-claims, §15 open questions.
- `docs/derivations/scripts/s01_reference.py` and `.json`: `--check` passes 127 claims and the byte-compare; ruff is clean.
- `docs/S01_DECISIONS.md` (+9 lines), `docs/decision-register.md` R-505 to R-509, and `docs/FRANK_QUESTIONS.md` Q-S01-1.

Gaps I stopped at, each small, for a fresh `specifier` pass or the WO-1 engineer's first ruling round:
1. **Closed (close-out pass, brief `S01-spec-closeout.md`).** A19's case is registered as `ref.partial_dormancy`; its analytic
   root under (`ZERO_FLOW`, `ZERO_FLOW`, `LIQUID`), `T = (330, 330, 340)` K, passes §8 by generator claims.
2. **Closed (same pass).** `ref.dormant.D1`/`D2` are derived: closed-form state, label chain, declared rows, swapped energy
   rows, outcome and cause. `--check` now passes 153 claims (127 + 26). Spec rows A13, A14 and A19 cite the keys.
3. A10's floor is measured on the generator's formulation with float-rounded outputs. WO-2 must re-measure it on the
   compiled Jacobian, and §10 must be amended if the floor exceeds 1e-8.
4. Open questions §15.1 and §15.2 need facts from WO-2 and WO-3.
5. ADR 0005 restart behaviour for C4 and C5 was not measured. The generator only proves the registered signatures are
   admissible roots, not that they are unique.

Next executable action: the build lane starts WO-1 (spec §12) on `wp/S01`.
