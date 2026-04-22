Personal atomic Fedora image built with [BlueBuild](https://github.com/blue-build/) on top of [Universal Blue's base-main](https://github.com/ublue-os/main/pkgs/container/base-main). Uses the [niri](https://github.com/niri-wm/niri) scrolling Wayland compositor.

> **Not intended for general use.** This is a personal daily-driver image — opinionated, occasionally broken during transitions, and not compatible with Secure Boot. If you want a niri-based Universal Blue image, see [Wayblue](https://github.com/wayblueorg/wayblue), [Zirconium](https://github.com/zirconium-dev/zirconium), or [TunaOS](https://github.com/tuna-os/tunaOS) instead.

## What's in the image

- **Compositor:** Niri (from [yalter/niri](https://copr.fedorainfracloud.org/coprs/yalter/niri/) COPR)
- **Bar:** Waybar with custom Niri IPC modules
- **Terminals:** Alacritty (primary), Kitty (for Yazi previews)
- **Editor:** Zed
- **Browsers:** Zen Browser (3 profiles: personal/utility/work), Helium
- **Shell:** Zsh + Powerlevel10k + fzf-tab
- **File manager:** Yazi (in Kitty), Nemo (backup)
- **Display manager:** greetd + gtkgreet
- **Kernel:** `@kernel-vanilla/stable` upstream stable
- **Homebrew** framework pre-installed for user CLI tools
- **Flatpaks:** Obsidian, Bitwarden, LibreOffice, EasyEffects, Quod Libet, QGIS, and others

System-wide default configs for niri, waybar, and fuzzel are baked in as fallbacks, active until user dotfiles are applied.

## Fresh install

### 1. Install Fedora Silverblue

- Filesystem: **XFS**
- Disable Secure Boot in BIOS (required — the vanilla kernel cannot be signed)

### 2. Rebase to this image

```bash
bootc switch ghcr.io/samuelueluel/samuel-niri:latest
systemctl reboot
```

After reboot you land at the gtkgreet login screen. Press **Super+`** to open a terminal or **Super+Space** to open the app launcher. Use `nmtui` if WiFi needs configuring.

> **CapsLock** is rebound to Super. The physical Super key becomes Menu (`XF86MenuKB` in niri config). Press **Mod+/** for the keybind dashboard before doing anything else.

### 3. Run sjust setup

All user-level configuration is handled by `sjust`, a setup command runner baked into the image. No repo cloning or SSH keys required to get a working system.

```bash
sjust setup
```

This runs the following steps in order — each can also be run individually:

| Recipe | What it does |
|---|---|
| `sjust dirs` | Pre-creates `~/.ssh`, `~/.claude`, `~/.config`, etc. |
| `sjust chezmoi` | Deploys dotfiles snapshot from image → `~/dotfiles`, applies via chezmoi |
| `sjust zsh-plugins` | Clones Powerlevel10k and fzf-tab |
| `sjust zen` | Creates Zen Browser profiles, restores settings and themes, generates launchers |
| `sjust claude-gemini` | Restores Claude Code and Gemini CLI settings |
| `sjust brew` | Fixes Homebrew, runs `brew bundle`, installs rtk and bbrew |
| `sjust flatpaks` | Applies Flatpak permission overrides for GTK theming |
| `sjust system` | Adds user to libvirt group, sets Zsh as default shell |
| `sjust swap` | Replaces default zRAM with a 16GB swap file on `/var` |

Log out and back in after setup to activate the new shell and Homebrew PATH.
