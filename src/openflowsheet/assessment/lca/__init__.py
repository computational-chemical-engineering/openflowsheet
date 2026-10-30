"""Life-cycle assessment of a solved flowsheet as a frozen linear map (E01 design §4.8; ADR 0052 D7,
D8; register R-850…R-867).

`h_m(x) = A_fac(x) · (Σ_k q_{m,k} a_k(x) + Σ_e c_{m,e} b_e(x))`: `tables` loads and checks the
frozen unit-score and direct-factor tables and enforces their rights; `inventory` builds the
boundary exchanges `a_k`, `b_e` and the allocation factor; `impact` the category rates; `section`
the report section. `brightway` is the optional offline adapter (extra `lca`) that computes a
unit-score table from a user's Brightway project; nothing else here imports Brightway.
"""
