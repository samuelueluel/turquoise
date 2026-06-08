#!/usr/bin/env bash
# Installs the latest Lemonade Server (AMD NPU/GPU LLM inference) from the
# official Fedora 44 RPM on GitHub releases. Tracks the latest release so the
# image picks up new versions on each rebuild (like install-anythingllm.sh).
# Provides the `lemonade-server` CLI + systemd integration, used for the
# XDNA2 NPU path (Zed autocomplete + RAG embeddings) on Strix Halo.
set -euo pipefail

echo "Installing Lemonade Server (latest fc44 RPM)..."

VERSION=$(git ls-remote --tags --refs --sort='v:refname' https://github.com/lemonade-sdk/lemonade.git | tail -n1 | cut -d/ -f3)
RPM_URL="https://github.com/lemonade-sdk/lemonade/releases/download/${VERSION}/lemonade-server-${VERSION#v}-fc44.x86_64.rpm"

if ! curl -fsSLI --retry 5 --retry-delay 5 "$RPM_URL" > /dev/null; then
  echo "ERROR: no fc44 x86_64 RPM found at ${RPM_URL}." >&2
  echo "Upstream may have changed its asset naming; check https://github.com/lemonade-sdk/lemonade/releases/latest" >&2
  exit 1
fi

echo "Found: ${RPM_URL}"
dnf install -y --setopt=install_weak_deps=False "${RPM_URL}"

echo "Lemonade Server installed: $(command -v lemonade-server || echo 'NOT on PATH')"
