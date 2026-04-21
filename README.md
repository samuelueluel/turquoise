Personal atomic image built with [BlueBuild](https://github.com/blue-build/) and based on the [Universal Blue main image](https://github.com/ublue-os/main). Uses the [niri compositor](https://github.com/niri-wm/niri). Opinionated. Work in progress. Not compatible with secure boot. Use at your own risk, especially if you have an NVIDIA GPU. 

If you are looking for a Universal Blue-type image using niri, it would be much easier to use [Wayblue](https://github.com/wayblueorg/wayblue) or [TunaOS](https://github.com/tuna-os/tunaOS).

Some but not all of my personal configuration/dotfiles are applied as system-wide defaults as a fallback for when user account config files are absent: niri, waybar, and fuzzel. I would suggest to test this image in a VM to familiarize yourself with the (perhaps idiosyncratic) custom keybinds before installing. However, some systems have issues with displaying niri in a VM. It has always given me errors and a black screen. Therefore, I would not try out this image unless you are already committed to installing or have already installed a Fedora Atomic / Universal Blue distrobution. In that case you can simply swap back to your old image if you don't like it or it breaks. You should figure out what that involves. If it were me, I would create a separate user account just for testing the new image to prevent any config file shenanigans.

One option is to install Fedora Silverblue, disable secure boot through UEFI, and then rebase to this image with

```bash
sudo bootc switch ghcr.io/samuelueluel/samuel-niri:latest
systemctl reboot
```

Note that CapsLock has been rebound to the Super/Mod/Start key and the physical Super/Mod/Start key has been rebound to Menu. The latter is recognized by niri as XF86MenuKB in the config file. Mod+/ brings up the keybind dashboard---you must read this closely or things will be unusable. I suggest you run

```bash
cp -r /etc/niri/ ~/.config/niri/
```

so that you can edit the keybinds to your liking at the copy destination. SETUP.md, setup-dotfiles.sh, and setup-waydroid.sh require access to private repos and should not be used. They are for my own use and reference.

The system updates in the background every night on a timer like other Universal Blue images. 

Much of this is written by Claude Code. However, I run this on my work and personal laptop, so I view it as stable. Things may need fixing upon new releases of Fedora and niri. I will try to fix them and keep this repo up to date. Feel free to file an issue here if you have a question or if something goes wrong. Use at your own risk, though.
