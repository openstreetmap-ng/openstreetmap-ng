import contextlib
import os
import pathlib
import re
from hashlib import sha256
from logging.config import dictConfig

from anyio import Path
from pydantic import SecretStr

from app.lib.yarn_lock_version import yarn_lock_version

VERSION = '0.1.0'
VERSION_DATE = ''
if VERSION_DATE:
    VERSION += f'.{VERSION_DATE}'

NAME = 'openstreetmap-website'
WEBSITE = 'https://www.openstreetmap.org'
USER_AGENT = f'{NAME}/{VERSION} (+{WEBSITE})'

DEFAULT_LANGUAGE = 'en'

GENERATOR = 'OpenStreetMap-NextGen'
COPYRIGHT = 'OpenStreetMap contributors'
ATTRIBUTION_URL = 'https://www.openstreetmap.org/copyright'
LICENSE_URL = 'https://opendatacommons.org/licenses/odbl/1-0/'

# Configuration (required)
SECRET = os.environ['SECRET']
APP_URL = os.environ['APP_URL'].rstrip('/')
SMTP_HOST = os.environ['SMTP_HOST']
SMTP_PORT = int(os.environ['SMTP_PORT'])
SMTP_USER = os.environ['SMTP_USER']
SMTP_PASS = SecretStr(os.environ['SMTP_PASS'])


def _path(s: str, *, mkdir: bool = False) -> Path:
    """
    Convert a string to a Path object and resolve it.
    """
    p = pathlib.Path(s)

    with contextlib.suppress(FileNotFoundError):
        p = p.resolve(strict=True)
    if mkdir:
        p.mkdir(parents=True, exist_ok=True)

    return Path(p)


# Configuration (optional)
TEST_ENV = os.getenv('TEST_ENV', '0').strip().lower() in ('1', 'true', 'yes')
LOG_LEVEL = os.getenv('LOG_LEVEL', 'DEBUG' if TEST_ENV else 'INFO').upper()

CONFIG_DIR = _path(os.getenv('CONFIG_DIR', 'config'))
FILE_CACHE_DIR = _path(os.getenv('FILE_CACHE_DIR', 'data/cache'), mkdir=True)
FILE_CACHE_SIZE_GB = int(os.getenv('FILE_CACHE_SIZE_GB', 128))  # TODO: implement?
FILE_STORE_DIR = _path(os.getenv('FILE_STORE_DIR', 'data/store'), mkdir=True)
LEGAL_DIR = _path(os.getenv('LEGAL_DIR', 'config/legal'))
LOCALE_DIR = _path(os.getenv('LOCALE_DIR', 'config/locale'))
POSTGRES_LOG = os.getenv('POSTGRES_LOG', '0').strip().lower() in ('1', 'true', 'yes')
# TODO: SecretStr?
# see for options: https://docs.sqlalchemy.org/en/20/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.asyncpg
POSTGRES_URL = 'postgresql+asyncpg://' + os.getenv('POSTGRES_URL', 'postgres:postgres@127.0.0.1/postgres')
PRELOAD_DIR = _path(os.getenv('PRELOAD_DIR', 'data/preload'))
REDIS_URL = os.getenv('REDIS_URL', 'redis://127.0.0.1?password=redis&protocol=3')
SMTP_NOREPLY_FROM = os.getenv('SMTP_NOREPLY_FROM', SMTP_USER)
SMTP_MESSAGES_FROM = os.getenv('SMTP_MESSAGES_FROM', SMTP_USER)
TEST_USER_PASSWORD = os.getenv('TEST_USER_PASSWORD', 'openstreetmap')

API_URL = os.getenv('API_URL', APP_URL).rstrip('/')
ID_URL = os.getenv('ID_URL', APP_URL).rstrip('/')
NOMINATIM_URL = os.getenv('NOMINATIM_URL', 'https://nominatim.openstreetmap.org')
OVERPASS_INTERPRETER_URL = os.getenv('OVERPASS_INTERPRETER_URL', 'https://overpass-api.de/api/interpreter')
RAPID_URL = os.getenv('RAPID_URL', APP_URL).rstrip('/')

# Logging configuration
dictConfig(
    {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'default': {
                '()': 'uvicorn.logging.DefaultFormatter',
                'fmt': '%(levelprefix)s | %(asctime)s | %(message)s',
                'datefmt': '%Y-%m-%d %H:%M:%S',
            },
        },
        'handlers': {
            'default': {
                'formatter': 'default',
                'class': 'logging.StreamHandler',
                'stream': 'ext://sys.stderr',
            },
        },
        'loggers': {
            'root': {'handlers': ['default'], 'level': LOG_LEVEL},
            **{
                # reduce logging verbosity of some modules
                module: {'handlers': ['default'], 'level': 'INFO'}
                for module in (
                    'httpx',
                    'httpcore',
                    'markdown_it',
                    'multipart',
                    'PIL',
                )
            },
        },
    }
)


# Derived configuration
SECRET_32bytes = sha256(SECRET.encode()).digest()

SMTP_NOREPLY_FROM_HOST = re.search(r'@([a-zA-Z0-9.-]+)', SMTP_NOREPLY_FROM)[1] if SMTP_NOREPLY_FROM else None
SMTP_MESSAGES_FROM_HOST = re.search(r'@([a-zA-Z0-9.-]+)', SMTP_MESSAGES_FROM)[1] if SMTP_MESSAGES_FROM else None

ID_VERSION = yarn_lock_version('iD')
RAPID_VERSION = yarn_lock_version('@rapideditor/rapid')
