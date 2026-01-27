from asyncio import TaskGroup
from typing import override

import cython
from connectrpc.request import RequestContext
from psycopg.sql import SQL

from app.config import MESSAGES_INBOX_PAGE_SIZE
from app.lib.auth_context import require_web_user
from app.lib.standard_pagination import sp_paginate_table
from app.models.db.message import Message
from app.models.db.user import user_proto
from app.models.proto.message_connect import (
    MessageService,
    MessageServiceASGIApplication,
)
from app.models.proto.message_pb2 import (
    GetMessagesPageRequest,
    GetMessagesPageResponse,
)
from app.queries.message_query import MessageQuery
from app.queries.user_query import UserQuery


class _Service(MessageService):
    @override
    async def get_messages_page(
        self, request: GetMessagesPageRequest, ctx: RequestContext
    ):
        user_id = require_web_user()['id']

        inbox = request.inbox
        sp_state = request.state.SerializeToString()
        if inbox:
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
                sp_state,
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

        summaries = [
            _build_message_summary(message, inbox=inbox) for message in messages
        ]
        return GetMessagesPageResponse(state=state, messages=summaries)


def _build_message_summary(
    message: Message,
    *,
    inbox: bool,
):
    if inbox:
        return GetMessagesPageResponse.Summary(
            id=message['id'],
            sender=user_proto(message['from_user']),  # type: ignore
            recipients=[],
            recipients_count=0,
            unread=not message['user_recipient']['read'],  # type: ignore
            created_at=int(message['created_at'].timestamp()),
            subject=message['subject'],
            body_preview=_message_body_preview(message['body']),
        )

    recipients = message['recipients']  # type: ignore
    recipients_users = [
        user_proto(r_user)
        for r in recipients[:3]
        if (r_user := r.get('user')) is not None
    ]
    return GetMessagesPageResponse.Summary(
        id=message['id'],
        sender=None,
        recipients=recipients_users,
        recipients_count=len(recipients),
        unread=False,
        created_at=int(message['created_at'].timestamp()),
        subject=message['subject'],
        body_preview=_message_body_preview(message['body']),
    )


def _message_body_preview(value: str, *, _PREVIEW_SIZE: cython.size_t = 250):
    if len(value) <= _PREVIEW_SIZE:
        return value
    trimmed = value[: _PREVIEW_SIZE - 3].rstrip()
    return f'{trimmed}...'


service = _Service()
asgi_app_cls = MessageServiceASGIApplication
