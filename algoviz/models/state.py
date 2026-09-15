from dataclasses import dataclass, field
from typing import Any, List, Tuple
from collections import deque


@dataclass
class Cell:
    index: Tuple[int, ...]
    value: Any


@dataclass
class Variable:
    identity: str
    name: str
    type: str = ''
    value: Any = ''
    kind: str = 'scalar'
    shape: Tuple[int, ...] = ()
    cells: List[Cell] = field(default_factory=list)
    status: str = 'ok'
    offset: int = 0
    total: int = 0


@dataclass
class Snapshot:
    sequence: int
    line: int
    file: str
    function: str
    stack: list
    variables: List[Variable]
    reason: str = 'end-stepping-range'
    detail: str = ''


class History:
    def __init__(self, limit=500):
        self.items = deque(maxlen=limit)

    def append(self, snapshot):
        self.items.append(snapshot)

    def clear(self):
        self.items.clear()


def changes(current, previous):
    old = {v.identity: v for v in previous.variables} if previous else {}
    result = set()
    for var in current.variables:
        before = old.get(var.identity)
        if before is None:
            continue
        if var.kind == 'scalar' and var.value != before.value:
            result.add((var.identity, ()))
        prior = {c.index: c.value for c in before.cells}
        for cell in var.cells:
            if cell.index in prior and prior[cell.index] != cell.value:
                result.add((var.identity, cell.index))
    return result

