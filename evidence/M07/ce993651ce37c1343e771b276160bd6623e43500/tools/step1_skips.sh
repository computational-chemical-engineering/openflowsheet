#!/usr/bin/env bash
# M07 WO-8b (R-376, alpha spec §19.6 A7): each CI architecture's step-1 SKIPPED summary lines, from the
# dispatch run's `check` job logs (fetched by fetch_ci.sh), job/step/timestamp prefix stripped.
set -eu
J=$1; O=$2
for pair in "ubuntu-latest:ci-x86-64" "ubuntu-24.04-arm:ci-aarch64"; do
    runner=${pair%%:*}; out=${pair#*:}
    cut -f3- "$J/check-$runner.log" | sed -E 's/^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9:.]+Z //' | grep -E '^SKIPPED \[' > "$O/$out.txt"
done
