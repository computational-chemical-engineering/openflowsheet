#!/usr/bin/env bash
# Build the two T06 reference environments (IDAES, DWSIM), outside requirements.lock.
#
# Neither tool is a dependency of this project. Each gets its own git-ignored environment, exactly
# like the P02 backend spikes (scripts/build-backend-envs.sh):
#
#   .venv-idaes/              idaes-pse 2.13.0 and its closure (hash-locked), plus the IDAES
#     idaes-data/bin/         binary extensions 3.4.2 (Ipopt & co.) fetched by `idaes get-extensions`
#   .venv-dwsim/              pythonnet 3.1.0 (hash-locked) to drive DWSIM from CPython
#     dotnet/                 the .NET 8.0.31 runtime (Microsoft tarball, SHA-512 checked)
#     dwsim/                  DWSIM 9.0.5 unpacked from its Linux .deb (SHA-256 checked); not installed
#   .reference-downloads/     download cache for the two large artifacts, re-verified on every run
#
# pip is the one bundled with the host Python's venv (no pip upgrade is downloaded). Nothing is
# installed system-wide and nothing is edited inside either tool. Every downloaded
# artifact is pinned by URL and hash below; a mismatch stops that tool's build. Each environment is
# rebuilt from scratch on every run, and the script ends with a fingerprint (package list and
# content hashes) that must be identical between two runs. What this produces, the licences, and
# what failed are recorded in docs/reference-environments.md.
#
# Usage: scripts/build-reference-envs.sh [idaes|dwsim|all] [log-file]
set -uo pipefail

cd "$(dirname "$0")/.."
WHICH="${1:-all}"
CACHE=".reference-downloads"
mkdir -p "$CACHE"
LOG="${2:-$CACHE/reference-env-build.log}"
: > "$LOG"
PYTHON="${PYTHON:-python3}"

# ---- pinned artifacts ------------------------------------------------------------------------
IDAES_LOCK="spikes/references/idaes-requirements.lock"
IDAES_EXT_RELEASE="3.4.2"
# IDAES publishes no Debian 13 build; its own alias table maps ubuntu2404 and el9 onto the
# ubuntu2204 build, which is the one used here (glibc 2.35 build on a glibc 2.41 host).
IDAES_EXT_DISTRO="ubuntu2204"
IDAES_EXT_SHA256_LIB="341470b4b0b9d67758cfde6f3246ed3a3d08000e2306908186435262d5751184"
IDAES_EXT_SHA256_SOLVERS="f370fa258cc457cd84fd9fe4298bde55dfc03374b607e68aa4d38f24ad9730e5"

DWSIM_LOCK="spikes/references/dwsim-requirements.lock"
DWSIM_DEB="dwsim_9.0.5-amd64.deb"
DWSIM_URL="https://github.com/DanWBR/dwsim/releases/download/v9.0.5/${DWSIM_DEB}"
DWSIM_SHA256="52c041b1d659ea26e22750e8b7045c7bc68d3d95f6384abe28d07d967eafa20c"
DOTNET_TGZ="dotnet-runtime-8.0.31-linux-x64.tar.gz"
DOTNET_URL="https://builds.dotnet.microsoft.com/dotnet/Runtime/8.0.31/${DOTNET_TGZ}"
DOTNET_SHA512="f336bdec58d54bf50d74a1b38efa82f7290d976bd2ed98b845ebcbac42cf0d8cef504684fc088d4b05f98737b996bf3302e52bd9c23005deae7c60780b2652fb"

# ---- helpers ---------------------------------------------------------------------------------
note() { echo "=== $* ===" | tee -a "$LOG"; }
say() { echo "$*" | tee -a "$LOG"; }

# run <description> <command...>: log the command and its output, return its status.
run() {
    local what="$1"
    shift
    echo "--- $what: $*" >>"$LOG"
    "$@" >>"$LOG" 2>&1
    local rc=$?
    [ $rc -ne 0 ] && say "FAILED ($rc): $what"
    return $rc
}

# fetch <url> <file> <sha256|sha512> <hash>: download into the cache unless a verified copy is
# already there; verify the hash either way.
fetch() {
    local url="$1" file="$CACHE/$2" algo="$3" want="$4" got
    if [ -f "$file" ]; then
        got="$(${algo}sum "$file" | cut -d' ' -f1)"
        if [ "$got" = "$want" ]; then
            say "cached, $algo verified: $2"
            return 0
        fi
        say "cached copy of $2 has the wrong $algo; downloading again"
        rm -f "$file"
    fi
    run "download $2" curl --fail --location --silent --show-error -o "$file.part" "$url" || return 1
    got="$(${algo}sum "$file.part" | cut -d' ' -f1)"
    if [ "$got" != "$want" ]; then
        say "HASH MISMATCH for $2: want $want, got $got"
        rm -f "$file.part"
        return 1
    fi
    mv "$file.part" "$file"
    say "downloaded, $algo verified: $2"
}

# tree_hash <dir>: one SHA-256 over the sorted per-file SHA-256 list (content only).
tree_hash() {
    (cd "$1" && find . -type f -print0 | LC_ALL=C sort -z | xargs -0 sha256sum | sha256sum \
        | cut -d' ' -f1)
}

STATUS_IDAES="not built"
STATUS_DWSIM="not built"

