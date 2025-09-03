from datetime import timedelta
from hashlib import sha256
from logging.config import dictConfig
from os import chdir
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import urlsplit

from githead import githead
from pydantic import (
    AliasChoices,
    BeforeValidator,
    ByteSize,
    ConfigDict,
    DirectoryPath,
    Field,
    SecretBytes,
    SecretStr,
)

from app.lib.local_chapters import LOCAL_CHAPTERS as _LOCAL_CHAPTERS
from app.lib.pydantic_settings_integration import pydantic_settings_integration


def _ByteSize(v: str) -> ByteSize:  # noqa: N802
    return ByteSize._validate(v, None)  # noqa: SLF001  # type: ignore


def _validate_dir(v) -> Path:
    """Resolve directory to an absolute path and ensure it exists."""
    v = Path(v)
    v.mkdir(parents=True, exist_ok=True)
    return v.resolve(strict=True)


type _MakeDir = Annotated[Path, BeforeValidator(_validate_dir)]


def _strip_validator(chars: str, /) -> BeforeValidator:
    """Create a validator that strips the given characters from the input text."""

    def validate(v):
        return str(v).strip(chars)

    return BeforeValidator(validate)


type _StripSlash = Annotated[str, _strip_validator('/')]


# Change working directory to the project root
chdir(Path(__file__).parent.parent)

# -------------------- Required Configuration --------------------

SECRET: SecretStr = Field()
APP_URL: _StripSlash = Field()
SMTP_HOST: str = Field()
SMTP_PORT: int = Field(gt=0, lt=1 << 16)
SMTP_USER: str = Field()
SMTP_PASS: SecretStr = Field()
POSTGRES_URL: str = Field()
DUCKDB_MEMORY_LIMIT: str = Field()

# -------------------- System Configuration --------------------

# Core settings
ENV: Literal['dev', 'test', 'prod'] = 'prod'
LOG_LEVEL: Literal['DEBUG', 'INFO', 'WARNING'] | None = None
LEGACY_HIGH_PRECISION_TIME = False

# Storage paths
FILE_CACHE_DIR: _MakeDir = Path('data/cache')
FILE_CACHE_SIZE = _ByteSize('128 GiB')
PLANET_DIR: _MakeDir = Path('data/planet')
PRELOAD_DIR: _MakeDir = Path('data/preload')
REPLICATION_DIR: _MakeDir = Path('data/replication')

# Storage URLs
AVATAR_STORAGE_URL = 'db://avatar'
BACKGROUND_STORAGE_URL = 'db://background'
TRACE_STORAGE_URL = 'db://trace'

# Database connections
DUCKDB_TMPDIR: DirectoryPath | None = None

# Replication processing
REPLICATION_CONVERT_ELEMENT_BATCH_SIZE = 500_000_000

# -------------------- API and Services Integration --------------------

# Internal URLs
API_URL: _StripSlash = Field(validation_alias=AliasChoices('API_URL', 'APP_URL'))
ID_URL: _StripSlash = Field(validation_alias=AliasChoices('ID_URL', 'APP_URL'))
RAPID_URL: _StripSlash = Field(validation_alias=AliasChoices('RAPID_URL', 'APP_URL'))

# External services
GRAPHHOPPER_API_KEY = SecretStr('')
GRAPHHOPPER_URL = 'https://graphhopper.com'
NOMINATIM_URL = 'https://nominatim.openstreetmap.org'
OSM_REPLICATION_URL = (
    'https://osm-planet-eu-central-1.s3.dualstack.eu-central-1.amazonaws.com/planet'
)
OSM_OLD_REPLICATION_URL = 'https://planet.openstreetmap.org'
OSRM_URL = 'https://router.project-osrm.org'
OVERPASS_INTERPRETER_URL = 'https://overpass-api.de/api/interpreter'
VALHALLA_URL = 'https://valhalla1.openstreetmap.de'

# API and HTTP settings
HTTP_TIMEOUT = timedelta(seconds=20)
URLSAFE_BLACKLIST = '/;.,?%#'
TRACE_FILE_UPLOAD_MAX_SIZE = _ByteSize('50 MiB')
XML_PARSE_MAX_SIZE = _ByteSize('50 MiB')  # the same as CGImap
REQUEST_PATH_QUERY_MAX_LENGTH = 2000

