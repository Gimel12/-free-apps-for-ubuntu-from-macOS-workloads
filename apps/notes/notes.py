#!/usr/bin/env python3
"""Blue Notes — a small native notebook for Linux."""
import argparse
from datetime import datetime
import html
import json
import os
from pathlib import Path
import re
import sys
import zipfile

from PySide6.QtCore import Qt, QSize, QTimer, QSettings, QLockFile
from PySide6.QtGui import (QAction, QColor, QFont, QIcon, QKeySequence, QPainter,
                          QPixmap, QTextCursor, QTextCharFormat, QTextBlockFormat,
                          QTextListFormat, QDesktopServices, QTextDocument, QPalette,
                          QTextDocumentFragment, QTextTableFormat, QTextFormat)
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QFrame, QLabel,
    QPushButton, QToolButton, QLineEdit, QTextEdit, QVBoxLayout, QHBoxLayout,
    QListWidget, QListWidgetItem, QSplitter, QStackedWidget, QMenu, QFileDialog,
    QMessageBox, QInputDialog, QScrollArea, QSizeGrip)
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtNetwork import QLocalServer, QLocalSocket

from store import Store
from markdown_support import (CodeEditor, SourceEditor, encode_document, load_document,
    markdown_body, style_document as style_markdown, is_code, LANG, FENCE, QUOTE, MONO)
from glass import GlassSurface, GLASS_STYLE, shadow

BLUE = "#2463eb"
INK = "#15366b"
MUTED = "#6482af"
PALE = "#f4f8ff"
LINE = "#e1ebfc"
HERE = Path(__file__).resolve().parent
DATA = Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local/share"))) / "blue-notes/data"

PATHS = {
    "plus": '<path d="M12 5v14M5 12h14"/>',
    "note": '<rect x="5" y="3" width="14" height="18" rx="3"/><path d="M9 8h6M9 12h6M9 16h4"/>',
    "search": '<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 4.5 4.5"/>',
    "pin": '<path d="m9 3 6 0-1 6 4 4v2H6v-2l4-4-1-6ZM12 15v6"/>',
    "trash": '<path d="M3 6h18M9 6V3h6v3M6 6l1 15h10l1-15M10 10v7M14 10v7"/>',
    "tag": '<path d="M3 4v7l9 10 9-9L11 3H4z"/><circle cx="7.5" cy="7.5" r="1"/>',
    "more": '<circle cx="5" cy="12" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/>',
    "focus": '<path d="M8 3H3v5M16 3h5v5M21 16v5h-5M3 16v5h5"/>',
    "restore": '<path d="M3 4v6h6M3 10a9 9 0 1 1 1 8"/>',
    "link": '<path d="m10 14 4-4M8 15l-1 1a4 4 0 0 1-6-6l4-4a4 4 0 0 1 6 0M16 9l1-1a4 4 0 0 1 6 6l-4 4a4 4 0 0 1-6 0" transform="translate(0 -1) scale(.95)"/>',
    "list": '<path d="M9 6h12M9 12h12M9 18h12"/><circle cx="4" cy="6" r=".6"/><circle cx="4" cy="12" r=".6"/><circle cx="4" cy="18" r=".6"/>',
    "check": '<rect x="3" y="3" width="18" height="18" rx="4"/><path d="m7 12 3 3 7-7"/>',
    "quote": '<path d="M4 6h6v7H4v-2c0-3 1-4 3-5M14 6h6v7h-6v-2c0-3 1-4 3-5M10 13c0 3-2 5-5 5M20 13c0 3-2 5-5 5"/>',
    "download": '<path d="M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5"/>',
    "close": '<path d="m6 6 12 12M6 18 18 6"/>',
    "min": '<path d="M5 12h14"/>',
    "max": '<rect x="5" y="5" width="14" height="14" rx="2"/>',
    "sort": '<path d="M4 6h16M4 12h11M4 18h6"/>',
    "folder": '<path d="M3 7V5h7l2 3h9v12H3z"/>',
    "code": '<path d="m8 6-6 6 6 6m8-12 6 6-6 6m-3-15-2 18"/>',
}


def icon(name, color=BLUE, size=24):
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">{PATHS[name]}</svg>'
    image = QPixmap(size * 2, size * 2)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    QSvgRenderer(svg.encode()).render(painter)
    painter.end()
    image.setDevicePixelRatio(2)
    result = QIcon(image)
    disabled = QPixmap(size * 2, size * 2)
    disabled.fill(Qt.GlobalColor.transparent)
    painter = QPainter(disabled)
    QSvgRenderer(svg.replace(color, '#acc3e5').encode()).render(painter)
    painter.end()
    disabled.setDevicePixelRatio(2)
    result.addPixmap(disabled, QIcon.Mode.Disabled)
    return result


def label(text, name=None):
    w = QLabel(text)
    if name:
        w.setObjectName(name)
    return w


def tool(name, tip, callback=None, text=None):
    b = QToolButton()
    b.setObjectName("tool")
    b.setFixedSize(34, 34)
    if name:
        b.setIcon(icon(name))
        b.setIconSize(QSize(18, 18))
    if text:
        b.setText(text)
    b.setToolTip(tip)
    b.setAccessibleName(tip)
    if callback:
        b.clicked.connect(callback)
    return b


class Header(QFrame):
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.window().windowHandle().startSystemMove()
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        window = self.window()
        window.showNormal() if window.isMaximized() else window.showMaximized()


