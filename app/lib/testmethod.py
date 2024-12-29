from functools import wraps

import cython

from app.config import TEST_ENV


def testmethod(func):
    """Decorator to mark a method as runnable only in test environment."""
    test_env: cython.char = bool(TEST_ENV)

    @wraps(func)
    def wrapper(*args, **kwargs):
        if not test_env:
            raise AssertionError('Test method cannot be called outside test environment')
        return func(*args, **kwargs)

    return wrapper