# Compression settings
COMPRESS_HTTP_MIN_SIZE = _ByteSize('1 KiB')
COMPRESS_HTTP_ZSTD_LEVEL = 3
COMPRESS_HTTP_BROTLI_QUALITY = 3
COMPRESS_HTTP_GZIP_LEVEL = 3
COMPRESS_REPLICATION_GZIP_LEVEL = 9
COMPRESS_REPLICATION_GZIP_THREADS: int | float = 0.5

# Security settings
CORS_MAX_AGE = timedelta(days=1)
HSTS_MAX_AGE = timedelta(days=365)
RATE_LIMIT_OPTIMISTIC_BLACKLIST_EXPIRE = timedelta(minutes=10)
TRUSTED_HOSTS_EXTRA = ''

# -------------------- Authentication and User --------------------

# Cookie settings
COOKIE_AUTH_MAX_AGE = timedelta(days=365)
COOKIE_GENERIC_MAX_AGE = timedelta(days=365)
TEST_SITE_ACKNOWLEDGED_MAX_AGE = timedelta(days=365)
UNSUPPORTED_BROWSER_OVERRIDE_MAX_AGE = timedelta(days=365)

# Account settings
EMAIL_MIN_LENGTH = 5
PASSWORD_MIN_LENGTH = 6  # TODO: check pwned passwords
DISPLAY_NAME_MAX_LENGTH = 255
TIMEZONE_MAX_LENGTH = 56  # TODO: check
ACTIVE_SESSIONS_DISPLAY_LIMIT = 100
USER_PENDING_EXPIRE = timedelta(days=365)  # 1 year
USER_SCHEDULED_DELETE_DELAY = timedelta(days=7)

# Profile
AVATAR_MAX_FILE_SIZE = _ByteSize('80 KiB')
AVATAR_MAX_MEGAPIXELS = 384 * 384  # (resolution)
AVATAR_MAX_RATIO = 2.0
BACKGROUND_MAX_FILE_SIZE = _ByteSize('320 KiB')
BACKGROUND_MAX_MEGAPIXELS = 4096 * 512  # (resolution)
BACKGROUND_MAX_RATIO = 2 * 5.5  # 2 * ratio on website
USER_ACTIVITY_CHART_WEEKS = 26
USER_BLOCK_BODY_MAX_LENGTH = 20_000  # NOTE: value TBD
USER_DESCRIPTION_MAX_LENGTH = 20_000  # NOTE: value TBD
USER_NEW_DAYS = 21
USER_RECENT_ACTIVITY_ENTRIES = 6

# User preferences
USER_PREF_BULK_SET_LIMIT = 150

# User tokens
# TODO: delete unconfirmed accounts
USER_TOKEN_ACCOUNT_CONFIRM_EXPIRE = timedelta(days=30)
USER_TOKEN_EMAIL_CHANGE_EXPIRE = timedelta(days=1)
USER_TOKEN_EMAIL_REPLY_EXPIRE = timedelta(days=2 * 365)  # 2 years
USER_TOKEN_RESET_PASSWORD_EXPIRE = timedelta(days=1)

# OAuth/OpenID settings
AUTH_PROVIDER_UID_MAX_LENGTH = 255
AUTH_PROVIDER_STATE_MAX_AGE = timedelta(hours=2)
AUTH_PROVIDER_VERIFICATION_MAX_AGE = timedelta(hours=2)
OAUTH_APP_ADMIN_LIMIT = 100
OAUTH_APP_NAME_MAX_LENGTH = 50
OAUTH_APP_URI_LIMIT = 10
OAUTH_APP_URI_MAX_LENGTH = 1000
OAUTH_AUTH_USER_LIMIT = 500  # TODO: revoke oldest authorizations
OAUTH_AUTHORIZATION_CODE_TIMEOUT = timedelta(minutes=3)  # TODO: cleanup periodically
OAUTH_CODE_CHALLENGE_MAX_LENGTH = 255
OAUTH_PAT_LIMIT = 100
OAUTH_PAT_NAME_MAX_LENGTH = 50
OAUTH_SECRET_PREVIEW_LENGTH = 7
OAUTH_SILENT_AUTH_QUERY_SESSION_LIMIT = 10
OPENID_DISCOVERY_CACHE_EXPIRE = timedelta(hours=8)
OPENID_DISCOVERY_HTTP_TIMEOUT = timedelta(seconds=10)

