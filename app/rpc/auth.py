from asyncio import TaskGroup
from typing import override

from connectrpc.request import RequestContext

from app.config import COOKIE_AUTH_MAX_AGE
from app.lib.auth_context import auth_user
from app.lib.cookie import set_auth_cookie
from app.models.proto.auth_connect import (
    Service,
    ServiceASGIApplication,
)
from app.models.proto.auth_pb2 import (
    GetPasskeyChallengeRequest,
    GetPasskeyChallengeResponse,
    LoginRequest,
    LoginResponse,
    PasskeyChallenge,
)
from app.queries.user_query import UserQuery
from app.services.user_passkey_challenge_service import UserPasskeyChallengeService
from app.services.user_passkey_service import UserPasskeyService
from app.services.user_password_service import UserPasswordService
from app.services.user_service import UserService
from app.validators.unicode import normalize_display_name


class _Service(Service):
    @override
    async def login(self, request: LoginRequest, ctx: RequestContext):
        credentials = request.credentials if request.HasField('credentials') else None
        result = await UserService.login(
            display_name_or_email=(
                normalize_display_name(credentials.display_name_or_email)
                if credentials is not None
                else None
            ),
            password=credentials.password if credentials is not None else None,
            passkey=request.passkey if request.HasField('passkey') else None,
            totp_code=request.totp_code if request.HasField('totp_code') else None,
            recovery_code=(
                request.recovery_code if request.HasField('recovery_code') else None
            ),
            bypass_2fa=request.bypass_2fa,
        )
        if isinstance(result, LoginResponse):
            return result

        set_auth_cookie(
            ctx, result, max_age=COOKIE_AUTH_MAX_AGE if request.remember else None
        )
        return LoginResponse()

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
asgi_app_cls = ServiceASGIApplication
