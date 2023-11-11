import logging
import secrets
from typing import Annotated, Self
from urllib.parse import urlencode

from pydantic import Field

from lib.crypto import hash_hex
from lib.exceptions import Exceptions
from models.db.base_sequential import SequentialId
from models.db.oauth1_application import OAuth1Application
from models.db.oauth_token import OAuthToken
from models.scope import Scope
from models.str import NonEmptyStr, OOB_URIStr, Str255
from utils import extend_query_params, utcnow

# TODO: smooth reauthorize


class OAuth1Token(OAuthToken):
    key_secret: NonEmptyStr  # encryption here is redundant, key is already hashed
    callback_url: Annotated[OOB_URIStr | None, Field(frozen=True)]
    verifier: Str255 | None

    app_: Annotated[OAuth1Application | None, Field(exclude=True)] = None

    @classmethod
    async def find_one_by_key_with_(cls, key: str) -> Self | None:
        pipeline = [
            {'$match': {'key_hashed': hash_hex(key)}},
            {'$lookup': {  # this lookup ensures the oauth application exists
                'from': OAuth1Application._collection_name(),
                'localField': 'application_id',
                'foreignField': '_id',
                'as': 'application'
            }},
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
            Exceptions.get().raise_for_oauth_bad_app_token()

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
        token_ = await cls.find_one({
            'key_hashed': hash_hex(token, context=None),
            'user_id': None,
            'authorized_at': None,
        })

        if not token_:
            Exceptions.get().raise_for_oauth_bad_user_token()

        app = OAuth1Application.find_one_by_id(token_.application_id)

        if not app:
            Exceptions.get().raise_for_oauth_bad_user_token()
        if not set(scopes).issubset(app.scopes):
            Exceptions.get().raise_for_oauth_bad_scopes()

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
        token_ = await cls.find_one({
            'key_hashed': hash_hex(token, context=None),
            'user_id': {'$ne': None},
            'authorized_at': None,
        })

        if not token_:
            Exceptions.get().raise_for_oauth_bad_user_token()

        try:
            if token_.verifier != verifier:
                Exceptions.get().raise_for_oauth1_bad_verifier()
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
