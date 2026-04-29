from asyncio import TaskGroup
from typing import Annotated

from fastapi import APIRouter
from polyline_rs import encode_lonlat
from starlette import status
from starlette.responses import RedirectResponse

from app.config import API_URL
from app.lib.auth_context import web_user
from app.lib.exceptions_context import raise_for
from app.lib.render_response import render_proto_page
from app.lib.translation import t
from app.models.db.user import User, user_proto
from app.models.proto.trace_pb2 import Data, DetailsPage, EditPage, Metadata, UploadPage
from app.models.types import TraceId, UserId
from app.queries.trace_query import TraceQuery
from app.queries.user_query import UserQuery

router = APIRouter(prefix='/trace')


@router.get('/upload')
async def upload(_: Annotated[User, web_user()]):
    return await render_proto_page(
        UploadPage(),
        title_prefix=t('traces.new.upload_trace'),
    )


@router.get('/{trace_id:int}')
async def details(trace_id: TraceId):
    trace = await _build_data(trace_id)
    return await render_proto_page(
        DetailsPage(trace=trace),
        title_prefix=t('traces.show.title', name=trace.metadata.name),
    )


@router.get('/{trace_id:int}/edit')
async def edit(
    trace_id: TraceId,
    user: Annotated[User, web_user()],
):
    trace = await _build_data(trace_id, owner_id=user['id'])
    return await render_proto_page(
        EditPage(trace=trace),
        title_prefix=t('traces.edit.title', name=trace.metadata.name),
    )


@router.get('/{trace_id:int}/data{suffix:path}')
async def legacy_data(trace_id: TraceId, suffix: str):
    return RedirectResponse(
        f'{API_URL}/api/0.6/gpx/{trace_id}/data{suffix}', status.HTTP_302_FOUND
    )


async def _build_data(trace_id: TraceId, *, owner_id: UserId | None = None):
    trace = await TraceQuery.get_by_id(trace_id)
    if owner_id is not None and trace['user_id'] != owner_id:
        raise_for.trace_access_denied(trace_id)

    async with TaskGroup() as tg:
        traces = [trace]
        tg.create_task(UserQuery.resolve_users(traces))
        tg.create_task(
            TraceQuery.resolve_coords(traces, limit_per_trace=500, resolution=None)
        )

    return Data(
        id=trace['id'],
        user=user_proto(trace['user']),  # type: ignore[reportTypedDictNotRequiredAccess]
        metadata=Metadata(
            name=trace['name'],
            description=trace['description'],
            tags=trace['tags'],
            visibility=trace['visibility'],
        ),
        size=trace['size'],
        created_at=int(trace['created_at'].timestamp()),
        line=encode_lonlat(trace['coords'].tolist(), 6),  # type: ignore[reportTypedDictNotRequiredAccess]
    )
