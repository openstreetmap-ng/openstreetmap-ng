import contextlib
import os
import pathlib
import re
from hashlib import sha256
from logging.config import dictConfig

from anyio import Path

from app.lib.yarn_lock_version import yarn_lock_version

VERSION = '0.7.0'
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
API_URL = os.environ['API_URL'].rstrip('/')
ID_URL = os.environ['ID_URL'].rstrip('/')
OVERPASS_INTERPRETER_URL = os.environ['OVERPASS_INTERPRETER_URL'].rstrip('/')
RAPID_URL = os.environ['RAPID_URL'].rstrip('/')


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
NOMINATIM_URL = os.getenv('NOMINATIM_URL', 'https://nominatim.openstreetmap.org')
POSTGRES_LOG = os.getenv('POSTGRES_LOG', '0').strip().lower() in ('1', 'true', 'yes')
# see for options: https://docs.sqlalchemy.org/en/20/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.asyncpg
POSTGRES_URL = 'postgresql+asyncpg://' + os.getenv('POSTGRES_URL', 'postgres:postgres@127.0.0.1/postgres')
PRELOAD_DIR = _path(os.getenv('PRELOAD_DIR', 'data/preload'))
REDIS_URL = os.getenv('REDIS_URL', 'redis://127.0.0.1?password=redis&protocol=3')
SMTP_HOST = os.getenv('SMTP_HOST', '127.0.0.1')
SMTP_PORT = int(os.getenv('SMTP_PORT', 25))
SMTP_USER = os.getenv('SMTP_USER', None)
SMTP_PASS = os.getenv('SMTP_PASS', None)
SMTP_NOREPLY_FROM = os.getenv('SMTP_NOREPLY_FROM', '')
SMTP_MESSAGES_FROM = os.getenv('SMTP_MESSAGES_FROM', '')

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
            'httpx': {'handlers': ['default'], 'level': 'INFO'},
            'httpcore': {'handlers': ['default'], 'level': 'INFO'},
            'markdown_it': {'handlers': ['default'], 'level': 'INFO'},
        },
    }
)


# Derived configuration
SECRET_32bytes = sha256(SECRET.encode()).digest()

SMTP_SECURE = os.getenv('SMTP_SECURE', '0' if SMTP_PORT == 25 else '1').strip().lower() in ('1', 'true', 'yes')
SMTP_NOREPLY_FROM_HOST = re.search(r'@([a-zA-Z0-9.-]+)', SMTP_NOREPLY_FROM)[1] if SMTP_NOREPLY_FROM else ''
SMTP_MESSAGES_FROM_HOST = re.search(r'@([a-zA-Z0-9.-]+)', SMTP_MESSAGES_FROM)[1] if SMTP_MESSAGES_FROM else ''

ID_VERSION = yarn_lock_version('iD')
RAPID_VERSION = yarn_lock_version('@rapideditor/rapid')
