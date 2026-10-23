# Cloud session handoff to the workstation (2026-10-23)

The cloud session ran out of budget. Everything it made is pushed. What is on `main` and what still waits:

## On `main` (each with a read full gate and CI green on both architectures)
C1–C4, C7, C8, C9, C12 (build step), D1, S01, S02, S04. Details: `docs/V02_STATE.md` "Handoff" and the
`docs/*_DECISIONS.md` files.

## Waiting on branches (pushed; not merged)

| Branch | Package | State | Next action |
| --- | --- | --- | --- |
| `wp/C10` `c21f242` | **S05** IAPWS-95 provider (ADR 0045 Proposed; spec `docs/derivations/S05-IAPWS95-spec.md`) | WO-S05-1…3 done; review `docs/reviews/S05-review.md` (F1 fixed, R-595…R-600); manifest `evidence/S05/4ac00a0…` **tested**. Full gate PASS at `4ff1d55` (10947 passed) before `main` moved; gate PASS at `c21f242` (main with WS1 merged in; 10947 passed, 106 skipped). `main` has moved since (ADR 0044 Accepted, briefs) | Merge current `main` into `wp/C10`, run `scripts/gate.sh`, check CI, merge. Rights: IAPWS terms unread (C10-Q1); the provider is library-only and nothing ships before the terms are checked |
| `wp/C11` `6053c73` (+ possibly a local review commit, see below) | **S06** column purity / recovery / stage-temperature specifications (spec `docs/derivations/S06-spec.md`, R-601…R-607) | WO-1, WO-2 done; manifest `evidence/S06/be4ea98…` **implemented** (22/25: A02's I3 probe strict xfail; J8 deviation 0.182 of tolerance > 1/10 margin; gate not run) | The `reviewer` pass was running when the session stopped; if `docs/reviews/S06-review.md` is absent on the branch, run the review (brief: the open QUESTION lines in `docs/C11_DECISIONS.md`, Q-S06-WO1-1 and Q-S06-WO2-1), then the fix work order, manifest re-take, harvest, gate, CI, merge. `HARVEST_SIZE` will conflict with S05's at merge (re-count) |

## Open for Frank or the workstation
- C12's design step (amend T08.A32) waits for the six `unresolved` sources in `docs/l01-rights-check.md`
  (the cloud proxy refused their terms pages); `pr-lib-v1` records do not ship before that.
- S04's measured development-half coverage re-take can now be built on C9's W27 registration version 2
  (L01 spec WO-L01-3).
- Questions: `docs/FRANK_QUESTIONS.md` (C10-Q1/Q2, Q-S06-1/2, and earlier ones).
- Remote `wp/*` branches merged into `main` could not be deleted from the cloud (HTTP 403); the list and a loop are in
  the session's chat. `wp/M06-wo17` holds an unmerged WIP commit — keep it.
