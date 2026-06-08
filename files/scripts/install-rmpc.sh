#!/usr/bin/env bash
# Downloads and installs the latest rmpc binary from GitHub releases.
# rmpc is not in Fedora repos; we use the pre-built musl static binary.
set -euo pipefail

ARCH="x86_64"
WORK_DIR="$(mktemp -d)"
trap "rm -rf '$WORK_DIR'" EXIT

VERSION=$(git ls-remote --tags --refs --sort='v:refname' https://github.com/mierak/rmpc.git | tail -n1 | cut -d/ -f3)
TARBALL="rmpc-${VERSION}-${ARCH}-unknown-linux-musl.tar.gz"
URL="https://github.com/mierak/rmpc/releases/download/${VERSION}/${TARBALL}"

echo "Installing rmpc ${VERSION}..."

cd "$WORK_DIR"
curl -fsSLo "$TARBALL" --retry 5 --retry-delay 5 "$URL"
tar -xzf "$TARBALL"

# Must install to /usr/bin/, NOT /usr/local/bin/.
# On Fedora Atomic, /usr/local/ is a writable overlay (/var/usrlocal/)
# and would not be part of the immutable image.
install -Dm755 rmpc /usr/bin/rmpc

echo "Done: $(rmpc --version)"
