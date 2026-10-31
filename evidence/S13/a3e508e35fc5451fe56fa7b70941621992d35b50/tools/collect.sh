#!/usr/bin/env bash
# V03 WO-6 (from 0.2.0's collect.sh): step 12's five kept certificates into artifacts/rc/step12/certificates/<kept
# bundle path>/solution-certificate.json (the bundle's `artifacts/` segment left out, R-348), then collect_records.py
# over tools/cited.txt into the branch worktree's evidence/S13/<C>/rc/.
set -eu
W=$(cd "$(dirname "$0")/.." && pwd)
RC=/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/rc-v03-a3e508e
DEST=/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/v03rc
C=$(git -C "$RC" rev-parse HEAD)
A=$RC/evidence/S13/$C/artifacts/rc
cd "$A/step12"
rm -rf certificates
find g12-bundles g12-edges-bundles -name solution-certificate.json | LC_ALL=C sort | while read -r kept; do
    bundle=$(dirname "$(dirname "$kept")")
    mkdir -p "certificates/$bundle"; cp -p "$kept" "certificates/$bundle/solution-certificate.json"
done
"$W/rcvenv/bin/python" "$W/tools/collect_records.py" "$A" "$DEST/evidence/S13/$C/rc" "$W/tools/cited.txt" "$C" docs/v03-rc-record.md
