#!/usr/bin/env bash
# Builds and installs xdg-desktop-portal-termfilechooser (hunkyburrito fork).
# Provides Yazi as the system file picker via the XDG portal protocol.
# C/Meson project — not packaged for Fedora.
set -euo pipefail

REPO_URL="https://github.com/hunkyburrito/xdg-desktop-portal-termfilechooser"
BUILD_DIR="$(mktemp -d)"
trap "rm -rf '$BUILD_DIR'" EXIT

# Build-time deps (meson, ninja-build, gcc, inih-devel, systemd-devel, scdoc) are pre-installed by the recipe's build-toolchain block.

git clone --depth=1 "$REPO_URL" "$BUILD_DIR/src"
cd "$BUILD_DIR/src"

meson setup --prefix=/usr "$BUILD_DIR/build"
ninja -C "$BUILD_DIR/build"
ninja -C "$BUILD_DIR/build" install

# Default config — use yazi, open with kitty (both are in the image)
SHARE_DIR="/usr/share/xdg-desktop-portal-termfilechooser"
mkdir -p "$SHARE_DIR"
cat > "$SHARE_DIR/config" << 'EOF'
[filechooser]
cmd=yazi-wrapper.sh
default_dir=$HOME
env=TERMCMD=kitty --title 'File Picker'
open_mode=suggested
save_mode=suggested
EOF
