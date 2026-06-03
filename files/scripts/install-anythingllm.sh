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
# Move it to /usr/lib/anythingllm and ensure world-readable permissions.
# AppImage extraction runs as root and can leave directories mode 700,
# which causes desktop shells to hit EACCES when resolving icon paths.
rm -rf /usr/lib/anythingllm
mv squashfs-root /usr/lib/anythingllm
chmod -R a+rX /usr/lib/anythingllm

# Create symlink for the main executable
# (Checks common naming patterns inside the AppImage)
if [ -f /usr/lib/anythingllm/anythingllm ]; then
    ln -sf /usr/lib/anythingllm/anythingllm /usr/bin/anythingllm
elif [ -f /usr/lib/anythingllm/anythingllm-desktop ]; then
    ln -sf /usr/lib/anythingllm/anythingllm-desktop /usr/bin/anythingllm
elif [ -f /usr/lib/anythingllm/anything-llm-desktop ]; then
    ln -sf /usr/lib/anythingllm/anything-llm-desktop /usr/bin/anythingllm
else
    # Find any executable in the root as fallback (excluding shared libraries and helpers)
    EXE_PATH=$(find /usr/lib/anythingllm -maxdepth 1 -executable -type f ! -name "*.so*" ! -name "chrome-sandbox" ! -name "chrome_crashpad_handler" | head -n 1)
    ln -sf "$EXE_PATH" /usr/bin/anythingllm
fi

# Copy icon to a standard system path so the .desktop Icon= field uses a bare
# name (not an absolute path). This prevents crashes in desktop shells that
# fatally handle a missing/unreadable absolute icon path.
ICON_FILE=$(find /usr/lib/anythingllm -maxdepth 2 \( -name "*.png" -o -name "*.svg" \) | sort | head -n 1)
if [ -n "$ICON_FILE" ]; then
    ICON_EXT="${ICON_FILE##*.}"
    install -Dm644 "$ICON_FILE" "/usr/share/pixmaps/anythingllm.${ICON_EXT}"
    ICON_NAME="anythingllm"
else
    ICON_NAME="anythingllm"
fi

# Write the desktop launcher directly — don't rely on the AppImage's bundled
# .desktop file, which may have stale paths or missing fields.
cat > /usr/share/applications/anythingllm.desktop << EOF
[Desktop Entry]
Name=AnythingLLM
Comment=A full-stack application for private AI
Exec=anythingllm %U
Icon=${ICON_NAME}
Terminal=false
Type=Application
Categories=Office;Utility;
MimeType=x-scheme-handler/anythingllm;
StartupWMClass=anythingllm
EOF

echo "AnythingLLM installed successfully."
