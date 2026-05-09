#!/usr/bin/env bash
# Installs a custom SELinux policy module allowing the display manager (xdm_t)
# to start/status systemd unit files.
set -euo pipefail

echo "Configuring SELinux for ly display manager (TEST RECIPE)..."

# 1. Ensure the ly binary is correctly labeled as a display manager exec
# This allows the process to transition to the xdm_t domain.
if [ -f /usr/bin/ly ]; then
    echo "Labeling /usr/bin/ly as xdm_exec_t..."
    semanage fcontext -a -t xdm_exec_t "/usr/bin/ly" || true
    restorecon -v /usr/bin/ly || true
fi

echo "Installing custom SELinux policy: xdm_t -> systemd_unit_file_t:service..."

dnf install -y checkpolicy policycoreutils 2>&1 | tail -5

WORK_DIR="$(mktemp -d)"
trap "rm -rf '$WORK_DIR'" EXIT

cat > "$WORK_DIR/niri_dm.te" << 'EOF'
module niri_dm 1.0;

require {
    type xdm_t;
    type systemd_unit_file_t;
    class service { start status };
}

allow xdm_t systemd_unit_file_t:service { start status };
EOF

checkmodule -M -m -o "$WORK_DIR/niri_dm.mod" "$WORK_DIR/niri_dm.te"
semodule_package -o "$WORK_DIR/niri_dm.pp" -m "$WORK_DIR/niri_dm.mod"

if semodule -i "$WORK_DIR/niri_dm.pp" 2>&1; then
    echo "SELinux policy installed via semodule."
else
    echo "WARNING: semodule failed (expected in some container builds)."
    echo "Falling back to semanage permissive for xdm_t..."
    # policycoreutils-python-utils is pre-installed by the recipe's build-toolchain block.
    if semanage permissive -a xdm_t 2>&1; then
        echo "xdm_t set to permissive mode."
    else
        echo "ERROR: Both semodule and semanage failed. SELinux policy not installed."
        echo "You may need to run 'sudo semanage permissive -a xdm_t' on the host after deployment."
        exit 1
    fi
fi
