import logging
from io import StringIO
from time import gmtime
from typing import override

from app.lib.logging_formatter import ConsoleFormatter


class _Stream(StringIO):
    def __init__(self, *, isatty: bool):
        super().__init__()
        self._isatty = isatty

    @override
    def isatty(self):
        return self._isatty


def _record(level: int):
    record = logging.LogRecord('root', level, __file__, 1, 'hello', (), None)
    record.created = 0
    return record


def _formatter(stream: _Stream):
    formatter = ConsoleFormatter(
        format='%(levelname)s | %(asctime)s | %(name)s %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        stream=stream,
    )
    formatter.converter = gmtime
    return formatter


def test_console_formatter_keeps_plain_output_for_non_tty(monkeypatch):
    monkeypatch.delenv('FORCE_COLOR', raising=False)
    monkeypatch.delenv('NO_COLOR', raising=False)

    assert (
        _formatter(_Stream(isatty=False)).format(_record(logging.INFO))
        == 'INFO  | 1970-01-01 00:00:00 | root hello'
    )


def test_console_formatter_colors_terminal_output(monkeypatch):
    monkeypatch.delenv('FORCE_COLOR', raising=False)
    monkeypatch.delenv('NO_COLOR', raising=False)

    assert (
        _formatter(_Stream(isatty=True)).format(_record(logging.WARNING))
        == '\x1b[33mWARNING\x1b[0m | \x1b[2m1970-01-01 00:00:00\x1b[0m | root hello'
    )


def test_console_formatter_force_color_overrides_non_tty(monkeypatch):
    monkeypatch.setenv('FORCE_COLOR', '1')
    monkeypatch.delenv('NO_COLOR', raising=False)

    assert '\x1b[32mINFO \x1b[0m' in _formatter(_Stream(isatty=False)).format(
        _record(logging.INFO)
    )


def test_console_formatter_no_color_wins_over_force_color(monkeypatch):
    monkeypatch.setenv('FORCE_COLOR', '1')
    monkeypatch.setenv('NO_COLOR', '1')

    assert '\x1b[' not in _formatter(_Stream(isatty=True)).format(
        _record(logging.ERROR)
    )


def test_console_formatter_disables_color_for_dumb_terminal(monkeypatch):
    monkeypatch.delenv('FORCE_COLOR', raising=False)
    monkeypatch.delenv('NO_COLOR', raising=False)
    monkeypatch.setenv('TERM', 'dumb')

    assert '\x1b[' not in _formatter(_Stream(isatty=True)).format(
        _record(logging.CRITICAL)
    )


def test_console_formatter_force_color_overrides_dumb_terminal(monkeypatch):
    monkeypatch.setenv('FORCE_COLOR', '1')
    monkeypatch.delenv('NO_COLOR', raising=False)
    monkeypatch.setenv('TERM', 'dumb')

    assert '\x1b[1;31mCRITICAL\x1b[0m' in _formatter(_Stream(isatty=False)).format(
        _record(logging.CRITICAL)
    )
