#!/usr/bin/env bash
# Installs the latest Lemonade Server (AMD NPU/GPU LLM inference) from the
# official Fedora 44 RPM on GitHub releases. Tracks the latest release so the
# image picks up new versions on each rebuild (like install-anythingllm.sh).
# Provides the `lemonade-server` CLI + systemd integration, used for the
# XDNA2 NPU path (Zed autocomplete + RAG embeddings) on Strix Halo.
set -euo pipefail

echo "Installing Lemonade Server (latest fc44 RPM)..."

API="https://api.github.com/repos/lemonade-sdk/lemonade/releases/latest"

# Resolve the Fedora 44 x86_64 RPM asset URL from the latest release.
RPM_URL="$(curl -fsSL --retry 5 --retry-delay 5 "$API" \
  | grep -oE '"browser_download_url"[[:space:]]*:[[:space:]]*"[^"]*fc44\.x86_64\.rpm"' \
  | grep -oE 'https[^"]*' \
  | head -n1)"

if [ -z "${RPM_URL:-}" ]; then
  echo "ERROR: no fc44 x86_64 RPM found in the latest Lemonade release." >&2
  echo "Upstream may have changed its asset naming; check ${API}." >&2
  exit 1
fi

echo "Found: ${RPM_URL}"
dnf install -y --setopt=install_weak_deps=False "${RPM_URL}"

echo "Lemonade Server installed: $(command -v lemonade-server || echo 'NOT on PATH')"
