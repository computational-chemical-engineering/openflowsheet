# LINE06 standing rules (every worker gets these; they decide nothing here)

- **The user's words** (2026-11-26, session chat): "let's go for 0.6 = F2 + F8 + X06. Update plans for this, create
  release/lines/0.6.json, prepare the campaign. Post decisions you need on the Decision Desk." Scope (R-1070, ADR 0057
  Amendment 3): F2 (ADR 0062, WO1 to WO7), F8 WO1 to WO3 and WO5 (ADR 0067), X06 (ADR 0078, to be written), then the
  0.6.0 release (REL060). Nothing else enters 0.6 without the user. F4 to F6 and F8 WO4, WO6 are out.
- **The user on cost** (2026-11-24): "there is too much testing and CI going on and this slows down development,
  wasting tokens". Hence: push a branch only when CI must judge a commit (a merge into `main`, a release candidate);
  docs, log and state commits stay local and ride along with the next real push. No backup pushes. The real release
  dispatch only after every CI run on `main`'s pushed head is green.
- **Authority:** the ADR of the package (0062, 0067, 0078) as it stands, read by section; `CLAUDE.md` (Scientific
  conduct; Branch and merge discipline; the two lanes; never set `reviewed` on your own package); for the release, RP
  `docs/derivations/release-procedure.md` and the `rel050` skill's order.
- **Proposed ADRs:** F2 and F8 are built on ADR 0062 and 0067 as written (as F3 was on 0061). A branch merges into
  `main` only after its ADR is Accepted on a signed Decision Desk card. Where an ADR is silent, the engineer takes the
  reading that changes no existing byte, logs it as `DECISION` in the package's decisions file, isolated in one
  commit, and carries on.
- **Identity:** no work order changes a released number, hash or replay. F0 (`scripts/corpus_identity.py --check`)
  passes on every branch before its merge and on `main` after it. ADR 0062 D8: a lowered run is a v1 run in every
  artifact (E-F2-3 bitwise). A changed digit is a bug in the change until shown otherwise.
- **Stops (report, do not choose):** a scientific ambiguity (escalate to the design lane through the state file); an
  ADR premise that the current code contradicts (post-S19 layout, ADR 0076); a change that would move F0; a test that
  can only pass by relaxing a check. A failed gate stays failed.
- **Lanes:** build lane: the work orders marked Opus or Sonnet, manifests, CI, docs. Design lane: one `architect` pass
  for X06 (ADR 0078); one `reviewer` pass per package (F2, F8, X06) before its merge; for the release one `specifier`
  (LINE06-L1, the line file's design fields) and one `verdict`.
- **Agents:** at most 2 at a time; small work orders (about 150k context each; at the cap commit, write where it
  stopped, end); never resume a large-context agent; a fresh agent per follow-up; no agent spawns agents. Reports of
  200 to 300 words; numbers go into the decisions file.
- **The user:** decisions go to the Decision Desk through hub (DECISION-REQUEST: "the user", never a first name;
  action text for every option). Act on a card only after `python3 ~/.claude/tools/decision_desk_verify.py` prints
  VERIFIED for the exact action; afterwards write `executed` on it. Every merge into `main`, every ADR acceptance, the
  tag, the dispatch and the PyPI approval are the user's.
- **Git:** one branch per package (`wp/F2`, `wp/F8`, `wp/X06`) in `.claude/worktrees/<id>`; merge commits, never
  squash; stage named paths, never `git add -A`; pushes need
  `git -c credential.helper= -c credential.helper='!gh auth git-credential' push`. Delete a worktree when its branch
  lands. Never copy the V17 login token (R-116); never read or touch `~/.config/procsim/`.
- **Every work order's acceptance includes the surface suites** (added 2026-11-26 after F2-WO1's miss):
  `tests/test_t07_*.py`, `tests/test_t08_w2_*.py` and `tests/test_m07a_surface_chain.py` (the served-interface,
  `list_models` and chain digests; chain links: F2 c_11 R-1072, X06 c_12 R-1073) besides F0. A
  change that moves a served digest registers the move in the same work order (the F1/F3/X04 `without_<pkg>` pattern
  in `tests/test_t08_w2_surface_digest.py`).
- **Runs:** tests a commit touches run locally; the full gate (`scripts/gate.sh`) only before a release-candidate cut,
  in its own clean detached worktree (`PATH=<main>/.venv/bin:$PATH PYTHONPATH=src`), no commits during the run. Long
  runs go through `.claude/skills/line06/run.sh` (one summary line, log in a file, PID recorded). GitHub: poll CI every
  300 s at most (shared API quota).
