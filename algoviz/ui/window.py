from pathlib import Path
import re

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QFont, QPixmap
from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QListWidget, QMainWindow, QMessageBox, QPlainTextEdit, QPushButton, QScrollArea,
    QSlider, QSpinBox, QSplitter, QTabWidget, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)
from algoviz.compiler.service import prepare_source
from algoviz.environment import ROOT
from algoviz.models.state import History, Snapshot
from algoviz.visualization.renderer import Binding, render
from .editor import CodeEditor
from .fonts import ensure_fonts
from .worker import SessionWorker

STYLE = '''
QWidget { background: #141d27; color: #dce6ef; font-family: 'Microsoft YaHei UI'; font-size: 12px; }
QMainWindow { background: #101821; }
QPushButton { background: #27394a; border: 1px solid #3a5267; padding: 7px 11px; border-radius: 5px; }
QPushButton:hover { background: #36536c; }
QPushButton:disabled { color: #687b8e; background: #1a2632; border-color: #263441; }
QPushButton#primary { background: #247e74; color: white; border-color: #359d90; }
QPushButton#primary:disabled { background: #1a2632; color: #687b8e; border-color: #263441; }
QPlainTextEdit, QLineEdit, QTableWidget, QListWidget { background: #18232e; border: 1px solid #304456; selection-background-color: #36566e; }
QComboBox, QSpinBox { padding: 4px; background: #243544; border: 1px solid #3a5267; }
QTabBar::tab { background: #1e2d3b; padding: 8px 14px; }
QTabBar::tab:selected { background: #30485c; color: #a9e8dd; }
QHeaderView::section { background: #253748; padding: 5px; border: none; }
QSplitter::handle { background: #304456; }
QSlider::groove:horizontal { height: 5px; background: #35495c; }
QSlider::handle:horizontal { background: #7cdbc8; width: 12px; margin: -5px 0; border-radius: 5px; }
QScrollBar:vertical { width: 11px; background: #172330; }
QScrollBar::handle:vertical { background: #476077; min-height: 24px; }
'''


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        ensure_fonts()
        self.setWindowTitle('算法可视化调试器 · C++ / OpenCV')
        self.resize(1500, 980)
        self.setMinimumSize(1080, 720)
        self.setStyleSheet(STYLE)
        self.worker = None
        self.state = 'idle'
        self.history = History()
        self.bindings, self.watches = [], []
        self.pages = {}
        self.image = None
        self.build = None
        self.file_path = None
        self.restart_requested = False
        self.closing = False
        self.playing = False
        self.view_index = -1
        self._make_ui()
        self.play_timer = QTimer(self)
        self.play_timer.setSingleShot(True)
        self.play_timer.timeout.connect(lambda: self.debug('next'))
        self.output_timer = QTimer(self)
        self.output_timer.setInterval(500)
        self.output_timer.timeout.connect(self.update_output)
        self.output_timer.start()
        self.load_example('bubble_sort.cpp', initial=True)
        self.set_state('idle')

    def button(self, row, title, callback, primary=False):
        button = QPushButton(title)
        if primary:
            button.setObjectName('primary')
        button.clicked.connect(callback)
        row.addWidget(button)
        return button

    def _make_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setSpacing(9)
        files = QHBoxLayout()
        title = QLabel('ALGO / 算法实验室')
        title.setStyleSheet('font-size: 20px; font-weight: bold; color: #a2e2d5')
        files.addWidget(title)
        files.addStretch()
        self.open_button = self.button(files, '打开 .cpp', self.open_file)
        self.button(files, '保存代码', self.save_file)
        self.example = QComboBox()
        self.example.addItem('载入示例…', '')
        for name, file in [('冒泡排序', 'bubble_sort.cpp'), ('二分查找', 'binary_search.cpp'),
                           ('二维动态规划', 'matrix_dp.cpp'), ('递归与作用域', 'recursion.cpp')]:
            self.example.addItem(name, file)
        self.example.activated.connect(lambda _: self.load_example(self.example.currentData()))
        files.addWidget(self.example)
        self.button(files, '使用说明', self.show_help)
        layout.addLayout(files)
        controls = QHBoxLayout()
        self.start_button = self.button(controls, '开始 F5', self.start, True)
        self.next_button = self.button(controls, '逐过程 F10', lambda: self.debug('next'))
        self.step_button = self.button(controls, '进入 F11', lambda: self.debug('step'))
        self.finish_button = self.button(controls, '跳出', lambda: self.debug('finish'))
        self.continue_button = self.button(controls, '继续 F5', lambda: self.debug('continue'))
        self.play_button = self.button(controls, '自动单步', self.toggle_play)
        controls.addWidget(QLabel('间隔'))
        self.speed = QSpinBox()
        self.speed.setRange(100, 5000)
        self.speed.setValue(650)
        self.speed.setSingleStep(100)
        self.speed.setSuffix(' ms')
        controls.addWidget(self.speed)
        self.stop_button = self.button(controls, '停止', self.stop)
        self.restart_button = self.button(controls, '重启', self.restart)
        controls.addStretch()
        layout.addLayout(controls)
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.status.setStyleSheet('color: #9bb7cb; padding: 3px')
        layout.addWidget(self.status)
        tip = QLabel('请先初始化变量。调试器可能显示尚未初始化的内存值，不能将这些值作为算法结果。')
        tip.setStyleSheet('color: #b6a384; font-size: 11px')
        layout.addWidget(tip)
        vertical = QSplitter(Qt.Orientation.Vertical)
        main = QSplitter(Qt.Orientation.Horizontal)
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel('代码形式'))
        self.mode = QComboBox()
        self.mode.addItems(['完整程序', '语句片段'])
        mode_row.addWidget(self.mode)
        mode_row.addWidget(QLabel('点击行号左侧设置断点'))
        mode_row.addStretch()
        left_layout.addLayout(mode_row)
        self.code_tabs = QTabWidget()
        self.editor = CodeEditor()
        self.editor.textChanged.connect(self.source_changed)
        self.compiled = CodeEditor()
        self.compiled.setReadOnly(True)
        self.compiled.breakpointsChanged.connect(self.refresh_debugger)
        self.code_tabs.addTab(self.editor, '输入代码')
        self.code_tabs.addTab(self.compiled, '实际编译源码')
        left_layout.addWidget(self.code_tabs)
        main.addWidget(left)
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        visual_row = QHBoxLayout()
        self.container = QComboBox()
        self.container.setMinimumWidth(120)
        self.container.currentIndexChanged.connect(self.draw)
        visual_row.addWidget(self.container, 1)
        self.visual_mode = QComboBox()
        self.visual_mode.addItem('格子 / 热力图', 'grid')
        self.visual_mode.addItem('数值柱状图', 'bar')
        self.visual_mode.currentIndexChanged.connect(self.draw)
        visual_row.addWidget(self.visual_mode)
        self.zoom = QComboBox()
        self.zoom.addItems(['适应宽度', '100%'])
        self.zoom.currentIndexChanged.connect(self.scale_image)
        visual_row.addWidget(self.zoom)
        self.export_button = self.button(visual_row, '导出 PNG', self.export)
        right_layout.addLayout(visual_row)
        self.scroll = QScrollArea()
        self.canvas = QLabel('开始调试后，这里显示变量图形。')
        self.canvas.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.scroll.setWidget(self.canvas)
        right_layout.addWidget(self.scroll, 1)
        page_row = QHBoxLayout()
        self.prev_page = self.button(page_row, '上一页', lambda: self.page(-1))
        self.page_label = QLabel('每页最多 200 个元素')
        page_row.addWidget(self.page_label, 1)
        self.next_page = self.button(page_row, '下一页', lambda: self.page(1))
        right_layout.addLayout(page_row)
        bind_row = QHBoxLayout()
        bind_row.addWidget(QLabel('索引变量'))
        self.index_variable = QComboBox()
        bind_row.addWidget(self.index_variable, 1)
        self.axis = QComboBox()
        self.axis.addItem('数组下标', 'index')
        self.axis.addItem('矩阵行', 'row')
        self.axis.addItem('矩阵列', 'col')
        bind_row.addWidget(self.axis)
        self.bind_button = self.button(bind_row, '绑定', self.add_binding)
        self.button(bind_row, '移除选中', self.remove_binding)
        right_layout.addLayout(bind_row)
        self.binding_list = QListWidget()
        self.binding_list.setMaximumHeight(63)
        right_layout.addWidget(self.binding_list)
        main.addWidget(right)
        main.setSizes([550, 900])
        vertical.addWidget(main)
        self.bottom = QTabWidget()
        self.variables = QTableWidget(0, 4)
        self.variables.setHorizontalHeaderLabels(['变量名', '类型', '当前值 / 尺寸', '状态'])
        self.variables.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.variables.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.variables.cellClicked.connect(self.select_variable)
        vars_widget = QWidget()
        vars_layout = QVBoxLayout(vars_widget)
        vars_layout.setContentsMargins(3, 3, 3, 3)
        vars_layout.addWidget(self.variables)
        watch_row = QHBoxLayout()
        self.watch = QLineEdit()
        self.watch.setPlaceholderText('全局观察项，例如 ::count；只接受变量名或限定名')
        self.watch.returnPressed.connect(self.add_watch)
        watch_row.addWidget(self.watch, 1)
        self.watch_add = self.button(watch_row, '添加观察', self.add_watch)
        self.watch_remove = self.button(watch_row, '移除观察', self.remove_watch)
        vars_layout.addLayout(watch_row)
        self.bottom.addTab(vars_widget, '变量')
        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.bottom.addTab(self.output, '程序输出')
        self.stdin = QPlainTextEdit()
        self.stdin.setPlaceholderText('运行前填写 cin / scanf 所需输入。未提供的输入会读到 EOF。')
        self.bottom.addTab(self.stdin, '标准输入')
        self.stack = QListWidget()
        self.bottom.addTab(self.stack, '调用栈')
        self.diagnostics = QPlainTextEdit()
        self.diagnostics.setReadOnly(True)
        self.bottom.addTab(self.diagnostics, '编译与诊断')
        vertical.addWidget(self.bottom)
        vertical.setSizes([640, 190])
        layout.addWidget(vertical, 1)
        history_row = QHBoxLayout()
        history_row.addWidget(QLabel('历史快照'))
        self.timeline = QSlider(Qt.Orientation.Horizontal)
        self.timeline.setRange(0, 0)
        self.timeline.valueChanged.connect(self.show_snapshot)
        history_row.addWidget(self.timeline, 1)
        self.history_label = QLabel('尚无快照')
        history_row.addWidget(self.history_label)
        self.button(history_row, '回到最新', self.latest)
        layout.addLayout(history_row)
        for shortcut, callback in [('F5', self.f5), ('F10', lambda: self.debug('next')),
                                   ('F11', lambda: self.debug('step')), ('Shift+F11', lambda: self.debug('finish'))]:
            action = QAction(self)
            action.setShortcut(shortcut)
            action.triggered.connect(callback)
            self.addAction(action)

    def set_state(self, state, detail=''):
        self.state = state
        names = {'idle': '就绪', 'compiling': '正在编译', 'running': '正在执行 / 读取变量',
                 'paused': '已暂停', 'stopping': '正在停止', 'stopped': '已停止',
                 'exited': '程序已结束', 'error': '发生错误'}
        self.status.setText(names[state] + (' · ' + detail if detail else '') +
                            '    |    高亮行尚未执行；图形是当前暂停状态。')
        self.update_controls()

    def update_controls(self):
        paused = self.state == 'paused'
        active = self.worker is not None
        for button in (self.next_button, self.step_button, self.finish_button, self.continue_button):
            button.setEnabled(paused and not self.playing)
        self.start_button.setEnabled(not active)
        self.stop_button.setEnabled(active and self.state != 'stopping')
        self.restart_button.setEnabled(self.state != 'stopping')
        self.play_button.setEnabled(paused or self.playing)
        self.play_button.setText('暂停播放' if self.playing else '自动单步')
        self.mode.setEnabled(not active)
        self.example.setEnabled(not active)
        self.open_button.setEnabled(not active)
        self.editor.setReadOnly(active)
        self.editor.breakpoints_enabled = not active
        self.compiled.breakpoints_enabled = paused and not self.playing and self.is_latest()
        self.stdin.setReadOnly(active)
        self.timeline.setEnabled(bool(self.history.items) and self.state not in ('running', 'compiling', 'stopping'))
        self.export_button.setEnabled(self.image is not None)
        self.watch_add.setEnabled(not active or (paused and self.is_latest() and not self.playing))
        self.watch_remove.setEnabled(self.watch_add.isEnabled())
        var = self.selected_container()
        paging = paused and self.is_latest() and not self.playing and var is not None
        self.prev_page.setEnabled(bool(paging and var.offset > 0))
        self.next_page.setEnabled(bool(paging and var.offset + len(var.cells) < var.total))
        self.bind_button.setEnabled(var is not None and self.index_variable.count() > 0)

    def start(self):
        if self.worker is not None:
            return
        code = self.editor.toPlainText()
        if not code.strip():
            self.set_state('idle', '请输入代码')
            return
        text = prepare_source(code, self.mode.currentIndex() == 1)
        shift = 4 if self.mode.currentIndex() == 1 else 0
        self.compiled.setPlainText(text)
        self.compiled.breakpoints = {n + shift for n in self.editor.breakpoints}
        self.compiled.gutter.update()
        self.code_tabs.setCurrentIndex(1)
        self.history.clear()
        self.view_index = -1
        self.image = None
        self.canvas.clear()
        self.container.clear()
        self.variables.setRowCount(0)
        self.stack.clear()
        self.timeline.setRange(0, 0)
        self.history_label.setText('尚无快照')
        self.pages.clear()
        self.output.clear()
        self.diagnostics.clear()
        self.build = None
        self.worker = SessionWorker(text, self.stdin.toPlainText(), self.compiled.breakpoints, self.watches, self)
        self.worker.event.connect(self.on_event)
        self.worker.finished.connect(self.on_finished)
        self.set_state('compiling')
        self.worker.start()

    def source_changed(self):
        # A raw line number must not silently drift to a different statement.
        self.editor.breakpoints.clear()
        self.editor.gutter.update()

    def on_event(self, event):
        if self.state == 'stopping':
            return
        kind = event['kind']
        if kind == 'build':
            self.build = event['build']
            self.diagnostics.setPlainText(self.build.diagnostics or '编译成功')
            if not self.build.success:
                self.set_state('error', '编译失败，查看诊断')
                self.compiled.highlight_line(self.build.error_line or 0, error=True)
                self.bottom.setCurrentWidget(self.diagnostics)
        elif kind == 'running':
            self.set_state('running')
        elif kind == 'warning':
            self.diagnostics.appendPlainText(event['message'])
        elif kind == 'error':
            self.pause_play()
            self.diagnostics.appendPlainText(event['message'])
            self.bottom.setCurrentWidget(self.diagnostics)
            self.set_state('error', event['message'])
        elif kind == 'result':
            result = event['result']
            self.update_output()
            if isinstance(result, Snapshot):
                if event['replace'] and self.history.items:
                    self.history.items[-1] = result
                else:
                    self.history.append(result)
                if result.reason in ('breakpoint-hit', 'signal-received'):
                    self.pause_play()
                reasons = {'breakpoint-hit': '命中断点', 'end-stepping-range': '单步完成',
                           'function-finished': '函数已返回', 'signal-received': '异常信号'}
                self.set_state('paused', result.detail or reasons.get(result.reason, result.reason))
                self.timeline.blockSignals(True)
                self.timeline.setRange(0, len(self.history.items) - 1)
                self.timeline.setValue(len(self.history.items) - 1)
                self.timeline.blockSignals(False)
                self.show_snapshot(len(self.history.items) - 1)
                if self.playing:
                    self.play_timer.start(self.speed.value())
            else:
                self.pause_play()
                self.compiled.highlight_line(0)
                reason, code = result.get('reason', ''), result.get('exit-code', '0')
                abnormal = reason == 'exited-signalled' or code not in ('0', '00')
                detail = ('异常退出' if abnormal else '正常退出') + ' · 退出码 ' + code
                if result.get('signal-name'):
                    detail += ' · ' + result['signal-name']
                self.set_state('error' if abnormal else 'exited', detail)

    def on_finished(self):
        self.update_output()
        old = self.worker
        self.worker = None
        self.pause_play()
        if self.state not in ('error', 'exited'):
            self.set_state('stopped')
        self.update_controls()
        if old:
            old.deleteLater()
        if self.closing:
            self.close()
        elif self.restart_requested:
            self.restart_requested = False
            self.start()

    def stop(self):
        self.pause_play()
        if self.worker:
            self.set_state('stopping')
            self.worker.cancel()

    def restart(self):
        if self.worker:
            self.restart_requested = True
            self.stop()
        else:
            self.start()

    def f5(self):
        if self.worker is None:
            self.start()
        elif self.state == 'paused':
            self.debug('continue')

    def debug(self, action):
        if self.state != 'paused' or not self.worker:
            return
        self.latest()
        self.compiled.highlight_line(0)
        self.set_state('running')
        self.worker.submit(action)

    def toggle_play(self):
        if self.playing:
            self.pause_play()
        elif self.state == 'paused':
            self.playing = True
            self.update_controls()
            self.debug('next')

    def pause_play(self):
        self.playing = False
        self.play_timer.stop()
        self.update_controls()

    def is_latest(self):
        return self.view_index == len(self.history.items) - 1

    def latest(self):
        if self.history.items:
            self.timeline.setValue(len(self.history.items) - 1)
            self.show_snapshot(len(self.history.items) - 1)

    def show_snapshot(self, index):
        if not 0 <= index < len(self.history.items):
            return
        if index != len(self.history.items) - 1:
            self.pause_play()
        self.view_index = index
        snap = self.history.items[index]
        historical = not self.is_latest()
        self.history_label.setText(('历史回看' if historical else '最新快照') + f' #{snap.sequence} / 保留 {len(self.history.items)} 条')
        same_source = self.build and Path(snap.file).resolve() == self.build.source.resolve()
        self.compiled.highlight_line(snap.line if same_source else 0)
        if not same_source:
            self.status.setText(f'暂停于 {snap.function} · {snap.file or "外部代码"}:{snap.line}；可使用跳出返回用户代码。')
        self.variables.setRowCount(len(snap.variables))
        selection = self.container.currentText()
        selected_index = self.index_variable.currentText()
        self.container.blockSignals(True)
        self.container.clear()
        self.index_variable.clear()
        for row, var in enumerate(snap.variables):
            value = str(var.shape) if var.kind in ('array', 'matrix') else str(var.value)
            for col, text in enumerate((var.name, var.type, value, '可读' if var.status == 'ok' else var.status)):
                item = QTableWidgetItem(text)
                item.setToolTip(text + ('\n' + var.identity if col == 0 else ''))
                self.variables.setItem(row, col, item)
            if var.kind in ('array', 'matrix'):
                self.container.addItem(var.name, var.identity)
            elif isinstance(var.value, int) and not isinstance(var.value, bool):
                self.index_variable.addItem(var.name)
        if self.container.findText(selection) >= 0:
            self.container.setCurrentText(selection)
        if self.index_variable.findText(selected_index) >= 0:
            self.index_variable.setCurrentText(selected_index)
        self.container.blockSignals(False)
        self.stack.clear()
        for frame in snap.stack:
            self.stack.addItem(f"#{frame.get('level', '?')}  {frame.get('func', '?')}  {frame.get('file', '')}:{frame.get('line', '')}")
        self.draw()

    def selected_container(self):
        if not 0 <= self.view_index < len(self.history.items):
            return None
        return next((v for v in self.history.items[self.view_index].variables
                     if v.identity == self.container.currentData()), None)

    def draw(self, *_):
        if not 0 <= self.view_index < len(self.history.items):
            return
        snap = self.history.items[self.view_index]
        previous = self.history.items[self.view_index - 1] if self.view_index > 0 else None
        self.image = render(snap, self.container.currentData(), previous,
                            self.bindings, self.visual_mode.currentData())
        self.scale_image()
        var = self.selected_container()
        self.page_label.setText(f'第 {var.offset // 200 + 1} / {max(1, (var.total + 199) // 200)} 页 · {var.total} 个元素'
                                if var else '每页最多 200 个元素')
        self.update_controls()

    def scale_image(self, *_):
        if self.image is not None:
            pixmap = QPixmap.fromImage(self.image)
            if self.zoom.currentIndex() == 0:
                width = max(100, self.scroll.viewport().width() - 4)
                if width < pixmap.width():
                    pixmap = pixmap.scaledToWidth(width, Qt.TransformationMode.SmoothTransformation)
            self.canvas.setPixmap(pixmap)
            self.canvas.resize(pixmap.size())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'scroll'):
            QTimer.singleShot(0, self.scale_image)

    def select_variable(self, row, _):
        if self.variables.item(row, 0):
            name = self.variables.item(row, 0).text()
            self.container.setCurrentText(name)
            if name in self.watches:
                self.watch.setText(name)

    def page(self, delta):
        var = self.selected_container()
        if var and self.state == 'paused' and self.is_latest():
            self.pages[var.name] = max(0, var.offset + delta * 200)
            self.refresh_debugger()

    def refresh_debugger(self):
        if self.state == 'paused' and self.worker and self.is_latest():
            shift = 4 if self.mode.currentIndex() == 1 else 0
            self.editor.breakpoints = {n - shift for n in self.compiled.breakpoints
                                       if 1 <= n - shift <= self.editor.blockCount()}
            self.editor.gutter.update()
            self.set_state('running', '更新观察项 / 分页 / 断点')
            self.worker.submit('refresh', {'watches': self.watches, 'pages': self.pages,
                                           'breakpoints': set(self.compiled.breakpoints)})

    def add_watch(self):
        name = self.watch.text().strip()
        if not re.fullmatch(r'(?:::)?[^\W\d]\w*(?:::[^\W\d]\w*)*', name):
            self.status.setText('观察项只接受变量名或命名空间限定名，例如 ::count。')
            return
        if name not in self.watches:
            self.watches.append(name)
            self.refresh_debugger()

    def remove_watch(self):
        name = self.watch.text().strip()
        if name in self.watches:
            self.watches.remove(name)
            self.refresh_debugger()

    def add_binding(self):
        var = self.selected_container()
        if not var or not self.index_variable.currentText():
            return
        axis = self.axis.currentData()
        if (var.kind == 'array' and axis != 'index') or (var.kind == 'matrix' and axis == 'index'):
            self.status.setText('数组请选择数组下标；矩阵请选择行或列。')
            return
        binding = Binding(var.name, self.index_variable.currentText(), axis)
        if binding not in self.bindings:
            self.bindings.append(binding)
            self.binding_list.addItem(f'{binding.container} ← {binding.index} ({self.axis.currentText()})')
            self.draw()

    def remove_binding(self):
        index = self.binding_list.currentRow()
        if index >= 0:
            self.bindings.pop(index)
            self.binding_list.takeItem(index)
            self.draw()

    def update_output(self):
        if self.worker and self.worker.engine:
            try:
                text = self.worker.engine.output()
                if text != self.output.toPlainText():
                    self.output.setPlainText(text)
                    self.output.verticalScrollBar().setValue(self.output.verticalScrollBar().maximum())
            except OSError:
                pass

    def discard_ok(self):
        return not self.editor.document().isModified() or QMessageBox.question(
            self, '未保存的代码', '放弃尚未保存的代码修改？',
            QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel) == QMessageBox.StandardButton.Discard

    def load_example(self, name, initial=False):
        if not name or self.worker or (not initial and not self.discard_ok()):
            return
        path = ROOT / 'examples' / name
        if path.exists():
            self.editor.setPlainText(path.read_text(encoding='utf-8-sig'))
        elif initial:
            self.editor.setPlainText('#include <iostream>\nint main() {\n    int a[3] = {3, 1, 2};\n    a[0] = 1;\n    return 0;\n}\n')
        self.editor.document().setModified(False)
        self.editor.breakpoints.clear()
        self.editor.gutter.update()
        self.mode.setCurrentIndex(0)
        self.code_tabs.setCurrentIndex(0)
        self.file_path = None

    def open_file(self):
        if not self.discard_ok():
            return
        file, _ = QFileDialog.getOpenFileName(self, '打开 C++ 文件', str(ROOT / 'examples'), 'C++ (*.cpp *.cc *.cxx);;所有文件 (*)')
        if file:
            try:
                self.editor.setPlainText(Path(file).read_text(encoding='utf-8-sig'))
                self.editor.document().setModified(False)
                self.editor.breakpoints.clear()
                self.editor.gutter.update()
                self.file_path = file
                self.mode.setCurrentIndex(0)
                self.code_tabs.setCurrentIndex(0)
            except (OSError, UnicodeError) as exc:
                QMessageBox.warning(self, '打开失败', str(exc))

    def save_file(self):
        file, _ = QFileDialog.getSaveFileName(self, '保存输入代码', self.file_path or str(ROOT / 'algorithm.cpp'), 'C++ (*.cpp)')
        if file:
            try:
                Path(file).write_text(self.editor.toPlainText(), encoding='utf-8')
                self.file_path = file
                self.editor.document().setModified(False)
            except OSError as exc:
                QMessageBox.warning(self, '保存失败', str(exc))

    def export(self):
        if self.image is None:
            return
        file, _ = QFileDialog.getSaveFileName(self, '导出当前图形', str(ROOT / 'snapshot.png'), 'PNG (*.png)')
        if file and not self.image.save(file, 'PNG'):
            QMessageBox.warning(self, '导出失败', '无法写入所选路径。')

    def show_help(self):
        QMessageBox.information(self, '使用说明',
            '1. 输入完整 C++17 程序，或选择语句片段。\n'
            '2. 如需 cin 输入，先填写下方标准输入页签。\n'
            '3. 点击开始，在实际编译源码中逐步执行或设置断点。\n'
            '4. 右侧选择数组或矩阵，绑定索引变量。橙色边框表示值发生变化。\n'
            '5. 拖动历史条回看；执行操作自动回到最新状态。\n\n'
            '高亮行尚未执行。同一行多个表达式不保证逐个拆分。\n'
            '请初始化变量；GDB 无法可靠识别所有未初始化值。\n'
            '暂停播放会在当前单步完成后暂停；死循环可用停止结束。\n'
            '只运行你信任的本地代码。本工具不提供执行沙箱。\n'
            '完整文档：docs/usage.md')

    def closeEvent(self, event):
        if not self.closing and not self.discard_ok():
            event.ignore()
            return
        self.closing = True
        if self.worker:
            self.stop()
            event.ignore()
        else:
            event.accept()
