"""One ordered background command queue per debug session."""
import queue
import threading

from PySide6.QtCore import QThread, Signal
from algoviz.compiler.service import Compiler
from algoviz.debugger.engine import Engine
from algoviz.models.state import Snapshot
from algoviz.processes import kill_tree


class SessionWorker(QThread):
    event = Signal(object)

    def __init__(self, source, stdin, breakpoints=(), watches=(), parent=None):
        super().__init__(parent)
        self.source, self.stdin = source, stdin
        self.breakpoints, self.watches = list(breakpoints), list(watches)
        self.compiler = Compiler()
        self.engine = None
        self.commands = queue.Queue()
        self.cancelled = threading.Event()
        self.spawn_lock = threading.Lock()

    def submit(self, action, data=None):
        self.commands.put((action, data))

    def cancel(self):
        self.cancelled.set()
        self.commands.put((None, None))
        # Killing/waiting for a process tree must never block the Qt event loop.
        threading.Thread(target=self._terminate, daemon=True).start()

    def _terminate(self):
        self.compiler.cancel()
        with self.spawn_lock:
            if self.engine:
                kill_tree(self.engine.mi.process)

    def send(self, kind, **data):
        self.event.emit({'kind': kind, **data})

    def run(self):
        try:
            build = self.compiler.build(self.source, self.stdin)
            self.send('build', build=build)
            if not build.success or self.cancelled.is_set():
                return
            with self.spawn_lock:
                if self.cancelled.is_set():
                    return
                self.engine = Engine(build)
            self.engine.watches = self.watches
            self.engine.initialize(self.breakpoints)
            if self.engine.printer_warning:
                self.send('warning', message=self.engine.printer_warning)
            self.send('running')
            result = self.engine.execute('run')
            self.send('result', result=result, replace=False)
            if not isinstance(result, Snapshot):
                return
            while not self.cancelled.is_set():
                action, data = self.commands.get()
                if action is None:
                    return
                try:
                    if action == 'refresh':
                        self.engine.watches = list(data['watches'])
                        self.engine.pages = dict(data['pages'])
                        self.engine.set_breakpoints(data['breakpoints'])
                        result = self.engine.snapshot(advance=False)
                    else:
                        result = self.engine.execute(action)
                    self.send('result', result=result, replace=action == 'refresh')
                    if not isinstance(result, Snapshot):
                        return
                except Exception as exc:
                    if self.cancelled.is_set():
                        return
                    # Uncertain protocol state (e.g. timeout) cannot be treated as paused.
                    self.send('error', message=str(exc))
                    return
        except Exception as exc:
            if not self.cancelled.is_set():
                self.send('error', message=str(exc))
        finally:
            if self.engine:
                self.engine.close()

