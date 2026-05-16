from typing import Any

from google.protobuf.message import Message

from app.lib.render.response import render_response


async def render_proto_page(
    state: Message,
    /,
    *,
    title_prefix: str,
    template_data: dict[str, Any] | None = None,
    status: int = 200,
):
    """Render a proto-backed page with a unified template contract."""
    data = {
        'PAGE_TYPE_NAME': state.DESCRIPTOR.full_name,
        'PAGE_STATE_BYTES': state.SerializeToString(),
        'PAGE_TITLE_PREFIX': f'{title_prefix} |',
    }
    if template_data is not None:
        data.update(template_data)

    return await render_response('proto-page', data, status=status)
