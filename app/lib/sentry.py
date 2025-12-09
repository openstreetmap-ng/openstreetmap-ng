import logging
from sys import modules
from urllib.parse import urlsplit

import sentry_sdk
from pydantic import Field
from sentry_sdk.integrations.gnu_backtrace import GnuBacktraceIntegration
from sentry_sdk.integrations.pure_eval import PureEvalIntegration

from app.config import APP_URL, VERSION
from app.lib.pydantic_settings_integration import pydantic_settings_integration

SENTRY_DSN = ''

SENTRY_TRACES_SAMPLE_RATE: float = Field(1.0, ge=0, le=1)
SENTRY_PROFILE_SESSION_SAMPLE_RATE: float = Field(1.0, ge=0, le=1)

SENTRY_REPLICATION_MONITOR_SLUG = 'osm-ng-replication'
SENTRY_CHANGESET_MANAGEMENT_MONITOR_SLUG = 'osm-ng-changeset-management'
SENTRY_ELEMENT_SPATIAL_MONITOR_SLUG = 'osm-ng-element-spatial'
SENTRY_USERS_DELETED_TXT_MONITOR_SLUG = 'osm-ng-users-deleted-txt'
SENTRY_AUDIT_MANAGEMENT_MONITOR_SLUG = 'osm-ng-audit-management'

pydantic_settings_integration(
    __name__, globals(), name_filter=lambda name: name.startswith('SENTRY_')
)

if SENTRY_DSN and 'pytest' not in modules:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        release=VERSION,
        environment=urlsplit(APP_URL).hostname,
        integrations=[
            GnuBacktraceIntegration(),
            PureEvalIntegration(),
        ],
        keep_alive=True,
        traces_sample_rate=SENTRY_TRACES_SAMPLE_RATE,
        trace_propagation_targets=None,
        profile_session_sample_rate=SENTRY_PROFILE_SESSION_SAMPLE_RATE,
        profile_lifecycle='trace',
    )
    logging.debug('Initialized Sentry SDK')

SENTRY_REPLICATION_MONITOR = sentry_sdk.monitor(
    SENTRY_REPLICATION_MONITOR_SLUG,
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
    SENTRY_CHANGESET_MANAGEMENT_MONITOR_SLUG,
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

SENTRY_ELEMENT_SPATIAL_MONITOR = sentry_sdk.monitor(
    SENTRY_ELEMENT_SPATIAL_MONITOR_SLUG,
    {
        'schedule': {
            'type': 'interval',
            'value': 5,
            'unit': 'minute',
        },
        'checkin_margin': 5,
        'max_runtime': 3600,
        'failure_issue_threshold': 60,  # 5h
        'recovery_threshold': 1,
    },
)


SENTRY_USERS_DELETED_TXT_MONITOR = sentry_sdk.monitor(
    SENTRY_USERS_DELETED_TXT_MONITOR_SLUG,
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

SENTRY_AUDIT_MANAGEMENT_MONITOR = sentry_sdk.monitor(
    SENTRY_AUDIT_MANAGEMENT_MONITOR_SLUG,
    {
        'schedule': {
            'type': 'interval',
            'value': 24,
            'unit': 'hour',
        },
        'checkin_margin': 60,
        'max_runtime': 60,
        'failure_issue_threshold': 2,  # 2d
        'recovery_threshold': 1,
    },
)
