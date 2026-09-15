from contextlib import contextmanager
from pathlib import Path

from algoviz.compiler.service import Compiler
from algoviz.debugger.engine import Engine
from algoviz.environment import ROOT
from algoviz.models.state import Snapshot


@contextmanager
def stopped_at(source, marker, stdin='', watches=()):
    build = Compiler().build(source, stdin)
    assert build.success, build.diagnostics
    engine = Engine(build)
    try:
        line = next(i for i, text in enumerate(source.splitlines(), 1) if marker in text)
        engine.watches = list(watches)
        engine.initialize([line])
        snapshot = engine.execute('run')
        if snapshot.line != line:
            snapshot = engine.execute('continue')
        assert snapshot.line == line
        yield engine, snapshot
    finally:
        engine.close()


def values(snapshot):
    return {v.name: v for v in snapshot.variables}


def test_page_matrix_empty_scalar_and_global_input():
    source = '''#include <bits/stdc++.h>
using namespace std;
int total = 42;
int main() {
    vector<int> large(450, -2);
    large[205] = 777;
    int matrix[2][3] = {{1,2,3}, {4,5,6}};
    int (*pointer)[3] = matrix;
    vector<int> empty;
    array<int, 0> zero{};
    string text = "hello";
    char letter = 'A';
    bool yes = true;
    double negative = -1.25;
    int input = 0;
    cin >> input;
    cout << input << endl; // STOP
    return 0;
}
'''
    with stopped_at(source, '// STOP', '123\n', ['::total', 'missing']) as (engine, snapshot):
        v = values(snapshot)
        assert v['large'].total == 450
        assert len(v['large'].cells) == 200
        assert v['matrix'].shape == (2, 3)
        assert [c.value for c in v['matrix'].cells] == [1, 2, 3, 4, 5, 6]
        assert v['pointer'].kind == 'summary'
        assert not v['pointer'].cells
        assert v['empty'].total == v['zero'].total == 0
        assert 'hello' in v['text'].value
        assert 'A' in v['letter'].value
        assert v['yes'].value is True
        assert v['negative'].value == -1.25
        assert v['input'].value == 123
        assert v['::total'].value == 42
        assert v['missing'].status.startswith('不可读')
        engine.pages['large'] = 200
        next_page = engine.snapshot(advance=False)
        assert next_page.sequence == snapshot.sequence
        large = values(next_page)['large']
        assert large.offset == 200
        assert large.cells[5].value == 777
        engine.pages['large'] = 400
        assert len(values(engine.snapshot())['large'].cells) == 50
        assert engine.execute('continue')['state'] == 'exited'
        assert '123' in engine.output()


def test_shadowed_local_identity_and_scope_exit():
    source = '''int main() {
    int x = 1;
    {
        int x = 5;
        x += 1; // INNER
    }
    x += 2; // OUTER
    return x;
}
'''
    with stopped_at(source, '// INNER') as (engine, snapshot):
        inner = values(snapshot)['x']
        assert inner.value == 5
        line = next(i for i, s in enumerate(source.splitlines(), 1) if '// OUTER' in s)
        engine.set_breakpoints([line])
        outside = engine.execute('continue')
        outer = values(outside)['x']
        assert outer.value == 1
        assert outer.identity != inner.identity


def test_recursive_frames_step_and_finish():
    source = (ROOT / 'examples/recursion.cpp').read_text(encoding='utf-8')
    with stopped_at(source, 'int result = factorial(n);') as (engine, snapshot):
        entered = engine.execute('step')
        assert entered.function == 'factorial'
        assert values(entered)['n'].value == 4
        first_identity = values(entered)['n'].identity
        call_line = next(i for i, s in enumerate(source.splitlines(), 1) if 'result = n *' in s)
        engine.set_breakpoints([call_line])
        outer = engine.execute('continue')
        inner = engine.execute('step')
        assert values(inner)['n'].value == 3
        assert values(inner)['n'].identity != first_identity
        assert len(inner.stack) > len(outer.stack)
        engine.set_breakpoints([])
        finished = engine.execute('finish')
        assert finished.function == 'factorial'
        assert values(finished)['n'].value == 4
        assert engine.execute('continue')['state'] == 'exited'
        assert '24' in engine.output()


def test_signal_is_reported_and_cleanup():
    source = '''int main() {
    volatile int* pointer = nullptr;
    *pointer = 1; // STOP
    return 0;
}
'''
    with stopped_at(source, '// STOP') as (engine, _):
        result = engine.execute('continue')
        assert isinstance(result, Snapshot)
        assert result.reason == 'signal-received'
        assert 'SIGSEGV' in result.detail


def test_unicode_variable_name():
    source = '''int main() {
    int 数值 = 3;
    数值 += 2; // STOP
    return 数值;
}
'''
    with stopped_at(source, '// STOP') as (_, snapshot):
        assert values(snapshot)['数值'].value == 3


def test_bool_vector_ragged_matrix_and_batched_page_budget():
    source = '''#include <bits/stdc++.h>
using namespace std;
int main() {
    vector<bool> flags{true, false, true};
    vector<vector<int>> ragged{{1,2}, {3}};
    int large[205] = {};
    large[204] = 8; // STOP
    return 0;
}
'''
    with stopped_at(source, '// STOP') as (engine, snapshot):
        v = values(snapshot)
        assert [c.value for c in v['flags'].cells] == [True, False, True]
        assert '非矩形' in v['ragged'].status
        assert v['ragged'].cells[-1].value == '不等长行'
        before = engine.mi.token
        engine.snapshot(advance=False)
        assert engine.mi.token - before < 50, 'A page must be batched, not read one element per command'
