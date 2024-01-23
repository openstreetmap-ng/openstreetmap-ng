import logging
import os
import pathlib
import re
from hashlib import sha256

from anyio import Path

from app.lib.directory_hash import directory_hash
from app.lib.yarn_lock import get_yarn_lock_version


def _path(s: str) -> Path:
    """
    Convert a string to a Path object and resolve it.
    """
    try:
        return Path(pathlib.Path(s).resolve(strict=True))
    except FileNotFoundError:
        return Path(s)


VERSION = '0.7.0'
if VERSION.count('.') != 2:
    raise ValueError('VERSION must be in the format "x.y.z"')

VERSION_DATE = ''
if VERSION_DATE:
    VERSION += f'.{VERSION_DATE}'

NAME = 'openstreetmap-website'
WEBSITE = 'https://www.openstreetmap.org'
USER_AGENT = f'{NAME}/{VERSION} (+{WEBSITE})'

DEFAULT_LANGUAGE = 'en'

GENERATOR = 'OpenStreetMap-NG'
COPYRIGHT = 'OpenStreetMap contributors'
ATTRIBUTION_URL = 'https://www.openstreetmap.org/copyright'
LICENSE_URL = 'https://opendatacommons.org/licenses/odbl/1-0/'

# Configuration (required)
SECRET = os.environ['SECRET']
APP_URL = os.environ['APP_URL'].rstrip('/')
API_URL = os.environ['API_URL'].rstrip('/')
ID_URL = os.environ['ID_URL'].rstrip('/')
RAPID_URL = os.environ['RAPID_URL'].rstrip('/')

# Configuration (optional)
TEST_ENV = os.getenv('TEST_ENV', '0').strip().lower() in ('1', 'true', 'yes')

CONFIG_DIR = _path(os.getenv('CONFIG_DIR', 'config'))
FILE_CACHE_DIR = _path(os.getenv('FILE_CACHE_DIR', 'data/cache'))
FILE_CACHE_SIZE_GB = int(os.getenv('FILE_CACHE_SIZE_GB', 128))
FILE_CACHE_TTL = int(os.getenv('FILE_CACHE_TTL', 7 * 24 * 3600))  # 1 week
FILE_STORE_DIR = _path(os.getenv('FILE_STORE_DIR', 'data/store'))
HTTPS_ONLY = os.getenv('HTTPS_ONLY', '1').strip().lower() in ('1', 'true', 'yes')
ID_ASSETS_DIR = _path(os.getenv('ID_ASSETS_DIR', 'node_modules/iD/dist'))
LEGAL_DIR = _path(os.getenv('LEGAL_DIR', 'config/legal'))
LOCALE_DIR = _path(os.getenv('LOCALE_DIR', 'config/locale'))
NOMINATIM_URL = os.getenv('NOMINATIM_URL', 'https://nominatim.openstreetmap.org')
# see for options: https://docs.sqlalchemy.org/en/20/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.asyncpg
POSTGRES_URL = 'postgresql+asyncpg://' + os.getenv('POSTGRES_URL', 'postgres:postgres@localhost/openstreetmap')
RAPID_ASSETS_DIR = _path(os.getenv('RAPID_ASSETS_DIR', 'node_modules/@rapideditor/rapid/dist'))
SMTP_HOST = os.getenv('SMTP_HOST', '127.0.0.1')
SMTP_PORT = int(os.getenv('SMTP_PORT', 25))
SMTP_USER = os.getenv('SMTP_USER', None)
SMTP_PASS = os.getenv('SMTP_PASS', None)
SMTP_NOREPLY_FROM = os.getenv('SMTP_NOREPLY_FROM', '')
SMTP_MESSAGES_FROM = os.getenv('SMTP_MESSAGES_FROM', '')
SRID = int(os.getenv('SRID', 4326))

# Checks
if not HTTPS_ONLY and not TEST_ENV:
    logging.warning('HTTPS_ONLY cookies are disabled (unsafe)')

# Derived configuration
SECRET_32bytes = sha256(SECRET.encode()).digest()

SMTP_SECURE = os.getenv('SMTP_SECURE', '0' if SMTP_PORT == 25 else '1').strip().lower() in ('1', 'true', 'yes')
SMTP_NOREPLY_FROM_HOST = re.search(r'@([a-zA-Z0-9.-]+)', SMTP_NOREPLY_FROM)[1] if SMTP_NOREPLY_FROM else ''
SMTP_MESSAGES_FROM_HOST = re.search(r'@([a-zA-Z0-9.-]+)', SMTP_MESSAGES_FROM)[1] if SMTP_MESSAGES_FROM else ''

LOCALE_FRONTEND_VERSION = directory_hash(LOCALE_DIR / 'frontend', strict=False)
ID_VERSION = get_yarn_lock_version('iD')
RAPID_VERSION = get_yarn_lock_version('@rapideditor/rapid')

# Synchronously create directories if missing
pathlib.Path(FILE_CACHE_DIR).mkdir(parents=True, exist_ok=True)
pathlib.Path(FILE_STORE_DIR).mkdir(parents=True, exist_ok=True)
