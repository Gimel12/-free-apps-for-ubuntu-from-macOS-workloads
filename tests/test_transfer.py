"""Exercise real SQLite transfers using synthetic libraries in an isolated home."""
import json
import os
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'scripts'), str(ROOT / 'apps/notes'), str(ROOT / 'apps/snippets')]
import transfer
from store import Store
from library import Library


class TransferTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        env = patch.dict(os.environ, {'HOME': str(self.home), 'XDG_DATA_HOME': str(self.home / '.local/share')})
        env.start()
        self.addCleanup(env.stop)
        running = patch.object(transfer, 'running_apps', return_value=[])
        running.start()
        self.addCleanup(running.stop)
        self.mapping = transfer.locations()
        notes, installed, _ = self.mapping['notes.sqlite3']
        installed.parent.mkdir(parents=True)
        installed.touch()
        store = Store(notes.parent)
        self.note = store.create('Synthetic note', '<p>Original 🌊</p>', 'Original 🌊', ['test'])
        store.close()
        snippets, installed, _ = self.mapping['snippets.sqlite3']
        shutil.copytree(ROOT / 'apps/snippets', installed.parent, ignore=shutil.ignore_patterns('__pycache__', 'tests'))
        library = Library(snippets.parent)
        self.snippet = library.save(dict(name='Greeting', text='Hello {{name}}', abbreviation=';greeting', enabled=True))
        library.db.close()
        self.archive = self.home / 'transfer.zip'

    def value(self, name, query):
        with sqlite3.connect(self.mapping[name][0]) as db:
            return db.execute(query).fetchone()[0]

    def test_roundtrip_preserves_libraries_and_regenerates_shortcuts(self):
        self.assertEqual(transfer.backup(self.archive), 2)
        self.assertEqual(self.archive.stat().st_mode & 0o777, 0o600)
        for name, query in [('notes.sqlite3', "UPDATE notes SET plain='New computer'"),
                            ('snippets.sqlite3', "UPDATE snippets SET text='New computer'")]:
            with sqlite3.connect(self.mapping[name][0]) as db:
                db.execute(query)
        self.assertEqual(transfer.restore(self.archive), 2)
        self.assertEqual(self.value('notes.sqlite3', 'SELECT plain FROM notes'), 'Original 🌊')
        self.assertEqual(self.value('snippets.sqlite3', 'SELECT text FROM snippets'), 'Hello {{name}}')
        for path, _, _ in self.mapping.values():
            self.assertTrue(list((path.parent / 'restore-backups').glob('*/*')))
        generated = self.home / '.config/autokey/data/Bizon Snippet Expansions'
        scripts = list(generated.glob('snippet-*.py'))
        self.assertEqual(len(scripts), 1)
        self.assertIn(str(self.home / '.local/share/bizon-snippets/bridge.py'), scripts[0].read_text())

    def test_backup_will_not_overwrite(self):
        transfer.backup(self.archive)
        original = self.archive.read_bytes()
        with self.assertRaises(FileExistsError):
            transfer.backup(self.archive)
        self.assertEqual(self.archive.read_bytes(), original)

    def test_corruption_and_unexpected_paths_rejected_before_writes(self):
        transfer.backup(self.archive)
        with zipfile.ZipFile(self.archive) as archive:
            contents = {name: archive.read(name) for name in archive.namelist()}
        for kind in ('checksum', 'path'):
            bad = self.home / (kind + '.zip')
            edited = dict(contents)
            if kind == 'checksum':
                manifest = json.loads(edited['manifest.json'])
                manifest['files']['notes.sqlite3']['sha256'] = 'invalid'
                edited['manifest.json'] = json.dumps(manifest).encode()
            else:
                edited['../escape'] = b'no'
            with zipfile.ZipFile(bad, 'w') as archive:
                for name, data in edited.items():
                    archive.writestr(name, data)
            with self.assertRaises(ValueError):
                transfer.restore(bad)
            self.assertEqual(self.value('notes.sqlite3', 'SELECT plain FROM notes'), 'Original 🌊')
            self.assertFalse((self.home / 'escape').exists())

    def test_failed_shortcut_sync_rolls_back_databases_and_generated_files(self):
        transfer.backup(self.archive)
        with sqlite3.connect(self.mapping['notes.sqlite3'][0]) as db:
            db.execute("UPDATE notes SET plain='Preserve destination'")
        generated = self.home / '.config/autokey/data/Bizon Snippet Expansions'
        generated.mkdir(parents=True)
        (generated / 'before.txt').write_text('Original shortcuts')
        def failure(*args, **kwargs):
            (generated / 'before.txt').unlink()
            (generated / 'partial.txt').write_text('Partial sync')
            raise RuntimeError('Simulated sync failure')
        with patch.object(transfer.subprocess, 'run', side_effect=failure):
            with self.assertRaisesRegex(RuntimeError, 'Simulated'):
                transfer.restore(self.archive)
        self.assertEqual(self.value('notes.sqlite3', 'SELECT plain FROM notes'), 'Preserve destination')
        self.assertEqual((generated / 'before.txt').read_text(), 'Original shortcuts')
        self.assertFalse((generated / 'partial.txt').exists())

    def test_running_apps_block_restore(self):
        transfer.backup(self.archive)
        with patch.object(transfer, 'running_apps', return_value=['123']):
            with self.assertRaisesRegex(RuntimeError, 'Close Notes'):
                transfer.restore(self.archive)


if __name__ == '__main__':
    unittest.main()
