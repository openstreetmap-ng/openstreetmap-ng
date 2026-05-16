from typing import override

from connectrpc.request import RequestContext

from app.lib.auth.context import auth_user, require_web_user
from app.lib.standard.feedback import StandardFeedback
from app.lib.text.socials import user_socials
from app.lib.text.translation import t
from app.models.proto.settings_connect import (
    Service,
    ServiceASGIApplication,
)
from app.models.proto.settings_pb2 import (
    UpdateAvatarRequest,
    UpdateAvatarResponse,
    UpdateBackgroundRequest,
    UpdateBackgroundResponse,
    UpdateDescriptionRequest,
    UpdateDescriptionResponse,
    UpdateEmailRequest,
    UpdateEmailResponse,
    UpdateSettingsRequest,
    UpdateSettingsResponse,
    UpdateSocialsRequest,
    UpdateSocialsResponse,
    UpdateTimezoneRequest,
    UpdateTimezoneResponse,
)
from app.models.types import DisplayName, Email, LocaleCode
from app.queries.user_profile_query import UserProfileQuery
from app.services.user_profile_service import UserProfileService


class _Service(Service):
    @override
    async def update_avatar(self, request: UpdateAvatarRequest, ctx: RequestContext):
        require_web_user()

        avatar_case = request.WhichOneof('avatar')
        if avatar_case == 'avatar_file':
            avatar_url = await UserProfileService.update_avatar(
                avatar_file=request.avatar_file
            )
        else:
            avatar_url = await UserProfileService.update_avatar(
                preset=(
                    'gravatar'
                    if request.preset == UpdateAvatarRequest.Preset.gravatar
                    else None
                )
            )

        return UpdateAvatarResponse(avatar_url=avatar_url)

    @override
    async def update_background(
        self, request: UpdateBackgroundRequest, ctx: RequestContext
    ):
        require_web_user()
        background_url = await UserProfileService.update_background(
            request.background_file
        )
        return UpdateBackgroundResponse(background_url=background_url)

    @override
    async def update_description(
        self, request: UpdateDescriptionRequest, ctx: RequestContext
    ):
        require_web_user()

        await UserProfileService.update_description(description=request.description)
        profile = await UserProfileQuery.get_by_user_id(auth_user(required=True)['id'])

        return UpdateDescriptionResponse(
            description=profile['description'],
            description_rich=profile['description_rich'],  # type: ignore
        )

    @override
    async def update_socials(self, request: UpdateSocialsRequest, ctx: RequestContext):
        require_web_user()

        socials = user_socials(request.socials)
        await UserProfileService.update_socials(socials=socials)

        response = UpdateSocialsResponse()
        for social in socials:
            item = response.socials.add()
            item.service = social.service
            item.value = social.value
        return response

    @override
    async def update_settings(
        self, request: UpdateSettingsRequest, ctx: RequestContext
    ):
        require_web_user()

        await UserProfileService.update_settings(
            display_name=DisplayName(request.display_name),
            language=LocaleCode(request.language),
            activity_tracking=request.activity_tracking,
            crash_reporting=request.crash_reporting,
        )

        return UpdateSettingsResponse(
            feedback=StandardFeedback.success_feedback(None, t('action.save_changes'))
        )

    @override
    async def update_email(self, request: UpdateEmailRequest, ctx: RequestContext):
        require_web_user()

        await UserProfileService.update_email(
            new_email=Email(request.email),
            password=request.password,
        )

        return UpdateEmailResponse(
            feedback=StandardFeedback.info_feedback(
                None, t('settings.email_change_confirmation_sent')
            )
        )

    @override
    async def update_timezone(
        self, request: UpdateTimezoneRequest, ctx: RequestContext
    ):
        require_web_user()
        await UserProfileService.update_timezone(request.timezone)
        return UpdateTimezoneResponse()


service = _Service()
asgi_app_cls = ServiceASGIApplication
