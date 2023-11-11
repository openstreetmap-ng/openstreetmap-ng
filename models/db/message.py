import logging
from email.message import EmailMessage
from email.utils import parsedate_to_datetime
from itertools import chain
from typing import Self

from asyncache import cached
from bs4 import BeautifulSoup
from sqlalchemy import Boolean, ForeignKey, LargeBinary, UnicodeText
from sqlalchemy.orm import Mapped, mapped_column, relationship

from lib.rich_text import RichText
from limits import MESSAGE_FROM_MAIL_DATE_VALIDITY
from models.db.base import Base
from models.db.created_at import CreatedAt
from models.db.user import User
from models.text_format import TextFormat


class Message(Base.Sequential, CreatedAt):
    from_user_id: Mapped[int] = mapped_column(ForeignKey(User.id), nullable=False)
    from_user: Mapped[User] = relationship(lazy='raise')
    to_user_id: Mapped[int] = mapped_column(ForeignKey(User.id), nullable=False)
    to_user: Mapped[User] = relationship(lazy='raise')
    subject: Mapped[str] = mapped_column(UnicodeText, nullable=False)
    body: Mapped[str] = mapped_column(UnicodeText, nullable=False)
    body_rich_hash: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True, default=None)

    # defaults
    read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    from_hidden: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    to_hidden: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # TODO: test text/plain; charset=utf-8
    # TODO: SQL
    @cached({})
    async def body_rich(self) -> str:
        cache = await RichText.get_cache(self.body, self.body_rich_hash, TextFormat.markdown)
        if self.body_rich_hash != cache.id:
            self.body_rich_hash = cache.id
            await self.update()
        return cache.value

    @classmethod
    def from_email(cls, mail: EmailMessage, from_user_id: SequentialId, to_user_id: SequentialId) -> Self:
        if not (title := mail.get('Subject')):
            raise ValueError('Message has no subject')

        def get_body(part: EmailMessage) -> str | None:
            if part.get_content_type() == 'text/plain':
                return part.get_payload(decode=True).decode()
            elif part.get_content_type() == 'text/html':
                return BeautifulSoup(part.get_payload(decode=True).decode(), 'html.parser').get_text(separator=' ')
            else:
                return None

        for part in chain(*mail.iter_parts(), (mail,)):
            if body := get_body(part):
                break
        else:
            raise ValueError('Message has no body')

        created_at = utcnow()

        if date := mail.get('Date'):
            try:
                created_at = parsedate_to_datetime(date)
            except Exception:
                logging.warning('Failed to parse message date %r', date)

        if created_at < utcnow() - MESSAGE_FROM_MAIL_DATE_VALIDITY:
            logging.debug('Message date %r is too old, using current time', created_at)
            created_at = utcnow()

        return cls(
            created_at=created_at,
            from_user_id=from_user_id,
            from_hidden=False,
            to_user_id=to_user_id,
            to_hidden=False,
            read=False,
            title=title,
            body=body)

    async def mark_read(self) -> None:
        if not self.read:
            self.read = True
            await self.update()
