#!/usr/bin/env bash
# Download the dispatch run's artifacts and the RC jobs' logs into C_α²'s artifacts/rc/ci/.
set -u
RUN=$1; CI=$2
mkdir -p "$CI/job-logs"
gh run download "$RUN" --dir "$CI" > "$CI/../download.log" 2>&1 || echo "download failed"
gh run view "$RUN" --json jobs --jq '.jobs[] | select(.conclusion != "skipped") | "\(.databaseId)\t\(.name)"' |
while IFS=$'\t' read -r id name; do
    f=$(echo "$name" | sed -E 's/ \((.*)\)/-\1/; s/^rc-ensemble$/rc-ensemble/')
    gh run view "$RUN" --job "$id" --log > "$CI/job-logs/$f.log" 2>/dev/null || echo "log failed $name"
done
ls "$CI" | tr '\n' ' '; echo; ls "$CI/job-logs" | tr '\n' ' '; echo