class Editor(CodeEditor):
    """Rich text editor with plain-text paste and keyboard-friendly task lists."""
    def insertFromMimeData(self, source):
        self.insertPlainText(source.text())

    def keyPressEvent(self, event):
        if self.isReadOnly():
            super().keyPressEvent(event)
            return
        cursor = self.textCursor()
        if not self.isReadOnly() and not is_code(cursor.block()) and not cursor.hasSelection():
            line = cursor.block().text()
            if cursor.atBlockEnd() and event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                fence = re.fullmatch(r'```([a-zA-Z0-9_+.-]*)', line)
                if fence:
                    cursor.beginEditBlock()
                    cursor.select(QTextCursor.SelectionType.BlockUnderCursor)
                    cursor.removeSelectedText()
                    fmt = cursor.blockFormat()
                    fmt.setProperty(LANG, fence.group(1))
                    fmt.setProperty(FENCE, '`')
                    fmt.setNonBreakableLines(True)
                    cursor.setBlockFormat(fmt)
                    cursor.endEditBlock()
                    self.setTextCursor(cursor)
                    self.restyle()
                    return
        if event.key() == Qt.Key.Key_Tab:
            self.insertPlainText("    ")
            return
        super().keyPressEvent(event)

    def mousePressEvent(self, event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            from PySide6.QtCore import QUrl
            anchor = self.anchorAt(event.position().toPoint())
            if anchor.startswith(("https://", "http://", "mailto:")):
                QDesktopServices.openUrl(QUrl(anchor))
                return
        cursor = self.cursorForPosition(event.position().toPoint())
        block = cursor.blockFormat()
        marker = block.marker()
        if not self.isReadOnly() and marker != QTextBlockFormat.MarkerType.NoMarker:
            start = QTextCursor(cursor.block())
            x = self.cursorRect(start).left()
            if x - 30 <= event.position().x() < x:
                block.setMarker(QTextBlockFormat.MarkerType.Checked if marker == QTextBlockFormat.MarkerType.Unchecked else QTextBlockFormat.MarkerType.Unchecked)
                cursor.setBlockFormat(block)
                return
        super().mousePressEvent(event)


class PreviewLabel(QLabel):
    def __init__(self, text, two_lines=False):
        super().__init__()
        self.original = text
        self.two_lines = two_lines
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setMinimumWidth(0)

    def resizeEvent(self, event):
        metrics = self.fontMetrics()
        width = max(1, self.width())
        if self.two_lines:
            words = self.original.split()
            first = ""
            while words and metrics.horizontalAdvance((first + " " + words[0]).strip()) <= width:
                first = (first + " " + words.pop(0)).strip()
            if not first and words:
                first = metrics.elidedText(words.pop(0), Qt.TextElideMode.ElideRight, width)
            rest = metrics.elidedText(" ".join(words), Qt.TextElideMode.ElideRight, width)
            self.setText(first + ("\n" + rest if rest else ""))
        else:
            self.setText(metrics.elidedText(self.original, Qt.TextElideMode.ElideRight, width))
        super().resizeEvent(event)


class NoteCard(QWidget):
    def __init__(self, note):
        super().__init__()
        self.setObjectName("card")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        box = QVBoxLayout(self)
        box.setContentsMargins(16, 15, 14, 14)
        box.setSpacing(7)
        title = PreviewLabel(("⌁  " if note["pinned"] else "") + (note["title"].strip() or "Untitled note"))
        title.setObjectName("cardTitle")
        title.setTextFormat(Qt.TextFormat.PlainText)
        title.setWordWrap(False)
        box.addWidget(title)
        snippet = re.sub(r"\s+", " ", note["plain"]).strip() or "A little space for something new…"
        subtitle = PreviewLabel(snippet, True)
        subtitle.setObjectName("cardSnippet")
        subtitle.setTextFormat(Qt.TextFormat.PlainText)
        subtitle.setWordWrap(False)
        subtitle.setFixedHeight(34)
        box.addWidget(subtitle)
        when = datetime.fromisoformat(note["updated"]).astimezone()
        today = datetime.now().date()
        date = "Today" if when.date() == today else when.strftime("%b %d")
        tags = json.loads(note["tags"])
        footer = label(date + ("   ·   #" + tags[0] if tags else ""), "cardDate")
        footer.setTextFormat(Qt.TextFormat.PlainText)
        box.addWidget(footer)


STYLE = f"""
* {{ font-family: 'Inter', 'DejaVu Sans'; color: {INK}; }}
QMainWindow, QWidget {{ background: white; font-size: 13px; }}
QFrame#header {{ background: white; border-bottom: 1px solid {LINE}; }}
QLabel#brand {{ color: {BLUE}; font-size: 17px; font-weight: 700; background: transparent; }}
QLabel#headerHint {{ color: {MUTED}; font-size: 12px; background: transparent; }}
QFrame#sidebar, QWidget#tagContainer, QFrame#sidebar QLabel, QFrame#sidebar QScrollArea {{ background: {PALE}; }}
QWidget#card {{ background: transparent; }}
QLabel#section {{ font-size: 10px; font-weight: 700; letter-spacing: 1.6px; color: {MUTED}; }}
QLabel#small {{ color: {MUTED}; font-size: 11px; }}
QLabel#panelTitle {{ font-size: 23px; font-weight: 700; }}
QLabel#panelCount {{ color: {MUTED}; font-size: 12px; }}
QLabel#cardTitle {{ font-size: 14px; font-weight: 650; background: transparent; }}
QLabel#cardSnippet {{ font-size: 12px; color: {MUTED}; background: transparent; }}
QLabel#cardDate {{ font-size: 10px; color: {MUTED}; background: transparent; }}
QPushButton {{ border: 0; border-radius: 8px; padding: 10px 13px; background: {PALE}; color: {BLUE}; }}
QPushButton:hover {{ background: #e7efff; }}
QPushButton#primary {{ background: {BLUE}; color: white; font-weight: 600; padding: 12px 16px; }}
QPushButton#primary:hover {{ background: #1c51cb; }}
QPushButton#nav {{ text-align: left; border-radius: 8px; padding: 10px 12px; font-size: 12px; color: {MUTED}; background: {PALE}; }}
QPushButton#nav:checked {{ background: #e4edff; color: {BLUE}; font-weight: 650; }}
QPushButton#nav:hover {{ background: #eaf1ff; }}
QToolButton#tool {{ background: transparent; border: 0; border-radius: 7px; color: {BLUE}; font-size: 14px; }}
QToolButton#tool:hover, QToolButton#tool:checked {{ background: #eaf1ff; }}
QToolButton:disabled {{ color: #adc6ed; }}
QLineEdit {{ border: 1px solid {LINE}; border-radius: 8px; padding: 9px 10px; color: {INK}; background: white; selection-background-color: #d5e5ff; selection-color: {INK}; }}
QLineEdit:focus {{ border: 1px solid #8db6ff; }}
QLineEdit#search {{ background: {PALE}; border: 0; padding: 11px 12px; font-size: 12px; }}
QLineEdit#title {{ border: 0; border-radius: 0; padding: 4px 0; font-size: 32px; font-weight: 700; background: white; }}
QLineEdit#tags {{ border: 0; padding: 3px 0; font-size: 12px; color: {BLUE}; }}
QTextEdit {{ border: 0; color: {INK}; background: white; selection-background-color: #d5e5ff; selection-color: {INK}; padding: 0; }}
QListWidget {{ border: 0; background: white; outline: 0; padding: 0 12px; }}
QListWidget::item {{ border-radius: 10px; margin: 3px 0; border: 1px solid transparent; }}
QListWidget::item:selected {{ background: #edf4ff; border: 1px solid #dbe9ff; }}
QListWidget::item:hover:!selected {{ background: #f7faff; }}
QSplitter::handle {{ background: {LINE}; width: 1px; }}
QScrollArea {{ border: 0; }}
QScrollBar:vertical {{ border: 0; background: transparent; width: 7px; margin: 3px; }}
QScrollBar::handle:vertical {{ background: #c8dbf8; min-height: 24px; border-radius: 3px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
QFrame#toolbar {{ border-bottom: 1px solid {LINE}; }}
QFrame#status {{ border-top: 1px solid {LINE}; }}
QLabel#statusText {{ color: {MUTED}; font-size: 11px; background: transparent; }}
QLabel#eyebrow {{ color: {MUTED}; font-size: 10px; font-weight: 600; letter-spacing: 1.4px; }}
QMenu {{ background: white; border: 1px solid {LINE}; padding: 6px; border-radius: 8px; }}
QMenu::item {{ padding: 9px 22px; border-radius: 5px; }}
QMenu::item:selected {{ background: #eaf1ff; color: {BLUE}; }}
QMenu::separator {{ height: 1px; background: {LINE}; margin: 5px; }}
QToolTip {{ color: {INK}; background: #edf4ff; border: 1px solid {LINE}; padding: 6px; }}
QMessageBox, QInputDialog, QFileDialog {{ background: white; }}
QSizeGrip {{ background: transparent; width: 12px; height: 12px; }}
"""

WELCOME = """A quiet place for everything on your mind.

## Make yourself at home

Capture a thought, plan your day, or start something entirely new. Your writing saves automatically, right here on your computer.

### A few little things to know

- **Ctrl + N** creates a fresh note.
- **Ctrl + K** searches your notebook.
- **Ctrl + B** and **Ctrl + I** format your words.
- **Ctrl + Shift + F** gives your writing the whole window.

Add tags beneath your title to keep related thoughts together. Pin a note to keep it close. Deleted notes wait safely in Trash until you choose to remove them.

### Yours to keep

Use the notebook menu at the bottom left to import text or Markdown files, export your notes, or open your local backup folder.

Every good idea starts with a little space.
"""


class Window(QMainWindow):
    def __init__(self, store, settings=None):
        super().__init__()
        self.store = store
        self.settings = settings or QSettings("BlueNotes", "Notes")
        self.current = None
        self.loading = False
        self.dirty = False
        self.scope = "all"
        self.sort = self.settings.value("sort", "updated")
        self.focus_mode = False
        self.mode = 'write'
        self.source_text = None
        self.source_dirty = False
        self.nav_buttons = {}
        self.setWindowTitle("Notes")
        self.setWindowIcon(QIcon(str(HERE / "icon.svg")))
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMinimumSize(1000, 650)
        self.resize(1320, 850)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(400)
        self.timer.timeout.connect(self.save)
        self.backup_timer = QTimer(self)
        self.backup_timer.setInterval(60 * 60 * 1000)
        self.backup_timer.timeout.connect(self.make_backup)
        self.backup_timer.start()
        root = GlassSurface()
        outer = QVBoxLayout(root)
        outer.setContentsMargins(12, 0, 12, 12)
        outer.setSpacing(4)
        self.setCentralWidget(root)
        header = Header()
        header.setObjectName("header")
        header.setFixedHeight(65)
        h = QHBoxLayout(header)
        h.setContentsMargins(22, 0, 12, 0)
        mark = QLabel()
        mark.setPixmap(QIcon(str(HERE / "icon.svg")).pixmap(30, 30))
        h.addWidget(mark)
        h.addSpacing(4)
        h.addWidget(label("notes", "brand"))
        h.addSpacing(21)
        h.addWidget(label("A little space for your thoughts.", "headerHint"))
        h.addStretch()
        self.focus_button = tool("focus", "Focus mode · Ctrl+Shift+F", self.toggle_focus)
        h.addWidget(self.focus_button)
        h.addSpacing(16)
        h.addWidget(tool("min", "Minimize", self.showMinimized))
        h.addWidget(tool("max", "Maximize", self.toggle_maximize))
        h.addWidget(tool("close", "Close", self.close))
        outer.addWidget(header)
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setHandleWidth(10)
        outer.addWidget(self.splitter, 1)
        self.build_sidebar()
        self.build_note_list()
        self.build_editor()
        self.splitter.setSizes([196, 306, 818])
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 0)
        self.splitter.setStretchFactor(2, 1)
        self.shortcuts()
        self.setStyleSheet(STYLE + GLASS_STYLE)
        shadow(self.list_panel, 24, 13, 4)
        shadow(self.stack, 30, 19, 5)
        if self.store.db.execute("SELECT count(*) FROM notes").fetchone()[0] == 0 and not (self.store.directory / ".initialized").exists():
            doc = QTextDocument()
            doc.setDefaultFont(QFont("Inter", 13))
            doc.setMarkdown(WELCOME)
            self.style_document(doc)
            self.store.create("A fresh page.", encode_document(doc), doc.toPlainText(), ["welcome"])
        (self.store.directory / ".initialized").touch()
        self.refresh_nav()
        self.refresh_list()
        last = self.settings.value("last_note", "")
        if last and self.store.get(last) and not self.store.get(last)["deleted"]:
            self.select(last)
        elif self.note_list.count():
            self.note_list.setCurrentRow(0)
        else:
            self.stack.setCurrentIndex(0)
        geometry = self.settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)
        else:
            screen = QApplication.primaryScreen().availableGeometry()
            self.move(screen.center() - self.rect().center())

    def build_sidebar(self):
        self.sidebar = QFrame()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setMinimumWidth(176)
        self.sidebar.setMaximumWidth(240)
        s = QVBoxLayout(self.sidebar)
        s.setContentsMargins(16, 24, 16, 15)
        s.setSpacing(5)
        new = QPushButton("  New note")
        new.setIcon(icon("plus", "white"))
        new.setObjectName("primary")
        new.setToolTip("New note · Ctrl+N")
        new.clicked.connect(self.new_note)
        s.addWidget(new)
        s.addSpacing(28)
        s.addWidget(label("LIBRARY", "section"))
        s.addSpacing(9)
        self.main_nav = QVBoxLayout()
        self.main_nav.setSpacing(4)
        s.addLayout(self.main_nav)
        s.addSpacing(28)
        s.addWidget(label("TAGS", "section"))
        s.addSpacing(8)
        tag_scroll = QScrollArea()
        tag_scroll.setWidgetResizable(True)
        tag_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        tags = QWidget()
        tags.setObjectName("tagContainer")
        self.tags_nav = QVBoxLayout(tags)
        self.tags_nav.setContentsMargins(0, 0, 0, 0)
        self.tags_nav.setSpacing(4)
        self.tags_nav.setAlignment(Qt.AlignmentFlag.AlignTop)
        tag_scroll.setWidget(tags)
        s.addWidget(tag_scroll, 1)
        self.storage_label = label("●  Saved on this computer", "small")
        s.addWidget(self.storage_label)
        s.addSpacing(8)
        menu = QPushButton("  Your notebook                 ···")
        menu.setObjectName("nav")
        menu.clicked.connect(self.notebook_menu)
        s.addWidget(menu)
        self.splitter.addWidget(self.sidebar)

    def build_note_list(self):
        self.list_panel = QFrame()
        self.list_panel.setObjectName('listPanel')
        self.list_panel.setMinimumWidth(262)
        self.list_panel.setMaximumWidth(440)
        lay = QVBoxLayout(self.list_panel)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        top = QWidget()
        t = QVBoxLayout(top)
        t.setContentsMargins(24, 26, 20, 16)
        t.setSpacing(7)
        row = QHBoxLayout()
        self.list_title = label("All notes", "panelTitle")
        row.addWidget(self.list_title, 1)
        row.addWidget(tool("sort", "Sort notes", self.sort_menu))
        t.addLayout(row)
        self.list_count = label("", "panelCount")
        t.addWidget(self.list_count)
        t.addSpacing(15)
        self.search = QLineEdit()
        self.search.setObjectName("search")
        self.search.setPlaceholderText("Search notes…    Ctrl K")
        self.search.setClearButtonEnabled(True)
        self.search.addAction(icon("search"), QLineEdit.ActionPosition.LeadingPosition)
        self.search.textChanged.connect(self.search_changed)
        t.addWidget(self.search)
        lay.addWidget(top)
        self.note_list = QListWidget()
        self.note_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.note_list.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        self.note_list.currentItemChanged.connect(self.changed_selection)
        self.note_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.note_list.customContextMenuRequested.connect(self.note_context_menu)
        lay.addWidget(self.note_list, 1)
        self.empty_list = label("No notes here yet.", "small")
        self.empty_list.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_list.setContentsMargins(10, 0, 10, 30)
        lay.addWidget(self.empty_list)
        self.splitter.addWidget(self.list_panel)

    def build_editor(self):
        self.stack = QStackedWidget()
        self.stack.setObjectName('editorPanel')
        empty = QWidget()
        e = QVBoxLayout(empty)
        e.addStretch()
        symbol = QLabel()
        symbol.setAlignment(Qt.AlignmentFlag.AlignCenter)
        symbol.setPixmap(icon("note", "#a6c5fc", 70).pixmap(70, 70))
        e.addWidget(symbol)
        prompt = label("Room for your next thought.", "panelTitle")
        prompt.setAlignment(Qt.AlignmentFlag.AlignCenter)
        e.addWidget(prompt)
        sub = label("Choose a note, or start with a fresh page.", "panelCount")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        e.addWidget(sub)
        e.addSpacing(16)
        fresh = QPushButton("Create a note")
        fresh.clicked.connect(self.new_note)
        fresh.setObjectName("primary")
        e.addWidget(fresh, 0, Qt.AlignmentFlag.AlignCenter)
        e.addStretch()
        self.stack.addWidget(empty)
        page = QWidget()
        p = QVBoxLayout(page)
        p.setContentsMargins(0, 0, 0, 0)
        p.setSpacing(0)
        self.toolbar = QFrame()
        self.toolbar.setObjectName("toolbar")
        self.toolbar.setFixedHeight(57)
        bar = QHBoxLayout(self.toolbar)
        bar.setContentsMargins(22, 7, 22, 7)
        bar.setSpacing(3)
        self.bold_button = tool(None, "Bold · Ctrl+B", self.bold, "B")
        self.bold_button.setCheckable(True)
        self.bold_button.setFont(QFont("Inter", 12, QFont.Weight.Bold))
        self.italic_button = tool(None, "Italic · Ctrl+I", self.italic, "I")
        self.italic_button.setCheckable(True)
        self.italic_button.setFont(QFont("Inter", 12, -1, True))
        bar.addWidget(self.bold_button)
        bar.addWidget(self.italic_button)
        bar.addWidget(tool(None, "Heading styles", self.heading_menu, "H₁"))
        bar.addSpacing(10)
        bar.addWidget(tool("list", "Bullet list", lambda: self.add_list(False)))
        bar.addWidget(tool("check", "Checklist · Ctrl+Shift+C", lambda: self.add_list(True)))
        bar.addWidget(tool("link", "Insert link · Ctrl+L", self.add_link))
        self.code_button = tool("code", "Insert code block · Ctrl+Shift+K", self.add_code_block)
        bar.addWidget(self.code_button)
        bar.addWidget(tool("plus", "More blocks: inline code, quote, table", self.insert_menu))
        self.format_buttons = [bar.itemAt(i).widget() for i in range(bar.count()) if bar.itemAt(i).widget()]
        bar.addStretch()
        self.pin_button = tool("pin", "Pin note", self.toggle_pin)
        self.pin_button.setCheckable(True)
        bar.addWidget(self.pin_button)
        self.restore_button = tool("restore", "Restore note", self.restore_note)
        bar.addWidget(self.restore_button)
        self.delete_button = tool("trash", "Move to Trash", self.delete_note)
        bar.addWidget(self.delete_button)
        bar.addWidget(tool("more", "Note options", self.note_menu))
        p.addWidget(self.toolbar)
        content = QWidget()
        c = QVBoxLayout(content)
        c.setContentsMargins(48, 37, 43, 22)
        c.setSpacing(12)
        meta_row = QHBoxLayout()
        self.date_label = label("", "eyebrow")
        meta_row.addWidget(self.date_label, 1)
        view_switch = QFrame()
        view_switch.setObjectName('viewSwitch')
        switch = QHBoxLayout(view_switch)
        switch.setContentsMargins(3, 3, 3, 3)
        switch.setSpacing(1)
        self.mode_buttons = {}
        for mode, title in [('write', 'Write'), ('markdown', 'Markdown'), ('preview', 'Read')]:
            button = QPushButton(title)
            button.setObjectName('viewButton')
            button.setCheckable(True)
            button.setChecked(mode == 'write')
            button.clicked.connect(lambda checked=False, m=mode: self.set_mode(m))
            switch.addWidget(button)
            self.mode_buttons[mode] = button
        meta_row.addWidget(view_switch)
        c.addLayout(meta_row)
        self.title = QLineEdit()
        self.title.setObjectName("title")
        self.title.setPlaceholderText("Untitled note")
        self.title.textEdited.connect(self.edited)
        self.title.returnPressed.connect(lambda: self.editor.setFocus())
        c.addWidget(self.title)
        tagrow = QHBoxLayout()
        tagrow.setSpacing(8)
        tag_icon = QLabel()
        tag_icon.setPixmap(icon("tag", MUTED, 14).pixmap(14, 14))
        tagrow.addWidget(tag_icon)
        self.tags = QLineEdit()
        self.tags.setObjectName("tags")
        self.tags.setPlaceholderText("Add tags, separated by commas")
        self.tags.setToolTip("Separate tags with commas. Find them in the sidebar.")
        self.tags.textEdited.connect(self.edited)
        tagrow.addWidget(self.tags)
        c.addLayout(tagrow)
        c.addSpacing(12)
        self.editor = Editor()
        self.editor.setPlaceholderText("Let your thoughts land here…")
        self.editor.setAcceptRichText(True)
        self.editor.setAutoFormatting(QTextEdit.AutoFormattingFlag.AutoBulletList)
        self.editor.setFont(QFont("Inter", 13))
        self.editor.setTextColor(QColor(INK))
        self.editor.document().setDefaultStyleSheet(f"body {{ color: {INK}; }} p {{ margin-bottom: 12px; }} a {{ color: {BLUE}; }}")
        self.editor.textChanged.connect(self.edited)
        self.editor.currentCharFormatChanged.connect(self.update_format_buttons)
        self.editor.setTabStopDistance(32)
        self.document_stack = QStackedWidget()
        self.document_stack.addWidget(self.editor)
        self.source_editor = SourceEditor()
        self.source_editor.textChanged.connect(self.source_edited)
        self.document_stack.addWidget(self.source_editor)
        c.addWidget(self.document_stack, 1)
        self.mode_hint = label('Markdown, made comfortable.   ·   Code blocks: Ctrl Shift K', 'modeHint')
        c.addWidget(self.mode_hint)
        p.addWidget(content, 1)
        status = QFrame()
        status.setObjectName("status")
        s = QHBoxLayout(status)
        s.setContentsMargins(30, 11, 12, 11)
        self.save_label = label("All changes saved", "statusText")
        self.word_label = label("", "statusText")
        s.addWidget(self.save_label)
        s.addStretch()
        s.addWidget(self.word_label)
        s.addSpacing(14)
        s.addWidget(QSizeGrip(self))
        p.addWidget(status)
        self.stack.addWidget(page)
        self.splitter.addWidget(self.stack)

    def shortcuts(self):
        bindings = {"Ctrl+N": self.new_note, "Ctrl+K": self.focus_search,
                    "Ctrl+F": self.focus_search, "Ctrl+S": self.save,
                    "Ctrl+B": self.bold, "Ctrl+I": self.italic,
                    "Ctrl+L": self.add_link, "Ctrl+Shift+C": lambda: self.add_list(True),
                    "Ctrl+Shift+F": self.toggle_focus, "Ctrl+E": self.export_note,
                    "Ctrl+Shift+P": self.toggle_pin,
                    "Ctrl+Shift+K": self.add_code_block,
                    "Ctrl+Shift+V": self.paste_markdown,
                    "Ctrl+Shift+M": lambda: self.set_mode('write' if self.mode == 'markdown' else 'markdown')}
        for key, callback in bindings.items():
            action = QAction(self)
            action.setShortcut(QKeySequence(key))
            action.triggered.connect(callback)
            self.addAction(action)

    def make_backup(self):
        try:
            self.store.backup()
        except Exception as error:
            self.save_label.setText("Backup could not be written")
            self.save_label.setToolTip(str(error))

    def clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().hide()
                item.widget().deleteLater()

    def refresh_nav(self):
        self.clear_layout(self.main_nav)
        self.clear_layout(self.tags_nav)
        self.nav_buttons = {}
        active, pinned, trash, tags = self.store.counts()
        def add(layout, name, key, symbol, count):
            b = QPushButton(f"  {name}   {count}")
            b.setObjectName("nav")
            b.setIcon(icon(symbol, BLUE if key == self.scope else MUTED, 17))
            b.setCheckable(True)
            b.setChecked(self.scope == key)
            b.clicked.connect(lambda checked=False, k=key: self.change_scope(k))
            layout.addWidget(b)
            self.nav_buttons[key] = b
        add(self.main_nav, "All notes", "all", "note", active)
        add(self.main_nav, "Pinned", "pinned", "pin", pinned)
        add(self.main_nav, "Trash", "trash", "trash", trash)
        for tag, count in sorted(tags.items()):
            add(self.tags_nav, tag, "tag:" + tag, "tag", count)
        if not tags:
            hint = label("Tags bring related\nthoughts together.", "small")
            hint.setContentsMargins(10, 8, 0, 0)
            self.tags_nav.addWidget(hint)

    def refresh_list(self):
        notes = self.store.notes(self.scope, self.search.text(), self.sort)
        self.note_list.blockSignals(True)
        self.note_list.clear()
        for note in notes:
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, note["id"])
            item.setSizeHint(QSize(240, 125))
            self.note_list.addItem(item)
            self.note_list.setItemWidget(item, NoteCard(note))
            if self.current == note["id"]:
                self.note_list.setCurrentItem(item)
        self.note_list.blockSignals(False)
        self.list_count.setText(f"{len(notes)} {'note' if len(notes) == 1 else 'notes'}" + (" found" if self.search.text() else " in your notebook"))
        self.empty_list.setVisible(not notes)
        self.empty_list.setText("No matching notes." if self.search.text() else "No notes here yet.")

    def search_changed(self):
        if not self.save(refresh=False):
            return
        self.refresh_list()

    def change_scope(self, key):
        if not self.save():
            return
        self.scope = key
        self.search.blockSignals(True)
        self.search.clear()
        self.search.blockSignals(False)
        self.list_title.setText({"all": "All notes", "pinned": "Pinned", "trash": "Trash"}.get(key, "#" + key[4:]))
        self.current = None
        self.refresh_nav()
        self.refresh_list()
        if self.note_list.count():
            self.note_list.setCurrentRow(0)
        else:
            self.stack.setCurrentIndex(0)

    def select(self, ident):
        for index in range(self.note_list.count()):
            item = self.note_list.item(index)
            if item.data(Qt.ItemDataRole.UserRole) == ident:
                self.note_list.setCurrentItem(item)
                self.note_list.scrollToItem(item)
                if self.current != ident:
                    self.load(ident)
                return

    def changed_selection(self, item, previous):
        if item is None or self.loading:
            return
        ident = item.data(Qt.ItemDataRole.UserRole)
        if ident == self.current:
            return
        if not self.save(refresh=False):
            self.note_list.blockSignals(True)
            self.note_list.setCurrentItem(previous)
            self.note_list.blockSignals(False)
            return
        self.load(ident)

    def load(self, ident):
        note = self.store.get(ident)
        if not note:
            return
        self.loading = True
        self.current = ident
        self.timer.stop()
        self.title.setText(note["title"])
        self.tags.setText(", ".join(json.loads(note["tags"])))
        self.source_dirty = False
        self.source_text = load_document(self.editor.document(), note['body'])
        self.editor.highlighter.rehighlight()
        self.editor.document().setDefaultFont(QFont("Inter", 13))
        if not note["plain"]:
            fmt = QTextCharFormat()
            fmt.setFontPointSize(13)
            fmt.setForeground(QColor(INK))
            self.editor.setCurrentCharFormat(fmt)
            cursor = self.editor.textCursor()
            block = cursor.blockFormat()
            block.setLineHeight(145, QTextBlockFormat.LineHeightTypes.ProportionalHeight.value)
            block.setBottomMargin(10)
            cursor.setBlockFormat(block)
        self.editor.moveCursor(QTextCursor.MoveOperation.Start)
        self.title.setReadOnly(bool(note["deleted"]))
        self.tags.setReadOnly(bool(note["deleted"]))
        self.editor.setReadOnly(bool(note["deleted"]) or self.mode != 'write')
        self.source_editor.setReadOnly(bool(note['deleted']))
        self.pin_button.setChecked(bool(note["pinned"]))
        self.pin_button.setEnabled(not note["deleted"])
        self.restore_button.setVisible(bool(note["deleted"]))
        self.delete_button.setToolTip("Delete permanently" if note["deleted"] else "Move to Trash")
        created = datetime.fromisoformat(note["created"]).astimezone()
        self.date_label.setText(("IN TRASH  ·  " if note["deleted"] else "") + created.strftime("%A, %B %d").upper())
        self.dirty = False
        self.loading = False
        self.set_mode(self.mode)
        self.stack.setCurrentIndex(1)
        self.save_label.setText("In Trash · restore to edit" if note["deleted"] else "All changes saved")
        self.update_words()
        self.update_format_buttons(self.editor.currentCharFormat())

    def edited(self):
        if self.loading or not self.current:
            return
        self.dirty = True
        if self.sender() is self.editor:
            self.source_text = None
        self.save_label.setText("Saving…")
        self.timer.start()
        self.update_words()

    def update_words(self):
        text = self.source_editor.toPlainText() if self.mode == 'markdown' else self.editor.toPlainText()
        words = len(re.findall(r"\S+", text))
        self.word_label.setText(f"{words:,} {'word' if words == 1 else 'words'}  ·  {max(1, round(words / 200))} min read")

    def save(self, refresh=True):
        if self.loading or not self.dirty or not self.current:
            return True
        self.timer.stop()
        try:
            self.sync_source()
            self.store.save(self.current, self.title.text(), encode_document(self.editor.document(), self.source_text),
                            self.editor.toPlainText(), self.tags.text().split(","))
        except Exception as error:
            self.save_label.setText("Could not save — your text is still open")
            self.save_label.setToolTip(str(error))
            QMessageBox.warning(self, "Your note hasn't saved", f"Your writing is still in the editor. Please free disk space or export a copy before closing.\n\n{error}")
            return False
        self.dirty = False
        self.save_label.setText("All changes saved")
        self.save_label.setToolTip("")
        if refresh:
            self.refresh_nav()
            self.refresh_list()
        return True

    def new_note(self):
        if not self.save():
            return
        tags = [self.scope[4:]] if self.scope.startswith("tag:") else []
        ident = self.store.create(tags=tags)
        if self.scope in ("trash", "pinned"):
            self.scope = "all"
            self.list_title.setText("All notes")
        self.search.blockSignals(True)
        self.search.clear()
        self.search.blockSignals(False)
        self.refresh_nav()
        self.refresh_list()
        self.select(ident)
        self.title.setFocus()

    def editable(self):
        return self.current is not None and self.mode == 'write' and not self.editor.isReadOnly()

    def source_edited(self):
        if self.loading or not self.current:
            return
        self.source_dirty = True
        self.source_text = self.source_editor.toPlainText()
        self.dirty = True
        self.save_label.setText('Saving…')
        self.timer.start()
        self.update_words()

    def sync_source(self):
        if not self.source_dirty:
            return
        previous = self.loading
        self.loading = True
        self.source_text = self.source_editor.toPlainText()
        self.editor.document().setMarkdown(self.source_text)
        style_markdown(self.editor.document())
        self.editor.highlighter.rehighlight()
        self.loading = previous
        self.source_dirty = False

    def set_mode(self, mode):
        self.sync_source()
        self.mode = mode
        if mode == 'markdown':
            source = self.source_text if self.source_text is not None else self.editor.document().toMarkdown()
            self.source_editor.blockSignals(True)
            self.source_editor.setPlainText(source)
            self.source_editor.blockSignals(False)
            self.document_stack.setCurrentIndex(1)
        else:
            self.document_stack.setCurrentIndex(0)
        deleted = bool(self.current and self.store.get(self.current)['deleted'])
        self.editor.setReadOnly(deleted or mode != 'write')
        self.source_editor.setReadOnly(deleted)
        for key, button in self.mode_buttons.items():
            button.setChecked(key == mode)
        for button in self.format_buttons:
            button.setEnabled(not deleted and mode == 'write')
        self.code_button.setEnabled(not deleted and mode != 'preview')
        self.mode_hint.setText({'write': 'Code blocks: Ctrl Shift K   ·   Leave a code block: Ctrl Enter',
            'markdown': 'Markdown source   ·   Fenced code, headings, quotes, tables & task lists',
            'preview': 'Reading view   ·   Copy code from any block, or switch to Write to edit'}[mode])
        self.editor.viewport().update()
        self.update_words()

    def insert_menu(self):
        menu = QMenu(self)
        menu.addAction('Code block…', self.add_code_block)
        menu.addAction('Inline code', self.inline_code)
        menu.addAction('Block quote', self.block_quote)
        menu.addAction('Table', self.insert_table)
        menu.addAction('Divider', self.insert_divider)
        menu.addSeparator()
        menu.addAction('Paste as Markdown · Ctrl+Shift+V', self.paste_markdown)
        menu.exec(self.toolbar.mapToGlobal(self.toolbar.rect().bottomLeft()))

    def paste_markdown(self):
        if not self.editable():
            return
        text = QApplication.clipboard().text()
        if not text:
            return
        cursor = self.editor.textCursor()
        cursor.beginEditBlock()
        cursor.insertFragment(QTextDocumentFragment.fromMarkdown(text))
        style_markdown(self.editor.document())
        cursor.endEditBlock()
        self.editor.highlighter.rehighlight()
        self.editor.setFocus()

    def add_code_block(self):
        if not self.current or self.mode == 'preview' or self.store.get(self.current)['deleted']:
            return
        language, ok = QInputDialog.getItem(self, 'Code block', 'Language',
            ['python', 'javascript', 'typescript', 'bash', 'sql', 'json', 'html', 'css', 'text'], 0, True)
        if ok:
            self.insert_code(language.strip())

    def insert_code(self, language, code=None):
        language = re.sub(r'[^a-zA-Z0-9_+.-]', '', language)[:40]
        if self.mode == 'markdown':
            cursor = self.source_editor.textCursor()
            text = code if code is not None else (cursor.selectedText().replace('\u2029', '\n') or 'Write your code here')
            fence = '`' * max(3, max((len(m.group()) + 1 for m in re.finditer(r'`+', text)), default=3))
            cursor.insertText('\n' + fence + language + '\n' + text + '\n' + fence + '\n')
            self.source_editor.setFocus()
            return
        if not self.editable():
            return
        cursor = self.editor.textCursor()
        text = code if code is not None else (cursor.selectedText().replace('\u2029', '\n') or 'Write your code here')
        cursor.beginEditBlock()
        cursor.removeSelectedText()
        normal = QTextCharFormat()
        normal.setFontFamilies(['Noto Sans'])
        normal.setFontPointSize(12)
        normal.setForeground(QColor(INK))
        if cursor.positionInBlock() or cursor.block().text():
            cursor.insertBlock(QTextBlockFormat(), normal)
        start = cursor.position()
        cursor.insertText(text, normal)
        end = cursor.position()
        first = self.editor.document().findBlock(start)
        block = first
        while block.isValid() and block.position() <= end:
            c = QTextCursor(block)
            fmt = block.blockFormat()
            fmt.setProperty(LANG, language)
            fmt.setProperty(FENCE, '`')
            fmt.setNonBreakableLines(True)
            c.setBlockFormat(fmt)
            if block == cursor.block():
                break
            block = block.next()
        cursor.insertBlock(QTextBlockFormat(), normal)
        style_markdown(self.editor.document())
        cursor.endEditBlock()
        cursor.setPosition(start)
        if code is None:
            cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
        self.editor.setTextCursor(cursor)
        self.editor.highlighter.rehighlight()
        self.editor.setFocus()

    def inline_code(self):
        if not self.editable():
            return
        cursor = self.editor.textCursor()
        fmt = QTextCharFormat()
        fmt.setFontFamilies([MONO, 'monospace'])
        fmt.setFontPointSize(11)
        fmt.setFontFixedPitch(True)
        fmt.setForeground(QColor(BLUE))
        fmt.setBackground(QColor('#eaf2ff'))
        if cursor.hasSelection():
            cursor.mergeCharFormat(fmt)
        else:
            cursor.insertText('code', fmt)
        self.editor.setFocus()

    def block_quote(self):
        if not self.editable():
            return
        cursor = self.editor.textCursor()
        fmt = cursor.blockFormat()
        fmt.setProperty(QUOTE, 1)
        fmt.setLeftMargin(20)
        cursor.mergeBlockFormat(fmt)
        self.editor.viewport().update()
        self.editor.setFocus()

    def insert_table(self):
        if not self.editable():
            return
        fmt = QTextTableFormat()
        fmt.setBorder(1)
        fmt.setBorderBrush(QColor('#c8dbfb'))
        fmt.setCellPadding(9)
        fmt.setCellSpacing(0)
        fmt.setHeaderRowCount(1)
        self.editor.textCursor().insertTable(3, 3, fmt)
        style_markdown(self.editor.document())
        self.editor.setFocus()

    def insert_divider(self):
        if self.editable():
            self.editor.textCursor().insertHtml('<hr style="background-color:#dbe8fc;"/><p></p>')
            self.editor.setFocus()

    def bold(self):
        if self.editable():
            fmt = QTextCharFormat()
            fmt.setFontWeight(QFont.Weight.Normal if self.editor.fontWeight() >= QFont.Weight.Bold else QFont.Weight.Bold)
            self.editor.mergeCurrentCharFormat(fmt)
            self.editor.setFocus()

    def italic(self):
        if self.editable():
            fmt = QTextCharFormat()
            fmt.setFontItalic(not self.editor.fontItalic())
            self.editor.mergeCurrentCharFormat(fmt)
            self.editor.setFocus()

    def update_format_buttons(self, fmt):
        self.bold_button.setChecked(fmt.fontWeight() >= QFont.Weight.Bold)
        self.italic_button.setChecked(fmt.fontItalic())

    def heading_menu(self):
        menu = QMenu(self)
        for level, name in [(0, "Body text"), (1, "Heading 1"), (2, "Heading 2"), (3, "Heading 3")]:
            menu.addAction(name, lambda checked=False, n=level: self.heading(n))
        menu.exec(self.toolbar.mapToGlobal(self.toolbar.rect().bottomLeft()))

    def heading(self, level):
        if not self.editable():
            return
        cursor = self.editor.textCursor()
        cursor.beginEditBlock()
        block = cursor.blockFormat()
        block.setHeadingLevel(level)
        block.setTopMargin(18 if level else 0)
        block.setBottomMargin(10)
        cursor.mergeBlockFormat(block)
        if not cursor.hasSelection():
            cursor.select(QTextCursor.SelectionType.BlockUnderCursor)
        fmt = QTextCharFormat()
        fmt.setFontPointSize({0: 13, 1: 24, 2: 19, 3: 15}[level])
        fmt.setFontWeight(QFont.Weight.Bold if level else QFont.Weight.Normal)
        cursor.mergeCharFormat(fmt)
        cursor.endEditBlock()
        self.editor.setFocus()

    def add_list(self, tasks):
        if not self.editable():
            return
        cursor = self.editor.textCursor()
        cursor.beginEditBlock()
        fmt = QTextListFormat()
        fmt.setStyle(QTextListFormat.Style.ListDisc)
        fmt.setIndent(1)
        start, end = cursor.selectionStart(), cursor.selectionEnd()
        cursor.createList(fmt)
        item = QTextCursor(self.editor.document())
        item.setPosition(start)
        while item.position() <= end:
            block = item.blockFormat()
            block.setMarker(QTextBlockFormat.MarkerType.Unchecked if tasks else QTextBlockFormat.MarkerType.NoMarker)
            item.setBlockFormat(block)
            if not item.movePosition(QTextCursor.MoveOperation.NextBlock):
                break
        cursor.endEditBlock()
        self.editor.setFocus()

    def add_link(self):
        if not self.editable():
            return
        url, ok = QInputDialog.getText(self, "Insert link", "Web address", text="https://")
        if not ok or not url.strip():
            return
        url = url.strip()
        if not url.startswith(("https://", "http://", "mailto:")):
            url = "https://" + url
        cursor = self.editor.textCursor()
        selected = cursor.selectedText() or url
        cursor.insertHtml(f'<a href="{html.escape(url, quote=True)}" style="color:{BLUE}">{html.escape(selected)}</a>')
        self.editor.setFocus()

    def toggle_pin(self):
        if not self.current or not self.save():
            return
        note = self.store.get(self.current)
        if note["deleted"]:
            return
        self.store.flag(self.current, "pinned", not note["pinned"])
        self.pin_button.setChecked(not note["pinned"])
        self.refresh_nav()
        self.refresh_list()

    def delete_note(self):
        if not self.current or not self.save():
            return
        note = self.store.get(self.current)
        if note["deleted"]:
            answer = QMessageBox.question(self, "Delete permanently?", "This note will be permanently deleted. You can export a copy first.", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel, QMessageBox.StandardButton.Cancel)
            if answer != QMessageBox.StandardButton.Yes:
                return
            self.store.remove(self.current)
        else:
            self.store.flag(self.current, "deleted", True)
        self.current = None
        self.refresh_nav()
        self.refresh_list()
        if self.note_list.count():
            self.note_list.setCurrentRow(0)
        else:
            self.stack.setCurrentIndex(0)

    def restore_note(self):
        if not self.current:
            return
        ident = self.current
        self.store.flag(ident, "deleted", False)
        self.change_scope("all")
        self.select(ident)

    def duplicate_note(self):
        if not self.current or not self.save():
            return
        original = self.store.get(self.current)
        ident = self.store.create((original["title"] or "Untitled note") + " — copy", original["body"], original["plain"], json.loads(original["tags"]))
        self.change_scope("all")
        self.select(ident)

    def note_context_menu(self, position):
        item = self.note_list.itemAt(position)
        if item:
            self.note_list.setCurrentItem(item)
            self.note_menu(self.note_list.mapToGlobal(position))

    def note_menu(self, position=None):
        if not self.current:
            return
        menu = QMenu(self)
        menu.addAction("Export as Markdown…", self.export_note)
        menu.addAction("Duplicate note", self.duplicate_note)
        menu.addSeparator()
        if self.scope == "trash":
            menu.addAction("Restore note", self.restore_note)
            menu.addAction("Delete permanently…", self.delete_note)
        else:
            menu.addAction("Unpin note" if self.pin_button.isChecked() else "Pin note", self.toggle_pin)
            menu.addAction("Move to Trash", self.delete_note)
        menu.exec(position if position and not isinstance(position, bool) else self.toolbar.mapToGlobal(self.toolbar.rect().bottomRight()))

    def notebook_menu(self):
        menu = QMenu(self)
        menu.addAction("Import Markdown or text…", self.import_notes)
        menu.addAction("Export all notes…", self.export_all)
        menu.addSeparator()
        menu.addAction("Open backup folder", self.open_backups)
        menu.addAction("Keyboard shortcuts", self.show_shortcuts)
        menu.addSeparator()
        menu.addAction("About Notes", lambda: QMessageBox.information(self, "Notes", "Blue Notes 2.0\n\nMarkdown, made comfortable.\nYour notes are stored on this computer.\n\nNo account. No subscription.\nAutomatic daily backups keep the last 14 days used."))
        menu.exec(self.sidebar.mapToGlobal(self.sidebar.rect().bottomLeft()))

    def show_shortcuts(self):
        QMessageBox.information(self, "A few useful shortcuts", "Ctrl+N    New note\nCtrl+K    Search notes\nCtrl+B    Bold\nCtrl+I    Italic\nCtrl+L    Add a link\nCtrl+Shift+K    Code block\nCtrl+Enter    Leave code block\nCtrl+Shift+M    Markdown / Write\nCtrl+Shift+V    Paste as Markdown\nCtrl+Shift+C    Checklist\nCtrl+Shift+P    Pin or unpin\nCtrl+Shift+F    Focus mode\nCtrl+E    Export current note\nCtrl+S    Save now\nCtrl+Z    Undo\nCtrl+Shift+Z    Redo")

    def sort_menu(self):
        menu = QMenu(self)
        for key, name in [("updated", "Last edited"), ("title", "Title A–Z")]:
            action = menu.addAction(name, lambda checked=False, k=key: self.set_sort(k))
            action.setCheckable(True)
            action.setChecked(self.sort == key)
        menu.exec(self.list_title.mapToGlobal(self.list_title.rect().bottomRight()))

    def set_sort(self, key):
        self.sort = key
        self.settings.setValue("sort", key)
        self.refresh_list()

    def focus_search(self):
        if self.focus_mode:
            self.toggle_focus()
        self.search.setFocus()
        self.search.selectAll()

    def toggle_focus(self):
        self.focus_mode = not self.focus_mode
        self.sidebar.setVisible(not self.focus_mode)
        self.list_panel.setVisible(not self.focus_mode)
        self.focus_button.setToolTip("Leave focus mode · Ctrl+Shift+F" if self.focus_mode else "Focus mode · Ctrl+Shift+F")

    def toggle_maximize(self):
        self.showNormal() if self.isMaximized() else self.showMaximized()

    @staticmethod
    def style_document(doc):
        style_markdown(doc)

    @staticmethod
    def markdown(note):
        title = note["title"].strip() or "Untitled note"
        tags = [t.strip().lstrip("#") for t in json.loads(note["tags"]) if t.strip().lstrip("#")]
        return "# " + title + "\n\n" + markdown_body(note['body']) + ("\n\n" + " ".join("#" + t for t in tags) + "\n" if tags else "")

    @staticmethod
    def filename(title):
        return re.sub(r'[^\w .-]', "", title, flags=re.UNICODE).strip(" .")[:100] or "Untitled note"

    def export_note(self):
        if not self.current:
            return
        # Export the live editor, so a failed disk save does not prevent recovery.
        self.sync_source()
        note = {"title": self.title.text(), "body": encode_document(self.editor.document(), self.source_text), "tags": json.dumps(self.tags.text().split(","))}
        path, _ = QFileDialog.getSaveFileName(self, "Export note", str(Path.home() / "Documents" / (self.filename(note["title"]) + ".md")), "Markdown (*.md)")
        if path:
            try:
                Path(path).write_text(self.markdown(note), encoding="utf-8")
                self.save_label.setText("Markdown copy exported")
            except OSError as error:
                QMessageBox.warning(self, "Export failed", str(error))

    def export_all(self):
        if not self.save():
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export your notebook", str(Path.home() / "Documents" / f"Notes-{datetime.now():%Y-%m-%d}.zip"), "ZIP archive (*.zip)")
        if not path:
            return
        try:
            notes = self.store.notes() + self.store.notes("trash")
            with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
                for note in notes:
                    folder = "Trash/" if note["deleted"] else "Notes/"
                    archive.writestr(folder + self.filename(note["title"]) + "-" + note["id"][:8] + ".md", self.markdown(note))
                archive.writestr("notebook.json", json.dumps(notes, ensure_ascii=False, indent=2))
            QMessageBox.information(self, "Notebook exported", f"Exported {len(notes)} notes, including Trash.\n\nThe archive contains Markdown files and a complete JSON copy.")
        except Exception as error:
            QMessageBox.warning(self, "Export failed", str(error))

    def import_notes(self):
        if not self.save():
            return
        paths, _ = QFileDialog.getOpenFileNames(self, "Import notes", str(Path.home() / "Documents"), "Notes (*.md *.markdown *.txt)")
        imported, errors, last = 0, [], None
        for path in paths:
            try:
                text = Path(path).read_text(encoding="utf-8-sig")
                title = Path(path).stem
                doc = QTextDocument()
                doc.setDefaultFont(QFont("Inter", 13))
                if Path(path).suffix.lower() in (".md", ".markdown"):
                    match = re.match(r"^# ([^\n]+)\n+", text)
                    if match:
                        title = match.group(1)
                        text = text[match.end():]
                    doc.setMarkdown(text)
                else:
                    doc.setPlainText(text)
                self.style_document(doc)
                last = self.store.create(title, encode_document(doc, text if Path(path).suffix.lower() != '.txt' else None), doc.toPlainText(), ["imported"])
                imported += 1
            except Exception as error:
                errors.append(Path(path).name + ": " + str(error))
        if last:
            self.change_scope("all")
            self.select(last)
        if errors:
            QMessageBox.warning(self, "Some files could not be imported", f"Imported {imported} notes.\n\n" + "\n".join(errors))

    def open_backups(self):
        from PySide6.QtCore import QUrl
        if not self.save():
            return
        self.make_backup()
        folder = self.store.directory / "backups"
        folder.mkdir(exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    def closeEvent(self, event):
        if not self.save():
            event.ignore()
            return
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("last_note", self.current or "")
        self.settings.sync()
        event.accept()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--new", action="store_true")
    parser.add_argument("--data-dir", type=Path, default=DATA)
    args = parser.parse_args()
    app = QApplication(sys.argv[:1])
    app.setApplicationName("Notes")
    app.setOrganizationName("BlueNotes")
    app.setDesktopFileName("com.bizon.Notes")
    app.setStyle("Fusion")
    app.setFont(QFont("Inter", 10))
    palette = QPalette()
    for role, value in [(QPalette.ColorRole.Window, "white"), (QPalette.ColorRole.Base, "white"), (QPalette.ColorRole.WindowText, INK), (QPalette.ColorRole.Text, INK), (QPalette.ColorRole.Button, PALE), (QPalette.ColorRole.ButtonText, BLUE), (QPalette.ColorRole.Highlight, "#d5e5ff"), (QPalette.ColorRole.HighlightedText, INK), (QPalette.ColorRole.PlaceholderText, MUTED)]:
        palette.setColor(role, QColor(value))
    app.setPalette(palette)
    args.data_dir.mkdir(parents=True, exist_ok=True)
    lock = QLockFile(str(args.data_dir / "app.lock"))
    lock.setStaleLockTime(0)
    server_name = "blue-notes-" + str(os.getuid())
    if not lock.tryLock(100):
        socket = QLocalSocket()
        socket.connectToServer(server_name)
        if socket.waitForConnected(1500):
            socket.write(b"new" if args.new else b"activate")
            socket.waitForBytesWritten(1000)
        else:
            QMessageBox.information(None, "Notes is already open", "Notes is already running. Please use its existing window.")
        return 0
    QLocalServer.removeServer(server_name)
    server = QLocalServer()
    server.listen(server_name)
    try:
        store = Store(args.data_dir)
        window = Window(store)
    except Exception as error:
        QMessageBox.critical(None, "Notes couldn't open", str(error))
        return 1
    def activate():
        socket = server.nextPendingConnection()
        def receive():
            message = bytes(socket.readAll())
            if window.isMinimized():
                window.showNormal()
            window.show()
            window.raise_()
            window.activateWindow()
            if message == b"new":
                window.new_note()
            socket.disconnectFromServer()
        if socket.bytesAvailable():
            receive()
        else:
            socket.readyRead.connect(receive)
    server.newConnection.connect(activate)
    window.show()
    if args.new:
        window.new_note()
    result = app.exec()
    store.close()
    server.close()
    lock.unlock()
    return result


if __name__ == "__main__":
    sys.exit(main())
