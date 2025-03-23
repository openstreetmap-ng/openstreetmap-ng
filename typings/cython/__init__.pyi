from collections.abc import Callable
from typing import TypeVar

from Cython.Shadow import *  # noqa: F403

_Callable = TypeVar('_Callable', bound=Callable)

def cfunc(func: _Callable) -> _Callable: ...

compiled: bool
