"""Adapters to external models, and the records of their evaluations (blueprint §15),
introduced by package M02 (design note `docs/design/M02-pymrm-adapter.md`, ADR 0033).

Variants, the frozen identities of external model configurations (`variants`); the launcher and
kill chain of the isolation profile `external-subprocess-v1` (`external`); experiment requests,
records, the exact cache and the runner (`experiments`); and the pinned reactor's child and
environment builder (`pymrm`), which no module of this package imports.
"""
