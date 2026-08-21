#!/usr/bin/env bash
# Cross-platform Python launcher for AI log hooks.
# Tries python3 → python → py -3 on PATH; on Windows, falls back to common
# Python install locations because Git Bash launched by some hooks gets a
# stripped PATH that omits the Windows Python directory.
# Designed to be sourced or called as: bash scripts/_pyrun.sh <script> [args...]
#
# Exits 0 silently if no Python is found — hooks must never block the AI tool.
set -u

# Try `py -3` first: the Windows Python launcher always resolves to a real
# install, whereas `python3`/`python` on PATH can silently be the Microsoft
# Store's App Execution Alias stub — it "exists" per `command -v` but just
# prints an install nag and exits nonzero when run, breaking the hook.
if command -v py >/dev/null 2>&1; then
  PY="py -3"
elif command -v python3 >/dev/null 2>&1; then
  PY=python3
elif command -v python >/dev/null 2>&1; then
  PY=python
else
  # PATH lookup failed — probe standard Windows install locations.
  PY=""
  shopt -s nullglob 2>/dev/null || true
  for cand in \
    /c/Users/*/AppData/Local/Programs/Python/Python*/python.exe \
    "/c/Program Files/Python"*/python.exe \
    "/c/Program Files (x86)/Python"*/python.exe \
    /c/Python*/python.exe; do
    if [ -x "$cand" ]; then PY="$cand"; break; fi
  done
  shopt -u nullglob 2>/dev/null || true
  [ -n "$PY" ] || exit 0
fi

# shellcheck disable=SC2086
exec $PY "$@"
