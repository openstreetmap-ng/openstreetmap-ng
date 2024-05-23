from collections.abc import Sequence
from typing import Annotated

from anyio import create_task_group
from fastapi import APIRouter, Query
from pydantic import PositiveInt
from sqlalchemy.orm import joinedload

from app.format import FormatLeaflet
from app.lib.element_list_formatter import format_element_members_list, format_element_parents_list
from app.lib.feature_name import feature_name
from app.lib.options_context import options_context
from app.lib.render_response import render_response
from app.lib.tags_format import tags_format
from app.lib.translation import t
from app.limits import ELEMENT_HISTORY_PAGE_SIZE
from app.models.db.changeset import Changeset
from app.models.db.element import Element
from app.models.db.user import User
from app.models.element_list_entry import ElementMemberEntry
from app.models.element_ref import ElementRef, VersionedElementRef
from app.models.element_type import ElementType
from app.models.tag_format import TagFormatCollection
from app.queries.changeset_query import ChangesetQuery
from app.queries.element_member_query import ElementMemberQuery
from app.queries.element_query import ElementQuery
from app.utils import JSON_ENCODE

router = APIRouter(prefix='/api/partial')


@router.get('/{type:element_type}/{id:int}')
async def get_latest(type: ElementType, id: PositiveInt):
    at_sequence_id = await ElementQuery.get_current_sequence_id()

    ref = ElementRef(type, id)
    elements = await ElementQuery.get_by_refs(
        (ref,),
        at_sequence_id=at_sequence_id,
        limit=1,
    )
    element = elements[0] if elements else None

    if element is None:
        return render_response(
            'partial/not_found.jinja2',
            {'type': type, 'id': id},
        )

    # if the element was superseded (very small chance), get data just before
    if element.next_sequence_id is not None:
        at_sequence_id = await ElementQuery.get_last_visible_sequence_id(element)

    await ElementMemberQuery.resolve_members((element,))
    data = await _get_element_data(element, at_sequence_id, include_parents=True)
    return render_response('partial/element.jinja2', data)


@router.get('/{type:element_type}/{id:int}/history/{version:int}')
async def get_version(type: ElementType, id: PositiveInt, version: PositiveInt):
    at_sequence_id = await ElementQuery.get_current_sequence_id()
    parents = True

    ref = VersionedElementRef(type, id, version)
    elements = await ElementQuery.get_by_versioned_refs(
        (ref,),
        at_sequence_id=at_sequence_id,
        limit=1,
    )
    element = elements[0] if elements else None

    if element is None:
        id_text = f'{id} {t("browse.version").lower()} {version}'
        return render_response(
            'partial/not_found.jinja2',
            {'type': type, 'id': id_text},
        )

    # if the element was superseded, get data just before
    if element.next_sequence_id is not None:
        at_sequence_id = await ElementQuery.get_last_visible_sequence_id(element)
        parents = False

    await ElementMemberQuery.resolve_members((element,))
    data = await _get_element_data(element, at_sequence_id, include_parents=parents)
    return render_response('partial/element.jinja2', data)


