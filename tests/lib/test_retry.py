from datetime import timedelta

import anyio
import pytest

from app.lib.retry import retry

pytestmark = pytest.mark.anyio


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


def test_retry_timeout():
    @retry(timedelta(seconds=1))
    async def func():
        raise RuntimeError

    with pytest.raises(TimeoutError):
        anyio.run(func)
