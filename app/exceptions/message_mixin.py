from typing import NoReturn

from starlette import status

from app.exceptions.api_error import APIError
from app.models.db.message import MessageId


class MessageExceptionsMixin:
    def message_not_found(self, message_id: MessageId) -> NoReturn:
        raise APIError(status.HTTP_404_NOT_FOUND, detail='Message not found')
