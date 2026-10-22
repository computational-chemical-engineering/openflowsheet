# S02 specification — handoff (design lane `specifier`, 2026-10-22)

Done (on `wp/S02`, not pushed): `docs/derivations/S02-spec.md`, `docs/derivations/scripts/s02_reference.py` and its JSON
(906 claims; `--check` byte-identical, about 3 min; ruff clean), R-530 to R-535, DECISION lines in `docs/S02_DECISIONS.md`,
Q-S02-1 to Q-S02-3 in `docs/FRANK_QUESTIONS.md`.

Next executable action: the build lane takes WO-1 (spec §12): `ColumnSpec`, validation S1–S10, slot rows,
total-condenser block, initializer; it closes A01–A04.

Open, with defaults in spec §15:
- P1's outcome under the v2 contract (A12 accepts the closed form or a typed outcome; record which).
- The A10 floor for the new rows (must be ≤ 1e-8).
- V-M1/V-M2 convergence from their own pre-solves (A07).

Not done here:
- `docs/progress.md` is not updated (the session owns it).
- A11's "≥ 1e-3 at the 2P root" is argued in prose (≈ 280 K per mol/s), not a generator claim. The reviewer may ask for one.

Finding for the design lane: the singular adjacent pairs and the block rule (§4.3, R-533). The v2 contract can propose
signatures that are structurally singular for cascades.
