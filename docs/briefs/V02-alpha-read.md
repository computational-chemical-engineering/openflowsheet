# Design-lane read: alpha gate WO-5, WO-8, WO-9 (one pass, before WO-10 cuts C_α)

Branch `wp/V02-alpha-gate` @ `5252040`, worktree `.claude/worktrees/alpha-gate`. Spec
`docs/derivations/V02-alpha-release-spec.md` (WO table l.988–998; assertion catalogue §10); ADR 0028 (Proposed);
ADR 0021 D4. Build log `docs/design/V02-alpha-build-decisions.md`. Commits: WO-6 `8427421`, WO-5 `b44f684`+`69cfc8e`,
WO-8 `e808406`+`f6a748a`, WO-9 `5252040`. Gates: 8558 passed at `f6a748a`; WO-9: 8565 passed then a ruff-only fix.

## Read and rule (one line each, with the change that implements it)
- **WO-5** (`scripts/m07a_rc.py surface`, CI input `rc_alpha`, step 8 chain + controls (i)–(iv), A37). B-WO5-1: c_2's
  digest is not registered anywhere; pinned `383b4e2c…` (served on the merged tree = M02 manifest) — write the register
  entry or rule otherwise. B-WO5-5: "R-133's files" have no registered hash; the two hashes in `REVIEW.json` at v0.1.0 used.
- **WO-8** (T08 harvest: 58 limitations + 2 non-pass checks classified E/S/P/B, `HARVEST_EXCLUDED = ()`, A50). B-WO8-1…4:
  the classification is a draft — confirm or correct it; should `[8]` (library-only) become an envelope row and `[9]`
  (A34's audit scope) a backlog id? B-WO8-5: the v0.1 "18 manifests" count scoped to P00–T07.
- **WO-9** (`## v0.2.0a1` changelog section, A52): the "What it does" prose is the implementer's own summary of M01, M02,
  M06 — check it against the claim set (V11–V20, W21, W22; W23–W27 not claimed) and §10.1; A52 (g) reads working-tree
  manifests, so M07a's own manifest or M04's will add a row — rule how M07a's row is treated; ADR 0021 D4 used for the six
  headings (ADR 0028 D4 is "Version and candidate").
- Anything that would make WO-10's RC fail or the claim set overstate.

## Deliverable
`docs/reviews/V02-alpha-read.md` + register entries (next free after R-318; check main and wp/* branches), committed on
`wp/V02-alpha-gate` (named paths; no push). Verdict: may WO-10 cut C_α after the listed fixes? Report ≤ 250 words.
