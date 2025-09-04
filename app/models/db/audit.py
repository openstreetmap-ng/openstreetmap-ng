from datetime import datetime
from ipaddress import IPv4Address, IPv6Address
from typing import Literal, NewType, NotRequired, TypedDict, get_args

from app.models.db.oauth2_application import OAuth2Application
from app.models.db.user import UserDisplay
from app.models.types import ApplicationId, DisplayName, Email, UserId

AuditId = NewType('AuditId', int)
AuditType = Literal[
    'admin_task',
    'auth_api',
    'auth_fail',
    'auth_web',
    'change_display_name',
    'change_email',
    'change_password',
    'change_roles',
    'impersonate',
    'rate_limit',
    'view_admin_users',
    'view_audit',
    # TODO: 'schedule_user_delete',
]

AUDIT_TYPE_SET = frozenset[AuditType](get_args(AuditType))


class AuditEventInit(TypedDict):
    id: AuditId
    type: AuditType
    ip: IPv4Address | IPv6Address
    user_agent: str | None
    user_id: UserId | None
    target_user_id: UserId | None
    application_id: ApplicationId | None
    email: Email | None
    display_name: DisplayName | None
    extra: str | None


class AuditEvent(AuditEventInit):
    created_at: datetime

    # runtime
    user: NotRequired[UserDisplay]
    target_user: NotRequired[UserDisplay]
    application: NotRequired[OAuth2Application]
