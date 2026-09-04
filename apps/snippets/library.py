"""Transactional local library shared by the editor and global picker."""
import csv
import io
import json
import os
import re
import sqlite3
import time
import uuid
from pathlib import Path

ROOT = Path(os.environ.get('BIZON_SNIPPETS_HOME', str(Path.home() / '.config/bizon-snippets')))


class Conflict(ValueError):
    pass


class Library:
    def __init__(self, root=None):
        self.root = Path(root) if root else ROOT
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path = self.root / 'library.sqlite3'
        self.db = sqlite3.connect(self.path, timeout=10)
        self.db.row_factory = sqlite3.Row
        os.chmod(self.path, 0o600)
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS groups (name TEXT PRIMARY KEY);
            CREATE TABLE IF NOT EXISTS snippets (
                id TEXT PRIMARY KEY, name TEXT NOT NULL, text TEXT NOT NULL,
                abbreviation TEXT NOT NULL DEFAULT '', group_name TEXT NOT NULL DEFAULT 'General',
                favorite INTEGER NOT NULL DEFAULT 0, enabled INTEGER NOT NULL DEFAULT 1,
                deleted INTEGER NOT NULL DEFAULT 0, note TEXT NOT NULL DEFAULT '',
                updated REAL NOT NULL, revision INTEGER NOT NULL DEFAULT 1);
            CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
            INSERT OR IGNORE INTO groups VALUES ('General');
        ''')
        if not self.db.execute("SELECT 1 FROM settings WHERE key='initialized'").fetchone():
            old = self.root / 'snippets.json'
            if old.exists():
                values = json.loads(old.read_text()).get('snippets', [])
                for value in values:
                    self._insert(dict(value, abbreviation=';thanks' if value.get('id') == 'thanks' else ''))
            self.db.execute("INSERT INTO settings VALUES ('initialized', 'yes')")
            self.db.commit()

    def all(self, trash=False):
        return [dict(r) for r in self.db.execute(
            'SELECT * FROM snippets WHERE deleted=? ORDER BY favorite DESC, name COLLATE NOCASE', (int(trash),))]

    def get(self, key):
        row = self.db.execute('SELECT * FROM snippets WHERE id=?', (key,)).fetchone()
        return dict(row) if row else None

    def groups(self):
        return [r[0] for r in self.db.execute('SELECT name FROM groups ORDER BY name COLLATE NOCASE')]

    def setting(self, key, default=''):
        r = self.db.execute('SELECT value FROM settings WHERE key=?', (key,)).fetchone()
        return r[0] if r else default

    def set_setting(self, key, value):
        with self.db:
            self.db.execute('INSERT OR REPLACE INTO settings VALUES (?,?)', (key, value))

    def backup(self):
        if not self.path.exists():
            return
        folder = self.root / 'backups'
        folder.mkdir(exist_ok=True, mode=0o700)
        path = folder / (time.strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:6] + '.sqlite3')
        dest = sqlite3.connect(path)
        try:
            self.db.backup(dest)
        finally:
            dest.close()
        path.chmod(0o600)
        for old in sorted(folder.glob('*.sqlite3'))[:-30]:
            old.unlink()

    def add_group(self, name):
        name = name.strip()
        if not name:
            raise ValueError('Enter a group name.')
        with self.db:
            self.db.execute('INSERT OR IGNORE INTO groups VALUES (?)', (name,))

    def validate(self, item):
        if not item.get('name', '').strip() or not item.get('text', '').strip():
            raise ValueError('Give the snippet a name and some text.')
        abbr = item.get('abbreviation', '').strip()
        if item.get('enabled', True) and abbr:
            if len(abbr) < 2 or re.search(r'\s', abbr):
                raise ValueError('Use an abbreviation of at least two characters, without spaces.')
            for other in self.all():
                other_abbr = other['abbreviation']
                if other['id'] != item.get('id') and other['enabled'] and other_abbr and (
                        other_abbr.startswith(abbr) or abbr.startswith(other_abbr)):
                    raise Conflict('Abbreviation overlaps with “' + other['name'] + '” (' + other_abbr + '). Choose another.')

    def _insert(self, item):
        key = str(item.get('id') or uuid.uuid4())
        group = item.get('group_name') or 'General'
        self.db.execute('INSERT OR IGNORE INTO groups VALUES (?)', (group,))
        self.db.execute('''INSERT INTO snippets
            (id,name,text,abbreviation,group_name,favorite,enabled,deleted,note,updated)
            VALUES (?,?,?,?,?,?,?,?,?,?)''',
            (key, item['name'].strip(), item['text'], item.get('abbreviation', '').strip(), group,
             int(bool(item.get('favorite', False))), int(bool(item.get('enabled', True))), 0,
             item.get('note', ''), time.time()))
        return key

    def save(self, item, expected_revision=None):
        self.validate(item)
        self.backup()
        with self.db:
            old = self.get(item.get('id', ''))
            if old:
                if expected_revision is not None and old['revision'] != expected_revision:
                    raise Conflict('This snippet changed in another window. Reopen it before saving.')
                self.db.execute('INSERT OR IGNORE INTO groups VALUES (?)', (item.get('group_name', 'General'),))
                self.db.execute('''UPDATE snippets SET name=?,text=?,abbreviation=?,group_name=?,
                    favorite=?,enabled=?,note=?,updated=?,revision=revision+1 WHERE id=?''',
                    (item['name'].strip(), item['text'], item.get('abbreviation', '').strip(),
                     item.get('group_name', 'General'), int(bool(item.get('favorite'))),
                     int(bool(item.get('enabled', True))), item.get('note', ''), time.time(), old['id']))
                return old['id']
            return self._insert(item)

    def trash(self, key, restore=False):
        self.backup()
        with self.db:
            # Restored snippets require an explicit re-enable to avoid abbreviation collisions.
            self.db.execute('UPDATE snippets SET deleted=?,enabled=?,revision=revision+1 WHERE id=?',
                            (0 if restore else 1, 0, key))

    def import_items(self, items):
        self.backup()
        added = duplicates = review = 0
        with self.db:
            known = {(s['abbreviation'], s['text']) for s in self.all()}
            for source in items:
                item = dict(source)
                signature = (item.get('abbreviation', ''), item['text'])
                if signature in known:
                    duplicates += 1
                    continue
                item.pop('id', None)
                if item.get('note'):
                    item['enabled'] = False
                try:
                    self.validate(item)
                except Conflict as exc:
                    item['enabled'] = False
                    item['note'] = (item.get('note', '') + '\n' + str(exc)).strip()
                except ValueError:
                    if not item.get('name') or not item.get('text', '').strip():
                        raise
                    item['enabled'] = False
                    item['note'] = (item.get('note', '') + '\nReview the abbreviation before enabling.').strip()
                self._insert(item)
                known.add(signature)
                added += 1
                review += int(bool(item.get('note')))
        return added, duplicates, review

    def export(self, path):
        path = Path(path)
        items = self.all()
        if path.suffix.lower() == '.csv':
            output = io.StringIO(newline='')
            writer = csv.writer(output)
            writer.writerow(['abbreviation', 'content', 'label', 'group'])
            for s in items:
                writer.writerow([s['abbreviation'], s['text'], s['name'], s['group_name']])
            content = output.getvalue()
        else:
            content = json.dumps({'app': 'Snippets', 'version': 1, 'snippets': items}, ensure_ascii=False, indent=2)
        with path.open('w', encoding='utf-8', newline='') as f:
            os.chmod(path, 0o600)
            f.write(content)


def matches(item, query):
    haystack = ' '.join(str(item.get(k, '')) for k in ('name','text','abbreviation','group_name')).casefold()
    return all(word in haystack for word in query.casefold().split())
