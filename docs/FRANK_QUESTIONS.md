# Questions only Frank can answer

Append-only. Each question has a default; work proceeds on the default until Frank answers.

## S01 (2026-10-21)

- **Q-S01-1.** In S01, a cascade where some stages carry no flow while others do (for example, a single liquid side feed at
  the bottom stage with nothing entering from above) is not claimed to converge. S01 promises only that the solver reports a
  typed failure or a checked root, never a false success (`docs/derivations/S01-spec.md` §4.7, A19). Is that acceptable for
  S01, with the capability left to a later package if a column case needs it? **Default: yes.**
