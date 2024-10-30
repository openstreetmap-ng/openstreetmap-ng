from asyncio import TaskGroup
from base64 import urlsafe_b64encode
from itertools import chain
from typing import Annotated

from fastapi import APIRouter, Query
from pydantic import PositiveInt
from sqlalchemy.orm import joinedload

from app.format import FormatLeaflet
from app.format.element_list import FormatElementList
from app.lib.feature_icon import features_icons
from app.lib.feature_name import features_names
from app.lib.options_context import options_context
from app.lib.render_response import render_response
from app.lib.tags_diff_mode import tags_diff_mode
from app.lib.tags_format import tags_format
from app.lib.translation import t
from app.limits import ELEMENT_HISTORY_PAGE_SIZE
from app.models.db.changeset import Changeset
from app.models.db.element import Element
from app.models.db.user import User
from app.models.element import ElementId, ElementRef, ElementType, VersionedElementRef
from app.models.proto.shared_pb2 import PartialElementParams
from app.queries.changeset_query import ChangesetQuery
from app.queries.element_member_query import ElementMemberQuery
from app.queries.element_query import ElementQuery

router = APIRouter(prefix='/api/partial')


@router.get('/{type:element_type}/{id:int}')
async def get_latest(type: ElementType, id: Annotated[ElementId, PositiveInt]):
    at_sequence_id = await ElementQuery.get_current_sequence_id()

    ref = ElementRef(type, id)
    elements = await ElementQuery.get_by_refs(
        (ref,),
        at_sequence_id=at_sequence_id,
        limit=1,
    )
    element = elements[0] if elements else None

    if element is None:
        return await render_response('partial/not_found.jinja2', {'type': type, 'id': id})

    # if the element was superseded (very small chance), get data just before
    last_sequence_id = await ElementQuery.get_last_visible_sequence_id(element)
    if last_sequence_id is not None:
        at_sequence_id = last_sequence_id

    await ElementMemberQuery.resolve_members((element,))
    data = await _get_element_data(element, at_sequence_id, include_parents=True)
    return await render_response('partial/element.jinja2', data)


@router.get('/{type:element_type}/{id:int}/history/{version:int}')
async def get_version(
    type: ElementType,
    id: Annotated[ElementId, PositiveInt],
    version: Annotated[int, PositiveInt],
):
    at_sequence_id = await ElementQuery.get_current_sequence_id()
    include_parents = True

    ref = VersionedElementRef(type, id, version)
    elements = await ElementQuery.get_by_versioned_refs(
        (ref,),
        at_sequence_id=at_sequence_id,
        limit=1,
    )
    element = elements[0] if elements else None

    if element is None:
        id_text = f'{id} {t("browse.version").lower()} {version}'
        return await render_response('partial/not_found.jinja2', {'type': type, 'id': id_text})

    # if the element was superseded, get data just before
    last_sequence_id = await ElementQuery.get_last_visible_sequence_id(element)
    if last_sequence_id is not None:
        at_sequence_id = last_sequence_id
        include_parents = False

    await ElementMemberQuery.resolve_members((element,))
    data = await _get_element_data(element, at_sequence_id, include_parents=include_parents)
    return await render_response('partial/element.jinja2', data)


