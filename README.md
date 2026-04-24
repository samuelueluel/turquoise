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
- [AI Disclaimer](#ai-disclaimer)

---

## Image

| Category | Software |
|---|---|
| Compositor | Niri |
| Bar | Waybar |
| Display manager | greetd + gtkgreet |
| Shell | Zsh + Powerlevel10k + fzf-tab |
| Terminals | Alacritty (primary), Kitty (Yazi only) |
| Editor | Zed |
| Browsers | Zen, Helium |
| File manager | Yazi (in Kitty), Nemo (backup) |
| Kernel | [@kernel-vanilla/stable](https://copr.fedorainfracloud.org/coprs/g/kernel-vanilla/stable/) |
| CLI tools | Homebrew (see `sjust brew`) |
| Flatpaks | Codecs/theming essentials only (see `sjust flatpaks`) |
| Automatic updates | Daily system updates via `uupd`, applied on next reboot |

Essential system packages track the Fedora update cycle. Most everything else tracks the latest release. Philosophy: Flatpak for GUI apps, Distrobox for apps without Flatpaks or needing deep system access, Homebrew for CLI tools. Never layer with `rpm-ostree`.

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

After reaching the gtkgreet login screen, press **Super+\`** to open a terminal or **Super+Space** to open the app launcher. Use `nmtui` to configure WiFi if needed.

> [!TIP]
> **CapsLock** is rebound to Mod (Super/Start). The physical Mod key becomes Menu (`XF86MenuKB` in niri config). Press **Mod+/** for the keybind dashboard before doing anything else, or you will have no idea how to navigate the desktop.

### 3. Run sjust

System-wide default configs for niri, waybar, and fuzzel are baked in as fallbacks, active until user dotfiles are applied. Remaining user-level configuration is handled by `sjust`, a `just` wrapper. All configuration files and scripts it applies are included in the image, tracking my personal dotfiles repo.

| Recipe | Description |
|---|---|
| `sjust setup` | Runs everything below in sequence (except `sjust swap` and `sjust update`) |
| `sjust dirs` | Pre-creates `~/.ssh`, `~/.config`, `~/.npm-global`, etc. |
| `sjust chezmoi` | Deploys dotfiles snapshot from image → `~/dotfiles`, applies via chezmoi |
| `sjust zsh-plugins` | Clones Powerlevel10k and fzf-tab |
| `sjust zen` | Creates Zen profiles, restores settings from dotfiles, sets Helium as default browser |
| `sjust brew` | Sets up Homebrew permissions, installs Brewfile packages (including Claude Code and Gemini CLI), configures RTK |
| `sjust flatpaks` | Adds Flathub, installs Flatpaks, applies permission overrides |
| `sjust system` | Adds user to required groups, sets Zsh as default shell |
| `sjust swap` | Replaces default zRAM with a 16GB swap file on `/var` |
| `sjust update` | Manually triggers the automatic system update with additional housecleaning |

> [!IMPORTANT]
> **`sjust chezmoi` must run before `sjust brew` and `sjust zen`** — both depend on files chezmoi puts in place (`~/.Brewfile` and `~/dotfiles/zen/`). All other recipes are order-independent.

Log out and back in after setup to activate the new shell and Homebrew PATH.

---

## AI Disclaimer

I am not a software developer. Much of this code was written by Claude or ripped from other projects, but I repeat myself.
