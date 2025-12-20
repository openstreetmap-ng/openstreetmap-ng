from base64 import urlsafe_b64encode
from typing import Any

from shapely import get_coordinates
from starlette.responses import HTMLResponse

from app.lib.auth_context import auth_user
from app.lib.locale import map_i18next_files
from app.lib.render_jinja import render_jinja
from app.lib.translation import translation_locales
from app.middlewares.parallel_tasks_middleware import ParallelTasksMiddleware
from app.middlewares.request_context_middleware import get_request
from app.models.db.user import user_avatar_url
from app.models.proto.shared_pb2 import WebConfig

_CONFIG_BASE = WebConfig()
_CONFIG_DEFAULT = urlsafe_b64encode(_CONFIG_BASE.SerializeToString()).decode()


async def render_response(
    template_name: str,
    template_data: dict[str, Any] | None = None,
    *,
    status: int = 200,
) -> HTMLResponse:
    """Render the given Jinja2 template with translation, returning an HTMLResponse."""
    data = {
        'request': get_request(),
        'I18NEXT_FILES': map_i18next_files(translation_locales()),
        'WEB_CONFIG': _CONFIG_DEFAULT,
    }

    user = auth_user()
    if user is not None:
        user_config = WebConfig.UserConfig(
            id=user['id'],
            display_name=user['display_name'],
            avatar_url=user_avatar_url(user),
            activity_tracking=user['activity_tracking'],
            crash_reporting=user['crash_reporting'],
        )

        user_home_point = user['home_point']
        if user_home_point is not None:
            x, y = get_coordinates(user_home_point)[0].tolist()
            user_config.home_point = WebConfig.UserConfig.HomePoint(lon=x, lat=y)

        messages_count_unread = await ParallelTasksMiddleware.messages_count_unread()
        user_config.messages_count_unread = messages_count_unread or 0

        reports_count = await ParallelTasksMiddleware.reports_count_attention()
        if reports_count is not None:
            user_config.reports_count_moderator = reports_count.moderator
            if reports_count.administrator is not None:
                user_config.reports_count_administrator = reports_count.administrator

        web_config = WebConfig(user_config=user_config)
        web_config.MergeFrom(_CONFIG_BASE)
        data['WEB_CONFIG'] = urlsafe_b64encode(web_config.SerializeToString()).decode()

    if template_data is not None:
        data.update(template_data)

    return HTMLResponse(render_jinja(template_name, data), status_code=status)
