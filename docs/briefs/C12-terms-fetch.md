# C12 — finish the unresolved rights rows from the workstation (build lane)

**Task.** `docs/l01-rights-check.md` marks rows RC-01, 02, 03, 05, 07, 08 (and the cross-check rows if affected) `unresolved`
because the cloud session could not reach the public terms pages (`docs/C12_DECISIONS.md`). This workstation has web
access (WebFetch / curl). Read and quote, for each row, the governing terms — the list at `docs/l01-rights-check.md` §4
"To finish the unresolved rows": NTRS record 19940013151 (NASA TM-4513); `https://atct.anl.gov/` (terms, citation
request for 1.112); `https://www.nist.gov/srd/public-law`; `https://janaf.nist.gov/`; PubChem's data policy; CAS's terms
for CAS RN use; the CIAAW atomic-weights page; the publishers' terms for the nine EOS papers (§3 lists them; for papers,
the relevant question is whether numerical constants transcribed from a paper are protectable — quote what the publisher
or a primary source says, do not opine from memory).

**Rules.** Quote verbatim with URL and fetch date; no terms from recollection. Re-mark each row only by the doc's own
criteria (§2 definitions); where a page is still unreachable or the terms are silent, keep `unresolved` and say why. You do
not decide whether the records ship (Frank's call) and do not answer A32-Q1…Q7 (design lane). Do not edit the records.
Work in worktree `.claude/worktrees/c12w` on branch `wp/C12-terms` from `main`. Update the rows, §3 summary and append one
line to `docs/C12_DECISIONS.md`. Run `pytest -q tests/test_l01_attribution.py` (in `.venv`) if it reads the doc. Commit,
push the branch, do not merge. Report ≤150 words: per row old → new status, one-line reason. Trailer:
`Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` /
`Claude-Session: https://claude.ai/code/session_014hjTc57iVNbNxYG2kezzvv`.
