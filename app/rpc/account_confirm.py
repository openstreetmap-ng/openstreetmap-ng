from typing import override

from connectrpc.request import RequestContext

from app.lib.auth_context import require_web_user
from app.lib.standard_feedback import StandardFeedback
from app.lib.translation import t
from app.models.proto.account_confirm_connect import (
    Service,
    ServiceASGIApplication,
)
from app.models.proto.account_confirm_pb2 import (
    ResendRequest,
    ResendResponse,
)
from app.services.user_token_email_service import UserTokenEmailService


class _Service(Service):
    @override
    async def resend(self, request: ResendRequest, ctx: RequestContext):
        user = require_web_user()

        if user['email_verified']:
            return ResendResponse(is_active=True)

        await UserTokenEmailService.send_email()
        return ResendResponse(
            feedback=StandardFeedback.success_feedback(
                None,
                t(
                    'confirmations.resend_success_flash.confirmation_sent',
                    email=user['email'],
                ),
            ),
        )


service = _Service()
asgi_app_cls = ServiceASGIApplication
