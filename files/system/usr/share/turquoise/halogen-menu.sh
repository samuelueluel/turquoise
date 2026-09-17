#!/usr/bin/env bash
# Interactive gum chooser for the standalone Peonist Halogen service's vision
# mode. Resolves the choice and execs halogen-update.sh, which remains the
# single writer of the container: the menu never touches podman state itself.
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UPDATE_SCRIPT="$SCRIPT_DIR/halogen-update.sh"

fail() {
  echo "halogen-menu: $*" >&2
  exit 1
}

[[ -x "$UPDATE_SCRIPT" ]] || fail "updater not found: $UPDATE_SCRIPT"
command -v gum >/dev/null 2>&1 || fail "gum not found"
command -v podman >/dev/null 2>&1 || fail "podman not found"

mode="not deployed"
state="absent"
if podman container exists halogen >/dev/null 2>&1; then
  state=$(podman inspect halogen --format '{{.State.Status}}')
  if podman inspect halogen --format '{{range .Config.Env}}{{println .}}{{end}}' |
    grep -q '^HALOGEN_VISION_TOWER='; then
    mode="vision"
  else
    mode="text-only"
  fi
fi

choice=$(gum choose --header "halogen-flash-server · current: ${mode} (${state})" \
  "vision on" "text-only") || exit 0

case "$choice" in
  "vision on")
    # Unset so halogen-update.sh applies its own pinned default tower path.
    exec env -u HALOGEN_VISION_TOWER "$UPDATE_SCRIPT"
    ;;
  "text-only")
    # Empty, not unset: the updater omits the env entirely for text-only.
    exec env HALOGEN_VISION_TOWER= "$UPDATE_SCRIPT"
    ;;
esac
