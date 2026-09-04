# Moving to another computer

Install the apps on the destination computer using the root README. Run transfer commands from the repository folder as your normal desktop user.

## Back up

Save current edits first. Notes saves automatically; use **Ctrl+S** in Snippets. SQLite's online backup API captures committed data, including edits still in its WAL journal.

```bash
python3 scripts/transfer.py backup ~/Documents/ubuntu-apps-backup.zip
```

The archive contains whichever libraries exist on the source computer, plus a versioned checksum manifest. It includes notes, formatting, tags, pinned notes, Trash, snippets, groups, and snippet settings. It does not include window preferences, old snapshots, custom AutoKey shortcuts, or the Python runtime. Back up any unrelated AutoKey configuration separately if needed.

The ZIP contains your private content and is **not encrypted**. Store and transfer it privately; do not upload it to this public repository. The command creates the archive with owner-only permissions and refuses to overwrite an existing backup. Choose a new filename for each backup.

## Restore

On the destination, install the apps first. Close Notes, Snippets, the picker, and AutoKey. Then run:

```bash
python3 scripts/transfer.py restore ~/Documents/ubuntu-apps-backup.zip
```

Restore checks checksums, database integrity, and the archive format before replacing anything. It replaces each included library; it does not merge two computers' libraries. Libraries absent from the archive are left alone. Previous databases are kept in a timestamped `restore-backups/` directory beside each database. Snippet abbreviations are regenerated for the destination account. Open Notes and Snippets, then restart AutoKey.

## Default data locations

| App | Database | Automatic app backups |
| --- | --- | --- |
| Notes | `~/.local/share/blue-notes/data/notes.db` | `~/.local/share/blue-notes/data/backups/` |
| Snippets | `~/.config/bizon-snippets/library.sqlite3` | `~/.config/bizon-snippets/backups/` |

Notes honors `XDG_DATA_HOME` if you use a custom data directory. Snippets uses the standard home paths above. The transfer tool targets these installed locations; a development library selected through `BIZON_SNIPPETS_HOME` is not supported.

To manually recover a previous database, quit both apps, the picker, and AutoKey. Preserve the current data folder, then restore the chosen database under its normal filename. Do not leave stale `-wal` or `-shm` files from a different database alongside it. Start the apps; saving a snippet or restarting the Snippets app rebuilds abbreviations.

## Coming from macOS

- **Bear:** export notes as Markdown, then use Notes → **Your notebook → Import**. Imported files preserve supported Markdown content; app-specific metadata and attachments are not migrated automatically.
- **Apple Notes:** export or copy content into UTF-8 text/Markdown files for import. Direct Apple Notes database and iCloud import are not implemented.
- **TextExpander:** export groups to CSV, then use Snippets → **Import snippets**. Review the preview and any disabled entries. Plain text and supported placeholders work; TextExpander scripts and macros need manual conversion. See the [Snippets guide](../apps/snippets/README.md).

## Removing the apps

Remove an app's launcher, desktop entry, and installed code. Keep the database folder until you have confirmed your backup.

- Notes code/runtime: `~/.local/share/blue-notes/app/` and `~/.local/share/blue-notes/venv/`; launcher `~/.local/bin/notes`; desktop entry `~/.local/share/applications/com.bizon.Notes.desktop`.
- Snippets code: `~/.local/share/bizon-snippets/`; launcher `~/.local/bin/bizon-snippets`; desktop entry `~/.local/share/applications/com.bizon.Snippets.desktop`.
- To remove Snippets keyboard integration, quit AutoKey, remove its generated **Bizon Snippet Expansions** folder and **Clipboard Shortcuts / Snippet Picker** script and metadata, then remove `~/.config/autostart/bizon-snippets-autokey.desktop` if present. Keep unrelated AutoKey shortcuts.
