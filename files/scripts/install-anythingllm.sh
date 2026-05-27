#!/usr/bin/env bash
# Downloads the latest AnythingLLM AppImage and extracts it into /usr/lib/anythingllm.
# This ensures it is pre-built into the Turquoise image and auto-updated nightly.
set -euo pipefail

echo "Installing AnythingLLM (AppImage Extract)..."

URL="https://cdn.anythingllm.com/latest/AnythingLLMDesktop.AppImage"
WORK_DIR="$(mktemp -d)"
trap "rm -rf '$WORK_DIR'" EXIT

cd "$WORK_DIR"
echo "Downloading $URL..."
curl -fsSL --retry 5 --retry-delay 5 "$URL" -o anythingllm.AppImage
chmod +x anythingllm.AppImage

echo "Extracting AppImage..."
./anythingllm.AppImage --appimage-extract

# Extracted directory is squashfs-root/
# Move it to /usr/lib/anythingllm
rm -rf /usr/lib/anythingllm
mv squashfs-root /usr/lib/anythingllm

# Create symlink for the main executable
# (Checks common naming patterns inside the AppImage)
if [ -f /usr/lib/anythingllm/anythingllm ]; then
    ln -sf /usr/lib/anythingllm/anythingllm /usr/bin/anythingllm
elif [ -f /usr/lib/anythingllm/anything-llm-desktop ]; then
    ln -sf /usr/lib/anythingllm/anything-llm-desktop /usr/bin/anythingllm
else
    # Find any executable in the root as fallback
    EXE_PATH=$(find /usr/lib/anythingllm -maxdepth 1 -executable -type f | head -n 1)
    ln -sf "$EXE_PATH" /usr/bin/anythingllm
fi

# Copy the desktop launcher
DESKTOP_FILE=$(find /usr/lib/anythingllm -maxdepth 1 -name "*.desktop" | head -n 1)
if [ -n "$DESKTOP_FILE" ]; then
    cp "$DESKTOP_FILE" /usr/share/applications/anythingllm.desktop
    sed -i 's|^Exec=.*|Exec=anythingllm %U|' /usr/share/applications/anythingllm.desktop
    
    # Configure icon
    ICON_FILE=$(find /usr/lib/anythingllm -maxdepth 1 -name "*.png" -o -name "*.svg" | head -n 1)
    if [ -n "$ICON_FILE" ]; then
        sed -i "s|^Icon=.*|Icon=$ICON_FILE|" /usr/share/applications/anythingllm.desktop
    fi
fi

echo "AnythingLLM installed successfully."
