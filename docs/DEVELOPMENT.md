# Development

Use Ubuntu 24.04 and system Python 3.12. Notes uses PySide6 and Pygments in a virtual environment; Snippets uses Ubuntu's system GTK, AutoKey, and xdotool packages. No browser server or npm build is required.

## Dependencies

`install.sh` lists the complete apt package set. To install dependencies without installing the apps:

```bash
sudo apt-get update
sudo apt-get install -y python3 python3-venv python3-gi gir1.2-gtk-3.0 \
  autokey-gtk xdotool desktop-file-utils xvfb xauth libegl1 libgl1 \
  libxcb-cursor0 libxkbcommon-x11-0 libxcb-icccm4 libxcb-image0 \
  libxcb-keysyms1 libxcb-render-util0 libxcb-xinerama0
python3 -m venv .venv
.venv/bin/python -m pip install -r apps/notes/requirements.lock
```

`requirements.lock` pins the tested direct dependencies. PySide6's wheel metadata pins its companion components. `requirements.txt` documents the minimum supported versions for manual installation. Test upgrades before changing the lock file.

## Verify

```bash
bash -n install.sh
./install.sh --dry-run
/usr/bin/python3 -m unittest discover -s tests -v
/usr/bin/python3 -m unittest discover -s apps/snippets/tests -v
xvfb-run -a -s '-screen 0 1440x1000x24' /usr/bin/python3 apps/snippets/tests/check_ui.py
.venv/bin/python apps/notes/tests/check_app.py
.venv/bin/python apps/notes/tests/check_markdown.py
.venv/bin/python tests/check_install.py
```

Notes checks use Qt's offscreen platform. GTK checks use a virtual X11 display. Databases and installation checks use temporary home directories and synthetic content. Tests must never read or modify the developer's personal libraries or send keystrokes to their live desktop.

The suite covers autosave, rich Markdown roundtrips, code-copy controls, imports, exports, Trash, SQLite integrity, abbreviation collisions, AutoKey parsing, focus handling, backup/restore, invalid archives, and installing/updating into an empty home directory. Actual expansion into third-party applications should also be checked manually on an X11 desktop before releasing keyboard behavior changes.

## Layout and storage

Keep each app self-contained under `apps/`. Installers copy code into user application directories and generate paths for the destination account. Never hardcode a developer's username, copy a virtual environment between computers, or add runtime data to Git. Do not run `sudo ./install.sh`.

New apps should include an app guide, isolated checks, an installer path, and any data-transfer support needed before they are added to the root installer.
