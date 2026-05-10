# samuel-niri

[![Build](https://github.com/samuelueluel/samuel-niri/actions/workflows/build.yml/badge.svg)](https://github.com/samuelueluel/samuel-niri/actions/workflows/build.yml)

Personal Fedora Atomic image built with [BlueBuild](https://github.com/blue-build/) on top of [Universal Blue's base-main](https://github.com/ublue-os/main/pkgs/container/base-main), using the [niri](https://github.com/niri-wm/niri) compositor.

> [!WARNING]
> **Not intended for general use. Unstable.** This is a personal daily-driver image with opinionated configuration. Packages are subject to frequent change. Secure Boot is not supported. If you want a Universal Blue-type image with niri, use [Wayblue](https://github.com/wayblueorg/wayblue), [Zirconium](https://github.com/zirconium-dev/zirconium), or [TunaOS](https://github.com/tuna-os/tunaOS) instead. If you do use this, file an issue so that we can talk and make sure I don't randomly change things on your system. But just use something else.

---

## Image

| Category | Software |
|---|---|
| Compositor | niri |
| Bar | waybar |
| Dedicated launcher and search | television (see `sjust brew`; fsel is pre-brew backup) |
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
| Automation | Daily image + Flatpak + Homebrew + Distrobox updates via uupd, random wallpaper on login, trash and clipboard history emptied on boot |

---

## Configuration

System-wide default configs for niri and waybar are baked in as fallbacks, active until user dotfiles are applied. Optional user-level configuration is handled by `sjust`. All configuration files and scripts it applies are included in the image, tracking my personal [dotfiles repo](https://github.com/samuelueluel/dotfiles). This means `sjust` changes over time.

> [!IMPORTANT]
> `sjust` is meant for fresh installs without existing dotfiles. Beware of accidently overwriting your files.

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
| `sjust swap` | Replaces default zRAM with a 16GB swap file on `/var` |
| `sjust update` | Manually triggers the automatic system update with additional housecleaning |
| `sjust obsidian-cli` | Sets up the Obsidian CLI wrapper |
| `sjust obsidian-vault` | Configures the Obsidian vault name and path for television search |

> [!IMPORTANT]
> `sjust chezmoi` must run before `sjust brew` because brew depends on `~/.Brewfile` that chezmoi puts in place. `sjust zen` and `sjust zen-extensions` are both optional. If you run them, you must run `sjust zen` before `sjust chezmoi`, and then run `sjust zen-extensions` after `sjust chezmoi`.
> `sjust` recipes not listed in this README but present in the justfile should never be used.

Log out and back in after setup to activate the new shell and Homebrew PATH.

---

## Keybinds

> [!IMPORTANT]
> **CapsLock** is rebound to Mod (Super/Start). The physical Mod key becomes Menu (`XF86MenuKB` in niri config). **Alt+Space** is rebound to Enter, though Enter still works. After running `sjust brew`, television will be installed with a channel dedicated to niri keybinds, accessible with **Mod+Space**. App-specific keybinds are found in their config files and below.

The following are applied by `sjust`. Keybinds tend to fall into a left-hand cluster, for example, **Alt+WASD** for moving the cursor. Below is not exhaustive. 

### Ghostty

| Key | Action |
|---|---|
| Alt+W / S | Up / down arrow |
| Alt+A / D | Jump backward / forward one word |
| Ctrl+W | Delete previous character |
| Ctrl+Q | Delete previous word |
| Alt+Q / E | Jump to start / end of line |
| Shift+Enter | New line |
| Ctrl+C | Copy when text selected, else SIGINT |
| Ctrl+V | Paste |

### Yazi

Yazi is launched by Mod+E as a floating Kitty window that closes after selection. Use Mod+Ctrl+E for a permanent window. Kitty itself has most keybinds no-op'd to not conflict with custom TUI keybinds.

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
| Ctrl+C / X / V | Copy / cut / paste |
| Ctrl+P | Copy path of item to clipboard |
| Ctrl+Shift+P | Visual mode |
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
| Alt+Q / E | Back / forward in tab history|
| Ctrl+Space | Command palette |
| Ctrl+T / Q | New tab / close tab |
| Ctrl+Shift+Q | Open last closed tab |
| Alt+Tab | Last recently focused tab (custom extension) |
| Ctrl+R | Refresh |

---

## AI Disclaimer

I am not a software developer. Much of this code was written by Claude or ripped from other projects, but I repeat myself.