# OAuth providers
# https://developers.facebook.com/docs/development/create-an-app/facebook-login-use-case
# https://developers.facebook.com/docs/facebook-login/guides/advanced/manual-flow/
FACEBOOK_OAUTH_PUBLIC = ''
FACEBOOK_OAUTH_SECRET = SecretStr('')
# https://docs.github.com/en/apps/creating-github-apps/registering-a-github-app/registering-a-github-app
GITHUB_OAUTH_PUBLIC = ''
GITHUB_OAUTH_SECRET = SecretStr('')
# https://developers.google.com/identity/openid-connect/openid-connect
GOOGLE_OAUTH_PUBLIC = ''
GOOGLE_OAUTH_SECRET = SecretStr('')
# https://learn.microsoft.com/en-us/entra/identity-platform/v2-protocols-oidc
MICROSOFT_OAUTH_PUBLIC = ''
# https://api.wikimedia.org/wiki/Special:AppManagement
WIKIMEDIA_OAUTH_PUBLIC = ''
WIKIMEDIA_OAUTH_SECRET = SecretStr('')

# -------------------- Email Communication --------------------

# Email configuration
SMTP_NOREPLY_FROM: str = Field(
    validation_alias=AliasChoices('SMTP_NOREPLY_FROM', 'SMTP_USER')
)
SMTP_MESSAGES_FROM: str = Field(
    validation_alias=AliasChoices('SMTP_MESSAGES_FROM', 'SMTP_USER')
)
EMAIL_REPLY_USAGE_LIMIT = 10

# Email processing settings
MAIL_PROCESSING_TIMEOUT = timedelta(minutes=1)
MAIL_UNPROCESSED_EXPONENT = 2.0  # 1 min, 2 min, 4 min, etc.
MAIL_UNPROCESSED_EXPIRE = timedelta(days=3)

# -------------------- Content and Map Features --------------------

# Elements
ELEMENT_HISTORY_PAGE_SIZE = 10
ELEMENT_WAY_MEMBERS_LIMIT = 2_000
ELEMENT_RELATION_MEMBERS_LIMIT = 32_000
FEATURE_PREFIX_TAGS_LIMIT = 100
LEGACY_GEOM_SKIP_MISSING_NODES = False

# Tags
TAGS_LIMIT = 600
TAGS_MAX_SIZE = _ByteSize('64 KiB')
TAGS_KEY_MAX_LENGTH = 63

# Changesets
CHANGESET_IDLE_TIMEOUT = timedelta(hours=1)
CHANGESET_OPEN_TIMEOUT = timedelta(days=1)
CHANGESET_EMPTY_DELETE_TIMEOUT = timedelta(hours=1)
CHANGESET_NEW_BBOX_MIN_DISTANCE = 0.5  # degrees
CHANGESET_NEW_BBOX_MIN_RATIO = 3.0
CHANGESET_BBOX_LIMIT = 10
CHANGESET_QUERY_DEFAULT_LIMIT = 100
CHANGESET_QUERY_MAX_LIMIT = 100
CHANGESET_QUERY_WEB_LIMIT = 30
CHANGESET_COMMENT_BODY_MAX_LENGTH = 5_000
CHANGESET_COMMENTS_PAGE_SIZE = 15
OPTIMISTIC_DIFF_RETRY_TIMEOUT = timedelta(seconds=30)

# Notes
NOTE_FRESHLY_CLOSED_TIMEOUT = timedelta(days=7)
NOTE_QUERY_AREA_MAX_SIZE = 25.0  # in square degrees
NOTE_QUERY_DEFAULT_LIMIT = 100
NOTE_QUERY_DEFAULT_CLOSED = 7.0  # open + max 7 days closed
NOTE_QUERY_WEB_LIMIT = 200
NOTE_QUERY_LEGACY_MAX_LIMIT = 10_000
NOTE_USER_PAGE_SIZE = 10
NOTE_COMMENT_BODY_MAX_LENGTH = 2_000
NOTE_COMMENTS_PAGE_SIZE = 15

