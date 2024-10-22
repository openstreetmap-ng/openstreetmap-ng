from collections.abc import Sequence
from typing import Annotated, Literal

import cython
from fastapi import APIRouter, Query, Response, status
from pydantic import PositiveInt
from sqlalchemy.orm import joinedload, raiseload

from app.format import Format06
from app.lib.auth_context import api_user
from app.lib.date_utils import parse_date
from app.lib.exceptions_context import raise_for
from app.lib.geo_utils import parse_bbox
from app.lib.options_context import options_context
from app.lib.xml_body import xml_body
from app.limits import CHANGESET_QUERY_DEFAULT_LIMIT, CHANGESET_QUERY_MAX_LIMIT
from app.models.db.changeset import Changeset
from app.models.db.changeset_comment import ChangesetComment
from app.models.db.user import User
from app.models.scope import Scope
from app.queries.changeset_comment_query import ChangesetCommentQuery
from app.queries.changeset_query import ChangesetQuery
from app.queries.element_query import ElementQuery
from app.queries.user_query import UserQuery
from app.responses.osm_response import DiffResultResponse, OSMChangeResponse
from app.services.changeset_service import ChangesetService
from app.services.optimistic_diff import OptimisticDiff

router = APIRouter(prefix='/api/0.6')

# TODO: 0.7 mandatory created_by and comment tags


@router.put('/changeset/create')
async def create_changeset(
    data: Annotated[dict, xml_body('osm/changeset')],
    _: Annotated[User, api_user(Scope.write_api)],
):
    try:
        tags = Format06.decode_tags_and_validate(data.get('tag', ()))
    except Exception as e:
        raise_for().bad_xml('changeset', str(e))

    changeset_id = await ChangesetService.create(tags)
    return Response(str(changeset_id), media_type='text/plain')


@router.get('/changeset/{changeset_id:int}')
@router.get('/changeset/{changeset_id:int}.xml')
@router.get('/changeset/{changeset_id:int}.json')
async def get_changeset(
    changeset_id: PositiveInt,
    include_discussion: Annotated[str | None, Query(alias='include_discussion')] = None,
):
    with options_context(joinedload(Changeset.user).load_only(User.display_name)):
        changeset = await ChangesetQuery.find_by_id(changeset_id)
    if changeset is None:
        raise_for().changeset_not_found(changeset_id)
    changesets = (changeset,)

    if include_discussion:
        with options_context(joinedload(ChangesetComment.user).load_only(User.display_name)):
            await ChangesetCommentQuery.resolve_comments(changesets, limit_per_changeset=None, resolve_rich_text=True)
    else:
        await ChangesetCommentQuery.resolve_num_comments(changesets)

    return Format06.encode_changesets(changesets)


@router.get('/changeset/{changeset_id:int}/download', response_class=OSMChangeResponse)
@router.get('/changeset/{changeset_id:int}/download.xml', response_class=OSMChangeResponse)
async def download_changeset(
    changeset_id: PositiveInt,
):
    with options_context(joinedload(Changeset.user).load_only(User.display_name)):
        changeset = await ChangesetQuery.find_by_id(changeset_id)
    if changeset is None:
        raise_for().changeset_not_found(changeset_id)

    elements = await ElementQuery.get_by_changeset(changeset_id, sort_by='sequence_id')
    await UserQuery.resolve_elements_users(elements, display_name=True)
    return Format06.encode_osmchange(elements)


@router.put('/changeset/{changeset_id:int}')
async def update_changeset(
    changeset_id: PositiveInt,
    data: Annotated[dict, xml_body('osm/changeset')],
    _: Annotated[User, api_user(Scope.write_api)],
):
    try:
        tags = Format06.decode_tags_and_validate(data.get('tag', ()))
    except Exception as e:
        raise_for().bad_xml('changeset', str(e))

    await ChangesetService.update_tags(changeset_id, tags)
    with options_context(joinedload(Changeset.user).load_only(User.display_name)):
        changeset = await ChangesetQuery.find_by_id(changeset_id)
    if changeset is None:
        raise AssertionError(f'Changeset {changeset_id} must exist in database')
    changesets = (changeset,)

    await ChangesetCommentQuery.resolve_num_comments(changesets)
    return Format06.encode_changesets(changesets)


