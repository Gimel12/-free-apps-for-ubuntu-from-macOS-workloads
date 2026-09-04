#!/usr/bin/python3
"""Install optional local GNOME 46 extensions without restarting the desktop."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

HERE = Path(__file__).resolve().parent
GENERAL = ['clock-top-left@local', 'game-mode-toggle@local', 'screen-keyboard@local', 'adaptive-touch@local']
Z13 = ['fan-control@local', 'quiet-mode@local']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--z13-controls', action='store_true', help='Also install fan and Quiet Mode controls; requires Z13 Fan Control backend')
    parser.add_argument('--workspace-shortcuts', action='store_true', help='Use Ctrl+Left/Right to switch workspaces')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    if os.getuid() == 0:
        parser.error('Run as your desktop user, without sudo.')
    names = GENERAL + (Z13 if args.z13_controls else [])
    if args.dry_run:
        print('Would install:', ', '.join(names))
        print('Would install the Game Mode user service and enable extensions for next login.')
        if args.workspace_shortcuts:
            print('Would back up and set Ctrl+Left/Right workspace shortcuts.')
        return
    version = subprocess.check_output(['/usr/bin/gnome-shell', '--version'], text=True).strip()
    if not version.startswith('GNOME Shell 46.') and version != 'GNOME Shell 46':
        parser.error('These extensions target GNOME Shell 46. No files were changed.')
    for executable in ('powerprofilesctl', 'gamemoded'):
        if not Path('/usr/bin', executable).exists():
            parser.error('Install power-profiles-daemon and gamemode first; see desktop/README.md.')
    if args.z13_controls and not Path('/usr/local/lib/bizon-fan-control/curves.py').exists():
        parser.error('Install apps/z13-fan-control first to provide the fan and Quiet Mode backend.')
    import gi
    from gi.repository import Gio
    settings = Gio.Settings.new('org.gnome.shell')
    enabled = settings.get_strv('enabled-extensions')
    backup = Path.home() / '.local/share/ubuntu-apps-desktop-backups' / str(time.time_ns())
    backup.mkdir(parents=True)
    (backup / 'enabled-extensions.json').write_text(json.dumps(enabled, indent=2))
    extensions = Path.home() / '.local/share/gnome-shell/extensions'
    extensions.mkdir(parents=True, exist_ok=True)
    for name in names:
        target = extensions / name
        if target.exists():
            shutil.copytree(target, backup / name)
        shutil.copytree(HERE / 'extensions' / name, target, dirs_exist_ok=True)
    units = Path.home() / '.config/systemd/user'
    units.mkdir(parents=True, exist_ok=True)
    unit = units / 'bizon-game-mode.service'
    if unit.exists():
        shutil.copy2(unit, backup / unit.name)
    shutil.copy2(HERE / 'systemd/bizon-game-mode.service', unit)
    subprocess.run(['/usr/bin/systemctl', '--user', 'daemon-reload'], check=True)
    settings.set_strv('enabled-extensions', list(dict.fromkeys(enabled + names)))
    if args.workspace_shortcuts:
        keys = Gio.Settings.new('org.gnome.desktop.wm.keybindings')
        previous = {key: keys.get_strv(key) for key in ('switch-to-workspace-left', 'switch-to-workspace-right')}
        (backup / 'workspace-shortcuts.json').write_text(json.dumps(previous, indent=2))
        keys.set_strv('switch-to-workspace-left', ['<Control>Left'])
        keys.set_strv('switch-to-workspace-right', ['<Control>Right'])
    Gio.Settings.sync()
    print('Installed. Sign out and back in when convenient to load newly discovered extensions.')
    print('Game Mode and Quiet Mode are not activated by this installer. Backups:', backup)


if __name__ == '__main__':
    main()
