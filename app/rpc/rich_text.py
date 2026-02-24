from typing import override

from connectrpc.request import RequestContext

from app.lib.auth_context import require_web_user
from app.lib.render_jinja import render_jinja
from app.lib.rich_text import rich_text
from app.models.proto.rich_text_connect import (
    Service,
    ServiceASGIApplication,
)
from app.models.proto.rich_text_pb2 import RenderRequest, RenderResponse


class _Service(Service):
    @override
    async def render(self, request: RenderRequest, ctx: RequestContext):
        require_web_user()
        html = (await rich_text(request.text, None, 'markdown'))[0]
        return RenderResponse(html=html or render_jinja('rich-text/_empty'))


service = _Service()
asgi_app_cls = ServiceASGIApplication
