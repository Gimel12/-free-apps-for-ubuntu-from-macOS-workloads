"""Portable Markdown metadata and native, syntax-highlighted code blocks."""
import base64
from functools import lru_cache
import html
import json
import re

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import (QColor, QFont, QPainter, QPen, QTextBlockFormat,
    QTextCharFormat, QTextCursor, QTextDocument, QTextFormat, QSyntaxHighlighter,
    QTextTable, QTextLength)
from PySide6.QtWidgets import QApplication, QTextEdit, QPlainTextEdit
from pygments import lex
from pygments.lexers import get_lexer_by_name, TextLexer
from pygments.token import Token

INK = '#15366b'
BLUE = '#2463eb'
MONO = 'Ubuntu Sans Mono'
LANG = QTextFormat.Property.BlockCodeLanguage
FENCE = QTextFormat.Property.BlockCodeFence
QUOTE = QTextFormat.Property.BlockQuoteLevel
META = re.compile(r'<!--blue-notes-v2:([A-Za-z0-9+/=]+)-->')


def is_code(block):
    return block.isValid() and block.blockFormat().hasProperty(FENCE)


def code_group(block):
    first = block
    while is_code(first.previous()):
        first = first.previous()
    blocks = []
    current = first
    while is_code(current):
        blocks.append(current)
        current = current.next()
    return blocks


def metadata(body):
    match = META.search(body)
    if not match:
        return {}
    try:
        value = json.loads(base64.b64decode(match.group(1)).decode('utf-8'))
        return value if isinstance(value, dict) else {}
    except (ValueError, TypeError, UnicodeError):
        return {}


def encode_document(document, source=None):
    blocks = []
    block = document.begin()
    while block.isValid():
        fmt = block.blockFormat()
        data = {'n': block.blockNumber()}
        if fmt.hasProperty(FENCE):
            data.update(code=str(fmt.property(LANG) or ''), fence=str(fmt.property(FENCE) or '`'))
        if fmt.hasProperty(QUOTE):
            data['quote'] = int(fmt.property(QUOTE) or 0)
        if len(data) > 1:
            blocks.append(data)
        block = block.next()
    value = {'markdown': document.toMarkdown() if source is None else source, 'blocks': blocks}
    encoded = base64.b64encode(json.dumps(value, ensure_ascii=False).encode('utf-8')).decode('ascii')
    return document.toHtml() + '\n<!--blue-notes-v2:' + encoded + '-->'


def load_document(document, body):
    value = metadata(body)
    # Qt's HTML reader can normalize table/preformatted block boundaries.
    # Markdown is the canonical v2 source, so fences and languages round-trip
    # without relying on HTML block numbers. Original v1 notes keep their HTML.
    if isinstance(value.get('markdown'), str):
        document.setMarkdown(value['markdown'])
        style_document(document)
        return value['markdown']
    document.setHtml(META.sub('', body))
    for item in value.get('blocks', []):
        block = document.findBlockByNumber(item.get('n', -1))
        if not block.isValid():
            continue
        cursor = QTextCursor(block)
        fmt = block.blockFormat()
        if 'code' in item:
            fmt.setProperty(LANG, item['code'])
            fmt.setProperty(FENCE, item.get('fence', '`'))
            fmt.setNonBreakableLines(True)
        if 'quote' in item:
            fmt.setProperty(QUOTE, item['quote'])
        cursor.setBlockFormat(fmt)
    style_document(document)
    return value.get('markdown')


def markdown_body(body):
    value = metadata(body)
    if isinstance(value.get('markdown'), str):
        return value['markdown']
    doc = QTextDocument()
    load_document(doc, body)
    return doc.toMarkdown()


