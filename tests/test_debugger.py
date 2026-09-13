from algoviz.compiler.service import Compiler
from algoviz.debugger.engine import Engine
from algoviz.models.state import Snapshot

SOURCE = '''#include <bits/stdc++.h>
using namespace std;
int main() {
    int a[3] = {3, 1, 2};
    vector<int> v{5, 6};
    vector<vector<int>> m{{1,2},{3,4}};
    array<int, 2> b{7,8};
    int i = 1;
    a[i] = 9;
    cout << a[i] << endl;
    return 0;
}
'''


def test_real_variables_step_and_output():
    build = Compiler().build(SOURCE)
    assert build.success, build.diagnostics
    engine = Engine(build)
    try:
        engine.initialize([9])
        first = engine.execute('run')
        assert isinstance(first, Snapshot)
        stop = engine.execute('continue')
        assert stop.line == 9
        values = {v.name: v for v in stop.variables}
        assert [c.value for c in values['a'].cells] == [3, 1, 2], values
        assert [c.value for c in values['v'].cells] == [5, 6], values['v']
        assert [c.value for c in values['m'].cells] == [1, 2, 3, 4], values['m']
        assert [c.value for c in values['b'].cells] == [7, 8], values['b']
        assert values['i'].value == 1
        after = engine.execute('next')
        assert after.line == 10
        assert next(v for v in after.variables if v.name == 'a').cells[1].value == 9
        exited = engine.execute('continue')
        assert exited['state'] == 'exited'
        assert '9' in engine.output()
    finally:
        engine.close()

