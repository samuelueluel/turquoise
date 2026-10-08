#!/usr/bin/env bash
# Builds and installs mmdr (mermaid-rs-renderer) from source.
# Pure-Rust Mermaid renderer used by the Claude Code figures plugin; not in
# Fedora or Homebrew, and mermaid-cli needs a headless Chrome download.
set -euo pipefail

for attempt in 1 2 3; do
  VERSION=$(git ls-remote --tags https://github.com/1jehuang/mermaid-rs-renderer \
    | grep 'refs/tags/v[0-9]' \
    | grep -v '\^{}' \
    | sed 's|.*refs/tags/v||' \
    | sort -V | tail -1) && break
  [[ $attempt -lt 3 ]] && sleep 5
done
[[ -n "${VERSION:-}" ]] || { echo "Failed to resolve mmdr version after 3 attempts"; exit 1; }
TARBALL_URL="https://github.com/1jehuang/mermaid-rs-renderer/archive/refs/tags/v${VERSION}.tar.gz"
BUILD_DIR="$(mktemp -d)"
trap "rm -rf '$BUILD_DIR'" EXIT

# Build-time deps (cargo, rust) are pre-installed by the recipe's build-toolchain block.

curl -fsSL --retry 3 --retry-delay 5 "$TARBALL_URL" | tar -xz -C "$BUILD_DIR"

cd "$BUILD_DIR/mermaid-rs-renderer-${VERSION}"
CARGO_NET_RETRY=5 cargo build --release --locked --bin mmdr

# Install directly to /usr/bin/ (required for immutable atomic images)
install -Dm755 target/release/mmdr /usr/bin/mmdr

echo "mmdr ${VERSION} installed successfully."
