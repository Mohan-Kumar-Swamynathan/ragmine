#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

if [[ -x "$ROOT_DIR/venv/bin/python" ]]; then
  PYTHONPATH=src "$ROOT_DIR/venv/bin/python" -m ragmine.cli "$@"
elif [[ -x "$ROOT_DIR/.venv/bin/python" ]]; then
  PYTHONPATH=src "$ROOT_DIR/.venv/bin/python" -m ragmine.cli "$@"
else
  PYTHONPATH=src python -m ragmine.cli "$@"
fi
