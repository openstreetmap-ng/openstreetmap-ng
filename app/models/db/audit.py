from datetime import datetime
from ipaddress import IPv4Address, IPv6Address
from typing import Literal, NotRequired, TypedDict, get_args

from app.config import AUDIT_POLICY
from app.models.db.oauth2_application import OAuth2Application
from app.models.db.user import UserDisplay
from app.models.types import ApplicationId, UserId

AuditType = Literal[
    'admin_task',
    'app_authorize',
    'app_revoke_all_users',
    'app_revoke',
    'auth_api',
    'auth_fail',
    'auth_web',
    'change_app_settings',
    'change_display_name',
    'change_email',
    'change_password',
    'change_roles',
    'connected_account_add',
    'connected_account_remove',
    'create_app',
    'create_pat',
    'impersonate',
    'nsfw_image',
    'rate_limit',
    'request_change_email',
    'request_reset_password',
    'send_message',
    'view_admin_applications',
    'view_admin_users',
    'view_audit',
    # TODO: 'schedule_user_delete',
]

AUDIT_TYPE_VALUES = list[AuditType](get_args(AuditType))

for t in AUDIT_TYPE_VALUES:
    assert hasattr(AUDIT_POLICY, t), f'AUDIT_POLICY is missing policy for {t!r}'


class AuditEventInit(TypedDict):
    type: AuditType
    ip: IPv4Address | IPv6Address
    user_agent: str | None
    user_id: UserId | None
    target_user_id: UserId | None
    application_id: ApplicationId | None
    extra: str | None


class AuditEvent(AuditEventInit):
    created_at: datetime

    # runtime
    user: NotRequired[UserDisplay]
    target_user: NotRequired[UserDisplay]
    application: NotRequired[OAuth2Application]
