from functools import wraps

from app.config import TEST_ENV


def testmethod(func):
    """Decorator to mark a method as runnable only in test environment."""
    if TEST_ENV:
        return func

    @wraps(func)
    def wrapper(*args, **kwargs):
        raise AssertionError('Test method must only run in the test environment')

    return wrapper
