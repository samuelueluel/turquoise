# samuel-niri

[![Build](https://github.com/samuelueluel/samuel-niri/actions/workflows/build.yml/badge.svg)](https://github.com/samuelueluel/samuel-niri/actions/workflows/build.yml)

Personal Fedora Atomic image built with [BlueBuild](https://github.com/blue-build/) on top of [Universal Blue's base-main](https://github.com/ublue-os/main/pkgs/container/base-main), using the [niri](https://github.com/niri-wm/niri) scrolling Wayland compositor.

> [!WARNING]
> **Not intended for general use.** This is a personal daily-driver image with opinionated configuration. Packages are subject to frequent change. Secure Boot is not supported. If you want a Universal Blue-type image with niri, consider [Wayblue](https://github.com/wayblueorg/wayblue), [Zirconium](https://github.com/zirconium-dev/zirconium), or [TunaOS](https://github.com/tuna-os/tunaOS) instead. If you do use this, file an issue so that we can talk and make sure I don't randomly change things on your system.

---

## Contents

- [Image](#image)
- [Fresh Install](#fresh-install)
  - [1. Install Fedora Silverblue](#1-install-fedora-silverblue)
  - [2. Rebase to this image](#2-rebase-to-this-image)
  - [3. Run sjust](#3-run-sjust)
- [Keybinds](#keybinds)
- [AI Disclaimer](#ai-disclaimer)

---

## Packages in image

Not exhaustive.

| Category | Software |
|---|---|
| Compositor | Niri |
| Bar | Waybar |
| App launcher | fsel |
| Display manager | greetd + gtkgreet |
| Shell | zsh + powerlevel10k + fzf-tab |
| Terminals | Alacritty (primary), Kitty (utility terminal for image previews) |
| Editor | Zed |
| Browsers | Zen, Helium |
| File manager | Yazi (launched in Kitty), Nemo (backup) |
| Music | rmpc + MPD |
| Cloud storage | Dropbox |
| Kernel | [@kernel-vanilla/stable](https://copr.fedorainfracloud.org/coprs/g/kernel-vanilla/stable/) |
| CLI tools | See `sjust brew` |
| Flatpaks | See `sjust flatpaks` |
| Automation | Daily image + Flatpak + Homebrew + Distrobox updates via `uupd`, random wallpaper on login, trash and clipboard history emptied on boot |

Essential system packages track the Fedora update cycle. Most everything else tracks the latest release.

> [!NOTE]
> VM installs may black-screen due to niri's OpenGL acceleration requirement.

---

## Fresh Install

### 1. Install Fedora Silverblue

- Filesystem: **XFS** 
- Disable Secure Boot in UEFI (the kernel cannot be signed)

### 2. Rebase to this image

```bash
sudo bootc switch ghcr.io/samuelueluel/samuel-niri:latest
systemctl reboot
```
After booting into the new image, press **Mod+\`** to open a terminal or **Mod+Space** to open the app launcher. Use `nmtui` to configure WiFi if needed.

> [!IMPORTANT]
> **CapsLock** is rebound to Mod (Super/Start). The physical Mod key becomes Menu (`XF86MenuKB` in niri config). Press **Mod+/** for the niri keybind dashboard before doing anything else, or you will have no idea how to navigate the desktop. App-specific keybinds are found in their config files and below.

### 3. Run sjust

System-wide default configs for niri and waybar are baked in as fallbacks, active until user dotfiles are applied. Optional user-level configuration is handled by `sjust`. All configuration files and scripts it applies are included in the image, tracking my personal [dotfiles repo](https://github.com/samuelueluel/dotfiles).

> [!IMPORTANT]
> This assumes a fresh install. If you rebase from something else carrying your home folders with you, then you need to make sure all dotfiles and wallpapers are backed up. `sjust chezmoi`, and therefore `sjust setup`, may overwrite them. Of course, you don't need to run any of the `sjust` commands if you don't want to.

| Recipe | Description |
|---|---|
| `sjust setup` | Runs everything below in sequence (except `sjust swap` and `sjust update`) |
| `sjust dirs` | Pre-creates `~/.ssh`, `~/.config`, etc. |
| `sjust zen` | Registers Zen profiles and creates `.desktop` launchers; sets Helium as default "light/utility" browser |
| `sjust chezmoi` | Deploys dotfiles snapshot from image → `~/dotfiles`, applies via chezmoi (includes Zen Browser config) |
| `sjust zen-extensions` | Installs Zen Browser extensions (AMO + custom XPIs) into each profile; run after chezmoi |
| `sjust zsh-plugins` | Clones powerlevel10k and fzf-tab |
| `sjust brew` | Sets up Homebrew permissions, installs Brewfile packages, and installs non-Brewfile things like bbrew |
| `sjust flatpaks` | Adds Flathub, installs Flatpaks, applies permission overrides for theming|
| `sjust system` | Adds user to required groups, sets zsh as default shell |
| `sjust swap` | Replaces default zRAM with a 16GB swap file on `/var` |
| `sjust update` | Manually triggers the automatic system update with additional housecleaning |

> [!IMPORTANT]
> `sjust chezmoi` must run before `sjust brew` because brew depends on `~/.Brewfile` that chezmoi puts in place. `sjust zen` and `sjust zen-extensions` are both optional. If you run them, you must run `sjust zen` before `sjust chezmoi`, and then run `sjust zen-extensions` after `sjust chezmoi`.
> `sjust` recipes not listed in this README but present in the justfile are not for general use---they will fail harmlessly due to lacking SSH access to private repos.

Log out and back in after setup to activate the new shell and Homebrew PATH.

---

## App-specific Keybinds

**CapsLock is Mod.** Press **Mod+/** for the full niri keybind dashboard.

An **Alt+WASD** navigation scheme is used across apps (up/down/left/right). Many default keybinds are remapped or disabled accordingly. Below is not exhaustive.

### Alacritty

| Key | Action |
|---|---|
| Alt+W / S | Scroll up / down one line |
| Alt+A / D | Jump backward / forward one word |
| Ctrl+W | Delete previous character |
| Ctrl+Q | Delete previous word |
| Alt+Q / E | Jump to beginning / end of line |
| Shift+Enter | New line |
| Ctrl+Shift+C / V | Copy / Paste |

### Yazi

Yazi is launched by Mod+E as a floating Kitty window that closes after selection. Use Mod+Ctrl+E for a permanent window.

| Key | Action |
|---|---|
| Alt+W / S | Cursor up / down |
| Alt+A / D | Parent directory / open |
| Alt+1–9 | Switch to tab 1–9 |
| Ctrl+T / Q | New tab / close tab |
| Ctrl+F | Fuzzy jump to file |
| Ctrl+G | Fuzzy jump to folder |
| Ctrl+H | Grep to file |
| Ctrl+J | Filter |
| Ctrl+K | Zoxide |
| Ctrl+N / B | Fuzzy search Obsidian notes / grep note content and open in Obsidian |
| Ctrl+A | Create file or folder |
| Ctrl+E | Rename |
| Ctrl+Delete | Trash file |
| Ctrl+Shift+C / X / V | Copy / cut / paste |
| Ctrl+Shift+P | Copy path of item to clipboard |
| Ctrl+P | Visual mode |
| Ctrl+. | Toggle hidden files |
| Ctrl+R | Reload |

### Zed

| Key | Action |
|---|---|
| Alt+W / S / A / D | Move cursor up / down / left / right |
| Ctrl+Space | Command palette |
| Ctrl+Q | Delete previous word (editor); close active item/pane (elsewhere) |
| Ctrl+W | Backspace (editor); close active item/pane (elsewhere) |
| Alt+Q / E | Jump to beginning / end of line |
| Alt+Tab / Shift+Tab | Tab switcher forward / select last |
| Ctrl+R | Reload file |

### Zen Browser

This assumes the full `sjust` sequence has been run and extensions enabled.

| Key | Action |
|---|---|
| Alt+W / S | Move up / down tab list (custom extension) |
| Alt+A / D | Next / previous workspace |
| Ctrl+Space | Command palette |
| Ctrl+T / Q | New tab / close tab |
| Ctrl+Shift+Q | Open last closed tab |
| Alt+Tab | Last recently focused tab (custom extension) |
| Ctrl+R | Refresh |

---

## AI Disclaimer

I am not a software developer. Much of this code was written by Claude or ripped from other projects, but I repeat myself.
