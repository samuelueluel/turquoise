#!/usr/bin/env bash
# Builds and installs nirius (nirius + niriusd binaries) from source.
# Terra is behind upstream; building directly from the tagged release tarball.
set -euo pipefail

VERSION=$(git ls-remote --tags https://git.sr.ht/~tsdh/nirius \
  | grep 'refs/tags/nirius-[0-9]' \
  | grep -v '\^{}' \
  | sed 's|.*refs/tags/nirius-||' \
  | sort -V | tail -1)
TARBALL_URL="https://git.sr.ht/~tsdh/nirius/archive/nirius-${VERSION}.tar.gz"
BUILD_DIR="$(mktemp -d)"
trap "rm -rf '$BUILD_DIR'" EXIT

# Build-time deps (cargo, rust) are pre-installed by the recipe's build-toolchain block.

curl -fsSL --retry 3 --retry-delay 5 "$TARBALL_URL" | tar -xz -C "$BUILD_DIR"

cd "$BUILD_DIR/nirius-nirius-${VERSION}"
cargo build --release

install -Dm755 target/release/nirius  /usr/bin/nirius
install -Dm755 target/release/niriusd /usr/bin/niriusd
