import sys
from hashlib import sha256
from itertools import chain
from logging.config import dictConfig
from os import chdir, environ, getenv
from pathlib import Path
from urllib.parse import urlsplit

import sentry_sdk
from githead import githead
from pydantic import ConfigDict
from sentry_sdk.integrations.pure_eval import PureEvalIntegration

from app.lib.local_chapters import LOCAL_CHAPTERS

try:
    VERSION = 'git#' + githead()[:7]
except FileNotFoundError:
    VERSION = 'dev'  # pyright: ignore [reportConstantRedefinition]

NAME = 'openstreetmap-website'
WEBSITE = 'https://www.openstreetmap.org'
USER_AGENT = f'{NAME}/{VERSION} (+{WEBSITE})'

GENERATOR = 'OpenStreetMap-NG'
COPYRIGHT = 'OpenStreetMap contributors'
ATTRIBUTION_URL = 'https://www.openstreetmap.org/copyright'
LICENSE_URL = 'https://opendatacommons.org/licenses/odbl/1-0/'

# Configuration (required)
chdir(Path(__file__).parent.parent)
SECRET = environ['SECRET']
APP_URL = environ['APP_URL'].rstrip('/')
SMTP_HOST = environ['SMTP_HOST']
SMTP_PORT = int(environ['SMTP_PORT'])
SMTP_USER = environ['SMTP_USER']
SMTP_PASS = environ['SMTP_PASS']


def _path(s: str, *, mkdir: bool = False) -> Path:
    """Convert a string to a Path object and resolve it."""
    p = Path(s)
    try:
        p = p.resolve(strict=True)
    except FileNotFoundError:
        pass
    if mkdir:
        p.mkdir(parents=True, exist_ok=True)
    return p


# Configuration (optional)
TEST_ENV = getenv('TEST_ENV', '0').strip().lower() in {'1', 'true', 'yes'}
LOG_LEVEL = getenv('LOG_LEVEL', 'DEBUG' if TEST_ENV else 'INFO').upper()
GC_LOG = getenv('GC_LOG', '0').strip().lower() in {'1', 'true', 'yes'}

FREEZE_TEST_USER = getenv('FREEZE_TEST_USER', '1').strip().lower() in {'1', 'true', 'yes'}
FORCE_RELOAD_LOCALE_FILES = getenv('FORCE_RELOAD_LOCALE_FILES', '0').strip().lower() in {'1', 'true', 'yes'}
LEGACY_HIGH_PRECISION_TIME = getenv('LEGACY_HIGH_PRECISION_TIME', '0').strip().lower() in {'1', 'true', 'yes'}
LEGACY_SEQUENCE_ID_MARGIN = getenv('LEGACY_SEQUENCE_ID_MARGIN', '0').strip().lower() in {'1', 'true', 'yes'}

FILE_CACHE_DIR = _path(getenv('FILE_CACHE_DIR', 'data/cache'), mkdir=True)
FILE_CACHE_SIZE_GB = int(getenv('FILE_CACHE_SIZE_GB', '128'))
FILE_STORE_DIR = _path(getenv('FILE_STORE_DIR', 'data/store'), mkdir=True)
PLANET_DIR = _path(getenv('PLANET_DIR', 'data/planet'), mkdir=True)
PRELOAD_DIR = _path(getenv('PRELOAD_DIR', 'data/preload'))
REPLICATION_DIR = _path(getenv('REPLICATION_DIR', 'data/replication'), mkdir=True)

# see for options: https://docs.sqlalchemy.org/en/20/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.asyncpg
POSTGRES_LOG = getenv('POSTGRES_LOG', '0').strip().lower() in {'1', 'true', 'yes'}
# https://www.postgresql.org/docs/current/libpq-connect.html#LIBPQ-CONNSTRING-URIS
POSTGRES_URL = getenv('POSTGRES_URL', f'postgresql://postgres@/postgres?host={_path("data/postgres_unix")}&port=49560')

DUCKDB_MEMORY_LIMIT = getenv('DUCKDB_MEMORY_LIMIT', '8GB')
DUCKDB_TMPDIR = getenv('DUCKDB_TMPDIR')

SMTP_NOREPLY_FROM = getenv('SMTP_NOREPLY_FROM', SMTP_USER)
SMTP_MESSAGES_FROM = getenv('SMTP_MESSAGES_FROM', SMTP_USER)

API_URL = getenv('API_URL', APP_URL).rstrip('/')
ID_URL = getenv('ID_URL', APP_URL).rstrip('/')
RAPID_URL = getenv('RAPID_URL', APP_URL).rstrip('/')

GRAPHHOPPER_API_KEY = getenv('GRAPHHOPPER_API_KEY')
GRAPHHOPPER_URL = getenv('GRAPHHOPPER_URL', 'https://graphhopper.com')
NOMINATIM_URL = getenv('NOMINATIM_URL', 'https://nominatim.openstreetmap.org')
OSM_REPLICATION_URL = getenv(
    'OSM_REPLICATION_URL', 'https://osm-planet-eu-central-1.s3.dualstack.eu-central-1.amazonaws.com/planet/replication'
)
OSRM_URL = getenv('OSRM_URL', 'https://router.project-osrm.org')
OVERPASS_INTERPRETER_URL = getenv('OVERPASS_INTERPRETER_URL', 'https://overpass-api.de/api/interpreter')
VALHALLA_URL = getenv('VALHALLA_URL', 'https://valhalla1.openstreetmap.de')

