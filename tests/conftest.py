import pytest
from httpx import AsyncClient

from app.main import main


@pytest.fixture(scope='session')
def anyio_backend():
    return 'asyncio'


@pytest.fixture()
def client():
    return AsyncClient(app=main, base_url='http://127.0.0.1:8000')
