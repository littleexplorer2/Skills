#!/bin/bash
set -euo pipefail
SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PY="${LECTURE_REVIEW_PYTHON:-$HOME/Library/Application Support/LectureReviewPDF/venv/bin/python}"
if [ ! -x "$VENV_PY" ]; then
  echo "Missing Python virtual environment. Set LECTURE_REVIEW_PYTHON to a Python environment with requirements.txt installed." >&2
  exit 2
fi
export DYLD_FALLBACK_LIBRARY_PATH="/opt/homebrew/lib:/usr/local/lib${DYLD_FALLBACK_LIBRARY_PATH:+:$DYLD_FALLBACK_LIBRARY_PATH}"
exec "$VENV_PY" "$SKILL_DIR/scripts/build_pdf.py" "$@"
