from asyncio import TaskGroup
from typing import override

from connectrpc.request import RequestContext

from app.lib.auth_context import auth_user
from app.models.proto.auth_connect import (
    AuthService,
    AuthServiceASGIApplication,
)
from app.models.proto.auth_pb2 import (
    GetPasskeyChallengeRequest,
    GetPasskeyChallengeResponse,
    PasskeyChallenge,
)
from app.queries.user_query import UserQuery
from app.services.user_passkey_challenge_service import UserPasskeyChallengeService
from app.services.user_passkey_service import UserPasskeyService
from app.services.user_password_service import UserPasswordService
from app.validators.unicode import normalize_display_name


class _Service(AuthService):
    @override
    async def get_passkey_challenge(
        self, request: GetPasskeyChallengeRequest, ctx: RequestContext
    ):
        user = auth_user()

        if user is None and request.HasField('credentials'):
            user = await UserQuery.find_by_display_name_or_email(
                normalize_display_name(request.credentials.display_name_or_email)
            )
            if user is not None and not await UserPasswordService.verify_password(
                user, request.credentials.password, error_message='ignore'
            ):
                user = None

        async with TaskGroup() as tg:
            challenge_t = tg.create_task(UserPasskeyChallengeService.create())
            credentials = (
                await UserPasskeyService.get_credentials(user['id'])
                if user is not None
                else []
            )

        challenge = PasskeyChallenge(
            challenge=challenge_t.result(),
            credentials=credentials,
        )
        if user is not None:
            challenge.user_id = user['id']
            challenge.user_display_name = user['display_name']
            challenge.user_email = user['email']

        return GetPasskeyChallengeResponse(challenge=challenge)


service = _Service()
asgi_app_cls = AuthServiceASGIApplication
