from pathlib import Path

import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

from app.exceptions06 import Exceptions06
from app.lib.auth_context import auth_context
from app.lib.exceptions_context import exceptions_context
from app.lib.xmltodict import XMLToDict
from app.main import main
from app.queries.user_query import UserQuery


@pytest.fixture(scope='session')
async def _lifespan():
    async with LifespanManager(main):
        yield


@pytest.fixture()
def client(_lifespan) -> AsyncClient:
    return AsyncClient(base_url='http://127.0.0.1:8000', transport=ASGITransport(main))  # type: ignore[arg-type]


@pytest.fixture()
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


@pytest.fixture()
def gpx() -> dict:
    return XMLToDict.parse(Path('tests/data/8473730.gpx').read_bytes())
