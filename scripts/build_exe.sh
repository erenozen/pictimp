#!/bin/bash
set -ex

SYSTEM="$(uname -s | tr '[:upper:]' '[:lower:]')"
MACHINE="$(uname -m | tr '[:upper:]' '[:lower:]')"

if [ "$SYSTEM" = "linux" ]; then
  TARGET="linux-x64"
elif [ "$SYSTEM" = "darwin" ]; then
  if [ "$MACHINE" = "arm64" ] || [ "$MACHINE" = "aarch64" ]; then
    TARGET="macos-arm64"
  else
    TARGET="macos-x64"
  fi
fi

echo "Building PyInstaller executable for $TARGET..."

pyinstaller --noconfirm --onefile --console \
  --name "pairwise-cli-$TARGET" \
  --add-data "vendor/pict/$TARGET/*:vendor/pict/$TARGET" \
  --add-data "THIRD_PARTY_NOTICES.txt:." \
  pairwise_cli/__main__.py

echo "Done! Executable is in dist/"
