# L01 handoff (design lane `specifier`, 2026-10-22)

**Done (on `wp/L01`, not pushed):** ADR 0043 (Proposed); `docs/derivations/L01-spec.md`;
`docs/derivations/scripts/l01_projection.py` with `--check`, whose record `l01_projection.json` is ruff-clean and
reproduces byte for byte; register R-520…R-527; ten DECISION lines; Frank questions L01-Q1…Q3.

**Result:**
- Water, CO2, O2, ethane and propane are admitted vapour-only via ADR 0026's PR, in a separate route `pr-lib-v1`.
  The route also carries H2, N2, Ar and CH4, copied verbatim. C1 is byte-identical.
- CO is stopped by W27-R24 (c) (`Co` casefolds to `CO`).
- Everything else needs a new method; IAPWS-95 is the largest.
- Development projection: CANDIDATE 0 → 0. COMPONENT 9 → 6 and ROUTE 0 → 3 (the IAPWS pump variants).

**Findings, for others to act on:**
- F-1: W27 cannot judge a second `cubic_pr` route (R-24 (a) and (d)). It needs a W27 Amendment 3.
- F-2: W27's casefold spelling check.
- F-3: the brief's re-take command overwrites `coverage.json` and prints all-450 counts. Do not run it.

**Next executable action:** wait for Frank on L01-Q1 and Q2. The default (Q2: yes) is to dispatch WO-L01-1 (records;
needs chemicals 1.5.2, Cantera 3.2.0 and CoolProp 8.0.0, so the workstation or a pip-capable session), then WO-L01-2
(provider plus a 50-digit reference generator, then a `reviewer` pass). Hold WO-L01-3 until W27 Amendment 3.

**Open facts:**
- Q-4: are C2H6 and C3H8 in `nasa_gas.yaml` and ATcT 1.112?
- Q-5: verify the † literature values (spec §5) against the printed sources. A mismatch amends the spec, never the
  test.

**Not done:** `docs/progress.md` was not edited (the build lane owns it on merge). No evidence manifest exists yet,
because nothing is implemented.