def style_document(document):
    """Presentation-only formats; code structure is preserved separately in HTML metadata."""
    document.setDefaultFont(QFont('Noto Sans', 12))
    cursor = QTextCursor(document)
    cursor.select(QTextCursor.SelectionType.Document)
    text = QTextCharFormat()
    text.setForeground(QColor(INK))
    cursor.mergeCharFormat(text)
    block = document.begin()
    while block.isValid():
        cursor = QTextCursor(block)
        fmt = block.blockFormat()
        if is_code(block):
            first, last = not is_code(block.previous()), not is_code(block.next())
            fmt.setTopMargin(38 if first else 0)
            fmt.setBottomMargin(22 if last else 0)
            fmt.setLeftMargin(20)
            fmt.setRightMargin(18)
            fmt.setLineHeight(140, QTextBlockFormat.LineHeightTypes.ProportionalHeight.value)
            fmt.setNonBreakableLines(True)
            cursor.setBlockFormat(fmt)
            cursor.select(QTextCursor.SelectionType.BlockUnderCursor)
            char = QTextCharFormat()
            char.setFontFamilies([MONO, 'monospace'])
            char.setFontPointSize(11)
            char.setFontFixedPitch(True)
            char.setFontWeight(QFont.Weight.Normal)
            char.setFontItalic(False)
            char.setBackground(Qt.BrushStyle.NoBrush)
            cursor.mergeCharFormat(char)
        else:
            level = fmt.headingLevel()
            quote = int(fmt.property(QUOTE) or 0)
            fmt.setTopMargin(18 if level else 3)
            fmt.setBottomMargin(10)
            fmt.setLineHeight(145, QTextBlockFormat.LineHeightTypes.ProportionalHeight.value)
            if quote:
                fmt.setLeftMargin(20 * quote)
                fmt.setRightMargin(12)
            cursor.setBlockFormat(fmt)
            if level:
                cursor.select(QTextCursor.SelectionType.BlockUnderCursor)
                char = QTextCharFormat()
                char.setFontPointSize({1: 23, 2: 19, 3: 15}.get(level, 13))
                char.setFontWeight(QFont.Weight.Bold)
                cursor.mergeCharFormat(char)
            # Inline code uses a gentle blue chip, keeping prose fonts untouched.
            iterator = block.begin()
            spans = []
            while not iterator.atEnd():
                fragment = iterator.fragment()
                if fragment.isValid():
                    char = fragment.charFormat()
                    families = ' '.join(char.fontFamilies() or []).lower()
                    if char.fontFixedPitch() or 'mono' in families:
                        spans.append((fragment.position(), fragment.length()))
                iterator += 1
            for start, length in spans:
                inline = QTextCursor(document)
                inline.setPosition(start)
                inline.setPosition(start + length, QTextCursor.MoveMode.KeepAnchor)
                char = QTextCharFormat()
                char.setFontFamilies([MONO, 'monospace'])
                char.setFontPointSize(11)
                char.setBackground(QColor('#eaf2ff'))
                char.setForeground(QColor('#285cb1'))
                inline.mergeCharFormat(char)
        block = block.next()
    def style_frames(frame):
        for child in frame.childFrames():
            if isinstance(child, QTextTable):
                fmt = child.format()
                fmt.setBorder(1)
                fmt.setBorderBrush(QColor('#c9ddfb'))
                fmt.setCellPadding(9)
                fmt.setCellSpacing(0)
                fmt.setWidth(QTextLength(QTextLength.Type.PercentageLength, 100))
                child.setFormat(fmt)
                for col in range(child.columns()):
                    cell = child.cellAt(0, col)
                    char = cell.format()
                    char.setBackground(QColor('#edf4ff'))
                    cell.setFormat(char)
            style_frames(child)
    style_frames(document.rootFrame())


def token_style(token):
    fmt = QTextCharFormat()
    if token in Token.Comment:
        fmt.setForeground(QColor('#7793b9'))
        fmt.setFontItalic(True)
    elif token in Token.Keyword or token in Token.Name.Tag:
        fmt.setForeground(QColor('#134bce'))
        fmt.setFontWeight(QFont.Weight.Bold)
    elif token in Token.Literal.String:
        fmt.setForeground(QColor('#3384d9'))
    elif token in Token.Literal.Number or token in Token.Name.Builtin:
        fmt.setForeground(QColor('#4270c9'))
    elif token in Token.Name.Function or token in Token.Name.Class:
        fmt.setForeground(QColor('#204a91'))
        fmt.setFontWeight(QFont.Weight.Bold)
    else:
        fmt.setForeground(QColor(INK))
    return fmt


@lru_cache(maxsize=24)
def tokens(language, code):
    try:
        lexer = get_lexer_by_name(language or 'text', stripnl=False, ensurenl=False)
    except Exception:
        lexer = TextLexer(stripnl=False, ensurenl=False)
    result, offset = [], 0
    for kind, text in lex(code, lexer):
        # Qt positions count UTF-16 code units, including astral Unicode characters.
        length = len(text.encode('utf-16-le')) // 2
        result.append((offset, length, kind))
        offset += length
    return result


class CodeHighlighter(QSyntaxHighlighter):
    def highlightBlock(self, text):
        block = self.currentBlock()
        if not is_code(block):
            return
        group = code_group(block)
        source = '\n'.join(b.text() for b in group)
        start = block.position() - group[0].position()
        end = start + len(text.encode('utf-16-le')) // 2
        for offset, length, kind in tokens(str(block.blockFormat().property(LANG) or ''), source):
            left, right = max(start, offset), min(end, offset + length)
            if left < right:
                self.setFormat(left - start, right - left, token_style(kind))


