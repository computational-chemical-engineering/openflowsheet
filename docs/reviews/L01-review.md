# L01 review: the library records, the provider `pr-lib-v1`, its 50-digit reference, and the T08.A32 question

**Reviewer:** design lane, `reviewer` (Claude Opus 5.5), 2026-10-22. This is the package's single reviewer pass, and it
carries the batched questions of `docs/L01_DECISIONS.md:26-43`. Plan §1.3 requires a design-lane review here because
`pr_lib.py` touches derivatives and phase/root logic.
**Reviewed at:** `wp/L01` = `ca7213b` (diff `wp/C-merge...wp/L01`).
**Design reviewed against:** `docs/derivations/L01-spec.md`, ADR 0043, ADR 0026 D1–D5, R-520…R-527, and M01 spec §3.3–§3.5
with R-158.
**Run here:** `pytest tests/test_l01_*.py` gave 132 passed, 1 skipped (the retrieval `--check`; no pins in the
project venv) and 1 xfailed (A12, C3H8). T08.A32 alone fails as recorded. I also wrote and ran
`tests/test_l01_review_adversarial.py`: 10 passed and 3 strict-xfail, which encode M-1. The probes are re-runnable
from that file.
**Not examined:**
- `l01_projection.py`, and the re-take design (§6, A23–A26; WO-3 is held);
- the internals of `components_crosscheck.py` beyond its A12 bound and scope;
- the † literature values against the printed sources (Q-5).

## Verdict

**Not merge-ready: 3 must-fix, 2 should-fix, 6 notes.**

What holds up:
- The method is a faithful transcription. An AST diff of every computing function in `pr_lib.py` against
  `pr_c1.py` shows that, docstrings aside, the only change is `range(5)` → `range(NC)`. A14 measures 0.0.
- The value and derivative paths describe one function at one root.
- `l01_reference.py` is independent of the provider: it imports nothing from `openflowsheet`, has its own
  `da_m` algebra, finds roots with `polyroots` and differentiates with `mp.diff` at 50 digits.
- `pr_c1.py` and `benchmarks/m01/` are untouched (`git diff` is empty, and the A22 pins hold).

What blocks the merge is the vapour rule itself. It is not a stability test for mixtures (M-1).

## Findings

**M-1 (must fix): the vapour rule answers `ok` where PR itself says the vapour is unstable.**
- *Where:* `src/openflowsheet/thermo/pr_lib.py:614-627`; spec §4.2, §5 A19 and §9.
- *What goes wrong:* ADR 0026 D2's guard compares two roots of the *same* composition. For a pure fluid that is the
  stability test. For a mixture it is not, because the competing liquid is near-pure water, not a same-composition
  liquid.
