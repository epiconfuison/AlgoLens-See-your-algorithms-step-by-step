import queue
import subprocess
import threading
import time

from algoviz.environment import tool, process_env
from algoviz.processes import CREATE_FLAGS, kill_tree
from .mi import parse_record


class DebugError(RuntimeError):
    pass


class Transport:
    def __init__(self):
        self.process = subprocess.Popen(
            [tool('gdb'), '-nx', '--quiet', '--interpreter=mi2'],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            env=process_env(), creationflags=CREATE_FLAGS)
        self.results = queue.Queue()
        self.stops = queue.Queue()
        self.logs = []
        self.token = 0
        self.closed = threading.Event()
        self.reader = threading.Thread(target=self._read, daemon=True)
        self.reader.start()

    def _read(self):
        try:
            for raw in iter(self.process.stdout.readline, b''):
                try:
                    record = parse_record(raw.decode('utf-8', errors='replace'))
                except (ValueError, IndexError) as exc:
                    self.logs.append(str(exc))
                    continue
                if not record:
                    continue
                if record['kind'] == '^':
                    self.results.put(record)
                elif record['kind'] == '*' and record['cls'] == 'stopped':
                    self.stops.put(record['data'])
                elif record['kind'] in '~&':
                    self.logs.append(record['text'])
                    if len(self.logs) > 1000:
                        del self.logs[:500]
        finally:
            self.closed.set()

    def command(self, command, timeout=15):
        if self.closed.is_set():
            raise DebugError('调试进程已结束')
        self.token += 1
        token = self.token
        try:
            self.process.stdin.write((str(token) + command + '\n').encode('utf-8'))
            self.process.stdin.flush()
        except (OSError, ValueError):
            raise DebugError('无法向 GDB 发送命令')
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                record = self.results.get(timeout=.1)
            except queue.Empty:
                if self.closed.is_set():
                    raise DebugError('调试进程已结束')
                continue
            if record['token'] != token:
                continue
            if record['cls'] == 'error':
                raise DebugError(record['data'].get('msg', 'GDB 命令失败'))
            return record['data']
        raise DebugError('GDB 命令响应超时')

    def wait_stop(self):
        while not self.closed.is_set():
            try:
                return self.stops.get(timeout=.1)
            except queue.Empty:
                pass
        raise DebugError('调试已停止')

    def close(self):
        self.closed.set()
        kill_tree(self.process)
        self.reader.join(timeout=2)
        for stream in (self.process.stdin, self.process.stdout):
            try:
                stream.close()
            except (OSError, ValueError):
                pass

