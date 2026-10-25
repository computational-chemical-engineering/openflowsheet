# S09 build decisions

Build-lane choices made while executing `docs/derivations/S09-spec.md` §12. Each is an isolated, revertible commit.
Scientific questions are not decided here.

## WO-S09-1 (environment)

- MEASURED: the spec's lock command resolves `biosteam==2.54.0` to 63 distributions; every version of §2.1 matches
  (thermosteam 0.54.2, thermo 0.6.1, chemicals 1.5.2, flexsolve 0.5.10, numba 0.68.0, numpy 2.5.4, scipy 1.18.1,
  CoolProp 8.0.0). The `aarch64-manylinux_2_28` resolution gives the same 63 pins.
- MEASURED: five distributions are sdists (biosteam, thermosteam, flexsolve, colorpalette, numpoly), not two as the spec
  says. Four are pure Python. **numpoly 1.3.9 has no wheel and compiles Cython/C code** (build-system requires
  setuptools, wheel, Cython, numpy); the spec calls them pure-Python wheels. With the default isolated build the install
  works, but its build tools are not hash-checked.
- DECISION: take the spec's fallback route, extended to numpoly's needs → pin `setuptools`, `wheel`, `cython` in the lock
  (added unpinned to the `.in`, so they resolve to the latest: setuptools 84.2.1, wheel 0.48.0, cython 3.3.0), hash-install
  those and numpy first, then the whole lock with `--no-build-isolation`. Alternative: leave isolated builds (unhashed
  build tools). Reversible by: dropping the three lines from the `.in`, recompiling the lock, and the two-phase install in
  `build_biosteam`.
- DECISION: the pip-freeze fingerprint now includes cython and wheel (they are in the environment). It does not cover the
  compiled bytes of numpoly's extension, which depend on the host gcc. Alternative: add a hash of numpoly's `.so` files
  to the fingerprint. Reversible by: editing `fingerprint()`. Open for the design lane: whether the spec wants that.
- DECISION: `--no-cache-dir` on both installs, so nothing comes from a local pip cache. Alternative: the pip cache as
  for IDAES. Reversible by: removing the flag.
- DECISION: the build-tool subset is cut from the lock at build time by awk, not kept as a second file. Alternative: a
  committed `biosteam-build-tools.lock`. Reversible by: swapping the awk step for `-r` that file.
- DECISION: `uv` 0.12.12 was already installed (`~/.local/bin/uv`); nothing installed.
- DECISION: `.venv-biosteam` is covered by the existing `.venv-*/` pattern of `.gitignore` (`git check-ignore` confirms).
- MEASURED: two consecutive builds, 38 s and 36 s, give the same pip-freeze SHA-256
  `0edea300bbf188030642265ca811425c270d5508bf119fa86431572c06c69a95`; `pip check` passes; the environment imports
  biosteam 2.54.0 (no column was run). Size 874 MB.
- DECISION: A04's file part is `tests/test_s09_environment.py`: lock pins every distribution by hash and holds §2.1's
  versions, `.in` matches the lock header, §9 carries one fingerprint twice and the licence and aarch64 statements, the
  script builds with `--require-hashes`. The record-fingerprint half of A04 waits for WO-S09-2's records. Alternative:
  rebuilding in the test (rejected: the gate never builds external tools). Reversible by: deleting the file.
