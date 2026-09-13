"""Parser for GDB/MI records, including repeated result keys and C strings."""
import json
import re


class Parser:
    def __init__(self, text):
        self.text, self.i = text, 0

    def string(self):
        self.i += 1
        data = bytearray()
        while self.i < len(self.text):
            char = self.text[self.i]
            self.i += 1
            if char == '"':
                return data.decode('utf-8', errors='replace')
            if char != '\\':
                data.extend(char.encode('utf-8'))
                continue
            char = self.text[self.i]
            self.i += 1
            if char in '01234567':
                digits = char
                for _ in range(2):
                    if self.i < len(self.text) and self.text[self.i] in '01234567':
                        digits += self.text[self.i]
                        self.i += 1
                    else:
                        break
                data.append(int(digits, 8) & 255)
            else:
                data.extend({'n': '\n', 'r': '\r', 't': '\t', 'b': '\b',
                             'f': '\f', 'v': '\v', 'a': '\a'}.get(char, char).encode())
        raise ValueError('unterminated MI string')

    def key(self):
        start = self.i
        while self.i < len(self.text) and self.text[self.i] not in '=,]}':
            self.i += 1
        return self.text[start:self.i]

    def value(self):
        char = self.text[self.i]
        if char == '"':
            return self.string()
        if char == '{':
            self.i += 1
            result = self.results('}')
            self.i += 1
            return result
        if char == '[':
            self.i += 1
            result = []
            while self.i < len(self.text) and self.text[self.i] != ']':
                if self.text[self.i] in '"{[':
                    result.append(self.value())
                else:
                    key = self.key()
                    if self.i < len(self.text) and self.text[self.i] == '=':
                        self.i += 1
                        result.append({key: self.value()})
                    else:
                        result.append(key)
                if self.i < len(self.text) and self.text[self.i] == ',':
                    self.i += 1
            self.i += 1
            return result
        return self.key()

    def results(self, end=''):
        result = {}
        while self.i < len(self.text) and (not end or self.text[self.i] != end):
            if self.text[self.i] == ',':
                self.i += 1
            key = self.key()
            if self.i >= len(self.text) or self.text[self.i] != '=':
                break
            self.i += 1
            result[key] = self.value()
        return result


def parse_record(line):
    match = re.match(r'^(\d*)([\^*+=~@&])(.*)$', line.rstrip('\r\n'))
    if not match:
        return None
    token, kind, tail = match.groups()
    record = {'token': int(token) if token else None, 'kind': kind}
    if kind in '~@&':
        record['text'] = Parser(tail).value()
    else:
        cls, _, rest = tail.partition(',')
        record.update(cls=cls, data=Parser(rest).results())
    return record


def quote(text):
    return json.dumps(str(text), ensure_ascii=True)

