from collections.abc import Sequence
from contextlib import nullcontext
from typing import Annotated

import cython
from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import PlainTextResponse
from pydantic import PositiveInt

from app.format06 import Format06
from app.lib.auth_context import api_user
from app.lib.date_utils import parse_date
from app.lib.exceptions_context import raise_for
from app.lib.geo_utils import parse_bbox
from app.lib.joinedload_context import joinedload_context
from app.lib.xmltodict import XMLToDict
from app.limits import CHANGESET_QUERY_DEFAULT_LIMIT, CHANGESET_QUERY_MAX_LIMIT
from app.models.db.changeset import Changeset
from app.models.db.changeset_comment import ChangesetComment
from app.models.db.user import User
from app.models.element_type import ElementType
from app.models.scope import Scope
from app.repositories.changeset_repository import ChangesetRepository
from app.repositories.user_repository import UserRepository
from app.responses.osm_response import DiffResultResponse, OSMChangeResponse
from app.services.changeset_service import ChangesetService
from app.services.optimistic_diff import OptimisticDiff

router = APIRouter()

# TODO: https://www.openstreetmap.org/history/feed
# TODO: 0.7 mandatory created_by and comment tags


@router.put('/changeset/create', response_class=PlainTextResponse)
async def changeset_create(
    request: Request,
    type: ElementType,
    _: Annotated[User, api_user(Scope.write_api)],
) -> PositiveInt:
    xml = (await request.body()).decode()
    data: dict = XMLToDict.parse(xml).get('osm', {}).get('changeset', {})

    if not data:
        raise_for().bad_xml(type.value, xml, "XML doesn't contain an osm/changeset element.")

    try:
        tags = Format06.decode_tags_and_validate(data.get('tag', ()))
    except Exception as e:
        raise_for().bad_xml(type.value, xml, str(e))

    changeset = await ChangesetService.create(tags)
    return changeset.id


@router.get('/changeset/{changeset_id}')
@router.get('/changeset/{changeset_id}.xml')
@router.get('/changeset/{changeset_id}.json')
async def changeset_read(
    changeset_id: PositiveInt,
    include_discussion_str: Annotated[str | None, Query(alias='include_discussion')] = None,
) -> dict:
    # treat any non-empty string as True
    include_discussion: cython.char = bool(include_discussion_str)

    with joinedload_context(Changeset.comments, ChangesetComment.user) if include_discussion else nullcontext():
        changesets = await ChangesetRepository.find_many_by_query(changeset_ids=(changeset_id,), limit=1)

    if not changesets:
        raise_for().changeset_not_found(changeset_id)

    return Format06.encode_changesets(changesets)


@router.put('/changeset/{changeset_id}')
async def changeset_update(
    request: Request,
    changeset_id: PositiveInt,
    _: Annotated[User, api_user(Scope.write_api)],
) -> dict:
    xml = (await request.body()).decode()
    data: dict = XMLToDict.parse(xml).get('osm', {}).get('changeset', {})

    if not data:
        raise_for().bad_xml(type.value, xml, "XML doesn't contain an osm/changeset element.")

    try:
        tags = Format06.decode_tags_and_validate(data.get('tag', ()))
    except Exception as e:
        raise_for().bad_xml(type.value, xml, str(e))

    changeset = await ChangesetService.update_tags(changeset_id, tags)
    return Format06.encode_changesets((changeset,))


@router.post('/changeset/{changeset_id}/upload', response_class=DiffResultResponse)
async def changeset_upload(
    request: Request,
    changeset_id: PositiveInt,
    _: Annotated[User, api_user(Scope.write_api)],
) -> dict:
    xml = (await request.body()).decode()
    data: Sequence[dict] = XMLToDict.parse(xml, sequence=True).get('osmChange', ())

    if not data:
        raise_for().bad_xml(type.value, xml, "XML doesn't contain an /osmChange element.")

    try:
        elements = Format06.decode_osmchange(data, changeset_id)
    except Exception as e:
        raise_for().bad_xml(type.value, xml, str(e))

    assigned_ref_map = await OptimisticDiff(elements).run()
    return Format06.encode_diff_result(assigned_ref_map)


@router.put('/changeset/{changeset_id}/close', response_class=PlainTextResponse)
async def changeset_close(
    changeset_id: PositiveInt,
    _: Annotated[User, api_user(Scope.write_api)],
) -> None:
    await ChangesetService.close(changeset_id)


@router.get('/changeset/{changeset_id}/download', response_class=OSMChangeResponse)
@router.get('/changeset/{changeset_id}/download.xml', response_class=OSMChangeResponse)
async def changeset_download(
    changeset_id: PositiveInt,
) -> Sequence[tuple[str, dict]]:
    with joinedload_context(Changeset.elements):
        changesets = await ChangesetRepository.find_many_by_query(changeset_ids=(changeset_id,), limit=1)

    if not changesets:
        raise_for().changeset_not_found(changeset_id)

    return Format06.encode_osmchange(changesets[0].elements)


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
) -> Sequence[dict]:
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
            raise HTTPException(status.HTTP_400_BAD_REQUEST, 'No changesets were given to search for')
    else:
        changeset_ids = None

    display_name_provided: cython.char = display_name is not None
    user_id_provided: cython.char = user_id is not None

    if display_name_provided and user_id_provided:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, 'provide either the user ID or display name, but not both')
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
        except Exception as e:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f'no time information in "{time}"') from e

        if (closed_after is not None) and (created_before is not None) and closed_after > created_before:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, 'The time range is invalid, T1 > T2')
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
