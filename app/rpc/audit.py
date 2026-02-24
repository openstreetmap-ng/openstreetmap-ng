from asyncio import TaskGroup
from ipaddress import ip_address, ip_network
from typing import override

from connectrpc.request import RequestContext
from starlette.exceptions import HTTPException
from starlette.status import HTTP_400_BAD_REQUEST

from app.config import AUDIT_LIST_PAGE_SIZE
from app.lib.auth_context import require_web_user
from app.lib.date_utils import datetime_unix, unix_datetime
from app.lib.standard_pagination import sp_paginate_table
from app.models.db.audit import AuditEvent as DBAuditEvent
from app.models.db.oauth2_application import (
    oauth2_app_avatar_url,
)
from app.models.db.user import user_proto
from app.models.proto.audit_connect import (
    Service,
    ServiceASGIApplication,
)
from app.models.proto.audit_pb2 import (
    Event as ProtoAuditEvent,
)
from app.models.proto.audit_pb2 import (
    Filters,
    ListRequest,
    ListResponse,
)
from app.models.proto.audit_pb2 import (
    Type as ProtoAuditType,
)
from app.models.types import ApplicationId
from app.queries.audit_query import AuditQuery
from app.queries.oauth2_application_query import OAuth2ApplicationQuery
from app.queries.user_query import UserQuery
from app.services.audit_service import audit


class _Service(Service):
    @override
    async def list(self, request: ListRequest, ctx: RequestContext):
        require_web_user('role_administrator')
        audit(
            'view_audit',
            extra_proto=request.filters,
            extra={'action': 'list'},
        ).close()

        (
            ip,
            user,
            application_id,
            audit_type,
            created_after,
            created_before,
        ) = _filters_parse(request.filters)

        where_clause, params = await AuditQuery.where_clause(
            ip=ip,
            user=user,
            application_id=application_id,
            type=audit_type,
            created_after=created_after,
            created_before=created_before,
        )

        events, state = await sp_paginate_table(
            DBAuditEvent,
            request.state.SerializeToString(),
            table='audit',
            where=where_clause,
            params=params,
            page_size=AUDIT_LIST_PAGE_SIZE,
            cursor_column='created_at',
            cursor_kind='datetime',
            order_dir='desc',
        )

        async with TaskGroup() as tg:
            tg.create_task(UserQuery.resolve_users(events))
            tg.create_task(
                UserQuery.resolve_users(
                    events, user_id_key='target_user_id', user_key='target_user'
                )
            )
            apps = await OAuth2ApplicationQuery.resolve_applications(events)
            tg.create_task(UserQuery.resolve_users(apps))

        return ListResponse(
            state=state,
            events=[_event_proto(event) for event in events],
        )


def _parse_ip_filter(value: str):
    for parser in (ip_address, ip_network):
        try:
            return parser(value)
        except ValueError:
            pass
    raise HTTPException(HTTP_400_BAD_REQUEST, 'Invalid IP filter')


def _filters_parse(filters: Filters):
    ip = (
        _parse_ip_filter(value)
        if filters.HasField('ip') and (value := filters.ip.strip())
        else None
    )
    user = (
        value if filters.HasField('user') and (value := filters.user.strip()) else None
    )
    application_id = (
        ApplicationId(filters.application_id)
        if filters.HasField('application_id')
        else None
    )
    audit_type = ProtoAuditType.Name(filters.type) if filters.HasField('type') else None
    created_after = (
        unix_datetime(filters.created_after)
        if filters.HasField('created_after')
        else None
    )
    created_before = (
        unix_datetime(filters.created_before)
        if filters.HasField('created_before')
        else None
    )

    return ip, user, application_id, audit_type, created_after, created_before


def _event_proto(event: DBAuditEvent):
    application = event.get('application')
    user = event.get('user')
    target_user = event.get('target_user')
    extra = event['extra']

    return ProtoAuditEvent(
        id=event['id'],
        type=event['type'],
        created_at=datetime_unix(event['created_at']),
        ip=event['ip'].packed,
        user_agent=event['user_agent'],
        user=user_proto(user),
        target_user=user_proto(target_user),
        application=(
            ProtoAuditEvent.Application(
                id=application['id'],
                name=application['name'],
                avatar_url=oauth2_app_avatar_url(application),
                owner=user_proto(application.get('user')),
            )
            if application is not None
            else None
        ),
        extra=str(extra) if extra is not None else None,
    )


service = _Service()
asgi_app_cls = ServiceASGIApplication
