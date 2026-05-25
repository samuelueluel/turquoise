#!/usr/bin/env bash
# Builds and installs wayvibes from source.
# wayvibes is a Wayland-native mechanical keyboard sound simulator (libevdev + miniaudio).
# Not packaged for Fedora; no releases — built from latest git.
set -euo pipefail

REPO="https://github.com/sahaj-b/wayvibes"
WORK_DIR="$(mktemp -d)"
trap "rm -rf '$WORK_DIR'" EXIT

# Build deps not in the shared toolchain block
dnf install -y --setopt=install_weak_deps=False libevdev-devel nlohmann-json-devel

echo "Cloning wayvibes..."
git clone --depth=1 "$REPO" "$WORK_DIR/wayvibes"
cd "$WORK_DIR/wayvibes"

COMMIT=$(git rev-parse --short HEAD)
echo "Building wayvibes @ ${COMMIT}..."

make -j"$(nproc)"

# Install to /usr/bin/ — /usr/local/ is a writable overlay (/var/usrlocal/) on
# Fedora Atomic and would not be part of the immutable image.
install -Dm755 wayvibes /usr/bin/wayvibes

# Remove build-only deps
dnf remove -y libevdev-devel nlohmann-json-devel

# Record version for the build manifest
echo "wayvibes: ${COMMIT}" >> /tmp/build-manifest.txt

echo "Done: wayvibes installed ($(wayvibes --version 2>&1 || echo 'no --version flag'))"
