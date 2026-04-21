#!/usr/bin/env bash
# Builds and installs keyd from source.
# keyd is not in Fedora repos; was in Terra which has recurring GPG issues.
set -euo pipefail

VERSION="2.6.0"
TARBALL_URL="https://github.com/rvaiya/keyd/archive/refs/tags/v${VERSION}.tar.gz"
BUILD_DIR="$(mktemp -d)"
trap "rm -rf '$BUILD_DIR'" EXIT

# Build-time deps (gcc, make) are pre-installed by the recipe's build-toolchain block.

curl -fsSL --retry 3 --retry-delay 5 "$TARBALL_URL" | tar -xz -C "$BUILD_DIR"

cd "$BUILD_DIR/keyd-${VERSION}"
# PREFIX=/usr: Fedora Atomic's /usr/local/ is a writable overlay, not part of the image.
# FORCE_SYSTEMD=1: build container lacks /run/systemd/system, so systemd detection fails without this.
make PREFIX=/usr
make install PREFIX=/usr FORCE_SYSTEMD=1

echo "Done: $(keyd --version 2>&1 || true)"