# Reports
REPORT_LIST_PAGE_SIZE = 15
REPORT_COMMENT_BODY_MAX_LENGTH = 50_000
REPORT_COMMENTS_PAGE_SIZE = 15

# Search and Query
MAP_QUERY_AREA_MAX_SIZE = 0.25  # in square degrees
MAP_QUERY_LEGACY_NODES_LIMIT = 50_000
SEARCH_LOCAL_AREA_LIMIT = 100.0  # in square degrees
SEARCH_LOCAL_MAX_ITERATIONS = 7
SEARCH_LOCAL_RATIO = 0.5  # [0 - 1], smaller = more locality
SEARCH_QUERY_MAX_LENGTH = 255
SEARCH_RESULTS_LIMIT = 100  # nominatim has hard-coded upper limit of 50
QUERY_FEATURES_RESULTS_LIMIT = 50
NEARBY_USERS_LIMIT = 30
NEARBY_USERS_RADIUS_METERS = 50_000.0

# Traces
TRACE_FILE_DECOMPRESSED_MAX_SIZE = _ByteSize('80 MiB')
TRACE_FILE_ARCHIVE_MAX_FILES = 10
TRACE_FILE_MAX_LAYERS = 2
TRACE_FILE_COMPRESS_ZSTD_THREADS = 4
TRACE_FILE_COMPRESS_ZSTD_LEVEL = 6
TRACE_POINT_QUERY_AREA_MAX_SIZE = 0.25  # in square degrees
TRACE_POINT_QUERY_DEFAULT_LIMIT = 5_000
TRACE_POINT_QUERY_MAX_LIMIT = 5_000
TRACE_POINT_QUERY_LEGACY_MAX_SKIP = 45_000
TRACE_POINT_QUERY_CURSOR_EXPIRE = timedelta(hours=1)
TRACES_LIST_PAGE_SIZE = 30
TRACE_TAG_MAX_LENGTH = 40
TRACE_TAGS_LIMIT = 10

# Diary
DIARY_TITLE_MAX_LENGTH = 255
DIARY_BODY_MAX_LENGTH = 100_000  # Q95: 1745, Q99: 3646, Q99.9: 10864, Q100: 636536
DIARY_COMMENT_BODY_MAX_LENGTH = 5_000
DIARY_LIST_PAGE_SIZE = 15
DIARY_COMMENTS_PAGE_SIZE = 15
LOCALE_CODE_MAX_LENGTH = 15

# Messages
MESSAGE_RECIPIENTS_LIMIT = 5
MESSAGE_SUBJECT_MAX_LENGTH = 100
MESSAGE_BODY_MAX_LENGTH = 50_000
MESSAGES_INBOX_PAGE_SIZE = 50

# -------------------- Administration --------------------

# Audit
AUDIT_DISCARD_REPEATED_AUTH_API = timedelta(days=1)
AUDIT_DISCARD_REPEATED_AUTH_FAIL = timedelta(minutes=1)
AUDIT_DISCARD_REPEATED_AUTH_WEB = timedelta(days=1)
AUDIT_DISCARD_REPEATED_RATE_LIMIT = timedelta(hours=6)
AUDIT_LIST_PAGE_SIZE = 50
AUDIT_RETENTION_ADMIN_TASK = timedelta(days=60)
AUDIT_RETENTION_AUTH_API = timedelta(days=14)
AUDIT_RETENTION_AUTH_FAIL = timedelta(days=30)
AUDIT_RETENTION_AUTH_WEB = timedelta(days=14)
AUDIT_RETENTION_CHANGE_DISPLAY_NAME = timedelta(days=30)
AUDIT_RETENTION_CHANGE_EMAIL = timedelta(days=60)
AUDIT_RETENTION_CHANGE_PASSWORD = timedelta(days=60)
AUDIT_RETENTION_CHANGE_ROLES = timedelta(days=60)
AUDIT_RETENTION_IMPERSONATE = timedelta(days=60)
AUDIT_RETENTION_RATE_LIMIT = timedelta(days=14)
AUDIT_SAMPLE_RATE_AUTH = 0.05
AUDIT_SAMPLE_RATE_RATE_LIMIT = 0.05
AUDIT_USER_AGENT_MAX_LENGTH = 200

