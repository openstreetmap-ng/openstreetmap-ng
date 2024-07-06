from datetime import timedelta

import pytest

from app.lib.retry import retry


async def test_retry():
    runs = 0

    @retry(None)
    async def func():
        nonlocal runs
        runs += 1

        # raise exception on first run
        if runs < 2:
            raise Exception  # noqa: TRY002

    await func()
    assert runs == 2


async def test_retry_timeout():
    @retry(timedelta(seconds=0.1))
    async def func():
        raise RuntimeError

    with pytest.raises(TimeoutError):
        await func()
