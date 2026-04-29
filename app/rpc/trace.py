from asyncio import TaskGroup
from typing import override

from connectrpc.request import RequestContext
from polyline_rs import encode_lonlat
from psycopg.sql import SQL

from app.config import TRACES_LIST_PAGE_SIZE
from app.lib.auth_context import auth_scopes, auth_user, require_web_user
from app.lib.standard_pagination import sp_paginate_table
from app.models.db.trace import Trace
from app.models.db.user import user_proto
from app.models.proto.trace_connect import Service, ServiceASGIApplication
from app.models.proto.trace_pb2 import (
    DeleteRequest,
    DeleteResponse,
    GetPageRequest,
    GetPageResponse,
    Summary,
    UpdateRequest,
    UpdateResponse,
    UploadRequest,
    UploadResponse,
    Visibility,
)
from app.models.types import TraceId, UserId
from app.queries.trace_query import TraceQuery
from app.queries.user_query import UserQuery
from app.services.trace_service import TraceService


class _Service(Service):
    @override
    async def get_page(self, request: GetPageRequest, ctx: RequestContext):
        conditions = []
        params = []

        current_user = auth_user()
        request_user_id = (
            UserId(request.user_id) if request.HasField('user_id') else None
        )
        if (
            current_user is None
            or current_user['id'] != request_user_id
            or 'read_gpx' not in auth_scopes()
        ):
            conditions.append(SQL("visibility IN ('identifiable', 'public')"))

        if request_user_id is not None:
            conditions.append(SQL('user_id = %s'))
            params.append(request_user_id)

        if request.HasField('tag'):
            conditions.append(SQL('tags @> ARRAY[%s]'))
            params.append(request.tag)

        traces, state = await sp_paginate_table(
            Trace,
            request.state.SerializeToString(),
            table='trace',
            where=SQL(' AND ').join(conditions or (SQL('TRUE'),)),
            params=tuple(params),
            page_size=TRACES_LIST_PAGE_SIZE,
            cursor_column='id',
            cursor_kind='id',
            order_dir='desc',
        )

        async with TaskGroup() as tg:
            tg.create_task(UserQuery.resolve_users(traces))
            tg.create_task(
                TraceQuery.resolve_coords(traces, limit_per_trace=100, resolution=90)
            )

        return GetPageResponse(
            state=state,
            traces=[
                GetPageResponse.Entry(
                    summary=Summary(
                        id=trace['id'],
                        created_at=int(trace['created_at'].timestamp()),
                        description=trace['description'],
                        tags=trace['tags'],
                        visibility=trace['visibility'],
                        size=trace['size'],
                        preview_line=encode_lonlat(trace['coords'].tolist(), 0),  # type: ignore[reportTypedDictNotRequiredAccess]
                    ),
                    user=user_proto(trace['user']),  # type: ignore[reportTypedDictNotRequiredAccess]
                    name=trace['name'],
                )
                for trace in traces
            ],
        )

    @override
    async def upload(self, request: UploadRequest, ctx: RequestContext):
        require_web_user()
        trace_id = await TraceService.upload(
            request.file,
            name=request.metadata.name,
            description=request.metadata.description,
            tags=list(request.metadata.tags),
            visibility=Visibility.Name(request.metadata.visibility),
        )
        return UploadResponse(id=trace_id)

    @override
    async def update(self, request: UpdateRequest, ctx: RequestContext):
        require_web_user()
        await TraceService.update(
            TraceId(request.id),
            name=request.metadata.name,
            description=request.metadata.description,
            tags=list(request.metadata.tags),
            visibility=Visibility.Name(request.metadata.visibility),
        )
        return UpdateResponse()

    @override
    async def delete(self, request: DeleteRequest, ctx: RequestContext):
        require_web_user()
        await TraceService.delete(TraceId(request.id))
        return DeleteResponse()


service = _Service()
asgi_app_cls = ServiceASGIApplication
