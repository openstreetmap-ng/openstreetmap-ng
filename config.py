import logging
import os
import pathlib
import re
from hashlib import sha256

from anyio import Path

NAME = 'openstreetmap-website'
VERSION = '0.7'
WEBSITE = 'https://www.openstreetmap.org'
USER_AGENT = f'{NAME}/{VERSION} (+{WEBSITE})'

DEFAULT_LANGUAGE = 'en'
LOCALE_DOMAIN = 'combined'  # run "make locale-compile" to generate combined locales

GENERATOR = 'OpenStreetMap-NG'
COPYRIGHT = 'OpenStreetMap and contributors'
ATTRIBUTION_URL = 'https://www.openstreetmap.org/copyright'
LICENSE_URL = 'https://opendatacommons.org/licenses/odbl/1-0/'

# Configuration (required)
SECRET = os.environ['SECRET']
BASE_URL = os.environ['BASE_URL']

# Configuration (optional)
SRID = int(os.getenv('SRID', 4326))
FILE_CACHE_DIR = Path(os.getenv('FILE_CACHE_DIR', 'tmp/file'))
FILE_CACHE_SIZE_GB = int(os.getenv('FILE_CACHE_SIZE_GB', 128))
FILE_CACHE_TTL = int(os.getenv('FILE_CACHE_TTL', 7 * 24 * 3600))  # 1 week
FILE_DATA_DIR = Path(os.getenv('FILE_DATA_DIR', 'data/file'))
HTTPS_ONLY = os.getenv('HTTPS_ONLY', '1').strip().lower() in ('1', 'true', 'yes')
NOMINATIM_URL = os.getenv('NOMINATIM_URL', 'https://nominatim.openstreetmap.org')
# see for options: https://docs.sqlalchemy.org/en/20/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.asyncpg
POSTGRES_URL = 'postgresql+asyncpg://' + os.getenv('POSTGRES_URL', 'localhost/openstreetmap')
SMTP_HOST = os.getenv('SMTP_HOST', '127.0.0.1')
SMTP_PORT = int(os.getenv('SMTP_PORT', 25))
SMTP_USER = os.getenv('SMTP_USER', None)
SMTP_PASS = os.getenv('SMTP_PASS', None)
SMTP_NOREPLY_FROM = os.getenv('SMTP_NOREPLY_FROM', '')
SMTP_MESSAGES_FROM = os.getenv('SMTP_MESSAGES_FROM', '')

# Checks
if not HTTPS_ONLY:
    logging.warning('HTTPS_ONLY cookies are disabled (unsafe)')

# Derived configuration
SECRET_32b = sha256(SECRET.encode()).digest()

SMTP_SECURE = os.getenv('SMTP_SECURE', '0' if SMTP_PORT == 25 else '1').strip().lower() in ('1', 'true', 'yes')
SMTP_NOREPLY_FROM_HOST = re.search(r'@([a-zA-Z0-9.-]+)', SMTP_NOREPLY_FROM).group(1) if SMTP_NOREPLY_FROM else ''
SMTP_MESSAGES_FROM_HOST = re.search(r'@([a-zA-Z0-9.-]+)', SMTP_MESSAGES_FROM).group(1) if SMTP_MESSAGES_FROM else ''

# synchronously create directories if missing
pathlib.Path(FILE_CACHE_DIR).mkdir(parents=True, exist_ok=True)
pathlib.Path(FILE_DATA_DIR).mkdir(parents=True, exist_ok=True)
