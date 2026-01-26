from asyncio import TaskGroup
from typing import Annotated

from fastapi import APIRouter, Path, Query, Response, status

from app.format import Format06
from app.lib.auth_context import api_user
from app.lib.exceptions_context import raise_for
from app.lib.xml_body import xml_body
from app.models.db.element import Element
from app.models.db.user import User
from app.models.element import ElementId, ElementType, TypedElementId
from app.queries.element_query import ElementQuery
from app.queries.user_query import UserQuery
from app.services.optimistic_diff import OptimisticDiff
from speedup import (
    element_id,
    typed_element_id,
    versioned_typed_element_id,
)

router = APIRouter(prefix='/api/0.6')

# TODO: redaction (403 forbidden), https://wiki.openstreetmap.org/wiki/API_v0.6#Redaction:_POST_/api/0.6/[node|way|relation]/#id/#version/redact?redaction=#redaction_id
# TODO: HttpUrl, ConstrainedUrl
# TODO: create many


@router.post('/{type:element_type}s')
@router.put('/{type:element_type}/create')
async def create_element(
    type: ElementType,
    elements: Annotated[list, xml_body('osm')],
    _: Annotated[User, api_user('write_api')],
):
    data = _get_elements_data(elements, type)
    if not data:
        raise_for.bad_xml(type, f"XML doesn't contain an osm/{type} element.")

    for i, d in enumerate(data, 1):
        d[1]['@id'] = -i  # Force dynamic id allocation
        d[1]['@version'] = 0

    try:
        elements = Format06.decode_elements(data)
    except Exception as e:
        raise_for.bad_xml(type, str(e))

    assigned_ref_map = await OptimisticDiff.run(elements)
    assigned_id = element_id(next(iter(assigned_ref_map.values()))[0])
    return Response(str(assigned_id), media_type='text/plain')


@router.put('/{type:element_type}/{id:int}')
async def update_element(
    type: ElementType,
    id: Annotated[ElementId, Path(gt=0)],  # Updating requires a positive id
    elements: Annotated[list, xml_body('osm')],
    _: Annotated[User, api_user('write_api')],
):
    data = _get_elements_data(elements, type)
    if not data:
        raise_for.bad_xml(type, f"XML doesn't contain an osm/{type} element.")

    for d in data:
        d[1]['@id'] = id

    try:
        elements = Format06.decode_elements(data)
    except Exception as e:
        raise_for.bad_xml(type, str(e))

    await OptimisticDiff.run(elements)
    return Response(str(elements[-1]['version']), media_type='text/plain')


@router.delete('/{type:element_type}/{id:int}')
async def delete_element(
    type: ElementType,
    id: Annotated[ElementId, Path(gt=0)],  # Updating requires a positive id
    elements: Annotated[list, xml_body('osm')],
    _: Annotated[User, api_user('write_api')],
):
    data = _get_elements_data(elements, type)
    if not data:
        raise_for.bad_xml(type, f"XML doesn't contain an osm/{type} element.")

    data = [data[0]]  # Supports deleting only one element
    for d in data:
        d[1]['@id'] = id
        d[1]['@visible'] = False

    try:
        elements = Format06.decode_elements(data)
    except Exception as e:
        raise_for.bad_xml(type, str(e))

    await OptimisticDiff.run(elements)
    return Response(str(elements[-1]['version']), media_type='text/plain')


@router.get('/{type:element_type}s')
@router.get('/{type:element_type}s.xml')
@router.get('/{type:element_type}s.json')
async def get_many(
    type: ElementType,
    nodes: Annotated[str | None, Query()] = None,
    ways: Annotated[str | None, Query()] = None,
    relations: Annotated[str | None, Query()] = None,
):
    if type == 'node':
        query = nodes
    elif type == 'way':
        query = ways
    elif type == 'relation':
        query = relations
    else:
        raise NotImplementedError(f'Unsupported element type {type!r}')

    if not query:
        return Response(
            f'The parameter {type}s is required, and must be of the form {type}s=ID[vVER][,ID[vVER][,ID[vVER]...]].',
            status.HTTP_400_BAD_REQUEST,
        )

    # Remove duplicates and preserve order
    parsed_query_set = set[str]()
    parsed_query: list[TypedElementId | tuple[TypedElementId, int]] = []

    try:
        for q in query.split(','):
            q = q.strip()
            if not q or q in parsed_query_set:
                continue
            parsed_query_set.add(q)
            parsed_query.append(
                versioned_typed_element_id(type, q)
                if 'v' in q
                else typed_element_id(type, int(q))  # type: ignore
            )
    except ValueError:
        # Return not found on parsing errors, why?, IDK
        return Response(None, status.HTTP_404_NOT_FOUND)

    elements = await ElementQuery.find_by_any_refs(parsed_query, limit=None)
    if None in elements:
        return Response(None, status.HTTP_404_NOT_FOUND)

    return await _encode_elements(elements)  # type: ignore


