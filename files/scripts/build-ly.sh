#!/usr/bin/env bash
set -euo pipefail

# Build and install the ly display manager from source
# Ly now uses the Zig build system for its latest versions.

echo "--- Building ly display manager from source ---"

# 1. Install Zig (required for building)
# Since we remove it at the end of the recipe, we can install it here if missing.
if ! command -v zig &> /dev/null; then
    dnf install -y zig
fi

# 2. Clone the repository
TEMP_DIR=$(mktemp -d)
git clone --recurse-submodules https://github.com/fairyglade/ly "$TEMP_DIR"
cd "$TEMP_DIR"

# 3. Build and install
# We use the provided build system
zig build
zig build install --prefix /usr

# 4. Manual installation of systemd unit and config (if zig build doesn't handle /etc)
# The zig build usually puts things in /usr/bin and /usr/lib
# We ensure the config and service are in the right places for Fedora
mkdir -p /etc/ly
cp res/config.ini /etc/ly/
cp res/ly.service /usr/lib/systemd/system/

echo "ly built and installed to /usr/bin/ly"
rm -rf "$TEMP_DIR"
