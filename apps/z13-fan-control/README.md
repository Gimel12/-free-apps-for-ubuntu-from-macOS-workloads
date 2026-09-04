# Z13 Fan Control

A native GTK 4 app for the ASUS ROG Flow Z13 (GZ302EAC), with a white and blue
interface, touch-friendly curve graph, live CPU/GPU temperatures and fan RPM,
separate eight-point CPU/GPU curves, and multiple named local profiles.

## Use

Open Ulauncher and type **Z13 Fan Control** (or run `z13-fan-control`).

- Select Quiet reading, Everyday, or Cool & steady in the sidebar.
- Drag graph points. Switch CPU/GPU to edit each fan independently.
- Expand **Exact temperature & fan values** for numeric controls or to copy a
  curve to the other fan.
- **New profile**, **Duplicate**, and the editable name field let you build your
  own collection. **Save profile** stores edits without touching the fans.
- **Apply profile** saves and activates the selected settings.
- **Automatic cooling** returns fan control to the firmware and releases the
  app's low-power limits.

Curves continue after closing the app. They return to automatic on suspend,
backend shutdown/restart, or a change of power profile. Reboot starts in automatic
mode; saved profiles remain available. The app does not start automatically.

Quiet reading includes optional light-task power limits: CPU boost off, 625 MHz
minimum / 2.2 GHz maximum CPU policy, Power Saver, and supported ASUS sustained /
slow / fast power limits of 28 / 32 / 45 W. It stops the existing manual Game Mode
service if installed. These are limits, not measured savings. Other curves leave
the current power profile alone after releasing Quiet Mode's limits.

Applying the built-in Quiet reading profile also updates the curve used by the
desktop Quiet Mode toggle. Save alone does not change the toggle's stored curve.
Turning Quiet Mode on always includes the low-power settings.

## Temperature behavior

The processor's [rated Tjmax is 100°C](https://www.amd.com/en/products/processors/laptop/ryzen/ai-300-series/amd-ryzen-ai-max-plus-395.html).
This app edits fan response; it does not modify processor thermal limits.
The final curve point stays at 95°C / 100% to leave a margin below Tjmax.
Backend validation requires increasing temperatures (2°C minimum separation),
nondecreasing fan duty, and at least 20% / 30% / 60% cooling at 80 / 85 / 90°C.
The firmware may override requests, enforce minimum RPM, or use hysteresis.
Requested percentages are fan duty values, not percentages of measured RPM.

Quiet reading requests 0% through 70°C, 20% at 80°C, 35% at 85°C,
65% at 90°C and full cooling at 95°C. This replaces the earlier full-speed point
at 85°C. Both temperature sources are monitored; losing one releases custom
control. Fan curves execute in the embedded controller rather than the app.

## Files and architecture

- App: `~/.local/share/z13-fan-control/`
- Profiles: `~/.config/z13-fan-control/profiles.json`
- Launcher: `~/.local/share/applications/com.bizon.Z13FanControl.desktop`
- Root-owned backend: `/usr/local/lib/bizon-fan-control/`
- D-Bus service: `com.bizon.FanControl`, systemd `bizon-fan-control.service`
- Applied Quiet preset: `/var/lib/bizon-fan-control/quiet-profile.json`
- Transient limit-restore state: `/run/bizon-quiet-mode/restore.json`

The GUI runs as the user. The restricted service accepts fixed actions and
validated curve data from root and the installed user's UID. It never accepts
arbitrary file paths, shell commands, or scripts from clients. Failed curve writes
return both fans to automatic. Edits use explicit Save/Apply with a prompt for
unsaved changes. Malformed profile files are preserved as recovery copies.

## Install on another compatible Z13

Ubuntu 24.04 / GNOME 46 and the ASUS custom-fan-curve / ASUS Armoury kernel
interfaces are required. This targets the GZ302EAC Ryzen AI Max+ hardware, not
every laptop sold under the Z13 name. The desktop Quick Settings extensions are
optional and separate from this app installer.

```sh
sudo apt install python3-gi python3-gi-cairo python3-cairo gir1.2-gtk-4.0 gir1.2-adw-1 power-profiles-daemon desktop-file-utils
/usr/bin/python3 install.py
```

Run these commands from this app directory. Use `--dry-run` to preview. The installer
checks the GZ302EAC model before writing files.

Run the installer as your normal user; it uses sudo only for the system backend.
Existing user profiles are preserved. Root service files are backed up before
replacement. Installing the backend restores automatic cooling.

## Validation

```sh
/usr/bin/python3 -m unittest discover -s . -p 'test_*.py' -v
```

Tests cover presets, unsafe/invalid input, independent fan programming, hardware
write failure recovery, and validation before hardware access. Live validation
on this Z13 covered profile activation through the GUI, CPU limit restoration,
firmware curve readback, persistence, and normal / narrow window layouts.
