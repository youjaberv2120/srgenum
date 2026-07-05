#!/usr/bin/env bash
# Mirror this project's source + organized outputs into the sibling srgenum
# clone. Excludes generated / heavy / IDE / venv artifacts.
set -euo pipefail

SRC="$(cd "$(dirname "$0")/.." && pwd)"
DEST="$(cd "$SRC/.." && pwd)/srgenum"

if [ ! -d "$DEST/.git" ]; then
  echo "Expected clone at $DEST" >&2
  exit 1
fi

rsync -a --delete \
  --exclude='.venv/' \
  --exclude='__pycache__/' \
  --exclude='*.pyc' \
  --exclude='.pytest_cache/' \
  --exclude='.DS_Store' \
  --exclude='Vendor/sms/build/' \
  --exclude='Vendor/sms/.git/' \
  --exclude='.git/' \
  --exclude='Output/_srg29_full.log' \
  "$SRC/" "$DEST/"

echo "Mirrored $SRC -> $DEST"