@router.get('/{type:element_type}/{id:int}')
@router.get('/{type:element_type}/{id:int}.xml')
@router.get('/{type:element_type}/{id:int}.json')
async def get_latest(type: ElementType, id: ElementId):
    typed_id = typed_element_id(type, id)
    elements = await ElementQuery.find_by_refs([typed_id], limit=1)
    element = next(iter(elements), None)
    if element is None:
        raise_for.element_not_found(typed_id)

    if not element['visible']:
        return Response(None, status.HTTP_410_GONE)

    return await _encode_element(element)


@router.get('/{type:element_type}/{id:int}/{version:int}')
@router.get('/{type:element_type}/{id:int}/{version:int}.xml')
@router.get('/{type:element_type}/{id:int}/{version:int}.json')
async def get_version(type: ElementType, id: ElementId, version: int):
    ref = (typed_element_id(type, id), version)
    elements = await ElementQuery.find_by_versioned_refs([ref], limit=1)
    if not elements:
        raise_for.element_not_found(ref)

    return await _encode_element(elements[0])


@router.get('/{type:element_type}/{id:int}/history')
@router.get('/{type:element_type}/{id:int}/history.xml')
@router.get('/{type:element_type}/{id:int}/history.json')
async def get_history(type: ElementType, id: ElementId):
    typed_id = typed_element_id(type, id)
    elements = await ElementQuery.find_versions_by_ref(typed_id, limit=None)
    if not elements:
        raise_for.element_not_found(typed_id)

    return await _encode_elements(elements)


@router.get('/{type:element_type}/{id:int}/full')
@router.get('/{type:element_type}/{id:int}/full.xml')
@router.get('/{type:element_type}/{id:int}/full.json')
async def get_full(type: ElementType, id: ElementId):
    typed_id = typed_element_id(type, id)
    at_sequence_id = await ElementQuery.get_current_sequence_id()
    elements = await ElementQuery.find_by_refs(
        [typed_id], at_sequence_id=at_sequence_id, limit=1
    )
    element = next(iter(elements), None)
    if element is None:
        raise_for.element_not_found(typed_id)

    if not element['visible']:
        return Response(None, status.HTTP_410_GONE)

    async with TaskGroup() as tg:
        tg.create_task(UserQuery.resolve_elements_users(elements))

        members_elements = await ElementQuery.find_by_refs(
            element['members'],
            at_sequence_id=at_sequence_id,
            skip_typed_ids=[typed_id],
            recurse_ways=True,
            sort_dir='asc',
            limit=None,
        )
        tg.create_task(UserQuery.resolve_elements_users(members_elements))

    # Ensure members are before the element
    members_elements.append(element)
    return Format06.encode_elements(members_elements)


@router.get('/{type:element_type}/{id:int}/relations')
@router.get('/{type:element_type}/{id:int}/relations.xml')
@router.get('/{type:element_type}/{id:int}/relations.json')
async def get_parent_relations(type: ElementType, id: ElementId):
    typed_id = typed_element_id(type, id)
    elements = await ElementQuery.find_parents_by_refs(
        [typed_id], parent_type='relation', limit=None
    )
    return await _encode_elements(elements)


@router.get('/node/{id:int}/ways')
@router.get('/node/{id:int}/ways.xml')
@router.get('/node/{id:int}/ways.json')
async def get_parent_ways(id: ElementId):
    typed_id = typed_element_id('node', id)
    elements = await ElementQuery.find_parents_by_refs(
        [typed_id], parent_type='way', limit=None
    )
    return await _encode_elements(elements)


def _get_elements_data(elements: list[tuple[ElementType, dict]], type: ElementType):
    """Get the first element of the given type from the sequence of elements."""
    return [s for s in elements if s[0] == type]


async def _encode_element(element: Element):
    """Resolve required data fields for element and encode it."""
    await UserQuery.resolve_elements_users([element])
    return Format06.encode_element(element)


async def _encode_elements(elements: list[Element]):
    """Resolve required data fields for elements and encode them."""
    await UserQuery.resolve_elements_users(elements)
    return Format06.encode_elements(elements)