- *Measured* with an independent float transcription (pure-component trial-phase tangent-plane distance,
  tm_i = ln φ_i^pure(min-G root) − ln y_i − ln φ_i(y)):
  - H2 0.45 / N2 0.15 / CH4 0.02 / H2O 0.30 / CO2 0.08 at 313.15 K and 3 MPa (a cooled reformer outlet, the ATR/SMR
    service these records exist for) → `ok` VAPOR, with tm_H2O = −4.6. Water's fugacity is about 100× that of
    pure liquid water.
  - H2O 0.6 / N2 0.4 at 330 K and 1 bar → `ok` (tm = −1.35, partial pressure 3.9× PR's P_sat).
  - C3H8 0.5 / N2 0.5 at 250 K and 1 MPa → `ok` (tm = −0.62).
- A19 passes only because its state is 95 % water. The text "water partial pressure 5.5× its vapour pressure" reads
  as a supersaturation guard, and none exists. §9 blames dew-point error on k_ij = 0, but nothing computes a dew
  point at all.
- This is a placeholder success path for an unimplemented capability (CLAUDE.md, scientific conduct).
- *Fix:* the refusal `vapour_unstable`, ruled in R-540 and specified in spec §12.3. It is closed form, needs no
  iteration and only refuses. For a pure fluid it reduces exactly to D2's guard. The adversarial tests show it
  leaves every registered admitted state admitted (min tm ≥ 0.05).

**M-2 (must fix): the A12 c_p bound sits below its own floor, and its scope is a narrowed denominator.**
- *Where:* `tests/test_l01_records.py:336-360`; `benchmarks/l01/components_crosscheck.py:73-77, 314-318`; spec §5 A12.
- *What goes wrong:* the 0.5 % bound was registered without a floor (A04 and A07–A11 each state one). The floor is
  the disagreement between NASA TM-4513 and the reference-EOS ideal parts for correct data:
  - M01 §3.3 measured it for the same retrieval chain: CH4 1.12 % at 1000 K, NH3 0.51 %;
  - L01's own JSON gives CH4 +0.68 % at 900 K, for the record that A02 requires to be bitwise C1's.
- So the bound fails correct data. Limiting A12 to the new five (the build-lane default) narrowed the denominator,
  and C3H8 was then xfailed.
- *Fix:* R-528 sets the bound to 2 % for all nine records (derivation in spec §12.1). C3H8 (0.577 %) and CH4
  (0.68 %) pass. The comparand is unchanged and no record is stopped.

**M-3 (must fix): T08.A32 is red on the branch.**
- *Where:* `tests/test_t08_w2_inventory.py:432-460`, clause (i), first failure `('benchmarks/l01/components.yaml',
  'C3H8')`.
- *Fix:* the amendment R-529, with the rule text in spec §12.4 and the test change in the work order below. It admits
  a second vetted file. It does not decide rights.

**S-1 (should fix): the records are packaged ahead of exposure and of Frank's rights answer.**
- *Where:* `src/openflowsheet/resources.py:47`, `pyproject.toml:77`, the link `src/openflowsheet/_data/benchmarks/l01/
  components.yaml`, `tests/test_t08_w2_inventory.py:364`, `tests/test_t08_w4_package_data.py:95` and
  `tests/test_l01_records.py:94-101`.
- *What goes wrong:* once merged, the next wheel built from `main` would carry the nine records. That contradicts
  L01-Q4's default ("nothing from L01 is released until …"). No packaged code can reach them: the route is unexposed
  and `load_records` falls back to the checkout.
- *Ruling (Q5 below):* spec §4.4 prevails over §11. Packaging moves with WO-L01-3, after L01-Q4.

**S-2 (should fix): the liquid-like guard is never exercised on a mixture.**
- *Where:* `pr_lib.py:625`; the A18 states are pure.
- *What goes wrong:* replacing `b_mix` with the smallest or the largest b_i of the components present survives every
  test.
- *Fix:* `test_l01_review_adversarial.py::test_s2_*` now pins a pair that flips under each mutation: CH4/C2H6 50/50
  at 350 K is admitted at 15 MPa (v/b_mix = 4.13) and refused at 20 MPa (3.16). The work order moves the pair into
  the generator's `guard_states`.

**Notes.**
- **N-1.** `pr_lib.py:623` tests `len(roots) > 1`, where the spec, the ADR and `l01_reference.py:220` say three roots.
  F(Z = B) = −2B² < 0, so the admissible count is 1 or 3 except at a deduplicated near-double root, where the two
  can classify differently. This is inherited byte for byte from `pr_c1`. No action.
- **N-2.** A21's homogeneity rows hold by construction of the simplex projection (`pr_lib.py:759-768`), so they cannot
  catch a wrong ∂X/∂y. A16 (`mp.diff`), Gibbs–Duhem and symmetry carry the derivative evidence. Inherited from M01.A12.
- **N-3.** R-523 refuses dense supercritical gas. CH4/C2H6 at 350 K and 20 MPa is refused `vapour_root_liquid_like`.
  This is a coverage cost of a rule that only refuses, already declared in `numerical_limitations`.
- **N-4.** The M-1 gap also exists in `pr-c1-v1`'s VAPOR evaluation of NH3 with light gas. There its flash is the
  caller's phase decision. `pr_c1.py` must stay byte-identical, so this is recorded for M01's owner and not changed here.
- **N-5.** A12's retrieval-equality test reads the committed JSON's booleans. Without the pins (CI), `--check` skips,
  so the JSON is pinned to the record bytes but self-attested. Same as M01. No action.
- **N-6.** A20 has no P < 10⁴ Pa state. Trivial; add it in the work order.

## Rulings on the batched questions (`docs/L01_DECISIONS.md:26-43`)

| # | Question | Ruling |
| --- | --- | --- |
| Q1 | A12 for C3H8 (+0.577 % at 600 K) | The bound was wrong. It becomes **2 %** (R-528, derivation §12.1). The comparand stays, C3H8 is not stopped, and the xfail goes. |
| Q2 | A12's scope | **All nine records.** CH4 at +0.68 % passes the amended bound. |
| Q3 | O2's critical point | **The stated parameters stand** (154.581 K, 5.043 MPa: the paper's and chemicals' `HEOS`). A07's comparand is the stated value. CoolProp's computed point (+0.018 K, +0.068 %) is a cross-check statement. Its effect on PR's a and b is ≤ 7·10⁻⁴, far below PR's own error. |
| Q4 | Spec numbers | Amended in §12.2: A18 CO2 v/b is **1.515**. A19 is **5.5× IAPWS-95's** P_sat(330 K) = 17.2 kPa and **6.14× PR's** 15 482 Pa. The assertions are unchanged. |
| Q5 | §4.4 vs §11 on `PACKAGED` | **§4.4 prevails.** The `PACKAGED` path, its link, the pyproject line and the two T08 test edits move with WO-L01-3, which is now also gated on Frank's L01-Q4. A01's mirror clause moves with them (§12.5). |

## T08.A32: amended (R-529), not refused

The amendment follows M01 §3.5's precedent: real records in the repository on a stricter rule, with distribution a
separate decision. L01's records meet the same vetting kind, and they carry `rights.source` and
`rights.redistribution`. The amendment checks that those statements *exist*; whether they are *right*, and whether
the records ship, is Frank's (L01-Q4, M01 Q-N4). With S-1 applied, nothing ships without the deliberate WO-3 commit.
The rule text is in spec §12.4.

## Fix work order WO-L01-R (build lane, Opus, about 120k context, branch `wp/L01`)

1. **`vapour_unstable` (R-540, spec §12.3)** in `pr_lib.py`, applied after the two existing guards, with
   `numerical_limitations` updated. Then remove the strict xfail in `test_l01_review_adversarial.py`.
2. **`l01_reference.py`:** the same guard in mpmath, written independently. Register the three M-1 states and the S-2
   pair as `guard_states` with tm, v/b and their codes, plus the claims (registered admitted states min tm ≥ 0.04;
   M-1 states ≤ −0.5; the S-2 flips). Then run `--emit`, and update `CLAIM_COUNT` and `GUARDS` in
   `test_l01_provider.py`. Add A20's P = 9.9·10³ Pa state.
3. **A12 (R-528):**
   - `components_crosscheck.py`: `A12_BOUND = 0.02` over all nine. Regenerate the JSON with
     `/home/user/venv-l01-sources` (`--emit`, then `--check`).
   - `test_l01_records.py`: parametrise over `NINE`, apply 0.02 and drop the xfail.
4. **Packaging (S-1):**
   - remove the `_data` link, the `pyproject.toml:77` line, the `PACKAGED` entry and its `resources.py` docstring
     clause;
   - revert `test_t08_w2_inventory.py:364` and `test_t08_w4_package_data.py:95` to their `wp/C-merge` text;
   - A01 now asserts that `RECORDS_PATH not in PACKAGED`, that no `_data` copy exists, and that `load_records()`
     reads the checkout copy.
5. **T08.A32 (R-529)**, `tests/test_t08_w2_inventory.py:425-460`:
   - replace `M01_RECORDS`/`M01_COMPONENTS` by `VETTED_RECORD_FILES`, mapping each file to its ids, its cross-check
     JSON and the retrieval predicate;
   - M01 keeps its current predicate. L01 needs all 13 `equal` flags, `retrieval_all_equal`, no
     `retrieval_failures`, and `records_sha256` equal to the file's SHA-256;
   - a record id present in two vetted files is the same whole mapping in each;
   - the real set equals the registry's (file, id) pairs;
   - rename the test `..._or_a_vetted_real_record_with_rights`.
6. **Done when:** `tests/test_l01_*.py` passes with no xfail, and `tests/test_t08_w2_inventory.py` and
   `tests/test_t08_w4_package_data.py` pass. Record the commands in `evidence/L01/<commit>/manifest.json` (`tested`;
   never `reviewed`) and the decisions in `docs/L01_DECISIONS.md`. Then a fresh `reviewer` checks M-1 to M-3 only.
