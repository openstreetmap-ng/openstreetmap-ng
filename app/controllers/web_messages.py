from asyncio import TaskGroup
from typing import Annotated

from fastapi import APIRouter, Form, Response
from starlette import status

from app.config import (
    MESSAGE_BODY_MAX_LENGTH,
    MESSAGE_SUBJECT_MAX_LENGTH,
)
from app.lib.auth_context import web_user
from app.models.db.message import messages_resolve_rich_text
from app.models.db.user import User, user_proto
from app.models.proto.message_pb2 import MessageRead
from app.models.types import MessageId
from app.queries.message_query import MessageQuery
from app.queries.user_query import UserQuery
from app.services.message_service import MessageService
from app.validators.display_name import DisplayNameNormalizing

router = APIRouter(prefix='/api/web/messages')


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
        created_at=int(message['created_at'].timestamp()),
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
