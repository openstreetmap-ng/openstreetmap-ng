from asyncio import TaskGroup
from collections.abc import Collection, Iterable, Sequence
from itertools import chain
from typing import Annotated

from fastapi import APIRouter, Query, Response, status
from pydantic import PositiveInt

from app.format import Format06
from app.lib.auth_context import api_user
from app.lib.exceptions_context import raise_for
from app.lib.xml_body import xml_body
from app.models.db.element import Element
from app.models.db.user import User
from app.models.element import ElementId, ElementRef, ElementType, VersionedElementRef
from app.models.scope import Scope
from app.queries.element_member_query import ElementMemberQuery
from app.queries.element_query import ElementQuery
from app.queries.user_query import UserQuery
from app.services.optimistic_diff import OptimisticDiff

router = APIRouter(prefix='/api/0.6')

# TODO: redaction (403 forbidden), https://wiki.openstreetmap.org/wiki/API_v0.6#Redaction:_POST_/api/0.6/[node|way|relation]/#id/#version/redact?redaction=#redaction_id
# TODO: HttpUrl, ConstrainedUrl


@router.put('/{type:element_type}/create')
async def create_element(
    type: ElementType,
    elements: Annotated[Sequence, xml_body('osm')],
    _: Annotated[User, api_user(Scope.write_api)],
):
    data = _get_element_data(elements, type)
    if data is None:
        raise_for.bad_xml(type, f"XML doesn't contain an osm/{type} element.")

    data[1]['@id'] = -1  # dynamic id allocation
    data[1]['@version'] = 0

    try:
        element = Format06.decode_element(data)
    except Exception as e:
        raise_for.bad_xml(type, str(e))

    assigned_ref_map = await OptimisticDiff.run((element,))
    assigned_id = next(iter(assigned_ref_map.values()))[0].id
    return Response(str(assigned_id), media_type='text/plain')


@router.put('/{type:element_type}/{id:int}')
async def update_element(
    type: ElementType,
    id: PositiveInt,
    elements: Annotated[Sequence, xml_body('osm')],
    _: Annotated[User, api_user(Scope.write_api)],
):
    data = _get_element_data(elements, type)
    if data is None:
        raise_for.bad_xml(type, f"XML doesn't contain an osm/{type} element.")

    data[1]['@id'] = id

    try:
        element = Format06.decode_element(data)
    except Exception as e:
        raise_for.bad_xml(type, str(e))

    await OptimisticDiff.run((element,))
    return Response(str(element.version), media_type='text/plain')


@router.delete('/{type:element_type}/{id:int}')
async def delete_element(
    type: ElementType,
    id: PositiveInt,
    elements: Annotated[Sequence, xml_body('osm')],
    _: Annotated[User, api_user(Scope.write_api)],
):
    data = _get_element_data(elements, type)
    if data is None:
        raise_for.bad_xml(type, f"XML doesn't contain an osm/{type} element.")

    data[1]['@id'] = id
    data[1]['@visible'] = False

    try:
        element = Format06.decode_element(data)
    except Exception as e:
        raise_for.bad_xml(type, str(e))

    await OptimisticDiff.run((element,))
    return Response(str(element.version), media_type='text/plain')


@router.get('/{type:element_type}s')
@router.get('/{type:element_type}s.xml')
@router.get('/{type:element_type}s.json')
async def get_many(
    type: ElementType,
    query: Annotated[str | None, Query(alias=f'{type}s')] = None,
):
    if not query:
        return Response(
            f'The parameter {type}s is required, and must be of the form '
            f'{type}s=ID[vVER][,ID[vVER][,ID[vVER]...]].',
            status.HTTP_400_BAD_REQUEST,
        )

    # remove duplicates and preserve order
    parsed_query_set: set[str] = set()
    parsed_query: list[VersionedElementRef | ElementRef] = []

    try:
        for q in query.split(','):
            q = q.strip()
            if (not q) or (q in parsed_query_set):
                continue
            parsed_query_set.add(q)
            parsed_query.append(
                VersionedElementRef.from_type_str(type, q)
                if 'v' in q  #
                else ElementRef(type, ElementId(int(q)))
            )
    except ValueError:
        # return not found on parsing errors, why?, idk
        return Response(None, status.HTTP_404_NOT_FOUND)

    elements = await ElementQuery.find_many_by_any_refs(parsed_query, limit=None)
    if any(element is None for element in elements):
        return Response(None, status.HTTP_404_NOT_FOUND)

    return await _encode_elements(elements)  # pyright: ignore[reportArgumentType]


