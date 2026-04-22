#!/bin/bash
# 1. Select the folder
target=$(fd -H -t d . ~ | fzf --keep-right --reverse --border=rounded --info=inline \
  --bind "ctrl-y:execute-silent(realpath {} | tr -d '\n' | wl-copy)+abort")

# 2. Exit if cancelled
if [ -z "$target" ]; then
    exit 0
fi

# 3. Get the absolute path
fullpath=$(realpath "$target")

# 4. Open with Yazi in Kitty
setsid kitty --title yazi -e yazi "$fullpath" >/dev/null 2>&1 &

# 5. Wait for detach
sleep 0.2

exit 0
