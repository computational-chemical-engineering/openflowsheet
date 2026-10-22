# C2 split registration, Amendment 1 — a re-taken pinned input (design lane, `specifier`, small pass)

Branch `wp/C7` (worktree `/home/user/ofs-c7`). C7 (R-460 after 0.2.0) re-took W27's coverage at `0.3.0.dev0`
(`f85fcd7`; `docs/C7_DECISIONS.md:25-30`: required by `test_committed_coverage_json_is_g14_and_this_builds_classification`;
only `package_version`, the snapshot commit and the snapshot hash moved; G14 passes). Now
`benchmarks/m06/openidaes450/coverage.json` has SHA-256 `aa89cdd6…` against SPLIT-R01's pin `b69626c7…`
(`docs/derivations/C2-OpenIDAES-450-split-registration.md:27-37`), and the split generator refuses (SPLIT-R12, :164-),
failing `tests/test_c2_openidaes450_split.py` A01, A07, A17 in the full gate.

## The question
Amend the split registration under SPLIT-R12 so a version-driven re-take of a pinned input does not break the split
and can never move a case. Candidates: (a) the generator reads each input at its pinned content from git history
(the blob of the commit where it had the pinned SHA-256; CI checks out with full history) when the working copy has
moved on, and separately asserts that the working copy's read fields (`case_id`, `family`, `class`) equal the pinned
ones (reporting drift as a SPLIT-R12 amendment trigger); (b) re-pin with an amendment recording that the read
fields are unchanged (the split JSON's recorded `coverage_snapshot` would then change); (c) other. Choose with
reasons; future re-takes happen at every version bump.

## Exit test
A dated "Amendment 1" in the registration; register entry **R-555**; the generator (`docs/derivations/scripts/
c2_openidaes450_split.py`) changed accordingly with `--check` passing; `tests/test_c2_openidaes450_split.py` passes
(add a test for the new behaviour, including a negative control where a read field drifts); ruff clean. Commit
(`C2 (amendment 1):` prefix, the two trailer lines). The split's case assignment must be byte-identical. Report ≤ 100 words.

## Out of scope
Re-drawing; any held-out data use; C7's version work.
