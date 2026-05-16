import logging
import os
from collections.abc import Mapping
from typing import Literal, TextIO, override

_RESET = '\x1b[0m'
_DIM = '\x1b[2m'
_LEVEL_WIDTH = len(logging.getLevelName(logging.DEBUG))
_LEVEL_COLORS = {
    level: f'{color}{logging.getLevelName(level):<{_LEVEL_WIDTH}}{_RESET}'
    for level, color in {
        logging.DEBUG: '\x1b[2;36m',
        logging.INFO: '\x1b[32m',
        logging.WARNING: '\x1b[33m',
        logging.ERROR: '\x1b[31m',
        logging.CRITICAL: '\x1b[1;31m',
    }.items()
}


def _env_enabled(name: str):
    value = os.environ.get(name)
    return value is not None and value.lower() not in ('', '0', 'false', 'no')


def _use_color(stream: TextIO):
    if 'NO_COLOR' in os.environ:
        return False
    if _env_enabled('FORCE_COLOR'):
        return True
    if os.environ.get('TERM') == 'dumb':
        return False
    return stream.isatty()


class ConsoleFormatter(logging.Formatter):
    def __init__(
        self,
        fmt: str | None = None,
        datefmt: str | None = None,
        stream: TextIO | None = None,
        style: Literal['%', '{', '$'] = '%',
        validate: bool = True,
        defaults: Mapping[str, object] | None = None,
        format: str | None = None,
    ):
        if format is not None:
            assert fmt is None
            fmt = format

        super().__init__(fmt, datefmt, style, validate, defaults=defaults)
        self._use_color = stream is not None and _use_color(stream)

    @override
    def format(self, record: logging.LogRecord):
        levelname = record.levelname
        if self._use_color and (colored_levelname := _LEVEL_COLORS.get(record.levelno)):
            record.levelname = colored_levelname
        else:
            record.levelname = f'{levelname:<{_LEVEL_WIDTH}}'
        try:
            return super().format(record)
        finally:
            record.levelname = levelname

    @override
    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None):
        text = super().formatTime(record, datefmt)
        return f'{_DIM}{text}{_RESET}' if self._use_color else text
