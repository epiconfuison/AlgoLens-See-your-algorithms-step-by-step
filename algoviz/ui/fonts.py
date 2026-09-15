"""Ensure offscreen renders use the same real fonts as the Windows desktop."""
import os
from pathlib import Path
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QApplication


def ensure_fonts():
    app = QApplication.instance()
    if app is None or app.property('algovizFontsReady'):
        return
    families = set(QFontDatabase.families())
    folder = Path(os.environ.get('SystemRoot', 'C:/Windows')) / 'Fonts'
    for family, filename in [('Microsoft YaHei UI', 'msyh.ttc'), ('Consolas', 'consola.ttf')]:
        if family not in families and (folder / filename).is_file():
            QFontDatabase.addApplicationFont(str(folder / filename))
    app.setProperty('algovizFontsReady', True)
