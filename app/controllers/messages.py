from asyncio import TaskGroup
from typing import Annotated

import cython
from fastapi import APIRouter, Query
from starlette import status
from starlette.responses import RedirectResponse

from app.config import APP_URL
from app.lib.auth_context import web_user
from app.lib.date_utils import format_sql_date
from app.lib.exceptions_context import raise_for
from app.lib.render_response import render_response
from app.lib.translation import t
from app.limits import (
    MESSAGE_BODY_MAX_LENGTH,
    MESSAGE_SUBJECT_MAX_LENGTH,
    MESSAGES_INBOX_PAGE_SIZE,
)
from app.models.db.user import User
from app.models.types import DiaryCommentId, DiaryId, DisplayName, MessageId, UserId
from app.queries.diary_comment_query import DiaryCommentQuery
from app.queries.diary_query import DiaryQuery
from app.queries.message_query import MessageQuery
from app.queries.user_query import UserQuery

router = APIRouter()


@router.get('/messages/inbox')
async def get_inbox(
    _: Annotated[User, web_user()],
    show: Annotated[MessageId | None, Query()] = None,
    after: Annotated[MessageId | None, Query()] = None,
    before: Annotated[MessageId | None, Query()] = None,
):
    data = await _get_messages_data(inbox=True, show=show, after=after, before=before)
    return await render_response('messages/index.jinja2', data)


@router.get('/messages/outbox')
async def get_outbox(
    _: Annotated[User, web_user()],
    show: Annotated[MessageId | None, Query()] = None,
    after: Annotated[MessageId | None, Query()] = None,
    before: Annotated[MessageId | None, Query()] = None,
):
    data = await _get_messages_data(inbox=False, show=show, after=after, before=before)
    return await render_response('messages/index.jinja2', data)


@router.get('/message/new')
async def new_message(
    user: Annotated[User, web_user()],
    to: Annotated[DisplayName | None, Query(min_length=1)] = None,
    to_id: Annotated[UserId | None, Query()] = None,
    reply: Annotated[MessageId | None, Query()] = None,
    reply_diary: Annotated[DiaryId | None, Query()] = None,
    reply_diary_comment: Annotated[DiaryCommentId | None, Query()] = None,
):
    recipient: DisplayName | None = None
    recipient_id: int | None = None
    subject: str = ''
    body: str = ''

    if reply is not None:
        reply_message = await MessageQuery.get_message_by_id(reply)
        is_recipient: cython.bint = reply_message['to_user_id'] == user['id']

        async with TaskGroup() as tg:
            items = [reply_message]
            tg.create_task(UserQuery.resolve_users(items, user_id_key='from_user_id', user_key='from_user'))
            if not is_recipient:
                tg.create_task(UserQuery.resolve_users(items, user_id_key='to_user_id', user_key='to_user'))

        from_user = reply_message['from_user']  # pyright: ignore [reportTypedDictNotRequiredAccess]
        other_user = from_user if is_recipient else reply_message['to_user']  # pyright: ignore [reportTypedDictNotRequiredAccess]

        recipient = other_user['display_name']
        recipient_id = other_user['id']
        subject = f'{t("messages.compose.reply.prefix")}: {reply_message["subject"]}'
        reply_header_date = format_sql_date(reply_message['created_at'])
        reply_header_user = f'[{from_user["display_name"]}]({APP_URL}/user-id/{reply_message["from_user_id"]})'
        reply_header = t('messages.compose.reply.header', date=reply_header_date, user=reply_header_user)
        body = '\n'.join((f'\n\n\n{reply_header}:\n', *(f'> {line}' for line in reply_message['body'].splitlines())))

    elif reply_diary is not None:
        diary = await DiaryQuery.find_one_by_id(reply_diary)
        if diary is None:
            raise_for.diary_not_found(reply_diary)

        await UserQuery.resolve_users([diary])

        recipient = diary['user']['display_name']  # pyright: ignore [reportTypedDictNotRequiredAccess]
        recipient_id = diary['user_id']
        subject = f'{t("messages.compose.reply.prefix")}: {diary["title"]}'

    elif reply_diary_comment is not None:
        diary_comment = await DiaryCommentQuery.find_one_by_id(reply_diary_comment)
        if diary_comment is None:
            raise_for.diary_comment_not_found(reply_diary_comment)

        async with TaskGroup() as tg:
            tg.create_task(UserQuery.resolve_users([diary_comment]))
            diary = await DiaryQuery.find_one_by_id(diary_comment['diary_id'])
            assert diary is not None, f'Parent diary {diary_comment["diary_id"]!r} must exist'

        recipient = diary_comment['user']['display_name']  # pyright: ignore [reportTypedDictNotRequiredAccess]
        recipient_id = diary_comment['user_id']
        subject = f'{t("messages.compose.reply.prefix")}: {diary["title"]}'

    elif to_id is not None:
        recipient_user = await UserQuery.find_one_by_id(to_id)
        if recipient_user is None:
            raise_for.user_not_found(to_id)
        recipient = recipient_user['display_name']
        recipient_id = to_id

    elif to is not None:
        recipient_user = await UserQuery.find_one_by_display_name(to)
        if recipient_user is None:
            raise_for.user_not_found(to)
        recipient = to
        recipient_id = recipient_user['id']

    return await render_response(
        'messages/new.jinja2',
        {
            'recipient': recipient,
            'recipient_id': recipient_id,
            'subject': subject,
            'body': body,
            'MESSAGE_SUBJECT_MAX_LENGTH': MESSAGE_SUBJECT_MAX_LENGTH,
            'MESSAGE_BODY_MAX_LENGTH': MESSAGE_BODY_MAX_LENGTH,
        },
    )


