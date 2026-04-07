#!/usr/bin/env bash
# Builds and installs nwg-look from source.
# dustee071/unstable-apps COPR does not publish Fedora 43 builds.
set -euo pipefail

WORK_DIR="$(mktemp -d)"
trap "rm -rf '$WORK_DIR'" EXIT

# Build-time deps (golang, make, glib2-devel, gtk3-devel) are pre-installed by the recipe's build-toolchain block.

git clone --depth=1 https://github.com/nwg-piotr/nwg-look.git "$WORK_DIR/nwg-look"
cd "$WORK_DIR/nwg-look"

make build
make install

echo "nwg-look installed."
