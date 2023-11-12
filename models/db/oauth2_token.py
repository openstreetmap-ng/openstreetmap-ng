import logging
import secrets
from base64 import urlsafe_b64encode
from datetime import datetime
from hashlib import sha256
from typing import Self, Sequence

from sqlalchemy import (ARRAY, DateTime, Enum, ForeignKey, LargeBinary,
                        Sequence, Unicode)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from lib.crypto import HASH_SIZE, hash_hex
from lib.exceptions import Exceptions
from models.db.base import Base
from models.db.created_at import CreatedAt
from models.db.oauth2_application import OAuth2Application
from models.db.user import User
from models.oauth2_code_challenge_method import OAuth2CodeChallengeMethod
from models.scope import Scope
from utils import extend_query_params, utcnow


class OAuth2Token(Base.UUID, CreatedAt):
    __tablename__ = 'oauth2_token'

    user_id: Mapped[int] = mapped_column(ForeignKey(User.id), nullable=False)
    user: Mapped[User] = relationship(back_populates='oauth2_tokens', lazy='raise')
    application_id: Mapped[int] = mapped_column(ForeignKey(OAuth2Application.id), nullable=False)
    application: Mapped[OAuth2Application] = relationship(back_populates='oauth2_tokens', lazy='raise')
    key_hashed: Mapped[bytes] = mapped_column(LargeBinary(HASH_SIZE), nullable=False)
    scopes: Mapped[Sequence[Scope]] = mapped_column(ARRAY(Enum(Scope)), nullable=False)
    redirect_uri: Mapped[str] = mapped_column(Unicode, nullable=False)
    code_challenge_method: Mapped[OAuth2CodeChallengeMethod | None] = mapped_column(Enum(OAuth2CodeChallengeMethod), nullable=True)
    code_challenge: Mapped[str | None] = mapped_column(Unicode, nullable=True)

    # defaults
    authorized_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=None)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=None)

    @property
    def scopes_str(self) -> str:
        return ' '.join(sorted(self.scopes))

    # TODO: SQL
    @classmethod
    async def find_one_by_key_with_(cls, key: str) -> Self | None:
        pipeline = [
            {'$match': {'key_hashed': hash_hex(key)}},
            {'$lookup': {  # this lookup ensures the oauth application exists
                'from': OAuth2Application._collection_name(),
                'localField': 'application_id',
                'foreignField': '_id',
                'as': 'application'
            }},
            {'$unwind': '$application'},
        ]

        cursor = cls._collection().aggregate(pipeline)
        result = await cursor.to_list(1)

        if not result:
            logging.debug('OAuth2 token not found')
            return None

        data: dict = result[0]
        app = OAuth2Application.model_validate(data.pop('application'))
        token = cls.model_validate(data)
        token.app_ = app
        return token

    @classmethod
    async def authorize(cls, user_id: SequentialId, app_token: str, redirect_uri: str, scopes: Sequence[Scope], code_challenge: str | None, code_challenge_method: OAuth2CodeChallengeMethod | None, state: str | None) -> str:
        app = await OAuth2Application.find_one_by_key(app_token)

        if not app:
            Exceptions.get().raise_for_oauth_bad_app_token()
        if redirect_uri not in app.redirect_uris:
            Exceptions.get().raise_for_oauth_bad_redirect_uri()
        if not set(scopes).issubset(app.scopes):
            Exceptions.get().raise_for_oauth_bad_scopes()

        authorization_code = secrets.token_urlsafe(32)

        await cls(
            user_id=user_id,
            application_id=app.id,
            key_hashed=hash_hex(authorization_code, context=None),
            scopes=scopes,
            redirect_uri=redirect_uri,
            code_challenge=code_challenge,
            code_challenge_method=code_challenge_method,
        ).create()

        params = {
            'code': authorization_code,
        }

        if state:
            params['state'] = state

        # TODO: support OOB
        return extend_query_params(redirect_uri, params)

    @classmethod
    async def token(cls, authorization_code: str, verifier: str | None) -> dict:
        token_ = await cls.find_one({
            'key_hashed': hash_hex(authorization_code, context=None),
            'authorized_at': None,
        })

        if not token_:
            Exceptions.get().raise_for_oauth_bad_user_token()

        try:
            if token_.code_challenge_method is None:
                if verifier:
                    Exceptions.get().raise_for_oauth2_challenge_method_not_set()
            elif token_.code_challenge_method == OAuth2CodeChallengeMethod.plain:
                if token_.code_challenge != verifier:
                    Exceptions.get().raise_for_oauth2_bad_verifier(token_.code_challenge_method)
            elif token_.code_challenge_method == OAuth2CodeChallengeMethod.S256:
                if token_.code_challenge != urlsafe_b64encode(sha256(verifier.encode()).digest()).decode().rstrip('='):
                    Exceptions.get().raise_for_oauth2_bad_verifier(token_.code_challenge_method)
            else:
                raise NotImplementedError(f'Unsupported OAuth2 code challenge method {token_.code_challenge_method!r}')
        except Exception as e:
            # for safety, delete the token if the verification fails
            await token_.delete()
            raise e

        access_token = secrets.token_urlsafe(32)

        token_.key_hashed = hash_hex(access_token, context=None)
        token_.authorized_at = utcnow()
        token_.code_challenge = None
        token_.code_challenge_method = None
        result = await token_.update()

        if result.modified_count != 1:
            raise RuntimeError('OAuth2 token update failed')

        return {
            'access_token': access_token,
            'token_type': 'Bearer',
            'scope': token_.scopes_str,
            'created_at': int(token_.authorized_at.timestamp()),
            # TODO: id_token
        }
