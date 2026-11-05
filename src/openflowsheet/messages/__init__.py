"""Messages a student understands (MSG design note `docs/design/MSG-messages.md`, ADR 0058).

One explanation model over a catalogue of typed codes: every failure, refusal, warning or notice
renders in the same layered form — what and where, why (with the numbers), what to do, the kind,
the code, then the machine details. Text is rendered on read from the catalogue and stored nowhere
(I2); machine messages never change (I1).

Modules: `diagnostic` (the sidecar; standard library only, the one module the solver path
imports), `catalogue` (load, validate, merge, `register`), `template` (the §4.2.4 grammar),
`legacy` (the §4.3 parser), `render` (§4.4), `text` (§4.5's text format), `lint` (MSG-G4) and
`audit` (MSG-G3). This package imports nothing from `application`, `models`, `orchestrator` or
`verify`, and this module imports nothing, so importing `messages.diagnostic` stays cheap.
"""
