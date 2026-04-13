# First-Time Setup Guide

Complete walkthrough from a fresh Fedora Silverblue install to a fully working **samuel-niri** system.

!! If someone besides me ever reads this: obviously all this may not apply to you. !!

---

## 1. Pre-Flight Checklist (Before You Wipe)

Save your SSH keys to Bitwarden as secure notes to ensure you can clone your private repositories on the new system.

```bash
cat ~/.ssh/id_ed25519      # Copy this → Bitwarden secure note: "SSH Private Key"
cat ~/.ssh/id_ed25519.pub  # Copy this → Bitwarden secure note: "SSH Public Key"
```

Include the full content, including header and footer lines for the private key. You'll retrieve these from bitwarden.com on first boot using Zen Browser, which is baked into the image.

---

## 2. OS Installation (Fedora Silverblue)

During the Fedora Silverblue installer (Anaconda):
- **Filesystem:** Choose **XFS**.
- **User Account:** Set username to **`samuel`** (crucial, as Niri/Chezmoi configs have hardcoded `/home/samuel/` paths).
- **Network:** Connect to WiFi during install (the profile persists to the installed system).

---

## 3. Image Rebase

After the first boot into stock Silverblue GNOME, open a terminal and rebase to the custom image.

```bash
rpm-ostree rebase ostree-unverified-registry:ghcr.io/samuelueluel/samuel-niri:latest
systemctl reboot
```

This pulls the full image (~3–5 GB). After reboot, you will land at the **tuigreet** login screen, which starts **Niri**.

---

## 4. Initial Environment Setup

Niri starts with built-in defaults until dotfiles are applied.
- **Terminal:** Press **`Super+T`** to open Alacritty.
- **WiFi:** If not connected, run `nmtui`.
- **File browsing:** Use **Nemo** for any file browsing at this stage. Yazi depends on Homebrew CLI tools (`fd`, `rg`, `bat`, `eza`) that aren't available until step 6, so search and previews won't work correctly beforehand.

### Restore SSH Keys
Open Zen Browser (already in the image), log into Bitwarden, and restore your keys:

```bash
mkdir -p ~/.ssh && chmod 700 ~/.ssh

# Paste private key content (include header/footer lines):
nano ~/.ssh/id_ed25519
chmod 600 ~/.ssh/id_ed25519

# Paste public key content:
nano ~/.ssh/id_ed25519.pub
chmod 644 ~/.ssh/id_ed25519.pub

# Verify connection
ssh -T git@github.com
```

---

## 5. Repository Cloning

Clone the three core repositories that define the system.

```bash
git clone git@github.com:samuelueluel/samuel-niri.git ~/samuel-niri
git clone git@github.com:samuelueluel/dotfiles.git ~/dotfiles
git clone git@github.com:samuelueluel/system_config_git.git ~/system_config_git
```

---

## 6. Automated Configuration

Run the setup script to automate the bulk of the user-level configuration.

```bash
bash ~/samuel-niri/setup-dotfiles.sh
```

**What this script handles:**
- **Dotfiles:** Deploys via `chezmoi apply`.
- **Zsh:** Installs Powerlevel10k/fzf-tab and sets Zsh as the default shell.
- **Zen Browser:** Creates Personal, Utility, and Work profiles and restores settings from `system_config_git/zen/`.
- **Dev Tools:** Installs Homebrew packages from `~/.Brewfile` (CLI tools: bat, eza, ripgrep, lazygit, etc.), plus GCC, Gemini CLI, Claude Code, `rtk`, and `bbrew`.
- **Theming:** Applies Flatpak overrides for theme access.

**Log out and back in** to activate the new shell and environment settings. This is required for Homebrew to be injected into the systemd user session PATH. Note that Yazi search (`fd`, `rg`, fzf plugins) relies on Homebrew tools; to ensure these are always available regardless of how it's launched, the Niri keybinds wrap Yazi in a shell command (`zsh -c 'exec yazi'`).

---

## 7. Manual Polish & Authentication

### Application Authentication
```bash
claude   # browser-based login
gemini   # browser OAuth
dropbox start -i  # sign in via tray
```

### Zen Browser — Manual Steps
Settings, keybindings, and mods are restored automatically by the setup script. Extensions must be installed manually in each profile:
- **uBlock Origin** — `https://addons.mozilla.org/en-US/firefox/addon/ublock-origin/`
- Any other extensions you use

Toolbar button positions are already set in `user.js` and will snap into place once the extensions are installed.

### Manual Config Restoration
Some application data is too large or specific for Chezmoi/automation:

- **Wallpapers:**
  ```bash
  cp -r ~/system_config_git/Wallpapers ~/Pictures/Wallpapers
  ```
- **Okular (Flatpak) PROBABLY DONT DO THIS:**
  ```bash
  # Launch once to create sandbox, then copy config
  flatpak run org.kde.okular & sleep 2 && kill $!
  mkdir -p ~/.var/app/org.kde.okular/config
  cp ~/system_config_git/okular/.config/okularrc ~/.var/app/org.kde.okular/config/okularrc
  ```
- **EasyEffects:** Open the app to confirm presets (applied by Chezmoi) have loaded correctly.

---

## 8. System Reference: Noctalia Theme

**Noctalia** is the custom system-wide color palette. It is applied per-application via Chezmoi-managed config files.

| Component | Config Location |
|---|---|
| **GTK 3/4** | `~/.config/gtk-x.0/gtk.css` (imports `noctalia.css`) |
| **Alacritty** | `~/.config/alacritty/themes/noctalia.toml` |
| **Kitty** | `~/.config/kitty/kitty.conf` |
| **Zed** | `~/.config/zed/themes/noctalia.json` |
| **Qt 5/6** | `~/.config/qtXct/colors/noctalia.conf` |
| **Claude Code** | Uses `dark-ansi` (inherits terminal palette) |
| **Gemini CLI** | Hand-crafted `AlacrittyCompatible` theme |

**Flatpaks:** If a new GTK Flatpak is added, it needs permission to read the theme files:
```bash
flatpak override --user --filesystem=xdg-config/gtk-3.0:ro <app-id>
```
Once verified, add the override to `setup-dotfiles.sh`.

Qt/KDE Flatpaks are much more annoying. Use kvantum?
