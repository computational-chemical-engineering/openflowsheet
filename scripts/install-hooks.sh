#!/usr/bin/env bash
# Install this clone's git hooks (docs/RELEASING.md, "The pre-push guard"): `pre-push` becomes a
# copy of scripts/pre_push_guard.py, which refuses to push to the public repository
# computational-chemical-engineering/openflowsheet any commit that does not descend from v0.1.0
# (R-150). The hooks directory is the clone's (`git rev-parse --git-path hooks`), shared by all of
# its worktrees. A different existing pre-push hook is left alone unless --force is given.
#
#     scripts/install-hooks.sh [--force]
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source="$here/pre_push_guard.py"
hooks="$(git -C "$here" rev-parse --path-format=absolute --git-path hooks)"
target="$hooks/pre-push"

force=0
case "${1:-}" in
    "") ;;
    --force) force=1 ;;
    *) echo "usage: $0 [--force]" >&2; exit 2 ;;
esac

mkdir -p "$hooks"
if [ -e "$target" ] && ! cmp -s "$source" "$target" && [ "$force" -ne 1 ]; then
    echo "refused: $target exists and differs from $source; rerun with --force to replace it" >&2
    exit 1
fi
install -m 755 "$source" "$target"
echo "installed $target"
