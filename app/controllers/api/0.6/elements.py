from collections.abc import Sequence
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import PlainTextResponse
from pydantic import PositiveInt

from app.lib.auth_context import api_user
from app.lib.exceptions_context import raise_for
from app.lib.format06 import Format06
from app.lib.optimistic import Optimistic
from app.lib.xmltodict import XMLToDict
from app.models.db.user import User
from app.models.element_type import ElementType
from app.models.scope import Scope
from app.models.typed_element_ref import TypedElementRef
from app.models.versioned_element_ref import VersionedElementRef
from app.repositories.element_repository import ElementRepository

# TODO: rate limit
# TODO: dependency for xml parsing?
router = APIRouter()

# TODO: redaction (403 forbidden), https://wiki.openstreetmap.org/wiki/API_v0.6#Redaction:_POST_/api/0.6/[node|way|relation]/#id/#version/redact?redaction=#redaction_id
# TODO: HttpUrl, ConstrainedUrl


@router.put('/{type}/create', response_class=PlainTextResponse)
async def element_create(
    request: Request,
    type: ElementType,
    _: Annotated[User, api_user(Scope.write_api)],
) -> int:
    xml = (await request.body()).decode()
    data: dict = XMLToDict.parse(xml).get('osm', {}).get(type.value, {})

    if not data:
        raise_for().bad_xml(type.value, xml, f"XML doesn't contain an osm/{type.value} element.")

    # force dynamic id allocation
    data['@id'] = -1

    try:
        element = Format06.decode_element(data, changeset_id=None)
    except Exception as e:
        raise_for().bad_xml(type.value, xml, str(e))

    assigned_ref_map = await Optimistic([element]).update()
    return next(iter(assigned_ref_map.values()))[0].typed_id


@router.get('/{type}/{typed_id}')
@router.get('/{type}/{typed_id}.xml')
@router.get('/{type}/{typed_id}.json')
async def element_read_latest(
    type: ElementType,
    typed_id: PositiveInt,
) -> dict:
    typed_ref = TypedElementRef(type=type, typed_id=typed_id)
    elements = await ElementRepository.get_many_latest_by_typed_refs([typed_ref], limit=None)
    element = elements[0] if elements else None

    if not element:
        raise_for().element_not_found(typed_ref)
    if not element.visible:
        raise HTTPException(status.HTTP_410_GONE)

    return Format06.encode_element(element)


@router.get('/{type}/{typed_id}/{version}')
@router.get('/{type}/{typed_id}/{version}.xml')
@router.get('/{type}/{typed_id}/{version}.json')
async def element_read_version(
    type: ElementType,
    typed_id: PositiveInt,
    version: PositiveInt,
) -> dict:
    versioned_ref = VersionedElementRef(type=type, typed_id=typed_id, version=version)
    elements = await ElementRepository.get_many_by_versioned_refs([versioned_ref])

    if not elements:
        raise_for().element_not_found(versioned_ref)

    return Format06.encode_element(elements[0])


@router.put('/{type}/{typed_id}', response_class=PlainTextResponse)
async def element_update(
    request: Request,
    type: ElementType,
    typed_id: PositiveInt,
    _: Annotated[User, api_user(Scope.write_api)],
) -> int:
    xml = (await request.body()).decode()
    data: dict = XMLToDict.parse(xml).get('osm', {}).get(type.value, {})

    if not data:
        raise_for().bad_xml(type.value, xml, f"XML doesn't contain an osm/{type.value} element.")

    data['@id'] = typed_id

    try:
        element = Format06.decode_element(data, changeset_id=None)
    except Exception as e:
        raise_for().bad_xml(type.value, xml, str(e))

    await Optimistic([element]).update()
    return element.version


@router.delete('/{type}/{typed_id}', response_class=PlainTextResponse)
async def element_delete(
    request: Request,
    type: ElementType,
    typed_id: PositiveInt,
    _: Annotated[User, api_user(Scope.write_api)],
) -> int:
    xml = (await request.body()).decode()
    data: dict = XMLToDict.parse(xml).get('osm', {}).get(type.value, {})

    if not data:
        raise_for().bad_xml(type.value, xml, f"XML doesn't contain an osm/{type.value} element.")

    data['@id'] = typed_id
    data['@visible'] = False

    try:
        element = Format06.decode_element(data, changeset_id=None)
    except Exception as e:
        raise_for().bad_xml(type.value, xml, str(e))

    await Optimistic([element]).update()
    return element.version


