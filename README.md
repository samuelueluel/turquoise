Personal Fedora Atomic image built with [BlueBuild](https://github.com/blue-build/) on top of [Universal Blue's base-main](https://github.com/ublue-os/main/pkgs/container/base-main). Uses the [niri](https://github.com/niri-wm/niri) scrolling Wayland compositor.

> **Not intended for general use and work-in-progress.** This is a personal daily-driver image with opinionated configuration. Included packages are subject to frequent change. Not compatible with Secure Boot. If you want a Universal Blue-type image with niri, it would be safer and easier to use [Wayblue](https://github.com/wayblueorg/wayblue), [Zirconium](https://github.com/zirconium-dev/zirconium), or [TunaOS](https://github.com/tuna-os/tunaOS) instead. I assume I'm the only person that will ever use this, but if someone else does, you should let me know by filing an issue in this GitHub repository. We can talk and make sure I don't screw up your system with an update.

## Image

> The image always fails for me when I boot it in a VM due to niri breaking. If you try this in a VM and get black-screened, it is likely an issue with OpenGL acceleration.

- **Compositor:** Niri
- **Bar:** Waybar
- **Terminals:** Alacritty (primary), Kitty (only for Yazi)
- **Editor:** Zed
- **Browsers:** Zen, Helium
- **Shell:** Zsh + Powerlevel10k + fzf-tab
- **File manager:** Yazi (in Kitty), Nemo (backup)
- **Display manager:** greetd + gtkgreet
- **Kernel:** [@kernel-vanilla/stable](https://copr.fedorainfracloud.org/coprs/g/kernel-vanilla/stable/)
- **Homebrew** for user CLI tools; see `sjust brew` below
- **Flatpaks:** Only codec/theming essentials pre-installed; see `sjust flatpaks` below
- **Automatic system updates:** Everything on the system updates daily through `uupd`, available upon reboot

Essential system packages are usually pinned to the Fedora update cycle. Most of everything else tracks the latest release. You should follow the Universal Blue philosophy of using Flatpak for GUI applications, Distrobox for things without Flatpaks or that need deeper system access, and Homebrew for CLI tools. Never layer with rpm-ostree.

## Fresh install

### 1. Install Fedora Silverblue

- Filesystem: **XFS**
- Disable Secure Boot in UEFI (required---the kernel cannot be signed)

### 2. Rebase to this image

```bash
sudo bootc switch ghcr.io/samuelueluel/samuel-niri:latest
systemctl reboot
```

After getting through the gtkgreet login screen, press **Super+\`** to open a terminal or **Super+Space** to open the app launcher. Use `nmtui` if WiFi needs configuring.

> **CapsLock** is rebound to Mod (Super/Start). The physical Mod key becomes Menu (`XF86MenuKB` in niri config). Press **Mod+/** for the keybind dashboard before doing anything else.

### 3. Run sjust

System-wide default configs for niri, waybar, and fuzzel are baked in as fallbacks, active until user dotfiles are applied. Remaining user-level configuration is handled by `sjust`, a wrapper for `just`. All configuration files and scripts it applies are included in the image.

| Recipe | Description |
|---|---|
| `sjust setup` | Runs everything below in sequence, except sjust swap and sjust update |
| `sjust dirs` | Pre-creates `~/.ssh`, `~/.config`, `~/.npm-global`, etc. |
| `sjust chezmoi` | Deploys dotfiles snapshot from image → `~/dotfiles`, applies via chezmoi |
| `sjust zsh-plugins` | Clones Powerlevel10k and fzf-tab |
| `sjust zen` | Creates Zen profiles, restores settings from dotfiles, and sets Helium as default "light/utility" browser |
| `sjust brew` | Sets up Homebrew permissions, installs Brewfile packages including Claude Code and Gemini CLI, and configures RTK |
| `sjust flatpaks` | Adds Flathub, installs my Flatpaks, and applies permission overrides |
| `sjust system` | Adds user to all required groups, sets Zsh as default shell |
| `sjust swap` | Replaces default zRAM with a 16GB swap file on `/var` |
| `sjust update` | Manually runs the automatic system update with some additional housecleaning

When running recipes individually rather than via `sjust setup`, note that **`sjust chezmoi` must run before `sjust brew` and `sjust zen`** — both depend on files from `~/dotfiles` that chezmoi puts in place (`~/.Brewfile` and `~/dotfiles/zen/`). All other recipes are order-independent.

Log out and back in after setup to activate the new shell and Homebrew PATH.

> These settings are optimized for my 14 inch laptop and may not look great on a larger monitor.

## AI Disclaimer

I am not a software developer. Much of this code was written by Claude or ripped from other projects, but I repeat myself.
