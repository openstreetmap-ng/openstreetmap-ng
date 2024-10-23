from asyncio import TaskGroup
from typing import Annotated

from fastapi import APIRouter, Query
from pydantic import PositiveInt
from sqlalchemy.orm import joinedload

from app.lib.auth_context import web_user
from app.lib.options_context import options_context
from app.lib.render_response import render_response
from app.limits import MESSAGES_INBOX_PAGE_SIZE
from app.models.db.message import Message
from app.models.db.user import User
from app.queries.message_query import MessageQuery

router = APIRouter(prefix='/messages')


# TODO: show argument


async def _get_messages_data(
    inbox: bool,
    after: int | None,
    before: int | None,
) -> dict:
    with options_context(
        joinedload(Message.from_user).load_only(
            User.id,
            User.display_name,
            User.avatar_type,
            User.avatar_id,
        )
    ):
        messages = await MessageQuery.get_messages(
            inbox=inbox,
            after=after,
            before=before,
            limit=MESSAGES_INBOX_PAGE_SIZE,
        )

    async def new_after_task():
        after = messages[0].id
        after_messages = await MessageQuery.get_messages(
            inbox=inbox,
            after=after,
            limit=1,
        )
        return after if after_messages else None

    async def new_before_task():
        before = messages[-1].id
        before_messages = await MessageQuery.get_messages(
            inbox=inbox,
            before=before,
            limit=1,
        )
        return before if before_messages else None

    if messages:
        async with TaskGroup() as tg:
            new_after_t = tg.create_task(new_after_task())
            new_before_t = tg.create_task(new_before_task())
        new_after = new_after_t.result()
        new_before = new_before_t.result()
    else:
        new_after = None
        new_before = None

    return {
        'inbox': inbox,
        'new_after': new_after,
        'new_before': new_before,
        'messages': messages,
    }


@router.get('/inbox')
async def inbox(
    _: Annotated[User, web_user()],
    after: Annotated[PositiveInt | None, Query()] = None,
    before: Annotated[PositiveInt | None, Query()] = None,
):
    data = await _get_messages_data(inbox=True, after=after, before=before)
    return render_response('messages/index.jinja2', data)


@router.get('/outbox')
async def outbox(
    _: Annotated[User, web_user()],
    after: Annotated[PositiveInt | None, Query()] = None,
    before: Annotated[PositiveInt | None, Query()] = None,
):
    data = await _get_messages_data(inbox=False, after=after, before=before)
    return render_response('messages/index.jinja2', data)
