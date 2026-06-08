#!/usr/bin/env bash
# Builds and installs the latest bluetuith from source.
# bluetuith is not in Fedora repos or Homebrew; built with Go toolchain.
set -euo pipefail

WORK_DIR="$(mktemp -d)"
trap "rm -rf '$WORK_DIR'" EXIT

VERSION=$(git ls-remote --tags --refs --sort='v:refname' https://github.com/darkhz/bluetuith.git | tail -n1 | cut -d/ -f3)
echo "Building bluetuith ${VERSION}..."

cd "$WORK_DIR"
curl -fsSL --retry 5 --retry-delay 5 "https://github.com/darkhz/bluetuith/archive/refs/tags/${VERSION}.tar.gz" \
  | tar -xz
cd "bluetuith-${VERSION#v}"

go build -o bluetuith .

# Must install to /usr/bin/, NOT /usr/local/bin/.
# On Fedora Atomic, /usr/local/ is a writable overlay (/var/usrlocal/)
# and would not be part of the immutable image.
install -Dm755 bluetuith /usr/bin/bluetuith

echo "Done: bluetuith ${VERSION}"
