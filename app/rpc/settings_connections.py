from typing import override

from connectrpc.request import RequestContext

from app.lib.auth_context import require_web_user
from app.models.proto.settings_connections_connect import (
    Service,
    ServiceASGIApplication,
)
from app.models.proto.settings_connections_pb2 import (
    Provider,
    RemoveRequest,
    RemoveResponse,
)
from app.services.connected_account_service import ConnectedAccountService


class _Service(Service):
    @override
    async def remove(self, request: RemoveRequest, ctx: RequestContext):
        require_web_user()
        await ConnectedAccountService.remove_connection(Provider.Name(request.provider))
        return RemoveResponse()


service = _Service()
asgi_app_cls = ServiceASGIApplication
