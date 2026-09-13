"""Loaded inside GDB's Python, not the UI interpreter."""
import gdb
import json


class AlgoSymbols(gdb.Command):
    def __init__(self):
        super().__init__('algoviz-symbols', gdb.COMMAND_DATA)

    def invoke(self, arg, from_tty):
        symbols, seen = [], set()
        try:
            block = gdb.selected_frame().block()
            while block is not None and not block.is_global and not block.is_static:
                for symbol in block:
                    name = symbol.name
                    if name and name not in seen and (symbol.is_variable or symbol.is_argument):
                        seen.add(name)
                        symbols.append({'name': name, 'scope': str(block.start) + ':' + str(symbol.line)})
                block = block.superblock
        except gdb.error:
            pass
        gdb.write('ALGOVIZ_SYMBOLS=' + json.dumps(symbols) + '\n')


AlgoSymbols()

