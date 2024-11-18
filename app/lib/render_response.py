from base64 import urlsafe_b64encode
from typing import Any

from shapely import get_coordinates
from starlette.responses import HTMLResponse

from app.config import API_URL
from app.lib.auth_context import auth_user
from app.lib.jinja_env import render
from app.lib.locale import map_i18next_files
from app.lib.translation import translation_locales
from app.limits import MAP_QUERY_AREA_MAX_SIZE, NOTE_QUERY_AREA_MAX_SIZE
from app.middlewares.parallel_tasks_middleware import ParallelTasksMiddleware
from app.middlewares.request_context_middleware import get_request
from app.models.db.user import Editor
from app.models.proto.shared_pb2 import WebConfig

_default_editor = Editor.get_default().value
_config_base = WebConfig(
    api_url=API_URL,
    map_query_area_max_size=MAP_QUERY_AREA_MAX_SIZE,
    note_query_area_max_size=NOTE_QUERY_AREA_MAX_SIZE,
)
_config = urlsafe_b64encode(_config_base.SerializeToString()).decode()


async def render_response(
    template_name: str,
    template_data: dict[str, Any] | None = None,
    *,
    status: int = 200,
) -> HTMLResponse:
    """
    Render the given Jinja2 template with translation, returning an HTMLResponse.
    """
    data = {
        'request': get_request(),
        'I18NEXT_FILES': map_i18next_files(translation_locales()),
        'DEFAULT_EDITOR': _default_editor,
        'WEB_CONFIG': _config,
    }

    user = auth_user()
    if user is not None:
        user_config = WebConfig.UserConfig(
            activity_tracking=user.activity_tracking,
            crash_reporting=user.crash_reporting,
        )
        user_home_point = user.home_point
        if user_home_point is not None:
            x, y = get_coordinates(user_home_point)[0].tolist()
            user_config.home_point = WebConfig.UserConfig.HomePoint(lon=x, lat=y)

        web_config = WebConfig(user_config=user_config)
        web_config.MergeFrom(_config_base)
        data['WEB_CONFIG'] = urlsafe_b64encode(web_config.SerializeToString()).decode()

        messages_count_unread = await ParallelTasksMiddleware.messages_count_unread()
        if messages_count_unread is not None:
            data['MESSAGES_COUNT_UNREAD'] = messages_count_unread

    if template_data is not None:
        data.update(template_data)
    return HTMLResponse(render(template_name, data), status_code=status)
