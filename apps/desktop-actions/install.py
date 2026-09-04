#!/usr/bin/python3
"""Merge four desktop commands into Ulauncher without replacing other shortcuts."""
import argparse
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import time

HERE = Path(__file__).resolve().parent
ACTIONS = [
    ('e4408353-bcd2-5b0e-95b8-171cb83719dc', 'Log Out', 'logout', 'logout.svg', '--logout'),
    ('d142d8bf-6082-5e8d-97ed-2421e4f8c7dc', 'Shut Down', 'shutdown', 'shutdown.svg', '--power-off'),
    ('4b8ba5b1-a538-574d-8af1-c3052bed48ba', 'Restart Machine', 'restart', 'restart.svg', '--reboot'),
    ('18430723-6826-595c-9d3e-dcd2fd59c2f9', 'Quit All Apps', 'quit all apps', 'quit-all.svg', None),
]


def merged_shortcuts(existing, destination):
    if not isinstance(existing, dict) or any(not isinstance(v, dict) for v in existing.values()):
        raise ValueError('Unexpected Ulauncher shortcuts format; existing file was not changed.')
    result = dict(existing)
    for identifier, name, keyword, icon, flag in ACTIONS:
        if any(v.get('keyword') == keyword and key != identifier for key, v in existing.items()):
            raise ValueError(f'An unrelated shortcut already uses {keyword!r}; rename it in Ulauncher first.')
        command = (f'exec /usr/bin/gnome-session-quit {flag} --no-prompt' if flag else
                   f'exec /usr/bin/python3 {shlex.quote(str(destination / "quit_all_apps.py"))}')
        result[identifier] = dict(id=identifier, name=name, keyword=keyword,
            cmd='#!/bin/sh\n' + command + '\n', icon=str(destination / 'icons' / icon),
            is_default_search=False, run_without_argument=True,
            added=existing.get(identifier, {}).get('added', time.time()))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    if os.getuid() == 0:
        parser.error('Run as your normal desktop user, without sudo.')
    destination = Path.home() / '.local/lib/desktop-actions'
    config = Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config')) / 'ulauncher/shortcuts.json'
    existing = json.loads(config.read_text()) if config.exists() else {}
    result = merged_shortcuts(existing, destination)
    if args.dry_run:
        print('Would install logout, shutdown, restart and quit all apps; preserve other shortcuts.')
        return
    running = subprocess.run(['pgrep', '-u', str(os.getuid()), '-x', 'ulauncher'], capture_output=True)
    if running.returncode == 0:
        parser.error('Quit Ulauncher from its tray menu first, so it cannot overwrite the merged shortcuts.')
    destination.mkdir(parents=True, exist_ok=True)
    shutil.copy2(HERE / 'quit_all_apps.py', destination / 'quit_all_apps.py')
    shutil.copytree(HERE / 'icons', destination / 'icons', dirs_exist_ok=True)
    config.parent.mkdir(parents=True, exist_ok=True)
    if config.exists():
        shutil.copy2(config, config.with_name(f'shortcuts-before-desktop-actions-{time.time_ns()}.json'))
    temporary = config.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(result, indent=2) + '\n')
    temporary.chmod(0o600)
    temporary.replace(config)
    print('Installed. Reopen Ulauncher to use the four commands. No session actions were executed.')


if __name__ == '__main__':
    main()
