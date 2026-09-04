import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile

os.environ['QT_QPA_PLATFORM'] = 'offscreen'
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QTextCursor, QTextBlockFormat
from PySide6.QtWidgets import QApplication, QMessageBox, QFileDialog
from PySide6.QtTest import QTest
from notes import Window
from store import Store

app = QApplication([])
app.setStyle('Fusion')

with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    data = root / 'data'
    store = Store(data)
    settings = QSettings(str(root / 'settings.ini'), QSettings.Format.IniFormat)
    w = Window(store, settings)
    w.show()
    app.processEvents()

    # Rapidly switch away before the debounce interval: writing must survive.
    w.new_note()
    first = w.current
    QTest.keyClicks(w.title, 'A plan for tomorrow')
    QTest.keyClicks(w.editor, 'Small steps, with room to think.')
    QTest.keyClicks(w.tags, 'Ideas, Personal')
    w.new_note()
    assert store.get(first)['plain'] == 'Small steps, with room to think.'
    assert json.loads(store.get(first)['tags']) == ['ideas', 'personal']
    second = w.current
    QTest.keyClicks(w.title, 'Another thought')
    QTest.keyClicks(w.editor, 'A second note.')
    QTest.qWait(600)
    assert not w.dirty and store.get(second)['plain'] == 'A second note.'
    print('PASS immediate switch + debounced autosave')

    # Search across body and tags; wildcards are literals, not SQL syntax.
    assert len(store.notes(query='room personal')) == 1
    assert len(store.notes(query="%' OR 1=1")) == 0
    w.change_scope('tag:ideas')
    assert w.note_list.count() == 1 and w.current == first
    w.toggle_pin()
    assert len(store.notes('pinned')) == 1
    w.change_scope('pinned')
    assert w.current == first
    print('PASS tag, pin, and search')

    # Rich formatting and task markers persist in HTML and portable Markdown.
    cursor = w.editor.textCursor()
    cursor.select(QTextCursor.SelectionType.Document)
    w.editor.setTextCursor(cursor)
    w.bold()
    w.save()
    assert '**Small steps' in w.markdown(store.get(first))
    w.editor.moveCursor(QTextCursor.MoveOperation.End)
    w.editor.insertPlainText('\nWrite something meaningful')
    w.add_list(True)
    w.save()
    assert '[ ]' in w.markdown(store.get(first))
    w.load(first)
    w.editor.moveCursor(QTextCursor.MoveOperation.End)
    assert w.editor.textCursor().blockFormat().marker() == QTextBlockFormat.MarkerType.Unchecked
    print('PASS rich text + checklist roundtrip')

    # Trash is reversible and keeps the original record.
    w.delete_note()
    assert store.get(first)['deleted'] == 1
    w.change_scope('trash')
    assert w.current == first and w.editor.isReadOnly()
    w.restore_note()
    assert store.get(first)['deleted'] == 0 and w.current == first
    w.duplicate_note()
    duplicate = w.current
    assert store.get(duplicate)['plain'] == store.get(first)['plain']
    print('PASS trash, restore, duplicate')

    # Import multiple formats; export ZIP contains all notes and full JSON.
    (root / 'entry.md').write_text('# Imported title\n\nA **bold** paragraph.', encoding='utf-8')
    (root / 'entry.txt').write_text('Plain text, preserved.', encoding='utf-8')
    QFileDialog.getOpenFileNames = lambda *a, **kw: ([str(root/'entry.md'), str(root/'entry.txt')], '')
    w.import_notes()
    imported = store.notes(query='imported')
    assert len(imported) == 2
    assert any(n['title'] == 'Imported title' for n in imported)
    QFileDialog.getSaveFileName = lambda *a, **kw: (str(root/'export.zip'), '')
    QMessageBox.information = lambda *a, **kw: QMessageBox.StandardButton.Ok
    w.export_all()
    import zipfile
    with zipfile.ZipFile(root/'export.zip') as z:
        assert len(json.loads(z.read('notebook.json'))) == len(store.notes())
        assert any(name.endswith('.md') for name in z.namelist())
    print('PASS Markdown/text import + full export')

    # Closing before debounce flushes changes; reopening does not replace notes.
    w.editor.moveCursor(QTextCursor.MoveOperation.End)
    QTest.keyClicks(w.editor, ' Last edit before closing.')
    final_id = w.current
    w.close()
    expected = store.get(final_id)['plain']
    assert expected.endswith(' Last edit before closing.')
    store.close()
    store = Store(data)
    assert store.get(final_id)['plain'] == expected
    assert len(list((data/'backups').glob('*.sqlite3'))) == 1
    backup = next((data/'backups').glob('*.sqlite3'))
    with sqlite3.connect(backup) as db:
        assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
        assert db.execute('SELECT plain FROM notes WHERE id=?',(final_id,)).fetchone()[0] == expected
    w = Window(store, settings)
    assert w.current == final_id
    assert w.editor.toPlainText() == expected
    assert store.db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
    w.change_scope('all')
    w.select(first)
    w.show()
    app.processEvents()
    w.toggle_focus()
    assert not w.sidebar.isVisible()
    w.toggle_focus()
    w.close()
    store.close()
    print('PASS close/reopen, focus mode, database integrity + backup contents')

print('ALL CHECKS PASSED')
