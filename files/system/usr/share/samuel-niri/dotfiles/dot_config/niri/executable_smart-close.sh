#!/bin/bash

# 1. Check if fuzzel is running
if pgrep -x "fuzzel" > /dev/null; then
    pkill -x "fuzzel"
    exit 0
fi

# 2. Otherwise, tell niri to close the window
niri msg action close-window
