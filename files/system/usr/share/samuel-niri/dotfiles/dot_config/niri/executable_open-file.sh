#!/bin/bash

# --- CONFIGURATION ---
# Your exact Vault folder path (No trailing slash)
VAULT_ROOT="$HOME/Dropbox/Sam_Personal_Vault"
# Your Vault Name (As shown in Obsidian) - usually the folder name
VAULT_NAME="Sam_Personal_Vault"
# ---------------------

# 1. Select the file
#target=$(fd -H -t f . ~ | fzf --keep-right --reverse --border=rounded --info=inline)
target=$(fd -H -t f . ~ | fzf --keep-right --reverse --border=rounded --info=inline \
  --bind "ctrl-y:execute-silent(realpath {} | tr -d '\n' | wl-copy)+abort")

# 2. Exit if cancelled
if [ -z "$target" ]; then
    exit 0
fi

# 3. Get the absolute path
fullpath=$(realpath "$target")

# 4. Smart Launch Logic
if [[ "$fullpath" == *.md ]]; then

    # Check if the file is inside your Vault
    if [[ "$fullpath" == "$VAULT_ROOT"* ]]; then
        # STRIP the vault path to get a Relative Path (e.g. "Folder/File.md")
        # We use substring replacement: ${var#pattern}
        relative_path="${fullpath#$VAULT_ROOT/}"

        # Encode the RELATIVE path
        encoded=$(python3 -c "import urllib.parse, sys; print(urllib.parse.quote(sys.argv[1]))" "$relative_path")

        # Use Advanced URI with the Vault Name + Relative Path + New Tab
        uri="obsidian://advanced-uri?vault=$VAULT_NAME&filepath=$encoded&openmode=tab"

        setsid xdg-open "$uri" >/dev/null 2>&1 &
    else
        # Fallback: File is a markdown file OUTSIDE the vault
        # We just open it with the standard system handler (might reuse tab)
        setsid xdg-open "$fullpath" >/dev/null 2>&1 &
    fi

else
    # Standard Open for non-markdown files
    setsid xdg-open "$fullpath" >/dev/null 2>&1 &
fi

# WAIT for the process to detach safely
sleep 0.2

# 5. Exit
exit 0
