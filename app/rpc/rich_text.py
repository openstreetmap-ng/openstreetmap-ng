from typing import override

from connectrpc.request import RequestContext

from app.lib.auth_context import require_web_user
from app.lib.render_jinja import render_jinja
from app.lib.rich_text import rich_text
from app.models.proto.rich_text_connect import (
    RichTextService,
    RichTextServiceASGIApplication,
)
from app.models.proto.rich_text_pb2 import RenderMarkdownRequest, RenderMarkdownResponse


class _Service(RichTextService):
    @override
    async def render_markdown(
        self, request: RenderMarkdownRequest, ctx: RequestContext
    ):
        require_web_user()
        html = (await rich_text(request.text, None, 'markdown'))[0]
        return RenderMarkdownResponse(html=html or render_jinja('rich-text/_empty'))


service = _Service()
asgi_app_cls = RichTextServiceASGIApplication
