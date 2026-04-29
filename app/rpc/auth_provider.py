from typing import override

from connectrpc.request import RequestContext

from app.models.proto.auth_provider_connect import Service, ServiceASGIApplication
from app.models.proto.auth_provider_pb2 import (
    Action,
    StartAuthorizeRequest,
    StartAuthorizeResponse,
)
from app.models.proto.settings_connections_pb2 import Provider
from app.services.auth_provider_service import AuthProviderService


class _Service(Service):
    @override
    async def start_authorize(
        self,
        request: StartAuthorizeRequest,
        ctx: RequestContext,
    ):
        redirect_response = await AuthProviderService.start_authorize(
            provider=Provider.Name(request.provider),
            action=Action.Name(request.action),
            referer=request.referer if request.HasField('referer') else None,
        )
        redirect_url = redirect_response.headers.get('location')
        if redirect_url is None:
            raise RuntimeError('Missing redirect location in authorize response')

        response_headers = ctx.response_headers()
        response_headers.add('location', redirect_url)
        for set_cookie in redirect_response.headers.getlist('set-cookie'):
            response_headers.add('set-cookie', set_cookie)

        return StartAuthorizeResponse()


service = _Service()
asgi_app_cls = ServiceASGIApplication
