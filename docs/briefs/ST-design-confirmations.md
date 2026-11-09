# Specifier brief: ST — the five open design-lane confirmations before WO-7

Status: brief, 2026-11-08. Design lane, one ruling round (CLAUDE.md "batch design-lane questions"). **Do not spawn
sub-agents yourself.** Frank accepted ADR 0068 on the decision board (2026-11-08) with the ST defaults except O3 (the
web-shell display is now in ST; a build-lane work order, not yours).

## The question

The ST fix round (`wp/ST` `e16f7e6f`, worktree `/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/st`) applied rule
R1′ from the review (`docs/reviews/ST-review.md` M1, ruling (b) scoped) and left five items for a design-lane
confirmation (`docs/ST_DECISIONS.md` lines ~207–231, quoted in full there). For each: **confirm, or rule otherwise**
with the exact change the build lane must make.

1. **M1-1** — a flagged stream with no heater-style split that would reach R3 keeps `phase_source: "flash"` and
   `flash_near_phase_boundary: false`. Alternatives: a new source label, or the flag true.
2. **M1-2** — an R1′ phase whose provider returns mixture `h` takes `n_tot·h`, as the γ–φ verifier's `_phase_flow`
   does; the review's text names only the per-component form. Alternative: `property_not_provided`.
3. **M1-3** — Q4.R12 (b)(ii) dropped from `_near_boundary` as dead after R1′ (note §4.2 and ADR D3 say so).
4. **S1-1** — G8u compares a unit only with its whole-unit row `energy_balance.<U>`; `.hot`/`.cold` and the pump's
   `.work_relation` are other residuals. Alternative: compare every row.
5. **Products-style flash feed (a fact, no default):** a flagged products-style split's feed (`split.stream` = the
   drum's inlet) that is undeclared takes R1′'s no-split branch (`flash_failed`), although the verifier flashes that
   feed at its own state. No corpus or served case has one (flagged streams: 4 R1′, 2 declared, 0 no-split). Rule
   what ST must report there (and whether a degeneracy row / test case is needed), consistent with ADR 0068 D4 as
   amended by R1′.

## Constraints

No change may move any of the 44 served 0.3.0 documents (S4: byte-identical except SC-1/SC-3 from M1) or G7/G8/G8u
results on the corpus, unless you say so and why. A ruling that changes code states file, function and the test that
would catch a regression. Read: `docs/design/ST-stream-table.md` (§4, §12), `docs/adr/0068-*.md`, the review M1/S1,
`docs/ST_DECISIONS.md` ~180–235, and the code at the named functions (`_decide`, `_Properties.enthalpy_flow`,
`_near_boundary`, `_g8u`) — reading only.

## Deliverable

A short "Design-lane confirmations (2026-11-08)" section appended to `docs/reviews/ST-review.md` **on `wp/ST`**, one
numbered ruling per item (confirm / change + the exact change); if ADR 0068 or the design note's text must change,
make that docs edit too, quoting the replaced text in a dated amendment. Commit docs-only on `wp/ST` (named paths,
message `ST: design-lane confirmations M1-1…M1-3, S1-1, products-style feed`, trailers `Co-Authored-By: Claude Opus 5.5
<noreply@anthropic.com>` and `Claude-Session: https://claude.ai/code/session_014hjTc57iVNbNxYG2kezzvv`), push. Report
≤ 15 lines: each ruling in one line, and which need a code change. TRS2 shared: no test runs needed (reading only).
Never read `~/.config/procsim/`, `/home/frankp/s10-papers/`, `~/.cache/seider3/`, `~/.cache/seider4/`.
