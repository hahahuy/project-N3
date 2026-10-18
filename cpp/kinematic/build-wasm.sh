#!/usr/bin/env bash
set -euo pipefail

root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
out="$root/frontend/public/cpp-wasm"
mkdir -p "$out"

if ! command -v em++ >/dev/null 2>&1; then
  printf '%s\n' "em++ not found; source emsdk_env.sh first" >&2
  exit 1
fi

em++ "$root/cpp/kinematic/kernel.cpp" "$root/cpp/kinematic/wasm_bindings.cpp" \
  --bind -std=c++20 -O3 \
  -sMODULARIZE=1 -sEXPORT_ES6=1 -sEXPORT_NAME=createR2SKinematicModule \
  -sENVIRONMENT=web,worker -sSINGLE_FILE=1 -sALLOW_MEMORY_GROWTH=1 \
  -sEXPORTED_FUNCTIONS='["_malloc","_free"]' \
  -sEXPORTED_RUNTIME_METHODS='["UTF8ToString","stringToUTF8","lengthBytesUTF8"]' \
  -o "$out/kinematic.js"

printf '%s\n' "Built $out/kinematic.js"
