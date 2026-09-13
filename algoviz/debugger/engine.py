"""Real C++ debug session. UI receives only snapshots and state events."""
import json
import math
import re
from pathlib import Path

from algoviz.environment import tool
from algoviz.models.state import Cell, Snapshot, Variable
from .mi import quote
from .transport import DebugError, Transport

PAGE_SIZE = 200


def scalar(value):
    if value == 'true':
        return True
    if value == 'false':
        return False
    if re.fullmatch(r'[-+]?\d+', str(value)):
        return int(value)
    if re.fullmatch(r'[-+]?(?:\d+\.\d*|\d*\.\d+|\d+)(?:[eE][-+]?\d+)?', str(value)):
        try:
            result = float(value)
            return result if math.isfinite(result) else value
        except ValueError:
            pass
    return value


class Engine:
    def __init__(self, build, transport=None):
        self.build = build
        self.mi = transport or Transport()
        self.sequence = 0
        self.last_stop = None
        self.breakpoints = {}
        self.objects = []
        self.watches = []
        self.pages = {}
        self.printer_warning = ''

    def console(self, text):
        return self.mi.command('-interpreter-exec console ' + quote(text))

    def initialize(self, breakpoints=()):
        self.mi.command('-gdb-set pagination off')
        self.mi.command('-gdb-set confirm off')
        self.mi.command('-gdb-set print elements 200')
        self.mi.command('-gdb-set print repeats 0')
        self.mi.command('-environment-cd ' + quote(self.build.directory.as_posix()))
        self.mi.command('-file-exec-and-symbols ' + quote(self.build.executable.as_posix()))
        root = Path(tool('g++')).parent.parent
        printers = sorted((root / 'share').glob('gcc-*/python'))
        if printers:
            try:
                self.console('python import sys; sys.path.insert(0, ' + repr(printers[-1].as_posix()) +
                             '); from libstdcxx.v6.printers import register_libstdcxx_printers; register_libstdcxx_printers(None)')
            except DebugError as exc:
                self.printer_warning = str(exc)
        else:
            self.printer_warning = '未找到 libstdc++ pretty-printer'
        self.mi.command('-enable-pretty-printing')
        helper = repr(Path(__file__).with_name('symbols.py').as_posix())
        self.console("python exec(compile(open(" + helper + ", encoding='utf-8-sig').read(), " + helper + ", 'exec'))")
        self.mi.command('-break-insert -t main')
        self.set_breakpoints(breakpoints)

    def set_breakpoints(self, lines):
        wanted = set(lines)
        for line in set(self.breakpoints) - wanted:
            self.mi.command('-break-delete ' + self.breakpoints.pop(line))
        for line in wanted - set(self.breakpoints):
            data = self.mi.command('-break-insert ' + quote(self.build.source.as_posix() + ':' + str(line)))
            self.breakpoints[line] = data['bkpt']['number']

    def execute(self, action):
        if action == 'run':
            self.console('run < stdin.txt > stdout.txt 2> stderr.txt')
        else:
            commands = {'next': '-exec-next', 'step': '-exec-step', 'finish': '-exec-finish',
                        'continue': '-exec-continue'}
            self.mi.command(commands[action])
        self.last_stop = self.mi.wait_stop()
        if self.last_stop.get('reason', '').startswith('exited'):
            return {'state': 'exited', **self.last_stop}
        return self.snapshot()

    def _new_object(self, expression):
        data = self.mi.command('-var-create - * ' + quote(expression))
        self.objects.append(data['name'])
        return data

    def _integer(self, expression):
        data = self.mi.command('-data-evaluate-expression ' + quote(expression))
        value = data.get('value', '')
        match = re.match(r'^(-?\d+)', value)
        if not match:
            raise DebugError('无法确定容器尺寸')
        number = int(match.group(1))
        if number < 0 or number > 10_000_000:
            raise DebugError('容器尺寸异常（变量可能尚未初始化）')
        return number

    def _length(self, expression, type_name):
        if re.search(r'\[\d+\]', type_name):
            return self._integer('sizeof(' + expression + ')/sizeof((' + expression + ')[0])')
        if re.search(r'(?:std::)?vector\s*<', type_name):
            return self._integer('(' + expression + ')._M_impl._M_finish - (' + expression + ')._M_impl._M_start')
        if re.search(r'(?:std::)?array\s*<', type_name):
            # Empty std::array has no _M_elems array.
            match = re.search(r',\s*(\d+)\s*(?:ul|ull|u|l)?\s*>\s*$', type_name)
            if match:
                return int(match.group(1))
            return self._integer('sizeof((' + expression + ')._M_elems)/sizeof((' + expression + ')._M_elems[0])')
        return None

    def _element_expression(self, expression, type_name, index):
        if re.search(r'(?:std::)?vector\s*<', type_name):
            return '*((' + expression + ')._M_impl._M_start + ' + str(index) + ')'
        if re.search(r'(?:std::)?array\s*<', type_name):
            return '(' + expression + ')._M_elems[' + str(index) + ']'
        return '(' + expression + ')[' + str(index) + ']'

    def read_variable(self, name, identity, offset=0):
        var = Variable(identity, name)
        try:
            root = self._new_object(name)
            var.type = root.get('type', '')
            var.value = scalar(root.get('value', ''))
            if root.get('value') in ('<optimized out>', '<unavailable>'):
                var.status = root['value']
                return var
            length = self._length(name, var.type)
            if length is None:
                if root.get('numchild', '0') != '0' and 'string' not in var.type:
                    var.kind = 'summary'
                    var.status = '仅类型摘要（首版不支持此结构）'
                return var
            var.kind = 'array'
            var.shape = (length,)
            var.total = length
            first_type = ''
            cols = None
            if length:
                first_expr = self._element_expression(name, var.type, 0)
                first = self._new_object(first_expr)
                first_type = first.get('type', '')
                cols = self._length(first_expr, first_type)
                if cols is not None:
                    var.kind, var.shape, var.total = 'matrix', (length, cols), length * cols
            var.offset = min(max(0, offset // PAGE_SIZE * PAGE_SIZE),
                             max(0, (var.total - 1) // PAGE_SIZE * PAGE_SIZE))
            for flat in range(var.offset, min(var.total, var.offset + PAGE_SIZE)):
                if cols is None:
                    expr = self._element_expression(name, var.type, flat)
                    index = (flat,)
                else:
                    row, col = divmod(flat, cols)
                    row_expr = self._element_expression(name, var.type, row)
                    # Ragged vectors: validate the current row before any element access.
                    row_length = self._length(row_expr, first_type)
                    index = (row, col)
                    if row_length != cols:
                        var.status = '非矩形二维容器：不展示不等长行；请单独观察该行'
                        var.cells.append(Cell(index, '不等长行'))
                        continue
                    expr = self._element_expression(row_expr, first_type, col)
                try:
                    child = self._new_object(expr)
                    value = scalar(child.get('value', '<unavailable>'))
                except DebugError as exc:
                    value = '不可读: ' + str(exc)
                var.cells.append(Cell(index, value))
            if var.total > PAGE_SIZE and var.status == 'ok':
                var.status = '分页显示'
        except (DebugError, ValueError, OverflowError) as exc:
            var.status = '不可读: ' + str(exc)
        return var

    def _symbols(self):
        before = len(self.mi.logs)
        self.console('algoviz-symbols')
        for text in self.mi.logs[before:]:
            if text.startswith('ALGOVIZ_SYMBOLS='):
                return json.loads(text.split('=', 1)[1])
        data = self.mi.command('-stack-list-variables --no-values')
        seen = set()
        result = []
        for item in data.get('variables', []):
            name = item['name']
            if name not in seen:
                result.append({'name': name, 'scope': 'visible'})
                seen.add(name)
        return result

    def snapshot(self):
        if not self.last_stop:
            raise DebugError('程序尚未暂停')
        stack = [item['frame'] for item in self.mi.command('-stack-list-frames 0 30').get('stack', [])]
        frame = self.mi.command('-stack-info-frame').get('frame', {})
        symbols = self._symbols()
        # Frame base uses stack depth / function; block address distinguishes shadowed locals.
        base = frame.get('func', '?') + ':' + str(len(stack))
        variables = []
        names = set()
        for item in symbols:
            name = item['name']
            names.add(name)
            identity = base + ':' + item['scope'] + ':' + name
            variables.append(self.read_variable(name, identity, self.pages.get(name, 0)))
        for name in self.watches:
            if name not in names:
                variables.append(self.read_variable(name, 'watch:' + name, self.pages.get(name, 0)))
        for obj in self.objects:
            try:
                self.mi.command('-var-delete ' + obj)
            except DebugError:
                pass
        self.objects.clear()
        self.sequence += 1
        return Snapshot(self.sequence, int(frame.get('line', 0)), frame.get('fullname', ''),
                        frame.get('func', ''), stack, variables,
                        self.last_stop.get('reason', 'paused'))

    def output(self):
        result = []
        for name in ('stdout.txt', 'stderr.txt'):
            path = self.build.directory / name
            if path.exists():
                # Limit the UI log; the full output remains in the run directory.
                with path.open('rb') as stream:
                    stream.seek(0, 2)
                    length = stream.tell()
                    stream.seek(max(0, length - 100_000))
                    result.append(stream.read().decode('utf-8', errors='replace'))
        return '\n'.join(result)

    def close(self):
        self.mi.close()

