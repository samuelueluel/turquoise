#!/bin/bash

set -ouex pipefail

echo "--- Explicitly triggering systemd-sysusers to create missing system users ---"
# Packages like rtkit provide sysusers.d configs but the users might not be 
# created automatically during the container build phase in some environments.
systemd-sysusers
