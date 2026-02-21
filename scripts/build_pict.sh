#!/bin/bash
set -ex

if [ ! -d "third_party/pict-src" ]; then
  echo "third_party/pict-src not found!"
  exit 1
fi

SYSTEM="$(uname -s | tr '[:upper:]' '[:lower:]')"

if [ "$SYSTEM" = "linux" ]; then
  TARGET="linux-x64"
else
  echo "Unsupported system: $SYSTEM"
  echo "This script supports Linux x64 builds only."
  exit 1
fi

echo "Building PICT for $TARGET..."

cd third_party/pict-src
make clean || true
make
cd ../..

mkdir -p "vendor/pict/$TARGET"
cp third_party/pict-src/pict "vendor/pict/$TARGET/pict"
chmod +x "vendor/pict/$TARGET/pict"

echo "Successfully built and copied PICT to vendor/pict/$TARGET/pict"
