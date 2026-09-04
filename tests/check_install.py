"""Install twice into a temporary home; confirm launchers and data survive."""
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]

with tempfile.TemporaryDirectory(prefix='ubuntu-apps-install-') as directory:
    home = Path(directory)
    env = dict(os.environ, HOME=str(home), XDG_DATA_HOME=str(home / '.local/share'),
               XDG_CONFIG_HOME=str(home / '.config'), BIZON_SNIPPETS_HOME=str(home / '.config/bizon-snippets'))
    # Strip inherited Python overrides, while retaining the explicitly chosen interpreter.
    for key in ('PYTHONHOME', 'PYTHONPATH'):
        env.pop(key, None)
    notes = home / '.local/share/blue-notes/data/notes.db'
    notes.parent.mkdir(parents=True)
    with sqlite3.connect(notes) as db:
        db.execute('CREATE TABLE marker (text TEXT)')
        db.execute("INSERT INTO marker VALUES ('Keep my notebook')")
    unrelated = home / '.config/autokey/data/Unrelated'
    unrelated.mkdir(parents=True)
    (unrelated / 'existing.txt').write_text('Keep my other shortcuts')
    for iteration in range(2):
        subprocess.run([sys.executable, str(ROOT / 'apps/notes/install.py')], env=env, check=True)
        subprocess.run(['/usr/bin/python3', str(ROOT / 'apps/snippets/install.py')], env=env, check=True)
        with sqlite3.connect(notes) as db:
            assert db.execute('SELECT text FROM marker').fetchone()[0] == 'Keep my notebook'
        library = home / '.config/bizon-snippets/library.sqlite3'
        with sqlite3.connect(library) as db:
            if iteration == 0:
                db.execute("INSERT INTO settings VALUES ('install_test', 'Preserved')")
            else:
                assert db.execute("SELECT value FROM settings WHERE key='install_test'").fetchone()[0] == 'Preserved'
        assert (unrelated / 'existing.txt').read_text() == 'Keep my other shortcuts'
    for app in ('Notes', 'Snippets'):
        desktop = home / f'.local/share/applications/com.bizon.{app}.desktop'
        subprocess.run(['desktop-file-validate', str(desktop)], check=True)
        assert f'Name={app}' in desktop.read_text()
        assert str(home) in desktop.read_text()
    for name in ('notes', 'bizon-snippets'):
        launcher = home / '.local/bin' / name
        assert os.access(launcher, os.X_OK)
        subprocess.run(['sh', '-n', str(launcher)], check=True)
    picker = home / '.config/autokey/data/Clipboard Shortcuts/Snippet Picker.py'
    assert str(home / '.local/share/bizon-snippets/bridge.py') in picker.read_text()
    assert (picker.parent / '.folder.json').is_file()
    assert len(list((home / '.config/autostart').glob('*.desktop'))) == 1
    print('PASS clean installation, repeated installation, desktop entries, data preservation, and AutoKey setup')
