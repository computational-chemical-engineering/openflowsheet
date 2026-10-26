# Ruling round: three build-lane decisions from S10-C and S08b (design lane)

Repository `/home/frankp/Codes/OpenFlowsheet` (main checkout, branch `main`, head `75b226c6`; read-only for you). S10-C and
S08b are merged. Each decision below is already in main as an isolated, revertible commit, logged as a build decision. Rule on
each: **accept**, or **change** (with exact replacement text/code intent and the register entry), or **revert**. The governing
rule: no relaxed checks, removed cases, or narrowed denominators to pass a gate (`CLAUDE.md`, "Scientific conduct"); Frank's
standing directive: as few limitations as possible.

## D1 — S10-C structure gate G2 admits three named files (`docs/S10C_DECISIONS.md`, search "G2")

S10-C's spec froze `src/openflowsheet/numerics/` (G2: no edit under frozen paths relative to the merge base, plus a test-edit
allow-list). R-782 (registered design change, `docs/derivations/S10C-absent-component.md`, with its own `reviewer` pass
`docs/reviews/S10C-r782-review.md`) had to edit `numerics/newton.py` and two tests (`tests/test_t06_w20_counters.py`,
`tests/test_t07_interrupt.py`, re-pinned witnesses). The generator `scripts/s10c_evidence_manifest.py` now admits those three
paths by name so the manifest can be `tested`. Alternative: leave G2 failing, manifest `implemented`.

## D2 — T07 THM-09 start 4 on an unregistered machine class (`tests/test_t07_interrupt.py:63-81, ~230-245`)

The record length of THM-09 start 4 (uncapped) is pinned per registered machine class (`THM09_RECORDS`, keyed by
`benchmarks/t06/ensemble.py:359 machine_class()`, which follows T06 §7.5: an unregistered class is "reported, never gated").
On an unregistered class the length is not pinned; the test still asserts length > 89 (so every k in K=(1,…,89) interrupts
inside the run) and runs every record-k interrupt identity check against that machine's own reference run.

## D3 — T07-1: ci-x86-64 unpinned (`docs/S08b_BUILD_DECISIONS.md`, "T07 pin on ci-x86-64"; commits `f4b5d8dd`, `1d4ca814`)

Measured: THM-09/4 length = 94 on ref-x86-64 (local) and on ci-x86-64 in CI 40295317759 and 40315691647; **136** on ci-aarch64
and on ci-x86-64 in CI 40359016227 (S08b, which changes no numerics: `S08-IDENTITY`/`S10C-IDENTITY` PASS). The ci-x86-64
class (`benchmarks/t06/registry` `ensemble.machine_classes`) registers no `cpu_model`; GitHub's ubuntu-latest runners have been
seen as AMD EPYC 7763 and 9V74 (R-782 note §8 Q-C; register entry "ci-x86-64's runner CPU changed"). The CPU of run
40359016227's check job was not logged. Decision: drop ci-x86-64 from `THM09_RECORDS` (treated as D2), and the failure message
now names the CPU model. Alternative: pin per (class, CPU model) — needs a measured length per runner CPU.

Questions specific to D3: is unpinning correct, or should the class registry gain `cpu_model`-split CI classes (and how would
the lengths be measured without a dedicated dispatch)? Should the test print the CPU model and length on every CI run so the
evidence accrues? Does R-627 (machine-class policy) or T06 §7.5 already answer this?

## Deliverable

Write your rulings to `/tmp/claude-1003/-home-frankp-Codes-OpenFlowsheet/4eb41cce-83fd-4812-8ebc-a76f78cb2117/scratchpad/ruling.md`:
per decision, the ruling and reasoning (≤ 10 lines each), any register entry text (numbered after the register's last id —
check `docs/decision-register.md`'s tail), and any code change as a precise work order. Do not edit the repository. Report in at
most 15 lines.
