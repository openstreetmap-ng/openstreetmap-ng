from collections.abc import Callable, Iterator
from typing import Generic, TypeVar

_T = TypeVar('_T', str, bytes)

class error(Exception): ...

class Options:
    class Encoding:
        LATIN1: int
        UTF8: int

    NAMES: tuple[str, ...]

    encoding: int = ...  # Encoding.UTF8
    """Text and pattern are UTF-8; otherwise Latin-1."""

    posix_syntax: bool = False
    """Restrict regexps to POSIX egrep syntax."""

    longest_match: bool = False
    """Search for longest match, not first match."""

    log_errors: bool = True
    """Log syntax and execution errors to ERROR."""

    max_mem: int = 8388608  # 8 << 20
    """Approx. max memory footprint of RE2."""

    literal: bool = False
    """Interpret string as literal, not regexp."""

    never_nl: bool = False
    """Never match newline, even if it is in regexp."""

    dot_nl: bool = False
    """Dot matches everything including newline."""

    never_capture: bool = False
    """Parse all parens as non-capturing."""

    case_sensitive: bool = True
    """Match is case-sensitive (regexp can override with (?i) unless in posix_syntax mode)."""

    perl_classes: bool = False
    r"""Allow Perl's \d \s \w \D \S \W. Only checked when posix_syntax=True."""

    word_boundary: bool = False
    r"""Allow Perl's \b \B (word boundary). Only checked when posix_syntax=True."""

    one_line: bool = False
    """^ and $ only match beginning and end of text. Only checked when posix_syntax=True."""

    def __init__(self) -> None: ...

class _Anchor:
    UNANCHORED: int
    ANCHOR_START: int
    ANCHOR_BOTH: int

class _Regexp(Generic[_T]):
    pattern: _T
    groups: int
    groupindex: dict[str, int]

    def match(
        self,
        text: _T,
        pos: int | None = None,
        endpos: int | None = None,
    ) -> _Match[_T] | None: ...
    def search(
        self,
        text: _T,
        pos: int | None = None,
        endpos: int | None = None,
    ) -> _Match[_T] | None: ...
    def fullmatch(
        self,
        text: _T,
        pos: int | None = None,
        endpos: int | None = None,
    ) -> _Match[_T] | None: ...
    def finditer(
        self,
        text: _T,
        pos: int | None = None,
        endpos: int | None = None,
    ) -> Iterator[_Match[_T]]: ...
    def findall(
        self,
        text: _T,
        pos: int | None = None,
        endpos: int | None = None,
    ) -> list[_T] | list[tuple[_T, ...]]: ...
    def split(self, text: _T, maxsplit: int = 0) -> list[_T]: ...
    def sub(
        self,
        repl: _T | Callable[[_Match[_T]], _T],
        text: _T,
        count: int = 0,
    ) -> _T: ...
    def subn(
        self,
        repl: _T | Callable[[_Match[_T]], _T],
        text: _T,
        count: int = 0,
    ) -> tuple[_T, int]: ...

class _Match(Generic[_T]):
    re: _Regexp[_T]
    string: _T
    pos: int
    endpos: int
    lastindex: int | None
    lastgroup: str | None

    def group(self, *groups: int | str) -> _T: ...  # | tuple[_T, ...]: ...
    def groups(self, default: _T | None = None) -> tuple[_T | None, ...]: ...
    def groupdict(self, default: _T | None = None) -> dict[str, _T | None]: ...
    def start(self, group: int | str = 0) -> int: ...
    def end(self, group: int | str = 0) -> int: ...
    def span(self, group: int | str = 0) -> tuple[int, int]: ...
    def expand(self, template: _T) -> _T: ...
    def __getitem__(self, group: int | str) -> _T: ...

def compile(pattern: _T, options: Options | None = None) -> _Regexp[_T]: ...
def match(
    pattern: _T,
    text: _T,
    options: Options | None = None,
) -> _Match[_T] | None: ...
def search(
    pattern: _T,
    text: _T,
    options: Options | None = None,
) -> _Match[_T] | None: ...
def fullmatch(
    pattern: _T,
    text: _T,
    options: Options | None = None,
) -> _Match[_T] | None: ...
def finditer(
    pattern: _T,
    text: _T,
    options: Options | None = None,
) -> Iterator[_Match[_T]]: ...
def findall(
    pattern: _T,
    text: _T,
    options: Options | None = None,
) -> list[_T] | list[tuple[_T, ...]]: ...
def split(
    pattern: _T,
    text: _T,
    maxsplit: int = 0,
    options: Options | None = None,
) -> list[_T]: ...
def sub(
    pattern: _T,
    repl: _T | Callable[[_Match[_T]], _T],
    text: _T,
    count: int = 0,
    options: Options | None = None,
) -> _T: ...
def subn(
    pattern: _T,
    repl: _T | Callable[[_Match[_T]], _T],
    text: _T,
    count: int = 0,
    options: Options | None = None,
) -> tuple[_T, int]: ...
def escape(pattern: _T) -> _T: ...
def purge() -> None: ...

class Set:
    def __init__(self, anchor: int, options: Options | None = None) -> None: ...
    def Add(self, pattern: _T) -> int: ...
    def Compile(self) -> None: ...
    def Match(self, text: _T) -> list[int]: ...
    @classmethod
    def MatchSet(cls, options: Options | None = None) -> Set: ...
    @classmethod
    def SearchSet(cls, options: Options | None = None) -> Set: ...
    @classmethod
    def FullMatchSet(cls, options: Options | None = None) -> Set: ...

class Filter:
    def __init__(self) -> None: ...
    def Add(self, pattern: _T, options: Options | None = None) -> int: ...
    def Compile(self) -> None: ...
    def Match(self, text: _T, potential: bool = False) -> list[int]: ...
    def re(self, index: int) -> _Regexp[_T]: ...
