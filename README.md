Personal atomic Fedora image built with [BlueBuild](https://github.com/blue-build/) on top of [Universal Blue's base-main](https://github.com/ublue-os/main/pkgs/container/base-main). Uses the [niri](https://github.com/niri-wm/niri) scrolling Wayland compositor.

> **Not intended for general use and work-in-progress.** This is a personal daily-driver image with opinionated configuration. Included packages are subject to frequent change. Not compatible with Secure Boot. If you want a Universal Blue-type image with niri, it would be safer and easier to use [Wayblue](https://github.com/wayblueorg/wayblue), [Zirconium](https://github.com/zirconium-dev/zirconium), or [TunaOS](https://github.com/tuna-os/tunaOS) instead. I assume I'm the only person that will ever use this, but if someone else does, you should let me know by filing an issue in this GitHub repository. We can talk and make sure I don't screw up your system with an update.

## Image

- **Compositor:** Niri (from [yalter/niri](https://copr.fedorainfracloud.org/coprs/yalter/niri/) COPR)
- **Bar:** Waybar with custom Niri IPC modules
- **Terminals:** Alacritty (primary), Kitty (only for Yazi)
- **Editor:** Zed
- **Browsers:** Zen Browser, Helium
- **Shell:** Zsh + Powerlevel10k + fzf-tab
- **File manager:** Yazi (in Kitty), Nemo (backup)
- **Display manager:** greetd + gtkgreet
- **Kernel:** `@kernel-vanilla/stable` upstream stable
- **Homebrew** framework pre-installed for user CLI tools
- **Flatpaks:** Things I use
- **System updates:** Everything on the system updates daily through `uupd`, available upon reboot

System-wide default configs for niri, waybar, and fuzzel are baked in as fallbacks, active until user dotfiles are applied.

> The image always fails for me when I boot it in a VM due to niri having issues, even though it works on a real system. If you try this in a VM and get black-screened, it is probably a VM-niri problem. Not sure how to fix it.

## Fresh install

### 1. Install Fedora Silverblue

- Filesystem: **XFS**
- Disable Secure Boot in UEFI (required — the vanilla kernel cannot be signed)

### 2. Rebase to this image

```bash
bootc switch ghcr.io/samuelueluel/samuel-niri:latest
systemctl reboot
```

After reboot you land at the gtkgreet login screen. Press **Super+\`** to open a terminal or **Super+Space** to open the app launcher. Use `nmtui` if WiFi needs configuring.

> **CapsLock** is rebound to Super. The physical Super key becomes Menu (`XF86MenuKB` in niri config). Press **Mod+/** for the keybind dashboard before doing anything else.

### 3. Run sjust setup

All initial user-level configuration is handled by `sjust`, a wrapper for `just`. All configuration files and scripts it applies is included in the image.

| Recipe | What it does |
|---|---|
| `sjust setup` | Runs everything below in sequence |
| `sjust dirs` | Pre-creates `~/.ssh`, `~/.claude`, `~/.config`, etc. |
| `sjust chezmoi` | Deploys dotfiles snapshot from image → `~/dotfiles`, applies via chezmoi |
| `sjust zsh-plugins` | Clones Powerlevel10k and fzf-tab |
| `sjust zen` | Creates Zen Browser profiles, restores settings and themes, generates launchers |
| `sjust claude-gemini` | Restores Claude Code and Gemini CLI settings |
| `sjust brew` | Fixes Homebrew and runs `brew bundle`, installing common CLI tools |
| `sjust flatpaks` | Applies Flatpak permission overrides for GTK theming |
| `sjust system` | Adds user to libvirt group, sets Zsh as default shell |
| `sjust swap` | Replaces default zRAM with a 16GB swap file on `/var` |

Log out and back in after setup to activate the new shell and Homebrew PATH.

## AI Disclaimer

I am not a software developer. Much of this code was written by Claude or ripped from other projects, but I repeat myself.
