from collections.abc import Sequence
from typing import Annotated

import cython
from fastapi import APIRouter, Query, Response, status
from pydantic import PositiveInt
from sqlalchemy.orm import joinedload

from app.format06 import Format06
from app.lib.auth_context import api_user
from app.lib.exceptions_context import raise_for
from app.lib.statement_context import options_context
from app.lib.xml_body import xml_body
from app.models.db.element import Element
from app.models.db.user import User
from app.models.element_ref import ElementRef, VersionedElementRef
from app.models.element_type import ElementType
from app.models.scope import Scope
from app.repositories.element_repository import ElementRepository
from app.services.optimistic_diff import OptimisticDiff

router = APIRouter(prefix='/api/0.6')

# TODO: redaction (403 forbidden), https://wiki.openstreetmap.org/wiki/API_v0.6#Redaction:_POST_/api/0.6/[node|way|relation]/#id/#version/redact?redaction=#redaction_id
# TODO: HttpUrl, ConstrainedUrl


@cython.cfunc
def _get_element_data(elements: Sequence[tuple[str, dict]], type: ElementType):
    """
    Get the first element of the given type from the sequence of elements.
    """
    for s in elements:
        if s[0] == type:
            return s
    return None


@cython.cfunc
def _register_routes(type: ElementType):
    """
    Register routes for the given element type.
    """

    @router.put(f'/{type}/create')
    async def element_create(
        elements: Annotated[Sequence, xml_body('osm')],
        _: Annotated[User, api_user(Scope.write_api)],
    ):
        data = _get_element_data(elements, type)
        if data is None:
            raise_for().bad_xml(type, f"XML doesn't contain an osm/{type} element.")

        data[1]['@id'] = -1  # dynamic id allocation
        data[1]['@version'] = 0

        try:
            element = Format06.decode_element(data)
        except Exception as e:
            raise_for().bad_xml(type, str(e))

        assigned_ref_map = await OptimisticDiff((element,)).run()
        assigned_id = next(iter(assigned_ref_map.values()))[0].id
        return Response(str(assigned_id), media_type='text/plain')

    @router.get(f'/{type}/{{id:int}}')
    @router.get(f'/{type}/{{id:int}}.xml')
    @router.get(f'/{type}/{{id:int}}.json')
    async def element_read_latest(id: PositiveInt):
        at_sequence_id = await ElementRepository.get_current_sequence_id()

        with options_context(joinedload(Element.changeset)):
            ref = ElementRef(type, id)
            elements = await ElementRepository.get_many_by_refs(
                (ref,),
                at_sequence_id=at_sequence_id,
                limit=1,
            )
            element = elements[0] if elements else None

        if element is None:
            raise_for().element_not_found(ref)
        if not element.visible:
            return Response(None, status.HTTP_410_GONE)

        return Format06.encode_element(element)

    @router.get(f'/{type}/{{id:int}}/{{version:int}}')
    @router.get(f'/{type}/{{id:int}}/{{version:int}}.xml')
    @router.get(f'/{type}/{{id:int}}/{{version:int}}.json')
    async def element_read_version(id: PositiveInt, version: PositiveInt):
        with options_context(joinedload(Element.changeset)):
            versioned_ref = VersionedElementRef(type, id, version)
            elements = await ElementRepository.get_many_by_versioned_refs((versioned_ref,), limit=1)

        if not elements:
            raise_for().element_not_found(versioned_ref)

        return Format06.encode_element(elements[0])

    @router.put(f'/{type}/{{id:int}}')
    async def element_update(
        id: PositiveInt,
        elements: Annotated[Sequence, xml_body('osm')],
        _: Annotated[User, api_user(Scope.write_api)],
    ):
        data = _get_element_data(elements, type)
        if data is None:
            raise_for().bad_xml(type, f"XML doesn't contain an osm/{type} element.")

        data[1]['@id'] = id

        try:
            element = Format06.decode_element(data)
        except Exception as e:
            raise_for().bad_xml(type, str(e))

        await OptimisticDiff((element,)).run()
        return Response(str(element.version), media_type='text/plain')

    @router.delete(f'/{type}/{{id:int}}')
    async def element_delete(
        id: PositiveInt,
        elements: Annotated[Sequence, xml_body('osm')],
        _: Annotated[User, api_user(Scope.write_api)],
    ):
        data = _get_element_data(elements, type)
        if data is None:
            raise_for().bad_xml(type, f"XML doesn't contain an osm/{type} element.")

        data[1]['@id'] = id
        data[1]['@visible'] = False

        try:
            element = Format06.decode_element(data)
        except Exception as e:
            raise_for().bad_xml(type, str(e))

        await OptimisticDiff((element,)).run()
        return Response(str(element.version), media_type='text/plain')

    @router.get(f'/{type}/{{id:int}}/history')
    @router.get(f'/{type}/{{id:int}}/history.xml')
    @router.get(f'/{type}/{{id:int}}/history.json')
    async def element_history(id: PositiveInt):
        at_sequence_id = await ElementRepository.get_current_sequence_id()

        with options_context(joinedload(Element.changeset)):
            element_ref = ElementRef(type, id)
            elements = await ElementRepository.get_versions_by_ref(
                element_ref,
                at_sequence_id=at_sequence_id,
                limit=None,
            )

        if not elements:
            raise_for().element_not_found(element_ref)

        return Format06.encode_elements(elements)

    @router.get(f'/{type}s')
    @router.get(f'/{type}s.xml')
    @router.get(f'/{type}s.json')
    async def elements_read_many(
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
                    else ElementRef(type, int(q))
                )
        except ValueError:
            # return not found on parsing errors, why?, idk
            return Response(None, status.HTTP_404_NOT_FOUND)

        at_sequence_id = await ElementRepository.get_current_sequence_id()

        with options_context(joinedload(Element.changeset)):
            elements = await ElementRepository.find_many_by_any_refs(
                parsed_query,
                at_sequence_id=at_sequence_id,
                limit=None,
            )

        for element in elements:
            if element is None:
                return Response(None, status.HTTP_404_NOT_FOUND)

        return Format06.encode_elements(elements)

    @router.get(f'/{type}/{{id:int}}/relations')
    @router.get(f'/{type}/{{id:int}}/relations.xml')
    @router.get(f'/{type}/{{id:int}}/relations.json')
    async def element_parent_relations(id: PositiveInt):
        at_sequence_id = await ElementRepository.get_current_sequence_id()

        with options_context(joinedload(Element.changeset)):
            element_ref = ElementRef(type, id)
            elements = await ElementRepository.get_many_parents_by_refs(
                (element_ref,),
                at_sequence_id=at_sequence_id,
                parent_type='relation',
                limit=None,
            )
        return Format06.encode_elements(elements)

    @router.get(f'/{type}/{{id:int}}/full')
    @router.get(f'/{type}/{{id:int}}/full.xml')
    @router.get(f'/{type}/{{id:int}}/full.json')
    async def element_full(id: PositiveInt):
        at_sequence_id = await ElementRepository.get_current_sequence_id()

        with options_context(joinedload(Element.changeset)):
            element_ref = ElementRef(type, id)
            elements = await ElementRepository.get_many_by_refs(
                (element_ref,),
                at_sequence_id=at_sequence_id,
                limit=1,
            )
            element = elements[0] if elements else None

        if element is None:
            raise_for().element_not_found(element_ref)
        if not element.visible:
            return Response(None, status.HTTP_410_GONE)

        with options_context(joinedload(Element.changeset)):
            members_element_refs = tuple(member.element_ref for member in element.members)
            members_elements = await ElementRepository.get_many_by_refs(
                members_element_refs,
                at_sequence_id=at_sequence_id,
                recurse_ways=True,
                limit=None,
            )

        return Format06.encode_elements((element, *members_elements))


_register_routes('node')
_register_routes('way')
_register_routes('relation')


@router.get('/node/{id:int}/ways')
@router.get('/node/{id:int}/ways.xml')
@router.get('/node/{id:int}/ways.json')
async def node_parent_ways(id: PositiveInt):
    at_sequence_id = await ElementRepository.get_current_sequence_id()

    with options_context(joinedload(Element.changeset)):
        element_ref = ElementRef('node', id)
        elements = await ElementRepository.get_many_parents_by_refs(
            (element_ref,),
            at_sequence_id=at_sequence_id,
            parent_type='way',
            limit=None,
        )

    return Format06.encode_elements(elements)
