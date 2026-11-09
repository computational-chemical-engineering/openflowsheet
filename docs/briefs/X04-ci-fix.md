# Engineer brief: X04 CI red at 4c818959 — strip chains, B50 surface content, default-install import; D-21

Status: brief, 2026-11-09. Build lane. **Do not spawn sub-agents yourself.**

Branch `wp/X04`, worktree `/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/x04`, head `3e16b359` (FQ4 merged;
Frank's human reviews recorded `a39ebfff` — never edit `REVIEW.json`'s human entries). Shared rules as
`docs/briefs/X04-build-A.md` (venv/PYTHONPATH, serial tests, decisions log from D-22, stop rules, cap ~150k, trailers,
named paths, forbidden paths).

CI run 42624006442 at `4c818959` failed on both archs; the digest is `docs/briefs/X04-ci-red-digest.md` (on main).
Fix each, following the existing precedent for the earlier packages (`git log -S without_opt -- tests/` shows how OPT
and ST were added to the same chains):

1. `tests/test_m02_schemas.py:274` and `tests/test_m04_study_job.py:293`: add `without_x04` first in the strip chains
   (X04's job_result `display_units` reaches `submit_job`'s resolved response). The expected digests must not change.
2. `tests/test_t08_b50_surface_content.py` (:159 get_project `ambient_pressure`, :234, :245, :255 a51_b/a51_c): register
   X04's surface content the way ST/OPT did there — never edit a pinned value without a strip proving the pre-X04 one.
3. default-install: `tests/test_x04_messages.py:35` imports `openflowsheet.application.bindings.mcp` (needs `anyio`,
   absent in the default install). Guard it the way other MCP-using tests do (find the pattern; e.g. importorskip or
   the transport marker), so the module collects in the default install and those nodes skip there.
4. **D-21 (orchestrator decision, 2026-11-09):** apply Frank's FQ4 rule to `display_out_of_range`'s human text: the
   `{unit}` param is rendered through `units.display.text_unit` in rendered text, and stays `degF`/`degC` as a machine
   param. Test it. Mark D-21 decided in `docs/X04_DECISIONS.md`.
5. Then run **the whole default suite once locally** (it is what CI runs; this is the check the targeted batteries
   missed): `scripts/check.sh` if it fits the machine (`uptime` first; ≤ ~36 busy cores; it is long — run it in the
   background with its output to a log, read the summary line, grep failures only). Expected: 0 failures (Frank's
   reviews are recorded, so the description test passes). F0 PASS; MSG check; ruff/format.
6. Update `docs/X04_HANDOFF.md`; push `wp/X04`. Report (≤ 15 lines): commits, the full-suite summary line, F0, anything
   stopped on.
