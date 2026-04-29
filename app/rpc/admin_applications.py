from asyncio import TaskGroup
from datetime import timedelta
from typing import Literal, assert_never, override

from connectrpc.request import RequestContext

from app.config import ADMIN_APPLICATION_EXPORT_LIMIT, ADMIN_APPLICATION_LIST_PAGE_SIZE
from app.lib.auth_context import require_web_user
from app.lib.date_utils import unix_datetime
from app.lib.standard_pagination import sp_paginate_table
from app.models.db.oauth2_application import (
    OAuth2Application,
    oauth2_app_avatar_url,
)
from app.models.db.user import user_proto
from app.models.proto.admin_applications_connect import (
    Service,
    ServiceASGIApplication,
)
from app.models.proto.admin_applications_pb2 import (
    ExportIdsRequest,
    ExportIdsResponse,
    Filters,
    ListRequest,
    ListResponse,
)
from app.models.proto.shared_pb2 import IpCount
from app.models.types import ApplicationId
from app.queries.audit_query import AuditQuery
from app.queries.oauth2_application_query import OAuth2ApplicationQuery
from app.queries.oauth2_token_query import OAuth2TokenQuery
from app.queries.user_query import UserQuery
from app.services.audit_service import audit


class _Service(Service):
    @override
    async def list(self, request: ListRequest, ctx: RequestContext):
        require_web_user('role_administrator')
        audit(
            'view_admin_applications',
            extra_proto=request.filters,
            extra={'action': 'list'},
        ).close()

        search, owner, interacted_user, created_after, created_before, sort = (
            _filters_parse(request.filters)
        )

        where_clause, params = await OAuth2ApplicationQuery.where_clause(
            search=search,
            owner=owner,
            interacted_user=interacted_user,
            created_after=created_after,
            created_before=created_before,
        )

        order_dir: Literal['asc', 'desc']
        if sort == Filters.Sort.created_asc:
            order_dir = 'asc'
        elif sort == Filters.Sort.created_desc:
            order_dir = 'desc'
        else:
            assert_never(sort)

        apps, state = await sp_paginate_table(
            OAuth2Application,
            request.state.SerializeToString(),
            table='oauth2_application',
            where=where_clause,
            params=params,
            page_size=ADMIN_APPLICATION_LIST_PAGE_SIZE,
            cursor_column='created_at',
            cursor_kind='datetime',
            order_dir=order_dir,
        )

        app_ids: list[ApplicationId] = [app['id'] for app in apps]

        async with TaskGroup() as tg:
            tg.create_task(UserQuery.resolve_users(apps))
            ip_counts_t = tg.create_task(
                AuditQuery.count_ip_by_application(
                    app_ids, since=timedelta(days=1), limit=10
                )
            )
            user_counts_t = tg.create_task(
                OAuth2TokenQuery.count_users_by_applications(app_ids)
            )

        ip_counts = ip_counts_t.result()
        user_counts = user_counts_t.result()

        entries = [
            ListResponse.Entry(
                id=app['id'],
                name=app['name'],
                avatar_url=oauth2_app_avatar_url(app),
                client_id=app['client_id'],
                confidential=app['confidential'],
                redirect_uris=app['redirect_uris'],
                scopes=app['scopes'],
                owner=user_proto(app.get('user')),
                user_count=user_counts.get(app['id'], 0),
                created_at=int(app['created_at'].timestamp()),
                ip_counts=[
                    IpCount(ip=ip.packed, count=count)
                    for ip, count in ip_counts.get(app['id'], ())
                ],
            )
            for app in apps
        ]

        return ListResponse(entries=entries, state=state)

    @override
    async def export_ids(self, request: ExportIdsRequest, ctx: RequestContext):
        require_web_user('role_administrator')
        search, owner, interacted_user, created_after, created_before, _ = (
            _filters_parse(request.filters)
        )

        app_ids = await OAuth2ApplicationQuery.find_ids(
            limit=ADMIN_APPLICATION_EXPORT_LIMIT,
            search=search,
            owner=owner,
            interacted_user=interacted_user,
            created_after=created_after,
            created_before=created_before,
            sort='created_desc',
        )
        audit(
            'view_admin_applications',
            extra_proto=request.filters,
            extra={'action': 'export', 'count': len(app_ids)},
        ).close()

        return ExportIdsResponse(ids=app_ids)


def _filters_parse(filters: Filters):
    search = filters.search if filters.HasField('search') else None
    owner = filters.owner if filters.HasField('owner') else None
    interacted_user = (
        filters.interacted_user if filters.HasField('interacted_user') else None
    )
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
    sort = filters.sort

    return search, owner, interacted_user, created_after, created_before, sort


service = _Service()
asgi_app_cls = ServiceASGIApplication
