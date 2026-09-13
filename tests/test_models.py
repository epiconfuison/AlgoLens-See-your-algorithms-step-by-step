from algoviz.models.state import Cell, History, Snapshot, Variable, changes


def snap(value, seq=1):
    return Snapshot(seq, 1, 'x.cpp', 'main', [], [
        Variable('scope:a', 'a', 'int[2]', kind='array', cells=[Cell((0,), value)])])


def test_changes_use_identity_and_index():
    assert changes(snap(2), snap(1)) == {('scope:a', (0,))}
    other = snap(2)
    other.variables[0].identity = 'other:a'
    assert not changes(other, snap(1))


def test_history_bounded():
    history = History(500)
    for i in range(510):
        history.append(snap(i, i))
    assert len(history.items) == 500
    assert history.items[0].sequence == 10

