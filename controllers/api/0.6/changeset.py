from collections.abc import Sequence
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import PlainTextResponse
from pydantic import PositiveInt

from cython_lib.geoutils import parse_bbox
from cython_lib.xmltodict import XMLToDict
from lib.auth import api_user
from lib.exceptions import raise_for
from lib.format.format06 import Format06
from lib.optimistic import Optimistic
from limits import CHANGESET_QUERY_DEFAULT_LIMIT, CHANGESET_QUERY_MAX_LIMIT
from models.db.changeset import Changeset
from models.db.user import User
from models.element_type import ElementType
from models.scope import Scope
from models.str import NonEmptyStr, UserNameStr
from responses.osm_response import DiffResultResponse, OSMChangeResponse
from utils import parse_date, utcnow

router = APIRouter()

# TODO: 0.7 mandatory created_by and comment tags


@router.put('/changeset/create', response_class=PlainTextResponse)
async def element_create(
    request: Request,
    type: ElementType,
    user: Annotated[User, api_user(Scope.write_api)],
) -> PositiveInt:
    xml = (await request.body()).decode()
    data: dict = XMLToDict.parse(xml).get('osm', {}).get('changeset', {})

    if not data:
        raise_for().bad_xml(type.value, xml, "XML doesn't contain an osm/changeset element.")

    try:
        changeset = Changeset(user_id=user.id, tags=Format06.decode_tags(data.get('tag', [])))
    except Exception as e:
        raise_for().bad_xml(type.value, xml, str(e))

    async with Transaction() as session:
        await changeset.create(session)

    return changeset.id


@router.get('/changeset/{changeset_id}')
@router.get('/changeset/{changeset_id}.xml')
@router.get('/changeset/{changeset_id}.json')
async def changeset_read(
    changeset_id: PositiveInt,
    include_discussion: Annotated[str | None, Query(None)],
) -> dict:
    # TODO: sort by _id instead of created_date if sequential
    changeset = await Changeset.find_one_by_id_with_(
        changeset_id, comment_sort={'_id': ASCENDING}, comment_limit=None if include_discussion else 0
    )

    if not changeset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    return Format06.encode_changesets((changeset,))


@router.put('/changeset/{changeset_id}')
async def changeset_update(
    request: Request,
    changeset_id: PositiveInt,
    user: Annotated[User, api_user(Scope.write_api)],
) -> dict:
    xml = (await request.body()).decode()
    data: dict = XMLToDict.parse(xml).get('osm', {}).get('changeset', {})

    if not data:
        raise_for().bad_xml(type.value, xml, "XML doesn't contain an osm/changeset element.")

    try:
        new_tags = Format06.decode_tags(data.get('tag', []))
    except Exception as e:
        raise_for().bad_xml(type.value, xml, str(e))

    changeset = await Changeset.find_one_by_id(changeset_id)

    if not changeset:
        raise_for().changeset_not_found(changeset_id)
    if changeset.user_id != user.id:
        raise_for().changeset_access_denied()
    if changeset.closed_at:
        raise_for().changeset_already_closed(changeset_id, changeset.closed_at)

    changeset.tags = new_tags
    await changeset.update()  # TODO: check errors
    return Format06.encode_changesets((changeset,))


@router.put('/changeset/{changeset_id}/close', response_class=PlainTextResponse)
async def changeset_close(
    changeset_id: PositiveInt,
    user: Annotated[User, api_user(Scope.write_api)],
) -> None:
    changeset = await Changeset.find_one_by_id(changeset_id)

    if not changeset:
        raise_for().changeset_not_found(changeset_id)
    if changeset.user_id != user.id:
        raise_for().changeset_access_denied()
    if changeset.closed_at:
        raise_for().changeset_already_closed(changeset_id, changeset.closed_at)

    changeset.closed_at = utcnow()
    await changeset.update()


@router.get('/changeset/{changeset_id}/download', response_class=OSMChangeResponse)
@router.get('/changeset/{changeset_id}/download.xml', response_class=OSMChangeResponse)
async def changeset_download(
    changeset_id: PositiveInt,
) -> Sequence:
    changeset = await Changeset.find_one_by_id_with_(changeset_id, element_sort={'_id': ASCENDING}, element_limit=None)

    if not changeset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    return Format06.encode_osmchange(changeset.elements_)


@router.get('/changesets')
@router.get('/changesets.xml')
@router.get('/changesets.json')
async def changesets_read(
    bbox: Annotated[NonEmptyStr | None, Query(None)],
    user: Annotated[PositiveInt | None, Query(None)],
    display_name: Annotated[UserNameStr | None, Query(None)],
    time: Annotated[NonEmptyStr | None, Query(None)],
    open: Annotated[str | None, Query(None)],
    closed: Annotated[str | None, Query(None)],
    changesets: Annotated[NonEmptyStr | None, Query(None)],  # TODO: test sequence
    limit: Annotated[int, Query(CHANGESET_QUERY_DEFAULT_LIMIT, gt=0, le=CHANGESET_QUERY_MAX_LIMIT)],
) -> Sequence[dict]:
    geometry = parse_bbox(bbox) if bbox else None

    if user and display_name:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, 'provide either the user ID or display name, but not both')

    if user:
        user_ = await User.find_one_by_id(user)  # TODO: user cache
        if not user_:
            raise HTTPException(status.HTTP_404_NOT_FOUND, 'Object not found')

    if display_name:
        user_ = await User.find_one_by_display_name(display_name)
        if not user_:
            raise HTTPException(status.HTTP_404_NOT_FOUND, 'Object not found')
        user = user_.id

    if time:
        try:
            if ',' in time:
                parts = time.split(',', maxsplit=1)
                time_created_before = parse_date(parts[0])
                time_closed_after = parse_date(parts[1])
            else:
                time_closed_after = parse_date(time)
                time_created_before = None
        except Exception as e:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f'no time information in "{time}"') from e
    else:
        time_closed_after = None
        time_created_before = None

    if time_closed_after and time_created_before and time_closed_after > time_created_before:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, 'The time range is invalid, T1 > T2')

    if open and closed:
        return ()

    if changesets:
        parts = (c.strip() for c in changesets.split(','))
        parts = (c for c in parts if c and c.isdigit())
        changesets = tuple(int(c) for c in parts)
        if not changesets:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, 'No changesets were given to search for')

    changesets = await Changeset.find_many_by_query_with_(
        ids=changesets,
        user_id=user,
        time_closed_after=time_closed_after,
        time_created_before=time_created_before,
        open=True if open else (False if closed else None),
        geometry=geometry,
        sort={'_id': ASCENDING},
        limit=limit,
    )

    return Format06.encode_changesets(changesets)


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
        elements = await Format06.decode_osmchange(data, changeset_id)
    except Exception as e:
        raise_for().bad_xml(type.value, xml, str(e))

    assigned_ref_map = await Optimistic(elements).update()
    return Format06.encode_diff_result(assigned_ref_map)
