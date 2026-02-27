from asyncio import TaskGroup
from base64 import urlsafe_b64encode

from fastapi import APIRouter
from shapely import get_coordinates
from starlette import status

from typing import Annotated

from fastapi import Query

from app.config import ELEMENT_DEEP_HISTORY_DEFAULT_LIMIT, ELEMENT_HISTORY_PAGE_SIZE
from app.format import FormatRender
from app.format.element_list import FormatElementList
from app.lib.feature_icon import features_icons
from app.lib.feature_name import features_names
from app.lib.render_response import render_response
from app.lib.rich_text import process_rich_text_plain
from app.lib.translation import t
from app.models.db.element import Element
from app.models.element import ElementId, ElementType
from app.models.proto.shared_pb2 import PartialElementParams
from app.models.types import SequenceId
from app.queries.changeset_query import ChangesetQuery
from app.queries.element_query import ElementQuery
from app.queries.user_query import UserQuery
from speedup import element_type, typed_element_id

router = APIRouter(prefix='/partial')


@router.get('/{type:element_type}/{id:int}')
async def get_latest(type: ElementType, id: ElementId):
    typed_id = typed_element_id(type, id)
    at_sequence_id = await ElementQuery.get_current_sequence_id()
    elements = await ElementQuery.find_by_refs(
        [typed_id], at_sequence_id=at_sequence_id, limit=1
    )
    element = next(iter(elements), None)
    if element is None:
        return await render_response(
            'partial/not-found',
            {'type': type, 'id': id},
            status=status.HTTP_404_NOT_FOUND,
        )

    # if the element was superseded (very small chance), get data just before
    last_sequence_id = await ElementQuery.get_last_visible_sequence_id(element)
    if last_sequence_id is not None:
        at_sequence_id = last_sequence_id

    data = await get_element_data(element, at_sequence_id, include_parents=True)
    return await render_response('partial/element', data)


@router.get('/{type:element_type}/{id:int}/history/{version:int}')
async def get_version(type: ElementType, id: ElementId, version: int):
    versioned_typed_id = (typed_element_id(type, id), version)
    at_sequence_id = await ElementQuery.get_current_sequence_id()
    elements = await ElementQuery.find_by_versioned_refs(
        [versioned_typed_id], at_sequence_id=at_sequence_id, limit=1
    )
    element = next(iter(elements), None)
    if element is None:
        id_text = f'{id} {t("browse.version").lower()} {version}'
        return await render_response(
            'partial/not-found',
            {'type': type, 'id': id_text},
            status=status.HTTP_404_NOT_FOUND,
        )

    # if the element was superseded, get data just before
    last_sequence_id = await ElementQuery.get_last_visible_sequence_id(element)
    if last_sequence_id is not None:
        at_sequence_id = last_sequence_id
        include_parents = False
    else:
        include_parents = True

    data = await get_element_data(
        element, at_sequence_id, include_parents=include_parents
    )
    return await render_response('partial/element', data)


@router.get('/{type:element_type}/{id:int}/history')
async def get_history(type: ElementType, id: ElementId):
    typed_id = typed_element_id(type, id)
    at_sequence_id = await ElementQuery.get_current_sequence_id()
    current_version_map = await ElementQuery.map_refs_to_current_versions(
        [typed_id], at_sequence_id=at_sequence_id
    )
    if typed_id not in current_version_map:
        return await render_response(
            'partial/not-found',
            {'type': type, 'id': id},
            status=status.HTTP_404_NOT_FOUND,
        )

    return await render_response(
        'partial/element-history',
        {
            'type': type,
            'id': id,
            'page_size': ELEMENT_HISTORY_PAGE_SIZE,
        },
    )


