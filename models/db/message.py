from email.message import EmailMessage
from typing import Self

from bs4 import BeautifulSoup
from sqlalchemy import Boolean, ForeignKey, LargeBinary, UnicodeText
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from lib.crypto import HASH_SIZE
from lib.rich_text import RichTextMixin
from limits import MESSAGE_BODY_MAX_LENGTH
from models.db.base import Base
from models.db.cache_entry import CacheEntry
from models.db.created_at_mixin import CreatedAtMixin
from models.db.user import User
from models.text_format import TextFormat


class Message(Base.Sequential, CreatedAtMixin, RichTextMixin):
    __tablename__ = 'message'
    __rich_text_fields__ = (('body', TextFormat.markdown),)

    from_user_id: Mapped[int] = mapped_column(ForeignKey(User.id), nullable=False)
    from_user: Mapped[User] = relationship(foreign_keys=[from_user_id], lazy='raise')
    to_user_id: Mapped[int] = mapped_column(ForeignKey(User.id), nullable=False)
    to_user: Mapped[User] = relationship(foreign_keys=[to_user_id], lazy='raise')
    subject: Mapped[str] = mapped_column(UnicodeText, nullable=False)
    body: Mapped[str] = mapped_column(UnicodeText, nullable=False)
    body_rich_hash: Mapped[bytes | None] = mapped_column(LargeBinary(HASH_SIZE), nullable=True, default=None)
    body_rich: Mapped[CacheEntry | None] = relationship(
        CacheEntry,
        primaryjoin=CacheEntry.id == body_rich_hash,
        viewonly=True,
        default=None,
        lazy='raise',
    )

    # defaults
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    from_hidden: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    to_hidden: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    @validates('body')
    def validate_body(self, _: str, value: str) -> str:
        if len(value) > MESSAGE_BODY_MAX_LENGTH:
            raise ValueError('Message is too long')
        return value

    @classmethod
    def from_email(cls, mail: EmailMessage, from_user_id: int, to_user_id: int) -> Self:
        """
        Create a message instance from an email message.
        """

        subject = mail.get('Subject')

        if not subject:
            raise ValueError('Message has no subject')

        def get_body(part: EmailMessage) -> str | None:
            content_type = part.get_content_type()
            if content_type == 'text/plain':
                payload: str = part.get_payload(decode=True).decode()
                return payload.strip()
            elif content_type == 'text/html':
                payload: str = part.get_payload(decode=True).decode()
                return BeautifulSoup(payload, 'html.parser').get_text(separator=' ').strip()
            else:
                return None

        if mail.is_multipart():
            body = None
            for part in mail.iter_parts():
                if body := get_body(part):
                    break
        else:
            body = get_body(mail)

        if not body:
            raise ValueError('Message has no body')

        return cls(
            from_user_id=from_user_id,
            to_user_id=to_user_id,
            subject=subject,
            body=body,  # TODO: body check etc.
        )
