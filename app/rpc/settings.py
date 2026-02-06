from typing import override

from connectrpc.request import RequestContext

from app.lib.auth_context import require_web_user
from app.models.proto.settings_connect import (
    SettingsService,
    SettingsServiceASGIApplication,
)
from app.models.proto.settings_pb2 import UpdateTimezoneRequest, UpdateTimezoneResponse
from app.services.user_service import UserService


class _Service(SettingsService):
    @override
    async def update_timezone(
        self, request: UpdateTimezoneRequest, ctx: RequestContext
    ):
        require_web_user()
        await UserService.update_timezone(request.timezone)
        return UpdateTimezoneResponse()


service = _Service()
asgi_app_cls = SettingsServiceASGIApplication
