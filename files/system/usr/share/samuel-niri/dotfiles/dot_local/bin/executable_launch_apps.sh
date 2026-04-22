#!/bin/bash

# Launch Zen Personal
env MOZ_APP_REMOTINGNAME=zen-personal zen-browser -P "personal" --new-instance &

# Give it a second to start
sleep 2

# Launch Helium
helium &

# Give it a second to start
sleep 2

# Launch Quod Libet
flatpak run io.github.quodlibet.QuodLibet &

# Launch Alacritty
alacritty &
