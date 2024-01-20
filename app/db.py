from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import POSTGRES_URL

_db_engine = create_async_engine(
    POSTGRES_URL,
    echo=True,  # TODO: echo testing only
    echo_pool=True,
)

# see for options: https://docs.sqlalchemy.org/en/20/orm/session_api.html#sqlalchemy.orm.Session
DB = async_sessionmaker(
    _db_engine,
    expire_on_commit=False,
)

# TODO: test unicode normalization comparison
