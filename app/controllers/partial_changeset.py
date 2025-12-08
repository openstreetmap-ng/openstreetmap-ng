from asyncio import TaskGroup
from base64 import urlsafe_b64encode
from math import ceil

from fastapi import APIRouter
from shapely import measurement
from starlette import status

from app.config import CHANGESET_COMMENT_BODY_MAX_LENGTH, CHANGESET_COMMENTS_PAGE_SIZE
from app.format.element_list import FormatElementList
from app.lib.render_response import render_response
from app.lib.rich_text import process_rich_text_plain
from app.lib.translation import t
from app.models.proto.shared_pb2 import PartialChangesetParams, SharedBounds
from app.models.types import ChangesetId
from app.queries.changeset_bounds_query import ChangesetBoundsQuery
from app.queries.changeset_comment_query import ChangesetCommentQuery
from app.queries.changeset_query import ChangesetQuery
from app.queries.element_query import ElementQuery
from app.queries.user_query import UserQuery
from app.queries.user_subscription_query import UserSubscriptionQuery

router = APIRouter(prefix='/partial/changeset')


@router.get('/{id:int}')
async def get_changeset(id: ChangesetId):
    changeset = await ChangesetQuery.find_by_id(id)
    if changeset is None:
        return await render_response(
            'partial/not-found',
            {'type': 'changeset', 'id': id},
            status=status.HTTP_404_NOT_FOUND,
        )

    async def elements_task():
        return await FormatElementList.changeset_elements(
            await ElementQuery.find_by_changeset(id, sort_by='typed_id'),
        )

    async def adjacent_task():
        nonlocal prev_changeset_id, next_changeset_id
        changeset_user_id = changeset['user_id']
        if changeset_user_id is None:
            return None, None
        return await ChangesetQuery.find_adjacent_ids(id, user_id=changeset_user_id)

    async with TaskGroup() as tg:
        items = [changeset]
        tg.create_task(UserQuery.resolve_users(items))
        tg.create_task(ChangesetBoundsQuery.resolve_bounds(items))
        tg.create_task(ChangesetCommentQuery.resolve_num_comments(items))
        elements_t = tg.create_task(elements_task())
        adjacent_t = tg.create_task(adjacent_task())
        is_subscribed_t = tg.create_task(
            UserSubscriptionQuery.is_subscribed('changeset', id)
        )

    elements = elements_t.result()
    prev_changeset_id, next_changeset_id = adjacent_t.result()

    comment_text = changeset['tags'].pop('comment', None) or t('browse.no_comment')
    comment_html = process_rich_text_plain(comment_text)

    changeset_comments_num_items = changeset['num_comments']  # pyright: ignore [reportTypedDictNotRequiredAccess]
    changeset_comments_num_pages = ceil(
        changeset_comments_num_items / CHANGESET_COMMENTS_PAGE_SIZE
    )

    bounds = changeset.get('bounds')
    bboxes: list[list[float]]
    bboxes = measurement.bounds(bounds.geoms).tolist() if bounds is not None else []  # type: ignore
    params_bounds = [
        SharedBounds(
            min_lon=bbox[0],
            min_lat=bbox[1],
            max_lon=bbox[2],
            max_lat=bbox[3],
        )
        for bbox in bboxes
    ]

    params = PartialChangesetParams(
        id=id,
        bounds=params_bounds,
        nodes=elements['node'],
        ways=elements['way'],
        relations=elements['relation'],
    )

    return await render_response(
        'partial/changeset',
        {
            'changeset': changeset,
            'changeset_comments_num_items': changeset_comments_num_items,
            'changeset_comments_num_pages': changeset_comments_num_pages,
            'prev_changeset_id': prev_changeset_id,
            'next_changeset_id': next_changeset_id,
            'is_subscribed': is_subscribed_t.result(),
            'tags': changeset['tags'],
            'comment_html': comment_html,
            'params': urlsafe_b64encode(params.SerializeToString()).decode(),
            'CHANGESET_COMMENT_BODY_MAX_LENGTH': CHANGESET_COMMENT_BODY_MAX_LENGTH,
        },
    )
