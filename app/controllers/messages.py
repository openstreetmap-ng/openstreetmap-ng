from asyncio import TaskGroup
from itertools import chain
from typing import Annotated

from fastapi import APIRouter, Query
from pydantic import PositiveInt
from sqlalchemy.orm import joinedload
from starlette import status
from starlette.responses import RedirectResponse

from app.config import APP_URL
from app.lib.auth_context import web_user
from app.lib.date_utils import format_sql_date
from app.lib.exceptions_context import raise_for
from app.lib.options_context import options_context
from app.lib.render_response import render_response
from app.lib.translation import t
from app.limits import (
    DISPLAY_NAME_MAX_LENGTH,
    MESSAGE_BODY_MAX_LENGTH,
    MESSAGE_SUBJECT_MAX_LENGTH,
    MESSAGES_INBOX_PAGE_SIZE,
)
from app.models.db.diary import Diary
from app.models.db.message import Message
from app.models.db.user import User
from app.models.types import DisplayNameType
from app.queries.diary_query import DiaryQuery
from app.queries.message_query import MessageQuery
from app.queries.user_query import UserQuery

router = APIRouter()


async def _get_messages_data(
    inbox: bool,
    show: int | None,
    after: int | None,
    before: int | None,
) -> dict:
    if (show is not None) and (after is None) and (before is None):
        before = show + 1

    with options_context(
        joinedload(Message.from_user if inbox else Message.to_user).load_only(
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
        current_before = messages[0].id + 1
    else:
        new_after = None
        new_before = None
        current_before = None

    return {
        'inbox': inbox,
        'new_after': new_after,
        'new_before': new_before,
        'current_before': current_before,
        'messages': messages,
        'active_message_id': show,
    }


@router.get('/messages/inbox')
async def inbox(
    _: Annotated[User, web_user()],
    show: Annotated[PositiveInt | None, Query()] = None,
    after: Annotated[PositiveInt | None, Query()] = None,
    before: Annotated[PositiveInt | None, Query()] = None,
):
    data = await _get_messages_data(inbox=True, show=show, after=after, before=before)
    return await render_response('messages/index.jinja2', data)


@router.get('/messages/outbox')
async def outbox(
    _: Annotated[User, web_user()],
    show: Annotated[PositiveInt | None, Query()] = None,
    after: Annotated[PositiveInt | None, Query()] = None,
    before: Annotated[PositiveInt | None, Query()] = None,
):
    data = await _get_messages_data(inbox=False, show=show, after=after, before=before)
    return await render_response('messages/index.jinja2', data)


@router.get('/message/new')
async def new_message(
    user: Annotated[User, web_user()],
    to: Annotated[DisplayNameType | None, Query(min_length=1, max_length=DISPLAY_NAME_MAX_LENGTH)] = None,
    to_id: Annotated[PositiveInt | None, Query()] = None,
    reply: Annotated[PositiveInt | None, Query()] = None,
    reply_diary: Annotated[PositiveInt | None, Query()] = None,
):
    recipient: DisplayNameType | None = None
    recipient_id: int | None = None
    subject: str = ''
    body: str = ''
    if reply is not None:
        with options_context(
            joinedload(Message.from_user).load_only(User.id, User.display_name),
            joinedload(Message.to_user).load_only(User.id, User.display_name),
        ):
            reply_message = await MessageQuery.get_message_by_id(reply)
        other_user = reply_message.from_user if reply_message.to_user_id == user.id else reply_message.to_user
        recipient = other_user.display_name
        recipient_id = other_user.id
        subject = f'{t("messages.compose.reply.prefix")}: {reply_message.subject}'
        reply_header_date = format_sql_date(reply_message.created_at)
        reply_header_user = f'[{reply_message.from_user.display_name}]({APP_URL}/user-id/{reply_message.from_user_id})'
        reply_header = t('messages.compose.reply.header', date=reply_header_date, user=reply_header_user)
        body = '\n'.join(
            chain(
                (f'\n\n\n{reply_header}:\n',),
                (f'> {line}' for line in reply_message.body.splitlines()),
            )
        )
    elif reply_diary is not None:
        with options_context(joinedload(Diary.user).load_only(User.display_name)):
            diary = await DiaryQuery.find_one_by_id(reply_diary)
        if diary is None:
            raise_for.diary_not_found(reply_diary)
        recipient = diary.user.display_name
        recipient_id = diary.user_id
        subject = f'{t("messages.compose.reply.prefix")}: {diary.title}'
    elif to_id is not None:
        recipient_user = await UserQuery.find_one_by_id(to_id)
        if recipient_user is None:
            raise_for.user_not_found(to_id)
        recipient = recipient_user.display_name
        recipient_id = to_id
    elif to is not None:
        recipient_user = await UserQuery.find_one_by_display_name(to)
        if recipient_user is None:
            raise_for.user_not_found(to)
        recipient = to
        recipient_id = recipient_user.id
    return await render_response(
        'messages/new.jinja2',
        {
            'recipient': recipient,
            'recipient_id': recipient_id,
            'subject': subject,
            'body': body,
            'DISPLAY_NAME_MAX_LENGTH': DISPLAY_NAME_MAX_LENGTH,
            'MESSAGE_SUBJECT_MAX_LENGTH': MESSAGE_SUBJECT_MAX_LENGTH,
            'MESSAGE_BODY_MAX_LENGTH': MESSAGE_BODY_MAX_LENGTH,
        },
    )


@router.get('/message/new/{display_name:str}')
async def legacy_message_to(display_name: DisplayNameType):
    return RedirectResponse(f'/message/new?to={display_name}', status.HTTP_302_FOUND)


@router.get('/messages/{message_id:int}')
async def legacy_message(message_id: PositiveInt):
    return RedirectResponse(f'/messages/inbox?show={message_id}', status.HTTP_302_FOUND)


@router.get('/messages/{message_id:int}/reply')
async def legacy_message_reply(message_id: PositiveInt):
    return RedirectResponse(f'/message/new?reply={message_id}', status.HTTP_302_FOUND)
