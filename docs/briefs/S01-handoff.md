# S01 design-step handoff (specifier, 2026-10-21)

Done (branch `wp/S01`; commits 8bc23bf and 73000b0; not pushed):
- `docs/derivations/S01-spec.md`: §2 rows and DOF, §4 phase/zero flow, §5 refusals, §6 initializer, §7 solve path,
  §10 assertions A01–A20, §12 WO-1 to WO-3, §13 manifest, §14 non-claims, §15 open questions.
- `docs/derivations/scripts/s01_reference.py` and `.json`: `--check` passes 127 claims and the byte-compare; ruff is clean.
- `docs/S01_DECISIONS.md` (+9 lines), `docs/decision-register.md` R-505 to R-509, and `docs/FRANK_QUESTIONS.md` Q-S01-1.

Gaps I stopped at, each small, for a fresh `specifier` pass or the WO-1 engineer's first ruling round:
1. A19's side feed is described only in prose. Register it in the generator: `(0.2, 0.5, 0.3)` mol/s, 340 K, `P_r`, liquid,
   stage 3, N = 3. Its root is analytic (stage 3 a liquid pass-through, `T_3 = 340`).
2. D1 and D2 (`ref.dormant`) are written as static values, not derived. Add a claim deriving the label chain.
3. A10's floor is measured on the generator's formulation with float-rounded outputs. WO-2 must re-measure it on the
   compiled Jacobian, and §10 must be amended if the floor exceeds 1e-8.
4. Open questions §15.1 and §15.2 need facts from WO-2 and WO-3.
5. ADR 0005 restart behaviour for C4 and C5 was not measured. The generator only proves the registered signatures are
   admissible roots, not that they are unique.

Next executable action: the build lane starts WO-1 (spec §12) on `wp/S01`.
