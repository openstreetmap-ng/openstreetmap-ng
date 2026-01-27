from asyncio import TaskGroup
from typing import Annotated

import cython
from fastapi import APIRouter, Query
from starlette import status
from starlette.responses import RedirectResponse

from app.config import (
    APP_URL,
    MESSAGE_BODY_MAX_LENGTH,
    MESSAGE_SUBJECT_MAX_LENGTH,
)
from app.lib.auth_context import web_user
from app.lib.date_utils import format_sql_date
from app.lib.exceptions_context import raise_for
from app.lib.render_response import render_response
from app.lib.translation import t
from app.models.db.user import User
from app.models.types import DiaryCommentId, DiaryId, MessageId, UserId
from app.queries.diary_comment_query import DiaryCommentQuery
from app.queries.diary_query import DiaryQuery
from app.queries.message_query import MessageQuery
from app.queries.user_query import UserQuery
from app.validators.display_name import DisplayNameNormalizing

router = APIRouter()


@router.get('/messages/inbox')
async def get_inbox(
    _: Annotated[User, web_user()],
):
    return await render_response('messages/index', {'inbox': True})


@router.get('/messages/outbox')
async def get_outbox(
    _: Annotated[User, web_user()],
):
    return await render_response('messages/index', {'inbox': False})


@router.get('/message/new')
async def new_message(
    user: Annotated[User, web_user()],
    to: Annotated[DisplayNameNormalizing | None, Query(min_length=1)] = None,
    to_id: Annotated[UserId | None, Query()] = None,
    reply: Annotated[MessageId | None, Query()] = None,
    reply_all: Annotated[MessageId | None, Query()] = None,
    reply_diary: Annotated[DiaryId | None, Query()] = None,
    reply_diary_comment: Annotated[DiaryCommentId | None, Query()] = None,
):
    recipients: str | None = None
    subject: str = ''
    body: str = ''

    if reply is not None or reply_all is not None:
        reply_message = await MessageQuery.get_by_id(reply or reply_all)  # type: ignore
        assert 'recipients' in reply_message, 'Message recipients must be set'

        async with TaskGroup() as tg:
            tg.create_task(
                UserQuery.resolve_users(
                    [reply_message], user_id_key='from_user_id', user_key='from_user'
                )
            )
            tg.create_task(UserQuery.resolve_users(reply_message['recipients']))

        from_user = reply_message['from_user']  # pyright: ignore [reportTypedDictNotRequiredAccess]
        is_sender: cython.bint = from_user['id'] == user['id']
        other_users = [from_user] if not is_sender else []
        other_users.extend(
            r['user']  # pyright: ignore [reportTypedDictNotRequiredAccess]
            for r in reply_message['recipients']
            if r['user_id'] != user['id'] and not r['hidden']
        )

        recipients = (
            next(iter(u['display_name'] for u in other_users))
            if reply is not None and not is_sender
            else ','.join(u['display_name'] for u in other_users)
        )
        subject = f'{t("messages.compose.reply.prefix")}: {reply_message["subject"]}'
        reply_header_date = format_sql_date(reply_message['created_at'])
        reply_header_user = f'[{from_user["display_name"]}]({APP_URL}/user-id/{reply_message["from_user_id"]})'
        reply_header = t(
            'messages.compose.reply.header',
            date=reply_header_date,
            user=reply_header_user,
        )
        body = '\n'.join((
            f'\n\n\n{reply_header}:\n',
            *(f'> {line}' for line in reply_message['body'].splitlines()),
        ))

    elif reply_diary is not None:
        diary = await DiaryQuery.find_by_id(reply_diary)
        if diary is None:
            raise_for.diary_not_found(reply_diary)

        await UserQuery.resolve_users([diary])

        recipients = diary['user']['display_name']  # pyright: ignore [reportTypedDictNotRequiredAccess]
        subject = f'{t("messages.compose.reply.prefix")}: {diary["title"]}'

    elif reply_diary_comment is not None:
        diary_comment = await DiaryCommentQuery.find_by_id(reply_diary_comment)
        if diary_comment is None:
            raise_for.diary_comment_not_found(reply_diary_comment)

        async with TaskGroup() as tg:
            tg.create_task(UserQuery.resolve_users([diary_comment]))
            diary = await DiaryQuery.find_by_id(diary_comment['diary_id'])
            assert diary is not None, (
                f'Parent diary {diary_comment["diary_id"]!r} must exist'
            )

        recipients = diary_comment['user']['display_name']  # pyright: ignore [reportTypedDictNotRequiredAccess]
        subject = f'{t("messages.compose.reply.prefix")}: {diary["title"]}'

    elif to_id is not None:
        recipient_user = await UserQuery.find_by_id(to_id)
        if recipient_user is None:
            raise_for.user_not_found(to_id)
        recipients = recipient_user['display_name']

    elif to is not None:
        recipient_user = await UserQuery.find_by_display_name(to)
        if recipient_user is None:
            raise_for.user_not_found(to)
        recipients = to

    return await render_response(
        'messages/new',
        {
            'recipients': recipients,
            'subject': subject,
            'body': body,
            'MESSAGE_SUBJECT_MAX_LENGTH': MESSAGE_SUBJECT_MAX_LENGTH,
            'MESSAGE_BODY_MAX_LENGTH': MESSAGE_BODY_MAX_LENGTH,
        },
    )


@router.get('/message/new/{display_name:str}')
async def legacy_message_to(display_name: DisplayNameNormalizing):
    return RedirectResponse(f'/message/new?to={display_name}', status.HTTP_302_FOUND)


@router.get('/messages/{message_id:int}')
async def legacy_message(message_id: MessageId):
    return RedirectResponse(f'/messages/inbox?show={message_id}', status.HTTP_302_FOUND)


@router.get('/messages/{message_id:int}/reply')
async def legacy_message_reply(message_id: MessageId):
    return RedirectResponse(f'/message/new?reply={message_id}', status.HTTP_302_FOUND)
