"""Discover tools without changing the user's global PATH."""
import os
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def tool(name):
    variable = 'ALGOVIZ_CXX' if name == 'g++' else 'ALGOVIZ_' + name.upper()
    override = os.environ.get(variable)
    if override and not Path(override).is_file():
        raise RuntimeError(f'{variable} 指向的可执行文件不存在：{override}')
    candidate = Path(override or ('C:/mingw64/bin/' + name + '.exe'))
    if candidate.is_file():
        return str(candidate)
    found = shutil.which(name)
    if not found:
        raise RuntimeError(f'找不到 {name}，请设置 {variable} 为可执行文件路径')
    return found


def process_env():
    env = os.environ.copy()
    env['PATH'] = str(Path(tool('g++')).parent) + os.pathsep + env.get('PATH', '')
    return env


def check():
    import subprocess
    import cv2
    import numpy as np
    from PySide6.QtWidgets import QApplication, QWidget
    app = QApplication.instance() or QApplication([])
    widget = QWidget()
    canvas = np.zeros((20, 20, 3), np.uint8)
    cv2.rectangle(canvas, (1, 1), (10, 10), (0, 255, 0), 1)
    assert canvas.any()
    for name in ('g++', 'gdb'):
        result = subprocess.run([tool(name), '--version'], capture_output=True,
                                env=process_env(), timeout=10)
        if result.returncode:
            raise RuntimeError(result.stderr.decode(errors='replace'))
        print(result.stdout.decode(errors='replace').splitlines()[0])
    result = subprocess.run([tool('gdb'), '-nx', '--interpreter=mi2', '--quiet'],
                            input=b'1-gdb-version\n2-gdb-exit\n', capture_output=True,
                            env=process_env(), timeout=10)
    assert b'1^done' in result.stdout, result.stdout
    print('OpenCV', cv2.__version__, 'Qt window / drawing / GDB MI: OK')
    widget.close()
    app.processEvents()


if __name__ == '__main__':
    check()
