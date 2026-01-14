#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  ./scripts/run_log.sh PORT [extra args...]
  ./scripts/run_log.sh --replay FILE [extra args...]

Examples:
  ./scripts/run_log.sh /dev/ttyUSB0
  ./scripts/run_log.sh --replay logs/ms42_log_20260114_132209.csv
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
  exec python -m mslive.apps.logger_csv --replay "$file" "$@"
else
  port="$1"
  shift
  exec python -m mslive.apps.logger_csv --port "$port" "$@"
fi
