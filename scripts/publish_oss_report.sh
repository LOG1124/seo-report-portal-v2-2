#!/usr/bin/env bash
# Compatibility wrapper. Use publish_oss_report.py directly on Windows.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
exec "${PYTHON_BIN:-python3}" "$SCRIPT_DIR/publish_oss_report.py" "$@"
