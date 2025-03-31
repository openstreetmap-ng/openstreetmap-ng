from collections.abc import Callable
from functools import wraps

from app.config import ENV


def testmethod(func: Callable):
    """Decorator to mark a method as runnable only in test environment."""
    if ENV != 'prod':
        return func

    @wraps(func)
    def wrapper(*args, **kwargs):
        raise AssertionError(f'@testmethod: {func.__qualname__} is disabled in {ENV} environment')

    return wrapper
