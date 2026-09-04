# Changes

## September 4, 2026

- Added **Z13 Fan Control**, the white-and-blue GTK 4 app with live CPU/GPU
  temperatures, fan RPM, power telemetry, independent curves and multiple profiles.
- Included the restricted D-Bus/systemd backend, reversible low-power settings,
  validated curves, recovery behavior and hardware-specific installer.
- Quiet reading uses a gentler curve: fan-off requested through 70°C and full
  cooling at 95°C. Hardware thermal limits are unchanged.
- Added portable **Desktop Actions** installation for Ulauncher: logout, shutdown,
  restart and graceful Quit All Apps, preserving unrelated shortcuts.
- Added six optional GNOME 46 extensions: clock/calendar layout, Game Mode,
  fan controls, Quiet Mode, screen keyboard and adaptive touch/window dragging.
- Included the Game Mode user service and optional Ctrl+Left/Right workspace bindings.
- Documented dependencies, hardware/session requirements, backups and update steps.

Notes and Snippets runtime files were compared with the installed copies. No new
application changes were missing; existing repository portability improvements
were retained. Personal libraries, shortcut history, screenshots and system logs
are excluded. Third-party installed software is referenced rather than copied.

The apps and extensions were exercised on the original Ubuntu 24.04 / GNOME 46
Z13. Packaging checks cover dry runs, syntax, shortcut merging and fan-curve
validation; deployment to a second physical Z13 has not yet been tested.
