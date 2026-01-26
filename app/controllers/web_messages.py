from asyncio import TaskGroup
from typing import Annotated

from fastapi import APIRouter, Form, Response
from psycopg.sql import SQL
from starlette import status

from app.config import (
    MESSAGE_BODY_MAX_LENGTH,
    MESSAGE_SUBJECT_MAX_LENGTH,
    MESSAGES_INBOX_PAGE_SIZE,
)
from app.lib.auth_context import web_user
from app.lib.standard_pagination import (
    StandardPaginationStateBody,
    sp_paginate_table,
    sp_render_response_bytes,
)
from app.models.db.message import Message, messages_resolve_rich_text
from app.models.db.user import User, user_proto
from app.models.proto.shared_pb2 import MessagePage, MessageRead
from app.models.types import MessageId
from app.queries.message_query import MessageQuery
from app.queries.user_query import UserQuery
from app.services.message_service import MessageService
from app.validators.display_name import DisplayNameNormalizing

router = APIRouter(prefix='/api/web/messages')

_MESSAGE_BODY_PREVIEW_MAX = 250


@router.post('')
async def send_message(
    _: Annotated[User, web_user()],
    subject: Annotated[str, Form(min_length=1, max_length=MESSAGE_SUBJECT_MAX_LENGTH)],
    body: Annotated[str, Form(min_length=1, max_length=MESSAGE_BODY_MAX_LENGTH)],
    recipient: Annotated[list[DisplayNameNormalizing], Form(min_length=1)],
):
    message_id = await MessageService.send(
        recipients=list(set(recipient)),
        subject=subject,
        body=body,
    )
    return {'redirect_url': f'/messages/outbox?show={message_id}'}


@router.get('/{message_id:int}')
async def read_message(
    user: Annotated[User, web_user()],
    message_id: MessageId,
):
    message = await MessageQuery.get_by_id(message_id)
    assert 'recipients' in message, 'Message recipients must be set'

    user_recipient = message.get('user_recipient')
    is_recipient = user_recipient is not None

    async with TaskGroup() as tg:
        items = [message]
        tg.create_task(messages_resolve_rich_text(items))
        tg.create_task(
            UserQuery.resolve_users(
                items, user_id_key='from_user_id', user_key='from_user'
            )
        )
        tg.create_task(UserQuery.resolve_users(message['recipients']))

        was_unread = (
            await MessageService.set_state(message_id, read=True)
            if is_recipient
            else False
        )

    result = MessageRead(
        was_unread=was_unread,
        sender=user_proto(message['from_user']),  # type: ignore
        recipients=[
            user_proto(r['user'])  # type: ignore
            for r in message['recipients']
        ],
        is_recipient=is_recipient,
        time=int(message['created_at'].timestamp()),
        subject=message['subject'],
        body_rich=message['body_rich'],  # type: ignore
    )
    return Response(result.SerializeToString(), media_type='application/x-protobuf')


@router.post('/{message_id:int}/unread')
async def unread_message(
    _: Annotated[User, web_user()],
    message_id: MessageId,
):
    await MessageService.set_state(message_id, read=False)
    return Response(None, status.HTTP_204_NO_CONTENT)


@router.post('/{message_id:int}/delete')
async def delete_message(
    _: Annotated[User, web_user()],
    message_id: MessageId,
):
    await MessageService.delete_message(message_id)
    return Response(None, status.HTTP_204_NO_CONTENT)


@router.post('/inbox')
async def inbox_page(
    user: Annotated[User, web_user()],
    sp_state: StandardPaginationStateBody = b'',
):
    messages, state = await sp_paginate_table(
        Message,
        sp_state,
        table='message',
        where=SQL("""
            EXISTS (
                SELECT 1 FROM message_recipient
                WHERE message_id = id
                  AND user_id = %s
                  AND NOT hidden
            )
        """),
        params=(user['id'],),
        page_size=MESSAGES_INBOX_PAGE_SIZE,
        cursor_column='id',
        cursor_kind='id',
        order_dir='desc',
    )

    async with TaskGroup() as tg:
        tg.create_task(MessageQuery.resolve_recipients(user['id'], messages))
        tg.create_task(
            UserQuery.resolve_users(
                messages, user_id_key='from_user_id', user_key='from_user'
            )
        )

    summaries = [_build_message_summary(message, inbox=True) for message in messages]

    payload = MessagePage(messages=summaries)
    return sp_render_response_bytes(payload.SerializeToString(), state)


@router.post('/outbox')
async def outbox_page(
    user: Annotated[User, web_user()],
    sp_state: StandardPaginationStateBody = b'',
):
    messages, state = await sp_paginate_table(
        Message,
        sp_state,
        table='message',
        where=SQL('from_user_id = %s AND NOT from_user_hidden'),
        params=(user['id'],),
        page_size=MESSAGES_INBOX_PAGE_SIZE,
        cursor_column='id',
        cursor_kind='id',
        order_dir='desc',
    )

    await MessageQuery.resolve_recipients(None, messages)
    await UserQuery.resolve_users([
        r
        for m in messages
        for r in m['recipients']  # type: ignore
    ])

    summaries = [_build_message_summary(message, inbox=False) for message in messages]

    payload = MessagePage(messages=summaries)
    return sp_render_response_bytes(payload.SerializeToString(), state)


def _build_message_summary(
    message: Message,
    *,
    inbox: bool,
):
    if inbox:
        return MessagePage.Summary(
            id=message['id'],
            sender=user_proto(message['from_user']),  # type: ignore
            recipients=[],
            recipients_count=0,
            unread=not message['user_recipient']['read'],  # type: ignore
            time=int(message['created_at'].timestamp()),
            subject=message['subject'],
            body_preview=_message_body_preview(message['body']),
        )

    recipients = message['recipients']  # type: ignore
    recipients_users = [
        user_proto(r_user)
        for r in recipients[:3]
        if (r_user := r.get('user')) is not None
    ]
    return MessagePage.Summary(
        id=message['id'],
        sender=None,
        recipients=recipients_users,
        recipients_count=len(recipients),
        unread=False,
        time=int(message['created_at'].timestamp()),
        subject=message['subject'],
        body_preview=_message_body_preview(message['body']),
    )


def _message_body_preview(value: str):
    if len(value) <= _MESSAGE_BODY_PREVIEW_MAX:
        return value
    trimmed = value[: _MESSAGE_BODY_PREVIEW_MAX - 3].rstrip()
    return f'{trimmed}...'
