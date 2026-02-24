from typing import override

from connectrpc.request import RequestContext

from app.lib.auth_context import require_web_user
from app.lib.standard_feedback import StandardFeedback
from app.lib.translation import t
from app.models.proto.settings_applications_connect import (
    Service,
    ServiceASGIApplication,
)
from app.models.proto.settings_applications_pb2 import (
    CreateRequest,
    CreateResponse,
    CreateTokenRequest,
    CreateTokenResponse,
    DeleteRequest,
    DeleteResponse,
    ResetAccessTokenRequest,
    ResetAccessTokenResponse,
    ResetClientSecretRequest,
    ResetClientSecretResponse,
    RevokeAuthorizationRequest,
    RevokeAuthorizationResponse,
    UpdateAvatarRequest,
    UpdateAvatarResponse,
    UpdateRequest,
    UpdateResponse,
)
from app.models.scope import scope_from_proto
from app.models.types import ApplicationId, OAuth2TokenId
from app.services.oauth2_application_service import OAuth2ApplicationService
from app.services.oauth2_token_service import OAuth2TokenService


class _Service(Service):
    @override
    async def revoke_authorization(
        self, request: RevokeAuthorizationRequest, ctx: RequestContext
    ):
        require_web_user()
        await OAuth2TokenService.revoke_by_app_id(ApplicationId(request.id))
        return RevokeAuthorizationResponse()

    @override
    async def create(self, request: CreateRequest, ctx: RequestContext):
        require_web_user()
        app_id = await OAuth2ApplicationService.create(name=request.name)
        return CreateResponse(id=app_id)

    @override
    async def reset_client_secret(
        self, request: ResetClientSecretRequest, ctx: RequestContext
    ):
        require_web_user()
        secret = await OAuth2ApplicationService.reset_client_secret(
            ApplicationId(request.id)
        )
        return ResetClientSecretResponse(secret=secret.get_secret_value())

    @override
    async def update(self, request: UpdateRequest, ctx: RequestContext):
        require_web_user()

        await OAuth2ApplicationService.update_settings(
            app_id=ApplicationId(request.id),
            name=request.name,
            is_confidential=request.confidential,
            redirect_uris=OAuth2ApplicationService.validate_redirect_uris(
                request.redirect_uris
            ),
            scopes=scope_from_proto(request.scopes),
            revoke_all_authorizations=request.revoke_all_authorizations,
        )

        return UpdateResponse(
            feedback=StandardFeedback.success_feedback(
                None, t('settings.changes_have_been_saved')
            )
        )

    @override
    async def update_avatar(self, request: UpdateAvatarRequest, ctx: RequestContext):
        require_web_user()
        avatar_url = await OAuth2ApplicationService.update_avatar(
            ApplicationId(request.id), request.avatar_file
        )
        return UpdateAvatarResponse(avatar_url=avatar_url)

    @override
    async def delete(self, request: DeleteRequest, ctx: RequestContext):
        require_web_user()
        await OAuth2ApplicationService.delete(ApplicationId(request.id))
        return DeleteResponse()

    @override
    async def create_token(self, request: CreateTokenRequest, ctx: RequestContext):
        require_web_user()
        token_id = await OAuth2TokenService.create_pat(
            name=request.name,
            scopes=scope_from_proto(request.scopes),
        )
        return CreateTokenResponse(id=token_id)

    @override
    async def reset_access_token(
        self, request: ResetAccessTokenRequest, ctx: RequestContext
    ):
        require_web_user()
        token = await OAuth2TokenService.reset_pat_access_token(
            OAuth2TokenId(request.token_id)
        )
        return ResetAccessTokenResponse(secret=token.get_secret_value())


service = _Service()
asgi_app_cls = ServiceASGIApplication
