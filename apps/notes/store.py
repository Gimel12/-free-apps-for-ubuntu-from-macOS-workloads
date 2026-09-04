"""Local, transactional storage for Blue Notes. No network services."""
from pathlib import Path
from datetime import datetime, timezone
import json
import sqlite3
import uuid


def now():
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.directory / "notes.db")
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.execute("""CREATE TABLE IF NOT EXISTS notes (
            id TEXT PRIMARY KEY, title TEXT NOT NULL, body TEXT NOT NULL,
            plain TEXT NOT NULL, tags TEXT NOT NULL DEFAULT '[]',
            pinned INTEGER NOT NULL DEFAULT 0, deleted INTEGER NOT NULL DEFAULT 0,
            created TEXT NOT NULL, updated TEXT NOT NULL)""")
        self.db.commit()
        self.backup()

    def backup(self):
        # The SQLite backup API includes committed WAL data.
        if not self.db.execute("SELECT 1 FROM notes LIMIT 1").fetchone():
            return
        folder = self.directory / "backups"
        folder.mkdir(exist_ok=True)
        path = folder / (datetime.now().strftime("%Y-%m-%d") + ".sqlite3")
        if path.exists():
            return
        temporary = path.with_suffix(".partial")
        with sqlite3.connect(temporary) as target:
            self.db.backup(target)
        temporary.replace(path)
        for old in sorted(folder.glob("*.sqlite3"))[:-14]:
            old.unlink()

    def create(self, title="", body="", plain="", tags=()):
        ident, stamp = str(uuid.uuid4()), now()
        with self.db:
            self.db.execute("INSERT INTO notes VALUES (?,?,?,?,?,0,0,?,?)",
                            (ident, title, body, plain, json.dumps(list(tags)), stamp, stamp))
        return ident

    def get(self, ident):
        row = self.db.execute("SELECT * FROM notes WHERE id=?", (ident,)).fetchone()
        return dict(row) if row else None

    def save(self, ident, title, body, plain, tags):
        tags = sorted(set(t.strip().lstrip("#").lower() for t in tags if t.strip().lstrip("#")))
        with self.db:
            self.db.execute("UPDATE notes SET title=?, body=?, plain=?, tags=?, updated=? WHERE id=?",
                            (title, body, plain, json.dumps(tags), now(), ident))

    def flag(self, ident, field, value):
        if field not in ("pinned", "deleted"):
            raise ValueError("Unknown flag")
        with self.db:
            self.db.execute(f"UPDATE notes SET {field}=? WHERE id=?", (int(value), ident))

    def remove(self, ident):
        with self.db:
            self.db.execute("DELETE FROM notes WHERE id=? AND deleted=1", (ident,))

    def notes(self, scope="all", query="", sort="updated"):
        rows = self.db.execute("SELECT * FROM notes WHERE deleted=?", (int(scope == "trash"),))
        result = []
        words = query.casefold().split()
        for row in rows:
            note = dict(row)
            tags = json.loads(note["tags"])
            if scope == "pinned" and not note["pinned"]:
                continue
            if scope.startswith("tag:") and scope[4:] not in tags:
                continue
            haystack = (note["title"] + " " + note["plain"] + " " + " ".join(tags)).casefold()
            if all(word in haystack for word in words):
                result.append(note)
        if sort == "title":
            result.sort(key=lambda n: (not n["pinned"], (n["title"] or "Untitled").casefold()))
        else:
            result.sort(key=lambda n: (n["pinned"], n["updated"]), reverse=True)
        return result

    def counts(self):
        active, pinned, trash, tags = 0, 0, 0, {}
        for row in self.db.execute("SELECT deleted,pinned,tags FROM notes"):
            if row["deleted"]:
                trash += 1
                continue
            active += 1
            pinned += row["pinned"]
            for tag in json.loads(row["tags"]):
                tags[tag] = tags.get(tag, 0) + 1
        return active, pinned, trash, tags

    def close(self):
        self.db.close()
