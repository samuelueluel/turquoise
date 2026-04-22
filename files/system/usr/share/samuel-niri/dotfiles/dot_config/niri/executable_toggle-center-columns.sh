#!/bin/bash
CONFIG="$HOME/.config/niri/config.kdl"

if rg -q '^    center-focused-column "always"' "$CONFIG"; then
    sed -i '/^    center-focused-column "always"/s/"always"/"never"/' "$CONFIG"
else
    sed -i '/^    center-focused-column "never"/s/"never"/"always"/' "$CONFIG"
fi