class SourceHighlighter(QSyntaxHighlighter):
    def highlightBlock(self, text):
        fence = re.match(r'^\s*(`{3,}|~{3,})(\w*)', text)
        dim, blue = QTextCharFormat(), QTextCharFormat()
        dim.setForeground(QColor('#7793b9'))
        blue.setForeground(QColor(BLUE))
        blue.setFontWeight(QFont.Weight.Bold)
        if fence:
            self.setFormat(0, len(text), blue)
            self.setCurrentBlockState(0 if self.previousBlockState() == 1 else 1)
            return
        if self.previousBlockState() == 1:
            self.setCurrentBlockState(1)
            self.setFormat(0, len(text), dim)
            return
        self.setCurrentBlockState(0)
        if re.match(r'^#{1,6} ', text):
            self.setFormat(0, len(text), blue)
        for pattern in (r'\*\*[^*]+\*\*', r'`[^`]+`', r'\[[^\]]+\]\([^)]+\)', r'^\s*>', r'^\s*[-*+] '):
            for match in re.finditer(pattern, text):
                start = len(text[:match.start()].encode('utf-16-le')) // 2
                length = len(match.group().encode('utf-16-le')) // 2
                self.setFormat(start, length, blue)


class CodeEditor(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.highlighter = CodeHighlighter(self.document())
        self.copy_areas = []
        self.copied_block = -1
        self.viewport().setAutoFillBackground(False)

    def paintEvent(self, event):
        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.copy_areas = []
        block = self.document().begin()
        width = self.viewport().width() - 6
        while block.isValid():
            if is_code(block):
                group = code_group(block)
                first, last = group[0], group[-1]
                top = self.cursorRect(QTextCursor(first)).top() - 29
                bottom = self.cursorRect(QTextCursor(last)).top() + self.document().documentLayout().blockBoundingRect(last).height() + 10
                rect = QRectF(2, top, width - 4, bottom - top)
                if rect.bottom() >= 0 and rect.top() < self.viewport().height():
                    painter.setPen(QPen(QColor('#d9e7ff'), 1))
                    painter.setBrush(QColor('#f0f6ff'))
                    painter.drawRoundedRect(rect, 12, 12)
                    painter.setPen(QColor('#6482af'))
                    painter.setFont(QFont('Noto Sans', 8, QFont.Weight.Medium))
                    language = str(first.blockFormat().property(LANG) or 'code').upper()
                    painter.drawText(QRectF(20, top + 8, 190, 18), Qt.AlignmentFlag.AlignVCenter, language)
                    copy = QRectF(width - 70, top + 5, 60, 24)
                    painter.drawText(copy, Qt.AlignmentFlag.AlignCenter, 'Copied' if self.copied_block == first.blockNumber() else 'Copy')
                    self.copy_areas.append((copy, first.blockNumber(), '\n'.join(b.text() for b in group)))
                block = last.next()
                continue
            if int(block.blockFormat().property(QUOTE) or 0):
                y = self.cursorRect(QTextCursor(block)).top()
                height = self.document().documentLayout().blockBoundingRect(block).height()
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor('#a9c9ff'))
                painter.drawRoundedRect(QRectF(3, y, 3, height), 1.5, 1.5)
            block = block.next()
        painter.end()
        super().paintEvent(event)

    def mousePressEvent(self, event):
        for area, number, text in self.copy_areas:
            if area.contains(event.position()):
                from PySide6.QtCore import QTimer
                QApplication.clipboard().setText(text)
                self.copied_block = number
                self.viewport().update()
                QTimer.singleShot(1600, self.clear_copied)
                return
        super().mousePressEvent(event)

    def clear_copied(self):
        self.copied_block = -1
        self.viewport().update()

    def keyPressEvent(self, event):
        cursor = self.textCursor()
        if not self.isReadOnly() and is_code(cursor.block()):
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                    group = code_group(cursor.block())
                    cursor = QTextCursor(group[-1])
                    cursor.movePosition(QTextCursor.MoveOperation.EndOfBlock)
                    cursor.insertBlock(QTextBlockFormat(), QTextCharFormat())
                    fmt = QTextCharFormat()
                    fmt.setFontFamilies(['Noto Sans'])
                    fmt.setFontPointSize(12)
                    fmt.setForeground(QColor(INK))
                    cursor.setCharFormat(fmt)
                    self.setTextCursor(cursor)
                    return
                indent = re.match(r'^\s*', cursor.block().text()).group()
                super().keyPressEvent(event)
                self.insertPlainText(indent)
                self.restyle()
                return
        super().keyPressEvent(event)

    def restyle(self):
        cursor = self.textCursor()
        cursor.beginEditBlock()
        style_document(self.document())
        cursor.endEditBlock()
        self.highlighter.rehighlight()
        self.viewport().update()


class SourceEditor(QPlainTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('markdownSource')
        self.setFont(QFont(MONO, 11))
        self.setPlaceholderText('Write Markdown here…\n\nUse ```python for a code block.')
        self.highlighter = SourceHighlighter(self.document())
        self.setTabStopDistance(32)

    def keyPressEvent(self, event):
        if self.isReadOnly():
            super().keyPressEvent(event)
            return
        if event.key() == Qt.Key.Key_Tab:
            self.insertPlainText('    ')
            return
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            line = self.textCursor().block().text()
            indent = re.match(r'^\s*', line).group()
            super().keyPressEvent(event)
            self.insertPlainText(indent)
            return
        super().keyPressEvent(event)
