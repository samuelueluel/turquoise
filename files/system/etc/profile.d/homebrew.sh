# Add Homebrew to PATH for all login shells and sourcing processes.
# This ensures tools installed via Homebrew (fd, rg, bat, eza, etc.) are
# available to all processes, including scripts with #!/usr/bin/env sh.
if [ -d "/home/linuxbrew/.linuxbrew/bin" ]; then
    eval "$(/home/linuxbrew/.linuxbrew/bin/brew shellenv)"
fi
