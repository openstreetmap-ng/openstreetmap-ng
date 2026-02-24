from datetime import datetime
from ipaddress import IPv4Address, IPv6Address
from typing import Any, NotRequired, TypedDict, get_args

from app.config import AUDIT_POLICY
from app.models.db.oauth2_application import OAuth2Application
from app.models.db.user import UserDisplay
from app.models.proto.audit_types import Type
from app.models.types import ApplicationId, AuditId, OAuth2TokenId, UserId

AUDIT_TYPE_VALUES = list[Type](get_args(Type.__value__))

for t in AUDIT_TYPE_VALUES:
    assert hasattr(AUDIT_POLICY, t), f'AUDIT_POLICY is missing policy for {t!r}'


class AuditEventInit(TypedDict):
    id: AuditId
    type: Type
    ip: IPv4Address | IPv6Address
    user_agent: str | None
    user_id: UserId | None
    target_user_id: UserId | None
    application_id: ApplicationId | None
    token_id: OAuth2TokenId | None
    extra: dict[str, Any] | None


class AuditEvent(AuditEventInit):
    created_at: datetime

    # runtime
    user: NotRequired[UserDisplay]
    target_user: NotRequired[UserDisplay]
    application: NotRequired[OAuth2Application]
