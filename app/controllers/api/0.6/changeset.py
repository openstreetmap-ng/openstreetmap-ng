from collections.abc import Sequence
from contextlib import nullcontext
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import PlainTextResponse
from pydantic import PositiveInt

from app.lib.format06 import Format06
from app.lib.optimistic import Optimistic
from app.lib_cython.auth import api_user
from app.lib_cython.exceptions_context import raise_for
from app.lib_cython.geo_utils import parse_bbox
from app.lib_cython.joinedload_context import joinedload_context
from app.lib_cython.xmltodict import XMLToDict
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
from app.utils import parse_date

router = APIRouter()

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
        tags = Format06.decode_tags_and_validate(data.get('tag', []))
    except Exception as e:
        raise_for().bad_xml(type.value, xml, str(e))

    changeset = await ChangesetService.create(tags)
    return changeset.id


@router.get('/changeset/{changeset_id}')
@router.get('/changeset/{changeset_id}.xml')
@router.get('/changeset/{changeset_id}.json')
async def changeset_read(
    changeset_id: PositiveInt,
    include_discussion: Annotated[str | None, Query(None)],
) -> dict:
    # treat any non-empty string as True
    include_discussion = bool(include_discussion)

    with joinedload_context(Changeset.comments, ChangesetComment.user) if include_discussion else nullcontext():
        changesets = await ChangesetRepository.find_many_by_query(
            changeset_ids=[changeset_id],
            limit=None,
        )

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
        tags = Format06.decode_tags_and_validate(data.get('tag', []))
    except Exception as e:
        raise_for().bad_xml(type.value, xml, str(e))

    changeset = await ChangesetService.update_tags(changeset_id, tags)
    return Format06.encode_changesets([changeset])


@router.post('/changeset/{changeset_id}/upload', response_class=DiffResultResponse)
async def changeset_upload(
    request: Request,
    changeset_id: PositiveInt,
    _: Annotated[User, api_user(Scope.write_api)],
) -> dict:
    xml = (await request.body()).decode()
    data: Sequence[dict] = XMLToDict.parse(xml, sequence=True).get('osmChange', [])

    if not data:
        raise_for().bad_xml(type.value, xml, "XML doesn't contain an /osmChange element.")

    try:
        elements = Format06.decode_osmchange(data, changeset_id)
    except Exception as e:
        raise_for().bad_xml(type.value, xml, str(e))

    assigned_ref_map = await Optimistic(elements).update()
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
) -> Sequence:
    with joinedload_context(Changeset.elements):
        changesets = await ChangesetRepository.find_many_by_query(
            changeset_ids=[changeset_id],
            limit=None,
        )

    if not changesets:
        raise_for().changeset_not_found(changeset_id)

    return Format06.encode_osmchange(changesets[0].elements)


@router.get('/changesets')
@router.get('/changesets.xml')
@router.get('/changesets.json')
async def changesets_query(
    changesets: Annotated[str | None, Query(None, min_length=1)],
    display_name: Annotated[str | None, Query(None, min_length=1)],
    user_id: Annotated[PositiveInt | None, Query(None, alias='user')],
    time: Annotated[str | None, Query(None, min_length=1)],
    open: Annotated[str | None, Query(None)],
    closed: Annotated[str | None, Query(None)],
    bbox: Annotated[str | None, Query(None, min_length=1)],
    limit: Annotated[int, Query(CHANGESET_QUERY_DEFAULT_LIMIT, gt=0, le=CHANGESET_QUERY_MAX_LIMIT)],
) -> Sequence[dict]:
    # small logical optimization
    if open and closed:
        return Format06.encode_changesets([])

    geometry = parse_bbox(bbox) if bbox else None

    if changesets:
        parts = (c.strip() for c in changesets.split(','))
        parts = (c for c in parts if c and c.isdigit())
        changeset_ids = {int(c) for c in parts}
        if not changeset_ids:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, 'No changesets were given to search for')
    else:
        changeset_ids = None

    if display_name and user_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, 'provide either the user ID or display name, but not both')

    if display_name:
        user = await UserRepository.find_one_by_display_name(display_name)
        if not user:
            raise_for().user_not_found_bad_request(display_name)
    elif user_id:
        user = await UserRepository.find_one_by_id(user_id)
        if not user:
            raise_for().user_not_found_bad_request(user_id)

    if time:
        try:
            if ',' in time:
                parts = time.split(',', maxsplit=1)
                created_before = parse_date(parts[0])
                closed_after = parse_date(parts[1])
            else:
                closed_after = parse_date(time)
                created_before = None
        except Exception as e:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f'no time information in "{time}"') from e

        if closed_after and created_before and closed_after > created_before:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, 'The time range is invalid, T1 > T2')
    else:
        closed_after = None
        created_before = None

    changesets = await ChangesetRepository.find_many_by_query(
        changeset_ids=changeset_ids,
        user_id=user.id if user else None,
        created_before=created_before,
        closed_after=closed_after,
        is_open=True if open else (False if closed else None),
        geometry=geometry,
        limit=limit,
    )

    return Format06.encode_changesets(changesets)
