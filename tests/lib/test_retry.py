from datetime import timedelta

import pytest

from app.lib.retry import retry


@pytest.mark.extended
async def test_retry():
    runs: int = 0

    @retry(None)
    async def func():
        nonlocal runs
        runs += 1

        # raise exception on first run
        if runs < 2:
            raise Exception  # noqa: TRY002

    await func()
    assert runs == 2


@pytest.mark.extended
async def test_retry_timeout():
    @retry(timedelta(seconds=0.1))
    async def func():
        raise RuntimeError

    with pytest.raises(TimeoutError):
        await func()