@router.get('/{type:element_type}/{id:int}/deep-history')
async def get_deep_history(
    type: ElementType,
    id: ElementId,
    limit: Annotated[int, Query(ge=1, le=1000)] = ELEMENT_DEEP_HISTORY_DEFAULT_LIMIT,
):
    """Get deep history view showing all versions in a single table."""
    typed_id = typed_element_id(type, id)
    at_sequence_id = await ElementQuery.get_current_sequence_id()

    # Get all versions up to the limit
    elements = await ElementQuery.find_versions_by_ref(
        typed_id,
        at_sequence_id=at_sequence_id,
        sort_dir='desc',
        limit=limit,
    )
    if not elements:
        return await render_response(
            'partial/not-found',
            {'type': type, 'id': id},
            status=status.HTTP_404_NOT_FOUND,
        )

    # Resolve changesets and users for all versions
    changeset_ids = list({e['changeset_id'] for e in elements})
    changesets = await ChangesetQuery.find(changeset_ids=changeset_ids, limit=None)
    await UserQuery.resolve_users(changesets)
    changeset_map = {cs['id']: cs for cs in changesets}

    # Get parent ways for nodes (at current sequence)
    parent_ways = []
    if type == 'node':
        parent_ways = await ElementQuery.find_parents_by_refs(
            [typed_id],
            at_sequence_id=at_sequence_id,
            parent_type='way',
            limit=None,
        )

    # Build version data
    versions_data = []
    for element in elements:
        changeset = changeset_map.get(element['changeset_id'])

        # Get coordinates for nodes
        coords = None
        if (point := element['point']) is not None:
            from shapely import get_coordinates as shapely_get_coords
            x, y = shapely_get_coords(point)[0].tolist()
            coords = {'lat': y, 'lon': x}

        versions_data.append({
            'element': element,
            'changeset': changeset,
            'coords': coords,
        })

    total_versions = elements[0]['version'] if elements else 0
    has_more = len(elements) == limit and total_versions > limit

    return await render_response(
        'partial/element-deep-history',
        {
            'type': type,
            'id': id,
            'versions_data': versions_data,
            'parent_ways': parent_ways,
            'total_versions': total_versions,
            'limit': limit,
            'has_more': has_more,
            'default_limit': ELEMENT_DEEP_HISTORY_DEFAULT_LIMIT,
        },
    )


async def get_element_data(
    element: Element, at_sequence_id: SequenceId, *, include_parents: bool
) -> dict:
    typed_id = element['typed_id']
    type = element_type(typed_id)
    version = element['version']

    async def changeset_task():
        changeset = await ChangesetQuery.find_by_id(element['changeset_id'])
        assert changeset is not None, 'Parent changeset must exist'
        await UserQuery.resolve_users([changeset])
        return changeset

    async def data_task():
        members = element['members']
        members_elements = await ElementQuery.find_by_refs(
            members,
            at_sequence_id=at_sequence_id,
            recurse_ways=True,
            sort_dir='asc',
            limit=None,
        )
        return (
            [element, *members_elements],
            FormatElementList.element_members(
                members, element['members_roles'], members_elements
            ),
        )

    async def parents_task():
        return FormatElementList.element_parents(
            typed_id,
            await ElementQuery.find_parents_by_refs(
                [typed_id],
                at_sequence_id=at_sequence_id,
                limit=None,
            ),
        )

    async with TaskGroup() as tg:
        changeset_t = tg.create_task(changeset_task())

        data_t = parents_t = None
        if element['visible']:
            data_t = tg.create_task(data_task())
            if include_parents:
                parents_t = tg.create_task(parents_task())

    changeset = changeset_t.result()
    full_data, element_members = data_t.result() if data_t is not None else ([], [])
    element_parents = parents_t.result() if parents_t is not None else []

    comment_text = changeset['tags'].get('comment') or t('browse.no_comment')
    comment_html = process_rich_text_plain(comment_text)

    if (point := element['point']) is not None:
        x, y = get_coordinates(point)[0].tolist()
        place = f'{y:.7f}, {x:.7f}'
    else:
        place = None

    prev_version = version - 1 if version > 1 else None
    next_version = version + 1 if not element['latest'] else None
    icon = features_icons([element])[0]
    name = features_names([element])[0]
    render_data = FormatRender.encode_elements(full_data, detailed=True)

    param = PartialElementParams(
        type=type,
        members=element_members,
        parents=element_parents,
        render=render_data,
    )

    return {
        'element': element,
        'place': place,
        'changeset': changeset,
        'prev_version': prev_version,
        'next_version': next_version,
        'icon': icon,
        'name': name,
        'tags': element['tags'],
        'comment_html': comment_html,
        'show_elements': bool(element_members),
        'show_parents': bool(element_parents),
        'params': urlsafe_b64encode(param.SerializeToString()).decode(),
    }
