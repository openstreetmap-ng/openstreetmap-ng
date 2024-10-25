import contextlib
import logging
import os
from hashlib import sha256
from logging.config import dictConfig
from pathlib import Path

from app.lib.bun_packages import bun_packages

VERSION = 'dev'

NAME = 'openstreetmap-website'
WEBSITE = 'https://www.openstreetmap.org'
USER_AGENT = f'{NAME}/{VERSION} (+{WEBSITE})'

GENERATOR = 'OpenStreetMap-NG'
COPYRIGHT = 'OpenStreetMap contributors'
ATTRIBUTION_URL = 'https://www.openstreetmap.org/copyright'
LICENSE_URL = 'https://opendatacommons.org/licenses/odbl/1-0/'

# Configuration (required)
os.chdir(Path(__file__).parent.parent)
SECRET = os.environ['SECRET']
APP_URL = os.environ['APP_URL'].rstrip('/')
SMTP_HOST = os.environ['SMTP_HOST']
SMTP_PORT = int(os.environ['SMTP_PORT'])
SMTP_USER = os.environ['SMTP_USER']
SMTP_PASS = os.environ['SMTP_PASS']


def _path(s: str, *, mkdir: bool = False) -> Path:
    """
    Convert a string to a Path object and resolve it.
    """
    p = Path(s)
    with contextlib.suppress(FileNotFoundError):
        p = p.resolve(strict=True)
    if mkdir:
        p.mkdir(parents=True, exist_ok=True)
    return p


# Configuration (optional)
TEST_ENV = os.getenv('TEST_ENV', '0').strip().lower() in {'1', 'true', 'yes'}
LOG_LEVEL = os.getenv('LOG_LEVEL', 'DEBUG' if TEST_ENV else 'INFO').upper()
GC_LOG = os.getenv('GC_LOG', '0').strip().lower() in {'1', 'true', 'yes'}

LEGACY_HIGH_PRECISION_TIME = os.getenv('LEGACY_HIGH_PRECISION_TIME', '0').strip().lower() in {'1', 'true', 'yes'}
LEGACY_SEQUENCE_ID_MARGIN = os.getenv('LEGACY_SEQUENCE_ID_MARGIN', '0').strip().lower() in {'1', 'true', 'yes'}

FILE_CACHE_DIR = _path(os.getenv('FILE_CACHE_DIR', 'data/cache'), mkdir=True)
FILE_CACHE_SIZE_GB = int(os.getenv('FILE_CACHE_SIZE_GB', '128'))
FILE_STORE_DIR = _path(os.getenv('FILE_STORE_DIR', 'data/store'), mkdir=True)
PRELOAD_DIR = _path(os.getenv('PRELOAD_DIR', 'data/preload'))

# see for options: https://docs.sqlalchemy.org/en/20/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.asyncpg
POSTGRES_LOG = os.getenv('POSTGRES_LOG', '0').strip().lower() in {'1', 'true', 'yes'}
POSTGRES_URL = 'postgresql+asyncpg://' + os.getenv(
    'POSTGRES_URL', f'postgres:postgres@/postgres?host={_path('data/postgres_unix')}'
)

VALKEY_URL = os.getenv('VALKEY_URL', f'unix://{_path('data/valkey.sock')}?password=valkey&protocol=3')

SMTP_NOREPLY_FROM = os.getenv('SMTP_NOREPLY_FROM', SMTP_USER)
SMTP_MESSAGES_FROM = os.getenv('SMTP_MESSAGES_FROM', SMTP_USER)

API_URL = os.getenv('API_URL', APP_URL).rstrip('/')
ID_URL = os.getenv('ID_URL', APP_URL).rstrip('/')
RAPID_URL = os.getenv('RAPID_URL', APP_URL).rstrip('/')

NOMINATIM_URL = os.getenv('NOMINATIM_URL', 'https://nominatim.openstreetmap.org')
OVERPASS_INTERPRETER_URL = os.getenv('OVERPASS_INTERPRETER_URL', 'https://overpass-api.de/api/interpreter')

TEST_USER_DOMAIN = 'test.test'

# Logging configuration
dictConfig(
    {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'default': {
                '()': 'uvicorn.logging.DefaultFormatter',
                'fmt': '%(levelprefix)s | %(asctime)s | %(name)s %(message)s',
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
                module: {'handlers': [], 'level': 'INFO'}
                for module in (
                    'hpack',
                    'httpx',
                    'httpcore',
                    'markdown_it',
                    'multipart',
                )
            },
            **{
                # conditional database logging
                module: {'handlers': [], 'level': 'INFO'}
                for module in (
                    'sqlalchemy.engine',
                    'sqlalchemy.pool',
                )
                if POSTGRES_LOG
            },
        },
    }
)


# Derived configuration
SECRET_32b = sha256(SECRET.encode()).digest()

SMTP_NOREPLY_FROM_HOST = SMTP_NOREPLY_FROM.rpartition('@')[2] if SMTP_NOREPLY_FROM else None
SMTP_MESSAGES_FROM_HOST = SMTP_MESSAGES_FROM.rpartition('@')[2] if SMTP_MESSAGES_FROM else None

_bun_packages = bun_packages(FILE_CACHE_DIR)
ID_VERSION = _bun_packages['iD'].rpartition('#')[2]
RAPID_VERSION = _bun_packages['@rapideditor/rapid']
logging.info('Packages versions: iD=%s, Rapid=%s', ID_VERSION, RAPID_VERSION)
del _bun_packages
