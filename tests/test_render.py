import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtWidgets import QApplication
from algoviz.models.state import Cell, Snapshot, Variable
from algoviz.visualization.renderer import Binding, render


def test_render_unicode_negative_matrix_and_overflow(tmp_path):
    app = QApplication.instance() or QApplication([])
    snapshot = Snapshot(1, 8, 'x.cpp', 'main', [], [
        Variable('a', '数组', 'int[3]', kind='array', shape=(3,), total=3,
                 cells=[Cell((0,), -4), Cell((1,), 0), Cell((2,), 8)]),
        Variable('i', 'i', 'int', value=9)])
    image = render(snapshot, 'a', bindings=[Binding('数组', 'i')], mode='bar')
    assert image.width() >= 1000
    path = tmp_path / '图形.png'
    assert image.save(str(path))
    assert path.stat().st_size > 1000
    matrix = Variable('m', 'dp', kind='matrix', shape=(2, 2), total=4,
                      cells=[Cell((r,c), r-c) for r in range(2) for c in range(2)])
    snapshot.variables.append(matrix)
    assert not render(snapshot, 'm').isNull()
    app.processEvents()

