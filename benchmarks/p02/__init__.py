"""P02 composition test: judge-side closed forms, reference loading and the SuperLU evidence.

Nothing in this package imports a backend or `openflowsheet`. The harnesses that exercise
CasADi and Pyomo/PyNumero live under `spikes/p02/` and implement their own block formulas; the
values here are the independent expectation they are judged against
(`docs/derivations/P02-composition-spec.md` §6).
"""
