#!/usr/bin/env bash

set -euo pipefail

echo "Installing Zen Browser (Native Binary)..."

# Fetch latest release URL
URL="https://github.com/zen-browser/desktop/releases/latest/download/zen.linux-x86_64.tar.xz"

# Download and extract to /tmp
cd /tmp
echo "Downloading $URL..."
curl -fsSL --retry 3 --retry-delay 5 "$URL" -o zen.tar.xz

echo "Extracting..."
tar -xf zen.tar.xz

# Move to /usr/lib
mv zen /usr/lib/zen-browser

# Create symlink
ln -sf /usr/lib/zen-browser/zen /usr/bin/zen-browser

# Copy the desktop file and update Exec and Icon
if [ -f /usr/lib/zen-browser/zen.desktop ]; then
    cp /usr/lib/zen-browser/zen.desktop /usr/share/applications/zen-browser.desktop
    sed -i 's|^Exec=.*|Exec=zen-browser %u|' /usr/share/applications/zen-browser.desktop
    sed -i 's|^Icon=.*|Icon=/usr/lib/zen-browser/browser/chrome/icons/default/default128.png|' /usr/share/applications/zen-browser.desktop
fi

echo "Zen Browser installed successfully."
