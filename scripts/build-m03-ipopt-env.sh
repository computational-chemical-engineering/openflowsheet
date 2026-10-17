#!/usr/bin/env bash
# Build the environment of the optional general-NLP path (M03 WO-6, the [A10] audit of an Ipopt
# distribution; docs/m03-ipopt-audit.md), outside requirements.lock and outside the project .venv.
#
# Specification §9 and §14 N3: a user-space conda-forge environment, no root, no system packages.
# Nothing here is a dependency of the default install. The environment is:
#
#   <prefix>/                     conda-forge packages, exactly benchmarks/m03/nlp-conda-explicit.txt
#                                 (CPython 3.13.5, Ipopt 3.14.20, MUMPS 5.8.2, METIS 5.1.0, cyipopt
#                                 1.7.0, ampl-asl 1.0.0, OpenBLAS …), installed with no solve
#     lib/python3.13/site-packages  plus the PyPI wheels of benchmarks/m03/nlp-pip.lock, --no-deps
#                                 --require-hashes (the default runtime closure at the lock's
#                                 versions, pyomo 6.10.1, packaging)
#     share/pyomo/lib/            libpynumero_ASL.so, compiled here from the installed Pyomo's own
#                                 sources against the environment's ampl-asl (no conda-forge or PyPI
#                                 artifact ships it for CPython 3.13), and its build record
#     share/m03-ipopt-notices/    notices read from upstream sources that a package's own recipe
#                                 names and hashes, where a package ships none or the wrong one
#                                 (libsqlite3, libuuid, PORD)
#   <cache>/                      micromamba (hash-pinned), its package cache, the build
#                                 environment (benchmarks/m03/nlp-build-conda-explicit.txt) and logs
#
# The CasADi wheel's bundled Ipopt is never used (ADR 0006 D2.4); the HSL interfaces of PyNumero are
# switched off at configure time. Every downloaded artifact is pinned by hash. Using the
# environment needs PYTHONNOUSERSITE=1 (conda's CPython enables the user site) and
# PYOMO_CONFIG_DIR=<prefix>/share/pyomo (Pyomo otherwise searches the working directory and
# ~/.pyomo/lib first); scripts/m03_ipopt_inventory.py sets both and records what was loaded.
#
# Usage: scripts/build-m03-ipopt-env.sh [prefix] [cache]
#        defaults: .venv-nlp and .reference-downloads/m03-ipopt (both git-ignored)
set -euo pipefail

cd "$(dirname "$0")/.."
ROOT="$PWD"
PREFIX="$(realpath -m "${1:-.venv-nlp}")"
CACHE="$(realpath -m "${2:-.reference-downloads/m03-ipopt}")"
mkdir -p "$CACHE"
LOG="$CACHE/build.log"
: >"$LOG"

MICROMAMBA_URL="https://conda.anaconda.org/conda-forge/linux-64/micromamba-2.9.0-0.tar.bz2"
MICROMAMBA_SHA256="8761c382127e6363bd9e0a2451aa3ef90d071a79133f736e2f759a3bf13040dd"
# Upstream sources whose URL and SHA-256 are the ones the conda package's own recipe
# (info/recipe/*.yaml) pins, read for one notice each that the package does not ship correctly:
#   libsqlite3  libsqlite-3.53.4-h0737f62_103 ships no notice at all
#   libuuid     libuuid-2.42.4-hcfc3c73_0 ships util-linux's top-level COPYING (GPL-2.0, the default
#               for util-linux code without its own licence); libuuid carries its own
#   libpord     mumps-seq-5.8.2-gfortran_hfb83c00_3's LICENSE excludes PORD and points at
#               PORD/README, which the package does not ship
SOURCES=(
    "libsqlite3|https://www.sqlite.org/2026/sqlite-autoconf-3530400.tar.gz|0e9483900e92cd5de8fd48d16bf9200145a61f7fd5be542a5ac81d8a9516eb9c|sqlite-autoconf-3530400/sqlite3.h|libsqlite"
    "libuuid|https://github.com/util-linux/util-linux/archive/refs/tags/v2.42.4.tar.gz|e1d38037dab761a2d39114d88a6744ffd5a4576efa29fe41e1dfbd8453891fe7|util-linux-2.42.4/libuuid/COPYING,util-linux-2.42.4/Documentation/licenses/COPYING.BSD-3-Clause|libuuid"
    "libpord|https://mumps-solver.org/MUMPS_5.8.2.tar.gz|eb515aa688e6dbab414bb6e889ff4c8b23f1691a843c68da5230a33ac4db7039|MUMPS_5.8.2/PORD/README|mumps-seq"
)

