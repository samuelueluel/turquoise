#!/usr/bin/env bash
# First-run dotfiles setup for samuel-niri work laptop image.
# Run once after first login: bash ~/samuel-niri/setup-dotfiles.sh
#
# Assumes: ~/dotfiles has been cloned (SSH key must be set up first).
# Assumes: ~/samuel-niri (this repo) has been cloned.

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

# ── 4.6. Create Zen Browser Profiles & Launchers ────────────────────────────
if command -v zen-browser &> /dev/null; then
    echo "Creating Zen Browser profiles..."
    # Use explicit paths so we know exactly where to restore settings.
    # Syntax: -CreateProfile "name /absolute/path"
    ZEN_DIR="$HOME/.config/zen"
    zen-browser -CreateProfile "personal $ZEN_DIR/zen.personal" 2>/dev/null || true
    zen-browser -CreateProfile "utility $ZEN_DIR/zen.utility"  2>/dev/null || true
    zen-browser -CreateProfile "work $ZEN_DIR/zen.work"        2>/dev/null || true

    # ── Restore settings to all profiles ─────────────────────────────────────
    if [[ -d "$HOME/system_config_git/zen/personal" ]]; then
        echo "Restoring Zen profile settings..."
        SRC="$HOME/system_config_git/zen/personal"
        for profile in zen.personal zen.utility zen.work; do
            DEST="$ZEN_DIR/$profile"
            mkdir -p "$DEST/chrome"
            cp "$SRC/user.js"                    "$DEST/" 2>/dev/null || true
            cp "$SRC/zen-keyboard-shortcuts.json" "$DEST/" 2>/dev/null || true
            cp "$SRC/zen-themes.json"             "$DEST/" 2>/dev/null || true
            cp "$SRC/chrome/zen-themes.css"       "$DEST/chrome/" 2>/dev/null || true
            cp -r "$SRC/chrome/zen-themes"        "$DEST/chrome/" 2>/dev/null || true
        done
    fi

    echo "Generating Zen Browser launchers..."
    declare -A ICONS=( ["personal"]="a7xpg" ["utility"]="braindump" ["work"]="applications-office" )
    for profile in personal utility work; do
        NAME="Zen (${profile^})"
        ICON="${ICONS[$profile]}"
        FILE="$HOME/.local/share/applications/zen-${profile}.desktop"

        cat <<EOF > "$FILE"
[Desktop Entry]
Name=$NAME
Comment=Launch Zen Browser with the ${profile^} profile
Exec=env MOZ_APP_REMOTINGNAME=zen-$profile zen-browser --profile "\$ZEN_DIR/zen.$profile" %u
Icon=$ICON
Terminal=false
Type=Application
Categories=Network;WebBrowser;
StartupWMClass=zen-$profile
MimeType=x-scheme-handler/unknown;x-scheme-handler/about;x-scheme-handler/https;x-scheme-handler/http;text/html;
EOF
        chmod +x "$FILE"
    done

    echo "Setting Zen Utility as default web browser..."
    xdg-settings set default-web-browser zen-utility.desktop 2>/dev/null || true
    for mime in x-scheme-handler/http x-scheme-handler/https text/html application/xhtml+xml application/x-extension-html application/x-extension-shtml application/x-extension-xhtml x-scheme-handler/about x-scheme-handler/unknown; do
        xdg-mime default zen-utility.desktop "$mime" 2>/dev/null || true
    done
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

# Install CLI tools from ~/.Brewfile (created by chezmoi apply above)
brew bundle --global

# Install gcc and make for isolated developer toolchain
brew install gcc make


# Install rtk and initialize hooks
brew install rtk
rtk init -g --yes || true
rtk init -g --gemini --yes || true

# Install bbrew (Bold Brew) — Homebrew TUI manager
# Installed via binary release because the tap requires building from source,
# which fails on atomic images without system-level compilers.
BBREW_VERSION=$(curl -fsSL https://api.github.com/repos/Valkyrie00/bold-brew/releases/latest | grep '"tag_name"' | cut -d'"' -f4 | tr -d 'v')
curl -L "https://github.com/Valkyrie00/bold-brew/releases/download/v${BBREW_VERSION}/bbrew_${BBREW_VERSION}_linux_amd64.tar.gz" \
    | tar -xz -C /tmp \
    && mv /tmp/bbrew "$(brew --prefix)/bin/bbrew"

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
