"""OpenCV geometry and colors; QPainter adds Unicode variable labels."""
from dataclasses import dataclass
import math
import cv2
import numpy as np
from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter
from algoviz.models.state import changes


@dataclass(frozen=True)
class Binding:
    container: str
    index: str
    axis: str = 'index'


def number(value):
    return isinstance(value, (int, float)) and math.isfinite(value)


def render(snapshot, selected=None, previous=None, bindings=(), mode='grid'):
    variables = snapshot.variables
    var = next((v for v in variables if v.identity == selected), None)
    if var is None or var.kind not in ('array', 'matrix'):
        var = next((v for v in variables if v.kind in ('array', 'matrix')), None)
    scalars = [v for v in variables if v.kind not in ('array', 'matrix')]
    scalar_rows = (len(scalars) + 2) // 3
    y_start = 120 + scalar_rows * 82
    matrix_rows = sorted({c.index[0] for c in var.cells}) if var and var.kind == 'matrix' else []
    matrix_cols = sorted({c.index[1] for c in var.cells}) if var and var.kind == 'matrix' else []
    columns = len(matrix_cols) if matrix_cols else 10
    width = max(1060, 110 + columns * 88)
    row_count = len(matrix_rows) if matrix_rows else ((len(var.cells) + 9) // 10 if var else 1)
    is_bar = mode == 'bar' and var and var.kind == 'array'
    if is_bar:
        row_count = (len(var.cells) + 9) // 10
    height = max(540, y_start + 130 + row_count * (210 if is_bar else 94))
    canvas = np.full((height, width, 3), (29, 24, 20), np.uint8)
    labels = []

    def text(x, y, content, size=12, color='#dbe5ef', w=900, h=32):
        labels.append((x, y, str(content), size, color, w, h))

    def rect(x, y, w, h, color, border=None):
        cv2.rectangle(canvas, (x, y), (x + w, y + h), color, -1)
        if border:
            cv2.rectangle(canvas, (x, y), (x + w, y + h), border, 2)

    changed = changes(snapshot, previous)
    text(28, 20, '算法状态  /  ALGORITHM STATE', 19, '#f3f7fc')
    text(28, 57, f'快照 #{snapshot.sequence}   ·   {snapshot.function}   ·   下一执行行 {snapshot.line}', 11, '#93a6bb')
    text(width - 290, 27, '橙色边框 = 本次值发生变化', 10, '#ffbe73', 265)
    for n, scalar_var in enumerate(scalars):
        x, y = 28 + (n % 3) * 338, 104 + (n // 3) * 82
        # Three columns provide readable variable names and full Unicode labels.
        border = (100, 185, 255) if (scalar_var.identity, ()) in changed else None
        rect(x, y, 320, 68, (49, 40, 32), border)
        text(x + 12, y + 4, scalar_var.name, 10, '#91caff', 292, 24)
        value = scalar_var.value if scalar_var.status == 'ok' else scalar_var.status
        text(x + 12, y + 29, value, 13, '#f3f7fc', 292, 30)
    # Actual three-column layout, including room above the container.
    y_start = 120 + ((len(scalars) + 2) // 3) * 82
    if not var:
        text(28, y_start + 15, '当前没有数组或矩阵。单步执行初始化语句后查看变量。', 13)
    else:
        title = var.name + '   ' + ' × '.join(map(str, var.shape))
        text(28, y_start, title, 18, '#f3f7fc')
        note = f'元素 {var.offset}–{var.offset + len(var.cells) - 1} / 共 {var.total}' if var.total else '空容器'
        text(28, y_start + 36, note + '    ' + (var.status if var.status != 'ok' else ''), 10, '#93a6bb')
        bound = []
        notices = []
        by_name = {v.name: v for v in variables}
        for b in bindings:
            if b.container != var.name:
                continue
            v = by_name.get(b.index)
            value = v.value if v else None
            axis = 1 if b.axis == 'col' else 0
            size = var.shape[axis] if axis < len(var.shape) else 0
            if not isinstance(value, int) or isinstance(value, bool):
                notices.append(b.index + '：当前不可用')
            elif value < 0 or value >= size:
                notices.append(f'{b.index}={value} 越界 [0, {size})')
            else:
                bound.append((b, value))
                notices.append(f'{b.index}={value} ({b.axis})')
        text(28, y_start + 64, '   |   '.join(notices), 10, '#8ee4ce')
        top = y_start + 106
        numeric = [float(c.value) for c in var.cells if number(c.value)]
        low, high = (min(numeric), max(numeric)) if numeric else (0, 1)
        scale = max(abs(low), abs(high), 1)
        for n, cell in enumerate(var.cells):
            if var.kind == 'matrix':
                row, col = matrix_rows.index(cell.index[0]), matrix_cols.index(cell.index[1])
            else:
                row, col = divmod(n, 10)
            x, y = 64 + col * 88, top + row * (210 if is_bar else 94)
            markers = []
            for b, value in bound:
                axis = 1 if b.axis == 'col' else 0
                if axis < len(cell.index) and cell.index[axis] == value:
                    markers.append(b.index)
            border = (100, 185, 255) if (var.identity, cell.index) in changed else ((193, 218, 76) if markers else None)
            if is_bar and number(cell.value):
                rect(x, y, 78, 168, (49, 40, 32), border)
                baseline = y + 82
                cv2.line(canvas, (x + 4, baseline), (x + 74, baseline), (125, 116, 106), 1)
                bar = int(float(cell.value) / scale * 56)
                cv2.rectangle(canvas, (x + 17, min(baseline, baseline - bar)),
                              (x + 61, max(baseline, baseline - bar)), (195, 180, 61), -1)
                text(x + 3, y + 134, cell.value, 10, '#ffffff', 73, 27)
                label_y = y + 170
            else:
                color = (65, 55, 42)
                if var.kind == 'matrix' and number(cell.value):
                    fraction = (float(cell.value) - low) / max(high - low, 1)
                    color = (int(90 + 70 * fraction), int(65 + 60 * fraction), 35)
                rect(x, y, 78, 54, color, border)
                text(x + 4, y + 10, cell.value, 12, '#ffffff', 70, 32)
                label_y = y + 55
            text(x + 2, label_y, ','.join(map(str, cell.index)), 9, '#91a4b8', 78, 20)
            if markers:
                cv2.arrowedLine(canvas, (x + 39, y - 16), (x + 39, y - 2), (193, 218, 76), 2, tipLength=.4)
                text(x, label_y + 17, ','.join(markers), 9, '#8ee4ce', 83, 20)
    image = QImage(canvas.data, width, height, canvas.strides[0], QImage.Format.Format_BGR888).copy()
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    for x, y, value, size, color, w, h in labels:
        painter.setFont(QFont('Microsoft YaHei UI', size))
        painter.setPen(QColor(color))
        clipped = painter.fontMetrics().elidedText(value, Qt.TextElideMode.ElideRight, w)
        painter.drawText(QRect(x, y, w, h), Qt.AlignmentFlag.AlignVCenter, clipped)
    painter.end()
    return image

