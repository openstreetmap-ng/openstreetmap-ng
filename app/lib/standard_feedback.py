from collections import defaultdict
from typing import Any, Literal, NoReturn

from connectrpc.code import Code
from connectrpc.errors import ConnectError
from fastapi import HTTPException, status

from app.models.proto.shared_pb2 import StandardFeedbackDetail

MessageSeverity = Literal['success', 'info', 'error']


class StandardFeedback:
    """
    Standard feedback returns messages in OpenAPI-compatible format.

    This format is often used by StandardForm to parse and display form feedback.
    """

    __slots__ = ('_messages',)

    def __init__(self):
        self._messages: defaultdict[str | None, list[tuple[MessageSeverity, str]]]
        self._messages = defaultdict(list)

    def success(self, field: str | None, message: str):
        """Collect a success message for a field."""
        self._messages[field].append(('success', message))

    @classmethod
    def success_result(cls, field: str | None, message: str):
        """Collect a success message for a field. Instantly returns the result."""
        tmp = cls()
        tmp.success(field, message)
        return tmp.result

    @classmethod
    def success_feedback(
        cls, field: str | None, message: str
    ) -> StandardFeedbackDetail:
        """Build a StandardFeedbackDetail containing a single success message."""
        tmp = cls()
        tmp.success(field, message)
        return tmp.feedback_detail

    def info(self, field: str | None, message: str):
        """Collect an info message for a field."""
        self._messages[field].append(('info', message))

    @classmethod
    def info_result(cls, field: str | None, message: str):
        """Collect an info message for a field. Instantly returns the result."""
        tmp = cls()
        tmp.info(field, message)
        return tmp.result

    @classmethod
    def info_feedback(cls, field: str | None, message: str) -> StandardFeedbackDetail:
        """Build a StandardFeedbackDetail containing a single info message."""
        tmp = cls()
        tmp.info(field, message)
        return tmp.feedback_detail

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

    @property
    def feedback_detail(self) -> StandardFeedbackDetail:
        """Return the collected messages as an RPC-ready StandardFeedbackDetail."""
        return StandardFeedbackDetail(
            entries=[
                StandardFeedbackDetail.Entry(
                    severity=severity,
                    field=field,
                    message=message,
                )
                for field, messages in self._messages.items()
                for severity, message in messages
            ]
        )

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

    @staticmethod
    def raise_connect_error(
        field: str | None,
        message: str,
        *,
        code: Code = Code.INVALID_ARGUMENT,
    ) -> NoReturn:
        """Raise a ConnectError with StandardFeedbackDetail in details."""
        feedback = StandardFeedbackDetail(
            entries=[
                StandardFeedbackDetail.Entry(
                    severity='error',
                    field=field,
                    message=message,
                )
            ]
        )
        raise ConnectError(code, message, details=(feedback,))
