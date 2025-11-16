from datetime import datetime
from ipaddress import IPv4Address, IPv6Address
from typing import Any, Literal, NotRequired, TypedDict, get_args

from app.config import AUDIT_POLICY
from app.models.db.oauth2_application import OAuth2Application
from app.models.db.user import UserDisplay
from app.models.types import ApplicationId, UserId

AuditType = Literal[
    'add_2fa',
    'add_connected_account',
    'admin_task',
    'auth_2fa_fail',
    'auth_api',
    'auth_fail',
    'auth_web',
    'authorize_app',
    'change_app_settings',
    'change_display_name',
    'change_email',
    'change_password',
    'change_roles',
    'close_changeset',
    'create_app',
    'create_changeset_comment',
    'create_changeset',
    'create_diary_comment',
    'create_diary',
    'create_note_comment',
    'create_note',
    'create_pat',
    'create_trace',
    'delete_diary',
    'delete_prefs',
    'delete_trace',
    'edit_map',
    'impersonate',
    'nsfw_image',
    'rate_limit',
    'remove_2fa',
    'remove_connected_account',
    'request_change_email',
    'request_reset_password',
    'revoke_app_all_users',
    'revoke_app',
    'send_message',
    'update_changeset',
    'update_diary',
    'update_note_status',
    'update_prefs',
    'update_trace',
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
    extra: dict[str, Any] | None


class AuditEvent(AuditEventInit):
    created_at: datetime

    # runtime
    user: NotRequired[UserDisplay]
    target_user: NotRequired[UserDisplay]
    application: NotRequired[OAuth2Application]
