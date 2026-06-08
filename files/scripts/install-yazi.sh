#!/usr/bin/env bash
# Downloads and installs the latest yazi binary from GitHub releases.
# yazi is not in Fedora repos; we use the pre-built musl static binary.
set -euo pipefail

ARCH="x86_64"
WORK_DIR="$(mktemp -d)"
trap "rm -rf '$WORK_DIR'" EXIT

VERSION=$(git ls-remote --tags --refs --sort='v:refname' https://github.com/sxyazi/yazi.git | tail -n1 | cut -d/ -f3)
TARBALL="yazi-${ARCH}-unknown-linux-musl.zip"
URL="https://github.com/sxyazi/yazi/releases/download/${VERSION}/${TARBALL}"

echo "Installing yazi ${VERSION}..."

cd "$WORK_DIR"
curl -fsSLo "$TARBALL" --retry 5 --retry-delay 5 "$URL"
unzip -q "$TARBALL"

EXTRACTED="yazi-${ARCH}-unknown-linux-musl"
# Must install to /usr/bin/, NOT /usr/local/bin/.
# On Fedora Atomic, /usr/local/ is a writable overlay (/var/usrlocal/)
# and would not be part of the immutable image.
install -Dm755 "${EXTRACTED}/yazi" /usr/bin/yazi
install -Dm755 "${EXTRACTED}/ya"   /usr/bin/ya

# Record version for the build manifest
echo "Yazi: ${VERSION}" >> /tmp/build-manifest.txt

echo "Done: $(yazi --version)"
