#!/bin/bash
set -euo pipefail
if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "This installer is for macOS." >&2; exit 1
fi
SCRIPT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHECK_ONLY=0
for arg in "$@"; do
  case "$arg" in
    --check-only) CHECK_ONLY=1 ;;
    --no-install-skill) ;;
    --help|-h) echo "Usage: bash Install.command [--check-only] [--no-install-skill]"; exit 0 ;;
    *) echo "Unknown installer option: $arg" >&2; exit 2 ;;
  esac
done
find_python() {
  local candidate
  for candidate in "${LECTURE_REVIEW_PYTHON:-}" "$HOME/Library/Application Support/LectureReviewPDF/venv/bin/python" /opt/homebrew/bin/python3 /usr/local/bin/python3 "$(command -v python3 || true)"; do
    if [[ -n "$candidate" && -x "$candidate" ]] && "$candidate" -c 'import sys; raise SystemExit(sys.version_info < (3,10))' >/dev/null 2>&1; then
      printf '%s\n' "$candidate"; return 0
    fi
  done
  return 1
}
find_brew() {
  for candidate in "$(command -v brew || true)" /opt/homebrew/bin/brew /usr/local/bin/brew; do
    if [[ -n "$candidate" && -x "$candidate" ]]; then printf '%s\n' "$candidate"; return 0; fi
  done
  return 1
}
ensure_brew() {
  if ! BREW_BIN="$(find_brew)"; then
    echo "Installing Homebrew from its official installer; macOS may request administrator approval."
    local download_dir
    download_dir="$(mktemp -d)"
    /usr/bin/curl --fail --location --proto '=https' --tlsv1.2 https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh -o "$download_dir/homebrew-install.sh"
    /bin/bash "$download_dir/homebrew-install.sh"
    rm -rf "$download_dir"
    BREW_BIN="$(find_brew)" || { echo "Homebrew installation did not finish." >&2; exit 1; }
  fi
}
if ! PYTHON_BIN="$(find_python)"; then
  [[ "$CHECK_ONLY" != 1 ]] || { echo "Python 3.10+ missing; check-only installed nothing." >&2; exit 1; }
  ensure_brew
  "$BREW_BIN" install python@3.12
  PYTHON_BIN="$("$BREW_BIN" --prefix python@3.12)/bin/python3.12"
fi
if [[ "$CHECK_ONLY" != 1 ]]; then
  TEX_FOUND=0
  # Respect an existing custom engine, PATH, and MacTeX's standard link.
  for candidate in "${LECTURE_REVIEW_XELATEX:-}" "$(command -v xelatex || true)" /Library/TeX/texbin/xelatex; do
    if [[ -n "$candidate" && -x "$candidate" ]]; then TEX_FOUND=1; break; fi
  done
  if [[ "$TEX_FOUND" != 1 ]]; then
    ensure_brew
    "$BREW_BIN" install --cask basictex
    [[ -x /Library/TeX/texbin/xelatex ]] || { echo "BasicTeX installed but XeLaTeX not found; reopen Terminal and retry." >&2; exit 1; }
  fi
fi
# tlmgr and its helper commands must see the same distribution immediately.
export PATH="/Library/TeX/texbin:$PATH"
exec "$PYTHON_BIN" "$SCRIPT_ROOT/install_runtime.py" "$@"
