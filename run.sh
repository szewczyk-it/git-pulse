#!/usr/bin/env bash
set -euo pipefail

REPO="${1:-$(pwd)}"
BRANCH="${2:-}"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cd "$PROJECT_DIR"

if command -v python >/dev/null 2>&1; then
  PYTHON_BIN="python"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="python3"
else
  echo "Error: python or python3 is required but not found in PATH."
  exit 127
fi

if [ ! -d ".venv" ]; then
  "$PYTHON_BIN" -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

"$PYTHON_BIN" -m pip -q install -U pip
"$PYTHON_BIN" -m pip -q install -r requirements.txt

# Pre-scan to cache (do not block if repo is not ready / any other error)
PYTHONPATH="$PROJECT_DIR" "$PYTHON_BIN" -m gitpulse.cli scan --repo "$REPO" ${BRANCH:+--branch "$BRANCH"} >/dev/null 2>&1 || true

# Important: PYTHONPATH set to project root
PYTHONPATH="$PROJECT_DIR" "$PYTHON_BIN" -m streamlit run gitpulse/app.py -- --repo "$REPO" ${BRANCH:+--branch "$BRANCH"}
