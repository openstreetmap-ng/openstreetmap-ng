from asyncio import TaskGroup
from typing import Annotated, Literal
from warnings import catch_warnings, filterwarnings

import numpy as np
from fastapi import APIRouter, Query, Response, status
from pydantic import PositiveInt

from app.config import CHANGESET_QUERY_DEFAULT_LIMIT, CHANGESET_QUERY_MAX_LIMIT
from app.format import Format06
from app.lib.auth_context import api_user
from app.lib.date_utils import parse_date
from app.lib.exceptions_context import raise_for
from app.lib.geo_utils import parse_bbox
from app.lib.xml_body import xml_body
from app.models.db.changeset_comment import changeset_comments_resolve_rich_text
from app.models.db.user import User
from app.models.types import ChangesetId, UserId
from app.queries.changeset_comment_query import ChangesetCommentQuery
from app.queries.changeset_query import ChangesetQuery
from app.queries.element_query import ElementQuery
from app.queries.user_query import UserQuery
from app.responses.osm_response import DiffResultResponse, OSMChangeResponse
from app.services.changeset_service import ChangesetService
from app.services.optimistic_diff import OptimisticDiff
from app.validators.display_name import DisplayNameNormalizing

router = APIRouter(prefix='/api/0.6')

# TODO: 0.7 mandatory created_by and comment tags


@router.put('/changeset/create')
async def create_changeset(
    data: Annotated[dict, xml_body('osm/changeset')],
    _: Annotated[User, api_user('write_api')],
):
    try:
        tags = Format06.decode_tags_and_validate(data.get('tag'))
    except Exception as e:
        raise_for.bad_xml('changeset', str(e))

    changeset_id = await ChangesetService.create(tags)
    return Response(str(changeset_id), media_type='text/plain')


@router.get('/changeset/{changeset_id:int}')
@router.get('/changeset/{changeset_id:int}.xml')
@router.get('/changeset/{changeset_id:int}.json')
async def get_changeset(
    changeset_id: ChangesetId,
    include_discussion: Annotated[str | None, Query()] = None,
):
    changeset = await ChangesetQuery.find_by_id(changeset_id)
    if changeset is None:
        raise_for.changeset_not_found(changeset_id)
    changesets = [changeset]

    async with TaskGroup() as tg:
        tg.create_task(UserQuery.resolve_users(changesets))

        if include_discussion:
            comments = await ChangesetCommentQuery.resolve_comments(
                changesets, limit_per_changeset=None
            )
            tg.create_task(UserQuery.resolve_users(comments))
            tg.create_task(changeset_comments_resolve_rich_text(comments))
        else:
            tg.create_task(ChangesetCommentQuery.resolve_num_comments(changesets))

    return Format06.encode_changesets(changesets)


@router.get('/changeset/{changeset_id:int}/download', response_class=OSMChangeResponse)
@router.get(
    '/changeset/{changeset_id:int}/download.xml', response_class=OSMChangeResponse
)
async def download_changeset(
    changeset_id: ChangesetId,
):
    changeset = await ChangesetQuery.find_by_id(changeset_id)
    if changeset is None:
        raise_for.changeset_not_found(changeset_id)

    async with TaskGroup() as tg:
        tg.create_task(UserQuery.resolve_users([changeset]))

        elements = await ElementQuery.get_by_changeset(
            changeset_id, sort_by='sequence_id'
        )
        tg.create_task(UserQuery.resolve_elements_users(elements))

    return Format06.encode_osmchange(elements)


@router.put('/changeset/{changeset_id:int}')
async def update_changeset(
    changeset_id: ChangesetId,
    data: Annotated[dict, xml_body('osm/changeset')],
    _: Annotated[User, api_user('write_api')],
):
    try:
        tags = Format06.decode_tags_and_validate(data.get('tag'))
    except Exception as e:
        raise_for.bad_xml('changeset', str(e))

    await ChangesetService.update_tags(changeset_id, tags)
    changeset = await ChangesetQuery.find_by_id(changeset_id)
    assert changeset is not None, f'Changeset {changeset_id} must exist after update'

    async with TaskGroup() as tg:
        items = [changeset]
        tg.create_task(UserQuery.resolve_users(items))
        tg.create_task(ChangesetCommentQuery.resolve_num_comments(items))

    return Format06.encode_changesets(items)


