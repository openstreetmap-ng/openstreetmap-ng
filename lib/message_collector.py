from collections import defaultdict
from enum import StrEnum
from types import MappingProxyType
from typing import NoReturn

from fastapi import HTTPException, status


class MessageSeverity(StrEnum):
    success = 'success'
    info = 'info'
    error = 'error'


_MESSAGE_TYPE = MappingProxyType({severity: f'custom_{severity}' for severity in MessageSeverity})


class MessageCollector:
    def __init__(self) -> None:
        self._messages: dict[str | None, list[tuple[MessageSeverity, str]]] = defaultdict(list)

    def success(self, field: str | None, message: str) -> None:
        """
        Collect a success message for a field.
        """

        self._messages[field].append((MessageSeverity.success, message))

    def info(self, field: str | None, message: str) -> None:
        """
        Collect an info message for a field.
        """

        self._messages[field].append((MessageSeverity.info, message))

    def raise_error(self, field: str | None, message: str) -> NoReturn:
        """
        Collect an error message for a field and raise a HTTPException.
        """

        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail=[
                {
                    'type': _MESSAGE_TYPE[MessageSeverity.error],
                    'loc': [None, field],
                    'msg': message,
                }
            ],
        )

    @property
    def result(self) -> dict:
        """
        Return the collected messages as a dict.
        """

        return {
            'detail': [
                {
                    'type': _MESSAGE_TYPE[severity],
                    'loc': [None, field],
                    'msg': message,
                }
                for field, messages in self._messages.items()
                for severity, message in messages
            ]
        }


# _context = ContextVar('MessageCollector_context')


# @contextmanager
# def collector_context():
#     """
#     Context manager for collecting messages.
#     """

#     collector = MessageCollector()
#     token = _context.set(collector)
#     try:
#         yield collector
#     finally:
#         _context.reset(token)


# def collect_success(field: str | None, message: str) -> None:
#     """
#     Collect a success message for a field.
#     """

#     collector: MessageCollector = _context.get()
#     collector.success(field, message)


# def collect_info(field: str | None, message: str) -> None:
#     """
#     Collect an info message for a field.
#     """

#     collector: MessageCollector = _context.get()
#     collector.info(field, message)


# def collect_raise_error(field: str | None, message: str) -> NoReturn:
#     """
#     Collect an error message for a field and raise a HTTPException.
#     """

#     collector: MessageCollector = _context.get()
#     collector.raise_error(field, message)
