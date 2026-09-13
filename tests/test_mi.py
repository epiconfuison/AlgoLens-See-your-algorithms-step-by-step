from algoviz.debugger.mi import parse_record


def test_nested_and_repeated_keys():
    record = parse_record('12^done,stack=[frame={level="0",func="main"},frame={level="1",func="f"}]')
    assert record['token'] == 12
    assert record['data']['stack'][1]['frame']['func'] == 'f'


def test_escaped_stream():
    assert parse_record(r'~"a\\b\n\042ok\042"')['text'] == 'a\\b\n"ok"'


def test_utf8_octal():
    assert parse_record(r'~"\344\270\255"')['text'] == '中'


def test_stop():
    assert parse_record('*stopped,reason="exited-normally"')['data']['reason'] == 'exited-normally'

