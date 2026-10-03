# Where the history is

**The public repository.** `computational-chemical-engineering/openflowsheet` is the working
repository from v0.1.0 on (R-150). Its root commit `5a350199f1334e52cfd789109a0e1dc944ef328c`
("OpenFlowsheet v0.1.0 — initial public release", tag `v0.1.0`) carries the v0.1.0 tree without
the history that produced it: its tree is exactly that of the archive's v0.1.0 commit
`a3bc53480b1ea108038e693a347c267a2f945165`.

**The archive.** The development history up to v0.1.0 — the work packages P00–T08, their reviews
and their evidence runs — is kept, read-only, in the private repository
`computational-chemical-engineering/openflowsheet-dev`. Every commit id cited in a document or a
manifest written before v0.1.0 refers to that archive: the `commit` of each
`evidence/<package>/<commit>/manifest.json` (P00–T08), the release candidate `C` =
`67c66d98587f23bd7dfe8da28a8facccc92da21e` of v0.1 (`docs/t08-rc-record.md`, ADR 0021), the run
commits in `benchmarks/`, and the commits named in `docs/`. The ids are kept as written; they are
not rewritten to public commits, which do not exist for them.

**What works without the archive.** Everything the package and its tests need is in this
repository. Tests that read an archived commit skip, with the reason "pre-0.1.0 development
history is archived in openflowsheet-dev (R-150)", and run unchanged in a clone that has the
archive (`tests/conftest.py`, `require_archived_history`). The release gate identifies `C` by its
recorded file hashes, `release/rc-trees/<C>.json`, where `C` itself is absent (R-151).

**Reading the archive.** With access to `openflowsheet-dev`, fetch it into a clone of this
repository (`git fetch <archive url> main`) and the cited commits resolve. Install the pre-push
guard first (`scripts/install-hooks.sh`, `docs/RELEASING.md`): a clone that holds both histories
must never push the archived one to the public repository.
