from collections import defaultdict
from typing import Any, Literal, NoReturn

from fastapi import HTTPException, status

MessageSeverity = Literal['success', 'info', 'error']


class StandardFeedback:
    """
    Standard feedback returns messages in OpenAPI-compatible format.

    This format is often used by StandardForm to parse and display form feedback.
    """

    __slots__ = ('_messages',)

    def __init__(self) -> None:
        self._messages: defaultdict[str | None, list[tuple[MessageSeverity, str]]]
        self._messages = defaultdict(list)

    def success(self, field: str | None, message: str) -> None:
        """Collect a success message for a field."""
        self._messages[field].append(('success', message))

    @classmethod
    def success_result(
        cls, field: str | None, message: str
    ) -> dict[Literal['detail'], list[dict[str, Any]]]:
        """Collect a success message for a field. Instantly returns the result."""
        tmp = cls()
        tmp.success(field, message)
        return tmp.result

    def info(self, field: str | None, message: str) -> None:
        """Collect an info message for a field."""
        self._messages[field].append(('info', message))

    @classmethod
    def info_result(
        cls, field: str | None, message: str
    ) -> dict[Literal['detail'], list[dict[str, Any]]]:
        """Collect an info message for a field. Instantly returns the result."""
        tmp = cls()
        tmp.info(field, message)
        return tmp.result

    @property
    def result(self) -> dict[Literal['detail'], list[dict[str, Any]]]:
        """Return the collected messages as a dict."""
        return {
            'detail': [
                {
                    'type': severity,
                    'loc': (None, field),
                    'msg': message,
                }
                for field, messages in self._messages.items()
                for severity, message in messages
            ]
        }

    @staticmethod
    def raise_error(field: str | None, message: str) -> NoReturn:
        """Collect an error message for a field and raise a HTTPException."""
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail=(
                {
                    'type': 'error',
                    'loc': (None, field),
                    'msg': message,
                },
            ),
        )


# _context = ContextVar('MessageCollector')


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
