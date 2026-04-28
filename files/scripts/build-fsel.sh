#!/usr/bin/env bash
# Builds and installs fsel from source via git clone.
set -euo pipefail

# Build-time deps (cargo, rust, git) are pre-installed by the recipe's build-toolchain block.

echo "Building fsel from source..."
WORK_DIR="$(mktemp -d)"
trap "rm -rf '$WORK_DIR'" EXIT

cd "$WORK_DIR"
git clone https://github.com/Mjoyufull/fsel
cd fsel

# Build the release binary
cargo build --release

# Install directly to /usr/bin/ (required for immutable atomic images, /usr/local/bin is an overlay)
install -Dm755 target/release/fsel /usr/bin/fsel

echo "fsel installed successfully."
