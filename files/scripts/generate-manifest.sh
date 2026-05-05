#!/usr/bin/env bash
set -euo pipefail

# This script runs at the end of the BlueBuild image build process.
# It probes key packages and records their versions into a manifest file
# baked into the image. This manifest can be used to track changes between builds.

MANIFEST="/usr/share/samuel-niri/manifest.md"
mkdir -p "$(dirname "$MANIFEST")"

{
    echo "# samuel-niri Image Manifest"
    echo "Build Date: $(date -u +'%Y-%m-%d %H:%M UTC')"
    echo ""
    echo "## Key Package Versions"
} > "$MANIFEST"

get_ver() {
    local name="$1"
    local cmd="$2"
    if command -v "$cmd" &>/dev/null; then
        # Try --version, then -v, then fallback to first line of help
        local ver
        ver=$($cmd --version 2>&1 | head -n1 || $cmd -v 2>&1 | head -n1 || $cmd --help 2>&1 | head -n1)
        echo "- **$name**: $ver" >> "$MANIFEST"
    else
        echo "- **$name**: (Not found in image)" >> "$MANIFEST"
    fi
}

get_ver "Niri" "niri"
get_ver "Yazi" "yazi"
get_ver "Zed" "zed"
get_ver "Alacritty" "alacritty"
get_ver "Zen Browser" "zen-browser"
get_ver "Helium" "helium"
get_ver "mpd" "mpd"
get_ver "rmpc" "rmpc"
get_ver "Alacritty" "alacritty"
get_ver "Kitty" "kitty"
get_ver "Nemo" "nemo"
get_ver "Chezmoi" "chezmoi"
get_ver "Just" "just"

echo "- **Kernel**: $(uname -r 2>/dev/null || echo 'Vanilla Stable (see recipe)')" >> "$MANIFEST"

echo "Manifest generated at $MANIFEST"
