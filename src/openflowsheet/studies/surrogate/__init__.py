"""The C1 reactor surrogate and its Default split-conformal evidence (package M04).

Specification `docs/derivations/M04-spec.md`; ADRs 0036 (statistical semantics) and 0037 (the
surrogate in a flowsheet); register R-240…R-249. Three pure modules, none of which runs the parent:

* `plan` — the registered reference distribution's box, the SplitMix64 sampler, the iteration-1
  plan and its prefix, the experiment requests, and the plan guard (spec §3.1, §4, §5);
* `conformal` — the joint score, the integer finite-sample index, the order-statistic band with
  failed draws at +∞, the integer coverage test, the Clopper–Pearson bound, and the verdict
  function (spec §6, §7);
* `quadratic` — the scaled input, the full-quadratic basis, the QR fit and its identifiability
  test, prediction, ∇_z, the chain rule to the inlet, admissibility and the reference-domain status
  (spec §3).

and two that run and record a study (spec §5.4, §10):

* `study` — the plan and budget refused before anything runs, the plan's experiments one by one
  through M02's `ExperimentRunner` (cache first), and the evidence and verdict of the run plan;
* `manifest` — the SurrogateManifest, the ModelEvidence and the manifest checker (M04.A24).

Nothing here keeps global state: the sampler is a pure function of its seed (G20). Nothing here
imports `application`, which runs a study as the `surrogate_study` job operation.
"""
