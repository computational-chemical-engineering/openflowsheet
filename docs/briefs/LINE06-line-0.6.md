# LINE06-L0: the 0.6 line file, draft (build lane, 2026-11-26)

`release/lines/0.6.json` is drafted from `release/lines/0.5.json` at the planning commit, for the scope of R-1070
(ADR 0057 Amendment 3): F2, F8 WO1 to WO3 and WO5, X06. It loads clean (RP.L01 to RP.L04, RP.L06, RP.L07, RP.L09 to
RP.L11 by `release_gate.load_line` and `line_problems`: no problems; `line_release` = 0.6.0). RP.L05 and RP.L08's
scripts are checked only at `C`. The release design pass **LINE06-L1** (a `specifier`, once, RP §13 (1), as REL050-L1
was for 0.5) finalises the design-lane fields before K3. Until then the file is a DRAFT and no release reads it.

## 1. Fields and why they differ from 0.5's (`changed`)

| Field | 0.6 draft | Lane | Why |
| --- | --- | --- | --- |
| `gate_set.name` | `v0.6-gate-v1` | build | new line |
| `gate_set.covers` | `0\.6\.0(?:(?:b|rc)[1-9][0-9]*)?` | build | 0.6.0 and its pre-releases; a patch widens it (RP A-14) |
| `gate_set.evidence_package` | `REL060` | build | ADR 0074 D2, RP.L11 |
| `gate_set.verdict_document` | `docs/reviews/REL060-verdicts.md` | build | follows the package id |
| `gate_set.rc_record` | `docs/REL060-rc-record.md` | build | follows the package id |
| `gate_set.envelope_id` | `v0.6-envelope-1` | build | set at K3 (RP §7.1); main carries `v0.2-envelope-dev` until then |
| `gate_set.packages` | 0.5's plus `F2`, `F8`, `X06` | build | each needs `evidence/<ID>/<commit>/manifest.json` `tested` at C |
| `gate_set.required_adrs` | 0.5's plus `0062`, `0067`, `0078` | build (proposal) | the three ADRs 0.6 builds; 0078 is X06's, number reserved |
| `changelog_what_it_is_not` | three phrases changed | design (proposal) | see 3 |

Unchanged from 0.5 (proposal): the claim set V11 to V20, W21 to W26, X31; `not_claimed` W27; the clause; `gates[*]`;
`rc_steps`; `frank_items`; `rejudge_waits`; `links_item`; `rc_items` (0.5's nine).

## 2. Proposed for LINE06-L1 (not in the draft, because their scripts do not exist yet)

- **rc item `WHEEL-F2-F8`** (or `WHEEL-F1-F3` widened): F2's new schemas (`process-revision-v2`, `specification-v2`,
  `connection-definition`, payload schemas) and F8's (`run-manifest`, `replay-report`, `records-index`,
  `run-evidence`) ship in the wheel and load from it in a fresh venv. Owner `scripts/wheel_data_check.py` (RP §3.6
  item 4: a release that ships package data beyond the previous one's needs its own item).
- **rc item for the line clause** "a v2 revision with store-pinned records solves on the legacy route on all three
  OSes": the registered v2 case (F2 E-F2-3's lowering case) run on the Linux, Windows and macOS CI legs (X07a), read
  from the candidate's push run. The design pass decides whether this is an `rc_items` entry or a gate (RP §3.3; a new
  gate needs registered criteria, which 0.5 avoided, REL050-L1 D-3).
- **rc item for X06**: MCP over HTTP answers `list_capabilities` from the installed wheel (a loopback smoke), if ADR
  0078's exits make it a release check.
- **Phrases** (RP.S10: each once in the notes): "v2 revision documents solve only on the legacy route" and "no F4
  property methods, F5 phase equilibrium or std.* units" replace "no v2 revision documents" and "no solve reads the
  component record store"; "no W27 claim in 0.6.0". Whether a v2 solve reads the record store (it pins records by
  hash; the legacy route reads the lowered v1 document) is the design pass's call, from F2's built behaviour.
- **`frank_items`**: 0.5's five carry unless the lapse report at C says otherwise (RP §8.4).

## 3. Not established by this draft

That 0.6 can be released: nothing of F2, F8 or X06 is built. That the claim set is right for 0.6: R-1070 adds no
registered gate criteria, so the draft keeps 0.5's, as 0.5 kept 0.4's (REL050-L1 D-1); LINE06-L1 judges it.
