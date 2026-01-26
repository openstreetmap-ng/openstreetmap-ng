from asyncio import TaskGroup
from copy import deepcopy
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.exceptions06 import Exceptions06
from app.lib.auth_context import auth_context
from app.lib.exceptions_context import exceptions_context
from app.lib.xmltodict import XMLToDict
from app.main import app
from app.models.types import ChangesetId, DisplayName
from app.queries.user_query import UserQuery
from tests.utils.lifespan_manager import LifespanManager


def pytest_addoption(parser: pytest.Parser):
    parser.addoption(
        '--extended',
        action='store_true',
        default=False,
        help='run extended tests',
    )


def pytest_configure(config: pytest.Config):
    config.addinivalue_line(
        'markers', 'extended: mark test as part of the extended test suite'
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]):
    # run all tests in the session in the same event loop
    # https://pytest-asyncio.readthedocs.io/en/latest/how-to-guides/run_session_tests_in_same_loop.html
    session_scope_marker = pytest.mark.asyncio(loop_scope='session')
    for item in items:
        if pytest_asyncio.is_async_test(item):
            item.add_marker(session_scope_marker, append=False)

    # skip extended tests by default
    if not config.getoption('--extended'):
        skip_marker = pytest.mark.skip(reason='need --extended option to run')
        for item in items:
            if 'extended' in item.keywords:
                item.add_marker(skip_marker)


@pytest_asyncio.fixture(scope='session', autouse=True)
async def transport():
    async with LifespanManager(app):
        yield ASGITransport(app)


@pytest.fixture
def client(transport: ASGITransport):
    return AsyncClient(base_url='http://localhost:8000', transport=transport)


@pytest_asyncio.fixture
async def changeset_id(client: AsyncClient):
    client.headers['Authorization'] = 'User user1'

    async with TaskGroup() as tg:
        create_task = tg.create_task(
            client.put(
                '/api/0.6/changeset/create',
                content=XMLToDict.unparse({
                    'osm': {'changeset': {'tag': [{'@k': 'created_by', '@v': 'tests'}]}}
                }),
            )
        )
        user_task = tg.create_task(UserQuery.find_by_display_name(DisplayName('user1')))

    r = create_task.result()
    assert r.is_success, r.text

    user = user_task.result()
    assert user is not None, 'Test user "user1" must exist'

    with exceptions_context(Exceptions06()), auth_context(user):
        yield ChangesetId(int(r.text))


@pytest.fixture
def gpx(data=XMLToDict.parse(Path('tests/data/8473730.gpx').read_bytes())):
    return deepcopy(data)
