#!/usr/bin/env bash
# Ensure modules.dep exists for the installed vanilla kernel immediately after
# the kernel-vanilla/stable swap. This prevents subsequent dnf transactions
# (which execute kernel %posttrans scriptlets / dracut) from failing with:
# "dracut[F]: /usr/lib/modules/<KVER>/modules.dep is missing."
set -euo pipefail

KVER="$(rpm -q --qf '%{VERSION}-%{RELEASE}.%{ARCH}\n' kernel-core | sort -V | tail -1)"

# Fail the build if the swap silently left the stock Fedora kernel in place
# (happened on F45 when the from-repo pointed only at the empty stable copr).
if [[ "$(rpm -q kernel-core | grep -c vanilla)" -eq 0 || "$(rpm -q kernel-core | grep -vc vanilla)" -ne 0 ]]; then
    echo "ERROR: kernel-core is not (only) a kernel-vanilla build:" >&2
    rpm -q kernel-core >&2
    exit 1
fi

echo ">>> Pre-generating module dependencies (depmod -a) for kernel ${KVER}..."
depmod -a "${KVER}" || true
