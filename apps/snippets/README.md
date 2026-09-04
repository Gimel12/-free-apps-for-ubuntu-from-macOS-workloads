# Snippets

A local GTK desktop snippet library for Ubuntu X11. Built for your canned responses.

## Everyday use

- Open **Snippets** from the application launcher.
- Click in another application's text field, press **Ctrl + .**, search, then **Enter** to paste.
- Add an abbreviation such as `;thanks`, enable expansion, and save. Type it in another app to expand immediately at a word boundary.
- **Ctrl + N** creates a snippet, **Ctrl + S** saves, and **Ctrl + F** searches.
- Organize responses in groups, mark favorites, duplicate, or move to recoverable Trash.
- **Pause typed expansion** disables abbreviations while leaving the picker available.
- Snippets are inserted as clipboard text, never interpreted as keyboard commands or executable code. The application never presses Enter to send a message.

## Templates

`{{name}}` and other named placeholders open a fill-in dialog. Repeated fields use the same value. Built-ins:

- `{{date}}`: local date, YYYY-MM-DD
- `{{time}}`: local time, HH:MM
- `{{clipboard}}`: current clipboard text

Canceling a typed fill-in restores its abbreviation. If the original destination window disappears, the snippet is left on the clipboard without pasting into another window.

## TextExpander migration

In **TextExpander.com → Import / Export → Export**, download each group as CSV, then choose **Import snippets** here. Select multiple files to import several groups. A preview appears before the library changes.

The importer supports UTF-8/UTF-16 CSV, quoted multiline content, names, abbreviations, and group names. Headerless CSV follows TextExpander's documented order: abbreviation, content, optional label. Without a group column, the filename becomes the group name. Add a prefix in the preview if your old TextExpander group used one.

Exact abbreviation/content duplicates are skipped. Overlapping abbreviations and snippets with detected formatting/macros are disabled for review. Edit these and explicitly enable them after conversion. The picker can paste flagged entries as literal plain text after an explicit prompt.

Native Snippets JSON exports are supported, plus legacy `.textexpander` / `.plist` files containing `plainText` snippets. Rich-text-only legacy files should be exported to CSV from TextExpander first.

This is a local alternative, not a complete TextExpander clone: rich text and image expansion, arbitrary scripts, nested snippets, TextExpander macro syntax, cloud synchronization, team sharing, and password-vault storage are not implemented. Imported markup/macros remain text; they are not silently executed. Review your own export in the import preview before enabling expansions.

Export documentation: https://textexpander.com/blog/textexpander-import-export

## Storage and recovery

- Installed application: `~/.local/share/bizon-snippets/`
- Library: `~/.config/bizon-snippets/library.sqlite3`
- Last 30 pre-change snapshots: `~/.config/bizon-snippets/backups/`
- Original picker JSON: `~/.config/bizon-snippets/snippets.json` (retained after migration)
- App launcher: `~/.local/share/applications/com.bizon.Snippets.desktop`
- AutoKey expansions: `~/.config/autokey/data/Bizon Snippet Expansions/`
- The **Ctrl + .** picker script is registered in AutoKey's **Clipboard Shortcuts** folder.

SQLite transactions protect edits/imports. Revision checks prevent one open editor from silently overwriting a newer edit. Library and backups have owner-only permissions. JSON export includes group and per-snippet settings; CSV exports names, text, abbreviations, and groups. Global pause state is local.

To restore a database snapshot, close the app and any picker, preserve the current database, and copy the selected snapshot to `library.sqlite3`. Reopen the app to rebuild its AutoKey abbreviations. Never replace the database while an editor is open.

## Development

Runtime: system Python 3, PyGObject/GTK 3, AutoKey GTK, and xdotool. No web server, subscription, or npm environment is required.

```
/usr/bin/python3 -m unittest discover -s tests -v
xvfb-run -a -s '-screen 0 1440x1000x24' /usr/bin/python3 tests/check_ui.py
```

`BIZON_SNIPPETS_HOME` may point to an isolated library for development. Tests use temporary databases and a virtual display. They validate imports, transaction rollback, revision conflicts, duplicate/collision behavior, AutoKey trigger parsing, focus/cancel handling, and GTK editing/search. GUI interaction on the user's live desktop is not simulated during tests.
