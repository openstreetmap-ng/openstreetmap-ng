from collections.abc import Callable
from functools import wraps
from typing import ParamSpec, TypeVar

from app.config import ENV

_P = ParamSpec('_P')
_R = TypeVar('_R')


def testmethod(func: Callable[_P, _R]) -> Callable[_P, _R]:
    """Decorator to mark a method as runnable only in test environment."""
    if ENV != 'prod':
        return func

    @wraps(func)
    def wrapper(*args: _P.args, **kwargs: _P.kwargs) -> _R:
        raise AssertionError(
            f'@testmethod: {func.__qualname__} is disabled in {ENV} environment'
        )

    return wrapper
