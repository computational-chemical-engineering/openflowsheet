# X05 build decisions (replay from the wheel; ADR 0069, Proposed)

Build lane, `wp/X05`. Each choice the ADR left open, the alternative, and the commit that carries it. Ruling
round: folded into X05's single `reviewer` pass.

## Q-N1 — do the other environments that run `openflowsheet` verify? (measured 2026-11-07, before WO-1)

| Environment | How measured | `lock_sha256` / findings |
| --- | --- | --- |
| `.venv` (project, `ref-x86-64`, Python 3.13.5) | live, `PYTHONPATH=src`, `environment()` at the WO-1 code | `ead4edf1…`, `()` — verifies |
| `.venv-nlp` (m03 audited, `scripts/build-m03-ipopt-env.sh`) | static: not present in the main checkout (built per RC elsewhere). `benchmarks/m03/nlp-conda-explicit.txt` carries no closure member (only `python`); `benchmarks/m03/nlp-pip.lock` pins all nine at the lock's versions (`attrs 26.1.0`, `casadi 3.8.0`, `jsonschema 4.26.0`, `jsonschema_specifications 2025.9.1`, `numpy 2.2.4`, `PyYAML 6.0.2`, `referencing 0.37.0`, `rpds_py 2026.6.3`, `scipy 1.15.3`) | expected to verify; live measurement left to the next RC that builds it |
| `.venv-lca` (`scripts/build-lca-env.sh`) | static: not present. Built from `requirements.lock --no-deps`, then `lca-pip.lock`, which pins no closure member | expected to verify; live measurement left to the next build |
| reactor child (`adapters/pymrm/reactor-env.lock`) | static: `child.py` never imports `run.manifest`, so it never calls `environment()`; the parent process (project environment) writes the manifest. Its lock pins `numpy 2.5.3`, `scipy 1.18.1`, `pyyaml 6.0.3`, `rpds-py 2026.9.1` and no `casadi`, so it would record `""` if it ever did | not applicable (no `environment()` call) |

Default kept (ADR §11 Q-N1): the rule does not bend; nothing here needs it to.

## Decisions

- **D-1 (a58ef5a5) — M01.A35's exact dependency list follows the Q-F1 pins.** `tests/test_m01_provider.py`
  asserted `[project].dependencies` equal to the five pre-X05 pins ("M01 adds no runtime dependency"). The four
  pins of ADR 0069 D3.2 break it. Choice: the list stays exact and gains the four, with a docstring naming X05; it
  lives in the pin commit, so reverting Q-F1 reverts it too. Alternative: a subset check (rejected: loosens A35).
- **D-2 (WO-1) — `installed_version` memoises the raised exception, not only its class.** ADR D2 says "the raised
  class" is memoised. Re-raising the stored instance keeps that class exactly; re-constructing `cls(message)` would
  turn an exception whose constructor takes other arguments (e.g. `UnicodeDecodeError`) into a `TypeError` and
  misname F6. Observable behaviour (the class F6 names, one read per name) is the ADR's.
- **D-3 (WO-1) — `tests/test_t08_r3_a19_lock_lookup.py` is removed in the WO-1 commit.** WO-1 deletes
  `_checkout_lock`/`_repository_lock`, which that file's unit tests import; WO-2's
  `tests/test_x05_replay_from_the_wheel.py` is its end-to-end replacement (ADR D7.2, §7 WO-2).
- **D-4 (WO-1) — X05.A12's "schema unchanged on `wp/X05`" is evidenced by `git diff`, not a test.** CI checks out
  shallow, so a test diffing against the merge base would skip or fail there; the manifest records
  `git diff --quiet <merge-base> HEAD -- schemas/run-manifest.schema.json`. The test holds the document's keys equal
  to the schema's eight.
- **D-5 (WO-2) — `lock-check`'s interface.** `--state` takes ADR §6.2's four states and `installed-nolock`;
  `--bundle-on`/`--bundle-off` are optional and each one given is replayed against its registered cell (the record
  lists `replayed`), so the A25 environment runs `--state installed` with no bundle. `installed-nolock` copies the
  installed package below `--nolock-root` (beneath the stray) and deletes the copy's lock — never the clean
  environment's. Strays are looked for only in the installed states: in a checkout the root's lock *is* the packaged
  one. Expectations are read from `benchmarks/x05/reference_values.json` at run time, as the step already reads the
  checkout's lock and certificate as data.
- **D-6 (WO-2) — A22 is a new `t08_rc.py f0-replay` subcommand** running `corpus_identity.m7()` with the
  checkout's `sys.path` entries dropped (asserting `openflowsheet.__file__` outside the tree), judged against
  `benchmarks/f0/corpus.json` M7: the registered value on `ref-x86-64`, else `MATCH` + integrity +
  `exact_replay`/`compatible_reproduction`. CI's `clean-install` timeout 30 → 45 min for the 52 re-solves.