@router.get('/{type:element_type}/{id:int}/history')
async def get_history(
    type: ElementType,
    id: PositiveInt,
    page: Annotated[PositiveInt, Query()] = 1,
):
    at_sequence_id = await ElementQuery.get_current_sequence_id()

    ref = ElementRef(type, id)
    current_version = await ElementQuery.get_current_version_by_ref(ref, at_sequence_id=at_sequence_id)

    # TODO: cython?
    # TODO: not found
    page_size = ELEMENT_HISTORY_PAGE_SIZE
    num_pages = (current_version + page_size - 1) // page_size
    version_max = current_version - page_size * (page - 1)
    version_min = version_max - page_size + 1

    elements = await ElementQuery.get_versions_by_ref(
        ref,
        at_sequence_id=at_sequence_id,
        version_range=(version_min, version_max),
        sort='desc',
        limit=ELEMENT_HISTORY_PAGE_SIZE,
    )

    await ElementMemberQuery.resolve_members(elements)
    elements_data = [None] * len(elements)

    async def data_task(i: int, element: Element):
        at_sequence_id_ = at_sequence_id
        parents = True

        # if the element was superseded, get data just before
        if element.next_sequence_id is not None:
            at_sequence_id_ = await ElementQuery.get_last_visible_sequence_id(element)
            parents = False

        element_data = await _get_element_data(element, at_sequence_id_, include_parents=parents)
        elements_data[i] = element_data

    async with create_task_group() as tg:
        for i, element in enumerate(elements):
            tg.start_soon(data_task, i, element)

    return render_response(
        'partial/element_history.jinja2',
        {
            'type': type,
            'id': id,
            'page': page,
            'num_pages': num_pages,
            'elements_data': elements_data,
        },
    )


async def _get_element_data(element: Element, at_sequence_id: int, *, include_parents: bool) -> dict:
    changeset: Changeset = None
    list_parents: Sequence[ElementMemberEntry] = ()
    full_data: Sequence[Element] = ()
    list_elements: Sequence[ElementMemberEntry] = ()

    async def changeset_user_task():
        nonlocal changeset
        with options_context(
            joinedload(Changeset.user).load_only(
                User.id,
                User.display_name,
                User.avatar_type,
                User.avatar_id,
            )
        ):
            changesets = await ChangesetQuery.find_many_by_query(changeset_ids=(element.changeset_id,), limit=1)
            changeset = changesets[0]

    async def parents_task():
        nonlocal list_parents
        ref = ElementRef(element.type, element.id)
        parents = await ElementQuery.get_parents_by_refs(
            (ref,),
            at_sequence_id=at_sequence_id,
            limit=None,
        )
        await ElementMemberQuery.resolve_members(parents)
        list_parents = format_element_parents_list(ref, parents)

    async def data_task():
        nonlocal full_data, list_elements
        members_refs = {ElementRef(member.type, member.id) for member in element.members}
        members_elements = await ElementQuery.get_by_refs(
            members_refs,
            at_sequence_id=at_sequence_id,
            recurse_ways=True,
            limit=None,
        )
        await ElementMemberQuery.resolve_members(members_elements)
        direct_members = tuple(
            member
            for member in members_elements  #
            if ElementRef(member.type, member.id) in members_refs
        )
        full_data = (element, *members_elements)
        list_elements = format_element_members_list(element.members, direct_members)

    async with create_task_group() as tg:
        tg.start_soon(changeset_user_task)
        if element.visible:
            if include_parents:
                tg.start_soon(parents_task)
            if element.members:
                tg.start_soon(data_task)
            else:
                full_data = (element,)

    comment = changeset.tags.get('comment')
    if comment is not None:
        comment_tag = tags_format({'comment': comment})['comment']
    else:
        comment_tag = TagFormatCollection('comment', t('browse.no_comment'))

    prev_version = element.version - 1 if element.version > 1 else None
    next_version = element.version + 1 if (element.next_sequence_id is not None) else None
    name = feature_name(element.tags)
    tags = tags_format(element.tags)
    leaflet = FormatLeaflet.encode_elements(full_data, detailed=False)

    return {
        'element': element,
        'changeset': changeset,
        'prev_version': prev_version,
        'next_version': next_version,
        'name': name,
        'tags': tags.values(),
        'comment_tag': comment_tag,
        'show_elements': bool(list_elements),
        'show_part_of': bool(list_parents),
        'params': JSON_ENCODE(
            {
                'type': element.type,
                'id': element.id,
                'version': element.version,
                'lists': {
                    'part_of': list_parents,
                    'elements': list_elements,
                },
            }
        ).decode(),
        'leaflet': JSON_ENCODE(leaflet).decode(),
    }
