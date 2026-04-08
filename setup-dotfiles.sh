#!/usr/bin/env bash
# First-run dotfiles setup for samuel-niri work laptop image.
# Run once after first login: bash ~/work-image/setup-dotfiles.sh
#
# Assumes: ~/dotfiles has been cloned (SSH key must be set up first).
# Assumes: ~/work-image (this repo) has been cloned.

set -euo pipefail

DOTFILES="$HOME/dotfiles"

# ── 1. Verify dotfiles repo is present ───────────────────────────────────────
if [[ ! -d "$DOTFILES/.git" ]]; then
    echo "ERROR: ~/dotfiles not found. Clone it first:"
    echo "  git clone git@github.com:samuelueluel/dotfiles.git ~/dotfiles"
    exit 1
fi

# ── 2. Configure chezmoi (reads .chezmoi.toml.tmpl from source dir) ──────────
chezmoi init --source="$HOME/dotfiles"

# ── 3. Pre-create directories chezmoi won't create on its own ────────────────
mkdir -p \
    ~/.local/bin \
    ~/.local/share/applications \
    ~/.local/share/zsh/plugins \
    ~/.config \
    ~/.gnome2/accels \
    ~/.claude \
    ~/.gemini \
    ~/.ssh \
    ~/.npm-global/bin

chmod 700 ~/.ssh

# ── 3.5. Install Zsh Plugins (Powerlevel10k, fzf-tab) ────────────────────────
echo "Installing external zsh plugins..."
if [[ ! -d ~/.local/share/zsh/plugins/powerlevel10k ]]; then
    git clone --depth=1 https://github.com/romkatv/powerlevel10k.git ~/.local/share/zsh/plugins/powerlevel10k
fi
if [[ ! -d ~/.local/share/zsh/plugins/fzf-tab ]]; then
    git clone --depth=1 https://github.com/Aloxaf/fzf-tab ~/.local/share/zsh/plugins/fzf-tab
fi

# ── 4. Apply dotfiles ─────────────────────────────────────────────────────────
echo "Applying dotfiles via chezmoi..."
chezmoi apply --force

# ── 4.5. Clean up conflicting Vivaldi generated desktop files ────────────────
rm -f ~/.local/share/applications/com.vivaldi.Vivaldi.*.desktop || true

# ── 4.6. Copy Vivaldi Preferences ────────────────────────────────────────────
if [[ -d "$HOME/system_config_git/vivaldi" ]]; then
    echo "Copying Vivaldi preferences..."

    mkdir -p ~/.config/vivaldi-casual/Default
    cp ~/system_config_git/vivaldi/casual/Preferences      ~/.config/vivaldi-casual/Default/ 2>/dev/null || true
    cp ~/system_config_git/vivaldi/casual/contextmenu.json ~/.config/vivaldi-casual/Default/ 2>/dev/null || true

    mkdir -p ~/.config/vivaldi-work/Default
    cp ~/system_config_git/vivaldi/work/Preferences        ~/.config/vivaldi-work/Default/ 2>/dev/null || true
    cp ~/system_config_git/vivaldi/work/contextmenu.json   ~/.config/vivaldi-work/Default/ 2>/dev/null || true

    mkdir -p ~/.config/vivaldi-llm/Default
    cp ~/system_config_git/vivaldi/llm/Preferences         ~/.config/vivaldi-llm/Default/ 2>/dev/null || true
    cp ~/system_config_git/vivaldi/llm/contextmenu.json    ~/.config/vivaldi-llm/Default/ 2>/dev/null || true
fi

# ── 4.7. Restore Claude and Gemini settings ──────────────────────────────────
if [[ -d "$HOME/system_config_git/claude-code" ]]; then
    echo "Restoring Claude Code settings..."
    mkdir -p ~/.claude
    cp ~/system_config_git/claude-code/.claude/settings.json ~/.claude/settings.json 2>/dev/null || true
fi
if [[ -d "$HOME/system_config_git/gemini-cli" ]]; then
    echo "Restoring Gemini CLI settings..."
    mkdir -p ~/.gemini
    cp ~/system_config_git/gemini-cli/.gemini/settings.json ~/.gemini/settings.json 2>/dev/null || true
fi

# ── 5. Fix Homebrew Installation & Install Packages (Host) ───────────────
echo "Fixing Homebrew installation (requires password)..."
# Force extraction of Homebrew to /home on atomic desktops
sudo rm -f /etc/.linuxbrew
sudo systemctl start brew-setup.service || true

# Fix ownership of Homebrew
sudo chown -R "$(whoami):$(id -g)" /home/linuxbrew

echo "Installing Homebrew packages..."
# Make sure brew is available in this subshell
eval "$(/home/linuxbrew/.linuxbrew/bin/brew shellenv)"

# Install gcc and make for isolated developer toolchain
brew install gcc make

# Install gemini-cli
brew install gemini-cli

# Install claude-code
brew install claude-code@latest

# Install ouch (not in Fedora/Terra repos)
brew install ouch

# Install rtk and initialize hooks
brew install rtk
rtk init -g --yes || true
rtk init -g --gemini --yes || true

# ── 6. Refresh desktop file MIME database ────────────────────────────────────
update-desktop-database ~/.local/share/applications/ 2>/dev/null || true

# ── 7. Set zsh as default shell ──────────────────────────────────────────────
ZSH_PATH="$(command -v zsh)"
if [[ "$SHELL" != "$ZSH_PATH" ]]; then
    echo "Setting zsh as default shell (requires password)..."
    sudo usermod -s "$ZSH_PATH" "$(whoami)"
fi

# ── 8. Flatpak Overrides (Theme Access) ──────────────────────────────────────
echo "Applying Flatpak overrides for Quod Libet and pwvucontrol theme access..."
# gtk-3.0: Quod Libet needs access to gtk.css + noctalia.css for GTK3 theming
flatpak override --user --filesystem=xdg-config/gtk-3.0:ro io.github.quodlibet.QuodLibet || true

# gtk-4.0: pwvucontrol needs access to gtk.css + noctalia.css for libadwaita color overrides
flatpak override --user --filesystem=xdg-config/gtk-4.0:ro com.saivert.pwvucontrol || true

echo ""
echo "Done. If shell was changed, log out and back in for it to take effect."
echo ""
echo "Manual steps may still be needed:"
echo "  - Wallpapers — cp -r ~/system_config_git/Wallpapers ~/Pictures/Wallpapers"
echo "  - Dropbox — sign in"
echo "  - EasyEffects — presets are applied; open the app to confirm they loaded"
