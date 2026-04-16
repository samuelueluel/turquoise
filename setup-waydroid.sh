#!/usr/bin/env bash
# Post-reboot Waydroid setup for samuel-niri.
# Run once after first boot with Waydroid baked into the image:
#   bash ~/samuel-niri/setup-waydroid.sh
#
# What this does:
#   1. Initializes Waydroid with LineageOS + Google Apps (GAPPS)
#   2. Installs libndk ARM translation (required for most Android games)
#   3. Starts the container service
#   4. Prints Play Store device certification instructions

set -euo pipefail

# ── 1. Check not already initialized ─────────────────────────────────────────
if [[ -d /var/lib/waydroid/images ]]; then
    echo "Waydroid is already initialized."
    echo "To re-initialize from scratch: sudo waydroid init -s GAPPS -f"
    exit 0
fi

# ── 2. Initialize with GAPPS ──────────────────────────────────────────────────
echo "==> Initializing Waydroid with GAPPS (downloads ~1 GB)..."
sudo waydroid init \
    -c https://ota.waydro.id/system \
    -v https://ota.waydro.id/vendor \
    -s GAPPS -f

# ── 3. Install ARM translation (libndk) ──────────────────────────────────────
# Install before first container start so the image is patched from the outset.
# libndk: Google's ARM-to-x86 translator — required for most Play Store games.
echo "==> Installing libndk ARM translation via waydroid-script..."
TMPDIR="$(mktemp -d)"
trap 'rm -rf "$TMPDIR"' EXIT

curl -fsSL https://github.com/casualsnek/waydroid_script/archive/refs/heads/main.tar.gz \
    -o "$TMPDIR/waydroid_script.tar.gz"
tar -xz -C "$TMPDIR" -f "$TMPDIR/waydroid_script.tar.gz"
python3 -m venv "$TMPDIR/waydroid_script-main/venv"
"$TMPDIR/waydroid_script-main/venv/bin/pip" install --quiet \
    -r "$TMPDIR/waydroid_script-main/requirements.txt"
sudo "$TMPDIR/waydroid_script-main/venv/bin/python3" \
    "$TMPDIR/waydroid_script-main/main.py" install libndk

# ── 4. Start container service ────────────────────────────────────────────────
echo "==> Starting waydroid-container.service..."
sudo systemctl start waydroid-container.service

# ── 5. Print Play Store certification instructions ───────────────────────────
echo ""
echo "=========================================================="
echo " Waydroid is running. Final step: certify for Play Store."
echo "=========================================================="
echo ""
echo "1. Launch the Android UI:"
echo "     waydroid show-full-ui"
echo ""
echo "2. Once it's booted, get the device Android ID:"
echo "     sudo waydroid shell grep android_id \\"
echo "       /data/data/com.google.android.gsf/databases/gservices.db"
echo "   (The ID is the last column — a 16-digit hex number.)"
echo ""
echo "3. Register it at: https://www.google.com/android/uncertified"
echo "   Sign in with your Google account and paste the Android ID."
echo ""
echo "4. Wait a few minutes, then restart the container:"
echo "     sudo systemctl restart waydroid-container.service"
echo ""
echo "5. Open the Play Store in Waydroid and sign in."
