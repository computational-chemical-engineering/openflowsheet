# Specifier brief: confirm four S-6 procedure defaults (Q-S6a–d) and glance at X04 D-22

Status: brief, 2026-11-09. Design lane, short confirmation round (your earlier ruling is
`docs/reviews/REL040-s6-ruling.md`). **Do not spawn sub-agents yourself.** Reading only; the 35-test module may be run.

## Facts

The S-6 ruling's WO-6 (REAL re-take on kernel 6.12.113 at K3, proved digest-only) was rerun from a fresh worktree
(`docs/RP_DECISIONS.md` on `wp/REL040p`, commit `99ac9e6e`; outputs in
`/tmp/claude-1003/-home-frankp-Codes-OpenFlowsheet/fd59d98d-797a-4da8-93d6-9c61c6d4bdc7/scratchpad/wo6-fresh/`):
`RETAKE-DIGEST-ONLY PASS trust-region-study-real: changed-digests=103 digest=504 timing=528 path=128 version=0
platform=4 other=0 environment=equal`; T* = 653.1500351610193; same file set as the committed record. S6R-22 PASS
(environment sidecar equal, no attempt wrote stderr), S6R-23 IDAES proof PASS (differs only in `environment.platform`
and `inputs.reference_values_yaml_sha256`), S6R-25 PASS. S6R-24 (a trial J′ = head + both re-takes): step 11
`differing_members` [] and `REPLAY PASS REAL differences=0`, but step 14 failed one test that pinned the committed
record's platform to 6.12.111 — see Q-S6d.

Orchestrator defaults, taken and logged (`docs/roadmap/decisions.md` ~:947; `docs/RP_DECISIONS.md` § Q-S6d):

- **Q-S6a:** keep the build-decision class `path` (an attempt's log path names its experiment key's store directory;
  commit `81716c0a` on `wp/REL040p`).
- **Q-S6b:** "clean checkout" for an RC re-take means a fresh `git worktree add` (the first WO-6 run picked up a stray
  egg-info: sidecar 17→18 distributions).
- **Q-S6c:** an attempt's stderr stays in the identity (the first run's empty-file stderr digest did not recur from a
  fresh worktree).
- **Q-S6d:** `tests/test_m05_retake_digest_only.py::test_s6r10_the_committed_real_stem_retaken_on_another_kernel_passes`
  now reads the old platform from the committed record and re-takes onto a made-up platform `P_RETAKE`
  (commit `0282e4d6` on `wp/REL040p`); the asserted proof line is unchanged. Alternative: J updates P0/P1 with the
  re-take.

X04 (on `wp/X04`, read with `git show 9446a592`): **D-22** — to show `display_out_of_range`'s unit in the text
spelling (Frank's FQ4: °C/°F in human text), the message catalogue gains a param type `display_unit`
(`schemas/message-catalogue.schema.json` enum, `messages/render.py`, `docs/design/MSG-messages.md` type table); the
machine param stays `degF`. Rejected: a new template conversion `!unit`. Logged `docs/X04_DECISIONS.md` (D-22).

## Questions

1. Q-S6a–d: confirm each, or rule otherwise with the exact text/commit change. If Q-S6b belongs in RP §17.4 (A-11)
   as procedure text, give the sentence verbatim.
2. D-22: is a catalogue param-type addition covered by ADR 0075 / the MSG design, or does it need an ADR 0075 note
   (give the text)? It does not block X04's merge unless you say it must.

## Deliverable

Append a dated "Confirmation round (Q-S6a–d, D-22)" section to `docs/reviews/REL040-s6-ruling.md`. Commit on
**main** (docs only, named path, message `docs: S-6 confirmation round`, trailers `Co-Authored-By: Claude Opus 5.5
<noreply@anthropic.com>` and `Claude-Session: https://claude.ai/code/session_014hjTc57iVNbNxYG2kezzvv`; `git pull
--rebase` before push). Report ≤ 12 lines.

TRS2 shared: `uptime` first. Never read or touch `~/.config/procsim/`, `/home/frankp/s10-papers/`,
`~/.cache/seider3/`, `~/.cache/seider4/`; never copy the V17 login token (R-116).
