#!/usr/bin/env bash
# Builds and installs fsel from source via crates.io.
set -euo pipefail

# Build-time deps (cargo, rust) are pre-installed by the recipe's build-toolchain block.

echo "Building fsel..."
WORK_DIR="$(mktemp -d)"
trap "rm -rf '$WORK_DIR'" EXIT

cargo install --root "$WORK_DIR" fsel

install -Dm755 "$WORK_DIR/bin/fsel" /usr/bin/fsel
echo "fsel installed successfully."
