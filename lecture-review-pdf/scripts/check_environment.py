#!/usr/bin/env python3
"""Read-only runtime probe; does not install packages or generate PDFs."""
from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


def inspect_environment():
    errors = []
    warnings = []
    packages = {}
    for distribution in ("weasyprint", "PyMuPDF", "matplotlib"):
        try:
            packages[distribution] = importlib.metadata.version(distribution)
        except importlib.metadata.PackageNotFoundError:
            packages[distribution] = None
            errors.append(f"Missing {distribution}; use this interpreter with requirements.txt")
    dll_paths = [p for p in os.environ.get("WEASYPRINT_DLL_DIRECTORIES", "").split(";") if p]
    if os.name == "nt":
        for directory in dll_paths:
            if not Path(directory).is_dir():
                warnings.append(f"Configured DLL directory does not exist: {directory}")
    # A separate process captures native loader errors without importing optional
    # libraries during --help or mistaking package metadata for runtime readiness.
    native = {"ok": False}
    if not errors:
        try:
            probe = subprocess.run(
                [sys.executable, "-c", "import weasyprint, pymupdf, matplotlib; print(weasyprint.__version__, pymupdf.__version__)"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
            )
            native = {"ok": probe.returncode == 0, "exit_code": probe.returncode,
                      "stdout": probe.stdout.strip(), "stderr": probe.stderr.strip()}
            if probe.returncode:
                errors.append("Runtime import failed; inspect native_import and README Windows DLL guidance")
        except (OSError, subprocess.TimeoutExpired) as exc:
            errors.append(f"Runtime import probe could not finish: {exc}")
    poppler = shutil.which("pdftoppm")
    if not poppler:
        warnings.append("pdftoppm is not on PATH; page image review still needs a PDF rasterizer")
    font_hints = []
    if os.name == "nt":
        font_dir = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
        for name in ("msyh.ttc", "msyhbd.ttc", "simsun.ttc", "simhei.ttf"):
            if (font_dir / name).is_file():
                font_hints.append(str(font_dir / name))
    warnings.append("Font hints do not prove glyph coverage; inspect every rendered page")
    return {"ok": not errors, "python": sys.executable,
            "python_version": sys.version.split()[0], "packages": packages,
            "dll_directories": dll_paths, "native_import": native,
            "pdftoppm": poppler, "font_file_hints": font_hints,
            "errors": errors, "warnings": warnings}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Print machine-readable diagnostics")
    args = parser.parse_args()
    result = inspect_environment()
    if args.json:
        print(json.dumps(result, ensure_ascii=True, indent=2))
    else:
        print(f"Python: {result['python']} ({result['python_version']})")
        print(f"Packages: {result['packages']}")
        print("PASS: runtime imports" if result["ok"] else "FAIL: runtime is not ready")
        for message in result["errors"]:
            print(f"ERROR: {message}")
        for message in result["warnings"]:
            print(f"NOTE: {message}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
