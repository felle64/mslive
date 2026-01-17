#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  ./scripts/run_dash.sh PORT [extra args...]
  ./scripts/run_dash.sh --replay FILE [extra args...]

Examples:
  ./scripts/run_dash.sh /dev/ttyUSB0
  ./scripts/run_dash.sh --replay logs/ms42_dash_20260114_132209.csv
EOF
}

if [ "$#" -lt 1 ]; then
  usage
  exit 1
fi

if [ "$1" = "--replay" ]; then
  if [ "$#" -lt 2 ]; then
    usage
    exit 1
  fi
  file="$2"
  shift 2
  mkdir -p logs
  exec python -m mslive.apps.dash_pygame --replay "$file" "$@"
else
  port="$1"
  shift
  mkdir -p logs
  exec python -m mslive.apps.dash_pygame --port "$port" "$@"
fi
