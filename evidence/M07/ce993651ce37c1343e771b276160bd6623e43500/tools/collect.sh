#!/usr/bin/env bash
# M07 WO-8c action 8 (from the alpha's Am3 collect.sh): commit-ready copies of C''s cited RC records
# (alpha spec §8.3) into the m07 worktree's evidence/M07/<C'>/rc/: step 17's records from $S into
# artifacts/rc/step17/, step 12's five kept certificates (R-348 item 2: rc/step12/certificates/<kept
# bundle path>/solution-certificate.json; the bundle's `artifacts/` segment left out, B-AM2-9), then
# collect_records.py over tools/cited.txt.
set -eu
W=$(cd "$(dirname "$0")/.." && pwd)
RC=/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/rc-ce99365
DEST=/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/m07
C=$(git -C "$RC" rev-parse HEAD)
A=$RC/evidence/M07/$C/artifacts/rc
mkdir -p "$A/step17"
cp -p "$W"/s17/{rc-step17.json,at-cw.json,at-c.json,coverage-at-C.json} "$A/step17/"
for l in step17a-tree step17b-coverage step17c-write step17c-carry step17d-precheck step17d-aggregate step17d-diff step17d-sha256; do
    cp -p "$W/logs/$l.log" "$A/step17/$l.log"
done
cd "$A/step12"
rm -rf certificates
find g12-bundles g12-edges-bundles -name solution-certificate.json | LC_ALL=C sort | while read -r kept; do
    bundle=$(dirname "$(dirname "$kept")")
    mkdir -p "certificates/$bundle"; cp -p "$kept" "certificates/$bundle/solution-certificate.json"
done
cp "$W/tools/cited.base.txt" "$W/tools/cited.txt"
(cd "$A" && find step12/certificates -name solution-certificate.json | LC_ALL=C sort) >> "$W/tools/cited.txt"
"$W/rcvenv/bin/python" "$W/tools/collect_records.py" "$A" "$DEST/evidence/M07/$C/rc" "$W/tools/cited.txt"
