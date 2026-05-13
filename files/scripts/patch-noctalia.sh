#!/usr/bin/env bash
# patch-noctalia.sh — customizes noctalia-shell Taskbar.qml
#   1. Focused-icon indicator: full square background instead of tiny bottom dot
#   2. Slightly larger spacing between taskbar icons
#
# Fails loudly if the upstream file shape changes (so build breaks
# instead of silently producing an unpatched image).

set -euxo pipefail

# RPM installs to /etc/xdg; rpm-ostree compose later moves it to /usr/etc.
# At build-script time the file is normally at /etc/xdg.
TASKBAR=""
for p in \
  /etc/xdg/quickshell/noctalia-shell/Modules/Bar/Widgets/Taskbar.qml \
  /usr/etc/xdg/quickshell/noctalia-shell/Modules/Bar/Widgets/Taskbar.qml \
  /usr/share/quickshell/noctalia-shell/Modules/Bar/Widgets/Taskbar.qml ; do
  if [ -f "$p" ]; then TASKBAR="$p"; break; fi
done

if [ -z "$TASKBAR" ]; then
  echo "ERROR: Taskbar.qml not found in any expected location" >&2
  exit 1
fi

echo "Patching: $TASKBAR"

python3 - "$TASKBAR" << 'PYEOF'
import sys, pathlib

path = pathlib.Path(sys.argv[1])
src = path.read_text()

# --- 1) Icon spacing: marginXXS (~2px) -> 14px -----------------
# Wider gap leaves breathing room next to the focused-icon highlight,
# which extends 4px beyond the icon on each side (see patch 2).
old_col = "columnSpacing: isVerticalBar ? 0 : Style.marginXXS"
new_col = "columnSpacing: isVerticalBar ? 0 : 14"
old_row = "rowSpacing: isVerticalBar ? Style.marginXXS : 0"
new_row = "rowSpacing: isVerticalBar ? 14 : 0"

for old, new in [(old_col, new_col), (old_row, new_row)]:
    if old not in src:
        sys.exit(f"ERROR: spacing anchor not found: {old!r}")
    src = src.replace(old, new, 1)

# --- 2) Focused-icon indicator: tiny bottom dot -> full background -------
old_geom = (
    "                    anchors.bottomMargin: -2\n"
    "                    anchors.bottom: parent.bottom\n"
    "                    anchors.horizontalCenter: parent.horizontalCenter\n"
    "                    width: Style.toOdd(root.itemSize * 0.25)\n"
    "                    height: 4"
)
new_geom = (
    "                    anchors.fill: parent\n"
    "                    anchors.leftMargin: -4\n"
    "                    anchors.rightMargin: -4\n"
    "                    z: -1"
)
if old_geom not in src:
    sys.exit("ERROR: iconBackground geometry block not matched verbatim")
src = src.replace(old_geom, new_geom, 1)

# Radius: was sized for the 4px dot; use a small rounded square instead.
old_rad = "radius: Math.min(Style.radiusXXS, width / 2)"
new_rad = "radius: Style.radiusS"
if old_rad not in src:
    sys.exit(f"ERROR: iconBackground radius line not found: {old_rad!r}")
src = src.replace(old_rad, new_rad, 1)

path.write_text(src)
print("Taskbar.qml patched OK")
PYEOF

echo "patch-noctalia.sh complete"
