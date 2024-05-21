import pytest
from anyio import Path
from asgi_lifespan import LifespanManager
from httpx import AsyncClient

from app.lib.xmltodict import XMLToDict
from app.main import main


@pytest.fixture(scope='session')
def anyio_backend():
    return 'asyncio'


@pytest.fixture(scope='session')
async def _lifespan():
    async with LifespanManager(main):
        yield


@pytest.fixture()
def client(_lifespan):
    return AsyncClient(app=main, base_url='http://127.0.0.1:8000')


@pytest.fixture()
async def gpx() -> dict:
    gpx = await Path('tests/data/11152535.gpx').read_bytes()
    return XMLToDict.parse(gpx)
