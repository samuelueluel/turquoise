#!/usr/bin/env bash
# Downloads and installs the latest Neptune binary from GitHub releases.
# Neptune is a lightweight mechanical keyboard sound simulator written in Go.
# Not in Fedora repos; we use the pre-built binary from GitHub releases.
set -euo pipefail

API_URL="https://api.github.com/repos/M1ndo/Neptune/releases/latest"
WORK_DIR="$(mktemp -d)"
trap "rm -rf '$WORK_DIR'" EXIT

VERSION=$(curl -fsSL --retry 5 --retry-delay 5 "$API_URL" | grep '"tag_name"' | cut -d'"' -f4)
TARBALL="Neptune.tar.xz"
URL="https://github.com/M1ndo/Neptune/releases/download/${VERSION}/${TARBALL}"

echo "Installing Neptune ${VERSION}..."

cd "$WORK_DIR"
curl -fsSLo "$TARBALL" --retry 5 --retry-delay 5 "$URL"
tar -xJf "$TARBALL"

# Tarball installs to usr/local/bin/ — redirect to /usr/bin/ for Fedora Atomic.
# /usr/local/ is a writable overlay (/var/usrlocal/) and would not be part of
# the immutable image.
install -Dm755 usr/local/bin/Neptune /usr/bin/neptune
install -Dm644 usr/local/share/applications/Neptune.desktop /usr/share/applications/Neptune.desktop
install -Dm644 usr/local/share/pixmaps/Neptune.png /usr/share/pixmaps/Neptune.png

# Record version for the build manifest
echo "Neptune: ${VERSION}" >> /tmp/build-manifest.txt

echo "Done: $(neptune --version 2>&1 || echo 'installed')"
