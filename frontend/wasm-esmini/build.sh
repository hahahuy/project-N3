#!/usr/bin/env bash

set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd -- "$script_dir/../.." && pwd)"
upstream_root="${ESMINI_SOURCE_DIR:-$repo_root/../esmini}"
source_dir="$upstream_root/EnvironmentSimulator/Libraries/esminiJS"
build_dir="$script_dir/build"
output_dir="$script_dir/dist"
patched_fmt_root="$build_dir/patched-externals/fmt"
patched_fmt_include_dir="$patched_fmt_root/include"
fmt_patch="$upstream_root/scripts/patches/fmt-11.2.0-emscripten-cstdlib.patch"

if ! command -v emcmake >/dev/null 2>&1; then
    printf '%s\n' "emcmake not found. Activate Emscripten before building." >&2
    exit 1
fi

if [[ ! -f "$source_dir/CMakeLists.txt" ]]; then
    printf '%s\n' "esminiJS source not found: $source_dir" >&2
    printf '%s\n' "Set ESMINI_SOURCE_DIR to an external esmini checkout." >&2
    exit 1
fi

rm -rf "$build_dir" "$output_dir"
mkdir -p "$build_dir" "$output_dir"
mkdir -p "$patched_fmt_root"

if [[ ! -f "$fmt_patch" ]]; then
    printf '%s\n' "fmt compatibility patch not found: $fmt_patch" >&2
    exit 1
fi

cp -R "$upstream_root/externals/fmt/include" "$patched_fmt_root/"
patch -s -N -p1 -d "$patched_fmt_root" < "$fmt_patch"

emcmake cmake -S "$source_dir" -B "$build_dir" -G Ninja \
    -DCMAKE_BUILD_TYPE=Release \
    -DFMT_OVERRIDE_INCLUDE_DIR="$patched_fmt_include_dir" \
    -DCMAKE_CXX_FLAGS="-sENVIRONMENT=web,worker" \
    -DCMAKE_EXE_LINKER_FLAGS="-sMODULARIZE=1 -sEXPORT_ES6=1 -sEXPORT_NAME=createEsminiModule -sENVIRONMENT=web,worker -sALLOW_MEMORY_GROWTH=1 -sEXPORTED_RUNTIME_METHODS=['FS','callMain','UTF8ToString'] -sFORCE_FILESYSTEM=1 -sWASM=1 -sSINGLE_FILE=0 -sWASM_ASYNC_COMPILATION=1"

cmake --build "$build_dir" --parallel
cp "$build_dir/esmini.js" "$output_dir/esmini.js"
if [[ -f "$build_dir/esmini.wasm" ]]; then
    cp "$build_dir/esmini.wasm" "$output_dir/esmini.wasm"
fi

printf '%s\n' "Built esminiJS project probe in $output_dir"
