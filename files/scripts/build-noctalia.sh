#!/usr/bin/env bash
# Builds and installs Noctalia v5 from the latest GitHub release tarball.
# Replaces the lionheartp/Hyprland COPR RPM.
set -euo pipefail

BUILD_DIR="$(mktemp -d)"
trap "rm -rf '$BUILD_DIR'" EXIT

# Fixed latest-release asset URL: avoids the unauthenticated GitHub API, which
# rate-limits shared CI runner IPs and returns an error object instead of assets.
RELEASE_URL="https://github.com/noctalia-dev/noctalia/releases/latest/download/noctalia-latest.tar.gz"

echo "Downloading Noctalia release from: ${RELEASE_URL}"
curl -fsSL --retry 5 --retry-delay 5 "${RELEASE_URL}" | tar -xzf - -C "$BUILD_DIR"

cd "$BUILD_DIR"/noctalia-*

# PREFIX=/usr: Fedora Atomic's /usr/local/ is a writable overlay, not part of the image.
meson setup build-release --buildtype=release -Db_lto=true --prefix=/usr
meson compile -C build-release
meson install -C build-release

echo "Done: $(find /usr/bin/noctalia* /usr/share/noctalia* -maxdepth 0 2>/dev/null | tr '\n' ' ')"

