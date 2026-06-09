#!/usr/bin/env bash
# Builds and installs noctalia-shell v5 from source.
# Replaces the lionheartp/Hyprland COPR RPM.
set -euo pipefail

REPO_URL="https://github.com/noctalia-dev/noctalia-shell"
BRANCH="main"
BUILD_DIR="$(mktemp -d)"
trap "rm -rf '$BUILD_DIR'" EXIT

# Build-time deps are pre-installed by the recipe's build-toolchain block.
# All vendored third_party/ deps are committed directly; no submodules needed.

git clone --depth 1 --branch "$BRANCH" "$REPO_URL" "$BUILD_DIR/noctalia-shell"
cd "$BUILD_DIR/noctalia-shell"

# PREFIX=/usr: Fedora Atomic's /usr/local/ is a writable overlay, not part of the image.
meson setup build-release --buildtype=release -Db_lto=true --prefix=/usr
meson compile -C build-release
meson install -C build-release

echo "Done: $(find /usr/bin /usr/share/noctalia -maxdepth 0 2>/dev/null | tr '\n' ' ')"
