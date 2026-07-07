#!/usr/bin/env bash
# Build AI Content Factory into a distributable folder.
# Produces dist/AIContentFactory/. Wrap with an OS-specific installer separately.
set -euo pipefail
cd "$(dirname "$0")/.."

VENV=${VENV:-.venv}
"$VENV/bin/python" -m pip install -e ".[dev]"
"$VENV/bin/python" -m pip install pyinstaller

# Run the test suite first — never ship a red build.
QT_QPA_PLATFORM=offscreen "$VENV/bin/pytest" -q

"$VENV/bin/pyinstaller" --noconfirm --clean aicf.spec

echo
echo "Build complete → dist/AIContentFactory/"
echo "Next: wrap with NSIS (Windows) / dmgbuild (macOS) / appimage (Linux)."
