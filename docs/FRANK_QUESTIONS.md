# Questions for Frank

Questions only Frank can answer (scope, value judgments). Each carries the default that unattended work proceeds on.

## C2 — OpenIDAES-450 development / held-out split (2026-10-21)

- **C2-Q1. What should a release gate score on the held-out half?**
  The split says the held-out half is scored only at release gates. It does not say *what* is scored.
  - **Default:** the coverage classification of every held-out case (free), shown next to the development half with
    the gap.
  - An agent campaign on held-out cases (spend) happens only when a release registration asks for one. It draws its
    own seeded sample from the held-out half.
  - Reference: `docs/derivations/C2-OpenIDAES-450-split-registration.md` §11 Q-1.

- **C2-Q2. Should 17 more cases count as development?**
  Your rule made W27's 45 cases (and its 3 canaries) development. Another 17 cases are named in committed specs,
  tests and reviews: registered test states, stubs, the W27 verdict. Their content has been read and discussed.
  - **Default:** yes, they are development. That gives 65 exposed cases, 225 development and 224 held-out.
  - Saying no means a new (v2) draw before any held-out score is reported.
  - Reference: registration SPLIT-R04, R-488.
