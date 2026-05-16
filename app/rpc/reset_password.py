from typing import override

from connectrpc.request import RequestContext
from pydantic import SecretStr

from app.lib.auth.context import auth_user
from app.lib.standard.feedback import StandardFeedback
from app.lib.text.translation import t
from app.models.proto.reset_password_connect import (
    Service,
    ServiceASGIApplication,
)
from app.models.proto.reset_password_pb2 import (
    RequestRequest,
    RequestResponse,
    ResetRequest,
    ResetResponse,
)
from app.models.types import Email
from app.services.user_password_service import UserPasswordService
from app.services.user_token_reset_password_service import UserTokenResetPasswordService


class _Service(Service):
    @override
    async def request(self, request: RequestRequest, ctx: RequestContext):
        await UserTokenResetPasswordService.send_email(Email(request.email))
        return RequestResponse(
            feedback=StandardFeedback.success_feedback(
                None,
                t('settings.password_reset_link_sent'),
            ),
        )

    @override
    async def reset(self, request: ResetRequest, ctx: RequestContext):
        # When no user is signed in, revoke other sessions to invalidate any
        # leftover passwords the attacker might have planted via the same email.
        revoke_other_sessions = auth_user() is None

        await UserPasswordService.reset_password(
            token=SecretStr(request.token),
            new_password=request.new_password,
            revoke_other_sessions=revoke_other_sessions,
        )

        success_msg = t('settings.password_reset_success')
        if revoke_other_sessions:
            success_msg += ' ' + t('settings.password_reset_security_logout')

        return ResetResponse(
            feedback=StandardFeedback.success_feedback(None, success_msg),
        )


service = _Service()
asgi_app_cls = ServiceASGIApplication
