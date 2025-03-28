from typing import Annotated

from fastapi import APIRouter, Path, Query, Response
from feedgen.feed import FeedGenerator
from pydantic import PositiveInt
from shapely.geometry.base import BaseGeometry
from starlette import status

from app.config import APP_URL, ATTRIBUTION_URL
from app.format import FormatRSS06
from app.lib.date_utils import utcnow
from app.lib.geo_utils import parse_bbox
from app.lib.translation import primary_translation_locale, t
from app.limits import CHANGESET_QUERY_DEFAULT_LIMIT, CHANGESET_QUERY_MAX_LIMIT
from app.middlewares.request_context_middleware import get_request
from app.models.db.user import User
from app.models.types import DisplayName, UserId
from app.queries.changeset_query import ChangesetQuery
from app.queries.user_query import UserQuery

router = APIRouter()


@router.get('/history/feed')
async def history_feed(
    bbox: Annotated[str | None, Query(min_length=1)] = None,
    limit: Annotated[PositiveInt, Query(le=CHANGESET_QUERY_MAX_LIMIT)] = CHANGESET_QUERY_DEFAULT_LIMIT,
):
    geometry = parse_bbox(bbox)
    return await _get_feed(None, geometry, limit)


@router.get('/user/{display_name:str}/history/feed')
async def user_history_feed(
    display_name: Annotated[DisplayName, Path(min_length=1)],
    bbox: Annotated[str | None, Query(min_length=1)] = None,
    limit: Annotated[PositiveInt, Query(le=CHANGESET_QUERY_MAX_LIMIT)] = CHANGESET_QUERY_DEFAULT_LIMIT,
):
    user = await UserQuery.find_one_by_display_name(display_name)
    if user is None:
        return Response(None, status.HTTP_404_NOT_FOUND, media_type='application/atom+xml')

    geometry = parse_bbox(bbox)
    return await _get_feed(user, geometry, limit)


@router.get('/user-id/{user_id:int}/history/feed')
async def user_permalink_history_feed(
    user_id: UserId,
    bbox: Annotated[str | None, Query(min_length=1)] = None,
    limit: Annotated[PositiveInt, Query(le=CHANGESET_QUERY_MAX_LIMIT)] = CHANGESET_QUERY_DEFAULT_LIMIT,
):
    user = await UserQuery.find_one_by_id(user_id)
    if user is None:
        return Response(None, status.HTTP_404_NOT_FOUND, media_type='application/atom+xml')

    geometry = parse_bbox(bbox)
    return await _get_feed(user, geometry, limit)


async def _get_feed(user: User | None, geometry: BaseGeometry | None, limit: int) -> str:
    changesets = await ChangesetQuery.find_many_by_query(
        user_ids=[user['id']] if (user is not None) else None,
        geometry=geometry,
        legacy_geometry=True,
        sort='desc',
        limit=limit,
    )
    await UserQuery.resolve_users(changesets)

    url = str(get_request().url)
    html_url = url.replace('/feed', '')

    fg = FeedGenerator()
    fg.language(primary_translation_locale())
    fg.id(url)
    fg.updated(utcnow())

    fg.link(rel='self', type='text/html', href=html_url)
    fg.link(rel='alternate', type='application/atom+xml', href=url)
    fg.icon(f'{APP_URL}/static/img/favicon/64.webp')
    fg.logo(f'{APP_URL}/static/img/favicon/256.webp')
    fg.rights(ATTRIBUTION_URL)

    if user is not None:
        fg.title(t('changesets.index.title_user', user=user['display_name']))
    else:
        fg.title(t('changesets.index.title'))

    FormatRSS06.encode_changesets(fg, changesets)
    return fg.atom_str()
