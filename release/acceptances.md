# Standing acceptances

**Authority.** `docs/derivations/release-procedure.md` (RP) §8 is the normative text; ADR 0055 D3 is its policy
(R-918, R-919). The generic gate (`scripts/release_gate.py`, WO-R3) reads this file for every line whose
`gate_set.acceptances` names it, from the 0.4 line on. The 0.1–0.3 lines keep reading their policy ADRs.
**Seeded** 2026-11-06 by WO-R1 (design lane, `specifier`) at C₀.₃ = `a3e508e3` (0.3.0's release candidate):
ADR 0053's six cells verbatim (D3.6), and the licence acceptance of V03 spec §11 N-11 (ADR 0055 N-7).

**How the gate reads it (RP §8.1).** Exactly one table has a `Frank's acceptance` column (failure clauses) and
exactly one has a `Frank's answer` column (decision items). Each is read by column, and each answer cell by the
R-466 cell rule: with `*` and backticks removed it starts `accepted, YYYY-MM-DD`. The `Scope` cell is the text
between its outer backticks, read as written: it is never passed through the cell rule's `*` removal, which would
delete a glob's `**`. `Fingerprint` is 64 lower-case hex digits; `Accepted at` is a 40-hex commit id.

**How it changes (RP §8.4, §8.5).** A row stands at C while its scope recomputed at C equals `Fingerprint`. A row
whose scope differs has lapsed and counts as absent. It is replaced only by Frank's new dated answer, with the
fingerprint and commit at that C; the replaced row moves, unedited, to the history list at the end. Nothing else
edits a row. Table rows are longer than 120 columns because a table row cannot wrap and answer cells are verbatim.

## Failure clauses

| D3 clause | Frank's acceptance | Scope | Fingerprint | Accepted at |
| --- | --- | --- | --- | --- |
| V14 (b) | accepted, 2026-10-30 — Frank, verbatim: "Accept (Recommended)" (the default in this row; asked in plain words after W21's new judgement) | `paths:src/openflowsheet/**,benchmarks/t08/ptc_r1/**,docs/reviews/T08-verdict-V14b.md` | `7506c9086342b8bbe038f9aef651d18e98d3268305937f3c52f4ac999a6f7a77` | `a3e508e35fc5451fe56fa7b70941621992d35b50` |
| X31 (c) | accepted, 2026-10-30 — Frank, verbatim: "Accept (Recommended)" (the default in this row; asked in plain words after W21's new judgement) | `paths:docs/reviews/S09-verdicts.md,benchmarks/s03/**,benchmarks/s09/**` | `59503316001e10b9c3760e41271d5be31f515cdd99a6581fe6f6e87276611864` | `a3e508e35fc5451fe56fa7b70941621992d35b50` |

## Decision items

| Frank item | Default | Frank's answer | Scope | Fingerprint | Accepted at |
| --- | --- | --- | --- | --- | --- |
| Claim set | V11–V20, W21–W26 and X31 claimed; W27 not claimed (no campaign at 0.3.0). Alternative: claim W27 with a new W27 campaign under registration version 3 (R-808; three canaries and the approved runs; USD 15–45, the scale Frank approved for 0.2.0; about one working day), with C_W cut before C | accepted, 2026-10-30 — Frank, verbatim: "Yes, no W27 claim (Recommended)" (the default in this row; asked in plain words after W21's new judgement) | `extract:claim_set` | `f4a3cfbee85d5c3d6fff6df5c1224e6d68fff7a14d88ff59e4017cb77990a881` | `a3e508e35fc5451fe56fa7b70941621992d35b50` |
| V17 carry | carry `v17-c2`'s agent evidence (V17, and T08.B50's surface) across R-192, R-234 and R-295, with no new link at C (V03.A23). Alternative: a new V17 campaign (about USD 10, one hour) | accepted, 2026-10-30 — Frank, verbatim: "Reuse 0.2.0's (Recommended)" (the default in this row; asked in plain words after W21's new judgement) | `extract:links + extract:served_digest` | `367fdf465f7793d9c4224da4617130993a05d1f029b749b593d2f97d6c2d98f6` | `a3e508e35fc5451fe56fa7b70941621992d35b50` |
| M02 N1 | ship the reactor child process labelled "not a sandbox" | accepted, 2026-10-30 — Frank, verbatim: "Yes, ship it (Recommended)" (the default in this row; asked in plain words after W21's new judgement) | `paths:src/openflowsheet/adapters/external/**` | `c1b16371d5bd35a668e8ae3b11194ab41459cbf6ce165662dfdbd0015fff9cf4` | `a3e508e35fc5451fe56fa7b70941621992d35b50` |
| M03 N1 | accept the licences of the optional `nlp` extra | accepted, 2026-10-30 — Frank, verbatim: "Accept (Recommended)" (the default in this row; asked in plain words after W21's new judgement) | `extract:pyproject_extra:nlp + paths:docs/m03-ipopt-audit.md,benchmarks/m03/ipopt-inventory-*.json,scripts/build-m03-ipopt-env.sh` | `8eafbfef5ec2f333e341659182d4d824852c11b6bc4532914a9879715956a430` | `a3e508e35fc5451fe56fa7b70941621992d35b50` |
| coolprop and lca licences | accept the licence decisions of the two new extras: `coolprop`, R-624 (CoolProp is MIT; its numpy as under R-135); `lca`, R-900 (WO-B1/D04's audit of the pinned Brightway lock). V18 stays PASS | accepted, 2026-10-30 — Frank, verbatim: "Accept (Recommended)" (the default of V03 spec §11 N-11, asked in plain words after W21's new judgement; R-624 and R-900 accepted; V18 stays PASS) | `extract:pyproject_extra:coolprop + extract:pyproject_extra:lca + paths:requirements-coolprop.lock,docs/s07-coolprop-licences.json,benchmarks/e01/brightway/lca-pip.lock,docs/e01-lca-licences.json` | `0bb1c6342c455070cc02bf754274efb4d7fcf8f9180bafefcdbd7783e78b2ce7` | `a3e508e35fc5451fe56fa7b70941621992d35b50` |

## Seed computation (not read by the gate)

Computed at `a3e508e35fc5451fe56fa7b70941621992d35b50` by RP §8.2's definitions, with the design lane's reference
implementation (not committed; RP §15 Q-9). REL.A19 recomputes every value with WO-R3's implementation. The term
hashes are listed so that a disagreement can be traced to one term. `files` counts the tree entries a `paths:` term
selected; every glob matched at least one (RP §8.2, rule P3). For an `extract:` term the last column is its
canonical JSON, the exact bytes whose SHA-256 is the term hash.

| Row | Term | Term hash (SHA-256) | Value or files |
| --- | --- | --- | --- |
| V14 (b) | `paths:src/openflowsheet/**,benchmarks/t08/ptc_r1/**,docs/reviews/T08-verdict-V14b.md` | `1ee9389695dd2bb7ecdf47f4c932900346c4eabab442820f83451a31e7b45072` | 301 files (`src/openflowsheet/**` 287, `benchmarks/t08/ptc_r1/**` 13, `docs/reviews/T08-verdict-V14b.md` 1) |
| X31 (c) | `paths:docs/reviews/S09-verdicts.md,benchmarks/s03/**,benchmarks/s09/**` | `aeb7c5e5fb96e890aa3b572c1bc9a3c890adf96c9f6bf40b77957b056a7c985e` | 84 files (`docs/reviews/S09-verdicts.md` 1, `benchmarks/s03/**` 61, `benchmarks/s09/**` 22) |
| Claim set | `extract:claim_set` | `cf80a54ec21cd859bb86505f0b1d3d0b6db95839d31ddcc2848f1e48fdb2319b` | `{"claimed":["V11","V12","V13","V14","V15","V16","V17","V18","V19","V20","W21","W22","W23","W24","W25","W26","X31"],"not_claimed":["W27"]}` |
| V17 carry | `extract:links` | `fa4d94045d52947649a9ce4a7324517a38a913df789a5a98fce09ce431b4c797` | `["R-192","R-234","R-295"]` |
| V17 carry | `extract:served_digest` | `54d3fe119042936b7d419afb07775a10d8b2592362052e1ead482d556cd3a6fb` | `"455d01eb2f420032b27358798e6b331a0120aa1857f02ce3cb7851647849e125"` |
| M02 N1 | `paths:src/openflowsheet/adapters/external/**` | `1027b7c169c1be820c60a520b034f08370e11a6f239491e35cd408fa8e718811` | 3 files (`src/openflowsheet/adapters/external/**` 3) |
| M03 N1 | `extract:pyproject_extra:nlp` | `1d8e69bd6f2854a0ce183b6a1d04e1435ad5b36b3d08113b4440c540b7e37256` | `["cyipopt==1.7.0","packaging==26.3","pyomo==6.10.1"]` |
| M03 N1 | `paths:docs/m03-ipopt-audit.md,benchmarks/m03/ipopt-inventory-*.json,scripts/build-m03-ipopt-env.sh` | `628e6936bff6caf8431b351aa74ef9f59c8d42986ac7d5fa9cb325cad1a0ad7e` | 3 files (`docs/m03-ipopt-audit.md` 1, `benchmarks/m03/ipopt-inventory-*.json` 1, `scripts/build-m03-ipopt-env.sh` 1) |
| coolprop and lca licences | `extract:pyproject_extra:coolprop` | `e0a7d78446ffd5d4170426d691f88772fa73134616fdef400eba6b3447b97fed` | `["CoolProp==8.0.0"]` |
| coolprop and lca licences | `extract:pyproject_extra:lca` | `133d618a85d023c606ed5f09ca71b33f0f431f3d883cf668ea3d6406416f4372` | `["bw2calc==2.5.0","bw2data==4.7"]` |
| coolprop and lca licences | `paths:requirements-coolprop.lock,docs/s07-coolprop-licences.json,benchmarks/e01/brightway/lca-pip.lock,docs/e01-lca-licences.json` | `e9dee04fff7b03e789e0234a59cae1d088a51949374cfbd6dec1f8ea60003c69` | 4 files (`requirements-coolprop.lock` 1, `docs/s07-coolprop-licences.json` 1, `benchmarks/e01/brightway/lca-pip.lock` 1, `docs/e01-lca-licences.json` 1) |

**Why these scopes (ADR 0055 D3.6).**
- `X31 (c)`: its evidence is a document fact (S09 verdict 3: one independent reference for RC4), not re-run, so
  R-453's determining files are the verdict document and the reference data.
- `V14 (b)`: `gate_row:V14` needs the evidence fingerprint Φ, which is deferred with ADR 0055 D2 (Frank,
  2026-10-31). Until D2 is taken up the scope is D3.6's path fallback, which puts `src/` in it (R-453). It lapses at
  any release that changes `src/openflowsheet/`, so V14 (b) is asked again at 0.4.0 (R-919) and at every such
  release until D2. Measured at `main` = `1fcdbb1b`: this term already differs from the seed, while every other
  `paths:` term, the three `pyproject_extra` terms and `links` are equal to theirs (`claim_set` and
  `served_digest` are read from 0.4.0's line file and RC records, which do not exist yet).
- `coolprop and lca licences`: the two extras' requirement lists, the coolprop lock (R-624), the lca lock (R-900),
  and the two licence inventories that MR-12 v03 cites (V03 spec §9.3).

## History (not read by the gate)

Replaced rows are moved here unedited, each with the date and the C at which it lapsed. None yet.
