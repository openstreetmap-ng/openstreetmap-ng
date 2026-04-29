from typing import override

from connectrpc.request import RequestContext
from pydantic import TypeAdapter, ValidationError

from app.lib.cookie import delete_cookie, set_auth_cookie
from app.lib.standard_feedback import StandardFeedback
from app.middlewares.request_context_middleware import get_request
from app.models.db.oauth2_application import SYSTEM_APP_WEB_CLIENT_ID
from app.models.proto.signup_connect import Service, ServiceASGIApplication
from app.models.proto.signup_pb2 import (
    CancelProviderRequest,
    CancelProviderResponse,
    SubmitRequest,
    SubmitResponse,
)
from app.services.auth_provider_service import AuthProviderService
from app.services.system_app_service import SystemAppService
from app.services.user_signup_service import UserSignupService
from app.validators.display_name import DisplayNameValidating
from app.validators.email import EmailValidating

_DISPLAY_NAME_VALIDATOR = TypeAdapter(DisplayNameValidating)
_EMAIL_VALIDATOR = TypeAdapter(EmailValidating)


class _Service(Service):
    @override
    async def submit(self, request: SubmitRequest, ctx: RequestContext):
        try:
            display_name = _DISPLAY_NAME_VALIDATOR.validate_python(request.display_name)
        except ValidationError as e:
            StandardFeedback.raise_error('display_name', e.errors()[0]['msg'])

        try:
            email = _EMAIL_VALIDATOR.validate_python(request.email)
        except ValidationError as e:
            StandardFeedback.raise_error('email', e.errors()[0]['msg'])

        verification = AuthProviderService.validate_verification(
            get_request().cookies.get('auth_provider_verification')
        )
        email_verified = (
            verification is not None and verification.identity.email == email
        )

        user_id = await UserSignupService.signup(
            display_name=display_name,
            email=email,
            password=request.password,
            tracking=request.tracking,
            email_verified=email_verified,
        )

        access_token = await SystemAppService.create_access_token(
            SYSTEM_APP_WEB_CLIENT_ID, user_id=user_id
        )
        set_auth_cookie(ctx, access_token.token)
        if email_verified:
            delete_cookie(ctx, 'auth_provider_verification')

        return SubmitResponse(email_verified=email_verified)

    @override
    async def cancel_provider(
        self,
        request: CancelProviderRequest,
        ctx: RequestContext,
    ):
        del request
        delete_cookie(ctx, 'auth_provider_verification')
        return CancelProviderResponse()


service = _Service()
asgi_app_cls = ServiceASGIApplication
