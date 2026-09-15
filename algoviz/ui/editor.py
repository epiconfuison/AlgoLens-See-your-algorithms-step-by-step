import re
from PySide6.QtCore import Qt, QRect, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QTextCharFormat, QSyntaxHighlighter, QTextFormat
from PySide6.QtWidgets import QPlainTextEdit, QTextEdit, QWidget


class CppHighlighter(QSyntaxHighlighter):
    def highlightBlock(self, text):
        for pattern, color in [
            (r'\b(?:int|float|double|bool|char|void|auto|const|return|for|while|if|else|break|continue|using|namespace|class|struct|public|private|include|size_t)\b', '#91bfff'),
            (r'\b\d+(?:\.\d+)?\b', '#efbb82'),
            (r'"(?:[^"\\]|\\.)*"', '#88d8b0'),
            (r'//.*', '#7b8fa3'),
        ]:
            fmt = QTextCharFormat()
            fmt.setForeground(QColor(color))
            for match in re.finditer(pattern, text):
                self.setFormat(match.start(), match.end() - match.start(), fmt)


class Gutter(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor

    def paintEvent(self, event):
        self.editor.paint_gutter(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.editor.breakpoints_enabled:
            block = self.editor.firstVisibleBlock()
            while block.isValid():
                top = self.editor.blockBoundingGeometry(block).translated(self.editor.contentOffset()).top()
                height = self.editor.blockBoundingRect(block).height()
                if top <= event.position().y() < top + height:
                    line = block.blockNumber() + 1
                    if line in self.editor.breakpoints:
                        self.editor.breakpoints.remove(line)
                    else:
                        self.editor.breakpoints.add(line)
                    self.update()
                    self.editor.breakpointsChanged.emit()
                    break
                block = block.next()


class CodeEditor(QPlainTextEdit):
    breakpointsChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFont(QFont('Consolas', 11))
        self.setStyleSheet('QPlainTextEdit { font-family: Consolas; font-size: 14px; }')
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.setTabStopDistance(self.fontMetrics().horizontalAdvance(' ') * 4)
        self.breakpoints = set()
        self.breakpoints_enabled = True
        self.active_line = 0
        self.gutter = Gutter(self)
        self.highlighter = CppHighlighter(self.document())
        self.blockCountChanged.connect(self.update_margin)
        self.updateRequest.connect(self.update_gutter)
        self.update_margin()

    def update_margin(self, *_):
        self.setViewportMargins(self.gutter_width(), 0, 0, 0)

    def gutter_width(self):
        return 26 + self.fontMetrics().horizontalAdvance('9') * len(str(self.blockCount()))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        r = self.contentsRect()
        self.gutter.setGeometry(QRect(r.left(), r.top(), self.gutter_width(), r.height()))

    def update_gutter(self, rect, dy):
        if dy:
            self.gutter.scroll(0, dy)
        else:
            self.gutter.update(0, rect.y(), self.gutter.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self.update_margin()

    def paint_gutter(self, event):
        painter = QPainter(self.gutter)
        painter.fillRect(event.rect(), QColor('#18232e'))
        block = self.firstVisibleBlock()
        while block.isValid():
            top = int(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
            height = int(self.blockBoundingRect(block).height())
            if top > event.rect().bottom():
                break
            if block.isVisible() and top + height >= event.rect().top():
                line = block.blockNumber() + 1
                painter.setPen(QColor('#7890a5'))
                painter.drawText(20, top, self.gutter.width() - 24, height,
                                 Qt.AlignmentFlag.AlignRight, str(line))
                if line in self.breakpoints:
                    painter.setBrush(QColor('#f37878'))
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.drawEllipse(5, top + max(0, (height - 10) // 2), 10, 10)
            block = block.next()

    def highlight_line(self, line, error=False):
        self.active_line = line
        selected = []
        block = self.document().findBlockByNumber(line - 1)
        if line > 0 and block.isValid():
            item = QTextEdit.ExtraSelection()
            item.format.setBackground(QColor('#5a3039' if error else '#28495d'))
            item.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
            item.cursor = self.textCursor()
            item.cursor.setPosition(block.position())
            item.cursor.clearSelection()
            selected.append(item)
            self.setTextCursor(item.cursor)
            self.ensureCursorVisible()
        self.setExtraSelections(selected)