@router.post('/changeset/{changeset_id:int}/upload', response_class=DiffResultResponse)
async def upload_diff(
    changeset_id: ChangesetId,
    data: Annotated[list, xml_body('osmChange')],
    _: Annotated[User, api_user('write_api')],
):
    try:
        elements = Format06.decode_osmchange(changeset_id, data)
    except Exception as e:
        raise_for.bad_xml('osmChange', str(e))

    assigned_ref_map = await OptimisticDiff.run(elements)
    return Format06.encode_diff_result(assigned_ref_map)


@router.put('/changeset/{changeset_id:int}/close')
async def close_changeset(
    changeset_id: ChangesetId,
    _: Annotated[User, api_user('write_api')],
):
    await ChangesetService.close(changeset_id)
    return Response(None, status.HTTP_204_NO_CONTENT)


@router.get('/changesets')
@router.get('/changesets.xml')
@router.get('/changesets.json')
async def query_changesets(
    changesets_query: Annotated[
        str | None, Query(alias='changesets', min_length=1)
    ] = None,
    display_name: Annotated[DisplayNameNormalizing | None, Query(min_length=1)] = None,
    user_id: Annotated[UserId | None, Query(alias='user')] = None,
    time: Annotated[str | None, Query(min_length=1)] = None,
    open_str: Annotated[str | None, Query(alias='open')] = None,
    closed_str: Annotated[str | None, Query(alias='closed')] = None,
    bbox: Annotated[str | None, Query(min_length=1)] = None,
    order: Annotated[Literal['newest', 'oldest'], Query()] = 'newest',
    limit: Annotated[
        PositiveInt, Query(le=CHANGESET_QUERY_MAX_LIMIT)
    ] = CHANGESET_QUERY_DEFAULT_LIMIT,
):
    # Treat any non-empty string as True
    open = bool(open_str)
    closed = bool(closed_str)

    # Logical optimization
    if open and closed:
        return Format06.encode_changesets([])

    geometry = parse_bbox(bbox)

    changeset_ids: list[ChangesetId] | None = None
    if changesets_query is not None:
        try:
            with catch_warnings():
                filterwarnings(
                    'ignore',
                    category=DeprecationWarning,
                    message='.*could not be read to its end.*',
                )
                ids = np.fromstring(changesets_query, np.uint64, sep=',')
        except ValueError:
            return Response(
                'Changesets query must be a comma-separated list of integers',
                status.HTTP_400_BAD_REQUEST,
            )
        if not ids.size:
            return Response(
                'No changesets were given to search for', status.HTTP_400_BAD_REQUEST
            )
        changeset_ids = np.unique(ids).tolist()

    user: User | None = None
    if display_name is not None and user_id is not None:
        return Response(
            'provide either the user ID or display name, but not both',
            status.HTTP_400_BAD_REQUEST,
        )
    if display_name is not None:
        user = await UserQuery.find_one_by_display_name(display_name)
        if user is None:
            raise_for.user_not_found_bad_request(display_name)
    elif user_id is not None:
        user = await UserQuery.find_one_by_id(user_id)
        if user is None:
            raise_for.user_not_found_bad_request(user_id)

    if time is not None:
        time_left, _, time_right = time.partition(',')
        try:
            if time_right:
                created_before = parse_date(time_left)
                closed_after = parse_date(time_right)
            else:
                closed_after = parse_date(time)
                created_before = None
        except Exception:
            return Response(
                f'no time information in "{time}"', status.HTTP_400_BAD_REQUEST
            )
        if created_before is not None and closed_after > created_before:
            return Response(
                'The time range is invalid, T1 > T2', status.HTTP_400_BAD_REQUEST
            )
    else:
        closed_after = None
        created_before = None

    changesets = await ChangesetQuery.find_many_by_query(
        changeset_ids=changeset_ids,
        user_ids=[user['id']] if (user is not None) else None,
        created_before=created_before,
        closed_after=closed_after,
        is_open=True if open else (False if closed else None),
        geometry=geometry,
        legacy_geometry=True,
        sort='asc' if (order == 'newest') else 'desc',
        limit=limit,
    )

    async with TaskGroup() as tg:
        tg.create_task(UserQuery.resolve_users(changesets))
        tg.create_task(ChangesetCommentQuery.resolve_num_comments(changesets))

    return Format06.encode_changesets(changesets)