@router.get('/{type:element_type}/{id:int}/history')
async def get_history(
    type: ElementType,
    id: Annotated[ElementId, PositiveInt],
    tags_diff_mode_flag: Annotated[bool, Query(alias='tags_diff_mode')],
    page: Annotated[PositiveInt, Query()] = 1,
):
    ref = ElementRef(type, id)
    at_sequence_id = await ElementQuery.get_current_sequence_id()
    current_version = await ElementQuery.get_current_version_by_ref(ref, at_sequence_id=at_sequence_id)

    if current_version == 0:
        return await render_response('partial/not_found.jinja2', {'type': type, 'id': id})

    page_size = ELEMENT_HISTORY_PAGE_SIZE
    num_pages = (current_version + page_size - 1) // page_size
    version_max = current_version - page_size * (page - 1)
    version_min = version_max - page_size + 1

    async with TaskGroup() as tg:
        previous_task = (
            tg.create_task(
                ElementQuery.get_by_versioned_refs(
                    (VersionedElementRef(type, id, version_min - 1),),
                    at_sequence_id=at_sequence_id,
                    limit=1,
                )
            )
            if tags_diff_mode_flag
            else None
        )

        elements = await ElementQuery.get_versions_by_ref(
            ref,
            at_sequence_id=at_sequence_id,
            version_range=(version_min, version_max),
            sort='desc',
            limit=page_size,
        )
        await ElementMemberQuery.resolve_members(elements)

        async def data_task(element: Element):
            at_sequence_id_ = at_sequence_id
            include_parents = True

            # if the element was superseded, get data just before
            last_sequence_id = await ElementQuery.get_last_visible_sequence_id(element)
            if last_sequence_id is not None:
                at_sequence_id_ = last_sequence_id
                include_parents = False

            return await _get_element_data(element, at_sequence_id_, include_parents=include_parents)

        elements_tasks = tuple(tg.create_task(data_task(element)) for element in elements)

    elements_data = tuple(task.result() for task in elements_tasks)

    if tags_diff_mode_flag:
        previous_element_ = previous_task.result()  # pyright: ignore[reportOptionalMemberAccess]
        previous_element = previous_element_[0] if previous_element_ else None
        tags_diff_mode(previous_element, elements_data)

    return await render_response(
        'partial/element_history.jinja2',
        {
            'type': type,
            'id': id,
            'page': page,
            'num_pages': num_pages,
            'elements_data': elements_data,
            'tags_diff_mode': tags_diff_mode_flag,
        },
    )


async def _get_element_data(element: Element, at_sequence_id: int, *, include_parents: bool) -> dict:
    members = element.members
    if members is None:
        raise AssertionError('Element members must be set')

    async def changeset_task():
        with options_context(
            joinedload(Changeset.user).load_only(
                User.id,
                User.display_name,
                User.avatar_type,
                User.avatar_id,
            )
        ):
            changeset = await ChangesetQuery.find_by_id(element.changeset_id)
            if changeset is None:
                raise AssertionError('Parent changeset must exist')
            return changeset

    async def data_task():
        members_refs = {ElementRef(member.type, member.id) for member in members}
        members_elements = await ElementQuery.get_by_refs(
            members_refs,
            at_sequence_id=at_sequence_id,
            recurse_ways=True,
            limit=None,
        )
        await ElementMemberQuery.resolve_members(members_elements)
        full_data = chain((element,), members_elements)
        element_members = FormatElementList.element_members(members, members_elements)
        return full_data, element_members

    async def parents_task():
        ref = ElementRef(element.type, element.id)
        parents = await ElementQuery.get_parents_by_refs(
            (ref,),
            at_sequence_id=at_sequence_id,
            limit=None,
        )
        await ElementMemberQuery.resolve_members(parents)
        return FormatElementList.element_parents(ref, parents)

    async with TaskGroup() as tg:
        changeset_t = tg.create_task(changeset_task())
        data_t = parents_t = None
        if element.visible:
            data_t = tg.create_task(data_task())
            if include_parents:
                parents_t = tg.create_task(parents_task())

    changeset = changeset_t.result()
    full_data, element_members = data_t.result() if (data_t is not None) else ((), ())
    element_parents = parents_t.result() if (parents_t is not None) else ()

    comment_str = changeset.tags.get('comment') or t('browse.no_comment')
    comment_tag = tags_format({'comment': comment_str})['comment']

    prev_version = element.version - 1 if element.version > 1 else None
    next_version = element.version + 1 if (element.next_sequence_id is not None) else None
    icon = features_icons((element,))[0]
    name = features_names((element,))[0]
    tags_map = tags_format(element.tags)
    render_data = FormatLeaflet.encode_elements(full_data, detailed=False)

    param = PartialElementParams(
        type=element.type,
        members=element_members,
        parents=element_parents,
        render=render_data,
    )
    return {
        'element': element,
        'changeset': changeset,
        'prev_version': prev_version,
        'next_version': next_version,
        'icon': icon,
        'name': name,
        'tags_map': tags_map,
        'comment_tag': comment_tag,
        'show_elements': bool(element_members),
        'show_parents': bool(element_parents),
        'params': urlsafe_b64encode(param.SerializeToString()).decode(),
    }