note() { echo "=== $* ===" | tee -a "$LOG"; }
fetch() { # fetch <url> <sha256> <target>
    [ -f "$3" ] || curl -sSfL -o "$3" "$1"
    echo "$2  $3" | sha256sum -c --quiet - || { echo "hash mismatch: $3" | tee -a "$LOG"; exit 1; }
}

note "micromamba"
fetch "$MICROMAMBA_URL" "$MICROMAMBA_SHA256" "$CACHE/micromamba.tar.bz2"
mkdir -p "$CACHE/micromamba"
tar -xjf "$CACHE/micromamba.tar.bz2" -C "$CACHE/micromamba" bin/micromamba
MM="$CACHE/micromamba/bin/micromamba"
export MAMBA_ROOT_PREFIX="$CACHE/root"

note "runtime environment $PREFIX"
rm -rf "$PREFIX"
"$MM" create -y -p "$PREFIX" -f benchmarks/m03/nlp-conda-explicit.txt >>"$LOG" 2>&1
PYTHONNOUSERSITE=1 "$PREFIX/bin/python" -I -m pip install --no-deps --no-cache-dir --require-hashes \
    --only-binary=:all: -r benchmarks/m03/nlp-pip.lock >>"$LOG" 2>&1

note "build environment"
BUILD_ENV="$CACHE/build-env"
rm -rf "$BUILD_ENV"
"$MM" create -y -p "$BUILD_ENV" -f benchmarks/m03/nlp-build-conda-explicit.txt >>"$LOG" 2>&1

note "libpynumero_ASL"
# The sources are the installed Pyomo's own (pyomo/contrib/pynumero/src and the FindASL module it
# includes from ampl_function_demo/src), copied so that nothing is written into site-packages.
SITE="$PREFIX/lib/python3.13/site-packages"
SRC="$CACHE/pynumero-src"
BUILD="$CACHE/pynumero-build"
rm -rf "$SRC" "$BUILD"
mkdir -p "$SRC/pynumero" "$SRC/ampl_function_demo"
cp -r "$SITE/pyomo/contrib/pynumero/src" "$SRC/pynumero/"
cp -r "$SITE/pyomo/contrib/ampl_function_demo/src" "$SRC/ampl_function_demo/"
BUILD_ENVIRONMENT=(env -i "HOME=$HOME" "PATH=$BUILD_ENV/bin:/usr/bin:/bin")
# The conda compiler's spec files add `-rpath <build-env>/lib` to every link, which would make the
# library look for its C++ runtime in the build environment and make its bytes depend on where the
# cache is. A specs file read after them restates `*link_command` without that clause (the
# `-rpath-link` and `-L` of the toolchain stay); the run-time search path is then only the
# installed location's relative `$ORIGIN/../../../lib`, linked in directly rather than rewritten.
GCC_SPECS_DIR="$(dirname "$("$BUILD_ENV/bin/x86_64-conda-linux-gnu-c++" -print-libgcc-file-name)")"
LINK_SPECS="$CACHE/link-without-build-env-rpath.specs"
{
    echo "*link_command:"
    awk '/^\*link_command:/{body = 1; next} body && /^$/ {exit} body {print}' \
        "$GCC_SPECS_DIR/conda.specs" |
        sed "s|-rpath $BUILD_ENV/lib ||"
} >"$LINK_SPECS"
if grep -qF -- "-rpath $BUILD_ENV" "$LINK_SPECS" || ! grep -qF -- "-rpath-link $BUILD_ENV" "$LINK_SPECS"; then
    echo "unexpected conda.specs link_command; inspect $LINK_SPECS" | tee -a "$LOG"
    exit 1
