#!/usr/bin/env python3
"""Read-only checks for an installed Ubuntu apps setup."""
import os
from pathlib import Path
import shutil
import subprocess

home = Path.home()
data = Path(os.environ.get('XDG_DATA_HOME', str(home / '.local/share')))
print('Session:', os.environ.get('XDG_SESSION_TYPE', 'unknown'))
if os.environ.get('XDG_SESSION_TYPE') == 'wayland':
    print('Global snippet expansion requires X11; choose Ubuntu on Xorg at login.')
for command in ('python3', 'xdotool', 'autokey-gtk'):
    print(command + ':', shutil.which(command) or 'not installed')
for path in (home / '.local/bin/notes', home / '.local/bin/bizon-snippets',
             data / 'applications/com.bizon.Notes.desktop',
             home / '.local/share/applications/com.bizon.Snippets.desktop'):
    print(path.name + ':', 'present' if path.exists() else 'not installed')
python = data / 'blue-notes/venv/bin/python'
if python.exists():
    result = subprocess.run([str(python), '-c', 'import PySide6,pygments;print("Notes runtime:",PySide6.__version__,pygments.__version__)'], text=True, capture_output=True)
    print(result.stdout.strip() or result.stderr.strip())
else:
    print('Dedicated Notes runtime not installed. Run ./install.sh --notes.')
