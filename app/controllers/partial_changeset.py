from asyncio import TaskGroup
from base64 import urlsafe_b64encode
from itertools import starmap
from math import ceil

from fastapi import APIRouter
from shapely import measurement
from starlette import status

from app.format.element_list import FormatElementList
from app.lib.render_response import render_response
from app.lib.tags_format import tags_format
from app.lib.translation import t
from app.limits import CHANGESET_COMMENT_BODY_MAX_LENGTH, CHANGESET_COMMENTS_PAGE_SIZE
from app.models.db.changeset import ChangesetId
from app.models.proto.shared_pb2 import PartialChangesetParams, SharedBounds
from app.queries.changeset_bounds_query import ChangesetBoundsQuery
from app.queries.changeset_comment_query import ChangesetCommentQuery
from app.queries.changeset_query import ChangesetQuery
from app.queries.element_query import ElementQuery
from app.queries.user_query import UserQuery
from app.queries.user_subscription_query import UserSubscriptionQuery

router = APIRouter(prefix='/api/partial/changeset')


@router.get('/{id:int}')
async def get_changeset(id: ChangesetId):
    changeset = await ChangesetQuery.find_by_id(id)
    if changeset is None:
        return await render_response(
            'partial/not_found.jinja2',
            {'type': 'changeset', 'id': id},
            status=status.HTTP_404_NOT_FOUND,
        )

    async def elements_task():
        return await FormatElementList.changeset_elements(
            await ElementQuery.get_by_changeset(id, sort_by='typed_id'),
        )

    async def adjacent_task():
        nonlocal prev_changeset_id, next_changeset_id
        changeset_user_id = changeset['user_id']
        if changeset_user_id is None:
            return None, None
        return await ChangesetQuery.get_user_adjacent_ids(id, user_id=changeset_user_id)

    async with TaskGroup() as tg:
        items = [changeset]
        tg.create_task(UserQuery.resolve_users(items))
        tg.create_task(ChangesetBoundsQuery.resolve_bounds(items))
        tg.create_task(ChangesetCommentQuery.resolve_num_comments(items))
        elements_t = tg.create_task(elements_task())
        adjacent_t = tg.create_task(adjacent_task())
        is_subscribed_t = tg.create_task(UserSubscriptionQuery.is_subscribed('changeset', id))

    elements = elements_t.result()
    prev_changeset_id, next_changeset_id = adjacent_t.result()

    changeset_tags = changeset['tags']
    if not changeset_tags.get('comment'):
        changeset_tags['comment'] = t('browse.no_comment')
    tags = tags_format(changeset_tags)
    comment_tag = tags.pop('comment')

    changeset_comments_num_items = changeset['num_comments']  # pyright: ignore [reportTypedDictNotRequiredAccess]
    changeset_comments_num_pages = ceil(changeset_comments_num_items / CHANGESET_COMMENTS_PAGE_SIZE)

    bboxes: list[list[float]]
    bboxes = measurement.bounds(changeset['bounds'].geoms).tolist()  # type: ignore
    params_bounds = list(starmap(SharedBounds, bboxes))

    params = PartialChangesetParams(
        id=id,
        bounds=params_bounds,
        nodes=elements['node'],
        ways=elements['way'],
        relations=elements['relation'],
    )

    return await render_response(
        'partial/changeset.jinja2',
        {
            'changeset': changeset,
            'changeset_comments_num_items': changeset_comments_num_items,
            'changeset_comments_num_pages': changeset_comments_num_pages,
            'prev_changeset_id': prev_changeset_id,
            'next_changeset_id': next_changeset_id,
            'is_subscribed': is_subscribed_t.result(),
            'tags': tags.values(),
            'comment_tag': comment_tag,
            'params': urlsafe_b64encode(params.SerializeToString()).decode(),
            'CHANGESET_COMMENT_BODY_MAX_LENGTH': CHANGESET_COMMENT_BODY_MAX_LENGTH,
        },
    )