fi
CMAKE_ARGS=(
    -DCMAKE_BUILD_TYPE=Release
    "-DCMAKE_C_COMPILER=$BUILD_ENV/bin/x86_64-conda-linux-gnu-cc"
    "-DCMAKE_CXX_COMPILER=$BUILD_ENV/bin/x86_64-conda-linux-gnu-c++"
    "-DCMAKE_CXX_FLAGS=-ffile-prefix-map=$SRC=pyomo-src"
    "-DCMAKE_SHARED_LINKER_FLAGS=-specs=$LINK_SPECS"
    -DCMAKE_BUILD_WITH_INSTALL_RPATH=ON
    '-DCMAKE_INSTALL_RPATH=$ORIGIN/../../../lib'
    "-DAMPLASL_DIR=$PREFIX"
    -DBUILD_AMPLASL=OFF -DBUILD_AMPLASL_IF_NEEDED=OFF
    -DENABLE_HSL=OFF -DBUILD_MA27=OFF -DBUILD_MA57=OFF
)
"${BUILD_ENVIRONMENT[@]}" "$BUILD_ENV/bin/cmake" -S "$SRC/pynumero/src" -B "$BUILD" \
    "${CMAKE_ARGS[@]}" >>"$LOG" 2>&1
"${BUILD_ENVIRONMENT[@]}" "$BUILD_ENV/bin/cmake" --build "$BUILD" --target pynumero_ASL -j4 \
    >>"$LOG" 2>&1
if [ "$(objdump -p "$BUILD/libpynumero_ASL.so" | awk '$1 ~ /R(UN)?PATH/ {print $2}')" != '$ORIGIN/../../../lib' ]; then
    echo "libpynumero_ASL.so has an unexpected run-time search path" | tee -a "$LOG"
    exit 1
fi
if strings "$BUILD/libpynumero_ASL.so" | grep -qF -e "$CACHE" -e "$PREFIX"; then
    echo "libpynumero_ASL.so still names a build path" | tee -a "$LOG"
    exit 1
fi
mkdir -p "$PREFIX/share/pyomo/lib"
install -m 0644 "$BUILD/libpynumero_ASL.so" "$PREFIX/share/pyomo/lib/libpynumero_ASL.so"
"$PREFIX/bin/python" -I - "$SRC" "$PREFIX" "$CACHE" "${CMAKE_ARGS[@]}" <<'EOF'
import hashlib, json, sys
from pathlib import Path
src, prefix, cache, args = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3], sys.argv[4:]
def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
sources = {str(p.relative_to(src)): digest(p) for p in sorted(src.rglob("*")) if p.is_file()}
record = {
    "object": "share/pyomo/lib/libpynumero_ASL.so",
    "sha256": digest(prefix / "share/pyomo/lib/libpynumero_ASL.so"),
    "sources": "pyomo-6.10.1 site-packages: pyomo/contrib/pynumero/src, pyomo/contrib/ampl_function_demo/src",
    "sources_digest": hashlib.sha256("".join(f"{k}\t{v}\n" for k, v in sources.items()).encode()).hexdigest(),
    "cmake_args": [a.replace(str(src), "<src>").replace(str(prefix), "<prefix>").replace(cache, "<cache>") for a in args],
    "toolchain": "benchmarks/m03/nlp-build-conda-explicit.txt",
    "rpath": "$ORIGIN/../../../lib (linked in; the build environment's own rpath removed by a specs file)",
}
(prefix / "share/pyomo/lib/libpynumero_ASL.build.json").write_text(json.dumps(record, indent=1, sort_keys=True) + "\n")
EOF

note "notices from recipe-named upstream sources"
for entry in "${SOURCES[@]}"; do
    IFS='|' read -r key url sha members package <<<"$entry"
    archive="$CACHE/$(basename "$url")"
    fetch "$url" "$sha" "$archive"
    target="$PREFIX/share/m03-ipopt-notices/$key"
    mkdir -p "$target"
    IFS=',' read -r -a member_list <<<"$members"
    for member in "${member_list[@]}"; do
        if [ "$key" = libsqlite3 ]; then # the header's opening comment is SQLite's notice
            tar -xzf "$archive" -O "$member" | sed -n '1,/^\*\{8,\}/p' \
                >"$target/$(basename "$member").notice"
        else
            tar -xzf "$archive" -O "$member" >"$target/$(basename "$member")"
        fi
    done
    printf '%s\n' "$url sha256:$sha members $members (pinned by $package's recipe)" >"$target/SOURCE"
done

note "fingerprint"
"$MM" list -p "$PREFIX" --explicit --md5 2>/dev/null | grep '^https' | sha256sum | sed 's/-$/conda packages/'
PYTHONNOUSERSITE=1 "$PREFIX/bin/python" -I -m pip freeze --all | sha256sum | sed 's/-$/pip freeze/'
sha256sum "$PREFIX/share/pyomo/lib/libpynumero_ASL.so"
echo "built $PREFIX (log: $LOG)"
