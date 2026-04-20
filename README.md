Personal atomic image built with [BlueBuild](https://github.com/blue-build/) and based on the [Universal Blue main image](https://github.com/ublue-os/main). Uses the [niri compositor](https://github.com/niri-wm/niri). Opinionated. Work in progress.

Some but not all of my personal configuration/dotfiles are applied upon install, namely, niri + waybar + fuzzel. To verify that things work, and to familiarize yourself with the (perhaps idiosyncratic) custom keybinds before installing, you should boot into Fedora Silverblue on a VM and then rebase to this image with

```bash
bootc switch ghcr.io/samuelueluel/samuel-niri:latest
systemctl reboot
```

Note that CapsLock has been rebound to the Super/Mod/Start key and the physical Super/Mod/Start key has been rebound to Menu. The latter is recognized by niri as XF86MenuKB in the config file. Mod+/ brings up the keybind dashboard. I suggest you edit niri's config.kdl to your liking and then track it with chezmoi and GitHub. The system updates in the background every night on a timer like other Universal Blue images. 

SETUP.md, setup-dotfiles.sh, and setup-waydroid.sh require access to private repos and should not be used. They are for my own use and reference.

Much of this code is written by Claude Code. However, I run this on my work and personal laptop, so I view it as stable. Things may need fixing upon new releases of Fedora and niri. I will try to fix them and keep this repo up to date. Feel free to file an issue here if you have a question or if something goes wrong. Use at your own risk, though.
