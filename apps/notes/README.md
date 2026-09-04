# Blue Notes

A native Linux notebook with a white-and-blue glass-style interface. Open Ulauncher, type **notes**, and select **Notes**. Reopening brings your existing window forward.

## Markdown, made comfortable

**Write** is the formatted editor. **Markdown** lets you edit the source directly. **Read** provides a clean reading view. Changes in either editor save automatically and survive switching notes or closing the app.

- Click the **code icon** or press **Ctrl+Shift+K** to insert a code block. Choose a language for blue syntax highlighting.
- Type three backticks followed by a language, such as **python**, on a fresh line and press Enter to begin a block in Write mode.
- Press **Ctrl+Enter** to leave a code block and continue with normal prose.
- Each rendered code block has a **Copy** button.
- The **+** beside the code icon inserts inline code, quotes, tables, or a divider.
- **Ctrl+Shift+V** pastes clipboard Markdown as formatted content.
- **Ctrl+Shift+M** switches between Write and Markdown.

Code is displayed as text; the app never executes it. Syntax highlighting uses shades of blue. The glass effect uses soft gradients, translucent panel colors, highlights, and shadows; it does not capture or blur your desktop contents.

## Your notebook

- Rich text: bold, italic, headings, lists, checklists, and links.
- Markdown code blocks, inline code, quotes, tables, and horizontal dividers.
- Search titles, contents, and tags together.
- Comma-separated tags, pinned notes, and reversible Trash.
- Focus mode hides the sidebar and note list.
- Autosave after a short pause, when switching notes, and before closing.
- Import UTF-8 Markdown or text files through **Your notebook**.
- Export individual Markdown files or a ZIP of the whole notebook, including Trash and full JSON records.
- Ctrl-click a link to open it. Click a task's checkbox to toggle it.

## Keyboard shortcuts

| Shortcut | Action |
| --- | --- |
| Ctrl+N | New note |
| Ctrl+K / Ctrl+F | Search |
| Ctrl+B / Ctrl+I | Bold / italic |
| Ctrl+L | Insert link |
| Ctrl+Shift+C | Checklist |
| Ctrl+Shift+K | Insert code block |
| Ctrl+Enter | Leave a code block |
| Ctrl+Shift+M | Markdown / Write |
| Ctrl+Shift+V | Paste as Markdown |
| Ctrl+Shift+P | Pin / unpin |
| Ctrl+Shift+F | Focus mode |
| Ctrl+E | Export current note |
| Ctrl+S | Save immediately |
| Ctrl+Z / Ctrl+Shift+Z | Undo / redo |

Drag the top bar to move the window, double-click it to maximize, or use the bottom-right resize grip. Drag the dividers to adjust the panes.

## Storage and backups

Notes stay on this computer; there is no account or cloud synchronization.

By default, data lives in `~/.local/share/blue-notes/data/notes.db`. SQLite transactions and WAL protect committed edits. The original database is never replaced during installation or updates.

Daily database snapshots are created on startup when notes exist, checked hourly while running, and checked when opening the backup folder. The last 14 dated snapshots are retained in `data/backups/`. A snapshot represents the notebook at the time it was taken. Use **Your notebook → Export all notes** for a fresh portable copy whenever you like.

To restore a database snapshot, close Notes, preserve the current data folder separately, then place the chosen snapshot in a clean data folder under the name `notes.db`. Do not combine a restored database with old `notes.db-wal` or `notes.db-shm` files. Start Notes again.

## Installation

Use `./install.sh --notes` from the [repository root](../../README.md) to install the tested runtime and app together.

For manual installation, requires Python 3.10+, PySide6 6.8+, and Pygments 2.15+. Run `python3 install.py` using a Python installation with these packages installed. This copies the application to `~/.local/share/blue-notes/app`, creates `~/.local/bin/notes`, and registers a standard desktop entry for Ulauncher and the Linux application menu.

Run `notes --new` to open a fresh note. The installed launcher uses the exact Python executable selected during installation.

To remove the app, remove its `app` folder, `~/.local/bin/notes`, and `~/.local/share/applications/com.bizon.Notes.desktop`. Keep the `data` folder to preserve your notes.
