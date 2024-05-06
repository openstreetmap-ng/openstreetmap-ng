from anyio import create_task_group
from fastapi import APIRouter, Response
from pydantic import PositiveInt
from starlette import status

from app.lib.auth_context import auth_user
from app.lib.elements_format import elements_format
from app.lib.render_response import render_response
from app.lib.statement_context import joinedload_context
from app.lib.tags_format import tags_format
from app.lib.translation import t
from app.models.db.changeset_comment import ChangesetComment
from app.models.tag_format import TagFormatCollection
from app.repositories.changeset_comment_repository import ChangesetCommentRepository
from app.repositories.changeset_repository import ChangesetRepository
from app.repositories.changeset_subscription_repository import ChangesetSubscriptionRepository
from app.repositories.element_repository import ElementRepository
from app.utils import JSON_ENCODE

router = APIRouter(prefix='/changeset')


@router.get('/{id:int}')
async def get_changeset(id: PositiveInt):
    changesets = await ChangesetRepository.find_many_by_query(changeset_ids=(id,), limit=1)
    changeset = changesets[0] if changesets else None

    if changeset is None:
        return render_response(
            'partial/not_found.jinja2',
            {'type': 'changeset', 'id': id},
        )

    elements = None
    prev_changeset_id: int | None = None
    next_changeset_id: int | None = None
    is_subscribed = False

    async def elements_task():
        nonlocal elements
        elements_ = await ElementRepository.get_many_by_changeset(id, sort_by_id=True)
        elements = await elements_format(elements_)

    async def comments_task():
        with joinedload_context(ChangesetComment.user):
            await ChangesetCommentRepository.resolve_comments(changesets, limit_per_changeset=None, rich_text=True)

    async def adjacent_ids_task():
        nonlocal prev_changeset_id, next_changeset_id
        t: tuple = await ChangesetRepository.get_adjacent_ids(id, user_id=changeset.user_id)
        prev_changeset_id = t[0]
        next_changeset_id = t[1]

    async def is_subscribed_task():
        nonlocal is_subscribed
        is_subscribed = await ChangesetSubscriptionRepository.is_subscribed_by_id(id)

    async with create_task_group() as tg:
        tg.start_soon(elements_task)
        tg.start_soon(comments_task)
        if changeset.user_id is not None:
            tg.start_soon(adjacent_ids_task)
        if auth_user() is not None:
            tg.start_soon(is_subscribed_task)

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
