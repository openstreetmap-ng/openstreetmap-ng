from email.message import EmailMessage
from typing import Self

import cython
from bs4 import BeautifulSoup
from sqlalchemy import Boolean, ForeignKey, LargeBinary, UnicodeText
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.lib.crypto import HASH_SIZE
from app.lib.rich_text import RichTextMixin
from app.limits import MESSAGE_BODY_MAX_LENGTH
from app.models.db.base import Base
from app.models.db.created_at_mixin import CreatedAtMixin
from app.models.db.user import User
from app.models.text_format import TextFormat


class Message(Base.Sequential, CreatedAtMixin, RichTextMixin):
    __tablename__ = 'message'
    __rich_text_fields__ = (('body', TextFormat.markdown),)

    from_user_id: Mapped[int] = mapped_column(ForeignKey(User.id), nullable=False)
    from_user: Mapped[User] = relationship(foreign_keys=(from_user_id,), init=False, lazy='raise', innerjoin=True)
    to_user_id: Mapped[int] = mapped_column(ForeignKey(User.id), nullable=False)
    to_user: Mapped[User] = relationship(foreign_keys=(to_user_id,), init=False, lazy='raise', innerjoin=True)
    subject: Mapped[str] = mapped_column(UnicodeText, nullable=False)
    body: Mapped[str] = mapped_column(UnicodeText, nullable=False)
    body_rich_hash: Mapped[bytes | None] = mapped_column(
        LargeBinary(HASH_SIZE),
        init=False,
        nullable=True,
        server_default=None,
    )

    # defaults
    is_read: Mapped[bool] = mapped_column(Boolean, init=False, nullable=False, server_default='false')
    from_hidden: Mapped[bool] = mapped_column(Boolean, init=False, nullable=False, server_default='false')
    to_hidden: Mapped[bool] = mapped_column(Boolean, init=False, nullable=False, server_default='false')

    # runtime
    body_rich: str | None = None

    @validates('body')
    def validate_body(self, _: str, value: str) -> str:
        if len(value) > MESSAGE_BODY_MAX_LENGTH:
            raise ValueError(f'Message body is too long ({len(value)} > {MESSAGE_BODY_MAX_LENGTH})')
        return value

    @classmethod
    def from_email(cls, mail: EmailMessage, from_user_id: int, to_user_id: int) -> Self:
        """
        Create a message instance from an email message.
        """
        subject = mail.get('Subject')
        if subject is None:
            raise ValueError('Email message has no subject')

        if mail.is_multipart():
            body = None
            for part in mail.iter_parts():
                body = get_body(part)
                if body is not None:
                    break
        else:
            body = get_body(mail)

        if body is None:
            raise ValueError(f'Email message {subject!r} has no body')

        return cls(
            from_user_id=from_user_id,
            to_user_id=to_user_id,
            subject=subject,
            body=body,  # TODO: body check etc.
        )


@cython.cfunc
def get_body(part: EmailMessage):
    content_type = part.get_content_type()
    if content_type not in ('text/plain', 'text/html'):
        return None

    payload_bytes: bytes | None = part.get_payload(decode=True)  # type: ignore[assignment]
    if payload_bytes is None:
        return None

    payload: str = payload_bytes.decode()
    if content_type == 'text/html':
        payload = BeautifulSoup(payload, 'lxml').get_text(separator=' ')
    return payload.strip()
