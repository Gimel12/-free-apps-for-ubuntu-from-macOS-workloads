# Optional GNOME desktop controls

Our custom GNOME Shell **46** extensions, tested on Ubuntu 24.04 and the ASUS
ROG Flow Z13. They use GNOME internals and do not claim compatibility with other
Shell versions. The app installers do not install these controls automatically.

| Control | Behavior |
| --- | --- |
| Clock at Top Left | Workspace indicator first, then date/calendar; portrait panel spacing and tray allocation fix |
| Game Mode | Quick Settings switch for a Performance profile hold and Feral GameMode |
| Screen Keyboard | Manual keyboard button beside Wi-Fi/Bluetooth; automatic behavior when off |
| Adaptive Touch | Touch hides the pointer, enlarges controls and exposes a blue window-drag grip; mouse restores normal interaction |
| Fan Control (Z13) | Manual fan slider, readings, Automatic cooling, and shortcut to the curve editor |
| Quiet Mode (Z13) | Low-power settings and the saved Quiet reading fan curve |

## Install

Run as the desktop user inside a GNOME session:

```sh
sudo apt install python3-gi gnome-shell power-profiles-daemon gamemode
/usr/bin/python3 desktop/install.py --dry-run
/usr/bin/python3 desktop/install.py
```

For the Z13 fan and quiet controls, install [Z13 Fan Control](../apps/z13-fan-control/README.md)
first, then run:

```sh
/usr/bin/python3 desktop/install.py --z13-controls
```

Add `--workspace-shortcuts` to set Ctrl+Left/Right for switching virtual desktops.
This replaces those GNOME bindings and can take precedence over app text-navigation
shortcuts. The previous bindings are backed up. Existing unrelated extensions remain
enabled. New extensions may need a sign-out/sign-in; the installer never restarts
your session. Game Mode and Quiet Mode are not switched on by installation.

Copies of replaced extensions, the user service, enabled-extension list and any
changed bindings are saved under `~/.local/share/ubuntu-apps-desktop-backups/`.
Disable individual controls through GNOME Extensions, or run
`gnome-extensions disable UUID` using the directory name under `extensions/`.
Disabling a UI is not a substitute for turning off its active mode first: use
Automatic cooling for fan/quiet profiles and turn Game Mode off before removing it.

## Touch, rotation and other software

Adaptive Touch helps desktop interaction; scrolling and pinch-to-zoom still depend
on each app. The blue grip moves a window with a one-finger drag. Automatic rotation
uses GNOME/Mutter and the machine's sensor through `iio-sensor-proxy`; it is not a
separate app or bundled driver. Enable rotation in the desktop controls when supported.

Caffeine, Blur My Shell and Rounded Window Corners Reborn are third-party extensions
installed separately through [GNOME Extensions](https://extensions.gnome.org/).
They are not our code and are not copied into this repository. Steam, Slack, Spark,
game files, graphics drivers, system-wide package upgrades and device-specific
troubleshooting changes are likewise not bundled as apps.
