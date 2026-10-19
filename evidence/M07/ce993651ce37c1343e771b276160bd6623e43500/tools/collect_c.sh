#!/usr/bin/env bash
# M07 WO-8c action 8, RC.3 (M07 spec §24.6; alpha §18.4 item 4): C = c899c85's small-text records kept
# under the m07 worktree's evidence/M07/<C>/rc/ (J59-J65), by C''s cited list where the file exists at C
# (C has no G11 records: J59), plus step 17's records from C's $S, step 12's kept certificates, and the
# push run 39224203477's `check (ubuntu-latest)` job log (step 16's CI half at C, J58).
set -eu
W=$(cd "$(dirname "$0")/.." && pwd)
WC=/home/frankp/.cache/of-rc-c899c85
RC=/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/rc-c899c85
DEST=/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/m07
C=$(git -C "$RC" rev-parse HEAD)
A=$RC/evidence/M07/$C/artifacts/rc
mkdir -p "$A/step17" "$A/ci-push/job-logs"
cp -p "$WC"/s17/{rc-step17.json,at-cw.json,at-c.json,coverage-at-C.json} "$A/step17/"
for l in step17a-tree step17b-coverage step17c-write step17c-carry step17d-precheck step17d-aggregate step17d-diff step17d-sha256; do
    cp -p "$WC/logs/$l.log" "$A/step17/$l.log"
done
[ -s "$A/ci-push/job-logs/check-ubuntu-latest.log" ] || {
    id=$(gh run view 39224203477 --json jobs --jq '.jobs[] | select(.name == "check (ubuntu-latest)") | .databaseId')
    gh run view 39224203477 --job "$id" --log > "$A/ci-push/job-logs/check-ubuntu-latest.log"
}
cd "$A/step12"
rm -rf certificates
find g12-bundles g12-edges-bundles -name solution-certificate.json | LC_ALL=C sort | while read -r kept; do
    bundle=$(dirname "$(dirname "$kept")")
    mkdir -p "certificates/$bundle"; cp -p "$kept" "certificates/$bundle/solution-certificate.json"
done
cd "$A"
{ while read -r p; do [ -f "$p" ] && echo "$p"; done < "$W/tools/cited.base.txt"
  echo ci-push/job-logs/check-ubuntu-latest.log
  find step12/certificates -name solution-certificate.json | LC_ALL=C sort; } > "$W/tools/cited-c899c85.txt"
"$W/rcvenv/bin/python" "$W/tools/collect_records.py" "$A" "$DEST/evidence/M07/$C/rc" "$W/tools/cited-c899c85.txt" \
    "$C" "docs/design/M07-build-decisions.md J56-J66 (no RC record for C, M07 spec §24.6 RC.3)"
# records.json then hand-edited (J74): rc_record null, description naming C as superseded and its account in J56-J66.
