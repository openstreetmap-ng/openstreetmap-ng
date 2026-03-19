from asyncio import TaskGroup
from typing import Annotated

from fastapi import APIRouter, Form, Query, Response
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
from app.models.db.user import User, UserDisplay, user_avatar_url
from app.models.proto.shared_pb2 import MessagePage, MessageRead
from app.models.types import MessageId
from app.queries.message_query import MessageQuery
from app.queries.user_query import UserQuery
from app.services.message_service import MessageService
from app.validators.display_name import DisplayNameNormalizing

router = APIRouter(prefix='/api/web/messages')

_MESSAGE_BODY_PREVIEW_MAX = 250


def _message_body_preview(value: str) -> str:
    if len(value) <= _MESSAGE_BODY_PREVIEW_MAX:
        return value
    trimmed = value[: _MESSAGE_BODY_PREVIEW_MAX - 3].rstrip()
    return f'{trimmed}...'


def _message_user_summary(user: UserDisplay) -> MessagePage.Summary.User:
    return MessagePage.Summary.User(
        display_name=user['display_name'],
        avatar_url=user_avatar_url(user),
    )


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

    user_recipient = (
        next((r for r in message['recipients'] if r['user_id'] == user['id']), None)
        if message['from_user_id'] != user['id']
        else None
    )

    async with TaskGroup() as tg:
        items = [message]
        tg.create_task(messages_resolve_rich_text(items))
        tg.create_task(
            UserQuery.resolve_users(
                items, user_id_key='from_user_id', user_key='from_user'
            )
        )
        tg.create_task(UserQuery.resolve_users(message['recipients']))

        # Only mark as read if user is recipient and message is unread
        if user_recipient is not None and not user_recipient['read']:
            tg.create_task(MessageService.set_state(message_id, read=True))

    from_user = message['from_user']  # type: ignore
    time_unix = int(message['created_at'].timestamp())

    result = MessageRead(
        sender=MessageRead.Sender(
            id=message['from_user_id'],
            display_name=from_user['display_name'],
            avatar_url=user_avatar_url(from_user),
        ),
        recipients=[
            MessageRead.Recipient(
                display_name=r['user']['display_name'],  # type: ignore
                avatar_url=user_avatar_url(r['user']),  # type: ignore
            )
            for r in message['recipients']
        ],
        is_recipient=user_recipient is not None,
        time=time_unix,
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


@router.post('/bulk/read')
async def bulk_mark_read(
    _: Annotated[User, web_user()],
    message_id: Annotated[list[int], Form(min_length=1)],
):
    await MessageService.bulk_set_state(
        [MessageId(mid) for mid in message_id], read=True
    )
    return Response(None, status.HTTP_204_NO_CONTENT)


@router.post('/bulk/unread')
async def bulk_mark_unread(
    _: Annotated[User, web_user()],
    message_id: Annotated[list[int], Form(min_length=1)],
):
    await MessageService.bulk_set_state(
        [MessageId(mid) for mid in message_id], read=False
    )
    return Response(None, status.HTTP_204_NO_CONTENT)


@router.post('/bulk/delete')
async def bulk_delete(
    _: Annotated[User, web_user()],
    message_id: Annotated[list[int], Form(min_length=1)],
):
    count = await MessageService.bulk_delete_messages(
        [MessageId(mid) for mid in message_id]
    )
    return {'deleted': count}


def _build_search_conditions(
    q: str | None,
    after: str | None,
    before: str | None,
) -> tuple[list[SQL], list[object]]:
    """Build additional WHERE conditions from search/filter parameters."""
    conditions: list[SQL] = []
    params: list[object] = []

    if q:
        conditions.append(SQL("""
            (subject ILIKE %s OR body ILIKE %s
             OR EXISTS (
                SELECT 1 FROM "user"
                WHERE "user".id = from_user_id
                AND "user".display_name ILIKE %s
             ))
        """))
        escaped = q.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
        pattern = f'%{escaped}%'
        params.extend((pattern, pattern, pattern))

    if after:
        conditions.append(SQL('created_at >= %s::timestamptz'))
        params.append(after)

    if before:
        conditions.append(SQL('created_at < %s::timestamptz'))
        params.append(before)

    return conditions, params


@router.post('/inbox')
async def inbox_page(
    user: Annotated[User, web_user()],
    q: Annotated[str | None, Query(max_length=200)] = None,
    after: Annotated[str | None, Query()] = None,
    before: Annotated[str | None, Query()] = None,
    sp_state: StandardPaginationStateBody = b'',
):
    base_conditions = [SQL("""
        EXISTS (
            SELECT 1 FROM message_recipient
            WHERE message_id = id
              AND user_id = %s
              AND NOT hidden
        )
    """)]
    base_params: list[object] = [user['id']]

    search_conditions, search_params = _build_search_conditions(q, after, before)
    all_conditions = base_conditions + search_conditions
    all_params = base_params + search_params

    messages, state = await sp_paginate_table(
        Message,
        sp_state,
        table='message',
        where=SQL(' AND ').join(all_conditions),
        params=tuple(all_params),
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

    summaries = []
    for message in messages:
        from_user = message['from_user']  # type: ignore
        user_recipient = message.get('user_recipient')
        summaries.append(
            MessagePage.Summary(
                id=message['id'],
                sender=_message_user_summary(from_user),
                unread=bool(user_recipient and not user_recipient['read']),
                time=int(message['created_at'].timestamp()),
                subject=message['subject'],
                body_preview=_message_body_preview(message['body']),
            )
        )

    payload = MessagePage(messages=summaries)
    return sp_render_response_bytes(payload.SerializeToString(), state)


@router.post('/outbox')
async def outbox_page(
    user: Annotated[User, web_user()],
    q: Annotated[str | None, Query(max_length=200)] = None,
    after: Annotated[str | None, Query()] = None,
    before: Annotated[str | None, Query()] = None,
    sp_state: StandardPaginationStateBody = b'',
):
    base_conditions = [SQL('from_user_id = %s AND NOT from_user_hidden')]
    base_params: list[object] = [user['id']]

    search_conditions, search_params = _build_search_conditions(q, after, before)
    all_conditions = base_conditions + search_conditions
    all_params = base_params + search_params

    messages, state = await sp_paginate_table(
        Message,
        sp_state,
        table='message',
        where=SQL(' AND ').join(all_conditions),
        params=tuple(all_params),
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

    summaries = []
    for message in messages:
        recipients = message['recipients']  # type: ignore
        summaries.append(
            MessagePage.Summary(
                id=message['id'],
                recipients=[_message_user_summary(r['user']) for r in recipients[:3]],  # type: ignore
                recipients_count=len(recipients),
                unread=False,
                time=int(message['created_at'].timestamp()),
                subject=message['subject'],
                body_preview=_message_body_preview(message['body']),
            )
        )

    payload = MessagePage(messages=summaries)
    return sp_render_response_bytes(payload.SerializeToString(), state)
