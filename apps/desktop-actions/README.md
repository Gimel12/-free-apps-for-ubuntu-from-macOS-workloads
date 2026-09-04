# Ulauncher desktop actions

Type one of these phrases into Ulauncher and press Enter on its result:

| Phrase | Action |
|---|---|
| `logout` | Log out through GNOME Session Manager |
| `shutdown` | Shut down through GNOME Session Manager |
| `restart` | Restart through GNOME Session Manager |
| `quit all apps` | Request normal closure of app windows on all workspaces |

The power/session commands use `gnome-session-quit --no-prompt`, without
`--force`, so existing session inhibitors are respected. They execute when
selected; they are not run as part of installation verification.

Quit All Apps uses the window manager's `_NET_CLOSE_WINDOW` protocol and never
kills processes. Unsaved-work dialogs can keep an app open until you respond.
Desktop components, Ulauncher, and background services are excluded. Apps
configured to minimize to the system tray can continue running there; this
action closes their windows rather than forcibly terminating them.

The close command supports the machine's current X11 session. It refuses to
operate on a future Wayland session rather than silently handling only some apps.

Read-only preview:

```sh
/usr/bin/python3 ~/.local/lib/desktop-actions/quit_all_apps.py --dry-run
```

To remove these commands, delete the four entries from Ulauncher Preferences
→ Shortcuts. The installer preserves unrelated shortcuts and backs up the existing configuration in the Ulauncher configuration directory.

## Install on another Ubuntu desktop

Install Ulauncher separately first. Quit it from the tray before installing so
it cannot overwrite the updated shortcut file, then reopen it afterward.

```sh
sudo apt install python3-xlib libnotify-bin gnome-session-bin
/usr/bin/python3 apps/desktop-actions/install.py --dry-run
/usr/bin/python3 apps/desktop-actions/install.py
```

The installer merges only the four named commands, preserves unrelated shortcuts,
and refuses keyword collisions. It never logs out, shuts down or closes apps as
part of installation. Quit All Apps requires X11; the other commands use GNOME.
