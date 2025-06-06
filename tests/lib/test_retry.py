import asyncio
from datetime import timedelta
from inspect import unwrap

import pytest

from app.lib.retry import retry


@pytest.mark.extended
async def test_retry():
    runs: int = 0

    @retry(None)
    async def func():
        nonlocal runs
        await asyncio.sleep(0)
        runs += 1

        # Raise exception on the first attempt
        if runs < 2:
            raise Exception  # noqa: TRY002

    await func()
    assert runs == 2, 'Function must succeed after second attempt'


async def test_retry_timeout():
    @retry(timedelta())
    async def func():
        await asyncio.sleep(0)
        raise RuntimeError

    with pytest.raises(TimeoutError):
        await func()


def test_retry_unwrap():
    async def func():
        pass

    wrapper = retry(timedelta())(func)
    assert unwrap(wrapper) == func, 'retry must support unwrapping'
