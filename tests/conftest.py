import pytest
from anyio import Path
from asgi_lifespan import LifespanManager
from httpx import AsyncClient

from app.exceptions06 import Exceptions06
from app.lib.auth_context import auth_context
from app.lib.exceptions_context import exceptions_context
from app.lib.xmltodict import XMLToDict
from app.main import main
from app.queries.user_query import UserQuery


@pytest.fixture(scope='session')
def anyio_backend():
    return 'asyncio'


@pytest.fixture(scope='session')
async def _lifespan():
    async with LifespanManager(main):
        yield


@pytest.fixture()
def client(_lifespan) -> AsyncClient:
    return AsyncClient(app=main, base_url='http://127.0.0.1:8000')


@pytest.fixture()
async def changeset_id(client: AsyncClient):
    client.headers['Authorization'] = 'User user1'

    # create changeset
    r = await client.put(
        '/api/0.6/changeset/create',
        content=XMLToDict.unparse({'osm': {'changeset': {'tag': [{'@k': 'created_by', '@v': 'tests'}]}}}),
    )
    assert r.is_success, r.text

    exceptions = Exceptions06()
    user = await UserQuery.find_one_by_display_name('user1')
    with exceptions_context(exceptions), auth_context(user, ()):
        yield int(r.text)


@pytest.fixture()
async def gpx() -> dict:
    gpx = await Path('tests/data/11152535.gpx').read_bytes()
    return XMLToDict.parse(gpx)
