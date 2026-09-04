import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
import sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QTextCursor, QTextDocument, QTextBlockFormat
from PySide6.QtTest import QTest
from notes import Window
from store import Store
from markdown_support import encode_document, load_document, markdown_body, is_code, LANG, FENCE

app = QApplication([])
app.setStyle('Fusion')
source = '''An introduction with **bold** and `inline code`.

## A useful snippet

```python
# a comment
def greet(name):
    return "Hello, " + name + " 🌊"

print(greet("world"))
```

> Remember to make a little space.

| Item | State |
| --- | --- |
| Notes | Saved |

- [ ] A task
- [x] A finished task

````text
literal ``` backticks
````

The ending stays here.
'''

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    store = Store(root/'data')
    settings = QSettings(str(root/'s.ini'), QSettings.Format.IniFormat)
    window = Window(store, settings)
    window.resize(1460, 1020)
    window.show()
    window.new_note()
    note = window.current
    window.title.setText('Markdown, made comfortable.')
    window.tags.setText('markdown, guide')
    window.set_mode('markdown')
    window.source_editor.setPlainText(source)
    window.new_note()  # switch before debounce must synchronize the source
    assert markdown_body(store.get(note)['body']) == source
    window.select(note)
    assert window.source_editor.toPlainText() == source
    window.set_mode('write')
    blocks=[]
    block=window.editor.document().begin()
    while block.isValid():
        if is_code(block): blocks.append(block)
        block=block.next()
    assert len(blocks)==6, [(b.text(), b.blockFormat().property(LANG)) for b in blocks]
    assert blocks[-1].text() == 'literal ``` backticks'
    assert blocks[0].blockFormat().property(LANG)=='python'
    assert '🌊' in window.editor.toPlainText()
    assert window.editor.toPlainText().endswith('The ending stays here.')
    assert '```python' in window.markdown(store.get(note))
    print('PASS exact source, Unicode, fence languages, tables, and rapid-switch saving')

    app.processEvents()
    assert window.editor.copy_areas
    area, number, code = window.editor.copy_areas[0]
    QTest.mouseClick(window.editor.viewport(), Qt.MouseButton.LeftButton, pos=area.center().toPoint())
    assert QApplication.clipboard().text()==code
    print('PASS code copy action')

    # Edit rendered prose, save, and reopen; code fences survive HTML serialization.
    window.editor.moveCursor(QTextCursor.MoveOperation.End)
    window.editor.insertPlainText(' An extra sentence.')
    window.save()
    rendered_markdown = markdown_body(store.get(note)['body'])
    assert '```python' in rendered_markdown
    assert 'literal ``` backticks' in rendered_markdown
    window.load(note)
    assert window.editor.toPlainText().endswith(' An extra sentence.')
    print('PASS rich-edit HTML/Markdown roundtrip')

    # Code insertion and Ctrl+Enter create ordinary prose without code formatting.
    window.new_note()
    window.insert_code('javascript', 'const message = "hello";\nconsole.log(message);')
    assert is_code(window.editor.textCursor().block())
    QTest.keyClick(window.editor, Qt.Key.Key_Return, Qt.KeyboardModifier.ControlModifier)
    assert not is_code(window.editor.textCursor().block())
    QTest.keyClicks(window.editor, 'Ordinary prose after code.')
    window.save()
    md = markdown_body(store.get(window.current)['body'])
    assert '```javascript' in md and 'Ordinary prose after code.' in md
    print('PASS insert code + leave block')

    # Typing a Markdown fence turns into a code block.
    window.new_note()
    QTest.keyClicks(window.editor, '```python')
    QTest.keyClick(window.editor, Qt.Key.Key_Return)
    assert is_code(window.editor.textCursor().block())
    QTest.keyClicks(window.editor, 'print(42)')
    window.save()
    assert '```python' in markdown_body(store.get(window.current)['body'])
    print('PASS typed code fence')

    # Paste-as-Markdown inserts structured content, not literal fence syntax.
    window.new_note()
    QApplication.clipboard().setText('## Pasted heading\n\n```sql\nSELECT 1;\n```')
    window.paste_markdown()
    window.save()
    assert '```sql' in markdown_body(store.get(window.current)['body'])
    assert 'SELECT 1;' in window.editor.toPlainText()
    print('PASS paste Markdown')

    # Existing 1.0 HTML has no new metadata and still loads without content loss.
    old=QTextDocument();old.setHtml('<h2>Existing title</h2><p>Your original <b>writing</b>.</p>')
    old_body=old.toHtml()
    ident=store.create('Existing note',old_body,old.toPlainText())
    window.change_scope('all');window.select(ident)
    assert window.editor.toPlainText()==old.toPlainText()
    window.editor.moveCursor(QTextCursor.MoveOperation.End)
    window.editor.insertPlainText(' And more.')
    window.save()
    assert 'Your original **writing**.' in markdown_body(store.get(ident)['body'])
    print('PASS existing note compatibility')

    window.close();store.close()
    reopened=Store(root/'data')
    assert reopened.db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    print('ALL MARKDOWN CHECKS PASSED')
