"""Produce reviewable screenshots from a real debugger session, then exit."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from algoviz.environment import ROOT
from algoviz.ui.window import MainWindow
from tests.test_ui import wait_for, dispose


def main():
    app = QApplication.instance() or QApplication([])
    directory = ROOT / 'artifacts'
    directory.mkdir(exist_ok=True)
    window = MainWindow()
    window.show()
    try:
        for file, marker, container, indexes in [
            ('bubble_sort.cpp', 'a[j] = a[j + 1]', 'a', [('i', 'index'), ('j', 'index')]),
            ('matrix_dp.cpp', 'else dp[row][col]', 'dp', [('row', 'row'), ('col', 'col')]),
        ]:
            window.load_example(file)
            line = next(i for i, s in enumerate(window.editor.toPlainText().splitlines(), 1) if marker in s)
            window.editor.breakpoints = {line}
            window.start()
            wait_for(lambda: window.state in ('paused', 'error'))
            assert window.state == 'paused', window.diagnostics.toPlainText()
            window.debug('continue')
            wait_for(lambda: window.state in ('paused', 'error'))
            assert window.state == 'paused', window.diagnostics.toPlainText()
            window.container.setCurrentText(container)
            for variable, axis in indexes:
                window.index_variable.setCurrentText(variable)
                window.axis.setCurrentIndex(window.axis.findData(axis))
                window.add_binding()
            window.debug('next')
            wait_for(lambda: window.state in ('paused', 'error'))
            QTest.qWait(200)
            stem = file.split('.')[0]
            assert window.grab().save(str(directory / (stem + '-window.png')))
            assert window.image.save(str(directory / (stem + '-canvas.png')))
            window.stop()
            wait_for(lambda: window.worker is None)
        print(str(directory))
    finally:
        dispose(window)
        app.processEvents()


if __name__ == '__main__':
    main()
