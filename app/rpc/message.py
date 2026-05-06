from asyncio import TaskGroup
from typing import override

import cython
from connectrpc.request import RequestContext
from psycopg.sql import SQL

from app.config import MESSAGES_INBOX_PAGE_SIZE
from app.lib.auth_context import require_web_user
from app.lib.standard_pagination import sp_paginate_table
from app.models.db.message import Message, messages_resolve_rich_text
from app.models.db.user import user_proto
from app.models.proto.message_connect import (
    Service as MessageServiceConnect,
)
from app.models.proto.message_connect import ServiceASGIApplication
from app.models.proto.message_pb2 import (
    DeleteRequest,
    DeleteResponse,
    GetPageRequest,
    GetPageResponse,
    GetRequest,
    GetResponse,
    SendRequest,
    SendResponse,
    UpdateReadStateRequest,
    UpdateReadStateResponse,
)
from app.models.types import MessageId
from app.queries.message_query import MessageQuery
from app.queries.user_query import UserQuery
from app.services.message_service import MessageService
from app.validators.unicode import normalize_display_name


class _Service(MessageServiceConnect):
    @override
    async def get_page(self, request: GetPageRequest, ctx: RequestContext):
        user_id = require_web_user()['id']

        inbox = request.inbox
        if inbox:
            messages, state = await sp_paginate_table(
                Message,
                request.state,
                table='message',
                where=SQL("""
                    EXISTS (
                        SELECT 1 FROM message_recipient
                        WHERE message_id = id
                          AND user_id = %s
                          AND NOT hidden
                    )
                """),
                params=(user_id,),
                page_size=MESSAGES_INBOX_PAGE_SIZE,
                cursor_column='id',
                cursor_kind='id',
                order_dir='desc',
            )

            async with TaskGroup() as tg:
                tg.create_task(MessageQuery.resolve_recipients(user_id, messages))
                tg.create_task(
                    UserQuery.resolve_users(
                        messages, user_id_key='from_user_id', user_key='from_user'
                    )
                )

        else:
            messages, state = await sp_paginate_table(
                Message,
                request.state,
                table='message',
                where=SQL('from_user_id = %s AND NOT from_user_hidden'),
                params=(user_id,),
                page_size=MESSAGES_INBOX_PAGE_SIZE,
                cursor_column='id',
                cursor_kind='id',
                order_dir='desc',
            )

            await MessageQuery.resolve_recipients(None, messages)
            await UserQuery.resolve_users([
                r
                for m in messages
                for r in m['recipients']  # pyright: ignore [reportTypedDictNotRequiredAccess]
            ])

        response = GetPageResponse()
        response.state.CopyFrom(state)
        for message in messages:
            _build_message_summary(response.messages.add(), message, inbox=inbox)
        return response

    @override
    async def get(self, request: GetRequest, ctx: RequestContext):
        require_web_user()
        message_id = MessageId(request.id)

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
            mark_read_t = (
                tg.create_task(MessageService.set_state(message_id, read=True))
                if is_recipient
                else None
            )

        response = GetResponse(
            was_unread=mark_read_t.result() if mark_read_t else False,
            is_recipient=is_recipient,
            created_at=int(message['created_at'].timestamp()),
            subject=message['subject'],
            body_rich=message['body_rich'],  # type: ignore
        )
        response.sender.CopyFrom(user_proto(message['from_user']))  # type: ignore
        for recipient in message['recipients']:
            response.recipients.add().CopyFrom(user_proto(recipient['user']))  # type: ignore
        return response

    @override
    async def update_read_state(
        self, request: UpdateReadStateRequest, ctx: RequestContext
    ):
        require_web_user()
        updated = await MessageService.set_state(
            MessageId(request.id),
            read=request.read,
        )
        return UpdateReadStateResponse(updated=updated)

    @override
    async def delete(self, request: DeleteRequest, ctx: RequestContext):
        require_web_user()
        await MessageService.delete_message(MessageId(request.id))
        return DeleteResponse()

    @override
    async def send(self, request: SendRequest, ctx: RequestContext):
        require_web_user()
        recipients = list(
            dict.fromkeys(normalize_display_name(value) for value in request.recipient)
        )
        message_id = await MessageService.send(
            recipients=recipients,
            subject=request.subject,
            body=request.body,
        )
        return SendResponse(id=message_id)


def _build_message_summary(
    result: GetPageResponse.Summary,
    message: Message,
    *,
    inbox: bool,
):
    result.id = message['id']
    if inbox:
        result.sender.CopyFrom(user_proto(message['from_user']))  # type: ignore
        result.recipients_count = 0
        result.unread = not message['user_recipient']['read']  # type: ignore
        result.created_at = int(message['created_at'].timestamp())
        result.subject = message['subject']
        result.body_preview = _message_body_preview(message['body'])
        return

    recipients = message['recipients']  # type: ignore
    for recipient in recipients[:3]:
        result.recipients.add().CopyFrom(user_proto(recipient['user']))  # type: ignore
    result.recipients_count = len(recipients)
    result.unread = False
    result.created_at = int(message['created_at'].timestamp())
    result.subject = message['subject']
    result.body_preview = _message_body_preview(message['body'])


def _message_body_preview(value: str, *, _PREVIEW_SIZE: cython.size_t = 250):
    if len(value) <= _PREVIEW_SIZE:
        return value
    trimmed = value[: _PREVIEW_SIZE - 3].rstrip()
    return f'{trimmed}...'


service = _Service()
asgi_app_cls = ServiceASGIApplication
