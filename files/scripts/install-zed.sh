#!/usr/bin/env bash
# Downloads and installs the official Zed binary from GitHub releases.
# Replaces the Terra RPM which has a wasmtime bug causing crashes on file open.
set -euo pipefail

URL="https://github.com/zed-industries/zed/releases/latest/download/zed-linux-x86_64.tar.gz"
WORK_DIR="$(mktemp -d)"
trap "rm -rf '$WORK_DIR'" EXIT

echo "Installing Zed editor..."

cd "$WORK_DIR"
curl -fsSL --retry 5 --retry-delay 5 "$URL" -o zed.tar.gz
tar -xzf zed.tar.gz

# Extracted directory is zed.app/
# bin/zed is the CLI wrapper; lib/zed/zed is the editor binary.
# The CLI wrapper resolves the editor via its own path, so both must stay together.
rm -rf /usr/lib/zed.app
mv zed.app /usr/lib/zed.app
ln -sf /usr/lib/zed.app/bin/zed /usr/bin/zed

# Desktop file
if [ -f /usr/lib/zed.app/share/applications/zed.desktop ]; then
    cp /usr/lib/zed.app/share/applications/zed.desktop /usr/share/applications/zed.desktop
    sed -i 's|^Exec=.*|Exec=zed %F|' /usr/share/applications/zed.desktop
fi

echo "Done: $(zed --version 2>&1 | head -1)"
