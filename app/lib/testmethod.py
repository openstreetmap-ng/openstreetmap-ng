from functools import wraps

import cython

from app.config import TEST_ENV


def testmethod(func):
    """Decorator to mark a method as runnable only in test environment."""
    test_env: cython.bint = TEST_ENV

    @wraps(func)
    def wrapper(*args, **kwargs):
        assert test_env, 'Test method cannot be called outside test environment'
        return func(*args, **kwargs)

    return wrapper
