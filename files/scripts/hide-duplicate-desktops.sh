#!/usr/bin/env bash

set -ouex pipefail

echo "Removing system desktop files to prevent fsel duplicates..."

# fsel ignores NoDisplay=true and doesn't deduplicate between system and local paths.
# We physically remove these from /usr/share/applications during the image build
# to ensure only the user's versions in ~/.local/share/applications are active.

APPS_TO_REMOVE=(
    "kitty.desktop"
    "Alacritty.desktop"
    "dev.zed.Zed.desktop"
    "com.mitchellh.ghostty.desktop"
)

for APP in "${APPS_TO_REMOVE[@]}"; do
    if [[ -f "/usr/share/applications/$APP" ]]; then
        echo "Removing system $APP"
        rm "/usr/share/applications/$APP"
    else
        echo "System $APP not found, skipping."
    fi
done
