# C12 — build decisions (rights check and attribution for pr-lib-v1)

Append-only. One line per choice: `DECISION: <question> → <choice>. Alternative: <x>. Reversible by: <how>.`

DECISION: Where the attribution text lives → `docs/attributions/pr-lib-v1.md` (records not released; NOTICE stays about what ships now). Alternative: a NOTICE section. Reversible by: moving the file's sections into NOTICE when the records ship (A32-Q2 asks whether a packaged copy is required).
DECISION: Public terms pages unreachable (proxy 403 `connect_rejected`, WebFetch ENOTFOUND, 2026-10-22 19:34-19:36 UTC) → every source whose terms rest on such a page is `unresolved`; no recollection of a page's content is used as its terms. Alternative: quote terms from memory. Reversible by: a workstation fetch quoting each page, then re-marking the row.
DECISION: Sources the records do not name but whose data passed through the retrieval (REFPROP route, PubChem, CIAAW) → separate rows RC-02, RC-07, RC-08. Alternative: fold them into the `chemicals` row. Reversible by: merging the rows.
DECISION: Cross-check-only sources (CoolProp, thermo, JANAF, literature table) → rows RC-09..RC-12 scoped to the cross-check and projection files, not the records. Alternative: omit them. Reversible by: deleting the rows.
DECISION: Test name and location → `tests/test_l01_attribution.py` (inside the `test_l01_*` battery). Alternative: `tests/test_c12_*.py`. Reversible by: renaming.
DECISION: Record findings F-1 (H2/N2/Ar `rights.source` names ATcT where the value is zero by definition) and F-3 ("Setzmann and Wagner et al.") → stated, records not edited (any edit changes both vetted files and the cross-check hash). Alternative: correct the text now. Reversible by: a design-lane ruling (A32-Q6).
