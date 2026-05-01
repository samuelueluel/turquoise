#!/usr/bin/env bash
# Builds and installs rmpcd from source via cargo.
# rmpcd is not distributed as a pre-built binary.
set -euo pipefail

# Build-time deps (cargo, rust, git) are pre-installed by the recipe's build-toolchain block.

echo "Building rmpcd from source..."
WORK_DIR="$(mktemp -d)"
trap "rm -rf '$WORK_DIR'" EXIT

cd "$WORK_DIR"
for i in 1 2 3 4 5; do
    git clone --depth=1 https://github.com/mierak/rmpc.git && break
    echo "Clone attempt $i failed, retrying in 5 seconds..."
    sleep 5
done
cd rmpc

CARGO_NET_RETRY=5 cargo build --release --package rmpcd

# Install directly to /usr/bin/ (required for immutable atomic images, /usr/local/bin is an overlay)
install -Dm755 target/release/rmpcd /usr/bin/rmpcd

echo "rmpcd installed successfully."