@router.get('/{type}/{typed_id}/history')
@router.get('/{type}/{typed_id}/history.xml')
@router.get('/{type}/{typed_id}/history.json')
async def element_history(
    type: ElementType,
    typed_id: PositiveInt,
) -> Sequence[dict]:
    typed_ref = TypedElementRef(type=type, typed_id=typed_id)
    elements = await ElementRepository.get_many_by_typed_ref(typed_ref, limit=None)

    if not elements:
        raise_for().element_not_found(typed_ref)

    return Format06.encode_elements(elements)


@router.get('/{type}s')
@router.get('/{type}s.xml')
@router.get('/{type}s.json')
async def elements_read_many(
    type: ElementType,
    nodes: Annotated[str | None, Query(None)],
    ways: Annotated[str | None, Query(None)],
    relations: Annotated[str | None, Query(None)],
) -> Sequence[dict]:
    query = {
        ElementType.node: nodes,
        ElementType.way: ways,
        ElementType.relation: relations,
    }[type]

    if not query:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f'The parameter {type.value}s is required, and must be of the form '
            f'{type.value}s=ID[vVER][,ID[vVER][,ID[vVER]...]].',
        )

    try:
        query = (q.strip() for q in query.split(','))
        query = (q for q in query if q)
        query = {
            VersionedElementRef.from_type_str(type, q)
            if 'v' in q
            else TypedElementRef(
                type=type,
                typed_id=int(q),
            )
            for q in query
        }
    except ValueError as e:
        # parsing error => element not found
        raise HTTPException(status.HTTP_404_NOT_FOUND) from e

    elements = await ElementRepository.find_many_by_refs(query, limit=None)

    if not all(elements):
        raise HTTPException(status.HTTP_404_NOT_FOUND)

    return Format06.encode_elements(elements)


@router.get('/{type}/{typed_id}/relations')
@router.get('/{type}/{typed_id}/relations.xml')
@router.get('/{type}/{typed_id}/relations.json')
async def element_parent_relations(
    type: ElementType,
    typed_id: PositiveInt,
) -> Sequence[dict]:
    typed_ref = TypedElementRef(type=type, typed_id=typed_id)
    elements = await ElementRepository.get_many_parents_by_typed_refs(
        [typed_ref],
        parent_type=ElementType.relation,
        limit=None,
    )
    return Format06.encode_elements(elements)


@router.get('/node/{typed_id}/ways')
@router.get('/node/{typed_id}/ways.xml')
@router.get('/node/{typed_id}/ways.json')
async def element_parent_ways(
    typed_id: PositiveInt,
) -> Sequence[dict]:
    typed_ref = TypedElementRef(type=ElementType.node, typed_id=typed_id)
    elements = await ElementRepository.get_many_parents_by_typed_refs(
        [typed_ref],
        parent_type=ElementType.way,
        limit=None,
    )
    return Format06.encode_elements(elements)


@router.get('/{type}/{typed_id}/full')
@router.get('/{type}/{typed_id}/full.xml')
@router.get('/{type}/{typed_id}/full.json')
async def element_full(
    type: ElementType.way | ElementType.relation,
    typed_id: PositiveInt,
) -> Sequence[dict]:
    typed_ref = TypedElementRef(type=type, typed_id=typed_id)
    elements = await ElementRepository.get_many_latest_by_typed_refs([typed_ref], limit=None)
    element = elements[0] if elements else None

    if not element:
        raise_for().element_not_found(typed_ref)
    if not element.visible:
        raise HTTPException(status.HTTP_410_GONE)

    elements = await ElementRepository.get_many_latest_by_typed_refs(
        tuple(member.typed_ref for member in element.members),
        recurse_ways=True,
        limit=None,
    )

    return Format06.encode_elements(elements)
