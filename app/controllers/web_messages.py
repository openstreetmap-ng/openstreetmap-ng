from asyncio import TaskGroup
from typing import Annotated

from fastapi import APIRouter, Response
from pydantic import PositiveInt
from sqlalchemy.orm import joinedload

from app.lib.auth_context import web_user
from app.lib.date_utils import format_rfc2822_date
from app.lib.options_context import options_context
from app.models.db.message import Message
from app.models.db.user import User
from app.queries.message_query import MessageQuery
from app.services.message_service import MessageService

router = APIRouter(prefix='/api/web/messages')


@router.get('/{message_id:int}')
async def read_message(
    user: Annotated[User, web_user()],
    message_id: PositiveInt,
):
    with options_context(
        joinedload(Message.from_user).load_only(
            User.id,
            User.display_name,
            User.avatar_type,
            User.avatar_id,
        ),
        joinedload(Message.to_user).load_only(
            User.id,
            User.display_name,
            User.avatar_type,
            User.avatar_id,
        ),
    ):
        message = await MessageQuery.get_message_by_id(message_id)
    async with TaskGroup() as tg:
        tg.create_task(message.resolve_rich_text())
        if not message.is_read:
            tg.create_task(MessageService.set_state(message_id, is_read=True))
    other_user = message.from_user if message.to_user_id == user.id else message.to_user
    return {
        'user_display_name': other_user.display_name,
        'user_avatar_url': other_user.avatar_url,
        'time': format_rfc2822_date(message.created_at),
        'subject': message.subject,
        'body_rich': message.body_rich,
    }


@router.post('/{message_id:int}/unread')
async def unread_message(
    _: Annotated[User, web_user()],
    message_id: PositiveInt,
):
    await MessageService.set_state(message_id, is_read=False)
    return Response()


@router.post('/{message_id:int}/delete')
async def delete_message(
    _: Annotated[User, web_user()],
    message_id: PositiveInt,
):
    await MessageService.delete_message(message_id)
    return Response()
