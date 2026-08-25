#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$ROOT/.venv"
PY="${PYTHON:-python3}"
ensure_core() {
  if [[ ! -x "$VENV/bin/python" ]]; then
    "$PY" -m venv "$VENV"
    "$VENV/bin/python" -m pip install --upgrade pip
    "$VENV/bin/python" -m pip install -e "$ROOT[test]"
  fi
}
cmd="${1:-serve}"; shift || true
case "$cmd" in
  bootstrap) ensure_core ;;
  serve) ensure_core; exec "$VENV/bin/python" -m sonicforge serve "$@" ;;
  doctor) ensure_core; exec "$VENV/bin/python" -m sonicforge doctor "$@" ;;
  provision) ensure_core; exec "$VENV/bin/python" -m sonicforge provision "$@" ;;
  test) ensure_core; exec "$VENV/bin/python" -m pytest "$@" ;;
  *) echo "usage: $0 {bootstrap|serve|doctor|provision|test}" >&2; exit 2 ;;
esac
