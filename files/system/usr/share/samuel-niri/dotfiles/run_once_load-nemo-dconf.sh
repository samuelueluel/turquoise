#!/usr/bin/env bash
# chezmoi run_once: loads nemo dconf settings on first apply.
# Re-runs if this file's content changes (chezmoi hashes it).

if command -v dconf &>/dev/null; then
    dconf load /org/nemo/ <<'DCONF'
[list-view]
enable-folder-expansion=false

[preferences]
quick-renames-with-pause-in-between=true
show-full-path-titles=true
show-hidden-files=true
show-location-entry=true

[window-state]
sidebar-bookmark-breakpoint=0
start-with-sidebar=true
DCONF
fi
