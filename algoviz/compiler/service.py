from dataclasses import dataclass
from pathlib import Path
import re
import subprocess
import tempfile
import threading

from algoviz.environment import ROOT, tool, process_env
from algoviz.processes import CREATE_FLAGS, kill_tree

HEADERS = '#include <bits/stdc++.h>\nusing namespace std;\n\nint main() {\n'


def prepare_source(code, snippet=False):
    return HEADERS + code + '\nreturn 0;\n}\n' if snippet else code


@dataclass
class Build:
    directory: Path
    source: Path
    executable: Path
    text: str
    diagnostics: str
    success: bool

    @property
    def error_line(self):
        match = re.search(r'program\.cpp:(\d+):\d+:.*error:', self.diagnostics)
        return int(match.group(1)) if match else None


class Compiler:
    def __init__(self):
        self.process = None
        self.cancelled = threading.Event()
        self.lock = threading.Lock()

    def cancel(self):
        self.cancelled.set()
        with self.lock:
            kill_tree(self.process)

    def build(self, text, stdin=''):
        if self.cancelled.is_set():
            raise RuntimeError('编译已取消')
        runs = ROOT / '.runs'
        runs.mkdir(exist_ok=True)
        directory = Path(tempfile.mkdtemp(prefix='session-', dir=str(runs)))
        source = directory / 'program.cpp'
        executable = directory / 'program.exe'
        source.write_text(text, encoding='utf-8')
        (directory / 'stdin.txt').write_text(stdin, encoding='utf-8')
        (directory / 'stdout.txt').write_bytes(b'')
        (directory / 'stderr.txt').write_bytes(b'')
        command = [tool('g++'), '-std=c++17', '-g', '-O0', '-fno-omit-frame-pointer',
                   '-finput-charset=UTF-8', '-fexec-charset=UTF-8', str(source), '-o', str(executable)]
        with self.lock:
            if self.cancelled.is_set():
                raise RuntimeError('编译已取消')
            self.process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                            env=process_env(), creationflags=CREATE_FLAGS)
        try:
            out, err = self.process.communicate(timeout=60)
        except subprocess.TimeoutExpired:
            self.cancel()
            raise RuntimeError('编译超过 60 秒，已终止')
        if self.cancelled.is_set():
            raise RuntimeError('编译已取消')
        return Build(directory, source, executable, text,
                     (out + err).decode('utf-8', errors='replace'), self.process.returncode == 0)

