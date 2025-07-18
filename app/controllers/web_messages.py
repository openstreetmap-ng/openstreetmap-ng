from asyncio import TaskGroup
from typing import Annotated

from fastapi import APIRouter, Form, Response
from starlette import status

from app.config import MESSAGE_BODY_MAX_LENGTH, MESSAGE_SUBJECT_MAX_LENGTH
from app.lib.auth_context import web_user
from app.models.db.message import messages_resolve_rich_text
from app.models.db.user import User, user_avatar_url
from app.models.types import DisplayName, MessageId
from app.queries.message_query import MessageQuery
from app.queries.user_query import UserQuery
from app.services.message_service import MessageService

router = APIRouter(prefix='/api/web/messages')


@router.post('/')
async def send_message(
    _: Annotated[User, web_user()],
    subject: Annotated[str, Form(min_length=1, max_length=MESSAGE_SUBJECT_MAX_LENGTH)],
    body: Annotated[str, Form(min_length=1, max_length=MESSAGE_BODY_MAX_LENGTH)],
    recipient: Annotated[list[DisplayName], Form(min_length=1)],
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
    message = await MessageQuery.get_message_by_id(message_id)
    assert 'recipients' in message, 'Message recipients must be set'

    async with TaskGroup() as tg:
        items = [message]
        tg.create_task(messages_resolve_rich_text(items))
        tg.create_task(
            UserQuery.resolve_users(
                items, user_id_key='from_user_id', user_key='from_user'
            )
        )
        tg.create_task(UserQuery.resolve_users(message['recipients']))

        if (
            message['from_user_id'] != user['id']
            and not next(
                iter(
                    r  #
                    for r in message['recipients']
                    if r['user_id'] == user['id']
                )
            )['read']
        ):
            tg.create_task(MessageService.set_state(message_id, read=True))

    from_user = message['from_user']  # pyright: ignore [reportTypedDictNotRequiredAccess]
    time_html = f'<time datetime="{message["created_at"].isoformat()}" data-date="long" data-time="short"></time>'

    return {
        'sender': {
            'display_name': from_user['display_name'],
            'avatar_url': user_avatar_url(from_user),
        },
        'recipients': [
            {
                'display_name': r['user']['display_name'],  # pyright: ignore [reportTypedDictNotRequiredAccess]
                'avatar_url': user_avatar_url(r['user']),  # pyright: ignore [reportTypedDictNotRequiredAccess]
            }
            for r in message['recipients']
        ],
        'time': time_html,
        'subject': message['subject'],
        'body_rich': message['body_rich'],  # pyright: ignore [reportTypedDictNotRequiredAccess]
    }


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
