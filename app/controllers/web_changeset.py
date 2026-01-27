from asyncio import TaskGroup
from datetime import date, datetime, time, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Query, Response

from app.config import (
    CHANGESET_QUERY_WEB_LIMIT,
)
from app.format import FormatRender
from app.lib.geo_utils import parse_bbox
from app.models.types import ChangesetId
from app.queries.changeset_bounds_query import ChangesetBoundsQuery
from app.queries.changeset_comment_query import ChangesetCommentQuery
from app.queries.changeset_query import ChangesetQuery
from app.queries.user_query import UserQuery
from app.validators.display_name import DisplayNameNormalizing

router = APIRouter(prefix='/api/web/changeset')


@router.get('/map')
async def get_map(
    bbox: Annotated[str | None, Query()] = None,
    scope: Annotated[
        Literal['nearby', 'friends'] | None, Query()
    ] = None,  # TODO: support scope
    display_name: Annotated[DisplayNameNormalizing | None, Query(min_length=1)] = None,
    date_: Annotated[date | None, Query(alias='date')] = None,
    before: Annotated[ChangesetId | None, Query()] = None,
):
    geometry = parse_bbox(bbox)

    if display_name is not None:
        user = await UserQuery.find_by_display_name(display_name)
        user_ids = [user['id']] if user is not None else []
    else:
        user_ids = None

    if date_ is not None:
        dt = datetime.combine(date_, time(0, 0, 0))
        created_before = dt + timedelta(days=1)
        created_after = dt - timedelta(microseconds=1)
    else:
        created_before = None
        created_after = None

    changesets = await ChangesetQuery.find(
        changeset_id_before=before,
        user_ids=user_ids,
        created_before=created_before,
        created_after=created_after,
        geometry=geometry,
        sort='desc',
        limit=CHANGESET_QUERY_WEB_LIMIT,
    )

    async with TaskGroup() as tg:
        tg.create_task(UserQuery.resolve_users(changesets))
        tg.create_task(ChangesetBoundsQuery.resolve_bounds(changesets))
        tg.create_task(ChangesetCommentQuery.resolve_num_comments(changesets))

    return Response(
        FormatRender.encode_changesets(changesets).SerializeToString(),
        media_type='application/x-protobuf',
    )