# Task management
ADMIN_TASK_HEARTBEAT_INTERVAL = timedelta(minutes=1)
ADMIN_TASK_TIMEOUT = timedelta(minutes=3)

# User management
USER_EXPORT_LIMIT = 1_000_000
USER_LIST_PAGE_SIZE = 50

# -------------------- Caching and Performance --------------------

# General cache settings
CACHE_DEFAULT_EXPIRE = timedelta(days=3)
FILE_CACHE_LOCK_TIMEOUT = timedelta(seconds=15)

# External service caches
DNS_CACHE_EXPIRE = timedelta(minutes=10)
EMAIL_DELIVERABILITY_CACHE_EXPIRE = timedelta(minutes=20)
EMAIL_DELIVERABILITY_DNS_TIMEOUT = timedelta(seconds=10)
NOMINATIM_REVERSE_CACHE_EXPIRE = timedelta(days=7)
NOMINATIM_REVERSE_HTTP_TIMEOUT = timedelta(seconds=10)
NOMINATIM_SEARCH_CACHE_EXPIRE = timedelta(hours=1)
NOMINATIM_SEARCH_HTTP_TIMEOUT = timedelta(seconds=30)
OVERPASS_CACHE_EXPIRE = timedelta(minutes=10)
S3_CACHE_EXPIRE = timedelta(days=1)

# Content caches
DYNAMIC_AVATAR_CACHE_EXPIRE = timedelta(days=30)
GRAVATAR_CACHE_EXPIRE = timedelta(days=7)
INITIALS_CACHE_MAX_AGE = timedelta(days=7)
RICH_TEXT_CACHE_EXPIRE = timedelta(hours=8)
STATIC_CACHE_MAX_AGE = timedelta(days=30)
STATIC_CACHE_STALE = timedelta(days=30)

pydantic_settings_integration(__name__, globals())

# -------------------- Constant or derived configuration --------------------

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

SECRET_32 = SecretBytes(sha256(SECRET.get_secret_value().encode()).digest())

APP_DOMAIN = urlsplit(APP_URL).netloc
API_DOMAIN = urlsplit(API_URL).netloc

REQUEST_BODY_MAX_SIZE = (  #
    max(TRACE_FILE_UPLOAD_MAX_SIZE, XML_PARSE_MAX_SIZE) + _ByteSize('8 KiB')
)

TEST_USER_EMAIL_SUFFIX = '@test.test'
DELETED_USER_EMAIL_SUFFIX = '@deleted.invalid'  # SQL index depends on this value

SMTP_NOREPLY_FROM_HOST = (
    SMTP_NOREPLY_FROM.rpartition('@')[2] if SMTP_NOREPLY_FROM else None
)
SMTP_MESSAGES_FROM_HOST = (
    SMTP_MESSAGES_FROM.rpartition('@')[2] if SMTP_MESSAGES_FROM else None
)

TRUSTED_HOSTS = frozenset[str](
    h.casefold()
    for host in (
        *(
            line
            for line in Path('config/trusted_hosts.txt').read_text().splitlines()
            if not line.lstrip().startswith('#')
        ),
        *(urlsplit(lc.url).hostname or '' for lc in _LOCAL_CHAPTERS),
        *TRUSTED_HOSTS_EXTRA.split(),
    )
    if (h := host.strip())
)

PYDANTIC_CONFIG = ConfigDict(
    extra='forbid',
    arbitrary_types_allowed=True,
    allow_inf_nan=False,
    strict=True,
    cache_strings='keys',
)

if LOG_LEVEL is None:
    LOG_LEVEL = 'INFO' if ENV == 'prod' else 'DEBUG'  # pyright: ignore[reportConstantRedefinition]

# -------------------- Logging configuration --------------------

dictConfig({
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
                'botocore',
                'hpack',
                'httpx',
                'httpcore',
                'markdown_it',
                'multipart',
                'python_multipart',
            )
        },
    },
})
