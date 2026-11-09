# Specifier brief: S-6's three record findings — kernel in the replay fingerprint, step 11's IDAES record, journey J

Status: brief, 2026-11-09. Design-lane ruling; blocks 0.4.0's cut. **Do not spawn sub-agents yourself.** Reading only.

## Facts

S-6 rehearsal (`docs/RP_DECISIONS.md` § S-6 on `wp/REL040p`; records
`/tmp/claude-1003/-home-frankp-Codes-OpenFlowsheet/fd59d98d-797a-4da8-93d6-9c61c6d4bdc7/scratchpad/rel040p/s6-work/rc`)
and its debug (`docs/S6DBG_DECISIONS.md` on `wp/S6dbg`, worktree `.claude/worktrees/s6dbg`):

1. **Step 14/15 `a60.w24.m05_g10_real_replay`: `ReplayDivergedError`** (cold execution at 673.15 K). Not code:
   v0.3.0's own code diverges the same way today, in both `m05`'s and `alpha-main`'s `.venv-nlp` (identical packages).
   The live request differs from the recorded one only in `environment_fingerprint_sha256`, which hashes
   `platform.platform()` (M02 §2.4, `src/openflowsheet/…/child.py:409`). With kernel `6.12.113` replaced by `6.12.111`
   the live fingerprint equals the recorded `dfce4150…`. The REAL record was taken 2026-10-16 under 6.12.111 (0.3.0's
   RC ran in that boot); the workstation runs 6.12.113 since its 2026-11-06 reboot. Repro (9 s): `OMP_NUM_THREADS=1
   PYOMO_CONFIG_DIR=<venv>/share/pyomo PYTHONNOUSERSITE=1 PYTHONPATH=src:<cache>/nlp-test-tools <venv>/bin/python
   scripts/m05_wo9_real.py --replay`. Engineer's options: (1) re-take the REAL record on the current kernel, plus an RP
   note that a kernel upgrade breaks the replay until a re-take (default); (2) ADR dropping the kernel from the
   fingerprint (moves every experiment key and every M02/M04/M05 store); (3) replay ignores the fingerprint (weakens
   G10; not recommended).
2. **Step 11 `a40.idaes_numbers_identical`**: differs from the committed IDAES record (`7dc55096…`) in
   `environment.platform` (presumably the same kernel change) and `inputs.reference_values_yaml_sha256` (an input file
   changed since the record — find which commit and whether the reference values themselves changed or only the file).
3. **Step 15 (W25 journey at J)**: fails with 0.3.0's J `2d945b5d` as expected; 0.4 needs its own J.
4. RP already says (`docs/derivations/release-procedure.md`): J is K3 plus the re-taken G10 records (R-458, §4.5
   ~:315–321, §7.1 ~:633, :662); "the five in-process G10 records are re-taken, digest-only, proved with
   `scripts/m05_retake_diff.py --digest-only`"; R3 carries M05's REAL record only if `carry.r3_files` are byte-equal
   between M05's run commit and J, otherwise R3 re-runs M05's study at J; §~952 "Nothing is edited, re-run or re-taken to
   pass."

## Questions (rule each, with the exact procedure text or record action)

1. Is the REAL-record divergence handled by the existing procedure at K3 (R3 re-run at J / the R-458 re-take), or does
   RP need an amendment (environment/kernel change between record and RC)? Pick among the engineer's options or another;
   if a record is re-taken, say which, by which command, with which proof (what must be equal), and where it lands.
2. Step 11: re-take the IDAES record, or is the `reference_values_yaml_sha256` change a real input change that needs a
   verdict first? State the rule.
3. Journey J for 0.4: confirm it is recorded at the cut by the procedure as written (no action now), or say what must be
   done before K3.
4. Whether any of this needs Frank (default: no — procedure, not a value judgment; but a kernel-dependent identity may
   be worth one line to him).

## Deliverable

`docs/reviews/REL040-s6-ruling.md` with the rulings, any RP amendment text verbatim (as A-11…, dated), the register
entry text if one is needed (next free: R-1008; R-1007 is RP.L11 on `wp/REL040p`, R-1010… are X04's), and a numbered
work order for the build lane. Commit on **main** (docs only, named path, message `docs: S-6 record findings (ruling)`,
trailers `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` and `Claude-Session:
https://claude.ai/code/session_014hjTc57iVNbNxYG2kezzvv`; `git pull --rebase` before push). Report ≤ 15 lines.

TRS2 shared: `uptime` first; reading only (the 9-second repro may be run). Never read or touch `~/.config/procsim/`,
`/home/frankp/s10-papers/`, `~/.cache/seider3/`, `~/.cache/seider4/`; never copy the V17 login token (R-116).
