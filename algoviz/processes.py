"""Only terminate processes owned by this session."""
import subprocess
import psutil

CREATE_FLAGS = getattr(subprocess, 'CREATE_NO_WINDOW', 0)


def kill_tree(process):
    if process is None or process.poll() is not None:
        return
    try:
        parent = psutil.Process(process.pid)
        children = parent.children(recursive=True)
        for child in reversed(children):
            try:
                child.kill()
            except psutil.NoSuchProcess:
                pass
        parent.kill()
        psutil.wait_procs(children + [parent], timeout=3)
        process.wait(timeout=3)
    except (psutil.NoSuchProcess, subprocess.TimeoutExpired):
        pass

