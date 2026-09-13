from algoviz.compiler.service import Compiler, prepare_source


def test_snippet_compiles():
    text = prepare_source('vector<int> a{3, 1}; cout << a[0];', True)
    result = Compiler().build(text)
    assert result.success, result.diagnostics
    assert text.splitlines()[4].startswith('vector')


def test_compile_error_location():
    result = Compiler().build('int main() {\n unknown = 1;\n}\n')
    assert not result.success
    assert result.error_line == 2

