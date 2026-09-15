import time
from pathlib import Path

from PySide6.QtTest import QTest
from algoviz.ui.window import MainWindow
from algoviz.models.state import changes


def wait_for(predicate, timeout=30):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        QTest.qWait(20)
        if predicate():
            return
    raise AssertionError('timed out waiting for UI state')


def dispose(window):
    window.editor.document().setModified(False)
    window.stop()
    wait_for(lambda: window.worker is None)
    window.close()


def test_desktop_snippet_step_bind_history_and_export(app, tmp_path):
    window = MainWindow()
    window.show()
    try:
        window.editor.setPlainText('int a[3] = {3, 1, 2};\nint i = 1;\na[i] = 8;\ncout << a[i] << endl;')
        window.mode.setCurrentIndex(1)
        window.editor.breakpoints = {3}
        window.start()
        wait_for(lambda: window.state in ('paused', 'error'))
        assert window.state == 'paused', window.diagnostics.toPlainText()
        assert window.editor.isReadOnly()
        assert 'int main()' in window.compiled.toPlainText()
        assert window.compiled.breakpoints == {7}
        window.debug('continue')
        wait_for(lambda: window.state in ('paused', 'error'))
        assert window.history.items[-1].line == 7
        window.container.setCurrentText('a')
        window.index_variable.setCurrentText('i')
        window.add_binding()
        assert len(window.bindings) == 1
        window.debug('next')
        wait_for(lambda: window.state in ('paused', 'error'))
        snap = window.history.items[-1]
        assert next(v for v in snap.variables if v.name == 'a').cells[1].value == 8
        assert changes(snap, window.history.items[-2])
        window.timeline.setValue(1)
        assert '历史回看' in window.history_label.text()
        assert not window.prev_page.isEnabled()
        window.latest()
        assert window.image.save(str(tmp_path / 'snapshot.png'))
        assert window.grab().save(str(tmp_path / 'window.png'))
        window.debug('continue')
        wait_for(lambda: window.worker is None)
        assert window.state == 'exited'
        assert '8' in window.output.toPlainText()
        assert window.start_button.isEnabled()
    finally:
        dispose(window)


def test_compile_error_and_stop_infinite_loop(app):
    window = MainWindow()
    try:
        window.editor.setPlainText('int main() {\n missing = 1;\n}')
        window.start()
        wait_for(lambda: window.worker is None)
        assert window.state == 'error'
        assert window.compiled.active_line == 2
        window.editor.setPlainText('int main() {\n volatile int i=0;\n while(true) { i = 1; }\n}')
        window.start()
        wait_for(lambda: window.state in ('paused', 'error'))
        assert window.state == 'paused', window.diagnostics.toPlainText()
        window.debug('continue')
        QTest.qWait(100)
        assert window.state == 'running'
        window.stop()
        wait_for(lambda: window.worker is None, 10)
        assert window.state == 'stopped'
    finally:
        dispose(window)
