#!/usr/bin/env bash
# Builds and installs a patched niri_window_buttons waybar CFFI module.
# Patch: set_halign(Center) on the icon box when titles are hidden, so the
# focused-window highlight rectangle is correctly centered around the icon.
# Not packaged for Fedora; built from source (Rust).
set -euo pipefail

VERSION="0.4.1"
REPO_URL="https://github.com/adelmonte/niri_window_buttons"
BUILD_DIR="$(mktemp -d)"
trap "rm -rf '$BUILD_DIR'" EXIT

# Build-time deps (cargo, rust, gtk3-devel, glib2-devel) are pre-installed by the recipe's build-toolchain block.

git clone --depth=1 --branch "v${VERSION}" "$REPO_URL" "$BUILD_DIR/src"

# Patch: use niri-ipc matching the installed niri version.
# niri_window_buttons pins niri-ipc to the version current at release time,
# which breaks when niri updates and sends new IPC event variants that the
# old crate can't deserialize (e.g. CastsChanged added in niri 26.04).
# niri version is e.g. "26.04"; crates.io niri-ipc drops the leading zero → "26.4.0"
NIRI_RAW=$(niri --version | grep -oP '\d+\.\d+')
NIRI_IPC_VERSION=$(awk -F. '{printf "%s.%d.0\n", $1, $2}' <<< "$NIRI_RAW")
sed -i "s/^niri-ipc = \"=.*\"/niri-ipc = \"=${NIRI_IPC_VERSION}\"/" \
    "$BUILD_DIR/src/Cargo.toml"

# Patch: center icon layout box when window titles are hidden
sed -i \
    's/let layout_box = gtk::Box::new(Orientation::Horizontal, icon_gap);/let layout_box = gtk::Box::new(Orientation::Horizontal, icon_gap);\n        if !display_titles {\n            layout_box.set_halign(gtk::Align::Center);\n        }/' \
    "$BUILD_DIR/src/src/widget.rs"

cd "$BUILD_DIR/src"
cargo build --release

install -Dm755 target/release/libniri_window_buttons.so \
    /usr/lib/waybar/libniri_window_buttons.so
