from collections.abc import Callable, Iterator
from typing import Generic, Literal, TypeVar, overload

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
    @property
    def pattern(self) -> _T: ...
    @property
    def options(self) -> Options: ...
    @property
    def groups(self) -> int: ...
    @property
    def groupindex(self) -> dict[_T, int]: ...
    @property
    def programsize(self) -> int: ...
    @property
    def reverseprogramsize(self) -> int: ...
    @property
    def programfanout(self) -> list[int]: ...
    @property
    def reverseprogramfanout(self) -> list[int]: ...
    def possiblematchrange(self, maxlen: int) -> tuple[bytes, bytes]: ...
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
    @property
    def re(self) -> _Regexp[_T]: ...
    @property
    def string(self) -> _T: ...
    @property
    def pos(self) -> int: ...
    @property
    def endpos(self) -> int: ...
    @property
    def lastindex(self) -> int | None: ...
    @property
    def lastgroup(self) -> _T | None: ...
    @overload
    def group(self, group: Literal[0] = 0, /) -> _T: ...
    @overload
    def group(self, group: int | str, /) -> _T | None: ...
    @overload
    def group(
        self, group1: int | str, group2: int | str, /, *groups: int | str
    ) -> tuple[_T | None, ...]: ...
    def groups(self, default: _T | None = None) -> tuple[_T | None, ...]: ...
    def groupdict(self, default: _T | None = None) -> dict[_T, _T | None]: ...
    # start/end/span raise TypeError on str arg — only int is accepted.
    # Returns -1 (or (-1, -1)) for unmatched optional groups.
    def start(self, group: int = 0) -> int: ...
    def end(self, group: int = 0) -> int: ...
    def span(self, group: int = 0) -> tuple[int, int]: ...
    def expand(self, template: _T) -> _T: ...
    @overload
    def __getitem__(self, group: Literal[0]) -> _T: ...
    @overload
    def __getitem__(self, group: int | str) -> _T | None: ...

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
    # Set/Filter accept a mix of str and bytes patterns/texts; their methods
    # are not parameterised by a single element type.
    def __init__(self, anchor: int, options: Options | None = None) -> None: ...
    def Add(self, pattern: str | bytes) -> int: ...
    def Compile(self) -> None: ...
    def Match(self, text: str | bytes) -> list[int] | None: ...
    @classmethod
    def MatchSet(cls, options: Options | None = None) -> Set: ...
    @classmethod
    def SearchSet(cls, options: Options | None = None) -> Set: ...
    @classmethod
    def FullMatchSet(cls, options: Options | None = None) -> Set: ...

class Filter:
    def __init__(self) -> None: ...
    def Add(self, pattern: str | bytes, options: Options | None = None) -> int: ...
    def Compile(self) -> None: ...
    def Match(self, text: str | bytes, potential: bool = False) -> list[int] | None: ...
    def re(self, index: int) -> _Regexp[str] | _Regexp[bytes]: ...