# ---- IDAES -----------------------------------------------------------------------------------
build_idaes() {
    local t0=$SECONDS
    note "IDAES: .venv-idaes"
    rm -rf .venv-idaes
    run "venv" "$PYTHON" -m venv .venv-idaes || return 1
    run "pip install (hash-locked)" .venv-idaes/bin/pip install --require-hashes --no-deps \
        -r "$IDAES_LOCK" || return 1
    run "pip check" .venv-idaes/bin/pip check || return 1

    note "IDAES: binary extensions $IDAES_EXT_RELEASE ($IDAES_EXT_DISTRO)"
    export IDAES_DATA="$PWD/.venv-idaes/idaes-data"
    run "idaes get-extensions" .venv-idaes/bin/idaes get-extensions \
        --release "$IDAES_EXT_RELEASE" --distro "$IDAES_EXT_DISTRO" --verbose || return 1
    local bin="$IDAES_DATA/bin" got
    got="$(sha256sum "$bin/idaes-lib-${IDAES_EXT_DISTRO}-x86_64.tar.gz" | cut -d' ' -f1)"
    [ "$got" = "$IDAES_EXT_SHA256_LIB" ] || { say "HASH MISMATCH idaes-lib: $got"; return 1; }
    got="$(sha256sum "$bin/idaes-solvers-${IDAES_EXT_DISTRO}-x86_64.tar.gz" | cut -d' ' -f1)"
    [ "$got" = "$IDAES_EXT_SHA256_SOLVERS" ] || { say "HASH MISMATCH idaes-solvers: $got"; return 1; }
    say "extension tarballs sha256 verified"
    "$bin/ipopt" --version 2>&1 | head -1 | tee -a "$LOG"
    .venv-idaes/bin/idaes --version | tee -a "$LOG"
    unset IDAES_DATA
    say "IDAES build took $((SECONDS - t0)) s"
}

# ---- DWSIM -----------------------------------------------------------------------------------
build_dwsim() {
    local t0=$SECONDS
    note "DWSIM: downloads"
    fetch "$DWSIM_URL" "$DWSIM_DEB" sha256 "$DWSIM_SHA256" || return 1
    fetch "$DOTNET_URL" "$DOTNET_TGZ" sha512 "$DOTNET_SHA512" || return 1

    note "DWSIM: .venv-dwsim"
    rm -rf .venv-dwsim
    run "venv" "$PYTHON" -m venv .venv-dwsim || return 1
    run "pip install (hash-locked)" .venv-dwsim/bin/pip install --require-hashes --no-deps \
        -r "$DWSIM_LOCK" || return 1
    run "pip check" .venv-dwsim/bin/pip check || return 1

    note "DWSIM: .NET runtime and DWSIM payload"
    mkdir -p .venv-dwsim/dotnet
    run "unpack .NET runtime" tar -xzf "$CACHE/$DOTNET_TGZ" -C .venv-dwsim/dotnet || return 1
    # The .deb is unpacked, not installed: its payload is usr/local/lib/dwsim (the program) plus a
    # launcher and desktop entries that are not needed here. Its postinst (chmod 0777 on the
    # install tree, pdb2mdb) is not run.
    local stage
    stage="$(mktemp -d "$CACHE/deb.XXXXXX")"
    run "unpack DWSIM .deb" dpkg-deb -x "$CACHE/$DWSIM_DEB" "$stage" || { rm -rf "$stage"; return 1; }
    mv "$stage/usr/local/lib/dwsim" .venv-dwsim/dwsim
    rm -rf "$stage"
    .venv-dwsim/dotnet/dotnet --list-runtimes | tee -a "$LOG"
    say "DWSIM build took $((SECONDS - t0)) s"
}

# ---- fingerprint -----------------------------------------------------------------------------
fingerprint() {
    note "fingerprint (must be identical between runs)"
    {
        echo "host: $(uname -srm); $("$PYTHON" --version 2>&1)"
        if [ -d .venv-idaes ]; then
            echo "[.venv-idaes] pip freeze sha256: $(.venv-idaes/bin/pip freeze | LC_ALL=C sort \
                | sha256sum | cut -d' ' -f1)"
            echo "[.venv-idaes] idaes-data/bin tree: $(tree_hash .venv-idaes/idaes-data/bin)"
            echo "[.venv-idaes] ipopt sha256: $(sha256sum .venv-idaes/idaes-data/bin/ipopt \
                | cut -d' ' -f1)"
        fi
        if [ -d .venv-dwsim ]; then
            echo "[.venv-dwsim] pip freeze sha256: $(.venv-dwsim/bin/pip freeze | LC_ALL=C sort \
                | sha256sum | cut -d' ' -f1)"
            echo "[.venv-dwsim] dotnet tree: $(tree_hash .venv-dwsim/dotnet)"
            echo "[.venv-dwsim] dwsim tree: $(tree_hash .venv-dwsim/dwsim)"
            echo "[.venv-dwsim] DWSIM.Automation.dll sha256: $(sha256sum \
                .venv-dwsim/dwsim/DWSIM.Automation.dll | cut -d' ' -f1)"
        fi
    } | tee -a "$LOG"
}

T_ALL=$SECONDS
note "host"
{ uname -a; "$PYTHON" --version; ldd --version | head -1; } >>"$LOG" 2>&1

if [ "$WHICH" = "all" ] || [ "$WHICH" = "idaes" ]; then
    if build_idaes; then STATUS_IDAES="built"; else STATUS_IDAES="BLOCKED (see $LOG)"; fi
fi
if [ "$WHICH" = "all" ] || [ "$WHICH" = "dwsim" ]; then
    if build_dwsim; then STATUS_DWSIM="built"; else STATUS_DWSIM="BLOCKED (see $LOG)"; fi
fi
fingerprint
note "summary"
say "IDAES: $STATUS_IDAES"
say "DWSIM: $STATUS_DWSIM"
say "total $((SECONDS - T_ALL)) s; full log in $LOG"
case "$STATUS_IDAES$STATUS_DWSIM" in *BLOCKED*) exit 1 ;; esac
exit 0
