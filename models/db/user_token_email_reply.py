import logging
import secrets
from abc import ABC
from base64 import urlsafe_b64encode
from datetime import timedelta
from hmac import compare_digest
from typing import Annotated, Self

from bson import ObjectId
from pydantic import Field

from config import SMTP_MESSAGES_FROM_HOST
from lib.crypto import hash_hex
from models.db.base_sequential import SequentialId
from models.db.user_token import UserToken
from models.mail_source import MailSource
from models.mail_source_type import MailSourceType
from utils import utcnow

_EXPIRE = timedelta(days=365 * 2)  # 2 years


class UserTokenEmailReply(UserToken, ABC):
    source_type: MailSourceType
    to_user_id: Annotated[SequentialId, Field(frozen=True)]

    @classmethod
    async def create_from_addr(cls, from_user_id: SequentialId, to_user_id: SequentialId, source_type: MailSourceType) -> str:
        # NOTE: atm, if the key is leaked, there is no way to revoke it (possible targeted spam)
        key_b = secrets.token_bytes(32)
        token = cls(
            user_id=from_user_id,
            expires_at=utcnow() + _EXPIRE,
            key_hashed=hash_hex(key_b, context=None),
            source_type=source_type,
            to_user_id=to_user_id,
        )
        await token.create()
        combined = urlsafe_b64encode(token.id.binary + key_b).decode()
        return f'{combined}@{SMTP_MESSAGES_FROM_HOST}'

    @classmethod
    async def find_one_by_from_addr(cls, from_addr: str) -> Self | None:
        try:
            combined, _ = from_addr.split('@', maxsplit=1)
            combined_b = urlsafe_b64encode(combined.encode())
            id_b = combined_b[:12]
            key_b = combined_b[12:]

            if len(id_b) != 12 or len(key_b) != 32:
                raise ValueError()
        except:
            logging.debug('Invalid from_addr format %r', from_addr)
            return None

        doc = await cls.find_one({'_id': ObjectId(id_b)})

        if not doc:
            return None

        if not compare_digest(doc.key_hashed, hash_hex(key_b, context=None)):
            logging.debug('Invalid key for from_addr %r', from_addr)
            return None

        return doc
