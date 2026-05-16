from typing import override

from connectrpc.request import RequestContext

from app.lib.auth.context import require_web_user
from app.models.proto.user_subscription_connect import (
    Service,
    ServiceASGIApplication,
)
from app.models.proto.user_subscription_pb2 import (
    Target as ProtoTarget,
)
from app.models.proto.user_subscription_pb2 import (
    UpdateRequest,
    UpdateResponse,
)
from app.models.types import UserSubscriptionTargetId
from app.services.user_subscription_service import UserSubscriptionService


class _Service(Service):
    @override
    async def update(self, request: UpdateRequest, ctx: RequestContext):
        require_web_user()

        target = ProtoTarget.Name(request.target)
        target_id: UserSubscriptionTargetId = request.target_id  # type: ignore
        if request.is_subscribed:
            await UserSubscriptionService.subscribe(target, target_id)
        else:
            await UserSubscriptionService.unsubscribe(target, target_id)
        return UpdateResponse()


service = _Service()
asgi_app_cls = ServiceASGIApplication
