#!/usr/bin/env bash
# Downloads and installs the latest systemd-manager-tui binary from GitHub releases.
# systemd-manager-tui is not in Fedora repos.
set -euo pipefail

API_URL="https://api.github.com/repos/matheus-git/systemd-manager-tui/releases/latest"
WORK_DIR="$(mktemp -d)"
trap "rm -rf '$WORK_DIR'" EXIT

echo "Fetching latest systemd-manager-tui version..."
VERSION=$(curl -fsSL --retry 5 --retry-delay 5 "$API_URL" | grep '"tag_name"' | cut -d'"' -f4)
FILENAME="systemd-manager-tui"
URL="https://github.com/matheus-git/systemd-manager-tui/releases/download/${VERSION}/${FILENAME}"

echo "Installing systemd-manager-tui ${VERSION}..."

cd "$WORK_DIR"
curl -fsSLo "$FILENAME" --retry 5 --retry-delay 5 "$URL"

# Install to /usr/bin/ to ensure it is part of the immutable image
install -Dm755 "$FILENAME" /usr/bin/systemd-manager-tui

echo "Done: $(systemd-manager-tui --version)"
