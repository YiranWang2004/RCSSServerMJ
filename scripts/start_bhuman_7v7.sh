#!/usr/bin/env bash
set -euo pipefail
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONPATH="$REPO_DIR/src${PYTHONPATH:+:$PYTHONPATH}"
exec "${RCSS_PYTHON:-python}" -m rcsssmj \
  --field fifa7vs7 --rules ssim --sync --bhuman-physics "$@"
