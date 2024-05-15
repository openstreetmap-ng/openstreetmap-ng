from collections.abc import Sequence
from typing import Annotated

import cython
from fastapi import APIRouter, Query, Response, status
from pydantic import PositiveInt
from sqlalchemy.orm import joinedload

from app.format06 import Format06
from app.lib.auth_context import api_user
from app.lib.date_utils import parse_date
from app.lib.exceptions_context import raise_for
from app.lib.geo_utils import parse_bbox
from app.lib.options_context import options_context
from app.lib.xml_body import xml_body
from app.limits import CHANGESET_QUERY_DEFAULT_LIMIT, CHANGESET_QUERY_MAX_LIMIT
from app.models.db.changeset_comment import ChangesetComment
from app.models.db.user import User
from app.models.scope import Scope
from app.repositories.changeset_comment_repository import ChangesetCommentRepository
from app.repositories.changeset_repository import ChangesetRepository
from app.repositories.element_repository import ElementRepository
from app.repositories.user_repository import UserRepository
from app.responses.osm_response import DiffResultResponse, OSMChangeResponse
from app.services.changeset_service import ChangesetService
from app.services.optimistic_diff import OptimisticDiff

router = APIRouter(prefix='/api/0.6')

# TODO: https://www.openstreetmap.org/history/feed
# TODO: 0.7 mandatory created_by and comment tags


@router.put('/changeset/create')
async def changeset_create(
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
async def changeset_read(
    changeset_id: PositiveInt,
    include_discussion: Annotated[str | None, Query(alias='include_discussion')] = None,
):
    changesets = await ChangesetRepository.find_many_by_query(changeset_ids=(changeset_id,), limit=1)

    if not changesets:
        raise_for().changeset_not_found(changeset_id)
    if include_discussion:
        with options_context(joinedload(ChangesetComment.user)):
            await ChangesetCommentRepository.resolve_comments(changesets, limit_per_changeset=None, rich_text=True)

    return Format06.encode_changesets(changesets)


@router.put('/changeset/{changeset_id:int}')
async def changeset_update(
    changeset_id: PositiveInt,
    data: Annotated[dict, xml_body('osm/changeset')],
    _: Annotated[User, api_user(Scope.write_api)],
):
    try:
        tags = Format06.decode_tags_and_validate(data.get('tag', ()))
    except Exception as e:
        raise_for().bad_xml('changeset', str(e))

    await ChangesetService.update_tags(changeset_id, tags)
    changesets = await ChangesetRepository.find_many_by_query(changeset_ids=(changeset_id,), limit=1)
    return Format06.encode_changesets(changesets)


@router.post('/changeset/{changeset_id:int}/upload', response_class=DiffResultResponse)
async def changeset_upload(
    changeset_id: PositiveInt,
    data: Annotated[Sequence[dict], xml_body('osmChange')],
    _: Annotated[User, api_user(Scope.write_api)],
):
    try:
        # implicitly assume stings are proper types
        elements = Format06.decode_osmchange(data, changeset_id=changeset_id)
    except Exception as e:
        raise_for().bad_xml('osmChange', str(e))

    assigned_ref_map = await OptimisticDiff(elements).run()
    return Format06.encode_diff_result(assigned_ref_map)


@router.put('/changeset/{changeset_id:int}/close')
async def changeset_close(
    changeset_id: PositiveInt,
    _: Annotated[User, api_user(Scope.write_api)],
):
    await ChangesetService.close(changeset_id)
    return Response()


@router.get('/changeset/{changeset_id:int}/download', response_class=OSMChangeResponse)
@router.get('/changeset/{changeset_id:int}/download.xml', response_class=OSMChangeResponse)
async def changeset_download(
    changeset_id: PositiveInt,
):
    changesets = await ChangesetRepository.find_many_by_query(changeset_ids=(changeset_id,), limit=1)
    changeset = changesets[0] if changesets else None
    if changeset is None:
        raise_for().changeset_not_found(changeset_id)

    elements = await ElementRepository.get_many_by_changeset(changeset_id, sort_by='sequence_id')

    for element in elements:
        element.changeset = changeset

    return Format06.encode_osmchange(elements)


@router.get('/changesets')
@router.get('/changesets.xml')
@router.get('/changesets.json')
async def changesets_query(
    changesets: Annotated[str | None, Query(min_length=1)] = None,
    display_name: Annotated[str | None, Query(min_length=1)] = None,
    user_id: Annotated[PositiveInt | None, Query(alias='user')] = None,
    time: Annotated[str | None, Query(min_length=1)] = None,
    open_str: Annotated[str | None, Query(alias='open')] = None,
    closed_str: Annotated[str | None, Query(alias='closed')] = None,
    bbox: Annotated[str | None, Query(min_length=1)] = None,
    limit: Annotated[int, Query(gt=0, le=CHANGESET_QUERY_MAX_LIMIT)] = CHANGESET_QUERY_DEFAULT_LIMIT,
):
    # treat any non-empty string as True
    open: cython.char = bool(open_str)
    closed: cython.char = bool(closed_str)

    # small logical optimization
    if open and closed:
        return Format06.encode_changesets(())

    geometry = parse_bbox(bbox) if (bbox is not None) else None

    if changesets is not None:
        changeset_ids = set()

        for c in changesets.split(','):
            c = c.strip()
            if c.isdigit():
                changeset_ids.add(int(c))

        if not changeset_ids:
            return Response('No changesets were given to search for', status.HTTP_400_BAD_REQUEST)
    else:
        changeset_ids = None

    display_name_provided: cython.char = display_name is not None
    user_id_provided: cython.char = user_id is not None

    if display_name_provided and user_id_provided:
        return Response('provide either the user ID or display name, but not both', status.HTTP_400_BAD_REQUEST)
    if display_name_provided:
        user = await UserRepository.find_one_by_display_name(display_name)
        if user is None:
            raise_for().user_not_found_bad_request(display_name)
    elif user_id_provided:
        user = await UserRepository.find_one_by_id(user_id)
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

        if (closed_after is not None) and (created_before is not None) and closed_after > created_before:
            return Response('The time range is invalid, T1 > T2', status.HTTP_400_BAD_REQUEST)
    else:
        closed_after = None
        created_before = None

    changesets = await ChangesetRepository.find_many_by_query(
        changeset_ids=changeset_ids,
        user_id=user.id if (user is not None) else None,
        created_before=created_before,
        closed_after=closed_after,
        is_open=True if open else (False if closed else None),
        geometry=geometry,
        limit=limit,
    )

    return Format06.encode_changesets(changesets)
