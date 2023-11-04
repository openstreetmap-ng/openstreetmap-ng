import logging
from datetime import datetime
from email.message import EmailMessage
from email.utils import parsedate_to_datetime
from itertools import chain
from time import time
from typing import Annotated, Self

from annotated_types import MaxLen
from asyncache import cached
from bs4 import BeautifulSoup
from pydantic import Field

from lib.rich_text import RichText
from limits import MESSAGE_BODY_MAX_LENGTH, MESSAGE_FROM_MAIL_DATE_VALIDITY
from models.collections.base_sequential import BaseSequential, SequentialId
from models.str import HexStr, NonEmptyStr, Str255
from models.text_format import TextFormat
from utils import utcnow


class Message(BaseSequential):
    created_at: Annotated[datetime, Field(frozen=True)]
    from_user_id: Annotated[SequentialId, Field(frozen=True)]
    from_hidden: Annotated[bool, Field(frozen=True)]
    to_user_id: Annotated[SequentialId, Field(frozen=True)]
    to_hidden: Annotated[bool, Field(frozen=True)]
    read: bool
    title: Annotated[Str255, Field(frozen=True)]
    body: Annotated[NonEmptyStr, Field(frozen=True, max_length=MESSAGE_BODY_MAX_LENGTH)]
    body_rich_hash: HexStr | None = None

    # TODO: test text/plain; charset=utf-8

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
