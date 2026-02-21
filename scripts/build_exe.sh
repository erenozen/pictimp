#!/bin/bash
set -ex

SYSTEM="$(uname -s | tr '[:upper:]' '[:lower:]')"

if [ "$SYSTEM" = "linux" ]; then
  TARGET="linux-x64"
else
  echo "Unsupported system for this script: $SYSTEM"
  echo "This script supports Linux x64 builds only."
  exit 1
fi

echo "Building PyInstaller executable for $TARGET..."

pyinstaller --noconfirm --onefile --console \
  --name "pairwise-cli-$TARGET" \
  --add-data "vendor/pict/$TARGET/*:vendor/pict/$TARGET" \
  --add-data "THIRD_PARTY_NOTICES.txt:." \
  pairwise_cli/__main__.py

echo "Done! Executable is in dist/"
