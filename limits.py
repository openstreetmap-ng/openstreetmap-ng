from datetime import datetime, timedelta
from math import inf

_kb = 1024
_mb = 1024 * _kb

CHANGESET_OPEN_TIMEOUT = timedelta(days=1)
CHANGESET_IDLE_TIMEOUT = timedelta(hours=1)
CHANGESET_COMMENT_BODY_MAX_LENGTH = 5_000  # NOTE: breaking change: trim; value TBD
CHANGESET_QUERY_DEFAULT_LIMIT = 100
CHANGESET_QUERY_MAX_LIMIT = 100

# Q95: 1745, Q99: 3646, Q99.9: 10864, Q100: 636536
DIARY_ENTRY_BODY_MAX_LENGTH = 100_000  # NOTE: breaking change: trim; value TBD
DIARY_ENTRY_COMMENT_BODY_MAX_LENGTH = 5_000  # NOTE: breaking change: trim; value TBD

ELEMENT_MAX_TAGS = 123  # TODO:

ELEMENT_WAY_MAX_NODES_SINCE = datetime(2008, 12, 1)  # 1st December 2008, commit 635daf1
ELEMENT_WAY_MAX_NODES = 2_000

ELEMENT_RELATION_MAX_MEMBERS_SINCE = datetime(2022, 3, 1)  # 1st March 2022, commit 2efd73c
ELEMENT_RELATION_MAX_MEMBERS = 32_000

FAST_PASSWORD_CACHE_EXPIRE = timedelta(hours=8)

ISSUE_COMMENT_BODY_MAX_LENGTH = 5_000  # NOTE: breaking change: trim; value TBD

MAIL_PROCESSING_TIMEOUT = timedelta(minutes=1)
MAIL_UNPROCESSED_EXPIRE = timedelta(days=3)  # TODO: expire index

MAP_QUERY_AREA_MAX_SIZE = 0.25  # in square degrees
MAP_QUERY_LEGACY_NODES_LIMIT = 50_000

MESSAGE_BODY_MAX_LENGTH = 50_000  # NOTE: breaking change: trim; value TBD
MESSAGE_FROM_MAIL_DATE_VALIDITY = timedelta(days=1)

NEARBY_USERS_LIMIT = 30
NEARBY_USERS_RADIUS_METERS = 50_000

NOMINATIM_CACHE_EXPIRE = timedelta(days=30)

NOTE_COMMENT_BODY_MAX_LENGTH = 2_000
NOTE_FRESHLY_CLOSED_TIMEOUT = timedelta(days=7)
NOTE_QUERY_AREA_MAX_SIZE = 25  # in square degrees
NOTE_QUERY_DEFAULT_LIMIT = 100
NOTE_QUERY_DEFAULT_CLOSED = 7  # open + max 7 days closed
NOTE_QUERY_LEGACY_MAX_LIMIT = 10_000

OAUTH1_TIMESTAMP_EXPIRE = timedelta(days=2)
OAUTH1_TIMESTAMP_VALIDITY = timedelta(days=1)

POLICY_LEGACY_IMAGERY_BLACKLISTS = [
    '.*\\.google(apis)?\\..*/.*',
    'http://xdworld\\.vworld\\.kr:8080/.*',
    '.*\\.here\\.com[/:].*',
    '.*\\.mapy\\.cz.*'
]

REPORT_BODY_MAX_LENGTH = 50_000  # NOTE: breaking change: trim; value TBD

TRACE_FILE_MAX_SIZE = 50 * _mb
TRACE_FILE_UNCOMPRESSED_MAX_SIZE = 80 * _mb
TRACE_FILE_ARCHIVE_MAX_FILES = 10
TRACE_FILE_COMPRESS_ZSTD_THREADS = 1
TRACE_FILE_COMPRESS_ZSTD_LEVEL = (
    # useful: zstd -f -b11 -e19 test_trace.gpx
    (0.25 * _mb, 19),
    (1.00 * _mb, 15),
    (inf, 13)
)

TRACE_POINT_QUERY_AREA_MAX_SIZE = 0.25  # in square degrees
TRACE_POINT_QUERY_DEFAULT_LIMIT = 5_000
TRACE_POINT_QUERY_MAX_LIMIT = 5_000
TRACE_POINT_QUERY_LEGACY_MAX_SKIP = 45_000
TRACE_POINT_QUERY_CURSOR_EXPIRE = timedelta(hours=1)

USER_BLOCK_BODY_MAX_LENGTH = 50_000  # NOTE: breaking change: trim; value TBD
USER_DESCRIPTION_MAX_LENGTH = 100_000  # NOTE: breaking change: trim; value TBD

XML_PARSE_MAX_SIZE = 50 * _mb  # the same as CGImap

HTTP_BODY_MAX_SIZE = max(TRACE_FILE_MAX_SIZE, XML_PARSE_MAX_SIZE) + 5 * _mb  # MAX + 5 MB
