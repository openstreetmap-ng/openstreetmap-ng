from datetime import datetime
from ipaddress import IPv4Address, IPv6Address
from typing import Literal, NewType, TypedDict

from app.models.types import ApplicationId, DisplayName, Email, UserId

AuditId = NewType('AuditId', int)
AuditType = Literal[
    'admin_task',
    # TODO: 'auth_api',
    # TODO: 'auth_web',
    'change_display_name',
    'change_email',
    'change_password',
    # TODO: 'rate_limit',
    # TODO: 'schedule_user_delete',
    # TODO: 'view_admin_users',
]


class AuditEventInit(TypedDict):
    id: AuditId
    type: AuditType
    ip: IPv4Address | IPv6Address
    user_agent: str | None
    user_id: UserId | None
    application_id: ApplicationId | None
    email: Email | None
    display_name: DisplayName | None
    extra: str | None


class AuditEvent(AuditEventInit):
    created_at: datetime
