#!/usr/bin/env bash

set -ouex pipefail

echo "Hiding system desktop files to prevent fsel duplicates..."

if [[ -f /usr/share/applications/kitty.desktop ]]; then
    echo "NoDisplay=true" >> /usr/share/applications/kitty.desktop
fi

if [[ -f /usr/share/applications/Alacritty.desktop ]]; then
    echo "NoDisplay=true" >> /usr/share/applications/Alacritty.desktop
fi
