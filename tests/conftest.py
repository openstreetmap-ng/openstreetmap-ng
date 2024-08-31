from copy import deepcopy
from functools import cache
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.exceptions06 import Exceptions06
from app.lib.auth_context import auth_context
from app.lib.exceptions_context import exceptions_context
from app.lib.xmltodict import XMLToDict
from app.main import main
from app.queries.user_query import UserQuery
from tests.utils.event_loop_policy import CustomEventLoopPolicy
from tests.utils.lifespan_manager import LifespanManager


@pytest.fixture(scope='session')
def event_loop_policy():
    policy = CustomEventLoopPolicy()
    yield policy
    policy.get_event_loop().close()


@pytest_asyncio.fixture(scope='session')
async def transport():
    async with LifespanManager(main):
        yield ASGITransport(main)  # pyright: ignore[reportArgumentType]


@pytest.fixture
def client(transport: ASGITransport) -> AsyncClient:
    return AsyncClient(base_url='http://127.0.0.1:8000', transport=transport)


@pytest_asyncio.fixture()
async def changeset_id(client: AsyncClient):
    client.headers['Authorization'] = 'User user1'

    # create changeset
    r = await client.put(
        '/api/0.6/changeset/create',
        content=XMLToDict.unparse({'osm': {'changeset': {'tag': [{'@k': 'created_by', '@v': 'tests'}]}}}),
    )
    assert r.is_success, r.text

    user = await UserQuery.find_one_by_display_name('user1')
    with exceptions_context(Exceptions06()), auth_context(user, ()):
        yield int(r.text)


@cache
def _gpx_data() -> dict:
    return XMLToDict.parse(Path('tests/data/8473730.gpx').read_bytes())


@pytest.fixture
def gpx() -> dict:
    return deepcopy(_gpx_data())
