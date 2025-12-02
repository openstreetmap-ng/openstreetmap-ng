import logging
from collections.abc import Generator, Iterable, Iterator
from contextlib import AbstractContextManager, contextmanager
from time import monotonic
from typing import Protocol, TypedDict, TypeVar, Unpack, overload

import cython

_T = TypeVar('_T')


class _ProgressKwargs(TypedDict, total=False):
    desc: str
    total: int
    level: int


class _Advance(Protocol):
    def __call__(self, n: cython.size_t = 1) -> None: ...


@cython.cfunc
def _format_rate(n: float) -> str:
    """Format rate with K/M/G suffix, 3 significant digits."""
    if n >= 1_000_000_000:
        v, suffix = n / 1_000_000_000, 'G/s'
    elif n >= 1_000_000:
        v, suffix = n / 1_000_000, 'M/s'
    elif n >= 1000:
        v, suffix = n / 1000, 'K/s'
    else:
        return f'{n:.0f}/s'
    if v >= 100:
        return f'{v:.0f}{suffix}'
    if v >= 10:
        return f'{v:.1f}{suffix}'
    return f'{v:.2f}{suffix}'


@cython.cfunc
def _format_time(seconds: float) -> str:
    """Format seconds into human readable time."""
    if seconds < 60:
        return f'{seconds:.0f}s'
    if seconds < 3600:
        minutes, secs = divmod(seconds, 60)
        return f'{minutes:.0f}m{secs:02.0f}s'
    if seconds < 86400:
        hours, remainder = divmod(seconds, 3600)
        minutes, secs = divmod(remainder, 60)
        return f'{hours:.0f}h{minutes:02.0f}m{secs:02.0f}s'
    days, remainder = divmod(seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes = remainder / 60
    return f'{days:.0f}d{hours:02.0f}h{minutes:02.0f}m'


@contextmanager
def _progress_context(
    **kwargs: Unpack[_ProgressKwargs],
) -> Generator[_Advance]:
    desc = kwargs.get('desc')
    total = kwargs.get('total')
    total_str = str(total) if total is not None else ''
    total_width = len(total_str)
    level = kwargs.get('level', logging.INFO)

    current: cython.size_t = 0
    start_time: cython.double = monotonic()
    last_time: cython.double = start_time
    rate_width: cython.size_t = 0

    def log(*, done: str | None = None) -> None:
        nonlocal rate_width
        now: cython.double = monotonic()
        elapsed = now - start_time

        parts: list[str] = []
        if desc:
            parts.append(desc)

        if total:
            parts.append(
                f'{current:>{total_width}}/{total_str} ({current * 100 / total:4.1f}%)'
            )
        else:
            parts.append(str(current))

        rate = current / elapsed
        rate_str = _format_rate(rate)
        rate_width = max(rate_width, len(rate_str))
        parts.append(rate_str.rjust(rate_width))

        if done:
            parts.append(done)
        elif total and rate:
            remaining = (total - current) / rate
            parts.append(f'ETA {_format_time(remaining)}')

        logging.log(level, ' · '.join(parts))

    def advance(n: cython.size_t = 1) -> None:
        nonlocal current, last_time
        current += n
        now: cython.double = monotonic()
        if now - last_time < 5:
            return
        last_time = now
        log()

    yield advance

    log(done=f'Done in {_format_time(monotonic() - start_time)}')


def _progress_iterable(
    iterable: Iterable[_T],
    **kwargs: Unpack[_ProgressKwargs],
) -> Generator[_T]:
    if 'total' not in kwargs and (__len__ := getattr(iterable, '__len__', None)):
        kwargs['total'] = __len__()
    with _progress_context(**kwargs) as advance:
        for item in iterable:
            yield item
            advance(1)


@overload
def progress(
    iterable: None = None,
    **kwargs: Unpack[_ProgressKwargs],
) -> AbstractContextManager[_Advance]: ...


@overload
def progress(
    iterable: Iterable[_T],
    **kwargs: Unpack[_ProgressKwargs],
) -> Iterator[_T]: ...


def progress(
    iterable: Iterable[_T] | None = None,
    **kwargs: Unpack[_ProgressKwargs],
) -> AbstractContextManager[_Advance] | Iterator[_T]:
    """
    Progress tracker that logs to the logging module.

    Can be used as a context manager or an iterable wrapper:

    Context manager usage:
        with progress(desc='Processing', total=100) as advance:
            for item in items:
                process(item)
                advance(1)

    Iterable wrapper usage:
        for item in progress(items, desc='Processing', total=len(items)):
            process(item)
    """
    return (
        _progress_context(**kwargs)
        if iterable is None
        else _progress_iterable(iterable, **kwargs)
    )
