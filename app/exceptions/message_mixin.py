from typing import NoReturn

from starlette import status

from app.exceptions.api_error import APIError


class MessageExceptionsMixin:
    def message_not_found(self, message_id: int) -> NoReturn:
        raise APIError(status.HTTP_404_NOT_FOUND, detail='Message not found')
