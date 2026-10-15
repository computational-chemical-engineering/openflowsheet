#!/usr/bin/env bash
# V02 alpha Am2 action 5: commit-ready copies of C_α¹'s cited RC records (spec §8.3) and of step 12's
# five kept certificates (R-348 item 2: rc/step12/certificates/<kept bundle path>/solution-certificate.json;
# the bundle's own `artifacts/` segment is left out, because `evidence/**/artifacts/` is git-ignored, B-AM2-9).
set -eu
W=$(cd "$(dirname "$0")/.." && pwd)
RC=/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/rc-6fec822
GATE=/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/alpha-gate
C=$(git -C "$RC" rev-parse HEAD)
A=$RC/evidence/M07a/$C/artifacts/rc
cd "$A/step12"
rm -rf certificates
find g12-bundles g12-edges-bundles -name solution-certificate.json | LC_ALL=C sort | while read -r kept; do
    bundle=$(dirname "$(dirname "$kept")")   # <kept dir>/<bundle>/artifacts/solution-certificate.json
    mkdir -p "certificates/$bundle"; cp -p "$kept" "certificates/$bundle/solution-certificate.json"
done
cp "$GATE/evidence/M07a/e0e198e4632224612671db5b07445639d272d6da/tools/cited.txt" "$W/tools/cited.txt"
(cd "$A" && find step12/certificates -name solution-certificate.json | LC_ALL=C sort) >> "$W/tools/cited.txt"
"$W/rcvenv/bin/python" "$W/tools/collect_records.py" "$A" "$GATE/evidence/M07a/$C/rc" "$W/tools/cited.txt"
