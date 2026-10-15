#!/usr/bin/env bash
set -u
image="${CARLA_IMAGE:-carla:0.9.15}"
port="${CARLA_PORT:-2000}"
host="${CARLA_HOST:-127.0.0.1}"
blocked=0
pass(){ printf 'PASS  %s\n' "$1"; }
block(){ printf 'BLOCK %s\n' "$1"; blocked=1; }
printf 'M5B CARLA preflight\nutc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
command -v python3 >/dev/null && pass "$(python3 --version 2>&1)" || block 'python3 missing'
python3 -c 'import carla' 2>/dev/null && pass 'CARLA Python client importable' || block 'CARLA Python client not importable'
command -v docker >/dev/null && docker image inspect "$image" >/dev/null 2>&1 && pass "Docker image present: $image" || block "Docker image absent: $image"
command -v carla >/dev/null && pass "CARLA executable: $(command -v carla)" || printf 'WARN  CARLA server executable not on PATH\n'
command -v nvidia-smi >/dev/null && nvidia-smi --query-gpu=name,driver_version --format=csv,noheader 2>/dev/null | sed 's/^/INFO  GPU: /' || printf 'WARN  nvidia-smi unavailable\n'
[[ -x "$HOME/esmini/bin/esmini" && -x "$HOME/esmini/bin/dat2csv" ]] && pass 'esmini baseline files found under HOME/esmini' || printf 'WARN  esmini baseline not found\n'
printf 'CARLA target: localhost:%s\n' "$port"
if command -v nc >/dev/null && nc -z "$host" "$port" 2>/dev/null; then
  pass "CARLA server port reachable: $host:$port"
else
  printf 'WARN  CARLA server not reachable at %s:%s\n' "$host" "$port"
fi
(( blocked )) && { printf 'RESULT BLOCKED: install/configure CARLA before spike.\n'; exit 1; }
printf 'RESULT READY: record versions/world/settings, then run checklist.\n'
