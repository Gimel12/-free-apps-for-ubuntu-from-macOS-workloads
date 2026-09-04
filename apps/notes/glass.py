"""Soft, composited white-and-blue glass styling without desktop capture."""
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QColor, QPainter, QLinearGradient, QRadialGradient, QPen, QPainterPath
from PySide6.QtWidgets import QWidget, QGraphicsDropShadowEffect


class GlassSurface(QWidget):
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        bounds = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        base = QLinearGradient(0, 0, self.width(), self.height())
        base.setColorAt(0, QColor('#e7f0ff'))
        base.setColorAt(.5, QColor('#f9fcff'))
        base.setColorAt(1, QColor('#d9e9ff'))
        p.setPen(QPen(QColor(255, 255, 255, 235), 1.5))
        p.setBrush(base)
        p.drawRoundedRect(bounds, 22, 22)
        clip = QPainterPath()
        clip.addRoundedRect(bounds.adjusted(1, 1, -1, -1), 21, 21)
        p.setClipPath(clip)
        for x, y, radius, alpha in [(self.width()*.15, 50, 360, 45), (self.width()*.95, self.height()*.8, 430, 55)]:
            glow = QRadialGradient(x, y, radius)
            glow.setColorAt(0, QColor(125, 174, 255, alpha))
            glow.setColorAt(1, QColor(125, 174, 255, 0))
            p.fillRect(bounds, glow)


def shadow(widget, blur=28, alpha=20, y=5):
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(blur)
    effect.setOffset(0, y)
    effect.setColor(QColor(40, 87, 160, alpha))
    widget.setGraphicsEffect(effect)


GLASS_STYLE = """
QMainWindow, QWidget { background: transparent; }
QFrame#header { background: transparent; border: 0; }
QFrame#sidebar { background: rgba(246,250,255,165); border: 1px solid rgba(255,255,255,245); border-radius: 16px; }
QFrame#sidebar QLabel, QFrame#sidebar QScrollArea, QWidget#tagContainer { background: transparent; }
QFrame#listPanel { background: rgba(255,255,255,190); border: 1px solid rgba(255,255,255,250); border-radius: 16px; }
QStackedWidget#editorPanel { background: rgba(255,255,255,235); border: 1px solid white; border-radius: 16px; }
QSplitter::handle { background: transparent; width: 10px; }
QLabel#brand { font-size: 19px; letter-spacing: -0.6px; }
QLabel#headerHint { color: #7b96bd; }
QPushButton#primary { border: 1px solid #3875f2; border-radius: 12px; background: qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #4484ff,stop:1 #2463eb); }
QPushButton#primary:hover { background: #3979f6; }
QPushButton#nav { background: transparent; border: 1px solid transparent; border-radius: 10px; }
QPushButton#nav:checked { background: rgba(255,255,255,225); border: 1px solid #dbe8fd; }
QPushButton#nav:hover { background: rgba(255,255,255,170); }
QLineEdit#search { background: rgba(233,241,255,170); border: 1px solid #e6efff; border-radius: 12px; }
QLineEdit#title, QLineEdit#tags, QTextEdit { background: transparent; }
QListWidget { background: transparent; padding: 0 10px; }
QListWidget::item { border-radius: 13px; margin: 4px 0; }
QListWidget::item:selected { background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #f5f9ff,stop:1 #e7f0ff); border: 1px solid #cbdffd; }
QListWidget::item:hover:!selected { background: rgba(246,250,255,220); }
QFrame#toolbar { background: transparent; border-bottom: 1px solid #edf3fe; }
QFrame#status { background: transparent; border-top: 1px solid #edf3fe; }
QToolButton#tool { border-radius: 9px; }
QToolButton#tool:hover, QToolButton#tool:checked { background: #eaf2ff; }
QFrame#viewSwitch { background: #edf3fe; border: 1px solid #e1ebfc; border-radius: 10px; }
QPushButton#viewButton { background: transparent; color: #6b89b2; padding: 6px 12px; border: 1px solid transparent; border-radius: 8px; font-size: 11px; }
QPushButton#viewButton:checked { background: white; color: #2463eb; border: 1px solid #dfe9fa; }
QPlainTextEdit#markdownSource { background: #f6f9ff; border: 1px solid #e4edfc; border-radius: 12px; color: #22416d; padding: 18px; selection-background-color: #d5e5ff; font-family: 'Ubuntu Sans Mono'; font-size: 14px; }
QLabel#modeHint { color: #7b96bd; font-size: 10px; }
QDialog, QMessageBox, QInputDialog, QFileDialog { background: #f8fbff; }
"""
