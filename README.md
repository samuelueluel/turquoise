# Turquoise

[![Build](https://github.com/samuelueluel/turquoise/actions/workflows/build.yml/badge.svg)](https://github.com/samuelueluel/turquoise/actions/workflows/build.yml)

Personal Fedora Atomic image built with [BlueBuild](https://github.com/blue-build/) on top of [Universal Blue's base-main](https://github.com/ublue-os/main/pkgs/container/base-main), using the [niri](https://github.com/niri-wm/niri) compositor and [Noctalia desktop shell](https://github.com/noctalia-dev/noctalia-shell).

> [!WARNING]
> **Not intended for general use. Unstable.** This is a personal daily-driver image with opinionated configuration. Packages are subject to frequent change. Secure Boot is not supported. If you want a Universal Blue-type image with niri, use [Wayblue](https://github.com/wayblueorg/wayblue), [Zirconium](https://github.com/zirconium-dev/zirconium), or [TunaOS](https://github.com/tuna-os/tunaOS) instead. If you do use this, file an issue so that we can talk and make sure I don't randomly change things on your system. But just use something else. Minimal effort has been made to make this usable for others.

---

## Image

| Category | Software |
|---|---|
| Compositor | niri |
| Desktop shell | noctalia |
| Dedicated launcher and search | tv/television (see `sjust brew`) |
| Display manager | greetd + gtkgreet |
| Shell | zsh + starship (see `sjust brew` and `sjust system`)|
| Terminals | ghostty (primary), kitty (lobatimized for TUIs)|
| Editor | zed |
| Browsers | zen, helium |
| File manager | yazi, nemo |
| Music | rmpc + mpd |
| Cloud storage | Dropbox |
| Kernel | [@kernel-vanilla/stable](https://copr.fedorainfracloud.org/coprs/g/kernel-vanilla/stable/) |
| CLI tools | `sjust brew` |
| Flatpaks | `sjust flatpaks` |
| Automation | Daily image + Flatpak + Homebrew + Distrobox updates via uupd, trash and clipboard history emptied on boot |

---

## Configuration

My config for niri is active until user config is applied. Optional configuration is handled by `sjust`. All configuration files and scripts it applies are included in the image, tracking my personal [dotfiles repo](https://github.com/samuelueluel/dotfiles). This means `sjust` changes over time.

> [!IMPORTANT]
> Fresh installs can navigate to ghostty through the Noctalia launcher button or Mod+Grave keybind.  
> CapsLock is rebound to Mod (Super/Start). The physical Mod key becomes Menu (`XF86MenuKB` in niri config). Alt+Space is rebound to Enter. 
> `sjust` is meant for fresh installs without existing dotfiles. Beware of accidently overwriting your files.
> After running `sjust brew`, tv/television will be installed with a channel dedicated to niri keybinds, accessible with Mod+Space. Running `sjust chezmoi` introduces many idiosyncratic, app-specific keybinds that are found in their config files. 

`sjust` recipes not listed in this README but present in the justfile should never be used. 

| Recipe | Description |
|---|---|
| `sjust setup` | Runs everything below in sequence (except `sjust swap` and `sjust update`) |
| `sjust dirs` | Pre-creates `~/.ssh`, `~/.config`, etc. |
| `sjust zen` | Registers Zen profiles (Personal, Utility, Work) and creates `.desktop` launchers; sets Zen-Utility as default browser |
| `sjust chezmoi` | Deploys dotfiles snapshot from image to `~/dotfiles`, applies via chezmoi (includes Zen Browser config) |
| `sjust zen-extensions` | Installs Zen Browser extensions (AMO + custom XPIs) into each profile; run after chezmoi |
| `sjust brew` | Sets up Homebrew permissions, installs Brewfile packages, and installs non-Brewfile things like bbrew |
| `sjust flatpaks` | Adds Flathub, installs Flatpaks, applies permission overrides for theming |
| `sjust system` | Adds user to required groups, sets zsh as default shell |
| `sjust update` | Manually triggers the automatic system update with additional housecleaning |
| `sjust obsidian-cli` | Sets up the Obsidian CLI wrapper |
| `sjust obsidian-vault` | Configures the Obsidian vault name and path for tv/television search |

Log out and back in after setup to activate the new shell and Homebrew PATH.

---

## AI Disclaimer

I am not a software developer. Much of this code was written by Claude or ripped from other projects, but I repeat myself.
