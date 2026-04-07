#!/usr/bin/env bash
# Builds and installs nirius (nirius + niriusd binaries) from source.
# Terra is behind upstream; building directly from the tagged release tarball.
set -euo pipefail

VERSION="0.7.1"
TARBALL_URL="https://git.sr.ht/~tsdh/nirius/archive/nirius-${VERSION}.tar.gz"
BUILD_DIR="$(mktemp -d)"
trap "rm -rf '$BUILD_DIR'" EXIT

# Build-time deps (cargo, rust) are pre-installed by the recipe's build-toolchain block.

curl -sL "$TARBALL_URL" | tar -xz -C "$BUILD_DIR"

cd "$BUILD_DIR/nirius-nirius-${VERSION}"
cargo build --release

install -Dm755 target/release/nirius  /usr/bin/nirius
install -Dm755 target/release/niriusd /usr/bin/niriusd
