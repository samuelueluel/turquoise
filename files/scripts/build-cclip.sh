#!/usr/bin/env bash
# Builds and installs cclip from source.
set -euo pipefail

# Build-time deps (cargo, rust) are pre-installed by the recipe's build-toolchain block.

echo "Building cclip..."
WORK_DIR="$(mktemp -d)"
trap "rm -rf '$WORK_DIR'" EXIT

# Try crates.io first, fallback to known GitHub repo if not found
if ! cargo install --root "$WORK_DIR" cclip; then
    echo "crates.io failed, trying git repository..."
    cargo install --git https://github.com/heather7283/cclip --root "$WORK_DIR" cclip
fi

# The binary name might be cclip and cclipd
if [ -f "$WORK_DIR/bin/cclip" ]; then
    install -Dm755 "$WORK_DIR/bin/cclip" /usr/bin/cclip
fi
if [ -f "$WORK_DIR/bin/cclipd" ]; then
    install -Dm755 "$WORK_DIR/bin/cclipd" /usr/bin/cclipd
fi

echo "cclip installed successfully."
