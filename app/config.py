import contextlib
import os
from hashlib import sha256
from itertools import chain
from logging.config import dictConfig
from pathlib import Path
from urllib.parse import urlsplit

from app.lib.local_chapters import LOCAL_CHAPTERS

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
REPLICATION_DIR = _path(os.getenv('REPLICATION_DIR', 'data/replication'), mkdir=True)

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

GRAPHHOPPER_API_KEY = os.getenv('GRAPHHOPPER_API_KEY')
GRAPHHOPPER_URL = os.getenv('GRAPHHOPPER_URL', 'https://graphhopper.com')
NOMINATIM_URL = os.getenv('NOMINATIM_URL', 'https://nominatim.openstreetmap.org')
OSM_REPLICATION_URL = os.getenv(
    'OSM_REPLICATION_URL', 'https://osm-planet-eu-central-1.s3.dualstack.eu-central-1.amazonaws.com/planet/replication'
)
OSRM_URL = os.getenv('OSRM_URL', 'https://router.project-osrm.org')
OVERPASS_INTERPRETER_URL = os.getenv('OVERPASS_INTERPRETER_URL', 'https://overpass-api.de/api/interpreter')
VALHALLA_URL = os.getenv('VALHALLA_URL', 'https://valhalla1.openstreetmap.de')

# https://developers.facebook.com/docs/development/create-an-app/facebook-login-use-case
# https://developers.facebook.com/docs/facebook-login/guides/advanced/manual-flow/
# https://docs.github.com/en/apps/creating-github-apps/registering-a-github-app/registering-a-github-app
GITHUB_OAUTH_PUBLIC = os.getenv('GITHUB_OAUTH_PUBLIC')
GITHUB_OAUTH_SECRET = os.getenv('GITHUB_OAUTH_SECRET')
# https://developers.google.com/identity/openid-connect/openid-connect
GOOGLE_OAUTH_PUBLIC = os.getenv('GOOGLE_OAUTH_PUBLIC')
GOOGLE_OAUTH_SECRET = os.getenv('GOOGLE_OAUTH_SECRET')
# https://learn.microsoft.com/en-us/entra/identity-platform/v2-protocols-oidc
MICROSOFT_OAUTH_PUBLIC = os.getenv('MICROSOFT_OAUTH_PUBLIC')
# https://api.wikimedia.org/wiki/Special:AppManagement
WIKIMEDIA_OAUTH_PUBLIC = os.getenv('WIKIMEDIA_OAUTH_PUBLIC')
WIKIMEDIA_OAUTH_SECRET = os.getenv('WIKIMEDIA_OAUTH_SECRET')

TRUSTED_HOSTS: frozenset[str] = frozenset(
    host.casefold()
    for host in chain(
        (
            line
            for line in (line.strip() for line in Path('config/trusted_hosts.txt').read_text().splitlines())
            if line and not line.startswith('#')
        ),
        (urlsplit(url).hostname for _, url in LOCAL_CHAPTERS),
        os.getenv('TRUSTED_HOSTS_EXTRA', '').split(),
    )
    if host
)

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
                    'python_multipart',
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
SECRET_32 = sha256(SECRET.encode()).digest()

SMTP_NOREPLY_FROM_HOST = SMTP_NOREPLY_FROM.rpartition('@')[2] if SMTP_NOREPLY_FROM else None
SMTP_MESSAGES_FROM_HOST = SMTP_MESSAGES_FROM.rpartition('@')[2] if SMTP_MESSAGES_FROM else None