@router.get('/message/new/{display_name:str}')
async def legacy_message_to(display_name: DisplayName):
    return RedirectResponse(f'/message/new?to={display_name}', status.HTTP_302_FOUND)


@router.get('/messages/{message_id:int}')
async def legacy_message(message_id: MessageId):
    return RedirectResponse(f'/messages/inbox?show={message_id}', status.HTTP_302_FOUND)


@router.get('/messages/{message_id:int}/reply')
async def legacy_message_reply(message_id: MessageId):
    return RedirectResponse(f'/message/new?reply={message_id}', status.HTTP_302_FOUND)


async def _get_messages_data(
    inbox: bool,
    show: MessageId | None,
    after: MessageId | None,
    before: MessageId | None,
) -> dict:
    if (show is not None) and (after is None) and (before is None):
        before = show + 1  # type: ignore

    messages = await MessageQuery.get_messages(
        inbox=inbox,
        after=after,
        before=before,
        limit=MESSAGES_INBOX_PAGE_SIZE,
    )

    async def new_after_task():
        after = messages[0]['id']
        after_messages = await MessageQuery.get_messages(
            inbox=inbox,
            after=after,
            limit=1,
        )
        return after if after_messages else None

    async def new_before_task():
        before = messages[-1]['id']
        before_messages = await MessageQuery.get_messages(
            inbox=inbox,
            before=before,
            limit=1,
        )
        return before if before_messages else None

    async with TaskGroup() as tg:
        if inbox:
            user_id_key = 'from_user_id'
            user_key = 'from_user'
        else:
            user_id_key = 'to_user_id'
            user_key = 'to_user'
        tg.create_task(UserQuery.resolve_users(messages, user_id_key=user_id_key, user_key=user_key))

        if messages:
            new_after_t = tg.create_task(new_after_task())
            new_before_t = tg.create_task(new_before_task())
            new_after, new_before = await new_after_t, await new_before_t
            current_before = messages[0]['id'] + 1
        else:
            new_after, new_before = None, None
            current_before = None

    return {
        'inbox': inbox,
        'new_after': new_after,
        'new_before': new_before,
        'current_before': current_before,
        'messages': messages,
        'active_message_id': show,
    }
