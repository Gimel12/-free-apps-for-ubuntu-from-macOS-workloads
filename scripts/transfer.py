#!/usr/bin/env python3
"""Back up or restore both app libraries without third-party Python packages."""
import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import zipfile


def locations():
    home = Path.home()
    data = Path(os.environ.get('XDG_DATA_HOME', str(home / '.local/share')))
    return {
        'notes.sqlite3': (data / 'blue-notes/data/notes.db', data / 'blue-notes/app/notes.py', {'notes'}),
        'snippets.sqlite3': (home / '.config/bizon-snippets/library.sqlite3', home / '.local/share/bizon-snippets/app.py', {'snippets', 'groups', 'settings'}),
    }


def digest(data):
    return hashlib.sha256(data).hexdigest()


def validate_db(path, tables):
    with sqlite3.connect(path.as_uri() + '?mode=ro', uri=True) as db:
        if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise ValueError('Database integrity check failed: ' + path.name)
        present = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not tables.issubset(present):
            raise ValueError('Archive contains the wrong database schema: ' + path.name)


def backup(destination):
    destination = Path(destination).expanduser().resolve()
    if destination.exists():
        raise FileExistsError('Choose a new backup filename; this file already exists.')
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        manifest = {'format': 'ubuntu-workloads', 'version': 1, 'created': datetime.now().isoformat(), 'files': {}}
        for name, (source, _, tables) in locations().items():
            if not source.is_file():
                continue
            staged = folder / name
            with sqlite3.connect(source.as_uri() + '?mode=ro', uri=True) as db, sqlite3.connect(staged) as target:
                db.backup(target)
            validate_db(staged, tables)
            content = staged.read_bytes()
            manifest['files'][name] = {'sha256': digest(content), 'bytes': len(content)}
        if not manifest['files']:
            raise ValueError('No Notes or Snippets libraries found for this user.')
        # Write an exclusive temporary file in the destination filesystem.
        fd, temporary = tempfile.mkstemp(prefix='.ubuntu-apps-', suffix='.zip', dir=destination.parent)
        os.close(fd)
        try:
            with zipfile.ZipFile(temporary, 'w', zipfile.ZIP_DEFLATED) as archive:
                archive.writestr('manifest.json', json.dumps(manifest, indent=2))
                for name in manifest['files']:
                    archive.write(folder / name, name)
            # link() fails if another process created destination meanwhile.
            os.link(temporary, destination)
        finally:
            Path(temporary).unlink(missing_ok=True)
    return len(manifest['files'])


def running_apps():
    installed = [str(entry[1]) for entry in locations().values()]
    installed.append(str(Path.home() / '.local/share/bizon-snippets/picker.py'))
    found = []
    for process in Path('/proc').glob('[0-9]*'):
        try:
            if process.stat().st_uid != os.getuid():
                continue
            argv = (process / 'cmdline').read_bytes().decode(errors='replace').split('\0')
            if any(arg in installed for arg in argv) or any(Path(arg).name in ('autokey-gtk', 'autokey-qt') for arg in argv if arg):
                found.append(process.name)
        except (OSError, ValueError):
            continue
    return found


def restore(source):
    if running_apps():
        raise RuntimeError('Close Notes, Snippets, the picker, and AutoKey before restoring.')
    mapping = locations()
    with tempfile.TemporaryDirectory() as tmp, zipfile.ZipFile(Path(source).expanduser()) as archive:
        names = archive.namelist()
        allowed = {'manifest.json', *mapping}
        if len(names) != len(set(names)) or not set(names).issubset(allowed):
            raise ValueError('Unexpected or duplicate files in backup archive.')
        if 'manifest.json' not in names or archive.getinfo('manifest.json').file_size > 100_000:
            raise ValueError('Missing or invalid manifest.')
        manifest = json.loads(archive.read('manifest.json'))
        files = manifest.get('files', {})
        if manifest.get('format') != 'ubuntu-workloads' or manifest.get('version') != 1 or not files:
            raise ValueError('This is not a supported Ubuntu apps backup.')
        if set(files) != set(names) - {'manifest.json'}:
            raise ValueError('Manifest does not match archive files.')
        staged = Path(tmp)
        for name, record in files.items():
            target, installed, tables = mapping[name]
            if not installed.is_file():
                raise RuntimeError('Install the app before restoring: ' + name)
            if archive.getinfo(name).file_size > 2 * 1024**3:
                raise ValueError('Database exceeds the 2 GiB transfer limit.')
            with archive.open(name) as incoming, (staged / name).open('wb') as out:
                shutil.copyfileobj(incoming, out)
            content = (staged / name).read_bytes()
            if record.get('sha256') != digest(content) or record.get('bytes') != len(content):
                raise ValueError('Backup checksum mismatch: ' + name)
            validate_db(staged / name, tables)
        # Preserve every current database and sidecar before replacing anything.
        stamp = datetime.now().strftime('%Y%m%d-%H%M%S-%f')
        saved = []
        for name in files:
            target = mapping[name][0]
            target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            old = target.parent / 'restore-backups' / stamp
            old.mkdir(parents=True, mode=0o700)
            for suffix in ('', '-wal', '-shm'):
                path = Path(str(target) + suffix)
                if path.exists():
                    shutil.copy2(path, old / path.name)
            saved.append((target, old))
        generated = Path.home() / '.config/autokey/data/Bizon Snippet Expansions'
        old_generated = staged / 'autokey-before-restore'
        if 'snippets.sqlite3' in files and generated.exists():
            shutil.copytree(generated, old_generated)
        try:
            for name in files:
                target = mapping[name][0]
                for suffix in ('-wal', '-shm'):
                    Path(str(target) + suffix).unlink(missing_ok=True)
                temporary = target.with_name(target.name + '.restore-tmp')
                shutil.copyfile(staged / name, temporary)
                temporary.chmod(0o600)
                temporary.replace(target)
            if 'snippets.sqlite3' in files:
                app_dir = mapping['snippets.sqlite3'][1].parent
                code = "import sys;sys.path.insert(0,sys.argv[1]);from library import Library;from integration import sync;lib=Library();sync(lib);lib.db.close()"
                env = dict(os.environ, BIZON_SNIPPETS_HOME=str(mapping['snippets.sqlite3'][0].parent))
                subprocess.run(['/usr/bin/python3', '-c', code, str(app_dir)], check=True, env=env)
            if 'notes.sqlite3' in files:
                (mapping['notes.sqlite3'][0].parent / '.initialized').touch()
        except Exception:
            for target, old in saved:
                for suffix in ('', '-wal', '-shm'):
                    path = Path(str(target) + suffix)
                    path.unlink(missing_ok=True)
                    if (old / path.name).exists():
                        shutil.copy2(old / path.name, path)
            if 'snippets.sqlite3' in files:
                if generated.exists():
                    shutil.rmtree(generated)
                if old_generated.exists():
                    shutil.copytree(old_generated, generated)
            raise
    return len(files)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('backup', 'restore'))
    parser.add_argument('archive', type=Path)
    args = parser.parse_args()
    os.umask(0o077)
    try:
        count = backup(args.archive) if args.action == 'backup' else restore(args.archive)
        print(f'{args.action.capitalize()} complete: {count} libraries. Your data stays outside the repository.')
        if args.action == 'restore':
            print('Open your apps and restart AutoKey. Previous databases are in each data folder’s restore-backups/.')
    except Exception as error:
        print(str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
