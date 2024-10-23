from asyncio import TaskGroup
from typing import Annotated

from fastapi import APIRouter, Response
from pydantic import PositiveInt

from app.lib.auth_context import web_user
from app.models.db.user import User
from app.queries.message_query import MessageQuery
from app.services.message_service import MessageService

router = APIRouter(prefix='/api/web/messages')


@router.get('/{message_id:int}')
async def read_message(
    _: Annotated[User, web_user()],
    message_id: PositiveInt,
):
    message = await MessageQuery.get_message_by_id(message_id)
    async with TaskGroup() as tg:
        tg.create_task(message.resolve_rich_text())
        if not message.is_read:
            tg.create_task(MessageService.set_state(message_id, is_read=True))
    return {
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
