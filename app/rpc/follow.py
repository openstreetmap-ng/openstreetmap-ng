from typing import override

from connectrpc.request import RequestContext

from app.lib.auth_context import require_web_user
from app.models.proto.follow_connect import (
    Service,
    ServiceASGIApplication,
)
from app.models.proto.follow_pb2 import (
    UpdateRequest,
    UpdateResponse,
)
from app.models.types import UserId
from app.services.user_follow_service import UserFollowService


class _Service(Service):
    @override
    async def update(self, request: UpdateRequest, ctx: RequestContext):
        require_web_user()

        target_user_id = UserId(request.target_user_id)
        if request.is_following:
            await UserFollowService.follow(target_user_id)
        else:
            await UserFollowService.unfollow(target_user_id)

        return UpdateResponse()


service = _Service()
asgi_app_cls = ServiceASGIApplication
