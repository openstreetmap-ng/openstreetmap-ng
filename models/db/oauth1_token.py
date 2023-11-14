import logging
import secrets
from datetime import datetime
from typing import Self
from urllib.parse import urlencode

from sqlalchemy import ARRAY, DateTime, Enum, ForeignKey, LargeBinary, Sequence, Unicode
from sqlalchemy.orm import Mapped, mapped_column, relationship

from lib.crypto import HASH_SIZE
from lib.exceptions import exceptions
from models.db.base import Base
from models.db.created_at import CreatedAt
from models.db.oauth1_application import OAuth1Application
from models.db.user import User
from models.scope import Scope
from utils import extend_query_params, utcnow

# TODO: smooth reauthorize


class OAuth1Token(Base.UUID, CreatedAt):
    __tablename__ = 'oauth1_token'

    user_id: Mapped[int] = mapped_column(ForeignKey(User.id), nullable=False)
    user: Mapped[User] = relationship(back_populates='oauth1_tokens', lazy='raise')
    application_id: Mapped[int] = mapped_column(ForeignKey(OAuth1Application.id), nullable=False)
    application: Mapped[OAuth1Application] = relationship(back_populates='oauth1_tokens', lazy='raise')
    key_hashed: Mapped[bytes] = mapped_column(LargeBinary(HASH_SIZE), nullable=False)  # TODO: binary length
    key_secret: Mapped[bytes] = mapped_column(
        LargeBinary(40), nullable=False
    )  # encryption here is redundant, key is already hashed
    scopes: Mapped[Sequence[Scope]] = mapped_column(ARRAY(Enum(Scope)), nullable=False)
    callback_url: Mapped[str | None] = mapped_column(Unicode, nullable=True)
    verifier: Mapped[str | None] = mapped_column(Unicode, nullable=True)

    # defaults
    authorized_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=None)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=None)

    @property
    def scopes_str(self) -> str:
        return ' '.join(sorted(self.scopes))

    # TODO: SQL
    @classmethod
    async def find_one_by_key(cls, key: str) -> Self | None:
        return await cls.find_one({'key_hashed': hash_hex(key, context=None)})

    @classmethod
    async def find_one_by_key_with_(cls, key: str) -> Self | None:
        pipeline = [
            {'$match': {'key_hashed': hash_hex(key)}},
            {
                '$lookup': {  # this lookup ensures the oauth application exists
                    'from': OAuth1Application._collection_name(),
                    'localField': 'application_id',
                    'foreignField': '_id',
                    'as': 'application',
                }
            },
            {'$unwind': '$application'},
        ]

        cursor = cls._collection().aggregate(pipeline)
        result = await cursor.to_list(1)

        if not result:
            logging.debug('OAuth1 token not found')
            return None

        data: dict = result[0]
        app = OAuth1Application.model_validate(data.pop('application'))
        token = cls.model_validate(data)
        token.app_ = app
        return token

    @classmethod
    async def request_token(cls, app_token: str, callback_url: str | None) -> dict:
        app = await OAuth1Application.find_one_by_key(app_token)

        if not app:
            exceptions().raise_for_oauth_bad_app_token()

        token = secrets.token_urlsafe(32)
        token_secret = secrets.token_urlsafe(32)

        await cls(
            user_id=None,
            application_id=app.id,
            key_hashed=hash_hex(token, context=None),
            key_secret=token_secret,
            scopes=set(),
            callback_url=callback_url,
            verifier=None,
        ).create()

        result = {
            'oauth_token': token,
            'oauth_token_secret': token_secret,
        }

        if callback_url:
            result['oauth_callback_confirmed'] = 'true'

        return result

    @classmethod
    async def authorize(cls, token: str, user_id: SequentialId, scopes: list[Scope]) -> str:
        token_ = await cls.find_one(
            {
                'key_hashed': hash_hex(token, context=None),
                'user_id': None,
                'authorized_at': None,
            }
        )

        if not token_:
            exceptions().raise_for_oauth_bad_user_token()

        app = OAuth1Application.find_one_by_id(token_.application_id)

        if not app:
            exceptions().raise_for_oauth_bad_user_token()
        if not set(scopes).issubset(app.scopes):
            exceptions().raise_for_oauth_bad_scopes()

        verifier = secrets.token_urlsafe(32)

        token_.user_id = user_id
        token_.scopes = scopes
        token_.verifier = verifier
        result = await token_.update()

        # TODO: necessary?
        if result.modified_count != 1:
            raise RuntimeError('OAuth1 token update failed')

        params = {
            'oauth_token': token,
            'oauth_verifier': verifier,
        }

        if token_.callback_url:
            return extend_query_params(token_.callback_url, params)
        else:
            return urlencode(params)

    @classmethod
    async def access_token(cls, token: str, verifier: str) -> dict:
        token_ = await cls.find_one(
            {
                'key_hashed': hash_hex(token, context=None),
                'user_id': {'$ne': None},
                'authorized_at': None,
            }
        )

        if not token_:
            exceptions().raise_for_oauth_bad_user_token()

        try:
            if token_.verifier != verifier:
                exceptions().raise_for_oauth1_bad_verifier()
        except Exception as e:
            # for safety, delete the token if the verification fails
            await token_.delete()
            raise e

        token = secrets.token_urlsafe(32)
        token_secret = secrets.token_urlsafe(32)

        token_.key_hashed = hash_hex(token, context=None)
        token_.key_secret = token_secret
        token_.authorized_at = utcnow()
        token_.verifier = None
        result = await token_.update()

        # TODO: necessary?
        if result.modified_count != 1:
            raise RuntimeError('OAuth1 token update failed')

        return {
            'oauth_token': token,
            'oauth_token_secret': token_secret,
        }
