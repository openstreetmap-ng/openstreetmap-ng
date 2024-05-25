from collections.abc import Sequence

from anyio import create_task_group
from fastapi import APIRouter
from pydantic import PositiveInt
from sqlalchemy.orm import joinedload

from app.lib.auth_context import auth_user
from app.lib.element_list_formatter import ElementType, format_changeset_elements_list
from app.lib.options_context import options_context
from app.lib.render_response import render_response
from app.lib.tags_format import tags_format
from app.lib.translation import t
from app.models.db.changeset import Changeset
from app.models.db.changeset_comment import ChangesetComment
from app.models.db.user import User
from app.models.element_list_entry import ChangesetElementEntry
from app.models.tag_format import TagFormatCollection
from app.queries.changeset_comment_query import ChangesetCommentQuery
from app.queries.changeset_query import ChangesetQuery
from app.queries.element_query import ElementQuery
from app.utils import JSON_ENCODE

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
        changeset = await ChangesetQuery.get_by_id(id)

    if changeset is None:
        return render_response(
            'partial/not_found.jinja2',
            {'type': 'changeset', 'id': id},
        )

    elements: dict[ElementType, Sequence[ChangesetElementEntry]] | None = None
    prev_changeset_id: int | None = None
    next_changeset_id: int | None = None
    is_subscribed = False

    async def elements_task():
        nonlocal elements
        elements_ = await ElementQuery.get_by_changeset(id, sort_by='id')
        elements = await format_changeset_elements_list(elements_)

    async def comments_task():
        with options_context(joinedload(ChangesetComment.user)):
            await ChangesetCommentQuery.resolve_comments((changeset,), limit_per_changeset=None, resolve_rich_text=True)

    async def adjacent_ids_task():
        nonlocal prev_changeset_id, next_changeset_id
        t: tuple = await ChangesetQuery.get_user_adjacent_ids(id, user_id=changeset.user_id)
        prev_changeset_id = t[0]
        next_changeset_id = t[1]

    async def subscription_task():
        nonlocal is_subscribed
        is_subscribed = await ChangesetCommentQuery.is_subscribed(id)

    async with create_task_group() as tg:
        tg.start_soon(elements_task)
        tg.start_soon(comments_task)
        if changeset.user_id is not None:
            tg.start_soon(adjacent_ids_task)
        if auth_user() is not None:
            tg.start_soon(subscription_task)

    tags = tags_format(changeset.tags)
    comment_tag = tags.pop('comment', None)
    if comment_tag is None:
        comment_tag = TagFormatCollection('comment', t('browse.no_comment'))

    return render_response(
        'partial/changeset.jinja2',
        {
            'changeset': changeset,
            'prev_changeset_id': prev_changeset_id,
            'next_changeset_id': next_changeset_id,
            'is_subscribed': is_subscribed,
            'tags': tags.values(),
            'comment_tag': comment_tag,
            'params': JSON_ENCODE(
                {
                    'id': id,
                    **({'bounds': changeset.bounds.bounds} if (changeset.bounds is not None) else {}),
                    'elements': elements,
                }
            ).decode(),
        },
    )
