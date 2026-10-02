"""Jobs: the lifecycle model and checker, the operation bodies and the executors (T07 §6, §8, §9).

`model` holds the closed producer vocabularies of `schemas/job.schema.json` and
`schemas/job-event.schema.json` and the lifecycle checker every job-producing test runs (gate G3).
`interrupt` holds the cooperative interruption (§8.1), `runner` the `solve` and `reproduce`
bodies, and `executor` the inline executor behind the process-wide compute lock (§9.1).
"""
