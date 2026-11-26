#!/usr/bin/env bash
# LINE06 blind runner: run.sh <name> <command...>
# Runs the command detached in the current directory, full log to ~/.cache/line06/<name>.log, PID to <name>.pid.
# Blocks until it ends and prints ONE summary line (start it with run_in_background; stop it by `kill $(cat <pid>)`).
# The summary is the log's last line that starts with PASS, FAIL, GATE or SUMMARY, or else the exit code alone.
set -u
name=$1; shift
dir=$HOME/.cache/line06; mkdir -p "$dir"
log=$dir/$name.log; pidf=$dir/$name.pid
setsid bash -c '"$@"' _ "$@" >"$log" 2>&1 < /dev/null &
pid=$!; echo "$pid" >"$pidf"
wait "$pid"; rc=$?
line=$(grep -E '^(PASS|FAIL|GATE|SUMMARY)' "$log" | tail -1)
[ -z "$line" ] && line=$(tail -1 "$log" | cut -c1-200)
echo "$name rc=$rc | $line | log $log"
exit "$rc"