# https://developers.facebook.com/docs/development/create-an-app/facebook-login-use-case
# https://developers.facebook.com/docs/facebook-login/guides/advanced/manual-flow/
FACEBOOK_OAUTH_PUBLIC = getenv('FACEBOOK_OAUTH_PUBLIC')
FACEBOOK_OAUTH_SECRET = getenv('FACEBOOK_OAUTH_SECRET')
# https://docs.github.com/en/apps/creating-github-apps/registering-a-github-app/registering-a-github-app
GITHUB_OAUTH_PUBLIC = getenv('GITHUB_OAUTH_PUBLIC')
GITHUB_OAUTH_SECRET = getenv('GITHUB_OAUTH_SECRET')
# https://developers.google.com/identity/openid-connect/openid-connect
GOOGLE_OAUTH_PUBLIC = getenv('GOOGLE_OAUTH_PUBLIC')
GOOGLE_OAUTH_SECRET = getenv('GOOGLE_OAUTH_SECRET')
# https://learn.microsoft.com/en-us/entra/identity-platform/v2-protocols-oidc
MICROSOFT_OAUTH_PUBLIC = getenv('MICROSOFT_OAUTH_PUBLIC')
# https://api.wikimedia.org/wiki/Special:AppManagement
WIKIMEDIA_OAUTH_PUBLIC = getenv('WIKIMEDIA_OAUTH_PUBLIC')
WIKIMEDIA_OAUTH_SECRET = getenv('WIKIMEDIA_OAUTH_SECRET')

TRUSTED_HOSTS: frozenset[str] = frozenset(
    host.casefold()
    for host in chain(
        (
            line
            for line in (line.strip() for line in Path('config/trusted_hosts.txt').read_text().splitlines())
            if line and not line.startswith('#')
        ),
        (urlsplit(url).hostname for _, url in LOCAL_CHAPTERS),
        getenv('TRUSTED_HOSTS_EXTRA', '').split(),
    )
    if host
)

TEST_USER_EMAIL_SUFFIX = '@test.test'
DELETED_USER_EMAIL_SUFFIX = '@deleted.invalid'  # SQL index depends on this value

FORCE_CRASH_REPORTING = getenv('FORCE_CRASH_REPORTING', '0').strip().lower() in {'1', 'true', 'yes'}
SENTRY_TRACES_SAMPLE_RATE = float(getenv('SENTRY_TRACES_SAMPLE_RATE', '1'))
SENTRY_PROFILES_SAMPLE_RATE = float(getenv('SENTRY_PROFILES_SAMPLE_RATE', '1'))

# Derived configuration
SECRET_32 = sha256(SECRET.encode()).digest()

SMTP_NOREPLY_FROM_HOST = SMTP_NOREPLY_FROM.rpartition('@')[2] if SMTP_NOREPLY_FROM else None
SMTP_MESSAGES_FROM_HOST = SMTP_MESSAGES_FROM.rpartition('@')[2] if SMTP_MESSAGES_FROM else None

POSTGRES_SQLALCHEMY_URL = POSTGRES_URL.replace('postgresql://', 'postgresql+asyncpg://', 1)

PYDANTIC_CONFIG = ConfigDict(
    extra='forbid',
    allow_inf_nan=False,
    strict=True,
    cache_strings='keys',
)


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

# Sentry configuration
if SENTRY_DSN := (getenv('SENTRY_DSN') if ('pytest' not in sys.modules) else None):
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        release=VERSION,
        environment=urlsplit(APP_URL).hostname,
        keep_alive=True,
        traces_sample_rate=SENTRY_TRACES_SAMPLE_RATE,
        trace_propagation_targets=None,
        profiles_sample_rate=SENTRY_PROFILES_SAMPLE_RATE,
        integrations=(PureEvalIntegration(),),
        _experiments={
            'continuous_profiling_auto_start': True,
        },
    )

SENTRY_REPLICATION_MONITOR = sentry_sdk.monitor(
    getenv('SENTRY_REPLICATION_MONITOR_SLUG', 'osm-ng-replication'),
    {
        'schedule': {
            'type': 'interval',
            'value': 1,
            'unit': 'minute',
        },
        'checkin_margin': 5,
        'max_runtime': 60,
        'failure_issue_threshold': 720,  # 12h
        'recovery_threshold': 1,
    },
)

SENTRY_CHANGESET_MANAGEMENT_MONITOR = sentry_sdk.monitor(
    getenv('SENTRY_CHANGESET_MANAGEMENT_MONITOR_SLUG', 'osm-ng-changeset-management'),
    {
        'schedule': {
            'type': 'interval',
            'value': 1,
            'unit': 'minute',
        },
        'checkin_margin': 5,
        'max_runtime': 60,
        'failure_issue_threshold': 60,  # 1h
        'recovery_threshold': 1,
    },
)

SENTRY_USERS_DELETED_TXT_MONITOR = sentry_sdk.monitor(
    getenv('SENTRY_USERS_DELETED_TXT_MONITOR_SLUG', 'osm-ng-users-deleted-txt'),
    {
        'schedule': {
            'type': 'interval',
            'value': 12,
            'unit': 'hour',
        },
        'checkin_margin': 5,
        'max_runtime': 60,
        'failure_issue_threshold': 2,  # 1d
        'recovery_threshold': 1,
    },
)