@router.get('/{type:element_type}/{id:int}')
@router.get('/{type:element_type}/{id:int}.xml')
@router.get('/{type:element_type}/{id:int}.json')
async def get_latest(type: ElementType, id: Annotated[ElementId, PositiveInt]):
    ref = ElementRef(type, id)
    elements = await ElementQuery.get_by_refs((ref,), limit=1)
    element = elements[0] if elements else None
    if element is None:
        raise_for.element_not_found(ref)
    if not element.visible:
        return Response(None, status.HTTP_410_GONE)
    return await _encode_element(element)


@router.get('/{type:element_type}/{id:int}/{version:int}')
@router.get('/{type:element_type}/{id:int}/{version:int}.xml')
@router.get('/{type:element_type}/{id:int}/{version:int}.json')
async def get_version(
    type: ElementType,
    id: Annotated[ElementId, PositiveInt],
    version: Annotated[int, PositiveInt],
):
    ref = VersionedElementRef(type, id, version)
    elements = await ElementQuery.get_by_versioned_refs((ref,), limit=1)
    element = elements[0] if elements else None
    if element is None:
        raise_for.element_not_found(ref)
    return await _encode_element(element)


@router.get('/{type:element_type}/{id:int}/history')
@router.get('/{type:element_type}/{id:int}/history.xml')
@router.get('/{type:element_type}/{id:int}/history.json')
async def get_history(type: ElementType, id: Annotated[ElementId, PositiveInt]):
    ref = ElementRef(type, id)
    elements = await ElementQuery.get_versions_by_ref(ref, limit=None)
    if not elements:
        raise_for.element_not_found(ref)
    return await _encode_elements(elements)


@router.get('/{type:element_type}/{id:int}/full')
@router.get('/{type:element_type}/{id:int}/full.xml')
@router.get('/{type:element_type}/{id:int}/full.json')
async def get_full(type: ElementType, id: Annotated[ElementId, PositiveInt]):
    ref = ElementRef(type, id)
    at_sequence_id = await ElementQuery.get_current_sequence_id()
    elements = await ElementQuery.get_by_refs(
        (ref,),
        at_sequence_id=at_sequence_id,
        limit=1,
    )
    element = elements[0] if elements else None

    if element is None:
        raise_for.element_not_found(ref)
    if not element.visible:
        return Response(None, status.HTTP_410_GONE)

    async with TaskGroup() as tg:
        tg.create_task(UserQuery.resolve_elements_users(elements, display_name=True))
        tg.create_task(ElementMemberQuery.resolve_members(elements))

    members_refs = {ElementRef(member.type, member.id) for member in element.members}  # pyright: ignore[reportOptionalIterable]
    members_elements = await ElementQuery.get_by_refs(
        members_refs,
        at_sequence_id=at_sequence_id,
        recurse_ways=True,
        limit=None,
    )

    async with TaskGroup() as tg:
        tg.create_task(UserQuery.resolve_elements_users(members_elements, display_name=True))
        tg.create_task(ElementMemberQuery.resolve_members(members_elements))

    return Format06.encode_elements(chain((element,), members_elements))


@router.get('/{type:element_type}/{id:int}/relations')
@router.get('/{type:element_type}/{id:int}/relations.xml')
@router.get('/{type:element_type}/{id:int}/relations.json')
async def get_parent_relations(type: ElementType, id: Annotated[ElementId, PositiveInt]):
    ref = ElementRef(type, id)
    elements = await ElementQuery.get_parents_by_refs((ref,), parent_type='relation', limit=None)
    return await _encode_elements(elements)


@router.get('/node/{id:int}/ways')
@router.get('/node/{id:int}/ways.xml')
@router.get('/node/{id:int}/ways.json')
async def get_parent_ways(id: Annotated[ElementId, PositiveInt]):
    ref = ElementRef('node', id)
    elements = await ElementQuery.get_parents_by_refs((ref,), parent_type='way', limit=None)
    return await _encode_elements(elements)


def _get_element_data(
    elements: Iterable[tuple[ElementType, dict]], type: ElementType
) -> tuple[ElementType, dict] | None:
    """
    Get the first element of the given type from the sequence of elements.
    """
    return next((s for s in elements if s[0] == type), None)


async def _encode_element(element: Element):
    """
    Resolve required data fields for element and encode it.
    """
    elements = (element,)
    async with TaskGroup() as tg:
        tg.create_task(UserQuery.resolve_elements_users(elements, display_name=True))
        tg.create_task(ElementMemberQuery.resolve_members(elements))
    return Format06.encode_element(element)


async def _encode_elements(elements: Collection[Element]):
    """
    Resolve required data fields for elements and encode them.
    """
    async with TaskGroup() as tg:
        tg.create_task(UserQuery.resolve_elements_users(elements, display_name=True))
        tg.create_task(ElementMemberQuery.resolve_members(elements))
    return Format06.encode_elements(elements)