@router.post('/changeset/{changeset_id:int}/upload', response_class=DiffResultResponse)
async def upload_diff(
    changeset_id: PositiveInt,
    data: Annotated[Sequence, xml_body('osmChange')],
    _: Annotated[User, api_user(Scope.write_api)],
):
    try:
        # implicitly assume stings are proper types
        elements = Format06.decode_osmchange(data, changeset_id=changeset_id)
    except Exception as e:
        raise_for().bad_xml('osmChange', str(e))

    assigned_ref_map = await OptimisticDiff.run(elements)
    return Format06.encode_diff_result(assigned_ref_map)


@router.put('/changeset/{changeset_id:int}/close')
async def close_changeset(
    changeset_id: PositiveInt,
    _: Annotated[User, api_user(Scope.write_api)],
):
    await ChangesetService.close(changeset_id)
    return Response()


@router.get('/changesets')
@router.get('/changesets.xml')
@router.get('/changesets.json')
async def query_changesets(
    changesets_query: Annotated[str | None, Query(alias='changesets', min_length=1)] = None,
    display_name: Annotated[str | None, Query(min_length=1)] = None,
    user_id: Annotated[PositiveInt | None, Query(alias='user')] = None,
    time: Annotated[str | None, Query(min_length=1)] = None,
    open_str: Annotated[str | None, Query(alias='open')] = None,
    closed_str: Annotated[str | None, Query(alias='closed')] = None,
    bbox: Annotated[str | None, Query(min_length=1)] = None,
    order: Annotated[Literal['newest', 'oldest'], Query()] = 'newest',
    limit: Annotated[PositiveInt, Query(le=CHANGESET_QUERY_MAX_LIMIT)] = CHANGESET_QUERY_DEFAULT_LIMIT,
):
    # treat any non-empty string as True
    open: cython.char = bool(open_str)
    closed: cython.char = bool(closed_str)
    # small logical optimization
    if open and closed:
        return Format06.encode_changesets(())

    geometry = parse_bbox(bbox) if (bbox is not None) else None

    if changesets_query is not None:
        changeset_ids = set()
        for c in changesets_query.split(','):
            c = c.strip()
            if c.isdigit():
                changeset_ids.add(int(c))
        if not changeset_ids:
            return Response('No changesets were given to search for', status.HTTP_400_BAD_REQUEST)
    else:
        changeset_ids = None

    user: User | None = None
    if display_name is not None and user_id is not None:
        return Response('provide either the user ID or display name, but not both', status.HTTP_400_BAD_REQUEST)
    if display_name is not None:
        user = await UserQuery.find_one_by_display_name(display_name)
        if user is None:
            raise_for().user_not_found_bad_request(display_name)
    elif user_id is not None:
        user = await UserQuery.find_one_by_id(user_id)
        if user is None:
            raise_for().user_not_found_bad_request(user_id)

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
            return Response(f'no time information in "{time}"', status.HTTP_400_BAD_REQUEST)
        if (created_before is not None) and closed_after > created_before:
            return Response('The time range is invalid, T1 > T2', status.HTTP_400_BAD_REQUEST)
    else:
        closed_after = None
        created_before = None

    with options_context(joinedload(Changeset.user).load_only(User.display_name), raiseload(Changeset.bounds)):
        changesets = await ChangesetQuery.find_many_by_query(
            changeset_ids=changeset_ids,
            user_id=user.id if (user is not None) else None,
            created_before=created_before,
            closed_after=closed_after,
            is_open=True if open else (False if closed else None),
            geometry=geometry,
            legacy_geometry=True,
            sort='asc' if (order == 'newest') else 'desc',
            limit=limit,
        )

    await ChangesetCommentQuery.resolve_num_comments(changesets)
    return Format06.encode_changesets(changesets)
