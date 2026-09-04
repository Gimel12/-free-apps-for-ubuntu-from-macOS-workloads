#!/usr/bin/env python3
"""Install Blue Notes for the current Linux user."""
from pathlib import Path
import os
import shlex
import shutil
import subprocess
import sys

source = Path(__file__).resolve().parent
home = Path.home()
data_home = Path(os.environ.get("XDG_DATA_HOME", str(home / ".local/share")))
destination = data_home / "blue-notes/app"
launcher = home / ".local/bin/notes"
desktop = data_home / "applications/com.bizon.Notes.desktop"

if launcher.exists() and "# Blue Notes launcher" not in launcher.read_text():
    raise SystemExit(f"An unrelated launcher already exists: {launcher}")

import PySide6  # Fail before installing if the runtime is unavailable.
import pygments
destination.mkdir(parents=True, exist_ok=True)
launcher.parent.mkdir(parents=True, exist_ok=True)
desktop.parent.mkdir(parents=True, exist_ok=True)
for name in ("notes.py", "store.py", "markdown_support.py", "glass.py", "icon.svg", "README.md", "requirements.txt"):
    shutil.copy2(source / name, destination / name)

launcher.write_text("#!/bin/sh\n# Blue Notes launcher\nexec " + shlex.quote(sys.executable) + " " + shlex.quote(str(destination / "notes.py")) + ' "$@"\n')
launcher.chmod(0o755)
desktop.write_text(f"""[Desktop Entry]
Type=Application
Version=1.0
Name=Notes
GenericName=Personal Notebook
Comment=A quiet white-and-blue notebook for your thoughts
Exec={launcher}
Icon={destination / 'icon.svg'}
Terminal=false
Categories=Utility;TextEditor;
Keywords=notes;note;notebook;writing;markdown;bear;blue;
StartupWMClass=Notes
StartupNotify=true
Actions=NewNote;

[Desktop Action NewNote]
Name=New note
Exec={launcher} --new
""")
if shutil.which("update-desktop-database"):
    subprocess.run(["update-desktop-database", str(desktop.parent)], check=True)
if shutil.which("desktop-file-validate"):
    subprocess.run(["desktop-file-validate", str(desktop)], check=True)
print(f"Installed Notes: {launcher}")
print(f"Application entry: {desktop}")
print(f"Notes and backups: {data_home / 'blue-notes/data'}")
