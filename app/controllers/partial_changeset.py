from asyncio import TaskGroup
from base64 import urlsafe_b64encode

import cython
from fastapi import APIRouter
from pydantic import PositiveInt
from sqlalchemy.orm import joinedload
from starlette import status

from app.format.element_list import FormatElementList
from app.lib.options_context import options_context
from app.lib.render_response import render_response
from app.lib.tags_format import tags_format
from app.lib.translation import t
from app.limits import CHANGESET_COMMENT_BODY_MAX_LENGTH
from app.models.db.changeset import Changeset
from app.models.db.changeset_comment import ChangesetComment
from app.models.db.user import User
from app.models.db.user_subscription import UserSubscriptionTarget
from app.models.proto.shared_pb2 import PartialChangesetParams, SharedBounds
from app.queries.changeset_comment_query import ChangesetCommentQuery
from app.queries.changeset_query import ChangesetQuery
from app.queries.element_query import ElementQuery
from app.queries.user_subscription_query import UserSubscriptionQuery

router = APIRouter(prefix='/api/partial/changeset')


@router.get('/{id:int}')
async def get_changeset(id: PositiveInt):
    with options_context(
        joinedload(Changeset.user).load_only(
            User.id,
            User.display_name,
            User.avatar_type,
            User.avatar_id,
        )
    ):
        changeset = await ChangesetQuery.find_by_id(id)

    if changeset is None:
        return await render_response(
            'partial/not_found.jinja2',
            {'type': 'changeset', 'id': id},
            status=status.HTTP_404_NOT_FOUND,
        )

    prev_changeset_id: int | None = None
    next_changeset_id: int | None = None

    async def elements_task():
        elements_ = await ElementQuery.get_by_changeset(id, sort_by='id')
        return await FormatElementList.changeset_elements(elements_)

    async def comments_task():
        with options_context(joinedload(ChangesetComment.user)):
            await ChangesetCommentQuery.resolve_comments((changeset,), limit_per_changeset=None, resolve_rich_text=True)

    async def adjacent_ids_task():
        nonlocal prev_changeset_id, next_changeset_id
        changeset_user_id = changeset.user_id
        if changeset_user_id is None:
            return
        t = await ChangesetQuery.get_user_adjacent_ids(id, user_id=changeset_user_id)
        prev_changeset_id, next_changeset_id = t

    async with TaskGroup() as tg:
        elements_t = tg.create_task(elements_task())
        tg.create_task(comments_task())
        tg.create_task(adjacent_ids_task())
        is_subscribed_t = tg.create_task(UserSubscriptionQuery.is_subscribed(UserSubscriptionTarget.changeset, id))

    changeset_tags = changeset.tags
    if not changeset_tags.get('comment'):
        changeset_tags['comment'] = t('browse.no_comment')
    tags = tags_format(changeset.tags)
    comment_tag = tags.pop('comment')

    params_bounds: list[SharedBounds] = [None] * len(changeset.bounds)  # pyright: ignore[reportAssignmentType]
    i: cython.int
    for i, cb in enumerate(changeset.bounds):
        bounds = cb.bounds.bounds
        params_bounds[i] = SharedBounds(
            min_lon=bounds[0],
            min_lat=bounds[1],
            max_lon=bounds[2],
            max_lat=bounds[3],
        )
    elements = elements_t.result()
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
            'prev_changeset_id': prev_changeset_id,
            'next_changeset_id': next_changeset_id,
            'is_subscribed': is_subscribed_t.result(),
            'tags': tags.values(),
            'comment_tag': comment_tag,
            'params': urlsafe_b64encode(params.SerializeToString()).decode(),
            'CHANGESET_COMMENT_BODY_MAX_LENGTH': CHANGESET_COMMENT_BODY_MAX_LENGTH,
        },
    )
