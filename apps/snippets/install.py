#!/usr/bin/python3
"""Install for the current desktop user. AutoKey should be stopped first."""
import json
import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

os.umask(0o077)
parser=argparse.ArgumentParser(description='Install the Snippets app for the current desktop user.')
parser.add_argument('--no-autostart',action='store_true',help='Do not enable AutoKey at login.')
args=parser.parse_args()
source=Path(__file__).resolve().parent
home=Path.home()
destination=home/'.local/share/bizon-snippets'
backup=home/'.local/share/bizon-snippets-install-backups'/(time.strftime('%Y%m%d-%H%M%S')+'-'+str(time.time_ns()))
backup.mkdir(parents=True,exist_ok=True)
for path in (destination,home/'.config/bizon-snippets',home/'.config/autokey'):
    if path.exists():
        name='app' if path==destination else path.name
        shutil.copytree(path,backup/name)
destination.mkdir(parents=True,exist_ok=True)
for path in source.iterdir():
    if path.is_file() and path.suffix in ('.py','.css','.svg','.md'):
        shutil.copy2(path,destination/path.name)
sys.path.insert(0,str(destination))
from library import Library
from integration import sync,bridge_code,config,write_atomic
# Preserve any unrelated shortcut that happens to use the original picker filename.
folder=home/'.config/autokey/data/Clipboard Shortcuts'
picker_path=folder/'Snippet Picker.py'
if picker_path.exists() and 'bridge.py' not in picker_path.read_text() and 'bizon-snippets' not in picker_path.read_text():
    raise SystemExit('An unrelated Snippet Picker.py already exists. Rename it in AutoKey before installing.')
library=Library()
sync(library)
folder.mkdir(parents=True,exist_ok=True)
folder_meta=folder/'.folder.json'
if not folder_meta.exists():
    meta=config('Clipboard Shortcuts')
    meta.update(type='folder',title='Clipboard Shortcuts',modes=[])
    write_atomic(folder_meta,json.dumps(meta,indent=2))
write_atomic(folder/'Snippet Picker.py',bridge_code())
write_atomic(folder/'.Snippet Picker.json',json.dumps(config('Search and paste snippets',hotkey=True),indent=2))
launcher=home/'.local/bin/bizon-snippets'
launcher.parent.mkdir(parents=True,exist_ok=True)
import shlex
launcher.write_text('#!/bin/sh\nunset PYTHONPATH PYTHONHOME LD_LIBRARY_PATH LD_PRELOAD\nexec /usr/bin/python3 '+shlex.quote(str(destination/'app.py'))+' "$@"\n')
launcher.chmod(0o755)
desktop=home/'.local/share/applications/com.bizon.Snippets.desktop'
desktop.parent.mkdir(parents=True,exist_ok=True)
desktop.write_text('[Desktop Entry]\nType=Application\nName=Snippets\n'
    'Comment=Your personal text expansion and canned response library\n'
    'Exec='+str(launcher)+'\nIcon='+str(destination/'icon.svg')+'\n'
    'Terminal=false\nCategories=Utility;\nStartupWMClass=BizonSnippets\n'
    'Keywords=TextExpander;canned responses;snippets;text expansion;\n')
desktop.chmod(0o644)
subprocess.run(['update-desktop-database',str(desktop.parent)],check=True)
if not args.no_autostart:
    autostart=home/'.config/autostart'
    autostart.mkdir(parents=True,exist_ok=True)
    # Respect an existing AutoKey startup entry instead of launching two instances.
    existing=any('autokey' in p.read_text(errors='replace').lower() for p in autostart.glob('*.desktop'))
    if not existing:
        entry=autostart/'bizon-snippets-autokey.desktop'
        entry.write_text('[Desktop Entry]\nType=Application\nName=Snippets keyboard service\n'
            'Comment=Enable snippet abbreviations and the Ctrl+. picker\n'
            'Exec=autokey-gtk -c\nTerminal=false\nX-GNOME-Autostart-enabled=true\n')
        entry.chmod(0o644)
print('Installed Snippets; preserved',len(library.all()),'existing snippets.')
print('Backup:',backup)
print('Launcher:',launcher)
