from collections.abc import Sequence
from typing import Annotated

import anyio
from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import PlainTextResponse
from pydantic import PositiveInt

from cython_lib.xmltodict import XMLToDict
from lib.auth import api_user
from lib.exceptions import raise_for
from lib.format.format06 import Format06
from lib.optimistic import Optimistic
from models.db.element import Element
from models.db.user import User
from models.element_type import ElementType
from models.scope import Scope
from models.typed_element_ref import TypedElementRef
from models.versioned_element_ref import VersionedElementRef

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
) -> PositiveInt:
    xml = (await request.body()).decode()
    data: dict = XMLToDict.parse(xml).get('osm', {}).get(type.value, {})

    if not data:
        raise_for().bad_xml(type.value, xml, f"XML doesn't contain an osm/{type.value} element.")

    # dynamically assign element id
    data['@id'] = -1

    try:
        element = Format06.decode_element(data, changeset_id=None)
    except Exception as e:
        raise_for().bad_xml(type.value, xml, str(e))

    old_ref_elements_map = await Optimistic((element,)).update()
    return next(iter(old_ref_elements_map.values()))[0].typed_id


@router.get('/{type}/{typed_id}')
@router.get('/{type}/{typed_id}.xml')
@router.get('/{type}/{typed_id}.json')
async def element_read(
    type: ElementType,
    typed_id: PositiveInt,
) -> dict:
    element = await Element.find_one_by_typed_ref(TypedElementRef(type=type, typed_id=typed_id))

    if not element:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    if not element.visible:
        raise HTTPException(status.HTTP_410_GONE)

    return Format06.encode_element(element)


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

    await Optimistic((element,)).update()
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

    await Optimistic((element,)).update()
    return element.version


@router.get('/{type}/{typed_id}/{version}')
@router.get('/{type}/{typed_id}/{version}.xml')
@router.get('/{type}/{typed_id}/{version}.json')
async def element_read_version(
    type: ElementType,
    typed_id: PositiveInt,
    version: PositiveInt,
) -> dict:
    element = await Element.find_one_by_versioned_ref(
        VersionedElementRef(type=type, typed_id=typed_id, version=version)
    )

    if not element:
        raise HTTPException(status.HTTP_404_NOT_FOUND)

    return Format06.encode_element(element)


@router.get('/{type}/{typed_id}/history')
@router.get('/{type}/{typed_id}/history.xml')
@router.get('/{type}/{typed_id}/history.json')
async def element_history(
    type: ElementType,
    typed_id: PositiveInt,
) -> Sequence[dict]:
    elements = await Element.find_many_by_typed_ref(TypedElementRef(type=type, typed_id=typed_id), limit=None)

    if not elements:
        raise HTTPException(status.HTTP_404_NOT_FOUND)

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
            f'The parameter {type.value}s is required, and must be of the form {type.value}s=ID[vVER][,ID[vVER][,ID[vVER]...]].',
        )

    query = (q.strip() for q in query.split(','))
    query = tuple(
        VersionedElementRef.from_type_str(type, q) if 'v' in q else TypedElementRef(type=type, typed_id=int(q))
        for q in query
        if q
    )
    elements = [None] * len(query)

    # TODO: more of this style
    cls_: Element = {
        ElementType.node: ElementNode,
        ElementType.way: ElementWay,
        ElementType.relation: ElementRelation,
    }[type]

    async def get_one(i: int, q: VersionedElementRef | TypedElementRef) -> None:
        if isinstance(q, VersionedElementRef):
            element = await cls_.find_one_by_versioned_ref(q)
        else:
            element = await cls_.find_one_by_typed_ref(q)

        if not element:
            raise HTTPException(status.HTTP_404_NOT_FOUND)

        elements[i] = element

    async with anyio.create_task_group() as tg:
        for i, q in enumerate(query):
            tg.start_soon(get_one, i, q)

    return Format06.encode_elements(elements)


@router.get('/{type}/{typed_id}/relations')
@router.get('/{type}/{typed_id}/relations.xml')
@router.get('/{type}/{typed_id}/relations.json')
async def element_relations(
    type: ElementType,
    typed_id: PositiveInt,
) -> Sequence[dict]:
    element = await Element.find_one_by_typed_ref(TypedElementRef(type=type, typed_id=typed_id))
    elements = await element.get_referenced_by(ElementType.relation, limit=None) if element else ()
    return Format06.encode_elements(elements)


@router.get('/node/{typed_id}/ways')
@router.get('/node/{typed_id}/ways.xml')
@router.get('/node/{typed_id}/ways.json')
async def node_ways(
    typed_id: PositiveInt,
) -> Sequence[dict]:
    type = ElementType.node
    element = await Element.find_one_by_typed_ref(TypedElementRef(type=type, typed_id=typed_id))
    elements = await element.get_referenced_by(ElementType.way, limit=None) if element else ()
    return Format06.encode_elements(elements)


@router.get('/{type}/{typed_id}/full')
@router.get('/{type}/{typed_id}/full.xml')
@router.get('/{type}/{typed_id}/full.json')
async def element_full(
    type: ElementType.way | ElementType.relation,
    typed_id: PositiveInt,
) -> Sequence[dict]:
    element = await Element.find_one_by_typed_ref(TypedElementRef(type=type, typed_id=typed_id))

    if not element:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    if not element.visible:
        raise HTTPException(status.HTTP_410_GONE)

    elements = await element.get_references(recurse_ways=True, limit=None)
    return Format06.encode_elements(elements)
